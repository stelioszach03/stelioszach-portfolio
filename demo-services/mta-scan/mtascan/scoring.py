"""Online anomaly scoring — River, CPU, no labels, no torch.

Ported unchanged (arithmetic-wise) from the upstream ``worker/ml_online.py``
so the replay numbers still reproduce. What changed is everything around it:

* the PyTorch denoising-autoencoder shadow model is **gone**. It cost ~1 GB of
  disk (CUDA wheels on linux/x86_64) and ~400 MB of RSS, and nothing in the UI
  ever displayed its output;
* checkpoints are a single file rewritten atomically instead of a rotating set,
  so the model directory cannot grow at all.

The pipeline itself is unchanged: a PARegressor predicts the headway, the
residual is calibrated against a rolling residual quantile, HalfSpaceTrees adds
an unsupervised second opinion, and ADWIN resets the learners on drift.
"""
from __future__ import annotations

import json
import os
import pickle
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from river import anomaly, drift, linear_model, preprocessing

from .features import feature_vector_from_row, reason_candidates


@dataclass
class ModelTelemetry:
    rows_seen: int = 0
    rows_scored: int = 0
    drift_events: int = 0
    mae_ema: float = 0.0
    residual_q90: float = 0.0
    residual_q99: float = 0.0
    last_batch_scored: int = 0
    last_run_utc: str | None = None


@dataclass
class ModelBundle:
    reg: Any
    hst: Any
    adwin: Any
    telemetry: ModelTelemetry = field(default_factory=ModelTelemetry)
    residual_buffer: list = field(default_factory=list)


def new_bundle() -> ModelBundle:
    return ModelBundle(
        reg=preprocessing.StandardScaler() | linear_model.PARegressor(),
        hst=anomaly.HalfSpaceTrees(seed=42),
        adwin=drift.ADWIN(),
        telemetry=ModelTelemetry(),
        residual_buffer=[],
    )


def _clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _online_context_features(row: dict[str, Any], residual: float) -> dict[str, float]:
    return {
        "residual": float(residual),
        "hour": float(row.get("hour", 0.0) or 0.0),
        "is_peak": float(row.get("is_peak", 0.0) or 0.0),
        "rolling_zscore": float(row.get("rolling_zscore", 0.0) or 0.0),
        "station_baseline_deviation": float(row.get("station_baseline_deviation", 0.0) or 0.0),
        "feed_delay_sec": float(row.get("feed_delay_sec", 0.0) or 0.0),
    }


def _context_deviation_score(row: dict[str, Any]) -> float:
    rolling = max(float(row.get("rolling_zscore", 0.0) or 0.0), 0.0) / 3.5
    station = max(float(row.get("station_baseline_deviation", 0.0) or 0.0), 0.0) / 3.0
    quantile = max(float(row.get("quantile_band_deviation", 0.0) or 0.0), 0.0) / 2.75
    trend = max(float(row.get("lag_ratio", 1.0) or 1.0) - 1.0, 0.0) / 1.2
    delay = float(row.get("feed_delay_sec", 0.0) or 0.0) / 120.0
    weather = float(row.get("weather_severity", 0.0) or 0.0) / 3.0
    service = float(row.get("service_alert_active", 0.0) or 0.0) * 0.35
    return _clip01(
        0.28 * rolling
        + 0.26 * station
        + 0.18 * quantile
        + 0.13 * trend
        + 0.08 * delay
        + 0.04 * weather
        + 0.03 * service
    )


def _summarize_reasons(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in reason_candidates(row) if float(c.get("score", 0.0)) >= 0.3][:3]


def _trim_residual_buffer(buffer: list, max_len: int = 8000) -> None:
    if len(buffer) > max_len:
        del buffer[:-max_len]


def _self_supervised_residual_score(
    abs_residual: float, ema_scale: float, residual_buffer: list
) -> tuple[float, float, float]:
    if abs_residual <= 0:
        return 0.0, 0.0, 0.0

    if len(residual_buffer) >= 64:
        arr = np.asarray(residual_buffer, dtype=float)
        q50 = float(np.percentile(arr, 50.0))
        q90 = float(np.percentile(arr, 90.0))
        q99 = float(np.percentile(arr, 99.0))
        spread = max(q99 - q50, 1.0)
        return _clip01((abs_residual - q50) / spread), q90, q99

    scale = max(ema_scale, 1.0)
    return _clip01(abs_residual / (3.5 * scale)), 0.0, 0.0


def _adwin_drifted(monitor: Any, value: float) -> bool:
    monitor.update(value)
    return bool(
        getattr(monitor, "drift_detected", False) or getattr(monitor, "change_detected", False)
    )


