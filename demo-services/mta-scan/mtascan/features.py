"""Incremental feature engineering — one implementation, used everywhere.

The upstream project built features with a pandas ``groupby`` + ``rolling``
pass over the whole history. That is fine for a 216-row replay file and
hopeless for a live service: the same pass over a 48-hour window is hundreds
of thousands of rows every 30 seconds.

This module computes the *same* features one observation at a time from a
bounded per-(route, stop) ring buffer, so cost per row is O(24) and memory is
O(active stops). ``tests/test_features_equivalence.py`` asserts, column by
column, that it reproduces the pandas implementation from the original repo to
1e-9 — that is why the replay metrics below are still the repo's measured
numbers and not new ones.

pandas semantics that had to be preserved exactly:

* every rolling window is over ``headway_sec.shift(1)`` — the *previous*
  headways at that route-stop, never the current one (no leakage);
* ``min_periods`` counts non-NaN entries, so the first rows of a group fall
  back through the documented ``fillna`` chain;
* ``rolling.std()`` is the sample standard deviation (ddof=1);
* ``rolling.quantile(q)`` uses linear interpolation, i.e. ``np.percentile``.
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable

import numpy as np


NUMERIC_FEATURE_COLUMNS: tuple[str, ...] = (
    "hour",
    "day_of_week",
    "is_weekend",
    "is_peak",
    "route_hash",
    "stop_hash",
    "direction_code",
    "route_direction_hash",
    "lag_headway_1",
    "lag_headway_2",
    "observation_gap_sec",
    "rolling_mean_6",
    "rolling_std_6",
    "rolling_q10_12",
    "rolling_q50_12",
    "rolling_q90_12",
    "station_median_24",
    "station_mad_24",
    "headway_delta_mean",
    "headway_delta_lag",
    "lag_ratio",
    "rolling_zscore",
    "station_baseline_deviation",
    "quantile_band_deviation",
    "event_lead_sec",
    "feed_delay_sec",
    "stale_update_flag",
    "precipitation_mm",
    "weather_severity",
    "service_alert_active",
    "service_alert_severity",
)

FEATURE_DESCRIPTIONS: dict[str, str] = {
    "hour": "UTC hour-of-day for strong service-period effects.",
    "day_of_week": "Weekday context so weekday commute patterns do not look anomalous at baseline.",
    "is_weekend": "Weekend service patterns differ materially from weekday operations.",
    "is_peak": "Rush-hour indicator for the AM/PM commute windows.",
    "lag_headway_1": "Previous observed headway at the same route-stop pair.",
    "lag_headway_2": "Second-most recent headway for short-memory trend context.",
    "rolling_mean_6": "Recent local moving average for the route-stop headway.",
    "rolling_std_6": "Recent local volatility so large swings score higher only when unusual.",
    "rolling_q10_12": "Lower rolling quantile used to contextualize the current headway band.",
    "rolling_q90_12": "Upper rolling quantile used to contextualize the current headway band.",
    "station_baseline_deviation": "Deviation from the recent station-local baseline, scaled by robust MAD.",
    "feed_delay_sec": "How stale the GTFS event is relative to observation time.",
    "stale_update_flag": "Binary indicator for delayed/stale feed updates.",
    "direction_code": "Direction inferred from stop_id suffix when available (for example N/S).",
    "precipitation_mm": "Optional weather hook for replay or production enrichment.",
    "service_alert_active": "Optional service-alert hook for route-level incident context.",
}

# Longest rolling window in use. Keeping exactly this many previous headways is
# what bounds the collector's memory no matter how long it runs.
MAX_HISTORY = 24

# Below this many headways a stop has no usable MAD, so
# `station_baseline_deviation` falls back to a 30-second floor and saturates on
# any ordinary overnight variation. Used by the deviation maths below and by
# `FeatureEngine.history_stats()`; they must agree, so it lives here.
_MIN_HISTORY_FOR_MAD = 3


def safe_hash(value: str, mod: int) -> float:
    """Stable hash of a categorical value into [0, 1).

    blake2b rather than the builtin ``hash``: CPython randomises string hashing
    per process, which made a station's feature value change after every
    restart and the replay evaluation non-reproducible run to run.
    """
    if not value:
        return 0.0
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return float(int.from_bytes(digest, "big") % mod) / float(mod)


def direction_from_stop_id(stop_id: str) -> str:
    cleaned = (stop_id or "").strip().upper()
    if not cleaned:
        return "U"
    suffix = cleaned[-1]
    if suffix in {"N", "S", "E", "W"}:
        return suffix
    return "U"


def direction_code(stop_id: str) -> float:
    return {"N": 1.0, "S": -1.0, "E": 0.5, "W": -0.5}.get(direction_from_stop_id(stop_id), 0.0)


def is_peak(hour: int, day_of_week: int) -> float:
    if day_of_week >= 5:
        return 0.0
    return 1.0 if hour in {7, 8, 9, 16, 17, 18, 19} else 0.0


def _mad(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")
    median = float(np.median(arr))
    return float(np.median(np.abs(arr - median)))


def _to_epoch(value: Any) -> float | None:
    """Accept datetime, epoch number or ISO-8601 string; return epoch seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if not np.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).timestamp()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()


