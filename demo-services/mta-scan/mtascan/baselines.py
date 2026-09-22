"""Three deliberately boring baselines the online model has to beat.

Without these the replay evaluation says nothing: "the model flags the
incidents" is not a result if a five-line z-score rule flags them too. Ported
from the upstream `evaluation/baselines.py` with identical arithmetic, minus
pandas — they now stream row by row like everything else.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class BaselineBank:
    """Streaming version of the three baselines. Feed rows in observed order."""

    def __init__(self) -> None:
        # EWMA is the only stateful one: level + variance per route-stop.
        self._ewma: dict[tuple[str, str], tuple[float | None, float]] = {}

    def score(self, row: dict[str, Any]) -> dict[str, float]:
        headway = float(row.get("headway_sec") or 0.0)

        # 1. rolling z-score against the recent local mean/std
        zscore = _clip01(
            max(float(row.get("headway_delta_mean", 0.0) or 0.0), 0.0)
            / max(float(row.get("rolling_std_6", 0.0) or 0.0), 30.0)
            / 4.0
        )

        # 2. fixed threshold on the station's own recent median
        limit = max(
            float(row.get("station_median_24", 0.0) or 0.0) * 1.75,
            float(row.get("rolling_q90_12", 0.0) or 0.0) * 1.05,
        )
        limit = max(limit, 300.0)
        threshold = _clip01(max(headway - limit, 0.0) / max(limit * 0.75, 60.0))

        # 3. EWMA forecast error
        key = (str(row.get("route_id", "")), str(row.get("stop_id", "")))
        level, variance = self._ewma.get(key, (None, 0.0))
        alpha = 0.35
        prediction = headway if level is None else level
        error = headway - prediction
        scale = max(math.sqrt(max(variance, 0.0)), 45.0)
        ewma = _clip01(max(abs(error) - 30.0, 0.0) / (3.0 * scale))
        new_level = headway if level is None else alpha * headway + (1.0 - alpha) * level
        new_variance = alpha * (error ** 2) + (1.0 - alpha) * variance
        self._ewma[key] = (new_level, new_variance)

        return {
            "baseline_zscore": float(zscore),
            "baseline_threshold": float(threshold),
            "baseline_threshold_limit_sec": float(limit),
            "baseline_ewma": float(ewma),
            "baseline_ewma_prediction_sec": float(prediction),
        }


def add_baseline_scores(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    bank = BaselineBank()
    out: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        merged.update(bank.score(row))
        out.append(merged)
    return out