def score_feature_row(bundle: ModelBundle, row: dict[str, Any], learn: bool = True) -> dict[str, Any]:
    """Score one enriched observation. Identical arithmetic to the upstream repo."""
    y = float(row.get("headway_sec", 0.0) or 0.0)
    if y <= 0:
        raise ValueError("headway_sec must be positive")

    x = feature_vector_from_row(row)
    baseline_prediction = float(row.get("rolling_mean_6", y) or y)
    try:
        reg_prediction = bundle.reg.predict_one(x)
        y_hat = baseline_prediction if reg_prediction is None else (
            0.65 * float(reg_prediction) + 0.35 * baseline_prediction
        )
    except Exception:
        y_hat = baseline_prediction

    residual = float(y - y_hat)
    abs_residual = abs(residual)

    if bundle.telemetry.rows_seen == 0:
        bundle.telemetry.mae_ema = abs_residual
    else:
        bundle.telemetry.mae_ema = 0.92 * bundle.telemetry.mae_ema + 0.08 * abs_residual

    ssl_score, q90, q99 = _self_supervised_residual_score(
        abs_residual=abs_residual,
        ema_scale=bundle.telemetry.mae_ema,
        residual_buffer=bundle.residual_buffer,
    )

    hst_context = _online_context_features(row, residual=residual)
    try:
        hst_score = float(bundle.hst.score_one(hst_context))
        if learn:
            bundle.hst.learn_one(hst_context)
    except Exception:
        hst_score = 0.0

    relative_error_score = _clip01(abs_residual / max(abs(y_hat), baseline_prediction, 120.0))
    context_score = _context_deviation_score(row)
    station_score = _clip01(max(float(row.get("station_baseline_deviation", 0.0) or 0.0), 0.0) / 2.8)
    trend_score = _clip01(max(float(row.get("lag_ratio", 1.0) or 1.0) - 1.0, 0.0) / 1.0)
    quantile_score = _clip01(max(float(row.get("quantile_band_deviation", 0.0) or 0.0), 0.0) / 2.2)

    anomaly_score = _clip01(
        0.28 * ssl_score
        + 0.18 * _clip01(hst_score)
        + 0.16 * relative_error_score
        + 0.22 * context_score
        + 0.10 * station_score
        + 0.06 * trend_score
    )
    anomaly_score = max(anomaly_score, _clip01(0.62 * station_score + 0.38 * quantile_score))

    drifted = False
    if learn:
        try:
            drifted = _adwin_drifted(bundle.adwin, abs_residual)
        except Exception:
            drifted = False
        if drifted:
            bundle.telemetry.drift_events += 1
            bundle.reg = preprocessing.StandardScaler() | linear_model.PARegressor()
            bundle.hst = anomaly.HalfSpaceTrees(seed=42)
        try:
            bundle.reg.learn_one(x, y)
        except Exception:
            pass
        bundle.residual_buffer.append(abs_residual)
        _trim_residual_buffer(bundle.residual_buffer)
        bundle.telemetry.rows_seen += 1

    return {
        "predicted_headway_sec": float(y_hat),
        "residual": float(residual),
        "anomaly_score": float(anomaly_score),
        "ssl_score": float(ssl_score),
        "hst_score": float(_clip01(hst_score)),
        "relative_error_score": float(relative_error_score),
        "context_score": float(context_score),
        "station_score": float(station_score),
        "trend_score": float(trend_score),
        "quantile_score": float(quantile_score),
        "residual_q90": float(q90),
        "residual_q99": float(q99),
        "drifted": bool(drifted),
        "reasons": _summarize_reasons(row),
    }


# --------------------------------------------------------------------------
# Persistence — one file, rewritten atomically. Bounded by construction.
#
# SECURITY NOTE ON PICKLE. River learners hold live sklearn-style objects with
# no stable serialisation format, so the checkpoint is a pickle. Unpickling
# executes code, so the trust boundary matters: this file is written only by
# this service, into systemd's StateDirectory. Under `DynamicUser=yes` that is
# /var/lib/private/mta-scan, mode 0700, owned by this unit's transient UID —
# no other service and no unprivileged user on the box can write it, and the
# unit itself runs with ProtectSystem=strict and no other writable path.
# It is never uploaded, never user-supplied, and never read from anywhere else.
# A corrupt or foreign file fails `isinstance(obj, ModelBundle)` and the
# service starts from a fresh model rather than trusting it.
# --------------------------------------------------------------------------

def save_bundle(path: str | Path, bundle: ModelBundle) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    bundle.telemetry.last_run_utc = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            pickle.dump(bundle, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    telemetry_path = target.parent / "telemetry.json"
    tmp_telemetry = telemetry_path.with_suffix(".json.tmp")
    tmp_telemetry.write_text(json.dumps(asdict(bundle.telemetry), indent=2), encoding="utf-8")
    os.replace(tmp_telemetry, telemetry_path)
    return target


def load_bundle(path: str | Path) -> Optional[ModelBundle]:
    target = Path(path)
    if not target.exists():
        return None
    try:
        with target.open("rb") as handle:
            obj = pickle.load(handle)
    except Exception:
        return None
    if not isinstance(obj, ModelBundle):
        return None
    if not isinstance(getattr(obj, "telemetry", None), ModelTelemetry):
        obj.telemetry = ModelTelemetry()
    if not isinstance(getattr(obj, "residual_buffer", None), list):
        obj.residual_buffer = []
    if getattr(obj, "adwin", None) is None:
        obj.adwin = drift.ADWIN()
    return obj


def load_or_new(path: str | Path) -> ModelBundle:
    return load_bundle(path) or new_bundle()
