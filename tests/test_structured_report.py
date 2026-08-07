from backend.structured_report import build_structured_report_v2
from backend.summary_assembler import build_summary_artifacts


def _example_context(**overrides):
    context = {
        "patient_age": 89,
        "patient_sex": "male",
        "onset_to_admission_hours": 1.02,
        "admission_nihss": 9,
        "three_class_label": "ischemic_stroke",
        "three_class_label_cn": "脑缺血",
        "three_class_confidence": 0.93,
        "core_infarct_volume": 6.14,
        "penumbra_volume": 17.21,
        "mismatch_ratio": 2.80,
        "vessel_occlusion_result": {"status": "unavailable"},
    }
    context.update(overrides)
    return context


def _mrs_result(*, poor=0.316, mode="baseline"):
    predicted_class = int(poor >= 0.55)
    return {
        "status": "completed",
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
            "level": "medium",
            "ensemble_std": 0.03,
            "threshold_margin": abs(poor - 0.55),
            "reasons": [],
        },
        "key_evidence": {"clinical": [], "imaging": []},
        "data_quality": {
            "missing_clinical_fields": [],
            "image_quality_warnings": [],
        },
        "doctor_review_recommendation": {
            "review_level": "routine_review",
            "items": ["请结合临床资料复核。"],
        },
        "model": {
            "model_version": "mrs-v1",
            "external_validation_completed": False,
            "production_approved": False,
        },
    }


def _build(*, context=None, payload=None, icv=None, consensus=None, review=None):
    return build_structured_report_v2(
        run_id="run-example",
        file_id="file-example",
        report_payload=payload or {},
        patient_context=context if context is not None else _example_context(),
        icv=icv,
        consensus=consensus,
        review_state=review,
        legacy_report_text="",
    )


def _by_id(items):
    result = {}
    for item in items:
        item_id = (
            item.get("field_id")
            or item.get("metric_id")
            or item.get("rule_id")
            or item.get("claim_id")
            or item.get("issue_id")
        )
        if item_id:
            result[item_id] = item
    return result


def test_complete_example_preserves_values_and_rule_comparison():
    report = _build()
    fields = _by_id(report["patient_summary"]["fields"])
    metrics = _by_id(report["quantitative_metrics"])
    rules = _by_id(report["rule_evaluations"])

    assert fields["age"]["value"] == 89
    assert fields["sex"]["value"] == "male"
    assert fields["onset_to_admission_hours"]["value"] == 1.02
    assert fields["admission_nihss"]["value"] == 9
    assert metrics["core_infarct_volume"]["value"] == 6.14
    assert metrics["penumbra_volume"]["value"] == 17.21
    assert metrics["mismatch_ratio"]["value"] == 2.80

    mismatch_rule = rules["CTP_MISMATCH_RATIO_1_8_V1"]
    assert mismatch_rule["input_value"] == 2.80
    assert mismatch_rule["operator"] == ">"
    assert mismatch_rule["threshold"] == 1.80
    assert mismatch_rule["result"] == "met"


def test_vessel_missing_is_explicit_and_evt_claim_is_conditional():
    report = _build()
    missing = _by_id(report["missing_information"])
    claims = _by_id(report["clinical_assessment"])
    evt_claim = claims["claim_evt_further_evaluation"]

    assert "missing_vessel_occlusion_class" in missing
    assert "进一步评估机械取栓" in evt_claim["claim"]
    assert evt_claim["support_status"] == "partially_supported"
    assert "血管闭塞分类结果缺失。" in evt_claim["limitations"]
    assert "指南证据未绑定。" in evt_claim["limitations"]
    assert "确定适合取栓" not in evt_claim["claim"]


def test_zero_is_preserved_while_missing_rule_input_is_unknown():
    report = _build(
        context=_example_context(
            core_infarct_volume=0,
            penumbra_volume=None,
            mismatch_ratio=None,
        )
    )
    metrics = _by_id(report["quantitative_metrics"])
    rules = _by_id(report["rule_evaluations"])

    assert metrics["core_infarct_volume"]["value"] == 0
    assert metrics["core_infarct_volume"]["status"] == "present"
    assert metrics["penumbra_volume"]["status"] == "missing"
    assert rules["CTP_MISMATCH_RATIO_1_8_V1"]["result"] == "unknown"


