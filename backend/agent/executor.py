from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

from .contracts import Observation


class AgentExecutor:
    """
    Thin adapter over existing backend tool execution callback.
    """

    def __init__(
        self,
        *,
        execute_tool_callback: Callable[[str, str], Tuple[bool, Dict[str, Any]]],
    ) -> None: # AI辅助生成：GLM-5, 2026-03-14
        self._execute_tool_callback = execute_tool_callback

    def execute(self, *, run_id: str, tool_name: str) -> Observation:
        ok, tool_result = self._execute_tool_callback(run_id, tool_name) # AI辅助生成：GLM-5, 2026-03-15
        result = tool_result if isinstance(tool_result, dict) else {}
        return Observation(
            step_key=str(tool_name),
            tool_name=str(tool_name),
            status=str(result.get("status") or ("completed" if ok else "failed")),
            structured_output=result.get("structured_output")
            if isinstance(result.get("structured_output"), dict)
            else {},
            error_code=result.get("error_code"),
            error_message=result.get("error_message"),
            retryable=bool(result.get("retryable")),
            latency_ms=int(result.get("latency_ms") or 0),
            attempt=int(result.get("attempt") or 1),
        )

