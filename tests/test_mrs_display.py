from __future__ import annotations

import copy

import pytest

from backend.mrs_display import (
    mrs_prompt_context,
    normalize_mrs_prognosis_result,
)


def completed_mrs(*, poor=0.316, mode="baseline", confidence="medium"):
    predicted_class = int(poor >= 0.55)
    return {
        "status": "completed",
        "patient_id": 934,
        "file_id": "private-case-file",
        "run_id": "private-run",
        "result_mode": mode,
        "display_mode": "24小时更新评估" if mode == "update_24h" else "首诊初步评估",
        "prediction": {
            "good_prognosis_probability": 1 - poor,
            "poor_prognosis_risk": poor,
            "predicted_class": predicted_class,
            "class_name": "mRS 3-6 / 不良预后" if predicted_class else "mRS 0-2 / 良好预后",
            "decision_threshold": 0.55,
            "probability_calibrated": True,
        },
        "confidence": {
            "level": confidence,
            "ensemble_std": 0.03,
            "threshold_margin": abs(poor - 0.55),
            "reasons": ["接近阈值"],
        },
        "key_evidence": {
            "clinical": [
                {
                    "feature": "NIHSS Baseline",
                    "display_name": "入院 NIHSS",
                    "value": 9,
                    "contribution": 0.12,
                    "direction": "increase_poor_prognosis_risk",
                }
            ],
            "imaging": [
                {
                    "source_file": "E:/patients/private-case-file/ncct.nii",
                    "attention_score": 0.72,
                    "interpretation": "模型关注区域，不代表确定病灶。",
                }
            ],
            "attribution_notice": "模型归因不代表因果关系。",
        },
        "data_quality": {
            "missing_clinical_fields": ["glucose"],
            "image_quality_warnings": ["single slice"],
        },
        "doctor_review_recommendation": {
            "review_level": "focused_review",
            "items": ["请结合完整临床资料复核。"],
        },
        "model": {
            "model_version": "mrs-v1",
            "bundle_version": "bundle-v1",
            "release_status": "MVP_RESEARCH",
            "external_validation_completed": False,
            "production_approved": False,
        },
        "fallback_used": False,
    }


@pytest.mark.parametrize(
    ("poor", "expected_class", "expected_text"),
    [(0.316, 0, "良好预后"), (0.684, 1, "不良预后")],
)
def test_normalizer_preserves_only_two_group_prediction(poor, expected_class, expected_text):
    normalized = normalize_mrs_prognosis_result(completed_mrs(poor=poor))

    assert normalized["status"] == "completed"
    assert normalized["prediction"]["predicted_class"] == expected_class
    assert expected_text in normalized["prediction"]["class_name"]
    assert normalized["prediction"]["good_prognosis_probability"] == pytest.approx(1 - poor)
    assert normalized["prediction"]["poor_prognosis_risk"] == pytest.approx(poor)
    assert "具体 mRS 分数" in " ".join(normalized["limitations"])


def test_update_mode_fallback_and_reliability_fields_are_preserved():
    raw = completed_mrs(mode="update_24h", confidence="low")
    raw["fallback_used"] = True
    raw["fallback_reason"] = "update bundle unavailable"

    normalized = normalize_mrs_prognosis_result(raw)

    assert normalized["display_mode"] == "24小时更新评估"
    assert normalized["confidence"]["level"] == "low"
    assert normalized["confidence"]["ensemble_std"] == pytest.approx(0.03)
    assert normalized["fallback_used"] is True


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["prediction"].update(good_prognosis_probability=1.2),
        lambda value: value["prediction"].update(good_prognosis_probability=0.4),
        lambda value: value["prediction"].update(predicted_class=1),
        lambda value: value["prediction"].update(class_name="mRS 3-6 / 不良预后"),
    ],
)
def test_invalid_probability_or_class_never_becomes_zero_probability(mutator):
    raw = completed_mrs()
    mutator(raw)

    normalized = normalize_mrs_prognosis_result(raw)

    assert normalized["status"] == "unavailable"
    assert normalized["prediction"] is None
    assert "0.0%" not in normalized["deterministic_summary"]


def test_prompt_context_removes_case_identifiers_paths_and_source_filenames():
    raw = completed_mrs()
    prompt = mrs_prompt_context(copy.deepcopy(raw))
    serialized = repr(prompt)

    assert prompt["status"] == "completed"
    assert "patient_id" not in prompt
    assert "file_id" not in prompt
    assert "run_id" not in prompt
    assert "private-case-file" not in serialized
    assert "E:/patients" not in serialized
    assert prompt["key_evidence"]["imaging"][0]["region_label"] == "NCCT 关注区域 1"


def test_missing_result_is_explicitly_unavailable():
    normalized = normalize_mrs_prognosis_result({"status": "failed", "message": "bundle missing"})

    assert normalized["status"] == "unavailable"
    assert normalized["prediction"] is None
    assert "bundle missing" in normalized["deterministic_summary"]
