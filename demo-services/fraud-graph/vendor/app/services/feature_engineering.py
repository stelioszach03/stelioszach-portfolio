from __future__ import annotations

from math import log1p

import numpy as np

from .graph_store import GraphStore, TxEvent

CHANNEL_RISK = {
    "wire": 0.62,
    "ach": 0.35,
    "card": 0.22,
    "crypto": 0.92,
    "cash": 0.74,
}

FEATURE_ORDER = [
    "log_amount",
    "amount_z",
    "sender_out_degree",
    "receiver_in_degree",
    "sender_velocity_10m",
    "receiver_velocity_10m",
    "is_new_pair",
    "has_reverse_edge",
    "cross_border",
    "channel_risk",
    "sender_receiver_flow_ratio",
    "shared_counterparties",
    "sender_new_account",
    "receiver_new_account",
]


def _clip(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def build_edge_features(
    store: GraphStore,
    event: TxEvent,
    *,
    amount_z_warmup_events: int = 6,
) -> tuple[np.ndarray, dict[str, float]]:
    sender_mean, sender_std = store.sender_amount_stats(event.sender_id)
    sender_seen = store.sender_event_count(event.sender_id)
    warmup_n = max(1, int(amount_z_warmup_events))

    if sender_seen < warmup_n:
        global_mean, global_std = store.global_amount_stats()
        alpha = float(sender_seen) / float(warmup_n)
        mean = alpha * sender_mean + (1.0 - alpha) * global_mean
        std = alpha * sender_std + (1.0 - alpha) * global_std
    else:
        mean = sender_mean
        std = sender_std

    amount_z_raw = (float(event.amount) - float(mean)) / max(float(std), 1.0)

    sender_out = float(store.out_degree(event.sender_id))
    receiver_in = float(store.in_degree(event.receiver_id))

    sender_vel = float(store.recent_count(event.sender_id, seconds=600, direction="sender"))
    receiver_vel = float(store.recent_count(event.receiver_id, seconds=600, direction="receiver"))

    is_new_pair = 0.0 if store.has_seen_pair(event.sender_id, event.receiver_id) else 1.0
    has_reverse = 1.0 if store.has_reverse_edge(event.sender_id, event.receiver_id) else 0.0
    cross_border = 1.0 if event.country_from != event.country_to else 0.0

    sender_out_total, _ = store.totals(event.sender_id)
    _, receiver_in_total = store.totals(event.receiver_id)
    flow_ratio = sender_out_total / max(1.0, receiver_in_total)

    shared = float(store.shared_counterparties(event.sender_id, event.receiver_id))

    sender_age = store.account_age_seconds(event.sender_id)
    receiver_age = store.account_age_seconds(event.receiver_id)
    sender_new = 1.0 if 0.0 < sender_age < 3600.0 else 0.0
    receiver_new = 1.0 if 0.0 < receiver_age < 3600.0 else 0.0

    feature_map = {
        "log_amount": _clip(log1p(max(event.amount, 0.0)) / 11.5, 0.0, 1.2),
        "amount_z": _clip((amount_z_raw + 1.0) / 6.0, 0.0, 1.2),
        "sender_out_degree": _clip(sender_out / 40.0, 0.0, 1.0),
        "receiver_in_degree": _clip(receiver_in / 40.0, 0.0, 1.0),
        "sender_velocity_10m": _clip(sender_vel / 20.0, 0.0, 1.0),
        "receiver_velocity_10m": _clip(receiver_vel / 20.0, 0.0, 1.0),
        "is_new_pair": is_new_pair,
        "has_reverse_edge": has_reverse,
        "cross_border": cross_border,
        "channel_risk": float(CHANNEL_RISK.get(event.channel, 0.45)),
        "sender_receiver_flow_ratio": _clip(log1p(flow_ratio) / 4.5, 0.0, 1.0),
        "shared_counterparties": _clip(shared / 8.0, 0.0, 1.0),
        "sender_new_account": sender_new,
        "receiver_new_account": receiver_new,
    }

    vector = np.array([feature_map[name] for name in FEATURE_ORDER], dtype=np.float32)
    return vector, feature_map
