import csv
import json

import numpy as np

from mrs_prediction.inference import _confidence
from mrs_prediction.mvp_training import aggregate_oof_logits, median_best_epoch


def test_oof_aggregation_uses_one_row_per_patient_before_calibration(tmp_path):
    path = tmp_path / "oof.csv"
    fields = [
        "patient_key",
        "true_label",
        "analysis",
        "model_mode",
        "model_name",
        "fold",
        "seed",
        "raw_logit",
    ]
    rows = []
    logits = {
        "p0": (-2.0, -1.8, -2.2),
        "p1": (-1.0, -0.8, -1.2),
        "p2": (1.0, 0.8, 1.2),
        "p3": (2.0, 1.8, 2.2),
    }
    for patient_index, (patient_key, values) in enumerate(logits.items()):
        for seed, value in zip((10, 11, 12), values, strict=True):
            rows.append(
                {
                    "patient_key": patient_key,
                    "true_label": int(patient_index >= 2),
                    "analysis": "main",
                    "model_mode": "baseline",
                    "model_name": "clinical_only",
                    "fold": patient_index,
                    "seed": seed,
                    "raw_logit": value,
                }
            )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = aggregate_oof_logits(
        path,
        model_mode="baseline",
        model_name="clinical_only",
        expected_patients=4,
    )
    assert result["patient_count"] == 4
    assert len(result["rows"]) == 4
    assert all(row["seed_count"] == 3 for row in result["rows"])
    assert np.allclose([row["mean_raw_logit"] for row in result["rows"]], [-2, -1, 1, 2])
    assert result["temperature_scaling_parameter"] > 0
    assert 0 <= result["decision_threshold"] <= 1


def test_median_best_epoch_reads_exactly_fifteen_existing_cv_runs(tmp_path):
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    root = tmp_path / "baseline" / "clinical_only"
    for index, value in enumerate(values):
        path = root / f"seed_{index // 5}" / f"fold_{index % 5}" / "metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "analysis": "main",
                    "seed": index // 5,
                    "fold": index % 5,
                    "best_epoch": value,
                }
            ),
            encoding="utf-8",
        )
    result = median_best_epoch(
        tmp_path, model_mode="baseline", model_name="clinical_only"
    )
    assert result["median_best_epoch"] == 8
    assert len(result["source_runs"]) == 15


def test_confidence_is_separate_from_risk_probability():
    high = _confidence(
        ensemble_probability_std=0.01,
        threshold_margin=0.3,
        missing_clinical_fields=[],
        image_quality_warnings=[],
    )
    low = _confidence(
        ensemble_probability_std=0.2,
        threshold_margin=0.01,
        missing_clinical_fields=["age"],
        image_quality_warnings=["bad slice"],
    )
    assert high["level"] == "high"
    assert low["level"] == "low"
    assert "risk" not in high

