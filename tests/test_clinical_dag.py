from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest

from backend import app as app_module
from backend.clinical_dag import build_clinical_dag, normalize_modalities


PATH_CASES = [
    (["ncct"], "ncct_only"),
    (["ncct", "mcta"], "ncct_single_phase_cta"),
    (["ncct", "mcta", "vcta", "dcta"], "ncct_mcta"),
    (
        ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"],
        "ncct_mcta_ctp",
    ),
]


@pytest.fixture(autouse=True)
def clear_runtime_state():
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
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()


@pytest.mark.parametrize(("modalities", "expected_path"), PATH_CASES)
def test_four_supported_paths_have_stable_server_dag(modalities, expected_path):
    first = build_clinical_dag(modalities)
    second = build_clinical_dag(list(reversed(modalities)))

    assert first["valid"] is True
    assert first["path"] == expected_path
    assert first["dag_id"] == second["dag_id"]
    assert first["available_modalities"] == sorted(set(modalities))
    assert first["nodes"]
    assert first["edges"]


def test_modality_aliases_are_canonical_and_unsupported_combinations_are_rejected():
    assert normalize_modalities(["NCCT", "mcat", "vcat", "dcat"]) == [
        "ncct",
        "mcta",
        "vcta",
        "dcta",
    ]
    invalid = build_clinical_dag(["ncct", "cbf"])
    assert invalid["valid"] is False
    assert invalid["path"] is None


def test_collateral_node_is_inactive_metadata_and_not_an_execution_tool():
    dag = build_clinical_dag(["ncct", "mcta", "vcta", "dcta"])
    collateral = next(node for node in dag["nodes"] if node["id"] == "collateral_score")

    assert collateral["status"] == "inactive"
    assert collateral["active"] is False
    assert all(
        "collateral_score" not in sequence
        for sequence in app_module.AGENT_TOOL_SEQUENCE_MAP.values()
    )


def _stage_job(job_id="job-review", *, with_agent=True):
    modalities = ["ncct", "mcta", "vcta", "dcta"]
    dag = build_clinical_dag(modalities)
    run_id = f"run-{job_id}" if with_agent else None
    app_module._create_upload_job(
        job_id,
        patient_id=1,
        file_id=f"case-{job_id}",
        modalities=modalities,
        clinical_dag=dag,
    )
    if run_id:
        app_module._create_agent_run(
            run_id=run_id,
            patient_id=1,
            file_id=f"case-{job_id}",
            available_modalities=modalities,
            linked_upload_job_id=job_id,
            execution_mode="post_upload_summary",
        )
    payload = {
        "job_id": job_id,
        "patient_id": 1,
        "file_id": f"case-{job_id}",
        "modalities": modalities,
        "agent_run_id": run_id,
        "files": {},
    }
    staged = app_module._stage_upload_for_dag_review(job_id, payload, dag)
    return dag, payload, staged


def _review(client, job_id, dag, decision="approved", **overrides):
    payload = {
        "doctor_final_decision": decision,
        "reviewer": "doctor-test",
        "dag_id": dag["dag_id"],
        "available_modalities": dag["available_modalities"],
        **overrides,
    }
    return client.post(f"/api/upload/jobs/{job_id}/dag-review", json=payload)


def test_staging_waits_for_review_without_starting_models_or_agent(monkeypatch):
    starts = []
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda *_args, **_kwargs: starts.append(True),
    )

    dag, _payload, staged = _stage_job()

    assert dag["valid"] is True
    assert staged["status"] == "awaiting_review"
    assert staged["execution_authorized"] is False
    assert staged["dag_review"]["review_status"] == "pending"
    assert starts == []
    assert app_module._get_agent_run("run-job-review")["status"] == "queued"


