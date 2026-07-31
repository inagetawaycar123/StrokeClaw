from __future__ import annotations

import copy
from pathlib import Path

import pytest

import backend.app as app_module
from backend.compat.skill_registry import skill_id_for_tool


def _qc_result(
    *,
    overrideable=True,
    status="failed",
    fingerprint="f" * 64,
    input_mode="volume",
):
    severity = "high" if status == "failed" else ("medium" if status == "warning" else "none")
    findings = [] if status == "passed" else [
        {
            "code": "synthetic_quality_risk",
            "severity": severity,
            "modality": "ncct",
            "metric": 2,
            "threshold": 1,
            "message": "synthetic quality risk",
            "overrideable": overrideable,
        }
    ]
    return {
        "schema_version": "1.0",
        "qc_status": status,
        "qc_score": 0.8 if status != "passed" else 1.0,
        "qc_method": "rule_based_nifti_qc",
        "qc_input_mode": input_mode,
        "qc_not_applicable_checks": (
            ["axial_coverage", "internal_missing_slices", "inter_slice_motion"]
            if input_mode == "single_slice"
            else []
        ),
        "qc_file_readable": True,
        "qc_modality_complete": True,
        "qc_scan_coverage": "complete",
        "qc_slice_thickness_status": "normal",
        "qc_motion_artifact_level": "none",
        "qc_missing_slice_status": "none_suspected",
        "qc_geometry_status": "unknown",
        "qc_warning_message": "" if status == "passed" else "synthetic_quality_risk",
        "qc_affected_nodes": [] if status == "passed" else ["three_class"],
        "qc_blocking_required": status == "failed",
        "qc_review_required": status == "failed",
        "qc_review_reason": "synthetic_quality_risk" if status == "failed" else "",
        "findings": findings,
        "checks": {},
        "limitations": [],
        "review_override": None,
        "qc_fingerprint": fingerprint,
    }


@pytest.fixture(autouse=True)
def _clear_runtime_state():
    with app_module.UPLOAD_JOBS_LOCK:
        app_module.UPLOAD_JOBS.clear()
        app_module.UPLOAD_JOB_PAYLOADS.clear()
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()
    yield
    with app_module.UPLOAD_JOBS_LOCK:
        app_module.UPLOAD_JOBS.clear()
        app_module.UPLOAD_JOB_PAYLOADS.clear()


def _payload(tmp_path: Path, job_id="job-qc"):
    temp_dir = tmp_path / job_id
    temp_dir.mkdir()
    ncct = temp_dir / "ncct.nii.gz"
    ncct.write_bytes(b"synthetic")
    return {
        "job_id": job_id,
        "patient_id": 1,
        "file_id": "case-qc",
        "files": {"ncct_file": {"path": str(ncct), "filename": ncct.name}},
        "temp_dir": str(temp_dir),
        "modalities": ["ncct"],
        "agent_run_id": None,
    }


def _create_job(payload):
    app_module._create_upload_job(
        payload["job_id"], payload["patient_id"], payload["file_id"], payload["modalities"]
    )
    app_module._update_step(payload["job_id"], "archive_ready", "completed", "ready")


def test_failed_qc_pauses_before_any_model_and_preserves_payload(monkeypatch, tmp_path):
    payload = _payload(tmp_path)
    _create_job(payload)
    called = {"models": 0}
    monkeypatch.setattr(app_module, "run_image_quality_control", lambda *a, **k: _qc_result())
    monkeypatch.setattr(
        app_module,
        "_invoke_internal_upload",
        lambda *_: called.__setitem__("models", called["models"] + 1),
    )

    app_module._run_upload_processing_job(payload["job_id"], payload)

    job = app_module._get_upload_job(payload["job_id"])
    steps = {item["key"]: item for item in job["steps"]}
    assert called["models"] == 0
    assert job["status"] == "paused_review_required"
    assert steps["image_quality_control"]["status"] == "waiting"
    assert steps["modality_detect"]["status"] == "pending"
    assert Path(payload["temp_dir"]).exists()
    assert payload["job_id"] in app_module.UPLOAD_JOB_PAYLOADS


@pytest.mark.parametrize("qc_status", ["passed", "warning"])
def test_passed_and_warning_qc_continue_only_after_real_modality_check(
    monkeypatch, tmp_path, qc_status
):
    payload = _payload(tmp_path, job_id=f"job-{qc_status}")
    _create_job(payload)
    observed = {}
    monkeypatch.setattr(
        app_module,
        "run_image_quality_control",
        lambda *a, **k: _qc_result(
            status=qc_status,
            input_mode="single_slice" if qc_status == "warning" else "volume",
        ),
    )

    def invoke(_payload):
        job = app_module._get_upload_job(payload["job_id"])
        observed.update({step["key"]: step["status"] for step in job["steps"]})
        return False, "synthetic stop after model boundary", {}

    monkeypatch.setattr(app_module, "_invoke_internal_upload", invoke)
    app_module._run_upload_processing_job(payload["job_id"], payload)
    assert observed["image_quality_control"] == "completed"
    assert observed["modality_detect"] == "completed"
    assert observed["three_class"] == "running"
    assert not Path(payload["temp_dir"]).exists()
    if qc_status == "warning":
        job = app_module._get_upload_job(payload["job_id"])
        quality_step = next(
            item for item in job["steps"] if item["key"] == "image_quality_control"
        )
        assert "单层影像：三维质控项目不适用" in quality_step["message"]