def test_current_report_algorithm_values_override_legacy_patient_fields():
    report = _build(
        context=_example_context(
            core_infarct_volume=99,
            penumbra_volume=1,
            mismatch_ratio=0.1,
        ),
        payload={
            "sections": {
                "ctp": {
                    "core_infarct_volume": 6.14,
                    "penumbra_volume": 17.21,
                    "mismatch_ratio": 2.8,
                }
            }
        },
    )
    metrics = _by_id(report["quantitative_metrics"])

    assert metrics["core_infarct_volume"]["value"] == 6.14
    assert metrics["penumbra_volume"]["value"] == 17.21
    assert metrics["mismatch_ratio"]["value"] == 2.8


def test_available_perfusion_modalities_are_separate_traceable_findings():
    report = _build(
        context=_example_context(available_modalities=["CBF", "CBV", "Tmax"])
    )
    findings = {
        item["finding_id"]: item for item in report["imaging_findings"]
    }

    assert findings["cbf_availability"]["status"] == "completed"
    assert findings["cbv_availability"]["status"] == "completed"
    assert findings["tmax_availability"]["status"] == "completed"
    assert findings["cbf_availability"]["evidence_ids"]


def test_perfusion_finding_uses_quantitative_values_when_modalities_are_uploaded_only():
    report = _build(
        context=_example_context(
            available_modalities=["ncct", "mcta", "vcta", "dcta"]
        )
    )
    findings = {
        item["finding_id"]: item for item in report["imaging_findings"]
    }

    assert findings["perfusion_analysis"]["status"] == "completed"
    assert (
        findings["perfusion_analysis"]["value"]
        == "Core 6.14 mL · Penumbra 17.21 mL · Mismatch 2.80"
    )


def test_hemorrhage_gate_marks_perfusion_skipped_without_false_missing_items():
    gate = {
        "blocked": True,
        "reason_code": "NCCT_SUSPECTED_HEMORRHAGE",
        "reason": "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析",
        "requires_clinician_review": True,
    }
    report = _build(
        context=_example_context(
            three_class_label="hemo",
            three_class_label_cn="脑出血",
            core_infarct_volume=None,
            penumbra_volume=None,
            mismatch_ratio=None,
            vessel_occlusion_result={"status": "unavailable"},
            safety_gate=gate,
        )
    )
    findings = {
        item["finding_id"]: item for item in report["imaging_findings"]
    }
    missing_ids = {item["issue_id"] for item in report["missing_information"]}
    warning_ids = {item["issue_id"] for item in report["warnings"]}

    assert findings["perfusion_analysis"]["status"] == "skipped"
    assert "安全门控" in findings["perfusion_analysis"]["value"]
    assert "missing_core_infarct_volume" not in missing_ids
    assert "missing_penumbra_volume" not in missing_ids
    assert "missing_mismatch_ratio" not in missing_ids
    assert "missing_vessel_occlusion_class" not in missing_ids
    assert "ncct_safety_gate_blocked" in warning_ids
    assert report["report_meta"]["risk_level"] == "high"
    assert report["report_meta"]["urgency"] == "urgent"


def test_low_confidence_and_module_conflict_are_independent_warnings():
    report = _build(
        context=_example_context(three_class_confidence=0.41),
        consensus={
            "conflicts": [
                {
                    "claim_id": "significant_mismatch",
                    "message": "模型与规则结果不一致。",
                }
            ]
        },
    )
    statuses = {item["status"] for item in report["warnings"]}
    assert "low_confidence" in statuses
    assert "conflict" in statuses


def test_guideline_stub_is_unbound_and_does_not_raise_coverage():
    payload = {
        "evidence_items": [
            {
                "evidence_id": "legacy-random-id",
                "claim_id": "significant_mismatch",
                "source_type": "guideline_stub",
                "source_ref": "internal_guideline:placeholder",
                "doc_name": "占位指南",
            }
        ]
    }
    with_stub = _build(payload=payload)
    without_stub = _build()
    guideline = next(
        item
        for item in with_stub["evidence_catalog"]
        if item["evidence_type"] == "guideline"
    )

    assert guideline["binding_status"] == "unbound"
    assert "legacy-random-id" in guideline["legacy_aliases"]
    assert (
        with_stub["report_meta"]["evidence_coverage"]
        == without_stub["report_meta"]["evidence_coverage"]
    )
    assert any(
        item["issue_id"] == "unbound_guideline_evidence"
        for item in with_stub["uncertainties"]
    )


