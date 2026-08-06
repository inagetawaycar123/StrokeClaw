from backend import app as app_module


def _gated_result():
    gate = {
        "blocked": True,
        "reason_code": "NCCT_SUSPECTED_HEMORRHAGE",
        "reason": "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析",
        "requires_clinician_review": True,
    }
    result = {
        "status": "completed",
        "three_class_label": "hemo",
        "three_class_label_cn": "脑出血",
        "three_class_confidence": 0.81,
        "class_counts": {"normal": 0, "hemo": 1, "infarct": 0},
        "total_slices": 1,
        "safety_gate": gate,
    }
    return {
        "success": True,
        "file_id": "case-gated",
        "rgb_files": [],
        "three_class_summary": {
            "display": "正常 0 | 脑出血 1 | 脑缺血 0",
            "counts": result["class_counts"],
            **result,
        },
        "three_class_result": result,
        "safety_gate": gate,
        "analysis_blocked": True,
    }


def test_agent_tools_skip_models_when_ncct_gate_is_blocked(monkeypatch):
    run = {
        "planner_input": {
            "patient_id": 1,
            "file_id": "case-gated",
            "hemisphere": "both",
            "three_class_result": _gated_result()["three_class_result"],
        }
    }

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("downstream model must not run")

    monkeypatch.setattr(app_module, "_collect_case_upload_files", must_not_run)
    monkeypatch.setattr(app_module, "_run_vessel_occlusion_on_file", must_not_run)
    monkeypatch.setattr(app_module, "analyze_stroke_case", must_not_run)

    ctp_ok, ctp_output, _ = app_module._tool_generate_ctp_maps(run)
    vessel_ok, vessel_output, _ = app_module._tool_vessel_occlusion(run)
    stroke_ok, stroke_output, _ = app_module._tool_run_stroke_analysis(run)

    assert ctp_ok and ctp_output["status"] == "skipped"
    assert vessel_ok and vessel_output["status"] == "skipped"
    assert stroke_ok and stroke_output["status"] == "skipped"


def test_upload_job_skips_all_downstream_imaging_steps(monkeypatch):
    steps = {}

    monkeypatch.setattr(
        app_module,
        "_invoke_internal_upload",
        lambda _payload: (True, "ok", _gated_result()),
    )
    monkeypatch.setattr(
        app_module,
        "_update_step",
        lambda _job_id, key, status, message: steps.update(
            {key: (status, message)}
        ),
    )
    monkeypatch.setattr(app_module, "_set_job_status", lambda *_a, **_k: None)
    monkeypatch.setattr(app_module, "_add_job_warning", lambda *_a, **_k: None)
    monkeypatch.setattr(app_module, "_update_upload_job", lambda *_a, **_k: None)
    monkeypatch.setattr(app_module, "_upload_log", lambda **_k: None)
    monkeypatch.setattr(
        app_module, "_start_deferred_upload_agent_run", lambda **_k: None
    )
    monkeypatch.setattr(
        app_module, "_attach_three_class_to_agent_run", lambda *_a: True
    )
    monkeypatch.setattr(
        app_module, "_attach_vessel_result_to_agent_run", lambda *_a: True
    )
    monkeypatch.setattr(
        app_module, "_persist_three_class_result_to_imaging", lambda *_a: True
    )
    monkeypatch.setattr(
        app_module, "_persist_vessel_result_to_imaging", lambda *_a: True
    )
    monkeypatch.setattr(
        app_module, "_persist_quality_control_to_imaging", lambda *_a: True
    )

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("downstream imaging model must not run")

    monkeypatch.setattr(app_module, "_run_vessel_occlusion_on_file", must_not_run)
    monkeypatch.setattr(app_module, "_generate_pseudocolor_for_result", must_not_run)

    app_module._run_upload_processing_job(
        "job-gated",
        {
            "patient_id": 1,
            "file_id": "case-gated",
            "modalities": ["ncct", "mcta", "vcta", "dcta"],
            "agent_run_id": "run-gated",
            "quality_control_result": {
                "qc_status": "passed",
                "qc_score": 1.0,
                "qc_method": "rule_based_nifti_qc",
                "qc_fingerprint": "synthetic-passed-qc",
                "findings": [],
                "review_override": None,
            },
        },
    )

    assert steps["ctp_generate"][0] == "skipped"
    assert steps["vessel_occlusion"][0] == "skipped"
    assert steps["stroke_analysis"][0] == "skipped"
    assert steps["pseudocolor"][0] == "skipped"
