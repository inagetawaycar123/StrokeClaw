"""PyTorch 2.1 compatible DINOv3 vessel-classification adapter.

This module intentionally imports only ``dinov3.hub.backbones``.  Importing the
repository's ``hubconf.py`` also imports optional segmentation dependencies,
which are not needed for vessel classification and can make inference fail at
startup.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms


DEFAULT_CLASS_NAMES: Tuple[str, ...] = (
    "Class_0",
    "Class_1_LVO",
    "Class_2_MEVO",
)

_IMPORT_LOCK = threading.RLock()


def _ensure_dynamo_config_compat(config_module=None) -> None:
    """Register the DINOv3 cache setting missing from PyTorch 2.1.

    DINOv3 assigns ``torch._dynamo.config.accumulated_cache_size_limit`` while
    importing its transformer blocks.  PyTorch 2.1's strict ``ConfigModule``
    rejects unknown keys, so the key has to be registered before importing the
    backbone package.  Newer PyTorch versions already expose it and are left
    unchanged.
    """

    if config_module is None:
        try:
            config_module = torch._dynamo.config
        except (AttributeError, ImportError):
            return

    try:
        getattr(config_module, "accumulated_cache_size_limit")
        return
    except AttributeError:
        pass

    key = "accumulated_cache_size_limit"
    default_value = 1024
    config = getattr(config_module, "_config", None)
    defaults = getattr(config_module, "_default", None)
    allowed_keys = getattr(config_module, "_allowed_keys", None)

    # PyTorch 2.1 installs a strict ConfigModule backed by these containers.
    if isinstance(config, dict):
        config[key] = default_value
    if isinstance(defaults, dict):
        defaults[key] = default_value
    if isinstance(allowed_keys, set):
        allowed_keys.add(key)

    try:
        setattr(config_module, key, default_value)
    except AttributeError as exc:
        raise RuntimeError(
            "Unable to register DINOv3's PyTorch Dynamo compatibility setting"
        ) from exc


def _resolve_repo_root(repo_dir: str) -> Path:
    """Return the directory whose direct child is the ``dinov3`` package."""

    root = Path(repo_dir).expanduser().resolve()
    candidates = (root, root / "dinov3")
    for candidate in candidates:
        if (candidate / "dinov3" / "hub" / "backbones.py").is_file():
            return candidate
    raise FileNotFoundError(
        "DINOv3 backbone module not found under repository directory: "
        f"{repo_dir}"
    )


def _import_backbone_factory(repo_dir: str) -> Callable[..., nn.Module]:
    """Import ``dinov3_vitb16`` directly, bypassing torch.hub/hubconf.py."""

    repo_root = _resolve_repo_root(repo_dir)
    _ensure_dynamo_config_compat()

    with _IMPORT_LOCK:
        repo_root_text = os.fspath(repo_root)
        if repo_root_text not in sys.path:
            # Keep the path available: the factory lazily imports model modules
            # when it is called, after this function has returned.
            sys.path.insert(0, repo_root_text)
        module = importlib.import_module("dinov3.hub.backbones")

    module_file = getattr(module, "__file__", None)
    if module_file is not None:
        expected_package = (repo_root / "dinov3").resolve()
        try:
            Path(module_file).resolve().relative_to(expected_package)
        except ValueError as exc:
            raise ImportError(
                "A different 'dinov3' package is already loaded; expected the "
                f"local repository at {expected_package}"
            ) from exc

    factory = getattr(module, "dinov3_vitb16", None)
    if not callable(factory):
        raise ImportError("dinov3.hub.backbones.dinov3_vitb16 is unavailable")
    return factory


def _load_backbone(weights_path: str, repo_dir: str) -> nn.Module:
    if not os.path.isfile(weights_path):
        raise FileNotFoundError(f"DINOv3 pretrained weights not found: {weights_path}")

    factory = _import_backbone_factory(repo_dir)
    # Match the original classifier: construct the architecture without an
    # automatic download, then load the supplied local backbone checkpoint.
    backbone = factory(pretrained=False)
    state_dict = torch.load(weights_path, map_location="cpu")
    backbone.load_state_dict(state_dict, strict=False)
    return backbone


class CAMClassifier(nn.Module):
    """Vessel classifier architecture used by the existing trained weights."""

    def __init__(
        self,
        num_classes: int = 3,
        freeze_ratio: float = 0.75,
        weights_path: Optional[str] = None,
        repo_dir: Optional[str] = None,
        dropout_rate: float = 0.0,
        head_type: str = "simple",
    ) -> None:
        super().__init__()
        if weights_path is None or repo_dir is None:
            raise ValueError("weights_path and repo_dir are required")
        if not 0.0 <= freeze_ratio <= 1.0:
            raise ValueError("freeze_ratio must be between 0 and 1")

        self.model_name = "dinov3_vitb16"
        self.backbone = _load_backbone(weights_path, repo_dir)

        for parameter in self.backbone.parameters():
            parameter.requires_grad = False

        blocks = self.backbone.blocks
        total_blocks = len(blocks)
        block_params = [
            (index, sum(parameter.numel() for parameter in block.parameters()))
            for index, block in enumerate(blocks)
        ]
        total_params = sum(count for _, count in block_params)
        target_train = total_params * (1 - freeze_ratio)

        cumulative = 0
        unfreeze_start = total_blocks
        for index in reversed(range(total_blocks)):
            cumulative += block_params[index][1]
            unfreeze_start = index
            if cumulative >= target_train:
                break

        for block_index in range(unfreeze_start, total_blocks):
            for parameter in blocks[block_index].parameters():
                parameter.requires_grad = True

        normalized_shape = self.backbone.norm.normalized_shape
        self.embed_dim = (
            normalized_shape[0]
            if isinstance(normalized_shape, (tuple, list, torch.Size))
            else int(normalized_shape)
        )
        self.feature_extractor_layers = 1
        self.pool = nn.AdaptiveMaxPool2d((1, 1))
        self.last_conv_features = None

        if head_type == "mlp":
            self.head = nn.Sequential(
                nn.Dropout(p=dropout_rate),
                nn.Linear(self.embed_dim, 256),
                nn.ReLU(inplace=True),
                nn.Dropout(p=dropout_rate * 0.5),
                nn.Linear(256, num_classes),
            )
        else:
            self.head = nn.Sequential(
                nn.Dropout(p=dropout_rate),
                nn.Linear(self.embed_dim, num_classes),
            )

    def forward_features(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.backbone.get_intermediate_layers(
            inputs,
            n=self.feature_extractor_layers,
            reshape=True,
            return_class_token=False,
            norm=True,
        )
        features = torch.cat(features, dim=1)
        self.last_conv_features = features
        return features

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.forward_features(inputs)
        pooled = self.pool(features)[:, :, 0, 0]
        return self.head(pooled)


def build_transform() -> transforms.Compose:
    """Build the validation preprocessing pipeline used during training."""

    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                [0.485, 0.456, 0.406],
                [0.229, 0.224, 0.225],
            ),
        ]
    )


def load_image(image_path: str) -> torch.Tensor:
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with Image.open(image_path) as image:
        return build_transform()(image.convert("RGB")).unsqueeze(0)


def _normalise_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


@dataclass(frozen=True)
class _CacheEntry:
    model: CAMClassifier
    inference_lock: threading.Lock


class ModelManager:
    """Thread-safe cache for fully loaded vessel-classification models."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: Dict[Tuple[object, ...], _CacheEntry] = {}

    def load(
        self,
        model_path: str,
        dinov3_weights: str,
        repo_dir: str,
        num_classes: int = 3,
        freeze_ratio: float = 0.35,
        dropout_rate: float = 0.35,
        head_type: str = "mlp",
        device: Optional[torch.device] = None,
    ) -> _CacheEntry:
        if device is None:
            device = _select_device()

        key = (
            _normalise_path(model_path),
            _normalise_path(dinov3_weights),
            _normalise_path(repo_dir),
            num_classes,
            float(freeze_ratio),
            float(dropout_rate),
            head_type,
            str(device),
        )

        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            if not os.path.isfile(model_path):
                raise FileNotFoundError(
                    f"Vessel classifier weights not found: {model_path}"
                )
            if not os.path.isdir(repo_dir):
                raise FileNotFoundError(f"DINOv3 repository not found: {repo_dir}")

            model = CAMClassifier(
                num_classes=num_classes,
                freeze_ratio=freeze_ratio,
                weights_path=dinov3_weights,
                repo_dir=repo_dir,
                dropout_rate=dropout_rate,
                head_type=head_type,
            ).to(device)
            checkpoint = torch.load(model_path, map_location=device)
            model.load_state_dict(checkpoint)
            model.eval()

            entry = _CacheEntry(model=model, inference_lock=threading.Lock())
            self._cache[key] = entry
            return entry

    def clear(self) -> None:
        """Clear cached models (primarily useful for tests and service reloads)."""

        with self._lock:
            self._cache.clear()


