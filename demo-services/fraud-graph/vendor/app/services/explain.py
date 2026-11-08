from __future__ import annotations

from typing import Iterable
from math import isfinite

HUMAN_LABEL = {
    "amount_z": "Normalized amount-deviation feature",
    "sender_velocity_10m": "Normalized sender activity in the last 10 minutes",
    "receiver_velocity_10m": "Normalized receiver activity in the last 10 minutes",
    "is_new_pair": "First-time relationship between sender and receiver",
    "has_reverse_edge": "A reverse payment edge exists in the observed graph",
    "cross_border": "Cross-border payment path",
    "channel_risk": "Channel heuristic prior",
    "sender_new_account": "Sender has less than one hour of observed graph history",
    "receiver_new_account": "Receiver has less than one hour of observed graph history",
    "sender_receiver_flow_ratio": "Normalized sender-outflow / receiver-inflow feature",
}

NUMERIC_FEATURES = {
    "amount_z", "sender_velocity_10m", "receiver_velocity_10m",
    "channel_risk", "sender_receiver_flow_ratio",
}


def top_features(feature_map: dict[str, float], limit: int = 6) -> dict[str, float]:
    ordered = sorted(feature_map.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return {k: round(float(v), 4) for k, v in ordered[:limit]}


def reasons_from_contributions(
    weighted: Iterable[tuple[str, float]],
    feature_map: dict[str, float],
    limit: int = 4,
) -> list[str]:
    out: list[str] = []
    for name, contribution in sorted(weighted, key=lambda kv: kv[1], reverse=True):
        if len(out) >= limit:
            break
        if name not in HUMAN_LABEL:
            continue

        value = float(feature_map.get(name, 0.0))
        if not isfinite(value) or not isfinite(contribution) or value <= 0 or contribution <= 0:
            continue
        # Feature values are normalized inputs, not evidence of abnormality or
        # model attributions. A positive amount_z can even mean below baseline:
        # feature_engineering applies clip((raw_z + 1) / 6, 0, 1.2).
        label = HUMAN_LABEL[name]
        out.append(f"{label}: {value:.3f}" if name in NUMERIC_FEATURES else label)

    if not out:
        out.append("No positive named heuristic features in this snapshot")
    return out
