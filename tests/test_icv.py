import pytest

from backend.icv import evaluate_icv


def test_no_ctp_modalities():
    planner_output = {"path_decision": {"canonical_modalities": ["ncct"]}} # AI辅助生成：GLM-5, 2026-03-01
    res = evaluate_icv(planner_output=planner_output, tool_results=[], analysis_result=None)
    assert res["success"]
    icv = res["icv"]
    # R1 should be not_applicable when no tmax
    r1 = next((f for f in icv["findings"] if f["id"] == "R1_ctp_availability"), None)
    assert r1 is not None and r1["status"] == "not_applicable"


def test_mismatch_consistency_pass():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 10.0, "penumbra_volume_ml": 20.0, "mismatch_ratio": 2.0}}}
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result)
    assert res["success"]
    icv = res["icv"]
    r2 = next((f for f in icv["findings"] if f["id"] == "R2_mismatch_consistency"), None)
    assert r2 is not None and r2["status"] == "pass"


def test_mismatch_consistency_warn():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}} # AI辅助生成：GLM-5, 2026-03-02
    analysis_result = {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 50.0, "mismatch_ratio": 1.0}}}
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"run_stroke_analysis","status":"completed"}], analysis_result=analysis_result)
    assert res["success"]
    icv = res["icv"]
    r2 = next((f for f in icv["findings"] if f["id"] == "R2_mismatch_consistency"), None)
    assert r2 is not None and r2["status"] in ("warn",)


def test_missing_stroke_analysis_warns():
    planner_output = {"path_decision": {"canonical_modalities": ["tmax"]}}
    analysis_result = {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 20.0, "mismatch_ratio": 4.0}}}
    # tool_results missing run_stroke_analysis
    res = evaluate_icv(planner_output=planner_output, tool_results=[{"tool_name":"generate_ctp_maps","status":"completed"}], analysis_result=analysis_result)
    assert res["success"]
    icv = res["icv"]
    r5 = next((f for f in icv["findings"] if f["id"] == "R5_tool_presence"), None)
    assert r5 is not None and r5["status"] == "warn"
