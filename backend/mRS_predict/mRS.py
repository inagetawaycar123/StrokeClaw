from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image
import nibabel as nib
import torch
import torch.nn as nn


DEFAULT_INPUT_SIZE = (256, 256)
DEFAULT_THRESHOLD = 0.5
DEFAULT_WEIGHT_FILENAME = "cnn_2class_model.pth"


class MRSBinaryCNN(nn.Module):
    def __init__(self, in_channels: int = 4):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _weight_path(weight_path: Optional[str] = None) -> Path:
    if weight_path:
        return Path(weight_path)
    return Path(__file__).resolve().with_name(DEFAULT_WEIGHT_FILENAME)


def _load_nifti_array(file_path: str) -> np.ndarray:
    image = nib.load(str(file_path))
    data = image.get_fdata()
    if data.ndim == 4:
        data = data[..., 0]
    if data.ndim == 2:
        data = data[:, :, np.newaxis]
    if data.ndim != 3:
        raise ValueError(f"Unsupported image shape: {data.shape}")
    return np.asarray(data, dtype=np.float32)


def _normalize_slice(slice_data: np.ndarray) -> np.ndarray:
    arr = np.asarray(slice_data, dtype=np.float32)
    finite = np.isfinite(arr)
    if not finite.any():
        return np.zeros_like(arr, dtype=np.float32)
    arr = np.where(finite, arr, 0.0)
    low = float(np.percentile(arr, 1))
    high = float(np.percentile(arr, 99))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low = float(arr.min())
        high = float(arr.max())
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        return np.zeros_like(arr, dtype=np.float32)
    arr = np.clip(arr, low, high)
    arr = (arr - low) / (high - low)
    return arr.astype(np.float32)


def _resize_slice(slice_data: np.ndarray, size: Tuple[int, int] = DEFAULT_INPUT_SIZE) -> np.ndarray:
    arr = np.asarray(slice_data, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D slice, got {arr.shape}")
    image = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L")
    image = image.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.float32) / 255.0


