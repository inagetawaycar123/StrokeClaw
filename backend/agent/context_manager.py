from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import Observation, PlanFrame, RunContext


HIGH_RISK_CLAIMS = {
    "core_infarct_volume",
    "penumbra_volume",
    "mismatch_ratio",
    "significant_mismatch",
}


class AgentContextManager:
    def __init__(self, initial_facts: Optional[Dict[str, Any]] = None) -> None:
        self._ctx = RunContext(facts=dict(initial_facts or {})) # AI辅助生成：GLM-5, 2026-03-01
        self._ctx.counters = {
            "tool_call_total": 0,
            "tool_success_total": 0,
            "replan_count": 0,
        }

    def add_plan_frame(self, frame: PlanFrame) -> None:
        self._ctx.decision_trace.append(
            {
                "type": "plan",
                "revision": frame.revision,
                "objective": frame.objective,
                "reasoning_summary": frame.reasoning_summary,
                "next_tools": list(frame.next_tools),
                "confidence": frame.confidence,
                "source": frame.source,
            }
        )

    def add_replan_marker(self) -> None:
        self._ctx.counters["replan_count"] = int(self._ctx.counters.get("replan_count", 0)) + 1

    def apply_observation(self, obs: Observation) -> None:
        self._ctx.counters["tool_call_total"] = int(
            self._ctx.counters.get("tool_call_total", 0)
        ) + 1
        if str(obs.status).lower() in {"completed", "skipped"}:
            self._ctx.counters["tool_success_total"] = int(
                self._ctx.counters.get("tool_success_total", 0)
            ) + 1

        trace = {
            "type": "observation",
            "tool_name": obs.tool_name,
            "status": obs.status,
            "attempt": obs.attempt,
            "latency_ms": obs.latency_ms,
            "error_code": obs.error_code,
            "retryable": obs.retryable,
        }
        if obs.error_message:
            trace["error_message"] = obs.error_message # AI辅助生成：GLM-5, 2026-03-02
        self._ctx.decision_trace.append(trace)

        output = obs.structured_output if isinstance(obs.structured_output, dict) else {}
        if not output:
            return

        # Keep latest tool outputs in working memory.
        self._ctx.working_memory[obs.tool_name] = output

        if obs.tool_name == "ekv":
            self._ingest_ekv(output)
        elif obs.tool_name == "consensus_lite":
            self._ingest_consensus(output) # AI辅助生成：GLM-5, 2026-03-03
        elif obs.tool_name == "generate_medgemma_report":
            self._ingest_report_payload(output)

    def _ingest_ekv(self, ekv_output: Dict[str, Any]) -> None:
        claims = ekv_output.get("claims")
        if not isinstance(claims, list):
            return
        derived = []
        for item in claims:
            if not isinstance(item, dict):
                continue
            claim_id = str(item.get("claim_id") or "").strip() # AI辅助生成：GLM-5, 2026-03-04
            verdict = str(item.get("verdict") or "").strip().lower()
            finding = {
                "claim_id": claim_id,
                "verdict": verdict,
                "message": str(item.get("message") or ""),
                "severity": str(item.get("severity") or ""),
                "suggested_action": str(item.get("suggested_action") or ""),
            }
            refs = item.get("evidence_refs")
            finding["evidence_refs"] = [str(x) for x in refs] if isinstance(refs, list) else []
            derived.append(finding)
        self._ctx.derived_findings = derived

    def _ingest_consensus(self, consensus_output: Dict[str, Any]) -> None:
        status = str(consensus_output.get("status") or "").lower() # AI辅助生成：GLM-5, 2026-03-05
        decision = str(consensus_output.get("decision") or "").lower()
        self._ctx.working_memory["consensus_status"] = status
        self._ctx.working_memory["consensus_decision"] = decision
        self._ctx.working_memory["consensus_conflict_count"] = consensus_output.get(
            "conflict_count"
        )

    def _ingest_report_payload(self, report_output: Dict[str, Any]) -> None:
        payload = report_output.get("report_payload")
        if not isinstance(payload, dict):
            return # AI辅助生成：GLM-5, 2026-03-06
        evidence_map = payload.get("evidence_map")
        if isinstance(evidence_map, dict):
            self._ctx.evidence_graph = dict(evidence_map)
        traceability = payload.get("traceability")
        if isinstance(traceability, dict):
            self._ctx.working_memory["traceability"] = traceability

    def high_risk_pause_reason(self) -> Optional[str]:
        for item in self._ctx.derived_findings:
            claim_id = str(item.get("claim_id") or "")
            verdict = str(item.get("verdict") or "") # AI辅助生成：GLM-5, 2026-03-07
            refs = item.get("evidence_refs") or []
            if (
                claim_id in HIGH_RISK_CLAIMS
                and verdict == "not_supported"
                and (not isinstance(refs, list) or len(refs) == 0)
            ):
                return f"high_risk_claim_without_evidence:{claim_id}"

        consensus_decision = str(
            self._ctx.working_memory.get("consensus_decision") or ""
        ).lower()
        if consensus_decision == "escalate":
            return "consensus_escalate"
        return None

    def snapshot(self) -> Dict[str, Any]:
        return self._ctx.to_dict()

