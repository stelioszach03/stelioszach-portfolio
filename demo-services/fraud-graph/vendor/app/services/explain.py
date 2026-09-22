from __future__ import annotations

from typing import Iterable

HUMAN_LABEL = {
    "amount_z": "Amount is far above sender baseline",
    "sender_velocity_10m": "Sender velocity spike in last 10m",
    "receiver_velocity_10m": "Receiver is absorbing abnormal flow",
    "is_new_pair": "First-time relationship between sender and receiver",
    "has_reverse_edge": "Bidirectional circular transfer pattern detected",
    "cross_border": "Cross-border payment path",
    "channel_risk": "High-risk payment channel",
    "sender_new_account": "Sender account is very new",
    "receiver_new_account": "Receiver account is very new",
    "sender_receiver_flow_ratio": "Flow asymmetry suggests mule behavior",
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
    for name, _ in sorted(weighted, key=lambda kv: kv[1], reverse=True):
        if len(out) >= limit:
            break
        if name not in HUMAN_LABEL:
            continue

        value = float(feature_map.get(name, 0.0))
        if value <= 0 and name not in {"amount_z"}:
            continue
        out.append(HUMAN_LABEL[name])

    if not out:
        out.append("No single dominant signal; risk comes from combined graph context")
    return out