@dataclass
class _KeyState:
    """Bounded per route-stop memory: the last 24 headways and the last stamp."""

    history: Deque[float] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    prev_observed_epoch: float | None = None


class FeatureEngine:
    """Streaming feature builder.

    Feed observations in ascending ``observed_ts`` order (which is how both the
    live collector and the replay file produce them) and each call returns the
    full numeric feature row for that observation.
    """

    def __init__(self) -> None:
        self._state: Dict[tuple[str, str], _KeyState] = {}

    # -- housekeeping ----------------------------------------------------
    def active_keys(self) -> int:
        return len(self._state)

    def history_stats(self) -> dict[str, float]:
        """How full the per-stop windows are — the real readiness signal.

        This state is **in-memory only**. The model checkpoint persists across
        restarts but these windows do not, so a cumulative counter like
        ``telemetry.rows_seen`` keeps climbing while the windows it is supposed
        to describe are empty again. Anything that reports "is the model ready"
        has to ask here instead, or it will claim ready on a freshly restarted
        process whose scores are all pinned to 1.00.

        ``ready`` counts stops with at least ``_MIN_HISTORY_FOR_MAD`` headways,
        which is where a real MAD replaces the 30-second floor in
        ``station_baseline_deviation`` and the score stops saturating.
        """
        keys = len(self._state)
        if not keys:
            return {"keys": 0, "ready": 0, "ready_fraction": 0.0, "mean_history": 0.0}
        lengths = [len(state.history) for state in self._state.values()]
        ready = sum(1 for n in lengths if n >= _MIN_HISTORY_FOR_MAD)
        return {
            "keys": keys,
            "ready": ready,
            "ready_fraction": ready / keys,
            "mean_history": sum(lengths) / keys,
        }

    def evict_older_than(self, cutoff_epoch: float) -> int:
        """Drop route-stops that stopped reporting, so memory stays bounded."""
        stale = [
            key
            for key, state in self._state.items()
            if state.prev_observed_epoch is not None and state.prev_observed_epoch < cutoff_epoch
        ]
        for key in stale:
            del self._state[key]
        return len(stale)

    # -- the actual work -------------------------------------------------
    def compute(
        self,
        *,
        route_id: str,
        stop_id: str,
        observed_ts: Any,
        headway_sec: float,
        event_ts: Any = None,
        precipitation_mm: float = 0.0,
        weather_severity: float = 0.0,
        service_alert_active: float = 0.0,
        service_alert_severity: float = 0.0,
        learn: bool = True,
    ) -> dict[str, float]:
        route_id = str(route_id or "")
        stop_id = str(stop_id or "")
        headway = float(headway_sec)
        observed_epoch = _to_epoch(observed_ts)
        if observed_epoch is None:
            raise ValueError("observed_ts must be a parseable timestamp")
        event_epoch = _to_epoch(event_ts)

        key = (route_id, stop_id)
        state = self._state.get(key)
        if state is None:
            state = _KeyState()
            self._state[key] = state

        history = list(state.history)  # previous headways, oldest -> newest

        # --- lags --------------------------------------------------------
        lag_1 = history[-1] if history else headway
        lag_2 = history[-2] if len(history) >= 2 else lag_1
        if state.prev_observed_epoch is None:
            observation_gap = lag_1
        else:
            observation_gap = observed_epoch - state.prev_observed_epoch

        # --- rolling windows over the PREVIOUS headways ------------------
        w6 = history[-6:]
        w12 = history[-12:]
        w24 = history[-24:]

        rolling_mean_6 = float(np.mean(w6)) if len(w6) >= 1 else headway
        rolling_std_6 = float(np.std(np.asarray(w6, dtype=float), ddof=1)) if len(w6) >= 2 else 0.0

        if len(w12) >= 3:
            arr12 = np.asarray(w12, dtype=float)
            q10 = float(np.percentile(arr12, 10.0))
            q50 = float(np.percentile(arr12, 50.0))
            q90 = float(np.percentile(arr12, 90.0))
        else:
            q10 = q50 = q90 = rolling_mean_6

        if len(w24) >= _MIN_HISTORY_FOR_MAD:
            arr24 = np.asarray(w24, dtype=float)
            station_median_24 = float(np.median(arr24))
            station_mad_24 = _mad(arr24)
            if not np.isfinite(station_mad_24):
                station_mad_24 = 0.0
        else:
            station_median_24 = rolling_mean_6
            station_mad_24 = 0.0

        std_floor = max(rolling_std_6, 30.0)
        mad_floor = max(station_mad_24, 30.0)
        quantile_band = max(q90 - q10, 45.0)

        headway_delta_mean = headway - rolling_mean_6
        headway_delta_lag = headway - lag_1
        lag_ratio = headway / max(lag_1, 60.0)
        rolling_zscore = headway_delta_mean / std_floor
        station_baseline_deviation = (headway - station_median_24) / mad_floor
        quantile_band_deviation = (headway - q50) / quantile_band

        # --- calendar + categorical --------------------------------------
        observed_dt = datetime.fromtimestamp(observed_epoch, tz=timezone.utc)
        hour = float(observed_dt.hour)
        day_of_week = float(observed_dt.weekday())

        # --- feed freshness ----------------------------------------------
        event_delta = 0.0 if event_epoch is None else (event_epoch - observed_epoch)
        event_lead_sec = min(max(event_delta, 0.0), 7200.0)
        feed_delay_sec = min(max(-event_delta, 0.0), 7200.0)

        row: dict[str, float] = {
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": 1.0 if day_of_week >= 5 else 0.0,
            "is_peak": is_peak(int(hour), int(day_of_week)),
            "route_hash": safe_hash(route_id, 997),
            "stop_hash": safe_hash(stop_id, 4093),
            "direction_code": direction_code(stop_id),
            "route_direction_hash": safe_hash(f"{route_id}:{direction_from_stop_id(stop_id)}", 1237),
            "lag_headway_1": float(lag_1),
            "lag_headway_2": float(lag_2),
            "observation_gap_sec": float(observation_gap),
            "rolling_mean_6": float(rolling_mean_6),
            "rolling_std_6": float(rolling_std_6),
            "rolling_q10_12": float(q10),
            "rolling_q50_12": float(q50),
            "rolling_q90_12": float(q90),
            "station_median_24": float(station_median_24),
            "station_mad_24": float(station_mad_24),
            "headway_delta_mean": float(headway_delta_mean),
            "headway_delta_lag": float(headway_delta_lag),
            "lag_ratio": float(lag_ratio),
            "rolling_zscore": float(rolling_zscore),
            "station_baseline_deviation": float(station_baseline_deviation),
            "quantile_band_deviation": float(quantile_band_deviation),
            "event_lead_sec": float(event_lead_sec),
            "feed_delay_sec": float(feed_delay_sec),
            "stale_update_flag": 1.0 if feed_delay_sec > 30.0 else 0.0,
            "precipitation_mm": float(precipitation_mm or 0.0),
            "weather_severity": float(weather_severity or 0.0),
            "service_alert_active": float(service_alert_active or 0.0),
            "service_alert_severity": float(service_alert_severity or 0.0),
        }

        # Guard against a NaN ever reaching the model: the pandas version ended
        # with `to_numeric(...).fillna(0.0)` over every feature column.
        for column in NUMERIC_FEATURE_COLUMNS:
            value = row.get(column, 0.0)
            if value is None or not np.isfinite(value):
                row[column] = 0.0

        row["headway_sec"] = headway
        row["route_id"] = route_id  # type: ignore[assignment]
        row["stop_id"] = stop_id  # type: ignore[assignment]

        if learn:
            state.history.append(headway)
            state.prev_observed_epoch = observed_epoch

        return row


