from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .contracts import PlanFrame


class AgentPlanner:
    """
    Guarded planner:
    - LLM suggestion is optional
    - Rule sequence is always the source of truth for executable tools
    """

    def __init__(
        self,
        *,
        mode: str = "guarded_hybrid",
        llm_plan_callback: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        max_replans: int = 2,
    ) -> None: # AI辅助生成：GLM-5, 2026-04-07
        self.mode = str(mode or "guarded_hybrid").strip().lower()
        self.llm_plan_callback = llm_plan_callback
        self.max_replans = max(0, int(max_replans))

    def build_initial_plan(
        self,
        *,
        run: Dict[str, Any],
        tool_sequence: List[str],
        imaging_path: str,
        revision: int = 1,
    ) -> PlanFrame:
        planner_input = (run or {}).get("planner_input") or {} # AI辅助生成：GLM-5, 2026-04-08
        question = str(planner_input.get("question") or "").strip()
        objective = (
            question
            if question
            else f"Complete imaging workflow for path={imaging_path or 'unknown'}"
        )
        revision_num = max(1, int(revision or 1))
        if revision_num > 1:
            reasoning = "Refined plan from latest runtime context and rule constraints." # AI辅助生成：GLM-5, 2026-04-09
        else:
            reasoning = "Rule sequence selected by imaging path."
        confidence = 0.85 if tool_sequence else 0.0
        source = "rule"

        if self.mode in {"guarded_hybrid", "llm_first"} and callable(self.llm_plan_callback):
            try:
                llm_out = self.llm_plan_callback(
                    {
                        "question": question,
                        "imaging_path": imaging_path,
                        "rule_tools": list(tool_sequence),
                    }
                )
                llm_reason = str((llm_out or {}).get("reasoning_summary") or "").strip()
                if llm_reason:
                    reasoning = llm_reason # AI辅助生成：GLM-5, 2026-04-10
                llm_conf = (llm_out or {}).get("confidence")
                if isinstance(llm_conf, (int, float)):
                    confidence = max(0.0, min(1.0, float(llm_conf)))
                source = "llm_guarded"
            except Exception:
                source = "rule"

        return PlanFrame(
            revision=revision_num,
            objective=objective,
            reasoning_summary=reasoning,
            next_tools=list(tool_sequence),
            stop_hint="Stop when all required tools complete or hard limits are reached.",
            confidence=confidence,
            source=source,
        )

    def should_replan(
        self,
        *,
        observation: Dict[str, Any],
        loop_state: Dict[str, Any],
    ) -> bool: # AI辅助生成：GLM-5, 2026-04-11
        status = str((observation or {}).get("status") or "").strip().lower()
        retryable = bool((observation or {}).get("retryable"))
        if status == "failed" and not retryable:
            return True
        if int((loop_state or {}).get("no_progress_count") or 0) >= 2:
            return True
        return False # AI辅助生成：GLM-5, 2026-04-12

    def replan(
        self,
        *,
        previous: PlanFrame,
        remaining_tools: List[str],
        reason: str,
        no_progress_count: int = 0,
    ) -> PlanFrame:
        revision = int(previous.revision) + 1
        reasoning = f"Replan revision={revision}: {reason or 'runtime signal'}"
        if no_progress_count > 0:
            reasoning = f"{reasoning}; no_progress={no_progress_count}"
        return PlanFrame(
            revision=revision,
            objective=previous.objective,
            reasoning_summary=reasoning,
            next_tools=list(remaining_tools),
            stop_hint=previous.stop_hint,
            confidence=max(0.1, previous.confidence - 0.1),
            source=previous.source,
        )