def test_evidence_ids_are_stable_across_generation_times():
    first = _build()
    second = _build()
    first_ids = [item["evidence_id"] for item in first["evidence_catalog"]]
    second_ids = [item["evidence_id"] for item in second["evidence_catalog"]]
    assert first_ids == second_ids


def test_review_sections_map_to_fields_and_claims():
    review = {
        "all_confirmed": False,
        "sections": [
            {"section_id": "patient_context", "review_status": "confirmed"},
            {"section_id": "ctp_quant", "review_status": "needs_edit"},
            {"section_id": "question_answer", "review_status": "confirmed"},
        ],
    }
    report = _build(review=review)
    fields = _by_id(report["patient_summary"]["fields"])
    metrics = _by_id(report["quantitative_metrics"])
    claims = _by_id(report["clinical_assessment"])

    assert fields["age"]["clinician_confirmed"] is True
    assert metrics["mismatch_ratio"]["review_status"] == "needs_edit"
    assert claims["claim_significant_mismatch"]["clinician_confirmed"] is True


def test_pure_legacy_text_is_marked_without_reverse_extraction():
    report = build_structured_report_v2(
        run_id="",
        file_id="legacy-file",
        report_payload={},
        patient_context={},
        legacy_report_text="患者核心梗死体积 6.14 mL。",
    )
    metrics = _by_id(report["quantitative_metrics"])

    assert report["report_meta"]["legacy_mode"] is True
    assert metrics["core_infarct_volume"]["value"] is None
    assert report["narrative_summary"]["legacy_text"].startswith("患者核心")


def test_ncct_algorithm_output_does_not_require_an_ekv_claim():
    result = build_summary_artifacts(
        run_id="run-ncct",
        file_id="file-ncct",
        report_payload={},
        icv=None,
        ekv={"claims": []},
        consensus=None,
        goal_question="",
        patient_context=_example_context(),
    )
    uncertainty_text = " ".join(
        str(item.get("message") or item)
        for item in result["structured_report_v2"]["uncertainties"]
    )
    assert "NCCT 三分类结果: 外部知识验证未生成该结论" not in uncertainty_text


def test_mrs_prognosis_is_optional_independent_assessment_with_evidence():
    report = _build(payload={"mrs_prognosis_result": _mrs_result()})
    prognosis = report["prognosis_assessment"]

    assert prognosis["status"] == "completed"
    assert prognosis["prediction"]["good_prognosis_probability"] == 0.684
    assert prognosis["prediction"]["predicted_class"] == 0
    assert prognosis["requires_clinician_review"] is True
    assert prognosis["evidence_ids"]
    evidence = {
        item["evidence_id"]: item for item in report["evidence_catalog"]
    }
    assert evidence[prognosis["evidence_ids"][0]]["source_module"] == "MRSPrognosisAgent"


def test_mrs_result_does_not_change_acute_risk_urgency_or_rules():
    without_mrs = _build()
    with_mrs = _build(payload={"mrs_prognosis_result": _mrs_result(poor=0.9)})

    assert with_mrs["report_meta"]["risk_level"] == without_mrs["report_meta"]["risk_level"]
    assert with_mrs["report_meta"]["urgency"] == without_mrs["report_meta"]["urgency"]
    assert with_mrs["rule_evaluations"] == without_mrs["rule_evaluations"]
    assert with_mrs["recommendations"] == without_mrs["recommendations"]


def test_missing_mrs_is_nonblocking_and_not_fabricated():
    report = _build(payload={"mrs_prognosis_result": {"status": "failed"}})
    prognosis = report["prognosis_assessment"]

    assert prognosis["status"] == "unavailable"
    assert prognosis["prediction"] is None
    assert prognosis["requires_clinician_review"] is False
    assert prognosis["review_status"] == "not_applicable"


def test_mrs_review_section_status_is_applied_when_result_exists():
    review = {
        "all_confirmed": False,
        "sections": [
            {
                "section_id": "prognosis_assessment",
                "review_status": "confirmed",
            }
        ],
    }
    report = _build(
        payload={"mrs_prognosis_result": _mrs_result(mode="update_24h")},
        review=review,
    )

    assert report["prognosis_assessment"]["display_mode"] == "24小时更新评估"
    assert report["prognosis_assessment"]["review_status"] == "confirmed"
    assert report["prognosis_assessment"]["clinician_confirmed"] is True
