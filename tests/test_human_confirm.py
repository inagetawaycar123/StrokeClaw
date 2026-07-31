import copy

import pytest

from backend import app as app_module


PATH_NAMES = {
    "ncct_only",
    "ncct_single_phase_cta",
    "ncct_mcta",
    "ncct_mcta_ctp",
}


@pytest.fixture(autouse=True)
def clear_agent_runtime():
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()
    yield
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()


def _classification(*, blocked=False):
    label = "hemo" if blocked else "normal"
    return {
        "status": "completed",
        "three_class_label": label,
        "three_class_label_cn": "脑出血" if blocked else "正常",
        "three_class_confidence": 0.91,
        "class_counts": {
            "normal": 0 if blocked else 1,
            "hemo": 1 if blocked else 0,
            "infarct": 0,
        },
        "total_slices": 1,
        "safety_gate": {
            "blocked": blocked,
            "reason_code": (
                "NCCT_SUSPECTED_HEMORRHAGE" if blocked else None
            ),
            "reason": (
                "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析"
                if blocked
                else None
            ),
            "requires_clinician_review": blocked,
        },
    }


def _seed_report_run(run_id="run-human", *, blocked=False):
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=101,
        file_id=f"case-{run_id}",
        available_modalities=["ncct"],
        source="test",
    )

    report_output = {
        "report": "Synthetic report",
        "report_payload": {
            "summary_findings": ["Synthetic NCCT finding"],
            "question_answer": {
                "answer": "Synthetic answer",
                "confidence": 0.9,
                "key_points": ["Synthetic key point"],
                "next_steps": ["Synthetic next step"],
            },
            "final_report": {
                "risk_level": "high" if blocked else "medium",
                "uncertainties": ["Synthetic uncertainty"],
            },
            "traceability": {
                "coverage": 1.0,
                "mapped_findings": 1,
                "total_findings": 1,
                "high_risk_unmapped_count": 0,
            },
        },
    }

    def _prepare(run):
        run["status"] = "running"
        run["stage"] = "summary"
        run["planner_input"]["three_class_result"] = _classification(
            blocked=blocked
        )
        run["planner_output"] = {
            "imaging_path": "ncct_only",
            "path_decision": {"imaging_path": "ncct_only", "valid": True},
            "tool_sequence": [
                "generate_medgemma_report",
                "human_confirm",
            ],
        }
        run["steps"] = [
            {
                "key": "generate_medgemma_report",
                "title": "generate_medgemma_report",
                "status": "completed",
                "message": "Tool completed",
                "retryable": False,
                "attempts": 1,
                "started_at": "2026-07-31 10:00:00",
                "ended_at": "2026-07-31 10:00:01",
            },
            {
                "key": "human_confirm",
                "title": "human_confirm",
                "status": "pending",
                "message": "",
                "retryable": False,
                "attempts": 0,
                "started_at": None,
                "ended_at": None,
            },
        ]
        run["tool_results"] = [
            {
                "tool_name": "generate_medgemma_report",
                "status": "completed",
                "error_code": None,
                "retryable": False,
                "structured_output": copy.deepcopy(report_output),
                "raw_ref": {"tool_name": "generate_medgemma_report"},
                "latency_ms": 1,
                "attempt": 1,
            }
        ]
        if blocked:
            for tool_name in (
                "generate_ctp_maps",
                "vessel_occlusion",
                "run_stroke_analysis",
            ):
                run["tool_results"].append(
                    {
                        "tool_name": tool_name,
                        "status": "skipped",
                        "structured_output": {
                            "status": "skipped",
                            "reason": "Blocked by NCCT safety gate",
                        },
                    }
                )

    app_module._update_agent_run(run_id, _prepare)
    return run_id


def _pause_at_human_node(run_id):
    ok, tool_result = app_module._execute_agent_tool(
        run_id, "human_confirm"
    )
    assert ok is True
    assert tool_result["status"] == "waiting"
    app_module._pause_for_human_confirm(
        run_id,
        tool_name="human_confirm",
        tool_result=tool_result,
    )
    return app_module._get_agent_run(run_id)


def _confirm_all_sections(run_id):
    run = app_module._get_agent_run(run_id)
    review_state = copy.deepcopy(run["review_state"])
    for section in review_state["sections"]:
        section["review_status"] = "confirmed"
    review_state = app_module._review_recompute_state(review_state)

    def _save(run_state):
        app_module._review_attach_to_run_state(run_state, review_state)

    app_module._update_agent_run(run_id, _save)


def test_all_runtime_paths_end_with_terminal_human_confirm():
    assert PATH_NAMES == set(app_module.AGENT_TOOL_SEQUENCE_MAP)
    for sequence in app_module.AGENT_TOOL_SEQUENCE_MAP.values():
        assert sequence[-2:] == [
            "generate_medgemma_report",
            "human_confirm",
        ]
    assert app_module.POST_UPLOAD_SUMMARY_TOOL_SEQUENCE[-1] == "human_confirm"


