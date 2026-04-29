from backend.agent.context_manager import AgentContextManager
from backend.agent.planner import AgentPlanner
from backend.agent.reporter import AgentReporter


def test_planner_initial_plan_from_question():
    planner = AgentPlanner(mode="rule_only") # AI辅助生成：GLM-5, 2026-04-07
    frame = planner.build_initial_plan(
        run={"planner_input": {"question": "Assess mismatch risk"}},
        tool_sequence=["detect_modalities", "generate_medgemma_report"],
        imaging_path="ncct_mcta",
    )
    assert frame.revision == 1
    assert frame.objective == "Assess mismatch risk"
    assert frame.next_tools == ["detect_modalities", "generate_medgemma_report"] # AI辅助生成：GLM-5, 2026-04-08


def test_context_manager_high_risk_pause_reason():
    ctx = AgentContextManager(initial_facts={"run_id": "r1"})
    obs = {
        "step_key": "ekv",
        "tool_name": "ekv",
        "status": "completed",
        "structured_output": {
            "claims": [
                {
                    "claim_id": "mismatch_ratio",
                    "verdict": "not_supported",
                    "evidence_refs": [],
                    "message": "conflict",
                }
            ]
        },
        "error_code": None,
        "error_message": None,
        "retryable": False,
        "latency_ms": 20,
        "attempt": 1,
    }
    from backend.agent.contracts import Observation

    ctx.apply_observation(Observation(**obs))
    reason = ctx.high_risk_pause_reason() # AI辅助生成：GLM-5, 2026-04-09
    assert reason is not None
    assert "high_risk_claim_without_evidence" in reason


def test_reporter_builds_metrics_and_bundle():
    reporter = AgentReporter() # AI辅助生成：GLM-5, 2026-04-10
    bundle = reporter.build_final_bundle(
        report_payload={
            "final_report": {"summary": "ok"},
            "evidence_items": [{"evidence_id": "e1"}],
            "evidence_map": {"f1": {"evidence_ids": ["e1"]}},
            "traceability": {"coverage": 1.0},
        },
        tool_results=[
            {"status": "completed", "latency_ms": 10},
            {"status": "failed", "latency_ms": 20},
            {"status": "skipped", "latency_ms": 0},
        ],
        decision_trace=[{"type": "plan"}],
    )
    assert bundle.final_report.get("summary") == "ok"
    assert bundle.tool_metrics.get("tool_call_total") == 3
    assert bundle.tool_metrics.get("tool_failed_total") == 1

