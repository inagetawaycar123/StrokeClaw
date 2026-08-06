"""Build full-cohort MVP ensembles from fixed cross-validation evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from .calibration import calibrated_probability, fit_temperature, sigmoid
from .cv_training import (
    COHORT_SCHEMA_VERSION,
    ONSET_SCHEMA_VERSION,
    _make_loader,
    _make_model,
    _model_arguments,
    _scope_hash,
    _sha256,
    _write_csv,
    load_training_config,
    set_deterministic_seed,
)
from .dataset import read_manifest_rows
from .image_preprocessing import ImagePreprocessor, NCCTResizeCache
from .metrics import binary_metrics, select_youden_threshold
from .preprocessing import ClinicalPreprocessor
from .schema import FEATURE_SCHEMA_VERSION


MVP_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("baseline", "clinical_only", "mrs_baseline_mvp.pt"),
    ("update_24h", "ncct_clinical", "mrs_update24h_mvp.pt"),
)
MVP_ENSEMBLE_SEEDS = (42, 43, 44)
MVP_MODEL_VERSION = "mrs-mvp-0.1.0"
MVP_BUNDLE_VERSION = "mrs-mvp-bundle-1.0"


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load_frozen_records(project_root: Path, config: Mapping[str, Any]) -> list[dict[str, str]]:
    manifest = project_root / str(config["data"]["manifest"])
    cohort_summary_path = project_root / str(config["data"]["cohort_summary"])
    records = read_manifest_rows(manifest, eligible_only=True)
    expected_count = int(config["data"]["expected_patients"])
    labels = Counter(int(float(record["binary_label"])) for record in records)
    expected_labels = {int(key): int(value) for key, value in config["data"]["expected_labels"].items()}
    if len(records) != expected_count or dict(labels) != expected_labels:
        raise RuntimeError(
            f"Frozen cohort mismatch: patients={len(records)}, labels={dict(labels)}, "
            f"expected={expected_count}/{expected_labels}"
        )
    patient_keys = [str(record["patient_key"]) for record in records]
    if len(patient_keys) != len(set(patient_keys)):
        raise RuntimeError("Frozen MVP cohort contains duplicate patient keys")
    if any(str(record.get("mapping_status", "")).lower() != "unique" for record in records):
        raise RuntimeError("Frozen MVP cohort contains a non-unique clinical-image mapping")
    summary = json.loads(cohort_summary_path.read_text(encoding="utf-8"))
    if int(summary.get("v0_eligible_patients", -1)) != expected_count:
        raise RuntimeError("V0 cohort summary does not match the frozen manifest")
    return sorted(records, key=lambda record: str(record["patient_key"]))


def aggregate_oof_logits(
    oof_path: str | Path,
    *,
    model_mode: str,
    model_name: str,
    expected_patients: int = 315,
    expected_seed_count: int = 3,
    ece_bins: int = 10,
) -> dict[str, Any]:
    """Average each patient's three seed logits, then fit one global calibration."""

    with Path(oof_path).open("r", encoding="utf-8-sig", newline="") as handle:
        selected = [
            row
            for row in csv.DictReader(handle)
            if row.get("analysis") == "main"
            and row.get("model_mode") == model_mode
            and row.get("model_name") == model_name
        ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[str(row["patient_key"])].append(row)
    if len(grouped) != expected_patients:
        raise RuntimeError(
            f"OOF aggregation for {model_mode}/{model_name} found {len(grouped)} patients; "
            f"expected {expected_patients}"
        )

    aggregated_rows: list[dict[str, Any]] = []
    for patient_key, rows in sorted(grouped.items()):
        seeds = sorted(int(row["seed"]) for row in rows)
        labels = {int(row["true_label"]) for row in rows}
        folds = {int(row["fold"]) for row in rows}
        logits = [float(row["raw_logit"]) for row in rows]
        if len(rows) != expected_seed_count or len(set(seeds)) != expected_seed_count:
            raise RuntimeError(
                f"Patient {patient_key} has {len(rows)} OOF rows/{len(set(seeds))} seeds"
            )
        if len(labels) != 1 or len(folds) != 1 or not np.isfinite(logits).all():
            raise RuntimeError(f"Patient {patient_key} has inconsistent OOF labels, folds, or logits")
        aggregated_rows.append(
            {
                "patient_key": patient_key,
                "true_label": labels.pop(),
                "fold": folds.pop(),
                "seed_count": len(seeds),
                "seeds": json.dumps(seeds),
                "raw_logits": json.dumps(logits),
                "mean_raw_logit": float(np.mean(logits)),
                "seed_logit_std": float(np.std(logits, ddof=0)),
            }
        )

    labels = np.asarray([row["true_label"] for row in aggregated_rows], dtype=np.int64)
    logits = np.asarray([row["mean_raw_logit"] for row in aggregated_rows], dtype=np.float64)
    temperature = fit_temperature(logits, labels)
    raw_probability = sigmoid(logits)
    calibrated = calibrated_probability(logits, temperature)
    threshold = select_youden_threshold(labels, calibrated)
    for index, row in enumerate(aggregated_rows):
        row["raw_probability"] = float(raw_probability[index])
        row["calibrated_poor_risk"] = float(calibrated[index])
        row["calibrated_good_probability"] = float(1.0 - calibrated[index])
        row["decision_threshold"] = float(threshold)
        row["predicted_class"] = int(calibrated[index] >= threshold)

    raw_metrics = binary_metrics(labels, raw_probability, threshold=0.5, ece_bins=ece_bins)
    calibrated_fixed = binary_metrics(labels, calibrated, threshold=0.5, ece_bins=ece_bins)
    calibrated_youden = binary_metrics(labels, calibrated, threshold=threshold, ece_bins=ece_bins)
    return {
        "aggregation_method": "patient_key_group_then_arithmetic_mean_of_three_seed_raw_logits",
        "calibration_method": "global_temperature_scaling_on_patient_aggregated_oof_logits",
        "threshold_method": "global_youden_on_calibrated_patient_aggregated_oof_probability",
        "model_mode": model_mode,
        "model_name": model_name,
        "patient_count": len(aggregated_rows),
        "seed_count_per_patient": expected_seed_count,
        "temperature_scaling_parameter": float(temperature),
        "decision_threshold": float(threshold),
        "raw_threshold_0_5": raw_metrics,
        "calibrated_threshold_0_5": calibrated_fixed,
        "calibrated_global_youden": calibrated_youden,
        "rows": aggregated_rows,
    }


def median_best_epoch(
    training_root: str | Path, *, model_mode: str, model_name: str, expected_runs: int = 15
) -> dict[str, Any]:
    root = Path(training_root) / model_mode / model_name
    rows: list[dict[str, int]] = []
    for path in sorted(root.glob("seed_*/fold_*/metrics.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "completed" or payload.get("analysis") != "main":
            continue
        rows.append(
            {
                "seed": int(payload["seed"]),
                "fold": int(payload["fold"]),
                "best_epoch": int(payload["best_epoch"]),
            }
        )
    if len(rows) != expected_runs:
        raise RuntimeError(
            f"Expected {expected_runs} completed CV epochs for {model_mode}/{model_name}; got {len(rows)}"
        )
    identities = {(row["seed"], row["fold"]) for row in rows}
    if len(identities) != expected_runs:
        raise RuntimeError(f"Duplicate CV seed/fold epoch evidence for {model_mode}/{model_name}")
    value = statistics.median(row["best_epoch"] for row in rows)
    if not float(value).is_integer() or value < 1:
        raise RuntimeError(f"Invalid median best epoch {value}")
    return {"median_best_epoch": int(value), "source_runs": rows}


def _train_one_seed(
    *,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    model_mode: str,
    model_name: str,
    seed: int,
    epochs: int,
    clinical_preprocessor: ClinicalPreprocessor,
    image_cache: NCCTResizeCache | None,
    image_preprocessor: ImagePreprocessor | None,
    image_root: Path,
    history_path: Path,
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]], dict[str, Any]]:
    set_deterministic_seed(seed)
    requested = str(config["training"]["device"])
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device(
        "cuda" if requested == "cuda" or (requested == "auto" and torch.cuda.is_available()) else "cpu"
    )
    mixed_precision = bool(config["training"]["mixed_precision"] and device.type == "cuda")
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    loader = _make_loader(
        records,
        model_name=model_name,
        clinical_preprocessor=clinical_preprocessor,
        image_root=image_root,
        image_cache=image_cache,
        image_preprocessor=image_preprocessor,
        config=config,
        shuffle=True,
        seed=seed,
    )
    model = _make_model(model_name, clinical_preprocessor.output_dim, config).to(device)
    positives = sum(int(float(record["binary_label"])) == 1 for record in records)
    negatives = len(records) - positives
    if positives == 0 or negatives == 0:
        raise RuntimeError("Full MVP cohort lacks one binary class")
    pos_weight = negatives / positives
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["training"]["learning_rate"][model_name]),
        weight_decay=float(config["training"]["weight_decay"]),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=mixed_precision)
    history: list[dict[str, Any]] = []
    run_started = time.time()
    for epoch in range(1, epochs + 1):
        epoch_started = time.time()
        model.train()
        total_loss = 0.0
        patient_count = 0
        gradient_overflow_batches = 0
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            arguments = _model_arguments(model_name, batch, device)
            labels = batch["label"].to(device, non_blocking=True)
            context = (
                torch.amp.autocast("cuda", enabled=True) if mixed_precision else nullcontext()
            )
            with context:
                logits = model(**arguments)["logit"]
                loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite full-data loss for seed={seed}, epoch={epoch}")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["training"]["gradient_clip_norm"])
            )
            gradient_is_finite = bool(torch.isfinite(gradient_norm).detach().cpu())
            if not gradient_is_finite and not mixed_precision:
                raise RuntimeError(f"Non-finite gradient norm for seed={seed}, epoch={epoch}")
            if not gradient_is_finite:
                # GradScaler recorded the overflow during unscale_ and will skip
                # this optimizer step while reducing its scale. This is normal
                # dynamic-loss-scaling behavior and must not be treated as a
                # completed parameter update.
                gradient_overflow_batches += 1
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.detach().cpu()) * len(labels)
            patient_count += len(labels)
        row = {
            "epoch": epoch,
            "train_loss": total_loss / max(patient_count, 1),
            "learning_rate": optimizer.param_groups[0]["lr"],
            "patient_count": patient_count,
            "gradient_overflow_batches": gradient_overflow_batches,
            "epoch_seconds": time.time() - epoch_started,
        }
        history.append(row)
        _write_csv(history_path, history)
    cpu_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    runtime = {
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
        "mixed_precision": mixed_precision,
        "elapsed_seconds": time.time() - run_started,
        "gpu_peak_memory_mb": (
            float(torch.cuda.max_memory_allocated(device) / 1024**2) if device.type == "cuda" else 0.0
        ),
        "pos_weight_full_cohort": float(pos_weight),
    }
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return cpu_state, history, runtime


