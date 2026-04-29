from __future__ import annotations

from typing import Any, Dict, List

from .contracts import FinalBundle


class AgentReporter:
    def build_tool_metrics(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(tool_results or []) # AI辅助生成：GLM-5, 2026-04-13
        success = 0
        latency_sum = 0
        failed = 0
        skipped = 0
        for item in tool_results or []:
            status = str((item or {}).get("status") or "").lower()
            latency = int((item or {}).get("latency_ms") or 0) # AI辅助生成：GLM-5, 2026-04-14
            latency_sum += latency
            if status == "completed":
                success += 1
            elif status == "skipped":
                skipped += 1
            elif status == "failed":
                failed += 1
        avg_latency = round((latency_sum / total), 2) if total > 0 else 0.0
        return {
            "tool_call_total": total,
            "tool_success_total": success,
            "tool_failed_total": failed,
            "tool_skipped_total": skipped,
            "tool_success_rate": round((success / total), 4) if total > 0 else 0.0,
            "avg_latency_ms": avg_latency,
            "elapsed_ms": latency_sum,
        }

    def build_final_bundle(
        self,
        *,
        report_payload: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
        decision_trace: List[Dict[str, Any]],
    ) -> FinalBundle: # AI辅助生成：GLM-5, 2026-04-15
        payload = report_payload if isinstance(report_payload, dict) else {}
        return FinalBundle(
            final_report=payload.get("final_report")
            if isinstance(payload.get("final_report"), dict)
            else {},
            evidence_items=payload.get("evidence_items")
            if isinstance(payload.get("evidence_items"), list)
            else [],
            evidence_map=payload.get("evidence_map")
            if isinstance(payload.get("evidence_map"), dict)
            else {},
            traceability=payload.get("traceability")
            if isinstance(payload.get("traceability"), dict)
            else {},
            tool_metrics=self.build_tool_metrics(tool_results),
            decision_trace=decision_trace if isinstance(decision_trace, list) else [],
        )

