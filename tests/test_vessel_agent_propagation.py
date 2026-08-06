import json
import os

import backend.app as app_module


def _cleanup_run(run_id):
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.pop(run_id, None)
        app_module.AGENT_EVENTS.pop(run_id, None)


def test_failed_vessel_tool_contract_reaches_agent_final_context(monkeypatch):
    run_id = "test-vessel-soft-failure"
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=1,
        file_id="case-failed",
        available_modalities=["ncct", "mcta"],
    )
    stale_success = {
        "status": "completed",
        "vessel_occlusion_class_result": "大血管闭塞",
        "predicted_class": "Class_1_LVO",
        "confidence": 0.99,
        "class_counts": {"Class_1_LVO": 1},
        "total_slices": 1,
        "valid_predictions": 1,
    }
    failed = {
        "status": "failed",
        "error_code": "ALL_PREDICTIONS_FAILED",
        "error_message": "All 1 predictions failed",
        "total_slices": 1,
        "failures": [
            {
                "slice_file": "slice_000_mcta.png",
                "error_code": "MODEL_INFERENCE_FAILED",
                "error_message": "boom",
            }
        ],
    }

    try:
        assert app_module._attach_vessel_result_to_agent_run(run_id, stale_success)
        monkeypatch.setattr(
            app_module,
            "_tool_vessel_occlusion",
            lambda _run: (
                False,
                failed,
                app_module._tool_error_contract(
                    "TOOL_EXECUTION_FAILED", "All 1 predictions failed"
                ),
            ),
        )

        ok, tool_result = app_module._execute_agent_tool(run_id, "vessel_occlusion")

        assert ok is False
        assert tool_result["structured_output"]["status"] == "failed"
        run = app_module._get_agent_run(run_id)
        context = app_module._build_context_from_completed_tools(run)
        result = context["vessel_occlusion_result"]
        assert result["status"] == "failed"
        assert result["error_code"] == "ALL_PREDICTIONS_FAILED"
        assert result["vessel_occlusion_class_result"] is None
        assert result["failures"][0]["error_message"] == "boom"
    finally:
        _cleanup_run(run_id)


def test_report_tool_keeps_persisted_vessel_result_when_run_has_none(monkeypatch):
    persisted = {
        "status": "completed",
        "vessel_occlusion_class_result": "中血管闭塞",
        "predicted_class": "Class_2_MEVO",
        "confidence": 0.81,
        "class_counts": {"Class_2_MEVO": 1},
        "total_slices": 1,
        "valid_predictions": 1,
    }
    monkeypatch.setattr(
        app_module,
        "_invoke_internal_generate_report",
        lambda *_args, **_kwargs: (
            True,
            "ok",
            {
                "report": "report",
                "report_payload": {"vessel_occlusion_result": persisted},
                "json_path": None,
            },
        ),
    )
    monkeypatch.setattr(
        app_module,
        "build_summary_artifacts",
        lambda **kwargs: kwargs["report_payload"],
    )
    monkeypatch.setattr(app_module, "get_patient_by_id", lambda _patient_id: {})
    run = {
        "run_id": "report-db-fallback",
        "planner_input": {"patient_id": 1, "file_id": "case-1"},
        "tool_results": [],
    }

    ok, output, error = app_module._tool_generate_medgemma_report(run)

    assert ok is True
    assert error is None
    result = output["report_payload"]["vessel_occlusion_result"]
    assert result["status"] == "completed"
    assert result["predicted_class"] == "Class_2_MEVO"
    assert result["confidence"] == 0.81


def test_report_result_lookup_and_notes_sync_support_current_and_legacy_files(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REPORT_RESULTS_DIR", str(tmp_path))
    legacy_dir = tmp_path / "legacy_medgemma"
    legacy_dir.mkdir()
    legacy_path = legacy_dir / "medgemma_report_case-1_20260101_000000.json"
    current_path = tmp_path / "baichuan_report_case-1_20260102_000000.json"
    legacy_path.write_text(json.dumps({"report_payload": {}}), encoding="utf-8")
    current_path.write_text(json.dumps({"report_payload": {}}), encoding="utf-8")
    os.utime(legacy_path, (1, 1))
    os.utime(current_path, (2, 2))

    assert app_module._latest_result_json_for_file("case-1") == str(current_path)

    sync = app_module._sync_notes_to_result_json(
        file_id="case-1",
        patient_id=1,
        notes_html="<p>复核完成</p>",
        saved_at="2026-07-28T00:00:00Z",
    )
    assert set(sync["updated_files"]) == {str(legacy_path), str(current_path)}
    for path in (legacy_path, current_path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["doctor_notes"]["text"] == "复核完成"
        assert payload["report_payload"]["doctor_notes"]["patient_id"] == 1
