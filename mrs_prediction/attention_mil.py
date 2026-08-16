"""Mask-aware attention multiple-instance learning layers."""

from __future__ import annotations

import torch
from torch import nn


class MaskedAttentionMIL(nn.Module):
    """Aggregate variable-length instance features while ignoring padding."""

    def __init__(self, feature_dim: int, attention_dim: int = 64) -> None:
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(feature_dim, attention_dim),
            nn.Tanh(),
            nn.Linear(attention_dim, 1),
        )

    def forward(self, features: torch.Tensor, valid_mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if features.ndim != 3:
            raise ValueError(f"features must be [B,N,D], got {tuple(features.shape)}")
        if valid_mask.shape != features.shape[:2]:
            raise ValueError("valid_mask must have shape [B,N]")
        valid_mask = valid_mask.to(dtype=torch.bool, device=features.device)
        if not torch.all(valid_mask.any(dim=1)):
            raise ValueError("Each patient must have at least one valid NCCT file")
        scores = self.attention(features).squeeze(-1)
        scores = scores.masked_fill(~valid_mask, torch.finfo(scores.dtype).min)
        weights = torch.softmax(scores, dim=1)
        weights = weights.masked_fill(~valid_mask, 0.0)
        pooled = torch.sum(features * weights.unsqueeze(-1), dim=1)
        return pooled, weights

