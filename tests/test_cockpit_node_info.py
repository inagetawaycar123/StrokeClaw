import copy

import pytest

from backend import app as app_module
from backend.compat.skill_registry import skill_id_for_tool


@pytest.fixture(autouse=True)
def clear_agent_runtime():
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()
    yield
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()


def _seed_cockpit_run(run_id="run-cockpit-node-info"):
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=10001,
        file_id="synthetic-case",
        available_modalities=["ncct", "mcta"],
        source="test",
    )

    def _prepare(run):
        run["status"] = "paused_review_required"
        run["stage"] = "review"
        run["planner_output"] = {
            "imaging_path": "ncct_mcta",
            "tool_sequence": ["ekv", "human_confirm"],
        }
        run["steps"] = [
            {
                "key": "ekv",
                "status": "completed",
                "attempts": 1,
                "message": "evidence check completed",
            },
            {
                "key": "human_confirm",
                "status": "waiting",
                "attempts": 1,
                "message": "awaiting doctor review",
            },
        ]
        run["tool_results"] = [
            {
                "tool_name": "ekv",
                "status": "completed",
                "attempt": 1,
                "retryable": False,
                "structured_output": {
                    "summary": "Synthetic evidence summary",
                    "confidence_score": 0.62,
                    "confidence_method": "evidence_coverage_ratio",
                    "evidence_refs": ["E-1"],
                    "conflict_count": 1,
                },
            },
            {
                "tool_name": "human_confirm",
                "status": "waiting",
                "attempt": 1,
                "retryable": False,
                "structured_output": {"status": "waiting"},
            },
        ]
        run["human_checkpoint"] = {
            "required": True,
            "action_required": "confirm_report_sections",
        }

    app_module._update_agent_run(run_id, _prepare)
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_EVENTS[run_id] = [
            {
                "event_id": "evt-ekv",
                "event_seq": 1,
                "run_id": run_id,
                "timestamp": "2026-07-31 10:00:00",
                "stage": "ekv",
                "agent_name": "Evidence Verification Agent",
                "tool_name": "ekv",
                "status": "completed",
                "input_ref": {"summary": "Synthetic claims"},
                "output_ref": {
                    "summary": "Synthetic evidence summary",
                    "confidence_score": 0.62,
                    "confidence_method": "evidence_coverage_ratio",
                    "evidence_refs": ["E-1", "E-1", "E-2"],
                    "conflict_count": 1,
                },
                "latency_ms": 57,
                "retryable": False,
                "attempt": 1,
            },
            {
                "event_id": "evt-human",
                "event_seq": 2,
                "run_id": run_id,
                "timestamp": "2026-07-31 10:00:01",
                "stage": "review",
                "agent_name": "Human Review Agent",
                "tool_name": "human_confirm",
                "status": "waiting",
                "input_ref": {"pending_sections": ["imaging_summary"]},
                "output_ref": {"status": "waiting"},
                "latency_ms": 0,
                "retryable": False,
                "attempt": 1,
            },
        ]
    return run_id


def test_skill_registry_maps_normalized_cockpit_tool_keys():
    assert skill_id_for_tool("run_ncct_classification") == "SKILL_NCCT_TRIAGE"
    assert (
        skill_id_for_tool("run_vessel_occlusion_classification")
        == "SKILL_VESSEL_OCCLUSION"
    )
    assert skill_id_for_tool("human_confirm") == "SKILL_HUMAN_REVIEW"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.62, 0.62),
        (62, 0.62),
        (100, 1.0),
        (True, None),
        (-1, None),
        (101, None),
        ("invalid", None),
    ],
)
def test_node_info_confidence_normalization(value, expected):
    assert app_module._node_info_confidence(value) == expected


def test_node_info_extracts_evidence_and_conflict_without_fabrication():
    evidence = app_module._node_info_evidence_refs(
        {
            "evidence_refs": [
                {"evidence_id": "E-1"},
                "E-1",
                "E-2",
                {"source_ref": "GUIDE-1"},
            ]
        }
    )
    assert evidence == ["E-1", "E-2", "GUIDE-1"]
    assert app_module._node_info_conflict_status({"conflict_count": 1}) == "conflict"
    assert (
        app_module._node_info_conflict_status({"conflict_count": 0})
        == "no_conflict"
    )
    assert app_module._node_info_conflict_status({}) == "unknown"


