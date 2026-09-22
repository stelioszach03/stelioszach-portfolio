from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from ml.gnn import EdgeMLP, load_edge_model

from .explain import reasons_from_contributions, top_features
from .feature_engineering import FEATURE_ORDER, build_edge_features
from .graph_store import GraphStore, TxEvent

HEURISTIC_WEIGHTS: dict[str, float] = {
    "log_amount": 0.32,
    "amount_z": 0.90,
    "sender_out_degree": 0.12,
    "receiver_in_degree": 0.12,
    "sender_velocity_10m": 0.45,
    "receiver_velocity_10m": 0.35,
    "is_new_pair": 0.50,
    "has_reverse_edge": 0.70,
    "cross_border": 0.50,
    "channel_risk": 0.55,
    "sender_receiver_flow_ratio": 0.28,
    "shared_counterparties": 0.24,
    "sender_new_account": 0.30,
    "receiver_new_account": 0.30,
}


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _risk_band(score: float) -> str:
    if score < 0.45:
        return "low"
    if score < 0.70:
        return "medium"
    if score < 0.85:
        return "high"
    return "critical"


class FraudScoringService:
    def __init__(
        self,
        store: GraphStore,
        model_path: str,
        alert_min_score: float = 0.82,
        model_blend_weight: float = 0.15,
        model_uplift_only: bool = True,
        amount_z_warmup_events: int = 6,
    ) -> None:
        self.store = store
        self.model_path = model_path
        self.alert_min_score = float(alert_min_score)
        self.model_blend_weight = _clip01(float(model_blend_weight))
        self.model_uplift_only = bool(model_uplift_only)
        self.amount_z_warmup_events = max(1, int(amount_z_warmup_events))
        self.model: EdgeMLP | None = self._load_model(model_path)

    @staticmethod
    def _load_model(model_path: str) -> EdgeMLP | None:
        p = Path(model_path)
        if not p.exists():
            return None
        try:
            model = load_edge_model(path=str(p), input_dim=len(FEATURE_ORDER))
            model.eval()
            return model
        except Exception:
            return None

    def _heuristic_score(self, feature_map: dict[str, float]) -> tuple[float, list[tuple[str, float]]]:
        raw = -1.30
        weighted: list[tuple[str, float]] = []
        for name in FEATURE_ORDER:
            value = float(feature_map.get(name, 0.0))
            w = float(HEURISTIC_WEIGHTS.get(name, 0.0))
            contribution = w * value
            raw += contribution
            weighted.append((name, contribution))

        calibrated = _sigmoid(raw / 1.15)
        return _clip01(calibrated), weighted

    def _model_score(self, vector: np.ndarray) -> float | None:
        if self.model is None:
            return None
        with torch.no_grad():
            x = torch.tensor(vector, dtype=torch.float32).unsqueeze(0)
            logit = self.model(x).squeeze(0)
            prob = torch.sigmoid(logit).item()
        return _clip01(float(prob))

    def score(self, event: TxEvent) -> dict:
        vector, feature_map = build_edge_features(
            self.store,
            event,
            amount_z_warmup_events=self.amount_z_warmup_events,
        )
        heuristic_score, weighted = self._heuristic_score(feature_map)
        model_score = self._model_score(vector)

        if model_score is None:
            final = heuristic_score
        else:
            heuristic_w = 1.0 - self.model_blend_weight
            blended = _clip01((heuristic_w * heuristic_score) + (self.model_blend_weight * model_score))
            # Prevent low-confidence model outputs from suppressing strong rule signal.
            final = max(heuristic_score, blended) if self.model_uplift_only else blended

        band = _risk_band(final)
        reasons = reasons_from_contributions(weighted=weighted, feature_map=feature_map)
        processed_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

        payload = {
            "tx_id": event.tx_id,
            "risk_score": round(final, 6),
            "risk_band": band,
            "model_score": round(model_score, 6) if model_score is not None else None,
            "heuristic_score": round(heuristic_score, 6),
            "reasons": reasons,
            "top_features": top_features(feature_map),
            "processed_at_utc": processed_at_utc,
            "sender_id": event.sender_id,
            "receiver_id": event.receiver_id,
            "amount": float(event.amount),
            "timestamp_utc": event.timestamp_utc.isoformat(),
        }

        self.store.add_event(event=event, risk_score=final, risk_band=band, reasons=reasons)
        if final >= self.alert_min_score:
            self.store.add_alert(payload)
        return payload
