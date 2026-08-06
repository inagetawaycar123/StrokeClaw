import json
from pathlib import Path

import numpy as np
import torch

from mrs_prediction.calibration import (
    binary_log_loss_from_logits,
    calibrated_probability,
    fit_temperature,
)
from mrs_prediction.cv_training import run_fold, stratified_inner_split
from mrs_prediction.metrics import binary_metrics, select_youden_threshold


def _records(count_per_class=10):
    rows = []
    for label in (0, 1):
        for index in range(count_per_class):
            rows.append(
                {
                    "patient_key": f"p-{label}-{index:02d}",
                    "clinical_patient_id": f"ProVe-IT-{label:02d}-{index:03d}",
                    "binary_label": str(label),
                    "Gender": "M" if index % 2 else "F",
                    "Age": str(50 + label * 15 + index),
                    "onset_to_ct_hours": str(1 + index / 10),
                    "Onset to CT time": "0.1",
                    "NIHSS Baseline": str(3 + label * 8 + index % 3),
                    "NIHSS 24 HOURS": str(2 + label * 7 + index % 3),
                    "onset_to_ct_witness_status": "witnessed",
                    "v0_clinical_data_warnings": "[]",
                    "is_v0_eligible": "True",
                }
            )
    return rows


def _config():
    return {
        "cross_validation": {"inner_validation_fraction": 0.25},
        "image": {"image_size": [16, 16], "max_ncct_files": None},
        "model": {
            "embedding_dim": 8,
            "attention_dim": 4,
            "base_channels": 2,
            "fusion_dim": 8,
            "dropout": 0.1,
        },
        "training": {
            "device": "cpu",
            "mixed_precision": False,
            "num_workers": 0,
            "clinical_batch_size": 8,
            "image_batch_size": 2,
            "learning_rate": {
                "clinical_only": 0.01,
                "ncct_only": 0.001,
                "ncct_clinical": 0.001,
            },
            "weight_decay": 0.0,
            "scheduler_factor": 0.5,
            "scheduler_patience": 1,
            "minimum_learning_rate": 1e-6,
            "gradient_clip_norm": 1.0,
            "max_epochs": 2,
            "early_stopping_patience": 2,
            "auc_min_delta": 1e-6,
        },
        "evaluation": {"ece_bins": 5},
        "data": {"image_root": "unused"},
    }


def test_metrics_and_temperature_scaling_are_finite_and_validation_only():
    labels = np.asarray([0, 0, 0, 1, 1, 1])
    logits = np.asarray([-8.0, -4.0, -2.0, 2.0, 4.0, 8.0]) * 2.5
    temperature = fit_temperature(logits, labels)
    calibrated = calibrated_probability(logits, temperature)
    assert temperature > 0
    assert binary_log_loss_from_logits(logits / temperature, labels) <= binary_log_loss_from_logits(logits, labels)
    threshold = select_youden_threshold(labels, calibrated)
    metrics = binary_metrics(labels, calibrated, threshold=threshold, ece_bins=5)
    assert metrics["roc_auc"] == 1.0
    assert metrics["pr_auc"] == 1.0
    assert metrics["confusion_matrix"] == [[3, 0], [0, 3]]


def test_inner_split_is_patient_disjoint_and_stratified():
    train, validation = stratified_inner_split(_records(), 0.2, seed=42)
    assert {row["patient_key"] for row in train}.isdisjoint(
        {row["patient_key"] for row in validation}
    )
    assert {int(row["binary_label"]) for row in train} == {0, 1}
    assert {int(row["binary_label"]) for row in validation} == {0, 1}


def test_clinical_fold_bundle_is_reloadable_and_never_production(tmp_path):
    records = _records()
    assignment = {
        record["patient_key"]: index % 5 for index, record in enumerate(records)
    }
    context = {
        "project_root": tmp_path,
        "output_root": tmp_path / "outputs" / "mrs_training",
        "records": records,
        "record_by_key": {record["patient_key"]: record for record in records},
        "assignment_by_key": assignment,
    }
    result = run_fold(
        context,
        _config(),
        model_mode="baseline",
        model_name="clinical_only",
        fold=0,
        seed=7,
    )
    assert result["status"] == "completed"
    assert result["checkpoint_reload_max_abs_logit_difference"] <= 1e-5
    bundle = torch.load(result["bundle"], map_location="cpu", weights_only=False)
    assert bundle["artifact_role"] == "CV_EVAL_ONLY"
    assert bundle["production_approved"] is False
    assert bundle["is_real_inference"] is False
    assert bundle["model_mode"] == "baseline"
    metrics = json.loads(
        (Path(result["bundle"]).parent / "metrics.json").read_text(encoding="utf-8")
    )
    assert set(metrics["outer_test_metrics"]) == {
        "raw_threshold_0_5",
        "raw_validation_youden",
        "calibrated_threshold_0_5",
        "calibrated_validation_youden",
    }
