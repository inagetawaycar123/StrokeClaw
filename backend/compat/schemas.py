from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


@dataclass
class SkillRegistryItem:
    skill_id: str
    skill_name: str
    skill_type: str
    owner_agent: str
    clinical_task: str
    required_input: List[str]
    main_output: List[str]
    confidence_method: str
    confidence_threshold: Optional[float]
    failure_strategy: str
    version: str
    status: str
    doctor_review_required: bool

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class SkillInvocationView:
    invocation_id: str
    skill_id: str
    agent_session_id: str
    case_id: str
    input_payload: JsonDict = field(default_factory=dict)
    output_payload: JsonDict = field(default_factory=dict)
    status: str = "unknown"
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    evidence_used: List[Any] = field(default_factory=list)
    confidence: Optional[float] = None
    created_at: Optional[str] = None

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class CockpitNodeView:
    node_id: str
    node_name: str
    node_layer: str
    assigned_agent: str
    called_skill_id: str
    node_status: str
    runtime_ms: Optional[int] = None
    confidence_score: Optional[float] = None
    failure_reason: Optional[str] = None
    fallback_strategy: Optional[str] = None
    evidence_ids: List[Any] = field(default_factory=list)
    review_status: str = "not_required"
    risk_level: str = "unknown"
    input_summary: str = ""
    output_summary: str = ""

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class CockpitTaskView:
    task_id: str
    bundle_id: str
    case_id: str
    agent_session_id: str
    task_status: str
    node_count: int
    completed_node_count: int
    failed_node_count: int
    review_required: bool
    nodes: List[JsonDict] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class ClinicalDecisionBundle:
    bundle_id: str
    case_id: str
    patient_id: Optional[Any]
    case_context: JsonDict = field(default_factory=dict)
    imaging_context: JsonDict = field(default_factory=dict)
    quality_control: JsonDict = field(default_factory=dict)
    clinical_task_dag: JsonDict = field(default_factory=dict)
    system_execution_trace: JsonDict = field(default_factory=dict)
    algorithm_results: JsonDict = field(default_factory=dict)
    confidence_summary: JsonDict = field(default_factory=dict)
    consistency_checks: JsonDict = field(default_factory=dict)
    report: JsonDict = field(default_factory=dict)
    doctor_review: JsonDict = field(default_factory=dict)
    ai_qa: JsonDict = field(default_factory=dict)
    audit: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)
