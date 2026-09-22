from __future__ import annotations

import os

import numpy as np
import torch
import torch.nn as nn


class EdgeMLP(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        hidden = max(32, input_dim * 3)
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.12),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def train_edge_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    *,
    epochs: int = 12,
    batch_size: int = 512,
    lr: float = 1e-3,
    seed: int = 42,
) -> tuple[EdgeMLP, dict[str, float]]:
    torch.manual_seed(seed)

    model = EdgeMLP(input_dim=int(x_train.shape[1]))
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    xtr = torch.tensor(x_train, dtype=torch.float32)
    ytr = torch.tensor(y_train, dtype=torch.float32)
    xva = torch.tensor(x_val, dtype=torch.float32)
    yva = torch.tensor(y_val, dtype=torch.float32)
    pos = float(ytr.sum().item())
    neg = float(ytr.numel() - pos)
    pos_weight_value = neg / max(pos, 1.0)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight_value, dtype=torch.float32))

    bsz = max(64, int(batch_size))
    ep = max(1, int(epochs))

    last_train = 0.0
    last_val = 0.0
    for _ in range(ep):
        order = torch.randperm(xtr.size(0))
        model.train()
        for start in range(0, xtr.size(0), bsz):
            idx = order[start : start + bsz]
            xb = xtr[idx]
            yb = ytr[idx]
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()
            last_train = float(loss.item())

        model.eval()
        with torch.no_grad():
            val_logits = model(xva)
            val_loss = criterion(val_logits, yva)
            last_val = float(val_loss.item())

    with torch.no_grad():
        val_prob = torch.sigmoid(model(xva))
        val_pred = (val_prob >= 0.5).float()
        accuracy = float((val_pred == yva).float().mean().item())

    metrics = {
        "train_loss": round(last_train, 6),
        "val_loss": round(last_val, 6),
        "val_accuracy": round(accuracy, 6),
        "pos_weight": round(float(pos_weight_value), 6),
    }
    return model, metrics


def save_edge_model(model: EdgeMLP, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({"state_dict": model.state_dict()}, path)


def load_edge_model(path: str, input_dim: int) -> EdgeMLP:
    model = EdgeMLP(input_dim=input_dim)
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    state = payload.get("state_dict") if isinstance(payload, dict) else payload
    if not isinstance(state, dict):
        raise ValueError("invalid model checkpoint")
    model.load_state_dict(state, strict=False)
    return model
