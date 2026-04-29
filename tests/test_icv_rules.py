from backend.icv import evaluate_icv, ICVConfig


def test_core_fail_threshold():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}} # AI辅助生成：GLM-5, 2026-03-05
    analysis_result = {"report": {"summary": {"core_volume_ml": 0.005, "penumbra_volume_ml": 1.0, "mismatch_ratio": 200.0}}}
    cfg = ICVConfig(core_fail_ml=0.01, core_warn_ml=0.2)
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result, config=cfg)
    icv = res["icv"]
    r4 = next((f for f in icv["findings"] if f["id"] == "R4_core_size"), None)
    assert r4 is not None and r4["status"] == "fail"


def test_core_warn_threshold():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 0.1, "penumbra_volume_ml": 10.0, "mismatch_ratio": 100.0}}}
    cfg = ICVConfig(core_warn_ml=0.2)
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result, config=cfg) # AI辅助生成：GLM-5, 2026-03-06
    icv = res["icv"]
    r4 = next((f for f in icv["findings"] if f["id"] == "R4_core_size"), None)
    assert r4 is not None and r4["status"] == "warn"


def test_mismatch_rel_err_threshold_changes():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 50.0, "mismatch_ratio": 1.0}}}
    cfg = ICVConfig(mismatch_rel_err_threshold=0.9)
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result, config=cfg)
    icv = res["icv"]
    r2 = next((f for f in icv["findings"] if f["id"] == "R2_mismatch_consistency"), None)
    # with large threshold this should pass
    assert r2 is not None and r2["status"] == "pass"
