"""Leakage-safe NCCT resize cache and fold-local intensity normalization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as functional

from .dataset import ncct_bundle_files


def _load_resized_ncct(path: Path, image_size: tuple[int, int]) -> np.ndarray:
    array = np.load(path, allow_pickle=False)
    if array.ndim != 3 or array.shape[-1] != 4:
        raise ValueError(f"{path} must have HWC shape with 4 internal channels; got {array.shape}")
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{path} has non-numeric dtype {array.dtype}")
    ncct = np.asarray(array[..., 0], dtype=np.float32)
    if not np.isfinite(ncct).all():
        raise ValueError(f"{path} internal NCCT channel contains NaN or Inf")
    if tuple(ncct.shape) == image_size:
        return np.ascontiguousarray(ncct)
    tensor = torch.from_numpy(np.ascontiguousarray(ncct))[None, None]
    resized = functional.interpolate(
        tensor, size=image_size, mode="bilinear", align_corners=False
    )[0, 0]
    return np.ascontiguousarray(resized.numpy(), dtype=np.float32)


def resize_ncct_array(array: np.ndarray, image_size: tuple[int, int]) -> np.ndarray:
    """Validate and resize one already-decoded 2-D NCCT slice.

    This is the online NIfTI adapter counterpart of ``_load_resized_ncct``.
    It deliberately accepts NCCT only; no missing CTA phases are synthesized.
    """

    ncct = np.asarray(array, dtype=np.float32)
    if ncct.ndim != 2:
        raise ValueError(f"NCCT slice must be 2-D, got {ncct.shape}")
    if not np.isfinite(ncct).all():
        raise ValueError("NCCT slice contains NaN or Inf")
    if tuple(ncct.shape) == tuple(image_size):
        return np.ascontiguousarray(ncct)
    tensor = torch.from_numpy(np.ascontiguousarray(ncct))[None, None]
    resized = functional.interpolate(
        tensor, size=image_size, mode="bilinear", align_corners=False
    )[0, 0]
    return np.ascontiguousarray(resized.numpy(), dtype=np.float32)


class NCCTResizeCache:
    """Read-only deterministic resize cache; it contains no fitted statistics."""

    def __init__(self, array_path: Path, metadata_path: Path) -> None:
        self.array_path = Path(array_path).resolve()
        self.metadata_path = Path(metadata_path).resolve()
        self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        self.image_size = tuple(int(value) for value in self.metadata["image_size"])
        self.index = {str(name): int(index) for name, index in self.metadata["index"].items()}
        self.array = np.load(self.array_path, mmap_mode="r", allow_pickle=False)
        expected = (len(self.index), *self.image_size)
        if tuple(self.array.shape) != expected or self.array.dtype != np.float32:
            raise ValueError(
                f"NCCT cache is incompatible: shape={self.array.shape}, dtype={self.array.dtype}, "
                f"expected={expected}/float32"
            )

    def get(self, filename: str) -> np.ndarray:
        try:
            index = self.index[str(filename)]
        except KeyError as exc:
            raise KeyError(f"NCCT file is absent from resize cache: {filename}") from exc
        return np.asarray(self.array[index], dtype=np.float32)

    @classmethod
    def build_or_load(
        cls,
        records: Sequence[Mapping[str, Any]],
        image_root: str | Path,
        cache_dir: str | Path,
        image_size: tuple[int, int],
    ) -> "NCCTResizeCache":
        root = Path(image_root).resolve()
        output = Path(cache_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        files = sorted({name for record in records for name in ncct_bundle_files(record)})
        if not files:
            raise ValueError("Cannot build NCCT cache without image files")
        signature_rows = []
        for name in files:
            path = root / name
            stat = path.stat()
            signature_rows.append((name, stat.st_size, stat.st_mtime_ns))
        signature_payload = {
            "files": signature_rows,
            "image_size": list(image_size),
            "channel": 0,
            "resize": "torch_bilinear_align_corners_false",
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        stem = f"ncct_{image_size[0]}x{image_size[1]}_{signature[:12]}"
        array_path = output / f"{stem}.npy"
        metadata_path = output / f"{stem}.json"
        if array_path.exists() and metadata_path.exists():
            cached = json.loads(metadata_path.read_text(encoding="utf-8"))
            if cached.get("signature") == signature:
                return cls(array_path, metadata_path)

        temporary_array = output / f"{stem}.tmp.npy"
        temporary_metadata = output / f"{stem}.tmp.json"
        memmap = np.lib.format.open_memmap(
            temporary_array,
            mode="w+",
            dtype=np.float32,
            shape=(len(files), *image_size),
        )
        for index, name in enumerate(files):
            memmap[index] = _load_resized_ncct(root / name, image_size)
        memmap.flush()
        del memmap
        metadata = {
            "artifact_role": "DETERMINISTIC_RESIZE_CACHE_NOT_A_MODEL",
            "signature": signature,
            "image_root": str(root),
            "image_size": list(image_size),
            "internal_channel_index": 0,
            "internal_channel_interpretation": "NCCT",
            "dtype": "float32",
            "file_count": len(files),
            "index": {name: index for index, name in enumerate(files)},
            "contains_fitted_statistics": False,
        }
        temporary_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_array.replace(array_path)
        temporary_metadata.replace(metadata_path)
        return cls(array_path, metadata_path)


@dataclass
class ImagePreprocessor:
    image_size: tuple[int, int]
    mean: float
    std: float
    fitted_patient_count: int
    fitted_file_count: int
    fit_scope_hash: str
    eps: float = 1e-6

    @classmethod
    def fit(
        cls,
        records: Sequence[Mapping[str, Any]],
        cache: NCCTResizeCache,
        *,
        max_ncct_files: int | None = None,
    ) -> "ImagePreprocessor":
        if not records:
            raise ValueError("ImagePreprocessor.fit requires inner-train patients")
        patient_keys = sorted(str(record["patient_key"]) for record in records)
        selected: list[str] = []
        for record in records:
            files = ncct_bundle_files(record)
            if max_ncct_files and len(files) > max_ncct_files:
                indices = np.linspace(0, len(files) - 1, max_ncct_files, dtype=int)
                files = [files[index] for index in indices]
            selected.extend(files)
        selected = sorted(set(selected))
        total = 0.0
        total_square = 0.0
        count = 0
        for filename in selected:
            array = np.asarray(cache.get(filename), dtype=np.float64)
            total += float(array.sum(dtype=np.float64))
            total_square += float(np.square(array, dtype=np.float64).sum(dtype=np.float64))
            count += int(array.size)
        if count == 0:
            raise ValueError("Inner-train image normalization received no pixels")
        mean = total / count
        variance = max(total_square / count - mean * mean, 0.0)
        std = variance**0.5
        if not np.isfinite(mean) or not np.isfinite(std) or std <= 1e-6:
            raise ValueError(f"Invalid inner-train image statistics: mean={mean}, std={std}")
        fit_hash = hashlib.sha256("\n".join(patient_keys).encode("utf-8")).hexdigest()
        return cls(
            image_size=cache.image_size,
            mean=float(mean),
            std=float(std),
            fitted_patient_count=len(patient_keys),
            fitted_file_count=len(selected),
            fit_scope_hash=fit_hash,
        )

    def normalize(self, tensor: torch.Tensor) -> torch.Tensor:
        return (tensor - self.mean) / max(self.std, self.eps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_size": list(self.image_size),
            "selected_internal_channel": 0,
            "internal_channel_interpretation": "NCCT",
            "resize": "torch_bilinear_align_corners_false",
            "normalization": "inner_train_global_mean_std",
            "mean": self.mean,
            "std": self.std,
            "fitted_patient_count": self.fitted_patient_count,
            "fitted_file_count": self.fitted_file_count,
            "fit_scope_hash": self.fit_scope_hash,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ImagePreprocessor":
        return cls(
            image_size=tuple(int(value) for value in payload["image_size"]),
            mean=float(payload["mean"]),
            std=float(payload["std"]),
            fitted_patient_count=int(payload["fitted_patient_count"]),
            fitted_file_count=int(payload["fitted_file_count"]),
            fit_scope_hash=str(payload["fit_scope_hash"]),
        )