def _pick_center_slice(volume: np.ndarray) -> np.ndarray:
    if volume.ndim != 3:
        raise ValueError(f"Expected 3D volume, got {volume.shape}")
    center_idx = int(volume.shape[2] // 2)
    return volume[:, :, center_idx]


def build_mrs_input_tensor(ncct_path: str, mcta_path: str, vcta_path: str, dcta_path: str) -> Dict[str, Any]:
    ncct_volume = _load_nifti_array(ncct_path)
    mcta_volume = _load_nifti_array(mcta_path)
    vcta_volume = _load_nifti_array(vcta_path)
    dcta_volume = _load_nifti_array(dcta_path)
    if not (ncct_volume.shape == mcta_volume.shape == vcta_volume.shape == dcta_volume.shape):
        raise ValueError(
            "NCCT/mCTA/vCTA/dCTA shapes must match: "
            f"ncct={ncct_volume.shape}, mcta={mcta_volume.shape}, "
            f"vcta={vcta_volume.shape}, dcta={dcta_volume.shape}"
        )

    ncct_slice = _resize_slice(_normalize_slice(_pick_center_slice(ncct_volume)))
    mcta_slice = _resize_slice(_normalize_slice(_pick_center_slice(mcta_volume)))
    vcta_slice = _resize_slice(_normalize_slice(_pick_center_slice(vcta_volume)))
    dcta_slice = _resize_slice(_normalize_slice(_pick_center_slice(dcta_volume)))

    stacked = np.stack([ncct_slice, mcta_slice, vcta_slice, dcta_slice], axis=0).astype(np.float32)
    raw_tensor = torch.from_numpy(stacked).unsqueeze(0)
    model_tensor = raw_tensor
    return {
        "tensor": model_tensor,
        "raw_tensor": raw_tensor,
        "input_shape": [int(dim) for dim in raw_tensor.shape[1:]],
        "model_input_shape": [int(dim) for dim in model_tensor.shape[1:]],
        "ncct_shape": [int(dim) for dim in ncct_volume.shape],
        "mcta_shape": [int(dim) for dim in mcta_volume.shape],
        "vcta_shape": [int(dim) for dim in vcta_volume.shape],
        "dcta_shape": [int(dim) for dim in dcta_volume.shape],
    }


def _expand_first_conv_to_four_channels(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(state_dict)
    weight = cleaned.get("features.0.weight")
    if isinstance(weight, torch.Tensor) and weight.ndim == 4 and weight.shape[1] == 1:
        cleaned["features.0.weight"] = weight.repeat(1, 4, 1, 1) / 4.0
    return cleaned


def _load_model(weight_path: Optional[str] = None, device: Optional[str] = None) -> Tuple[MRSBinaryCNN, str, bool]:
    resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = MRSBinaryCNN(in_channels=4)
    path = _weight_path(weight_path)
    if path.exists():
        state = torch.load(str(path), map_location=resolved_device)
        if isinstance(state, dict):
            for key in ("state_dict", "model_state_dict", "net", "model", "module"):
                candidate = state.get(key)
                if isinstance(candidate, dict):
                    state = candidate
                    break
        if isinstance(state, dict):
            cleaned = {}
            for key, value in state.items():
                new_key = str(key).replace("module.", "")
                cleaned[new_key] = value
            cleaned = _expand_first_conv_to_four_channels(cleaned)
            model.load_state_dict(cleaned, strict=False)
    model.to(resolved_device)
    model.eval()
    return model, resolved_device, path.exists()


def _heuristic_fallback(tensor: torch.Tensor) -> Dict[str, Any]:
    sample = tensor.detach().cpu().numpy()[0]
    ncct = sample[0]
    mcta = sample[1]
    vcta = sample[2]
    dcta = sample[3]
    score = float(np.clip(
        0.35 * float((1.0 - np.minimum(ncct, mcta).mean()))
        + 0.25 * float((1.0 - np.minimum(mcta, vcta).mean()))
        + 0.20 * float((1.0 - np.minimum(vcta, dcta).mean()))
        + 0.20 * float((1.0 - np.minimum(ncct, dcta).mean())),
        0.0,
        1.0,
    ))
    risk_level = "high" if score >= DEFAULT_THRESHOLD else "low"
    return {
        "success": True,
        "model_available": False,
        "risk_level": risk_level,
        "risk_label_cn": "高风险" if risk_level == "high" else "低风险",
        "risk_score": score,
        "probabilities": {"low": float(1.0 - score), "high": score},
        "source": "heuristic_fallback",
        "message": "mRS 权重文件未找到，已使用规则回退结果",
    }


def predict_mrs_risk(
    ncct_path: str,
    mcta_path: str,
    vcta_path: str,
    dcta_path: str,
    *,
    weight_path: Optional[str] = None,
    device: Optional[str] = None,
    threshold: float = DEFAULT_THRESHOLD,
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    input_bundle = build_mrs_input_tensor(ncct_path, mcta_path, vcta_path, dcta_path)
    tensor = input_bundle["tensor"]
    model_path = _weight_path(weight_path)

    try:
        model, resolved_device, has_weights = _load_model(str(model_path), device)
        if has_weights:
            with torch.no_grad():
                logits = model(tensor.to(resolved_device))
                score = float(torch.sigmoid(logits).detach().cpu().numpy().reshape(-1)[0])
            risk_level = "high" if score >= threshold else "low"
            return {
                "success": True,
                "model_available": True,
                "model_path": str(model_path),
                "device": resolved_device,
                "input_shape": input_bundle["input_shape"],
                "model_input_shape": input_bundle["model_input_shape"],
                "ncct_shape": input_bundle["ncct_shape"],
                "mcta_shape": input_bundle["mcta_shape"],
                "vcta_shape": input_bundle["vcta_shape"],
                "dcta_shape": input_bundle["dcta_shape"],
                "risk_level": risk_level,
                "risk_label_cn": "高风险" if risk_level == "high" else "低风险",
                "risk_score": score,
                "probabilities": {"low": float(1.0 - score), "high": score},
                "source": "cnn_model",
                "message": "mRS CNN 推理完成",
            }
        if allow_fallback:
            fallback = _heuristic_fallback(tensor)
            fallback.update(
                {
                    "input_shape": input_bundle["input_shape"],
                    "model_input_shape": input_bundle["model_input_shape"],
                    "ncct_shape": input_bundle["ncct_shape"],
                    "mcta_shape": input_bundle["mcta_shape"],
                    "vcta_shape": input_bundle["vcta_shape"],
                    "dcta_shape": input_bundle["dcta_shape"],
                    "model_path": str(model_path),
                }
            )
            return fallback
        return {
            "success": False,
            "model_available": False,
            "model_path": str(model_path),
            "input_shape": input_bundle["input_shape"],
            "model_input_shape": input_bundle["model_input_shape"],
            "ncct_shape": input_bundle["ncct_shape"],
            "mcta_shape": input_bundle["mcta_shape"],
            "vcta_shape": input_bundle["vcta_shape"],
            "dcta_shape": input_bundle["dcta_shape"],
            "risk_level": "unknown",
            "risk_label_cn": "不可用",
            "risk_score": None,
            "probabilities": {},
            "source": "missing_weights",
            "message": f"mRS 权重未找到: {model_path}",
        }
    except Exception as exc:
        if allow_fallback:
            fallback = _heuristic_fallback(tensor)
            fallback.update(
                {
                    "input_shape": input_bundle["input_shape"],
                    "model_input_shape": input_bundle["model_input_shape"],
                    "ncct_shape": input_bundle["ncct_shape"],
                    "mcta_shape": input_bundle["mcta_shape"],
                    "vcta_shape": input_bundle["vcta_shape"],
                    "dcta_shape": input_bundle["dcta_shape"],
                    "model_path": str(model_path),
                    "warning": str(exc),
                }
            )
            return fallback
        return {
            "success": False,
            "model_available": False,
            "model_path": str(model_path),
            "input_shape": input_bundle["input_shape"],
            "model_input_shape": input_bundle["model_input_shape"],
            "ncct_shape": input_bundle["ncct_shape"],
            "mcta_shape": input_bundle["mcta_shape"],
            "vcta_shape": input_bundle["vcta_shape"],
            "dcta_shape": input_bundle["dcta_shape"],
            "risk_level": "unknown",
            "risk_label_cn": "不可用",
            "risk_score": None,
            "probabilities": {},
            "source": "error",
            "message": str(exc),
        }