_MODEL_MANAGER = ModelManager()


def _select_device() -> torch.device:
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def _default_paths() -> Tuple[str, str, str]:
    project_root = Path(__file__).resolve().parent.parent
    dinov3_dir = project_root / "dinov3"
    return (
        os.fspath(dinov3_dir / "dinov3权重.pth"),
        os.fspath(
            dinov3_dir
            / "ckpt"
            / "dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth"
        ),
        os.fspath(dinov3_dir / "dinov3"),
    )


def predict_single_image(
    image_path: str,
    model_path: Optional[str] = None,
    dinov3_weights: Optional[str] = None,
    repo_dir: Optional[str] = None,
    num_classes: int = 3,
    freeze_ratio: float = 0.35,
    dropout_rate: float = 0.35,
    head_type: str = "mlp",
    verbose: bool = False,
    class_names: Optional[Sequence[str]] = None,
) -> dict:
    """Predict one vessel image while preserving the legacy call signature."""

    default_model, default_backbone, default_repo = _default_paths()
    model_path = model_path or default_model
    dinov3_weights = dinov3_weights or default_backbone
    repo_dir = repo_dir or default_repo
    labels = tuple(class_names or DEFAULT_CLASS_NAMES)

    if len(labels) != num_classes:
        raise ValueError(
            f"class_names contains {len(labels)} labels, expected {num_classes}"
        )

    image_tensor = load_image(image_path)
    device = _select_device()
    entry = _MODEL_MANAGER.load(
        model_path=model_path,
        dinov3_weights=dinov3_weights,
        repo_dir=repo_dir,
        num_classes=num_classes,
        freeze_ratio=freeze_ratio,
        dropout_rate=dropout_rate,
        head_type=head_type,
        device=device,
    )

    with entry.inference_lock, torch.no_grad():
        logits = entry.model(image_tensor.to(device))
        probabilities = torch.softmax(logits, dim=1)[0]
        predicted_class = int(torch.argmax(probabilities).item())

    if probabilities.numel() != len(labels):
        raise RuntimeError(
            "Classifier output size does not match configured class labels: "
            f"{probabilities.numel()} != {len(labels)}"
        )

    predicted_label = labels[predicted_class]
    result = {
        "image_path": image_path,
        "predicted_class": predicted_class,
        "predicted_label": predicted_label,
        # ``label`` is a convenient explicit alias for new callers, while
        # ``predicted_label`` preserves compatibility with backend/app.py.
        "label": predicted_label,
        "confidence": float(probabilities[predicted_class].item()),
        "probabilities": {
            label: float(probabilities[index].item())
            for index, label in enumerate(labels)
        },
    }

    if verbose:
        _print_result(result)
    return result


def _print_result(result: dict) -> None:
    print(f"Image: {result['image_path']}")
    print(
        f"Prediction: {result['predicted_label']} "
        f"(class={result['predicted_class']}, confidence={result['confidence']:.4f})"
    )


__all__ = [
    "CAMClassifier",
    "DEFAULT_CLASS_NAMES",
    "ModelManager",
    "build_transform",
    "load_image",
    "predict_single_image",
]
