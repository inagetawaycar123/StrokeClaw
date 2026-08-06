"""Lightweight patient-level baseline models for Stage-2 validation."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from .attention_mil import MaskedAttentionMIL


class ClinicalEncoder(nn.Module):
    def __init__(self, input_dim: int, embedding_dim: int = 64, dropout: float = 0.2) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embedding_dim, embedding_dim),
            nn.GELU(),
        )

    def forward(self, clinical: torch.Tensor) -> torch.Tensor:
        if clinical.ndim != 2:
            raise ValueError(f"clinical must be [B,F], got {tuple(clinical.shape)}")
        return self.network(clinical)


class NCCTFileEncoder(nn.Module):
    """Small CNN baseline for one single-channel NCCT slice/file."""

    def __init__(self, embedding_dim: int = 64, base_channels: int = 16, dropout: float = 0.1) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, base_channels, kernel_size=5, stride=2, padding=2),
            nn.BatchNorm2d(base_channels),
            nn.GELU(),
            nn.MaxPool2d(2),
            nn.Conv2d(base_channels, base_channels * 2, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(base_channels * 2),
            nn.GELU(),
            nn.Conv2d(base_channels * 2, base_channels * 4, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(base_channels * 4),
            nn.GELU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.projection = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(base_channels * 4, embedding_dim),
            nn.GELU(),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        if image.ndim != 4 or image.shape[1] != 1:
            raise ValueError(f"NCCTFileEncoder expects [B,1,H,W], got {tuple(image.shape)}")
        return self.projection(self.features(image))


class PatientNCCTEncoder(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 64,
        attention_dim: int = 32,
        base_channels: int = 16,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.file_encoder = NCCTFileEncoder(embedding_dim, base_channels, dropout)
        self.mil = MaskedAttentionMIL(embedding_dim, attention_dim)

    def forward(self, ncct_images: torch.Tensor, ncct_mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if ncct_images.ndim != 5:
            raise ValueError(f"ncct_images must be [B,N,1,H,W], got {tuple(ncct_images.shape)}")
        batch_size, file_count, channels, height, width = ncct_images.shape
        flat_mask = ncct_mask.to(dtype=torch.bool, device=ncct_images.device).reshape(-1)
        if not flat_mask.any():
            raise ValueError("At least one NCCT file must be valid")
        flat_images = ncct_images.reshape(batch_size * file_count, channels, height, width)
        valid_encoded = self.file_encoder(flat_images[flat_mask])
        encoded = valid_encoded.new_zeros((batch_size * file_count, valid_encoded.shape[-1]))
        encoded[flat_mask] = valid_encoded
        encoded = encoded.reshape(batch_size, file_count, -1)
        return self.mil(encoded, ncct_mask)


class GatedFusion(nn.Module):
    """Project image/clinical embeddings, concatenate, then learn a mixing gate."""

    def __init__(self, image_dim: int, clinical_dim: int, fusion_dim: int = 64, dropout: float = 0.2) -> None:
        super().__init__()
        self.image_projection = nn.Linear(image_dim, fusion_dim)
        self.clinical_projection = nn.Linear(clinical_dim, fusion_dim)
        self.gate = nn.Sequential(
            nn.Linear(fusion_dim * 2, fusion_dim),
            nn.GELU(),
            nn.Linear(fusion_dim, fusion_dim),
            nn.Sigmoid(),
        )
        self.normalization = nn.LayerNorm(fusion_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, image: torch.Tensor, clinical: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        image_projected = self.image_projection(image)
        clinical_projected = self.clinical_projection(clinical)
        concatenated = torch.cat([image_projected, clinical_projected], dim=-1)
        gate = self.gate(concatenated)
        fused = gate * image_projected + (1.0 - gate) * clinical_projected
        return self.dropout(self.normalization(fused)), gate


class ClinicalOnlyMRSModel(nn.Module):
    def __init__(self, clinical_input_dim: int, embedding_dim: int = 64, dropout: float = 0.2) -> None:
        super().__init__()
        self.clinical_encoder = ClinicalEncoder(clinical_input_dim, embedding_dim, dropout)
        self.classifier = nn.Linear(embedding_dim, 1)

    def forward(self, clinical: torch.Tensor, **_: Any) -> dict[str, torch.Tensor | None]:
        embedding = self.clinical_encoder(clinical)
        return {
            "logit": self.classifier(embedding).squeeze(-1),
            "clinical_embedding": embedding,
            "attention_weights": None,
        }


class NCCTOnlyMRSModel(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 64,
        attention_dim: int = 32,
        base_channels: int = 16,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.ncct_encoder = PatientNCCTEncoder(embedding_dim, attention_dim, base_channels, dropout)
        self.classifier = nn.Linear(embedding_dim, 1)

    def forward(
        self, ncct_images: torch.Tensor, ncct_mask: torch.Tensor, **_: Any
    ) -> dict[str, torch.Tensor | None]:
        embedding, attention = self.ncct_encoder(ncct_images, ncct_mask)
        return {
            "logit": self.classifier(embedding).squeeze(-1),
            "ncct_embedding": embedding,
            "attention_weights": attention,
        }


class NCCTClinicalMRSModel(nn.Module):
    def __init__(
        self,
        clinical_input_dim: int,
        embedding_dim: int = 64,
        attention_dim: int = 32,
        base_channels: int = 16,
        fusion_dim: int = 64,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.ncct_encoder = PatientNCCTEncoder(embedding_dim, attention_dim, base_channels, dropout)
        self.clinical_encoder = ClinicalEncoder(clinical_input_dim, embedding_dim, dropout)
        self.fusion = GatedFusion(embedding_dim, embedding_dim, fusion_dim, dropout)
        self.classifier = nn.Linear(fusion_dim, 1)

    def forward(
        self,
        ncct_images: torch.Tensor,
        ncct_mask: torch.Tensor,
        clinical: torch.Tensor,
        **_: Any,
    ) -> dict[str, torch.Tensor]:
        ncct_embedding, attention = self.ncct_encoder(ncct_images, ncct_mask)
        clinical_embedding = self.clinical_encoder(clinical)
        fused, fusion_gate = self.fusion(ncct_embedding, clinical_embedding)
        return {
            "logit": self.classifier(fused).squeeze(-1),
            "ncct_embedding": ncct_embedding,
            "clinical_embedding": clinical_embedding,
            "fused_embedding": fused,
            "fusion_gate": fusion_gate,
            "attention_weights": attention,
        }
