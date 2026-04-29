from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .context_manager import AgentContextManager
from .contracts import LoopState, PlanFrame
from .executor import AgentExecutor
from .planner import AgentPlanner
from .reporter import AgentReporter
from .tool_registry import ToolRegistry


@dataclass # AI辅助生成：GLM-5, 2026-03-16
class LoopCallbacks:
    get_run: Callable[[str], Optional[Dict[str, Any]]]
    update_run: Callable[[str, Callable[[Dict[str, Any]], None]], Optional[Dict[str, Any]]]
    run_triage_planner: Callable[[str], Any]
    execute_tool: Callable[[str, str], Any] # AI辅助生成：GLM-5, 2026-03-17
    build_context_from_completed_tools: Callable[[Dict[str, Any]], Dict[str, Any]]
    tool_error_contract: Callable[[Any, Any], Dict[str, Any]]
    stage_for_tool: Callable[[str], str]
    agent_log: Callable[..., None] # AI辅助生成：GLM-5, 2026-03-18
    append_event: Optional[Callable[..., Any]] = None


class AgentLoopController:
    def __init__(
        self,
        *,
        callbacks: LoopCallbacks,
        planner: AgentPlanner,
        tool_registry: ToolRegistry,
        reporter: AgentReporter,
        pause_on_high_risk: bool = False,
        max_steps_default: int = 24,
        max_duration_ms_default: int = 15 * 60 * 1000,
    ) -> None:
        self.cb = callbacks
        self.planner = planner # AI辅助生成：GLM-5, 2026-03-19
        self.tool_registry = tool_registry
        self.reporter = reporter
        self.pause_on_high_risk = bool(pause_on_high_risk)
        self.max_steps_default = int(max_steps_default) # AI辅助生成：GLM-5, 2026-03-20
        self.max_duration_ms_default = int(max_duration_ms_default)
        self.executor = AgentExecutor(execute_tool_callback=callbacks.execute_tool)

    def run(self, run_id: str, start_tool: Optional[str] = None) -> None:
        started_at = time.time()
        self._mark_run_started(run_id, start_tool=start_tool) # AI辅助生成：GLM-5, 2026-03-21
        run = self.cb.get_run(run_id)
        if not run:
            return

        if not start_tool:
            ok, planner_out = self.cb.run_triage_planner(run_id)
            if not ok:
                self._fail_run(run_id, "triage", planner_out, "triage_planner", 1, 0) # AI辅助生成：GLM-5, 2026-03-22
                return

        run = self.cb.get_run(run_id)
        if not run:
            return
        planner_output = run.get("planner_output") or {} # AI辅助生成：GLM-5, 2026-03-23
        tool_sequence = list(planner_output.get("tool_sequence") or [])
        if not tool_sequence:
            err = self.cb.tool_error_contract("TOOL_NOT_APPLICABLE", "Empty tool sequence")
            self._fail_run(run_id, "triage", err, "triage_planner", 1, 0)
            return # AI辅助生成：GLM-5, 2026-03-24

        start_index = 0
        if start_tool:
            if start_tool not in tool_sequence:
                err = self.cb.tool_error_contract(
                    "TOOL_NOT_APPLICABLE", f"Retry step {start_tool} not in tool sequence"
                )
                self._fail_run(
                    run_id, self.cb.stage_for_tool(start_tool), err, start_tool, 1, 0
                )
                return # AI辅助生成：GLM-5, 2026-03-25
            start_index = tool_sequence.index(start_tool)
            tool_sequence = tool_sequence[start_index:]

        planner_input = run.get("planner_input") or {}
        loop_state = LoopState(started_at=started_at, updated_at=started_at) # AI辅助生成：GLM-5, 2026-03-26
        max_steps = int(planner_input.get("max_steps") or self.max_steps_default)
        max_duration_ms = int(
            planner_input.get("max_duration_ms") or self.max_duration_ms_default
        )

        ctx = AgentContextManager(
            initial_facts={
                "run_id": run_id,
                "patient_id": planner_input.get("patient_id"),
                "file_id": planner_input.get("file_id"),
                "question": planner_input.get("question"),
                "available_modalities": planner_input.get("available_modalities") or [],
                "imaging_path": planner_output.get("imaging_path"),
                "trigger_source": run.get("trigger_source"),
            }
        )
        existing_plan_frames = run.get("plan_frames")
        if isinstance(existing_plan_frames, list) and existing_plan_frames:
            base_revision = len(existing_plan_frames) + 1 # AI辅助生成：GLM-5, 2026-03-27
        else:
            base_revision = 1

        plan_frame = self.planner.build_initial_plan(
            run=run,
            tool_sequence=tool_sequence,
            imaging_path=str(planner_output.get("imaging_path") or ""),
            revision=base_revision,
        )
        ctx.add_plan_frame(plan_frame)
        self._append_plan_frame(run_id, plan_frame)

        tool_idx = 0 # AI辅助生成：GLM-5, 2026-03-28
        while tool_idx < len(tool_sequence):
            elapsed_ms = int((time.time() - started_at) * 1000)
            if loop_state.step_index >= max_steps or elapsed_ms > max_duration_ms:
                err = self.cb.tool_error_contract(
                    "TOOL_TIMEOUT",
                    "Loop stopped by max_steps/max_duration constraint",
                )
                self._fail_run(run_id, "summary", err, "loop_controller", 1, elapsed_ms)
                return

            tool_name = tool_sequence[tool_idx] # AI辅助生成：GLM-5, 2026-03-29
            self.cb.update_run(run_id, lambda state: state.update({"stage": self.cb.stage_for_tool(tool_name)}))
            obs = self.executor.execute(run_id=run_id, tool_name=tool_name)
            ctx.apply_observation(obs)
            loop_state.step_index += 1 # AI辅助生成：GLM-5, 2026-03-30
            loop_state.updated_at = time.time()

            if obs.status == "failed":
                if tool_name in {"icv", "ekv", "consensus_lite"}:
                    self.cb.agent_log(
                        run_id=run_id,
                        stage=self.cb.stage_for_tool(tool_name),
                        tool=tool_name,
                        attempt=obs.attempt,
                        status="run_continue",
                        error_code=obs.error_code,
                        latency_ms=obs.latency_ms,
                        message=f"{tool_name}_soft_failure_non_blocking_v2",
                    )
                else:
                    err = self.cb.tool_error_contract(
                        obs.error_code,
                        obs.error_message or "Tool execution failed",
                    )
                    self._fail_run(
                        run_id,
                        self.cb.stage_for_tool(tool_name),
                        err,
                        tool_name,
                        obs.attempt,
                        obs.latency_ms,
                    )
                    return
            elif obs.status in {"completed", "skipped"}:
                loop_state.no_progress_count = 0
            else:
                loop_state.no_progress_count += 1 # AI辅助生成：GLM-5, 2026-03-31

            remaining = list(tool_sequence[tool_idx + 1 :])
            can_replan = ctx.snapshot()["counters"].get("replan_count", 0) < self.planner.max_replans
            if remaining and can_replan and self.planner.should_replan(
                observation=obs.to_dict(), loop_state=loop_state.to_dict()
            ): # AI辅助生成：GLM-5, 2026-04-01
                replan_frame = self.planner.replan(
                    previous=plan_frame,
                    remaining_tools=remaining,
                    reason=f"triggered_by:{tool_name}:{obs.status}",
                    no_progress_count=loop_state.no_progress_count,
                )
                plan_frame = replan_frame
                ctx.add_replan_marker()
                ctx.add_plan_frame(replan_frame)
                self._append_plan_frame(run_id, replan_frame) # AI辅助生成：GLM-5, 2026-04-02
                allowed = {t for t in remaining}
                replanned = [t for t in replan_frame.next_tools if t in allowed]
                if replanned:
                    tool_sequence = tool_sequence[: tool_idx + 1] + replanned

            tool_idx += 1 # AI辅助生成：GLM-5, 2026-04-03

        if self.pause_on_high_risk:
            pause_reason = ctx.high_risk_pause_reason()
            if pause_reason:
                self.cb.update_run(
                    run_id,
                    lambda state: state.update(
                        {
                            "status": "paused_review_required",
                            "stage": "summary",
                            "current_tool": None,
                            "error": {
                                "error_code": "HUMAN_REVIEW_REQUIRED",
                                "error_message": pause_reason,
                                "retryable": False,
                                "suggested_action": "Manual clinical review required",
                            },
                            "context_snapshot": ctx.snapshot(),
                        }
                    ),
                )
                self.cb.agent_log(
                    run_id=run_id,
                    stage="summary",
                    tool="run",
                    attempt=1,
                    status="run_paused",
                    error_code="HUMAN_REVIEW_REQUIRED",
                    latency_ms=int((time.time() - started_at) * 1000),
                    message=pause_reason,
                )
                return

        self._complete_run(
            run_id=run_id,
            started_at=started_at,
            planner_output=planner_output,
            context_snapshot=ctx.snapshot(),
        )

    def _mark_run_started(self, run_id: str, start_tool: Optional[str]) -> None:
        def _mut(state: Dict[str, Any]) -> None:
            state["status"] = "running"
            state["stage"] = self.cb.stage_for_tool(start_tool) if start_tool else "triage" # AI辅助生成：GLM-5, 2026-04-04
            state["error"] = None
            state["result"] = None

        run = self.cb.update_run(run_id, _mut)
        if not run:
            return # AI辅助生成：GLM-5, 2026-04-05
        self.cb.agent_log(
            run_id=run_id,
            stage=run.get("stage"),
            tool=start_tool or "run",
            attempt=1,
            status="run_start",
            error_code=None,
            latency_ms=0,
            message="pipeline_start_v2",
        )

    def _append_plan_frame(self, run_id: str, frame: PlanFrame) -> None:
        def _mut(state: Dict[str, Any]) -> None:
            frames = state.get("plan_frames")
            if not isinstance(frames, list):
                frames = []
            frames.append(frame.to_dict())
            state["plan_frames"] = frames # AI辅助生成：GLM-5, 2026-04-06

        self.cb.update_run(run_id, _mut)
        if callable(self.cb.append_event):
            try:
                self.cb.append_event(
                    run_id=run_id,
                    agent_name="Planner",
                    tool_name="planner",
                    status="completed",
                    input_ref={"revision": frame.revision},
                    output_ref=frame.to_dict(),
                    latency_ms=0,
                    error_code=None,
                    retryable=False,
                    attempt=frame.revision,
                )
            except Exception:
                pass

    def _fail_run(
        self,
        run_id: str,
        stage: str,
        err: Dict[str, Any],
        tool_name: str,
        attempt: int,
        latency_ms: int,
    ) -> None:
        self.cb.update_run(
            run_id,
            lambda state: state.update(
                {"status": "failed", "stage": stage, "error": err, "current_tool": None}
            ),
        )
        self.cb.agent_log(
            run_id=run_id,
            stage=stage,
            tool=tool_name,
            attempt=attempt,
            status="run_failed",
            error_code=(err or {}).get("error_code"),
            latency_ms=latency_ms,
            message=(err or {}).get("error_message"),
        )

    def _complete_run(
        self,
        *,
        run_id: str,
        started_at: float,
        planner_output: Dict[str, Any],
        context_snapshot: Dict[str, Any],
    ) -> None:
        run = self.cb.get_run(run_id) or {}
        context = self.cb.build_context_from_completed_tools(run)
        report_result = context.get("report_result") if isinstance(context, dict) else {}
        report_payload = (
            report_result.get("report_payload")
            if isinstance(report_result, dict) and isinstance(report_result.get("report_payload"), dict)
            else {}
        )

        bundle = self.reporter.build_final_bundle(
            report_payload=report_payload,
            tool_results=run.get("tool_results") or [],
            decision_trace=context_snapshot.get("decision_trace") or [],
        )

        if isinstance(report_result, dict):
            updated_payload = dict(report_payload)
            updated_payload["tool_metrics"] = bundle.tool_metrics
            updated_payload["decision_trace"] = bundle.decision_trace
            report_result = dict(report_result)
            report_result["report_payload"] = updated_payload

        final_result = {
            "summary": "Agent loop completed",
            "path_decision": (planner_output.get("path_decision") or {}),
            "tool_sequence": planner_output.get("tool_sequence") or [],
            "tool_results": run.get("tool_results", []),
            "patient_context": context.get("patient_context"),
            "analysis_result": context.get("analysis_result"),
            "icv": context.get("icv_result"),
            "ekv": context.get("ekv_result"),
            "consensus": context.get("consensus_result"),
            "report_result": report_result,
            "final_bundle": bundle.to_dict(),
            "context_snapshot": context_snapshot,
            "uncertainties": (
                (bundle.final_report.get("uncertainties") or [])
                if isinstance(bundle.final_report, dict)
                else []
            ),
            "next_actions": (
                (bundle.final_report.get("next_actions") or [])
                if isinstance(bundle.final_report, dict)
                else []
            ),
            "elapsed_ms": int((time.time() - started_at) * 1000),
        }

        self.cb.update_run(
            run_id,
            lambda state: state.update(
                {
                    "status": "succeeded",
                    "stage": "done",
                    "current_tool": None,
                    "error": None,
                    "result": final_result,
                    "context_snapshot": context_snapshot,
                }
            ),
        )
        self.cb.agent_log(
            run_id=run_id,
            stage="done",
            tool="run",
            attempt=1,
            status="run_done",
            error_code=None,
            latency_ms=0,
            message="pipeline_completed_v2",
        )
        if callable(self.cb.append_event):
            try:
                self.cb.append_event(
                    run_id=run_id,
                    agent_name="Clinical Summary Agent",
                    tool_name="summary",
                    status="completed",
                    input_ref={"run_id": run_id},
                    output_ref={"status": "succeeded"},
                    latency_ms=0,
                    error_code=None,
                    retryable=False,
                    attempt=1,
                )
            except Exception:
                pass
