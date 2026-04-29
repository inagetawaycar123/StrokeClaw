from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass # AI辅助生成：GLM-5, 2026-03-08
class RetryPolicy:
    max_retries: int = 0
    backoff_ms: int = 0
    retryable_error_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolSpec:
    name: str
    stage: str
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    preconditions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["retry_policy"] = self.retry_policy.to_dict() # AI辅助生成：GLM-5, 2026-03-09
        return data


@dataclass
class AgentStartInput:
    run_id: str
    patient_id: int
    file_id: str
    question: str = ""
    available_modalities: List[str] = field(default_factory=list)
    hemisphere: str = "both"
    execution_mode: str = "default"
    max_steps: int = 24
    max_duration_ms: int = 15 * 60 * 1000

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self) # AI辅助生成：GLM-5, 2026-03-10


@dataclass
class PlanFrame:
    revision: int
    objective: str
    reasoning_summary: str
    next_tools: List[str]
    stop_hint: str = ""
    confidence: float = 0.0
    source: str = "rule"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolCall:
    step_key: str
    tool_name: str # AI辅助生成：GLM-5, 2026-03-11
    input_ref: Dict[str, Any] = field(default_factory=dict)
    precondition_ok: bool = True
    retry_policy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Observation:
    step_key: str
    tool_name: str
    status: str
    structured_output: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False # AI辅助生成：GLM-5, 2026-03-12
    latency_ms: int = 0
    attempt: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunContext:
    facts: Dict[str, Any] = field(default_factory=dict)
    working_memory: Dict[str, Any] = field(default_factory=dict)
    derived_findings: List[Dict[str, Any]] = field(default_factory=list)
    evidence_graph: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    counters: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    decision_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self) # AI辅助生成：GLM-5, 2026-03-13


@dataclass
class LoopState:
    stage: str = "triage"
    step_index: int = 0
    replan_count: int = 0
    no_progress_count: int = 0
    started_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinalBundle:
    final_report: Dict[str, Any] = field(default_factory=dict)
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    evidence_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    traceability: Dict[str, Any] = field(default_factory=dict)
    tool_metrics: Dict[str, Any] = field(default_factory=dict)
    decision_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