def test_upload_endpoint_stages_files_without_starting_execution(monkeypatch, tmp_path):
    starts = []
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(app_module, "NIBABEL_AVAILABLE", True)
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda *_args, **_kwargs: starts.append(True),
    )

    with app_module.app.test_client() as client:
        response = client.post(
            "/api/upload/start",
            data={
                "patient_id": "1",
                "ncct_file": (BytesIO(b"synthetic-nifti-placeholder"), "case.nii"),
                "start_agent_run": "false",
            },
            content_type="multipart/form-data",
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["status"] == "awaiting_review"
    assert data["dag_review_required"] is True
    assert data["clinical_dag"]["path"] == "ncct_only"
    assert starts == []
    assert data["job_id"] in app_module.UPLOAD_JOB_PAYLOADS


def test_approval_starts_exactly_once_and_records_reviewer(monkeypatch):
    dag, payload, _staged = _stage_job()
    starts = []
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda job_id, staged_payload: starts.append((job_id, staged_payload)),
    )

    with app_module.app.test_client() as client:
        first = _review(client, "job-review", dag)
        duplicate = _review(client, "job-review", dag)

    assert first.status_code == 200
    assert first.get_json()["execution_started"] is True
    assert duplicate.status_code == 409
    assert starts == [("job-review", payload)]
    job = app_module._get_upload_job("job-review")
    assert job["execution_authorized"] is True
    assert job["dag_review"]["reviewer"] == "doctor-test"


def test_concurrent_approval_only_authorizes_one_execution(monkeypatch):
    dag, _payload, _staged = _stage_job()
    starts = []
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda job_id, _payload: starts.append(job_id),
    )

    def submit():
        with app_module.app.test_client() as client:
            return _review(client, "job-review", dag).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _unused: submit(), range(2)))

    assert sorted(statuses) == [200, 409]
    assert starts == ["job-review"]


def test_rejection_is_terminal_clears_payload_and_cancels_queued_agent(monkeypatch):
    dag, _payload, _staged = _stage_job()
    starts = []
    monkeypatch.setattr(
        app_module,
        "_start_upload_processing_thread",
        lambda *_args, **_kwargs: starts.append(True),
    )

    with app_module.app.test_client() as client:
        rejected = _review(client, "job-review", dag, decision="rejected")
        approve_after_reject = _review(client, "job-review", dag)

    assert rejected.status_code == 200
    assert approve_after_reject.status_code == 409
    assert starts == []
    assert "job-review" not in app_module.UPLOAD_JOB_PAYLOADS
    assert app_module._get_upload_job("job-review")["status"] == "review_rejected"
    run = app_module._get_agent_run("run-job-review")
    assert run["status"] == "cancelled"
    assert run["termination_reason"] == "clinical_dag_rejected"


@pytest.mark.parametrize(
    "overrides,expected_status",
    [
        ({"doctor_final_decision": "maybe"}, 400),
        ({"reviewer": ""}, 400),
        ({"dag_id": "clinical:changed"}, 409),
        ({"available_modalities": ["ncct"]}, 409),
    ],
)
def test_review_rejects_invalid_or_changed_inputs(overrides, expected_status):
    dag, _payload, _staged = _stage_job()
    with app_module.app.test_client() as client:
        response = _review(client, "job-review", dag, **overrides)
    assert response.status_code == expected_status


def test_missing_job_and_lost_staged_payload_return_conflicts():
    dag, _payload, _staged = _stage_job()
    with app_module.app.test_client() as client:
        missing = _review(client, "unknown-job", dag)
        with app_module.UPLOAD_JOBS_LOCK:
            app_module.UPLOAD_JOB_PAYLOADS.pop("job-review", None)
        lost = _review(client, "job-review", dag)

    assert missing.status_code == 404
    assert lost.status_code == 409
    assert app_module._get_upload_job("job-review")["status"] == "awaiting_review"


def test_ctp_progress_callback_records_model_and_slice_progress(monkeypatch):
    updates = []
    monkeypatch.setattr(
        app_module,
        "_update_step",
        lambda job_id, key, status, message: updates.append(
            (job_id, key, status, message)
        ),
    )
    callback = app_module._make_ctp_progress_callback("job-ctp")

    callback(slice_number=2, total_slices=4, model_key="cbv", phase="model_running")
    callback(slice_number=2, total_slices=4, phase="slice_completed")

    assert updates[0][:3] == ("job-ctp", "ctp_generate", "running")
    assert "CBV" in updates[0][3]
    assert "切片 2/4" in updates[0][3]
    assert "切片 2/4 已完成" in updates[1][3]


