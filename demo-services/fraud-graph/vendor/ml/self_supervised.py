from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class DenoisingAutoEncoder(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 10) -> None:
        super().__init__()
        hidden = max(24, input_dim * 2)
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, latent_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


def pretrain_dae(
    x: np.ndarray,
    *,
    epochs: int = 5,
    batch_size: int = 512,
    lr: float = 1e-3,
    noise_std: float = 0.07,
    mask_ratio: float = 0.15,
) -> tuple[DenoisingAutoEncoder, float]:
    model = DenoisingAutoEncoder(input_dim=int(x.shape[1]))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    xt = torch.tensor(x, dtype=torch.float32)

    ep = max(1, int(epochs))
    bsz = max(64, int(batch_size))
    last_loss = 0.0

    model.train()
    for _ in range(ep):
        order = torch.randperm(xt.size(0))
        for start in range(0, xt.size(0), bsz):
            idx = order[start : start + bsz]
            clean = xt[idx]
            noise = torch.randn_like(clean) * float(noise_std)
            mask = (torch.rand_like(clean) > float(mask_ratio)).float()
            corrupted = (clean + noise) * mask

            optimizer.zero_grad(set_to_none=True)
            recon = model(corrupted)
            loss = F.mse_loss(recon, clean)
            loss.backward()
            optimizer.step()
            last_loss = float(loss.item())

    return model, float(last_loss)
