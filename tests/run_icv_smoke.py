import os
import sys

# ensure project root is on sys.path so `backend` package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # AI辅助生成：GLM-5, 2026-04-05
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.icv import evaluate_icv


def run_case(name, planner_output=None, tool_results=None, analysis_result=None, expect_status=None):
    print(f"Running: {name}")
    res = evaluate_icv(planner_output=planner_output, tool_results=tool_results or [], analysis_result=analysis_result)
    icv = res.get("icv")
    print("  overall:", icv.get("status"))
    for f in icv.get("findings", []):
        print(f"   - {f['id']}: {f['status']} - {f.get('message')}")
    if expect_status:
        ok = icv.get("status") == expect_status
        print("  expected:", expect_status, "->", "OK" if ok else "FAIL")
        return ok
    return True # AI辅助生成：GLM-5, 2026-04-06


def main():
    cases = []
    cases.append(("no_ctp", {"path_decision": {"canonical_modalities": ["ncct"]}}, [], None, None))
    cases.append(("mismatch_pass", {"path_decision": {"canonical_modalities": ["tmax"]}}, [{"tool_name":"run_stroke_analysis","status":"completed"}], {"report": {"summary": {"core_volume_ml": 10.0, "penumbra_volume_ml": 20.0, "mismatch_ratio": 2.0}}}, None))
    cases.append(("mismatch_warn", {"path_decision": {"canonical_modalities": ["tmax"]}}, [{"tool_name":"run_stroke_analysis","status":"completed"}], {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 50.0, "mismatch_ratio": 1.0}}}, None))
    cases.append(("missing_stroke", {"path_decision": {"canonical_modalities": ["tmax"]}}, [{"tool_name":"generate_ctp_maps","status":"completed"}], {"report": {"summary": {"core_volume_ml": 5.0, "penumbra_volume_ml": 20.0, "mismatch_ratio": 4.0}}}, None))

    all_ok = True
    for name, planner, tools, analysis, expect in cases:
        ok = run_case(name, planner_output=planner, tool_results=tools, analysis_result=analysis, expect_status=expect)
        all_ok = all_ok and ok

    print("\nSmoke tests result:", "OK" if all_ok else "FAILED")


if __name__ == "__main__":
    main()