def test_upload_step_statuses_follow_real_ncct_then_ctp_boundaries(monkeypatch):
    job_id = "job-status-order"
    modalities = ["ncct", "mcta", "vcta", "dcta"]
    app_module._create_upload_job(
        job_id,
        patient_id=1,
        file_id="case-status-order",
        modalities=modalities,
        clinical_dag=build_clinical_dag(modalities),
    )
    events = []
    monkeypatch.setattr(
        app_module,
        "_upload_log",
        lambda **entry: events.append(
            (entry.get("step"), entry.get("status"), entry.get("message"))
        ),
    )

    app_module._update_step(
        job_id,
        "three_class",
        "running",
        "正在执行 NCCT 三分类与 Grad-CAM",
    )
    status, _ = app_module._publish_three_class_step(
        job_id,
        {
            "display": "正常 1 | 脑出血 0 | 脑缺血 0",
            "counts": {"normal": 1, "hemo": 0, "infarct": 0},
            "gradcam": {"success": True, "error": ""},
        },
        {"status": "completed"},
    )
    assert status == "completed"
    assert app_module._start_ctp_generation_step(job_id) is True
    app_module._make_ctp_progress_callback(job_id)(
        slice_number=1,
        total_slices=2,
        model_key="cbf",
        phase="model_running",
    )
    app_module._update_step(
        job_id,
        "ctp_generate",
        "completed",
        "CTP 灌注图生成完成",
    )

    transitions = []
    for step, state, _ in events:
        item = (step, state)
        if not transitions or transitions[-1] != item:
            transitions.append(item)
    assert transitions == [
        ("three_class", "running"),
        ("three_class", "completed"),
        ("ctp_generate", "running"),
        ("ctp_generate", "completed"),
    ]


def test_terminal_ctp_status_cannot_regress_from_a_late_progress_callback(monkeypatch):
    job_id = "job-terminal-ctp"
    modalities = ["ncct", "mcta", "vcta", "dcta"]
    app_module._create_upload_job(
        job_id,
        patient_id=1,
        file_id="case-terminal-ctp",
        modalities=modalities,
        clinical_dag=build_clinical_dag(modalities),
    )
    app_module._update_step(job_id, "three_class", "completed", "三分类完成")
    assert app_module._start_ctp_generation_step(job_id) is True
    app_module._update_step(job_id, "ctp_generate", "completed", "CTP 完成")

    logged = []
    monkeypatch.setattr(
        app_module,
        "_upload_log",
        lambda **entry: logged.append((entry.get("step"), entry.get("status"))),
    )
    app_module._make_ctp_progress_callback(job_id)(
        slice_number=2,
        total_slices=2,
        model_key="tmax",
        phase="model_running",
    )

    job = app_module._get_upload_job(job_id)
    ctp_step = next(step for step in job["steps"] if step["key"] == "ctp_generate")
    assert ctp_step["status"] == "completed"
    assert ctp_step["message"] == "CTP 完成"
    assert logged == []


def test_ctp_cannot_start_before_ncct_reaches_completed():
    job_id = "job-ctp-before-ncct"
    modalities = ["ncct", "mcta", "vcta", "dcta"]
    app_module._create_upload_job(
        job_id,
        patient_id=1,
        file_id="case-ctp-before-ncct",
        modalities=modalities,
        clinical_dag=build_clinical_dag(modalities),
    )
    app_module._update_step(job_id, "three_class", "running", "NCCT 运行中")

    assert app_module._start_ctp_generation_step(job_id) is False
    job = app_module._get_upload_job(job_id)
    ctp_step = next(step for step in job["steps"] if step["key"] == "ctp_generate")
    assert ctp_step["status"] == "pending"
