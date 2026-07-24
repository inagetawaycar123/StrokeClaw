from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py"


def test_compat_routes_are_additive_and_do_not_replace_existing_cockpit_route():
    source = APP_PATH.read_text(encoding="utf-8")

    assert '@app.route("/api/cockpit/overview", methods=["GET"])' in source
    assert '@app.route("/api/compat/skill-registry", methods=["GET"])' in source
    assert '@app.route("/api/compat/clinical-decision-bundle", methods=["GET"])' in source
    assert "build_clinical_decision_bundle(" in source
    assert "get_skill_registry()" in source


def test_upload_execution_is_gated_by_clinical_dag_review():
    source = APP_PATH.read_text(encoding="utf-8")

    assert '@app.route("/api/upload/jobs/<job_id>/dag-review", methods=["POST"])' in source
    assert '"dag_review_required": True' in source
    assert 'UPLOAD_JOB_PAYLOADS[job_id] = payload' in source
    assert 'target=_run_upload_processing_job' in source


def test_internal_upload_reports_real_ctp_phase_progress_to_the_job():
    source = APP_PATH.read_text(encoding="utf-8")

    assert '"upload_job_id": str(payload.get("job_id") or "")' in source
    assert "def report_ctp_progress(" in source
    assert '"three_class",\n                    "completed"' in source
    assert 'progress_callback=report_ctp_progress' in source
    assert 'f"正在生成 CTP 灌注图：{progress_text} · {percent}%"' in source