def _state_digest(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(state.items()):
        digest.update(key.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def build_mvp_bundles(
    project_root: str | Path,
    *,
    config_path: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config_file = Path(config_path).resolve() if config_path else root / "configs" / "mrs_cv_train.yaml"
    config = load_training_config(config_file)
    records = _load_frozen_records(root, config)
    training_root = root / str(config["output_dir"])
    output_root = root / "outputs" / "mrs_model"
    output_root.mkdir(parents=True, exist_ok=True)
    oof_path = training_root / "oof_predictions.csv"
    image_root = root / str(config["data"]["image_root"])
    image_cache: NCCTResizeCache | None = None
    results: dict[str, Any] = {}

    for model_mode, model_name, filename in MVP_CANDIDATES:
        bundle_path = output_root / filename
        if bundle_path.exists() and not force:
            raise FileExistsError(f"MVP bundle already exists; pass force to rebuild: {bundle_path}")
        evidence = aggregate_oof_logits(
            oof_path,
            model_mode=model_mode,
            model_name=model_name,
            expected_patients=len(records),
            ece_bins=int(config["evaluation"]["ece_bins"]),
        )
        evidence_rows = evidence.pop("rows")
        evidence_csv = output_root / f"{model_mode}_{model_name}_aggregated_oof.csv"
        _write_csv(evidence_csv, evidence_rows)
        epoch_evidence = median_best_epoch(
            training_root, model_mode=model_mode, model_name=model_name
        )
        epochs = int(epoch_evidence["median_best_epoch"])
        clinical_preprocessor = ClinicalPreprocessor(model_mode).fit(records)
        image_preprocessor: ImagePreprocessor | None = None
        if model_name != "clinical_only":
            if image_cache is None:
                image_cache = NCCTResizeCache.build_or_load(
                    records,
                    image_root,
                    training_root / "cache",
                    tuple(int(value) for value in config["image"]["image_size"]),
                )
            image_preprocessor = ImagePreprocessor.fit(
                records,
                image_cache,
                max_ncct_files=config["image"].get("max_ncct_files"),
            )

        states: list[dict[str, torch.Tensor]] = []
        histories: dict[str, list[dict[str, Any]]] = {}
        runtimes: dict[str, dict[str, Any]] = {}
        for seed in MVP_ENSEMBLE_SEEDS:
            run_dir = output_root / "training" / model_mode / model_name / f"seed_{seed}"
            state, history, runtime = _train_one_seed(
                records=records,
                config=config,
                model_mode=model_mode,
                model_name=model_name,
                seed=seed,
                epochs=epochs,
                clinical_preprocessor=clinical_preprocessor,
                image_cache=image_cache,
                image_preprocessor=image_preprocessor,
                image_root=image_root,
                history_path=run_dir / "training_history.csv",
            )
            states.append(state)
            histories[str(seed)] = history
            runtimes[str(seed)] = runtime

        model_config = {
            "model_name": model_name,
            "class_name": (
                "ClinicalOnlyMRSModel" if model_name == "clinical_only" else "NCCTClinicalMRSModel"
            ),
            "clinical_input_dim": clinical_preprocessor.output_dim,
            "image_size": list(config["image"]["image_size"]),
            "max_ncct_files": config["image"].get("max_ncct_files"),
            "internal_channel_index": int(config["image"]["internal_channel_index"]),
            **{key: value for key, value in dict(config["model"]).items()},
        }
        clinical_preprocessing_config = clinical_preprocessor.to_dict()
        clinical_preprocessing_config["missing_strategy"] = (
            "full_frozen_cohort_median_plus_missing_indicator"
        )
        clinical_preprocessing_config["fit_scope"] = "all_315_frozen_v0_patients"
        if image_preprocessor is not None:
            image_preprocessing_config = image_preprocessor.to_dict()
            image_preprocessing_config["normalization"] = (
                "full_frozen_cohort_global_mean_std"
            )
            image_preprocessing_config["fit_scope"] = "all_315_frozen_v0_patients"
        else:
            image_preprocessing_config = {"status": "not_applicable_clinical_only"}
        manifest_path = root / str(config["data"]["manifest"])
        cohort_summary_path = root / str(config["data"]["cohort_summary"])
        bundle = {
            "artifact_role": "MVP_RESEARCH_ONLINE_BUNDLE",
            "ensemble_state_dicts": states,
            "ensemble_state_sha256": [_state_digest(state) for state in states],
            "ensemble_seeds": list(MVP_ENSEMBLE_SEEDS),
            "model_config": model_config,
            "model_mode": model_mode,
            "clinical_feature_names": list(clinical_preprocessor.feature_names),
            "clinical_preprocessor": clinical_preprocessing_config,
            "image_preprocessing_config": image_preprocessing_config,
            "class_mapping": {
                "0": "mRS 0-2 / good prognosis",
                "1": "mRS 3-6 / poor prognosis",
            },
            "temperature_scaling_parameter": evidence["temperature_scaling_parameter"],
            "decision_threshold": evidence["decision_threshold"],
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "onset_to_ct_schema_version": ONSET_SCHEMA_VERSION,
            "cohort_schema_version": COHORT_SCHEMA_VERSION,
            "model_version": MVP_MODEL_VERSION,
            "bundle_version": MVP_BUNDLE_VERSION,
            "oof_metrics": evidence,
            "external_validation_completed": False,
            "release_status": "MVP_RESEARCH",
            "online_loading_permitted": True,
            "is_real_inference": True,
            "production_approved": False,
            "weights_source": "real_full_cohort_training_315_patients",
            "training_epoch_selection": {
                "method": "median_best_epoch_from_existing_3_seed_5_fold_cv",
                **epoch_evidence,
            },
            "training_data_summary": {
                "patient_count": len(records),
                "label_distribution": {"0": 201, "1": 114},
                "patient_key_hash": _scope_hash(records),
                "ensemble_seeds": list(MVP_ENSEMBLE_SEEDS),
                "fixed_training_epochs": epochs,
                "full_cohort_pos_weight": 201 / 114,
                "clinical_preprocessor_fit_scope": "all_315_frozen_v0_patients",
                "image_preprocessor_fit_scope": (
                    "all_315_frozen_v0_patients" if image_preprocessor is not None else "not_applicable"
                ),
                "source_manifest_sha256": _sha256(manifest_path),
                "source_cohort_summary_sha256": _sha256(cohort_summary_path),
                "source_oof_predictions_sha256": _sha256(oof_path),
            },
            "training_runtime": runtimes,
            "minimum_input_requirements": {
                "requires_ncct": model_name != "clinical_only",
                "requires_nihss_24h_observed": model_mode == "update_24h",
                "forbidden_inputs": ["02", "03", "04", "ctp_core_volume", "mCTA", "mCTP"],
            },
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        temporary = bundle_path.with_suffix(bundle_path.suffix + ".tmp")
        torch.save(bundle, temporary)
        temporary.replace(bundle_path)
        reloaded = torch.load(bundle_path, map_location="cpu", weights_only=False)
        if reloaded["ensemble_state_sha256"] != bundle["ensemble_state_sha256"]:
            raise RuntimeError(f"Bundle state digest changed after reload: {bundle_path}")
        if not (
            reloaded["online_loading_permitted"] is True
            and reloaded["is_real_inference"] is True
            and reloaded["production_approved"] is False
            and reloaded["external_validation_completed"] is False
        ):
            raise RuntimeError(f"MVP release flags are invalid: {bundle_path}")
        results[model_mode] = {
            "bundle_path": str(bundle_path),
            "bundle_sha256": _sha256(bundle_path),
            "aggregated_oof_path": str(evidence_csv),
            "median_best_epoch": epochs,
            "temperature_scaling_parameter": evidence["temperature_scaling_parameter"],
            "decision_threshold": evidence["decision_threshold"],
            "oof_metrics": evidence,
            "state_digests": bundle["ensemble_state_sha256"],
            "training_runtime": runtimes,
        }

    summary = {
        "status": "completed",
        "artifact_role": "MVP_RESEARCH_BUILD_SUMMARY",
        "patient_count": len(records),
        "ensemble_seeds": list(MVP_ENSEMBLE_SEEDS),
        "external_validation_completed": False,
        "release_status": "MVP_RESEARCH",
        "online_loading_permitted": True,
        "is_real_inference": True,
        "production_approved": False,
        "models": results,
    }
    _json_dump(output_root / "mvp_build_summary.json", summary)
    return summary
