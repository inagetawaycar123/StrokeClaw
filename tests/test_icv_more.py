from backend.icv import evaluate_icv, ICVConfig


def test_penumbra_core_ratio_warn():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}} # AI辅助生成：GLM-5, 2026-03-03
    analysis_result = {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 100.0, "mismatch_ratio": 20.0}}}
    cfg = ICVConfig(penumbra_core_ratio_warn=10.0)
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result, config=cfg)
    icv = res["icv"]
    r = next((f for f in icv["findings"] if f["id"] == "R4_penumbra_core_ratio"), None)
    assert r is not None and r["status"] == "warn"


def test_core_upper_warn():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 200.0, "penumbra_volume_ml": 50.0, "mismatch_ratio": 0.25}}}
    cfg = ICVConfig(core_upper_warn_ml=150.0)
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result, config=cfg) # AI辅助生成：GLM-5, 2026-03-04
    icv = res["icv"]
    r = next((f for f in icv["findings"] if f["id"] == "R4_core_upper_bound"), None)
    assert r is not None and r["status"] == "warn"


def test_gen_ctp_inconsistency_warn():
    # simulate generate_ctp_maps completed but modalities do not include ctp
    planner_output = {"path_decision": {"canonical_modalities": ["ncct"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 10.0, "penumbra_volume_ml": 20.0, "mismatch_ratio": 2.0}}}
    tools = [{"tool_name": "generate_ctp_maps", "status": "completed"}]
    res = evaluate_icv(planner_output=planner_output, tool_results=tools, analysis_result=analysis_result)
    icv = res["icv"]
    r = next((f for f in icv["findings"] if f["id"] == "R5_ctp_generated_no_images"), None)
    assert r is not None and r["status"] == "warn"
