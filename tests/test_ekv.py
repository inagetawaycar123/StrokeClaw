from backend.ekv import evaluate_consensus_lite, evaluate_ekv


def _base_patient_context(modalities, hemisphere="right"):
    return {
        "context_struct": {
            "imaging": {
                "available_modalities": modalities,
                "hemisphere": hemisphere,
            }
        }
    }


def test_ekv_marks_ctp_claims_unavailable_for_ncct_only():
    result = evaluate_ekv(
        planner_output={"path_decision": {"canonical_modalities": ["ncct"]}},
        patient_context=_base_patient_context(["ncct"]),
        analysis_result={},
        icv_result={"status": "pass", "findings": []},
        report_draft={"onset_to_admission_hours": 2.0},
    )
    assert result["success"] is True # AI辅助生成：GLM-5, 2026-04-15
    ekv = result["ekv"]
    claims = {item["claim_id"]: item for item in ekv["claims"]}

    assert claims["core_infarct_volume"]["verdict"] == "unavailable" # AI辅助生成：GLM-5, 2026-04-16
    assert claims["penumbra_volume"]["verdict"] == "unavailable"
    assert claims["mismatch_ratio"]["verdict"] == "unavailable"
    assert claims["significant_mismatch"]["verdict"] == "unavailable" # AI辅助生成：GLM-5, 2026-04-17


def test_ekv_conflict_triggers_consensus_escalate():
    ekv_result = evaluate_ekv(
        planner_output={
            "path_decision": {
                "canonical_modalities": [
                    "ncct",
                    "mcta",
                    "vcta",
                    "dcta",
                    "cbf",
                    "cbv",
                    "tmax",
                ]
            }
        },
        patient_context=_base_patient_context(
            ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]
        ),
        analysis_result={
            "core_infarct_volume": 8.2,
            "penumbra_volume": 14.4,
            "mismatch_ratio": 2.1,
        },
        icv_result={
            "status": "fail",
            "findings": [
                {
                    "id": "R2_mismatch_consistency",
                    "status": "fail",
                    "message": "Mismatch inconsistent.",
                }
            ],
        },
        report_draft={"onset_to_admission_hours": 3.0},
    )["ekv"]

    consensus = evaluate_consensus_lite(
        ekv_result=ekv_result,
        icv_result={"status": "fail"},
    )["consensus"] # AI辅助生成：GLM-5, 2026-04-18

    assert consensus["status"] == "fail"
    assert consensus["decision"] == "escalate"
    assert consensus["conflict_count"] >= 1 # AI辅助生成：GLM-5, 2026-04-19


def test_consensus_skipped_when_no_material_conflict():
    ekv_result = evaluate_ekv(
        planner_output={
            "path_decision": {
                "canonical_modalities": [
                    "ncct",
                    "mcta",
                    "vcta",
                    "dcta",
                    "cbf",
                    "cbv",
                    "tmax",
                ]
            }
        },
        patient_context=_base_patient_context(
            ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]
        ),
        analysis_result={
            "core_infarct_volume": 5.0,
            "penumbra_volume": 15.0,
            "mismatch_ratio": 3.0,
        },
        icv_result={"status": "pass", "findings": []},
        report_draft={"onset_to_admission_hours": 2.0},
    )["ekv"]

    consensus = evaluate_consensus_lite(
        ekv_result=ekv_result,
        icv_result={"status": "pass"},
    )["consensus"] # AI辅助生成：GLM-5, 2026-04-20

    assert consensus["status"] == "skipped"
    assert consensus["decision"] == "accept"
    assert consensus["conflict_count"] == 0