def test_node_info_merges_event_tool_result_and_skill_registry():
    node_info = app_module._build_cockpit_node_info(
        tool_name="ekv",
        step={"key": "ekv", "status": "completed"},
        event={
            "agent_name": "Evidence Verification Agent",
            "input_ref": {"summary": "Synthetic claims"},
            "output_ref": {
                "summary": "Synthetic evidence summary",
                "confidence_score": 62,
                "evidence_refs": ["E-1"],
                "conflict_status": "conflict",
            },
            "result_summary": "Synthetic evidence summary",
        },
        tool_result={
            "tool_name": "ekv",
            "structured_output": {
                "confidence_method": "evidence_coverage_ratio",
            },
        },
    )

    assert node_info["agent_name"] == "Evidence Verification Agent"
    assert node_info["skill_id"] == "SKILL_GUIDELINE_CHECK"
    assert node_info["skill_name"] == "external_guideline_check"
    assert node_info["confidence_score"] == 0.62
    assert node_info["confidence_method"] == "evidence_coverage_ratio"
    assert node_info["evidence_refs"] == ["E-1"]
    assert node_info["conflict_status"] == "conflict"
    assert "Synthetic claims" in node_info["input_summary"]
    assert node_info["output_summary"] == "Synthetic evidence summary"


def test_run_and_event_serializers_attach_consistent_node_info():
    run_id = _seed_cockpit_run()
    run = app_module._ensure_w0_run_fields(
        app_module._get_agent_run(run_id),
        events=app_module._get_agent_events(run_id),
    )
    events = app_module._normalize_agent_events_for_api(
        run,
        app_module._get_agent_events(run_id),
    )

    ekv_step = next(step for step in run["steps"] if step["key"] == "ekv")
    ekv_result = next(
        result for result in run["tool_results"] if result["tool_name"] == "ekv"
    )
    ekv_event = next(event for event in events if event["tool_name"] == "ekv")

    for payload in (ekv_step, ekv_result, ekv_event):
        assert payload["node_info"]["skill_id"] == "SKILL_GUIDELINE_CHECK"
        assert payload["node_info"]["confidence_score"] == 0.62
        assert payload["node_info"]["conflict_status"] == "conflict"

    human_step = next(
        step for step in run["steps"] if step["key"] == "human_confirm"
    )
    assert human_step["status"] == "waiting"
    assert human_step["node_info"]["skill_id"] == "SKILL_HUMAN_REVIEW"


def test_cockpit_apis_return_node_info_without_changing_existing_contract():
    run_id = _seed_cockpit_run()
    client = app_module.app.test_client()

    run_response = client.get(f"/api/agent/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.get_json()
    assert run_payload["success"] is True
    assert "run" in run_payload
    assert any(
        step.get("node_info", {}).get("skill_id") == "SKILL_HUMAN_REVIEW"
        for step in run_payload["run"]["steps"]
    )

    event_response = client.get(f"/api/agent/runs/{run_id}/events")
    assert event_response.status_code == 200
    event_payload = event_response.get_json()
    assert event_payload["success"] is True
    assert event_payload["events"][0]["node_info"]["skill_id"] == "SKILL_GUIDELINE_CHECK"

    overview_response = client.get(f"/api/cockpit/overview?run_id={run_id}")
    assert overview_response.status_code == 200
    overview_payload = overview_response.get_json()
    ekv_node = next(
        node for node in overview_payload["dag"]["nodes"] if node["step_key"] == "ekv"
    )
    assert ekv_node["node_info"]["skill_id"] == "SKILL_GUIDELINE_CHECK"
    assert ekv_node["node_info"]["evidence_refs"] == ["E-1", "E-2"]

    detail_response = client.get(f"/api/cockpit/runs/{run_id}/nodes/ekv")
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["success"] is True
    assert detail_payload["node"]["node_info"] == ekv_node["node_info"]
    assert detail_payload["input_payload"] == ekv_node["input_payload"]
    assert detail_payload["output_payload"] == ekv_node["output_payload"]


def test_node_info_enrichment_does_not_mutate_original_runtime_state():
    run_id = _seed_cockpit_run()
    original = app_module._get_agent_run(run_id)
    enriched = app_module._ensure_w0_run_fields(
        copy.deepcopy(original),
        events=app_module._get_agent_events(run_id),
    )
    stored = app_module._get_agent_run(run_id)

    assert enriched["steps"][0].get("node_info")
    assert "node_info" not in stored["steps"][0]
