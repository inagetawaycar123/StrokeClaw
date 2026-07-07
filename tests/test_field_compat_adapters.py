from backend.compat.adapters import build_clinical_decision_bundle, build_skill_invocations
from backend.compat.skill_registry import get_skill_registry, skill_id_for_tool


def test_skill_registry_contains_p0_skills():
    registry = get_skill_registry()
    skill_ids = {item["skill_id"] for item in registry}

    assert "SKILL_IMG_QC" in skill_ids
    assert "SKILL_NCCT_TRIAGE" in skill_ids
    assert "SKILL_REPORT_GEN" in skill_ids
    assert skill_id_for_tool("generate_ctp_maps") == "SKILL_PSEUDO_CTP"
    assert skill_id_for_tool("generate_medgemma_report") == "SKILL_REPORT_GEN"


def test_skill_invocations_are_derived_from_legacy_events_and_tool_results():
    run = {
        "run_id": "run-1",
        "file_id": "case-1",
        "tool_results": [
            {
                "tool_name": "run_stroke_analysis",
                "status": "completed",
                "latency_ms": 12,
                "confidence_score": 0.91,
            }
        ],
    }
    events = [
        {
            "event_id": "evt-1",
            "event_seq": 1,
            "timestamp": "2026-07-07T10:00:00",
            "tool_name": "generate_ctp_maps",
            "status": "completed",
            "latency_ms": 33,
            "input_ref": {"case_id": "case-1"},
            "output_ref": {"confidence_score": 0.8, "evidence_refs": ["img-1"]},
        }
    ]

    invocations = build_skill_invocations(run=run, events=events)

    assert len(invocations) == 2
    assert invocations[0]["skill_id"] == "SKILL_PSEUDO_CTP"
    assert invocations[0]["evidence_used"] == ["img-1"]
    assert invocations[1]["skill_id"] == "SKILL_STROKE_ANALYSIS"


def test_clinical_decision_bundle_mirrors_legacy_fields_without_requiring_new_tables():
    patient = {
        "id": 7,
        "patient_age": 68,
        "patient_sex": "male",
        "admission_nihss": 12,
        "core_infarct_volume": 18.5,
        "penumbra_volume": 54.0,
        "mismatch_ratio": 2.9,
        "analysis_status": "completed",
    }
    imaging = {
        "patient_id": 7,
        "case_id": "case-7",
        "available_modalities": ["ncct", "mcta"],
        "hemisphere": "left",
        "analysis_result": {
            "core_volume_ml": 18.5,
            "penumbra_volume_ml": 54.0,
            "mismatch_ratio": 2.9,
            "total_slices": 24,
        },
    }
    run = {
        "run_id": "run-7",
        "patient_id": 7,
        "file_id": "case-7",
        "status": "running",
        "planner_input": {
            "patient_id": 7,
            "file_id": "case-7",
            "available_modalities": ["ncct", "mcta"],
            "question": "Assess treatment window.",
        },
        "review_state": {"all_confirmed": False},
    }
    events = [
        {
            "event_id": "evt-low",
            "event_seq": 1,
            "tool_name": "vessel_occlusion",
            "status": "completed",
            "output_ref": {
                "confidence_score": 0.55,
                "evidence_refs": ["series-cta"],
            },
        }
    ]
    dag = {
        "nodes": [
            {
                "id": "vessel_occlusion",
                "step_key": "vessel_occlusion",
                "title": "Vessel Occlusion",
                "stage": "tooling",
                "status": "completed",
                "confidence": 0.55,
                "output_payload": {"evidence_refs": ["series-cta"]},
            }
        ],
        "edges": [],
    }
    report_payload = {
        "three_class_label": "ischemia",
        "vessel_occlusion_class_result": "lvo",
        "final_report": {"summary": "AIS suspected."},
        "evidence_items": [{"evidence_id": "ev-1"}],
        "evidence_map": {"claim-1": {"evidence_ids": ["ev-1"]}},
        "traceability": {"coverage": 0.9},
    }

    bundle = build_clinical_decision_bundle(
        patient=patient,
        imaging=imaging,
        run=run,
        events=events,
        dag=dag,
        validation={},
        report_payload=report_payload,
        source_tag="test",
    )

    assert bundle["bundle_id"] == "bundle:case-7:run-7"
    assert bundle["case_context"]["nihss_score"] == 12
    assert bundle["imaging_context"]["available_modalities"] == ["ncct", "mcta"]
    assert bundle["quality_control"]["qc_status"] == "warning"
    assert bundle["algorithm_results"]["stroke_analysis_result"]["core_volume_ml"] == 18.5
    assert bundle["confidence_summary"]["items"][0]["review_required"] is True
    assert bundle["report"]["evidence_completeness"] == 0.9
    assert bundle["cockpit_view"]["cockpit_node_view"][0]["called_skill_id"] == "SKILL_VESSEL_OCCLUSION"


def test_clinical_decision_bundle_degrades_when_optional_payloads_are_missing():
    bundle = build_clinical_decision_bundle(
        patient=None,
        imaging=None,
        run={"run_id": "run-empty", "file_id": "case-empty"},
        events=[],
        dag={"nodes": [], "edges": []},
        validation=None,
        report_payload=None,
        source_tag="test",
    )

    assert bundle["case_id"] == "case-empty"
    assert bundle["quality_control"]["qc_blocking_required"] is True
    assert bundle["cockpit_view"]["cockpit_task_view"]["node_count"] == 0
    assert bundle["audit"]["persisted"] is False
