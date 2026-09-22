from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "vendor"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _label_rule(tx) -> float:
    suspicious_ring = 1.0 if tx.sender_id.startswith("RING_") or tx.receiver_id.startswith("RING_") else 0.0
    high_amount = 1.0 if tx.amount >= 9000 else 0.0
    cross_border = 1.0 if tx.country_from != tx.country_to else 0.0
    high_risk_channel = 1.0 if tx.channel in {"crypto", "wire", "cash"} else 0.0
    score = 0.45 * suspicious_ring + 0.25 * high_amount + 0.20 * cross_border + 0.10 * high_risk_channel
    return 1.0 if score >= 0.45 else 0.0


def main() -> None:
    from app.services.feature_engineering import FEATURE_ORDER, build_edge_features
    from app.services.graph_store import GraphStore
    from app.services.simulator import generate_stream
    from ml.gnn import save_edge_model, train_edge_model
    from ml.self_supervised import pretrain_dae

    parser = argparse.ArgumentParser(description="Train edge fraud model on synthetic graph stream")
    parser.add_argument("--samples", type=int, default=15000)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="artifacts/models/edge_model.pt")
    args = parser.parse_args()

    stream = generate_stream(n=max(2000, int(args.samples)), seed=int(args.seed))
    store = GraphStore(max_events=max(5000, len(stream) + 500))

    features: list[np.ndarray] = []
    labels: list[float] = []

    for tx in stream:
        vec, _ = build_edge_features(store, tx)
        y = _label_rule(tx)
        features.append(vec)
        labels.append(y)
        store.add_event(tx)

    x = np.vstack(features).astype(np.float32)
    y = np.asarray(labels, dtype=np.float32)
    rng = np.random.default_rng(int(args.seed))
    order = rng.permutation(x.shape[0])
    x = x[order]
    y = y[order]

    # Lightweight self-supervised pretraining step for representation stabilization.
    _, dae_loss = pretrain_dae(x, epochs=3, batch_size=768)

    n = x.shape[0]
    split = int(n * 0.85)
    x_train, y_train = x[:split], y[:split]
    x_val, y_val = x[split:], y[split:]

    model, metrics = train_edge_model(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        epochs=max(1, int(args.epochs)),
        batch_size=768,
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    save_edge_model(model, args.output)

    print("[train] model saved:", args.output)
    print("[train] features:", len(FEATURE_ORDER))
    print("[train] dae_loss:", round(float(dae_loss), 6))
    print("[train] metrics:", metrics)
    print("[train] pos_ratio_train:", round(float(y_train.mean()), 6))
    print("[train] pos_ratio_val:", round(float(y_val.mean()), 6))


if __name__ == "__main__":
    main()
