"""Patient-level NCCT/clinical Dataset and padding-aware collate function."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as functional
from torch.utils.data import Dataset

from .preprocessing import ClinicalPreprocessor


def read_manifest_rows(path: str | Path, *, eligible_only: bool = True) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if eligible_only:
        rows = [row for row in rows if str(row.get("is_v0_eligible", "")).strip().lower() == "true"]
    return rows


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    token = str(value or "").strip()
    if not token:
        return []
    parsed = json.loads(token)
    if not isinstance(parsed, list):
        raise ValueError("Manifest file list must be a JSON list")
    return [str(item) for item in parsed]


def ncct_bundle_files(record: Mapping[str, Any]) -> list[str]:
    """Return the per-patient files that each contain internal NCCT channel 0."""

    if record.get("npy_bundle_files"):
        return _json_list(record["npy_bundle_files"])
    combined: list[str] = []
    for column in ("channel_01_files", "channel_02_files", "channel_03_files", "channel_04_files"):
        combined.extend(_json_list(record.get(column)))
    return sorted(set(combined))


def _evenly_subsample(files: Sequence[str], maximum: int | None) -> list[str]:
    if maximum is None or maximum <= 0 or len(files) <= maximum:
        return list(files)
    indices = np.linspace(0, len(files) - 1, num=maximum, dtype=int)
    return [files[index] for index in indices]


class MRSPatientDataset(Dataset[dict[str, Any]]):
    """One item per patient, with a variable number of NCCT slice files."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        image_root: str | Path,
        clinical_preprocessor: ClinicalPreprocessor,
        *,
        image_size: tuple[int, int] = (256, 256),
        max_ncct_files: int | None = None,
        image_cache: Any | None = None,
        image_preprocessor: Any | None = None,
    ) -> None:
        self.records = [dict(record) for record in records]
        self.image_root = Path(image_root)
        self.clinical_preprocessor = clinical_preprocessor
        self.image_size = tuple(int(value) for value in image_size)
        self.max_ncct_files = max_ncct_files
        self.image_cache = image_cache
        self.image_preprocessor = image_preprocessor
        if not clinical_preprocessor.fitted:
            raise ValueError("Dataset requires a fold-fitted ClinicalPreprocessor")

    def __len__(self) -> int:
        return len(self.records)

    def _load_ncct(self, filename: str) -> torch.Tensor:
        if self.image_cache is not None:
            ncct = np.array(self.image_cache.get(filename), dtype=np.float32, copy=True)
            tensor = torch.from_numpy(ncct).unsqueeze(0)
            if tuple(tensor.shape[-2:]) != self.image_size:
                raise ValueError(
                    f"Cached NCCT shape {tuple(tensor.shape[-2:])} does not match {self.image_size}"
                )
            if self.image_preprocessor is not None:
                tensor = self.image_preprocessor.normalize(tensor)
            return tensor
        path = self.image_root / filename
        array = np.load(path, allow_pickle=False)
        if array.ndim != 3 or array.shape[-1] != 4:
            raise ValueError(f"{path} must have HWC shape with 4 internal phase channels; got {array.shape}")
        if not np.issubdtype(array.dtype, np.number):
            raise TypeError(f"{path} has non-numeric dtype {array.dtype}")
        ncct = np.asarray(array[..., 0], dtype=np.float32)
        if not np.isfinite(ncct).all():
            raise ValueError(f"{path} internal NCCT channel contains NaN or Inf")
        tensor = torch.from_numpy(np.ascontiguousarray(ncct)).unsqueeze(0)
        if tuple(tensor.shape[-2:]) != self.image_size:
            tensor = functional.interpolate(
                tensor.unsqueeze(0), size=self.image_size, mode="bilinear", align_corners=False
            ).squeeze(0)
        if self.image_preprocessor is not None:
            tensor = self.image_preprocessor.normalize(tensor)
        return tensor

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        files = _evenly_subsample(ncct_bundle_files(record), self.max_ncct_files)
        if not files:
            raise ValueError(f"Patient {record.get('patient_key')} has no NCCT-containing .npy files")
        images = torch.stack([self._load_ncct(filename) for filename in files])
        label = int(float(record["binary_label"]))
        if label not in (0, 1):
            raise ValueError(f"Invalid binary label for patient {record.get('patient_key')}: {label}")
        return {
            "patient_key": str(record.get("patient_key", "")),
            "clinical_patient_id": str(record.get("clinical_patient_id", "")),
            "ncct_images": images,
            "ncct_source_files": files,
            "clinical": torch.from_numpy(self.clinical_preprocessor.transform_one(record)),
            "label": torch.tensor(label, dtype=torch.float32),
        }


def mrs_patient_collate(batch: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(batch)
    if not items:
        raise ValueError("Cannot collate an empty patient batch")
    max_files = max(int(item["ncct_images"].shape[0]) for item in items)
    sample_shape = tuple(items[0]["ncct_images"].shape[1:])
    images = torch.zeros((len(items), max_files, *sample_shape), dtype=torch.float32)
    mask = torch.zeros((len(items), max_files), dtype=torch.bool)
    padded_files: list[list[str]] = []
    for batch_index, item in enumerate(items):
        patient_images = item["ncct_images"].to(dtype=torch.float32)
        if tuple(patient_images.shape[1:]) != sample_shape:
            raise ValueError("All images in a batch must share channel and spatial shape")
        count = patient_images.shape[0]
        images[batch_index, :count] = patient_images
        mask[batch_index, :count] = True
        padded_files.append(list(item["ncct_source_files"]) + [""] * (max_files - count))
    return {
        "patient_key": [str(item["patient_key"]) for item in items],
        "clinical_patient_id": [str(item["clinical_patient_id"]) for item in items],
        "ncct_images": images,
        "ncct_mask": mask,
        "ncct_source_files": padded_files,
        "clinical": torch.stack([item["clinical"] for item in items]),
        "label": torch.stack([item["label"] for item in items]),
    }