def test_structural_failure_cannot_be_overridden(monkeypatch, tmp_path):
    payload = _payload(tmp_path)
    _create_job(payload)
    monkeypatch.setattr(
        app_module, "run_image_quality_control", lambda *a, **k: _qc_result(overrideable=False)
    )
    app_module._run_upload_processing_job(payload["job_id"], payload)

    response = app_module.app.test_client().post(
        f"/api/upload/jobs/{payload['job_id']}/quality-review",
        json={
            "decision": "accept_risk",
            "reviewer": "doctor-test",
            "comment": "synthetic",
            "qc_fingerprint": "f" * 64,
        },
    )
    assert response.status_code == 409
    assert "cannot be overridden" in response.get_json()["error"]


def test_accept_risk_is_idempotent_and_resumes_once(monkeypatch, tmp_path):
    payload = _payload(tmp_path)
    _create_job(payload)
    monkeypatch.setattr(app_module, "run_image_quality_control", lambda *a, **k: _qc_result())
    app_module._run_upload_processing_job(payload["job_id"], payload)
    starts = []
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda job_id, staged: starts.append((job_id, staged)),
    )
    body = {
        "decision": "accept_risk",
        "reviewer": "doctor-test",
        "comment": "accept synthetic risk",
        "qc_fingerprint": "f" * 64,
    }
    client = app_module.app.test_client()
    first = client.post(f"/api/upload/jobs/{payload['job_id']}/quality-review", json=body)
    second = client.post(f"/api/upload/jobs/{payload['job_id']}/quality-review", json=body)
    assert first.status_code == 200
    assert first.get_json()["execution_resumed"] is True
    assert first.get_json()["quality_control_result"]["qc_status"] == "failed"
    assert first.get_json()["quality_control_result"]["review_override"]["decision"] == "accept_risk"
    assert second.status_code == 200
    assert second.get_json()["idempotent"] is True
    assert len(starts) == 1


def test_reject_marks_future_steps_skipped_and_removes_temp(monkeypatch, tmp_path):
    payload = _payload(tmp_path)
    _create_job(payload)
    monkeypatch.setattr(app_module, "run_image_quality_control", lambda *a, **k: _qc_result())
    app_module._run_upload_processing_job(payload["job_id"], payload)
    response = app_module.app.test_client().post(
        f"/api/upload/jobs/{payload['job_id']}/quality-review",
        json={
            "decision": "reject_reupload",
            "reviewer": "doctor-test",
            "comment": "re-upload synthetic case",
            "qc_fingerprint": "f" * 64,
        },
    )
    assert response.status_code == 200
    job = app_module._get_upload_job(payload["job_id"])
    steps = {item["key"]: item for item in job["steps"]}
    assert job["status"] == "review_rejected"
    assert steps["image_quality_control"]["status"] == "failed"
    assert steps["modality_detect"]["status"] == "skipped"
    assert not Path(payload["temp_dir"]).exists()


def test_agent_sequence_and_skill_metadata_use_distinct_nodes():
    for sequence in app_module.AGENT_TOOL_SEQUENCE_MAP.values():
        assert sequence[:3] == [
            "load_patient_context",
            "image_quality_control",
            "detect_modalities",
        ]
    assert app_module.AGENT_TOOL_LABELS["load_patient_context"] == "Case_Context.load()"
    assert app_module.AGENT_TOOL_LABELS["image_quality_control"] == "Image_QC.validate()"
    assert app_module.AGENT_TOOL_LABELS["detect_modalities"] == "Modality_Detect.route()"
    assert skill_id_for_tool("load_patient_context") == "SKILL_CASE_CONTEXT"
    assert skill_id_for_tool("image_quality_control") == "SKILL_IMG_QC"
    assert skill_id_for_tool("detect_modalities") == "SKILL_MODALITY_ID"


def test_direct_agent_quality_review_resumes_at_modality_detection(monkeypatch):
    run_id = "run-direct-qc"
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=1,
        file_id="case-direct-qc",
        available_modalities=["ncct"],
    )
    result = _qc_result()

    def pause(state):
        state["status"] = "paused_review_required"
        state["stage"] = "review"
        state["current_tool"] = "image_quality_control"
        state["planner_input"]["quality_control_result"] = copy.deepcopy(result)
        state["planner_output"] = {
            "tool_sequence": ["load_patient_context", "image_quality_control", "detect_modalities"],
            "path_decision": {"imaging_path": "ncct_only"},
        }
        state["steps"] = [
            {"key": "load_patient_context", "status": "completed"},
            {"key": "image_quality_control", "status": "waiting"},
            {"key": "detect_modalities", "status": "pending"},
        ]
        state["tool_results"] = [
            {"tool_name": "image_quality_control", "status": "waiting", "structured_output": copy.deepcopy(result)}
        ]
        state["human_checkpoint"] = {
            "type": "image_quality_control",
            "status": "waiting",
            "qc_fingerprint": result["qc_fingerprint"],
        }

    app_module._update_agent_run(run_id, pause)
    starts = []

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            starts.append((target, args, daemon))

        def start(self):
            return None

    monkeypatch.setattr(app_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(app_module, "_persist_quality_control_to_imaging", lambda *_: True)
    response = app_module.app.test_client().post(
        f"/api/agent/runs/{run_id}/quality-review",
        json={
            "decision": "accept_risk",
            "reviewer": "doctor-test",
            "comment": "synthetic direct review",
            "qc_fingerprint": result["qc_fingerprint"],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["execution_resumed"] is True
    assert len(starts) == 1
    assert starts[0][1] == (run_id, "detect_modalities")
