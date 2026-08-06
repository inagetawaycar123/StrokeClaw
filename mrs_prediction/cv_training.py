"""Leakage-safe nested cross-validation training for V0 mRS baselines."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import time
from collections import Counter, defaultdict
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .calibration import calibrated_probability, fit_temperature, sigmoid
from .dataset import MRSPatientDataset, mrs_patient_collate, read_manifest_rows
from .image_preprocessing import ImagePreprocessor, NCCTResizeCache
from .metrics import (
    average_precision,
    binary_metrics,
    calibration_curve,
    expected_calibration_error,
    pr_curve_points,
    require_both_classes,
    roc_auc,
    roc_curve_points,
    select_youden_threshold,
)
from .model import ClinicalOnlyMRSModel, NCCTClinicalMRSModel, NCCTOnlyMRSModel
from .preprocessing import ClinicalPreprocessor, _number_or_nan
from .schema import FEATURE_SCHEMA_VERSION
from .splits import assign_stratified_folds


MODEL_NAMES = ("clinical_only", "ncct_only", "ncct_clinical")
MODEL_MODES = ("baseline", "update_24h")
COHORT_SCHEMA_VERSION = "mrs-v0.2"
ONSET_SCHEMA_VERSION = "mrs-v0.2"


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scope_hash(records: Sequence[Mapping[str, Any]]) -> str:
    keys = sorted(str(record["patient_key"]) for record in records)
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _missing_24h(record: Mapping[str, Any]) -> bool:
    return not np.isfinite(_number_or_nan(record.get("NIHSS 24 HOURS")))


def _onset_warning(record: Mapping[str, Any]) -> bool:
    return (
        str(record.get("onset_to_ct_witness_status", "")) == "unwitnessed_or_wakeup"
        or "onset_time_unwitnessed_or_wakeup"
        in str(record.get("v0_clinical_data_warnings", ""))
    )


def load_training_config(path: str | Path) -> dict[str, Any]:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Training config must be a mapping")
    return config


def set_deterministic_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _label_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(int(float(record["binary_label"])) for record in records)
    return {"0": counts[0], "1": counts[1]}


def _missing_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "nihss_24h_missing": sum(_missing_24h(record) for record in records),
        "onset_to_ct_missing": sum(
            not np.isfinite(_number_or_nan(record.get("onset_to_ct_hours"))) for record in records
        ),
        "baseline_nihss_missing": sum(
            not np.isfinite(_number_or_nan(record.get("NIHSS Baseline"))) for record in records
        ),
        "onset_quality_warning": sum(_onset_warning(record) for record in records),
    }


def prepare_training_context(project_root: str | Path, config: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(project_root).resolve()
    manifest_path = root / str(config["data"]["manifest"])
    cohort_summary_path = root / str(config["data"]["cohort_summary"])
    records = read_manifest_rows(manifest_path, eligible_only=True)
    expected_count = int(config["data"]["expected_patients"])
    expected_labels = {str(k): int(v) for k, v in config["data"]["expected_labels"].items()}
    if len(records) != expected_count or _label_counts(records) != expected_labels:
        raise RuntimeError(
            f"Frozen cohort mismatch: patients={len(records)}, labels={_label_counts(records)}, "
            f"expected={expected_count}/{expected_labels}"
        )
    keys = [str(record["patient_key"]) for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Frozen cohort contains duplicate patient keys")
    forbidden = [
        record["patient_key"]
        for record in records
        if str(record.get("mapping_status", "")).lower() != "unique"
    ]
    if forbidden:
        raise RuntimeError(f"Frozen cohort contains non-unique mappings: {forbidden[:5]}")
    cohort_summary = json.loads(cohort_summary_path.read_text(encoding="utf-8"))
    if cohort_summary.get("v0_eligible_patients") != expected_count:
        raise RuntimeError("Cohort summary does not match frozen manifest")

    outer_folds = int(config["cross_validation"]["outer_folds"])
    fold_seed = int(config["cross_validation"]["fold_assignment_seed"])
    assignments = assign_stratified_folds(records, n_splits=outer_folds, seed=fold_seed)
    assignment_by_key = {str(item["patient_key"]): int(item["fold"]) for item in assignments}
    output_root = root / str(config["output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    fold_rows = []
    record_by_key = {str(record["patient_key"]): record for record in records}
    for item in assignments:
        record = record_by_key[str(item["patient_key"])]
        fold_rows.append(
            {
                **item,
                "nihss_24h_missing": _missing_24h(record),
                "onset_to_ct_missing": not np.isfinite(
                    _number_or_nan(record.get("onset_to_ct_hours"))
                ),
                "onset_to_ct_quality_warning": _onset_warning(record),
                "onset_to_ct_witness_status": record.get("onset_to_ct_witness_status", ""),
                "cohort_schema_version": COHORT_SCHEMA_VERSION,
                "onset_to_ct_schema_version": ONSET_SCHEMA_VERSION,
            }
        )
    _write_csv(output_root / "fold_assignments.csv", fold_rows)
    per_fold = {}
    for fold in range(outer_folds):
        subset = [record_by_key[key] for key, value in assignment_by_key.items() if value == fold]
        require_both_classes([int(float(record["binary_label"])) for record in subset], f"outer fold {fold}")
        per_fold[str(fold)] = {
            "patients": len(subset),
            "labels": _label_counts(subset),
            "missing": _missing_summary(subset),
        }
    training_manifest = {
        "artifact_role": "CV_TRAINING_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cohort_schema_version": COHORT_SCHEMA_VERSION,
        "onset_to_ct_schema_version": ONSET_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "patient_count": len(records),
        "label_distribution": _label_counts(records),
        "patient_key_hash": hashlib.sha256("\n".join(sorted(keys)).encode("utf-8")).hexdigest(),
        "source_files": {
            "manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "cohort_summary": {
                "path": str(cohort_summary_path),
                "sha256": _sha256(cohort_summary_path),
            },
        },
        "outer_fold_assignment": {
            "folds": outer_folds,
            "seed": fold_seed,
            "per_fold": per_fold,
        },
        "leakage_controls": {
            "outer_test_never_used_for_early_stopping": True,
            "outer_test_never_used_for_temperature": True,
            "outer_test_never_used_for_threshold": True,
            "clinical_preprocessor_fit_scope": "inner_train_only",
            "image_normalization_fit_scope": "inner_train_only",
            "patient_level_partitioning": True,
        },
        "production_approved": False,
    }
    _json_dump(output_root / "training_manifest.json", training_manifest)
    return {
        "project_root": root,
        "output_root": output_root,
        "records": records,
        "record_by_key": record_by_key,
        "assignment_by_key": assignment_by_key,
        "training_manifest": training_manifest,
    }


def stratified_inner_split(
    development_records: Sequence[Mapping[str, Any]], val_fraction: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0.05 <= val_fraction <= 0.5:
        raise ValueError("inner validation fraction must be between 0.05 and 0.5")
    rng = np.random.default_rng(seed)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for label in (0, 1):
        group = [dict(record) for record in development_records if int(float(record["binary_label"])) == label]
        if len(group) < 3:
            raise ValueError(f"Development class {label} is too small for inner split")
        indices = np.arange(len(group))
        rng.shuffle(indices)
        validation_count = max(1, int(round(len(group) * val_fraction)))
        validation.extend(group[index] for index in indices[:validation_count])
        train.extend(group[index] for index in indices[validation_count:])
    train.sort(key=lambda record: str(record["patient_key"]))
    validation.sort(key=lambda record: str(record["patient_key"]))
    require_both_classes([int(float(record["binary_label"])) for record in train], "inner train")
    require_both_classes(
        [int(float(record["binary_label"])) for record in validation], "inner validation"
    )
    if {record["patient_key"] for record in train} & {
        record["patient_key"] for record in validation
    }:
        raise RuntimeError("Patient leakage between inner train and validation")
    return train, validation


class _ClinicalDataset(Dataset[dict[str, Any]]):
    def __init__(
        self, records: Sequence[Mapping[str, Any]], preprocessor: ClinicalPreprocessor
    ) -> None:
        self.records = [dict(record) for record in records]
        self.preprocessor = preprocessor

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        return {
            "patient_key": str(record["patient_key"]),
            "clinical_patient_id": str(record.get("clinical_patient_id", "")),
            "clinical": torch.from_numpy(self.preprocessor.transform_one(record)),
            "label": torch.tensor(int(float(record["binary_label"])), dtype=torch.float32),
        }


def _clinical_collate(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    batch = list(items)
    return {
        "patient_key": [str(item["patient_key"]) for item in batch],
        "clinical_patient_id": [str(item["clinical_patient_id"]) for item in batch],
        "clinical": torch.stack([item["clinical"] for item in batch]),
        "label": torch.stack([item["label"] for item in batch]),
    }


def _make_model(model_name: str, clinical_dim: int, config: Mapping[str, Any]) -> nn.Module:
    model_config = dict(config["model"])
    common = {
        "embedding_dim": int(model_config["embedding_dim"]),
        "dropout": float(model_config["dropout"]),
    }
    if model_name == "clinical_only":
        return ClinicalOnlyMRSModel(clinical_dim, **common)
    imaging = {
        **common,
        "attention_dim": int(model_config["attention_dim"]),
        "base_channels": int(model_config["base_channels"]),
    }
    if model_name == "ncct_only":
        return NCCTOnlyMRSModel(**imaging)
    if model_name == "ncct_clinical":
        return NCCTClinicalMRSModel(
            clinical_dim,
            **imaging,
            fusion_dim=int(model_config["fusion_dim"]),
        )
    raise ValueError(f"Unknown model_name={model_name!r}")


def _make_loader(
    records: Sequence[Mapping[str, Any]],
    *,
    model_name: str,
    clinical_preprocessor: ClinicalPreprocessor,
    image_root: Path,
    image_cache: NCCTResizeCache | None,
    image_preprocessor: ImagePreprocessor | None,
    config: Mapping[str, Any],
    shuffle: bool,
    seed: int,
) -> DataLoader:
    is_imaging = model_name != "clinical_only"
    if is_imaging:
        if image_cache is None or image_preprocessor is None:
            raise ValueError("Imaging model requires image cache and fold-fitted preprocessor")
        dataset: Dataset = MRSPatientDataset(
            records,
            image_root,
            clinical_preprocessor,
            image_size=tuple(int(value) for value in config["image"]["image_size"]),
            max_ncct_files=config["image"].get("max_ncct_files"),
            image_cache=image_cache,
            image_preprocessor=image_preprocessor,
        )
        collate = mrs_patient_collate
        batch_size = int(config["training"]["image_batch_size"])
    else:
        dataset = _ClinicalDataset(records, clinical_preprocessor)
        collate = _clinical_collate
        batch_size = int(config["training"]["clinical_batch_size"])
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=int(config["training"]["num_workers"]),
        pin_memory=bool(config["training"].get("pin_memory", False)),
        collate_fn=collate,
        generator=generator,
        persistent_workers=bool(config["training"]["num_workers"] > 0),
    )


def _model_arguments(
    model_name: str,
    batch: Mapping[str, Any],
    device: torch.device,
    clinical_override: Mapping[str, torch.Tensor] | None = None,
) -> dict[str, torch.Tensor]:
    if clinical_override is None:
        clinical = batch["clinical"]
    else:
        clinical = torch.stack([clinical_override[key] for key in batch["patient_key"]])
    arguments = {"clinical": clinical.to(device, non_blocking=True)}
    if model_name != "clinical_only":
        arguments.update(
            {
                "ncct_images": batch["ncct_images"].to(device, non_blocking=True),
                "ncct_mask": batch["ncct_mask"].to(device, non_blocking=True),
            }
        )
    return arguments


def _predict(
    model: nn.Module,
    loader: DataLoader,
    model_name: str,
    device: torch.device,
    *,
    mixed_precision: bool,
    clinical_override: Mapping[str, torch.Tensor] | None = None,
) -> dict[str, Any]:
    model.eval()
    keys: list[str] = []
    labels: list[float] = []
    logits: list[float] = []
    with torch.no_grad():
        for batch in loader:
            arguments = _model_arguments(model_name, batch, device, clinical_override)
            context = (
                torch.amp.autocast("cuda", enabled=True)
                if mixed_precision and device.type == "cuda"
                else nullcontext()
            )
            with context:
                output = model(**arguments)
            keys.extend(batch["patient_key"])
            labels.extend(batch["label"].cpu().numpy().astype(float).tolist())
            logits.extend(output["logit"].detach().float().cpu().numpy().astype(float).tolist())
    return {
        "patient_key": keys,
        "label": np.asarray(labels, dtype=np.int64),
        "logit": np.asarray(logits, dtype=np.float64),
    }


def _plot_curves(
    output_dir: Path,
    labels: np.ndarray,
    raw_probability: np.ndarray,
    calibrated: np.ndarray,
    threshold: float,
    ece_bins: int,
) -> None:
    roc_raw = roc_curve_points(labels, raw_probability)
    roc_cal = roc_curve_points(labels, calibrated)
    fig, axis = plt.subplots(figsize=(5.5, 5.0))
    axis.plot(roc_raw["fpr"], roc_raw["tpr"], label=f"Raw AUC={roc_auc(labels, raw_probability):.3f}")
    axis.plot(roc_cal["fpr"], roc_cal["tpr"], label=f"Calibrated AUC={roc_auc(labels, calibrated):.3f}")
    axis.plot([0, 1], [0, 1], "--", color="gray")
    axis.set(xlabel="False positive rate", ylabel="True positive rate", title="Outer-test ROC")
    axis.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(output_dir / "roc_curve.png", dpi=160)
    plt.close(fig)

    pr_raw = pr_curve_points(labels, raw_probability)
    pr_cal = pr_curve_points(labels, calibrated)
    fig, axis = plt.subplots(figsize=(5.5, 5.0))
    axis.plot(pr_raw["recall"], pr_raw["precision"], label=f"Raw AP={average_precision(labels, raw_probability):.3f}")
    axis.plot(pr_cal["recall"], pr_cal["precision"], label=f"Calibrated AP={average_precision(labels, calibrated):.3f}")
    axis.set(xlabel="Recall", ylabel="Precision", title="Outer-test precision-recall")
    axis.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(output_dir / "pr_curve.png", dpi=160)
    plt.close(fig)

    raw_curve = calibration_curve(labels, raw_probability, bins=ece_bins)
    calibrated_curve = calibration_curve(labels, calibrated, bins=ece_bins)
    fig, axis = plt.subplots(figsize=(5.5, 5.0))
    axis.plot([0, 1], [0, 1], "--", color="gray", label="Ideal")
    axis.plot(raw_curve["mean_predicted"], raw_curve["fraction_positive"], "o-", label="Raw")
    axis.plot(
        calibrated_curve["mean_predicted"],
        calibrated_curve["fraction_positive"],
        "o-",
        label="Calibrated",
    )
    axis.set(xlabel="Mean predicted risk", ylabel="Observed event rate", title="Outer-test calibration")
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "calibration_curve.png", dpi=160)
    plt.close(fig)

    primary = binary_metrics(labels, calibrated, threshold=threshold, ece_bins=ece_bins)
    matrix = np.asarray(primary["confusion_matrix"], dtype=int)
    fig, axis = plt.subplots(figsize=(4.8, 4.4))
    image = axis.imshow(matrix, cmap="Blues")
    for row in range(2):
        for column in range(2):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
    axis.set_xticks([0, 1], ["Pred 0", "Pred 1"])
    axis.set_yticks([0, 1], ["True 0", "True 1"])
    axis.set_title(f"Outer-test confusion matrix (threshold={threshold:.3f})")
    fig.colorbar(image, ax=axis, fraction=0.046)
    fig.tight_layout()
    fig.savefig(output_dir / "confusion_matrix.png", dpi=160)
    plt.close(fig)


def _prediction_rows(
    prediction: Mapping[str, Any],
    record_by_key: Mapping[str, Mapping[str, Any]],
    *,
    model_mode: str,
    model_name: str,
    fold: int,
    seed: int,
    temperature: float,
    decision_threshold: float,
    analysis: str,
) -> list[dict[str, Any]]:
    raw_probability = sigmoid(prediction["logit"])
    calibrated = calibrated_probability(prediction["logit"], temperature)
    rows = []
    for index, key in enumerate(prediction["patient_key"]):
        record = record_by_key[key]
        baseline = _number_or_nan(record.get("NIHSS Baseline"))
        rows.append(
            {
                "patient_key": key,
                "true_label": int(prediction["label"][index]),
                "analysis": analysis,
                "model_mode": model_mode,
                "model_name": model_name,
                "fold": fold,
                "seed": seed,
                "raw_logit": float(prediction["logit"][index]),
                "raw_probability": float(raw_probability[index]),
                "calibrated_poor_risk": float(calibrated[index]),
                "calibrated_good_probability": float(1.0 - calibrated[index]),
                "decision_threshold": float(decision_threshold),
                "predicted_class": int(calibrated[index] >= decision_threshold),
                "baseline_nihss": "" if not np.isfinite(baseline) else float(baseline),
                "nihss_24h_missing": _missing_24h(record),
                "onset_to_ct_quality_warning": _onset_warning(record),
                "artifact_role": "CV_EVAL_ONLY",
                "production_approved": False,
                "is_real_inference": False,
            }
        )
    return rows


def _fit_or_load_image_preprocessor(
    path: Path,
    train_records: Sequence[Mapping[str, Any]],
    cache: NCCTResizeCache,
    max_ncct_files: int | None,
) -> ImagePreprocessor:
    expected_hash = _scope_hash(train_records)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        preprocessor = ImagePreprocessor.from_dict(payload)
        if preprocessor.fit_scope_hash != expected_hash:
            raise RuntimeError(f"Cached image preprocessor has wrong inner-train scope: {path}")
        return preprocessor
    preprocessor = ImagePreprocessor.fit(
        train_records, cache, max_ncct_files=max_ncct_files
    )
    _json_dump(path, preprocessor.to_dict())
    return preprocessor


def run_fold(
    context: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    model_mode: str,
    model_name: str,
    fold: int,
    seed: int,
    analysis: str = "main",
    image_cache: NCCTResizeCache | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if model_mode not in MODEL_MODES or model_name not in MODEL_NAMES:
        raise ValueError(f"Unsupported run {model_mode}/{model_name}")
    root: Path = context["project_root"]
    output_root: Path = context["output_root"]
    all_records: list[dict[str, Any]] = list(context["records"])
    assignment_by_key: dict[str, int] = dict(context["assignment_by_key"])
    if analysis == "sensitivity_witnessed_only":
        all_records = [record for record in all_records if not _onset_warning(record)]
    outer_test = [record for record in all_records if assignment_by_key[str(record["patient_key"])] == fold]
    development = [record for record in all_records if assignment_by_key[str(record["patient_key"])] != fold]
    require_both_classes([int(float(record["binary_label"])) for record in outer_test], "outer test")
    inner_seed = int(seed + fold * 1009 + (7919 if analysis != "main" else 0))
    inner_train, inner_validation = stratified_inner_split(
        development,
        float(config["cross_validation"]["inner_validation_fraction"]),
        inner_seed,
    )
    train_keys = {record["patient_key"] for record in inner_train}
    validation_keys = {record["patient_key"] for record in inner_validation}
    test_keys = {record["patient_key"] for record in outer_test}
    if train_keys & validation_keys or train_keys & test_keys or validation_keys & test_keys:
        raise RuntimeError("Patient leakage detected across inner train/validation/outer test")

    base = output_root if analysis == "main" else output_root / "sensitivity_analysis"
    run_dir = base / model_mode / model_name / f"seed_{seed}" / f"fold_{fold}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists() and not force:
        existing = json.loads(metrics_path.read_text(encoding="utf-8"))
        if existing.get("status") == "completed":
            return existing

    run_started = time.time()
    set_deterministic_seed(seed + fold * 10007)
    device_requested = str(config["training"]["device"])
    if device_requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device(
        "cuda" if device_requested == "cuda" or (device_requested == "auto" and torch.cuda.is_available()) else "cpu"
    )
    mixed_precision = bool(config["training"]["mixed_precision"] and device.type == "cuda")
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    clinical_preprocessor = ClinicalPreprocessor(model_mode).fit(inner_train)
    image_preprocessor = None
    if model_name != "clinical_only":
        if image_cache is None:
            raise ValueError("image_cache is required for imaging runs")
        image_preprocessor = _fit_or_load_image_preprocessor(
            output_root
            / "preprocessors"
            / analysis
            / f"seed_{seed}"
            / f"fold_{fold}"
            / "image_preprocessor.json",
            inner_train,
            image_cache,
            config["image"].get("max_ncct_files"),
        )
        if image_preprocessor.fitted_patient_count != len(inner_train):
            raise RuntimeError("Image preprocessor was not fitted on exactly inner train")

    image_root = root / str(config["data"]["image_root"])
    loaders = {
        split: _make_loader(
            records,
            model_name=model_name,
            clinical_preprocessor=clinical_preprocessor,
            image_root=image_root,
            image_cache=image_cache,
            image_preprocessor=image_preprocessor,
            config=config,
            shuffle=split == "train",
            seed=seed + fold * 101 + index,
        )
        for index, (split, records) in enumerate(
            (("train", inner_train), ("validation", inner_validation), ("test", outer_test))
        )
    }
    model = _make_model(model_name, clinical_preprocessor.output_dim, config).to(device)
    positives = sum(int(float(record["binary_label"])) == 1 for record in inner_train)
    negatives = len(inner_train) - positives
    if not positives or not negatives:
        raise RuntimeError("Inner train lacks a class for pos_weight")
    pos_weight = negatives / positives
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["training"]["learning_rate"][model_name]),
        weight_decay=float(config["training"]["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=float(config["training"]["scheduler_factor"]),
        patience=int(config["training"]["scheduler_patience"]),
        min_lr=float(config["training"]["minimum_learning_rate"]),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=mixed_precision)
    history: list[dict[str, Any]] = []
    best_auc = -math.inf
    best_loss = math.inf
    best_epoch = 0
    stale_epochs = 0
    best_state_path = run_dir / "best_training_state.pt"
    last_state_path = run_dir / "last_checkpoint.pt"

    for epoch in range(1, int(config["training"]["max_epochs"]) + 1):
        epoch_started = time.time()
        model.train()
        total_loss = 0.0
        patient_count = 0
        for batch in loaders["train"]:
            optimizer.zero_grad(set_to_none=True)
            arguments = _model_arguments(model_name, batch, device)
            labels = batch["label"].to(device, non_blocking=True)
            context_manager = (
                torch.amp.autocast("cuda", enabled=True) if mixed_precision else nullcontext()
            )
            with context_manager:
                logits = model(**arguments)["logit"]
                loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss at epoch {epoch}")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["training"]["gradient_clip_norm"])
            )
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.detach().cpu()) * len(labels)
            patient_count += len(labels)

        validation_prediction = _predict(
            model,
            loaders["validation"],
            model_name,
            device,
            mixed_precision=mixed_precision,
        )
        validation_probability = sigmoid(validation_prediction["logit"])
        validation_metrics = binary_metrics(
            validation_prediction["label"],
            validation_probability,
            threshold=0.5,
            ece_bins=int(config["evaluation"]["ece_bins"]),
        )
        validation_loss = float(
            np.mean(
                np.logaddexp(0.0, validation_prediction["logit"])
                - validation_prediction["label"] * validation_prediction["logit"]
            )
        )
        validation_auc = float(validation_metrics["roc_auc"])
        if not np.isfinite(validation_auc):
            raise RuntimeError("Validation ROC-AUC is non-finite")
        scheduler.step(validation_auc)
        improved = validation_auc > best_auc + float(config["training"]["auc_min_delta"])
        if not improved and abs(validation_auc - best_auc) <= float(config["training"]["auc_min_delta"]):
            improved = validation_loss < best_loss - 1e-8
        if improved:
            best_auc = validation_auc
            best_loss = validation_loss
            best_epoch = epoch
            stale_epochs = 0
            torch.save(
                {
                    "model_state_dict": {
                        key: value.detach().cpu() for key, value in model.state_dict().items()
                    },
                    "epoch": epoch,
                    "validation_roc_auc": best_auc,
                    "validation_loss": best_loss,
                },
                best_state_path,
            )
        else:
            stale_epochs += 1
        epoch_row = {
            "epoch": epoch,
            "train_loss": total_loss / max(patient_count, 1),
            "validation_loss": validation_loss,
            "validation_roc_auc": validation_auc,
            "validation_pr_auc": validation_metrics["pr_auc"],
            "validation_brier_score": validation_metrics["brier_score"],
            "learning_rate": optimizer.param_groups[0]["lr"],
            "improved": improved,
            "stale_epochs": stale_epochs,
            "epoch_seconds": time.time() - epoch_started,
        }
        history.append(epoch_row)
        _write_csv(run_dir / "training_history.csv", history)
        torch.save(
            {
                "artifact_role": "CV_TRAINING_RESUME_STATE",
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "scaler_state_dict": scaler.state_dict(),
                "epoch": epoch,
                "best_epoch": best_epoch,
                "best_validation_auc": best_auc,
                "stale_epochs": stale_epochs,
                "production_approved": False,
            },
            last_state_path,
        )
        if stale_epochs >= int(config["training"]["early_stopping_patience"]):
            break

    if not best_state_path.exists():
        raise RuntimeError("Training ended without a best validation checkpoint")
    best_state = torch.load(best_state_path, map_location="cpu", weights_only=False)
    model.load_state_dict(best_state["model_state_dict"])
    model.to(device)
    validation_prediction = _predict(
        model, loaders["validation"], model_name, device, mixed_precision=mixed_precision
    )
    test_prediction = _predict(
        model, loaders["test"], model_name, device, mixed_precision=mixed_precision
    )
    temperature = fit_temperature(validation_prediction["logit"], validation_prediction["label"])
    validation_raw = sigmoid(validation_prediction["logit"])
    validation_calibrated = calibrated_probability(validation_prediction["logit"], temperature)
    raw_threshold = select_youden_threshold(validation_prediction["label"], validation_raw)
    calibrated_threshold = select_youden_threshold(
        validation_prediction["label"], validation_calibrated
    )
    test_raw = sigmoid(test_prediction["logit"])
    test_calibrated = calibrated_probability(test_prediction["logit"], temperature)
    ece_bins = int(config["evaluation"]["ece_bins"])
    variants = {
        "raw_threshold_0_5": binary_metrics(
            test_prediction["label"], test_raw, threshold=0.5, ece_bins=ece_bins
        ),
        "raw_validation_youden": binary_metrics(
            test_prediction["label"], test_raw, threshold=raw_threshold, ece_bins=ece_bins
        ),
        "calibrated_threshold_0_5": binary_metrics(
            test_prediction["label"], test_calibrated, threshold=0.5, ece_bins=ece_bins
        ),
        "calibrated_validation_youden": binary_metrics(
            test_prediction["label"],
            test_calibrated,
            threshold=calibrated_threshold,
            ece_bins=ece_bins,
        ),
    }

    onset_importance = None
    if model_name != "ncct_only":
        values = np.stack(
            [clinical_preprocessor.transform_one(record) for record in outer_test]
        )
        feature_index = clinical_preprocessor.feature_names.index("onset_to_ct_time")
        missing_index = len(clinical_preprocessor.feature_names) + feature_index
        permutation = np.random.default_rng(seed + fold * 2029 + 17).permutation(len(outer_test))
        permuted = values.copy()
        permuted[:, feature_index] = values[permutation, feature_index]
        permuted[:, missing_index] = values[permutation, missing_index]
        override = {
            str(record["patient_key"]): torch.from_numpy(permuted[index].astype(np.float32))
            for index, record in enumerate(outer_test)
        }
        permuted_prediction = _predict(
            model,
            loaders["test"],
            model_name,
            device,
            mixed_precision=mixed_precision,
            clinical_override=override,
        )
        permuted_probability = calibrated_probability(permuted_prediction["logit"], temperature)
        onset_importance = {
            "method": "outer_test_foldwise_permutation_of_onset_value_and_missing_indicator",
            "roc_auc_drop": float(
                roc_auc(test_prediction["label"], test_calibrated)
                - roc_auc(test_prediction["label"], permuted_probability)
            ),
            "mean_absolute_probability_change": float(
                np.mean(np.abs(test_calibrated - permuted_probability))
            ),
            "not_causal": True,
        }

    validation_rows = _prediction_rows(
        validation_prediction,
        context["record_by_key"],
        model_mode=model_mode,
        model_name=model_name,
        fold=fold,
        seed=seed,
        temperature=temperature,
        decision_threshold=calibrated_threshold,
        analysis=analysis,
    )
    test_rows = _prediction_rows(
        test_prediction,
        context["record_by_key"],
        model_mode=model_mode,
        model_name=model_name,
        fold=fold,
        seed=seed,
        temperature=temperature,
        decision_threshold=calibrated_threshold,
        analysis=analysis,
    )
    _write_csv(run_dir / "validation_predictions.csv", validation_rows)
    _write_csv(run_dir / "test_predictions.csv", test_rows)
    _plot_curves(
        run_dir,
        test_prediction["label"],
        test_raw,
        test_calibrated,
        calibrated_threshold,
        ece_bins,
    )

    split_summary = {
        "inner_train": {
            "patients": len(inner_train),
            "labels": _label_counts(inner_train),
            "missing": _missing_summary(inner_train),
            "patient_key_hash": _scope_hash(inner_train),
        },
        "inner_validation": {
            "patients": len(inner_validation),
            "labels": _label_counts(inner_validation),
            "missing": _missing_summary(inner_validation),
            "patient_key_hash": _scope_hash(inner_validation),
        },
        "outer_test": {
            "patients": len(outer_test),
            "labels": _label_counts(outer_test),
            "missing": _missing_summary(outer_test),
            "patient_key_hash": _scope_hash(outer_test),
        },
    }
    model_config = {
        "name": model_name,
        "class_name": model.__class__.__name__,
        **dict(config["model"]),
        "clinical_input_dim": clinical_preprocessor.output_dim,
    }
    bundle = {
        "artifact_role": "CV_EVAL_ONLY",
        "status": "trained_cross_validation_evaluation_only",
        "weights_source": "real_patient_training",
        "production_approved": False,
        "is_real_inference": False,
        "online_loading_permitted": False,
        "model_state_dict": {
            key: value.detach().cpu() for key, value in model.state_dict().items()
        },
        "model_config": model_config,
        "model_name": model_name,
        "model_mode": model_mode,
        "clinical_feature_names": list(clinical_preprocessor.feature_names),
        "clinical_preprocessor": clinical_preprocessor.to_dict(),
        "image_preprocessing_config": (
            image_preprocessor.to_dict()
            if image_preprocessor is not None
            else {"status": "not_applicable_clinical_only"}
        ),
        "class_mapping": {"0": "mRS 0-2 / good prognosis", "1": "mRS 3-6 / poor prognosis"},
        "temperature_scaling_parameter": temperature,
        "decision_threshold": calibrated_threshold,
        "raw_validation_youden_threshold": raw_threshold,
        "fold_id": fold,
        "seed": seed,
        "analysis": analysis,
        "cohort_schema_version": COHORT_SCHEMA_VERSION,
        "onset_to_ct_schema_version": ONSET_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "training_data_summary": {
            **split_summary,
            "pos_weight_inner_train": pos_weight,
            "best_epoch": best_epoch,
            "best_validation_roc_auc": best_auc,
        },
    }
    bundle_path = run_dir / "fold_bundle.pt"
    torch.save(bundle, bundle_path)
    reloaded_bundle = torch.load(bundle_path, map_location="cpu", weights_only=False)
    if reloaded_bundle.get("production_approved") is not False or reloaded_bundle.get("artifact_role") != "CV_EVAL_ONLY":
        raise RuntimeError("CV bundle safety flags are invalid")
    reloaded = _make_model(model_name, clinical_preprocessor.output_dim, config).to(device)
    reloaded.load_state_dict(reloaded_bundle["model_state_dict"])
    reloaded_prediction = _predict(
        reloaded,
        loaders["validation"],
        model_name,
        device,
        mixed_precision=mixed_precision,
    )
    reload_difference = float(
        np.max(np.abs(reloaded_prediction["logit"] - validation_prediction["logit"]))
    )
    if reload_difference > 1e-5:
        raise RuntimeError(f"Reloaded bundle prediction mismatch: {reload_difference}")

    fold_rows = []
    for variant_name, values in variants.items():
        probability_variant = "calibrated" if variant_name.startswith("calibrated") else "raw"
        threshold_type = "validation_youden" if variant_name.endswith("validation_youden") else "fixed_0.5"
        flat = {key: value for key, value in values.items() if key != "confusion_matrix"}
        fold_rows.append(
            {
                "analysis": analysis,
                "model_mode": model_mode,
                "model_name": model_name,
                "seed": seed,
                "fold": fold,
                "probability_variant": probability_variant,
                "threshold_type": threshold_type,
                **flat,
                "confusion_matrix": json.dumps(values["confusion_matrix"]),
            }
        )
    elapsed = time.time() - run_started
    metrics_payload = {
        "status": "completed",
        "artifact_role": "CV_EVAL_ONLY",
        "production_approved": False,
        "is_real_inference": False,
        "analysis": analysis,
        "model_mode": model_mode,
        "model_name": model_name,
        "seed": seed,
        "fold": fold,
        "split_summary": split_summary,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "best_validation_roc_auc": best_auc,
        "temperature_scaling_parameter": temperature,
        "raw_validation_youden_threshold": raw_threshold,
        "decision_threshold": calibrated_threshold,
        "outer_test_metrics": variants,
        "onset_to_ct_permutation_importance": onset_importance,
        "checkpoint_reload_max_abs_logit_difference": reload_difference,
        "runtime": {
            "device": str(device),
            "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
            "mixed_precision": mixed_precision,
            "elapsed_seconds": elapsed,
            "mean_epoch_seconds": float(np.mean([row["epoch_seconds"] for row in history])),
            "gpu_peak_memory_mb": (
                float(torch.cuda.max_memory_allocated(device) / 1024**2)
                if device.type == "cuda"
                else 0.0
            ),
            "num_workers": int(config["training"]["num_workers"]),
        },
        "fold_metric_rows": fold_rows,
        "bundle": str(bundle_path),
    }
    _json_dump(run_dir / "fold_config.json", {
        "model_mode": model_mode,
        "model_name": model_name,
        "fold": fold,
        "seed": seed,
        "analysis": analysis,
        "config": config,
        "split_summary": split_summary,
    })
    _json_dump(metrics_path, metrics_payload)
    return metrics_payload


def _classification_from_rows(labels: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    tp = int(((labels == 1) & (predicted == 1)).sum())
    tn = int(((labels == 0) & (predicted == 0)).sum())
    fp = int(((labels == 0) & (predicted == 1)).sum())
    fn = int(((labels == 1) & (predicted == 0)).sum())
    divide = lambda a, b: float(a / b) if b else 0.0
    sensitivity = divide(tp, tp + fn)
    precision = divide(tp, tp + fp)
    return {
        "accuracy": divide(tp + tn, len(labels)),
        "sensitivity": sensitivity,
        "specificity": divide(tn, tn + fp),
        "precision": precision,
        "recall": sensitivity,
        "f1": divide(2 * precision * sensitivity, precision + sensitivity),
        "ppv": precision,
        "npv": divide(tn, tn + fn),
        "confusion_matrix": [[tn, fp], [fn, tp]],
    }


def _aggregate_one_analysis(
    base: Path,
    *,
    expected_patients: int,
    analysis: str,
    output_root: Path,
    ece_bins: int,
) -> dict[str, Any]:
    metrics_files = sorted(base.glob("*/*/seed_*/fold_*/metrics.json"))
    all_fold_rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    onset_rows: list[dict[str, Any]] = []
    for path in metrics_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "completed":
            failures.append({"path": str(path), "status": payload.get("status")})
            continue
        all_fold_rows.extend(payload["fold_metric_rows"])
        if payload.get("onset_to_ct_permutation_importance"):
            onset_rows.append(
                {
                    "model_mode": payload["model_mode"],
                    "model_name": payload["model_name"],
                    "seed": payload["seed"],
                    "fold": payload["fold"],
                    **payload["onset_to_ct_permutation_importance"],
                }
            )
        prediction_path = path.parent / "test_predictions.csv"
        with prediction_path.open("r", encoding="utf-8-sig", newline="") as handle:
            predictions.extend(csv.DictReader(handle))
    destination = output_root if analysis == "main" else output_root / "sensitivity_analysis"
    _write_csv(destination / "fold_metrics.csv", all_fold_rows)
    _write_csv(destination / "oof_predictions.csv", predictions)
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        grouped[(row["model_mode"], row["model_name"], int(row["seed"]))].append(row)
    oof_results = []
    for (mode, model, seed), rows in sorted(grouped.items()):
        if len(rows) != expected_patients:
            failures.append(
                {
                    "model_mode": mode,
                    "model_name": model,
                    "seed": seed,
                    "error": f"OOF patient count {len(rows)} != {expected_patients}",
                }
            )
            continue
        keys = [row["patient_key"] for row in rows]
        if len(keys) != len(set(keys)):
            raise RuntimeError(f"Duplicate OOF patient for {analysis}/{mode}/{model}/seed={seed}")
        labels = np.asarray([int(row["true_label"]) for row in rows], dtype=np.int64)
        raw = np.asarray([float(row["raw_probability"]) for row in rows])
        calibrated = np.asarray([float(row["calibrated_poor_risk"]) for row in rows])
        predicted = np.asarray([int(row["predicted_class"]) for row in rows], dtype=np.int64)
        result = {
            "analysis": analysis,
            "model_mode": mode,
            "model_name": model,
            "seed": seed,
            "patient_count": len(rows),
            "raw": {
                "roc_auc": roc_auc(labels, raw),
                "pr_auc": average_precision(labels, raw),
                "brier_score": float(np.mean((raw - labels) ** 2)),
                "expected_calibration_error": expected_calibration_error(labels, raw, bins=ece_bins),
            },
            "calibrated_fold_threshold": {
                "roc_auc": roc_auc(labels, calibrated),
                "pr_auc": average_precision(labels, calibrated),
                "brier_score": float(np.mean((calibrated - labels) ** 2)),
                "expected_calibration_error": expected_calibration_error(labels, calibrated, bins=ece_bins),
                **_classification_from_rows(labels, predicted),
            },
        }
        oof_results.append(result)
    return {
        "analysis": analysis,
        "fold_rows": all_fold_rows,
        "oof_rows": predictions,
        "oof_results": oof_results,
        "onset_importance_rows": onset_rows,
        "failures": failures,
    }


def _mean_std(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {"mean": float(array.mean()), "std": float(array.std(ddof=1)) if len(array) > 1 else 0.0}


def aggregate_training_outputs(context: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    output_root: Path = context["output_root"]
    ece_bins = int(config["evaluation"]["ece_bins"])
    main = _aggregate_one_analysis(
        output_root,
        expected_patients=len(context["records"]),
        analysis="main",
        output_root=output_root,
        ece_bins=ece_bins,
    )
    sensitivity_records = [record for record in context["records"] if not _onset_warning(record)]
    sensitivity_base = output_root / "sensitivity_analysis"
    sensitivity = _aggregate_one_analysis(
        sensitivity_base,
        expected_patients=len(sensitivity_records),
        analysis="sensitivity_witnessed_only",
        output_root=output_root,
        ece_bins=ece_bins,
    ) if sensitivity_base.exists() else {
        "analysis": "sensitivity_witnessed_only",
        "fold_rows": [],
        "oof_rows": [],
        "oof_results": [],
        "onset_importance_rows": [],
        "failures": [],
    }

    metric_names = ("roc_auc", "pr_auc", "brier_score", "expected_calibration_error")
    summaries = []
    grouped = defaultdict(list)
    for result in main["oof_results"]:
        grouped[(result["model_mode"], result["model_name"])].append(result)
    primary_fold_rows = [
        row
        for row in main["fold_rows"]
        if row["probability_variant"] == "calibrated"
        and row["threshold_type"] == "validation_youden"
    ]
    for (mode, model), results in sorted(grouped.items()):
        raw_metrics = {
            metric: _mean_std([result["raw"][metric] for result in results])
            for metric in metric_names
        }
        calibrated_metrics = {
            metric: _mean_std(
                [result["calibrated_fold_threshold"][metric] for result in results]
            )
            for metric in metric_names
        }
        model_fold_rows = [
            row
            for row in primary_fold_rows
            if row["model_mode"] == mode and row["model_name"] == model
        ]
        five_fold_by_seed = []
        for seed in sorted({int(row["seed"]) for row in model_fold_rows}):
            seed_rows = [row for row in model_fold_rows if int(row["seed"]) == seed]
            five_fold_by_seed.append(
                {
                    "seed": seed,
                    "fold_count": len(seed_rows),
                    "metrics": {
                        metric: _mean_std([float(row[metric]) for row in seed_rows])
                        for metric in metric_names
                    },
                }
            )
        summaries.append(
            {
                "model_mode": mode,
                "model_name": model,
                "seed_count": len(results),
                "raw_oof_across_seeds": raw_metrics,
                "calibrated_oof_across_seeds": calibrated_metrics,
                "five_fold_by_seed": five_fold_by_seed,
                "fold_metrics_across_all_seeds": {
                    metric: _mean_std([float(row[metric]) for row in model_fold_rows])
                    for metric in metric_names
                },
            }
        )

    primary_seed = int(config["cross_validation"]["seeds"][0])
    primary = {
        (item["model_mode"], item["model_name"]): item
        for item in main["oof_results"]
        if item["seed"] == primary_seed
    }
    result_by_key_seed = {
        (item["model_mode"], item["model_name"], int(item["seed"])): item
        for item in main["oof_results"]
    }
    configured_seeds = sorted({int(item["seed"]) for item in main["oof_results"]})
    gains = {"update_24h_vs_baseline": {}, "ncct_clinical_gain": {}}
    for model in MODEL_NAMES:
        paired = []
        for seed in configured_seeds:
            baseline = result_by_key_seed.get(("baseline", model, seed))
            update = result_by_key_seed.get(("update_24h", model, seed))
            if baseline and update:
                paired.append((baseline, update))
        if paired:
            gains["update_24h_vs_baseline"][model] = {
                metric: _mean_std(
                    [
                        update["calibrated_fold_threshold"][metric]
                        - baseline["calibrated_fold_threshold"][metric]
                        for baseline, update in paired
                    ]
                )
                for metric in metric_names
            }
    for mode in MODEL_MODES:
        gains["ncct_clinical_gain"][mode] = {}
        for comparator in ("clinical_only", "ncct_only"):
            paired = []
            for seed in configured_seeds:
                fusion = result_by_key_seed.get((mode, "ncct_clinical", seed))
                reference = result_by_key_seed.get((mode, comparator, seed))
                if fusion and reference:
                    paired.append((reference, fusion))
            if paired:
                gains["ncct_clinical_gain"][mode][f"vs_{comparator}"] = {
                    metric: _mean_std(
                        [
                            fusion["calibrated_fold_threshold"][metric]
                            - reference["calibrated_fold_threshold"][metric]
                            for reference, fusion in paired
                        ]
                    )
                    for metric in metric_names
                }

    sensitivity_comparison = []
    sensitivity_primary = {
        (item["model_mode"], item["model_name"]): item
        for item in sensitivity["oof_results"]
        if item["seed"] == primary_seed
    }
    for key, result in sorted(sensitivity_primary.items()):
        main_result = primary.get(key)
        if main_result:
            sensitivity_comparison.append(
                {
                    "model_mode": key[0],
                    "model_name": key[1],
                    "main_patients": main_result["patient_count"],
                    "sensitivity_patients": result["patient_count"],
                    "metric_difference_sensitivity_minus_main": {
                        metric: result["calibrated_fold_threshold"][metric]
                        - main_result["calibrated_fold_threshold"][metric]
                        for metric in metric_names
                    },
                }
            )

    onset_summary = {}
    for analysis_name, rows in (
        ("main", main["onset_importance_rows"]),
        ("sensitivity", sensitivity["onset_importance_rows"]),
    ):
        grouped_onset = defaultdict(list)
        for row in rows:
            grouped_onset[(row["model_mode"], row["model_name"])].append(row)
        onset_summary[analysis_name] = [
            {
                "model_mode": mode,
                "model_name": model,
                "run_count": len(values),
                "roc_auc_drop": _mean_std([float(value["roc_auc_drop"]) for value in values]),
                "mean_absolute_probability_change": _mean_std(
                    [float(value["mean_absolute_probability_change"]) for value in values]
                ),
            }
            for (mode, model), values in sorted(grouped_onset.items())
        ]

    candidates = {}
    for mode in MODEL_MODES:
        available = [item for item in summaries if item["model_mode"] == mode]
        if available:
            chosen = max(
                available,
                key=lambda item: (
                    item["calibrated_oof_across_seeds"]["roc_auc"]["mean"],
                    item["calibrated_oof_across_seeds"]["pr_auc"]["mean"],
                    -item["calibrated_oof_across_seeds"]["brier_score"]["mean"],
                ),
            )
            candidates[mode] = {
                "model_name": chosen["model_name"],
                "selection_basis": "three-seed mean patient-level outer-fold OOF ranking; CV candidate only",
                "metrics_mean_std": chosen["calibrated_oof_across_seeds"],
                "production_approved": False,
            }
    comparison = {
        "artifact_role": "CV_MODEL_COMPARISON_ONLY",
        "production_approved": False,
        "is_real_inference": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cohort": {
            "main_patients": len(context["records"]),
            "sensitivity_witnessed_only_patients": len(sensitivity_records),
            "label_distribution": _label_counts(context["records"]),
            "sensitivity_label_distribution": _label_counts(sensitivity_records),
        },
        "primary_seed": primary_seed,
        "oof_results": main["oof_results"],
        "cross_seed_summary": summaries,
        "gains": gains,
        "sensitivity_results": sensitivity["oof_results"],
        "sensitivity_comparison": sensitivity_comparison,
        "onset_to_ct_permutation_importance": {
            "main": main["onset_importance_rows"],
            "sensitivity": sensitivity["onset_importance_rows"],
            "summary": onset_summary,
            "interpretation": "permutation importance is model reliance, not causal effect",
        },
        "failures": [*main["failures"], *sensitivity["failures"]],
        "recommended_cv_candidates": candidates,
    }
    _json_dump(output_root / "model_comparison.json", comparison)
    _write_comparison_markdown(output_root / "model_comparison.md", comparison)
    return comparison


def _write_comparison_markdown(path: Path, comparison: Mapping[str, Any]) -> None:
    lines = [
        "# 90-day mRS V0.2 cross-validation comparison",
        "",
        "> All checkpoints are CV_EVAL_ONLY. None is approved for production or online inference.",
        "",
        f"Main cohort: {comparison['cohort']['main_patients']} patients; "
        f"witnessed-only sensitivity cohort: {comparison['cohort']['sensitivity_witnessed_only_patients']} patients.",
        "",
        "## Three-seed patient-level OOF results",
        "",
        "| Mode | Model | Calibrated ROC-AUC | Calibrated PR-AUC | Brier raw→cal | ECE raw→cal |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for result in comparison["cross_seed_summary"]:
        raw = result["raw_oof_across_seeds"]
        calibrated = result["calibrated_oof_across_seeds"]
        lines.append(
            f"| {result['model_mode']} | {result['model_name']} | "
            f"{calibrated['roc_auc']['mean']:.4f}±{calibrated['roc_auc']['std']:.4f} | "
            f"{calibrated['pr_auc']['mean']:.4f}±{calibrated['pr_auc']['std']:.4f} | "
            f"{raw['brier_score']['mean']:.4f}→{calibrated['brier_score']['mean']:.4f} | "
            f"{raw['expected_calibration_error']['mean']:.4f}→"
            f"{calibrated['expected_calibration_error']['mean']:.4f} |"
        )
    lines.extend(["", "## Five-fold results by seed", ""])
    for result in comparison["cross_seed_summary"]:
        lines.append(f"### {result['model_mode']} / {result['model_name']}")
        lines.append("")
        lines.append("| Seed | ROC-AUC mean±SD | PR-AUC mean±SD | Brier mean±SD | ECE mean±SD |")
        lines.append("|---:|---:|---:|---:|---:|")
        for seed_result in result["five_fold_by_seed"]:
            metrics = seed_result["metrics"]
            lines.append(
                f"| {seed_result['seed']} | {metrics['roc_auc']['mean']:.4f}±{metrics['roc_auc']['std']:.4f} | "
                f"{metrics['pr_auc']['mean']:.4f}±{metrics['pr_auc']['std']:.4f} | "
                f"{metrics['brier_score']['mean']:.4f}±{metrics['brier_score']['std']:.4f} | "
                f"{metrics['expected_calibration_error']['mean']:.4f}±"
                f"{metrics['expected_calibration_error']['std']:.4f} |"
            )
        lines.append("")
    lines.extend(["## Paired model gains across seeds", ""])
    for model, metrics in comparison["gains"]["update_24h_vs_baseline"].items():
        lines.append(
            f"- update_24h minus baseline / {model}: ROC-AUC "
            f"{metrics['roc_auc']['mean']:+.4f}±{metrics['roc_auc']['std']:.4f}, PR-AUC "
            f"{metrics['pr_auc']['mean']:+.4f}±{metrics['pr_auc']['std']:.4f}, Brier "
            f"{metrics['brier_score']['mean']:+.4f}±{metrics['brier_score']['std']:.4f}."
        )
    for mode, comparisons in comparison["gains"]["ncct_clinical_gain"].items():
        for reference, metrics in comparisons.items():
            lines.append(
                f"- {mode} NCCT+Clinical {reference}: ROC-AUC "
                f"{metrics['roc_auc']['mean']:+.4f}±{metrics['roc_auc']['std']:.4f}, PR-AUC "
                f"{metrics['pr_auc']['mean']:+.4f}±{metrics['pr_auc']['std']:.4f}, Brier "
                f"{metrics['brier_score']['mean']:+.4f}±{metrics['brier_score']['std']:.4f}."
            )
    lines.extend(["", "## CV candidates", ""])
    for mode, candidate in comparison["recommended_cv_candidates"].items():
        metrics = candidate["metrics_mean_std"]
        lines.append(
            f"- {mode}: `{candidate['model_name']}` — mean ROC-AUC "
            f"{metrics['roc_auc']['mean']:.4f}±{metrics['roc_auc']['std']:.4f}; "
            "evaluation candidate only, production_approved=false."
        )
    lines.extend(["", "## Sensitivity analysis", ""])
    if comparison["sensitivity_comparison"]:
        for item in comparison["sensitivity_comparison"]:
            diff = item["metric_difference_sensitivity_minus_main"]
            lines.append(
                f"- {item['model_mode']} / {item['model_name']}: witnessed-only minus main "
                f"ROC-AUC {diff['roc_auc']:+.4f}, PR-AUC {diff['pr_auc']:+.4f}, "
                f"Brier {diff['brier_score']:+.4f}."
            )
    else:
        lines.append("- Not completed yet.")
    lines.extend(["", "## Onset-to-CT permutation reliance", ""])
    for result in comparison["onset_to_ct_permutation_importance"]["summary"]["main"]:
        lines.append(
            f"- {result['model_mode']} / {result['model_name']}: mean ROC-AUC drop "
            f"{result['roc_auc_drop']['mean']:+.4f}±{result['roc_auc_drop']['std']:.4f}; "
            f"mean absolute risk change {result['mean_absolute_probability_change']['mean']:.4f}."
        )
    lines.append("- Permutation importance measures model reliance and is not a causal effect.")
    lines.extend(
        [
            "",
            "## Safety status",
            "",
            "- Real patient data were used for training and evaluation.",
            "- These are cross-validation evaluation weights, not deployment bundles.",
            "- No DAG, frontend, ICV, structured-report, or production inference integration was performed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
