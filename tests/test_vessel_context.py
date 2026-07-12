from backend.vessel_context import (
    VESSEL_OCCLUSION_UNAVAILABLE_TEXT,
    empty_vessel_occlusion_result,
    normalize_vessel_occlusion_result,
    vessel_result_display_label,
    vessel_result_from_sources,
)


def test_empty_contract_is_truthful_unavailable():
    result = empty_vessel_occlusion_result(
        "unavailable",
        total_slices=1,
        error_code="MODEL_DEPENDENCY_UNAVAILABLE",
        error_message="missing dependency",
    )

    assert result["status"] == "unavailable"
    assert result["vessel_occlusion_class_result"] is None
    assert result["confidence"] is None
    assert result["total_slices"] == 1
    assert vessel_result_display_label(result) == VESSEL_OCCLUSION_UNAVAILABLE_TEXT


def test_completed_contract_preserves_real_prediction():
    result = normalize_vessel_occlusion_result(
        {
            "status": "completed",
            "vessel_occlusion_class_result": "无明显狭窄",
            "predicted_class": "Class_0",
            "confidence": 0.519,
            "class_counts": {"Class_0": 1},
            "total_slices": 1,
            "valid_predictions": 1,
        }
    )

    assert result["status"] == "completed"
    assert result["vessel_occlusion_class_result"] == "无明显狭窄"
    assert result["predicted_class"] == "Class_0"
    assert result["confidence"] == 0.519
    assert result["class_counts"]["Class_0"] == 1


def test_legacy_label_without_model_evidence_is_not_treated_as_lvo_prediction():
    result = normalize_vessel_occlusion_result(
        {"vessel_occlusion_class_result": "大血管闭塞"}
    )

    assert result["status"] == "unavailable"
    assert result["vessel_occlusion_class_result"] is None
    assert vessel_result_display_label(result) == VESSEL_OCCLUSION_UNAVAILABLE_TEXT


def test_corrupt_completed_label_without_success_evidence_is_rejected():
    result = normalize_vessel_occlusion_result(
        {
            "status": "completed",
            "vessel_occlusion_class_result": "大血管闭塞",
            "confidence": 0.99,
            "valid_predictions": 0,
            "class_counts": {
                "Class_0": 0,
                "Class_1_LVO": 0,
                "Class_2_MEVO": 0,
            },
        }
    )

    assert result["status"] == "failed"
    assert result["vessel_occlusion_class_result"] is None
    assert result["predicted_class"] is None
    assert result["confidence"] is None
    assert result["class_counts"] == {
        "Class_0": 0,
        "Class_1_LVO": 0,
        "Class_2_MEVO": 0,
    }
    assert result["error_code"] == "MODEL_RESULT_INVALID"


def test_source_precedence_prefers_nested_result_and_keeps_failure_details():
    result = vessel_result_from_sources(
        {
            "vessel_occlusion_result": {
                "status": "failed",
                "error_code": "ALL_PREDICTIONS_FAILED",
                "error_message": "All 1 predictions failed",
                "failures": [
                    {
                        "slice_file": "slice_000_mcta.png",
                        "error_code": "MODEL_INFERENCE_FAILED",
                        "error_message": "boom",
                    }
                ],
            }
        },
        {
            "vessel_occlusion_status": "completed",
            "vessel_occlusion_class_result": "大血管闭塞",
            "confidence": 0.99,
        },
    )

    assert result["status"] == "failed"
    assert result["vessel_occlusion_class_result"] is None
    assert result["error_code"] == "ALL_PREDICTIONS_FAILED"
    assert result["failures"][0]["slice_file"] == "slice_000_mcta.png"
