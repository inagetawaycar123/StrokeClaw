"""Deterministic patient-level stratified fold assignment."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def assign_stratified_folds(
    records: Sequence[Mapping[str, Any]], n_splits: int = 5, seed: int = 20260806
) -> list[dict[str, Any]]:
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    keys = [str(record["patient_key"]) for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Patient keys must be unique before fold assignment")
    labels = np.asarray([int(float(record["binary_label"])) for record in records], dtype=np.int64)
    if set(labels.tolist()) - {0, 1}:
        raise ValueError("Stratified folds require binary labels 0/1")
    rng = np.random.default_rng(seed)
    fold_by_index: dict[int, int] = {}
    for label in (0, 1):
        indices = np.flatnonzero(labels == label)
        if indices.size < n_splits:
            raise ValueError(f"Class {label} has fewer patients than n_splits={n_splits}")
        rng.shuffle(indices)
        for offset, index in enumerate(indices.tolist()):
            fold_by_index[index] = offset % n_splits
    result: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        result.append(
            {
                "patient_key": str(record["patient_key"]),
                "clinical_patient_id": str(record.get("clinical_patient_id", "")),
                "binary_label": int(labels[index]),
                "split": "cv",
                "fold": fold_by_index[index],
                "available_channels": json.dumps(["internal_0_NCCT"], ensure_ascii=False),
                "missing_channel_mask": json.dumps([0]),
            }
        )
    return sorted(result, key=lambda item: (int(item["fold"]), item["patient_key"]))


def fold_summary(assignments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_fold: dict[str, Any] = {}
    for fold in sorted({int(item["fold"]) for item in assignments}):
        labels = [int(item["binary_label"]) for item in assignments if int(item["fold"]) == fold]
        counts = Counter(labels)
        per_fold[str(fold)] = {
            "patients": len(labels),
            "label_0": counts[0],
            "label_1": counts[1],
        }
    return {"patients": len(assignments), "folds": per_fold}


def write_splits(assignments: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "patient_key",
        "clinical_patient_id",
        "binary_label",
        "split",
        "fold",
        "available_channels",
        "missing_channel_mask",
    ]
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(assignments)
    temporary.replace(output)