def test_report_completion_pauses_run_at_waiting_human_node():
    run_id = _seed_report_run()
    run = _pause_at_human_node(run_id)

    human_step = next(
        step for step in run["steps"] if step["key"] == "human_confirm"
    )
    assert human_step["status"] == "waiting"
    assert human_step["ended_at"] is None
    assert run["status"] == "paused_review_required"
    assert run["stage"] == "review"
    assert run["current_tool"] == "human_confirm"
    assert run["human_checkpoint"]["required"] is True
    assert run["review_state"]["all_confirmed"] is False
    assert run["result"]["report_result"]["report"] == "Synthetic report"

    client = app_module.app.test_client()
    result_response = client.get(f"/api/agent/runs/{run_id}/result")
    review_response = client.get(f"/api/agent/runs/{run_id}/review")
    assert result_response.status_code == 200
    assert review_response.status_code == 200
    result_payload = result_response.get_json()
    assert result_payload["run_status"] == "paused_review_required"
    assert result_payload["human_checkpoint"]["required"] is True
    review_payload = review_response.get_json()
    assert review_payload["run_status"] == "paused_review_required"
    assert review_payload["can_enter_viewer"] is False


def test_completion_requires_all_sections_and_is_idempotent():
    run_id = _seed_report_run()
    _pause_at_human_node(run_id)

    updated, error = app_module._complete_human_confirm_checkpoint(run_id)
    assert updated is None
    assert "before all sections confirmed" in error

    _confirm_all_sections(run_id)
    updated, error = app_module._complete_human_confirm_checkpoint(run_id)
    assert error is None
    assert updated["status"] == "succeeded"
    assert updated["stage"] == "done"
    assert updated["human_checkpoint"]["required"] is False
    assert updated["finalization"]["signed"] is True
    assert updated["result"]["human_confirm_result"]["approved"] is True
    event_count = len(app_module._get_agent_events(run_id))

    repeated, error = app_module._complete_human_confirm_checkpoint(run_id)
    assert error is None
    assert repeated["status"] == "succeeded"
    assert len(app_module._get_agent_events(run_id)) == event_count


def test_confirm_section_endpoint_completes_node_only_on_final_section(
    monkeypatch,
):
    run_id = _seed_report_run("run-review-api")
    run = _pause_at_human_node(run_id)
    monkeypatch.setattr(
        app_module,
        "_persist_review_state_best_effort",
        lambda **_kwargs: {"success": True, "error": None, "mode": "test"},
    )
    client = app_module.app.test_client()
    section_ids = [
        section["section_id"] for section in run["review_state"]["sections"]
    ]

    for index, section_id in enumerate(section_ids):
        response = client.post(
            f"/api/agent/runs/{run_id}/review",
            json={
                "action": "confirm_section",
                "section_id": section_id,
                "draft_text": f"Synthetic section {index}",
                "doctor_note": "Synthetic note",
                "auto_finalize": True,
            },
        )
        assert response.status_code == 200
        payload = response.get_json()
        if index < len(section_ids) - 1:
            assert payload["run_status"] is None
            assert payload["can_enter_viewer"] is False
            assert app_module._get_agent_run(run_id)["status"] == (
                "paused_review_required"
            )
        else:
            assert payload["run_status"] == "succeeded"
            assert payload["can_enter_viewer"] is True
            assert payload["human_checkpoint"]["required"] is False
            completed_run = app_module._get_agent_run(run_id)
            assert completed_run["result"]["report_result"]["report"] == (
                payload["final_report"]
            )
            assert completed_run["result"]["report_result"][
                "report_payload"
            ]["final_confirmed_report"] == payload["final_report"]


def test_hemorrhage_gate_remains_blocked_after_human_completion():
    run_id = _seed_report_run("run-safety", blocked=True)
    paused = _pause_at_human_node(run_id)
    assert paused["human_checkpoint"]["safety_gate_blocked"] is True
    assert paused["human_checkpoint"]["reason_code"] == (
        "NCCT_SUSPECTED_HEMORRHAGE"
    )

    _confirm_all_sections(run_id)
    completed, error = app_module._complete_human_confirm_checkpoint(run_id)

    assert error is None
    assert completed["status"] == "succeeded"
    assert completed["result"]["safety_gate"]["blocked"] is True
    assert completed["human_checkpoint"]["safety_gate_blocked"] is True
    skipped = {
        result["tool_name"]
        for result in completed["result"]["tool_results"]
        if result.get("status") == "skipped"
    }
    assert {
        "generate_ctp_maps",
        "vessel_occlusion",
        "run_stroke_analysis",
    }.issubset(skipped)


def test_legacy_run_without_human_node_is_not_rewritten():
    run_id = _seed_report_run("run-legacy")

    def _make_legacy(run):
        run["status"] = "succeeded"
        run["stage"] = "done"
        run["steps"] = [
            step
            for step in run["steps"]
            if step.get("key") != "human_confirm"
        ]
        run["planner_output"]["tool_sequence"] = [
            "generate_medgemma_report"
        ]

    app_module._update_agent_run(run_id, _make_legacy)
    before = app_module._get_agent_run(run_id)
    updated, error = app_module._complete_human_confirm_checkpoint(run_id)

    assert error is None
    assert updated["steps"] == before["steps"]
    assert updated["tool_results"] == before["tool_results"]
    assert app_module._get_agent_events(run_id) == []