def feature_vector_from_row(row: dict[str, Any]) -> dict[str, float]:
    vector: dict[str, float] = {}
    for column in NUMERIC_FEATURE_COLUMNS:
        try:
            vector[column] = float(row.get(column, 0.0))
        except (TypeError, ValueError):
            vector[column] = 0.0
    return vector


def reason_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Human-readable drivers, ranked. Same weights as the original repo."""
    candidates = [
        {
            "key": "station_baseline_deviation",
            "label": "station baseline deviation",
            "score": abs(float(row.get("station_baseline_deviation", 0.0) or 0.0)),
        },
        {
            "key": "rolling_zscore",
            "label": "rolling z-score jump",
            "score": abs(float(row.get("rolling_zscore", 0.0) or 0.0)),
        },
        {
            "key": "lag_ratio",
            "label": "headway jump vs previous train",
            "score": abs(float(row.get("lag_ratio", 1.0) or 1.0) - 1.0) * 2.0,
        },
        {
            "key": "feed_delay_sec",
            "label": "stale feed update",
            "score": float(row.get("feed_delay_sec", 0.0) or 0.0) / 60.0,
        },
        {
            "key": "precipitation_mm",
            "label": "weather pressure",
            "score": float(row.get("precipitation_mm", 0.0) or 0.0) / 3.0,
        },
        {
            "key": "service_alert_active",
            "label": "service alert context",
            "score": float(row.get("service_alert_active", 0.0) or 0.0)
            * max(float(row.get("service_alert_severity", 1.0) or 1.0), 1.0),
        },
    ]
    return sorted(candidates, key=lambda item: float(item["score"]), reverse=True)


def build_feature_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convenience: run a whole sequence through a fresh engine (replay path)."""
    engine = FeatureEngine()
    out: list[dict[str, Any]] = []
    for record in records:
        features = engine.compute(
            route_id=record.get("route_id", ""),
            stop_id=record.get("stop_id", ""),
            observed_ts=record.get("observed_ts"),
            headway_sec=float(record.get("headway_sec") or 0.0),
            event_ts=record.get("event_ts"),
            precipitation_mm=float(record.get("precipitation_mm") or 0.0),
            weather_severity=float(record.get("weather_severity") or 0.0),
            service_alert_active=float(record.get("service_alert_active") or 0.0),
            service_alert_severity=float(record.get("service_alert_severity") or 0.0),
        )
        merged = dict(record)
        merged.update(features)
        out.append(merged)
    return out
