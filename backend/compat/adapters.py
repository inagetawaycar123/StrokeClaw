from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .schemas import ClinicalDecisionBundle, CockpitNodeView, CockpitTaskView, SkillInvocationView
from .skill_registry import get_skill_by_id, skill_id_for_tool


JsonDict = Dict[str, Any]

PERFUSION_MODALITIES = ("cbf", "cbv", "tmax")
MCTA_PHASES = ("mcta", "vcta", "dcta")
CORE_MODALITIES = ("ncct",)

FAILURE_POLICIES: Dict[str, JsonDict] = {
    "qc_failed": {
        "failure_type": "qc_failed",
        "failure_severity": "high",
        "retry_allowed": False,
        "max_retry_count": 0,
        "fallback_strategy": "block_downstream_and_request_review",
        "doctor_review_required": True,
        "blocking_required": True,
        "user_visible_message": "Image quality control failed. Review is required.",
    },
    "missing_modality": {
        "failure_type": "missing_modality",
        "failure_severity": "medium",
        "retry_allowed": False,
        "max_retry_count": 0,
        "fallback_strategy": "continue_with_available_modalities",
        "doctor_review_required": True,
        "blocking_required": False,
        "user_visible_message": "Some expected imaging modalities are missing.",
    },
    "low_confidence": {
        "failure_type": "low_confidence",
        "failure_severity": "medium",
        "retry_allowed": False,
        "max_retry_count": 0,
        "fallback_strategy": "surface_warning_and_request_review",
        "doctor_review_required": True,
        "blocking_required": False,
        "user_visible_message": "A low-confidence result needs clinical review.",
    },
    "rag_failed": {
        "failure_type": "rag_failed",
        "failure_severity": "medium",
        "retry_allowed": True,
        "max_retry_count": 1,
        "fallback_strategy": "generate_with_evidence_gap_warning",
        "doctor_review_required": True,
        "blocking_required": False,
        "user_visible_message": "Evidence retrieval failed or returned incomplete evidence.",
    },
    "report_conflict": {
        "failure_type": "report_conflict",
        "failure_severity": "high",
        "retry_allowed": False,
        "max_retry_count": 0,
        "fallback_strategy": "block_submission_until_conflict_review",
        "doctor_review_required": True,
        "blocking_required": True,
        "user_visible_message": "Report conclusions conflict with structured results.",
    },
    "system_error": {
        "failure_type": "system_error",
        "failure_severity": "high",
        "retry_allowed": True,
        "max_retry_count": 1,
        "fallback_strategy": "retry_or_show_partial_results",
        "doctor_review_required": True,
        "blocking_required": False,
        "user_visible_message": "A system error occurred. Partial results may be available.",
    },
}


def _as_dict(value: Any) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _first(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def _normalize_modalities(values: Any) -> List[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    aliases = {"mcat": "mcta", "vcat": "vcta"}
    result: List[str] = []
    seen = set()
    for item in values:
        token = aliases.get(_text(item).lower(), _text(item).lower())
        if token and token not in seen:
            seen.add(token)
            result.append(token)
    return result


def _normalize_confidence(value: Any) -> Optional[float]:
    try:
        score = float(value)
    except Exception:
        return None
    if score > 1.0 and score <= 100.0:
        score = score / 100.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return round(score, 4)


def _extract_evidence_ids(payload: Any) -> List[Any]:
    data = _as_dict(payload)
    for key in ("evidence_ids", "evidence_refs", "citations"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    evidence = data.get("evidence")
    if isinstance(evidence, list):
        ids = []
        for item in evidence:
            if isinstance(item, dict):
                ids.append(_first(item.get("evidence_id"), item.get("id"), default=item))
            else:
                ids.append(item)
        return ids
    return []


def _extract_report_payload(run: Optional[JsonDict], report_payload: Optional[JsonDict]) -> JsonDict:
    if isinstance(report_payload, dict):
        return report_payload
    run = _as_dict(run)
    result = _as_dict(run.get("result"))
    report_result = _as_dict(result.get("report_result"))
    payload = report_result.get("report_payload")
    return payload if isinstance(payload, dict) else {}


def _bundle_id(patient_id: Any, case_id: str, run_id: str = "") -> str:
    case_key = _text(case_id, "unknown")
    if run_id:
        return f"bundle:{case_key}:{run_id}"
    if patient_id not in (None, ""):
        return f"bundle:{patient_id}:{case_key}"
    return f"bundle:{case_key}"


def build_case_context(patient: Optional[JsonDict], run: Optional[JsonDict]) -> JsonDict:
    patient = _as_dict(patient)
    planner_input = _as_dict(_as_dict(run).get("planner_input"))
    return {
        "patient_id": _first(patient.get("id"), planner_input.get("patient_id")),
        "patient_id_hash": patient.get("patient_id_hash"),
        "age": patient.get("patient_age"),
        "sex": patient.get("patient_sex"),
        "onset_time": patient.get("onset_exact_time"),
        "admission_time": patient.get("admission_time"),
        "surgery_time": patient.get("surgery_time"),
        "nihss_score": patient.get("admission_nihss"),
        "baseline_mrs": patient.get("baseline_mrs"),
        "clinical_symptoms": patient.get("clinical_symptoms"),
        "suspected_stroke_type": patient.get("suspected_stroke_type"),
        "goal_question": _first(planner_input.get("goal_question"), planner_input.get("question")),
        "legacy_source": "patient_info",
    }


def build_imaging_context(imaging: Optional[JsonDict], run: Optional[JsonDict]) -> JsonDict:
    imaging = _as_dict(imaging)
    planner_input = _as_dict(_as_dict(run).get("planner_input"))
    modalities = _normalize_modalities(
        _first(imaging.get("available_modalities"), planner_input.get("available_modalities"), default=[])
    )
    case_id = _first(imaging.get("case_id"), planner_input.get("file_id"), _as_dict(run).get("file_id"), default="")
    return {
        "case_id": case_id,
        "file_id": _first(planner_input.get("file_id"), _as_dict(run).get("file_id"), case_id),
        "patient_id": _first(imaging.get("patient_id"), planner_input.get("patient_id"), _as_dict(run).get("patient_id")),
        "available_modalities": modalities,
        "hemisphere": _first(imaging.get("hemisphere"), planner_input.get("hemisphere")),
        "ncct_raw_url": imaging.get("ncct_raw_url"),
        "mcta_raw_url": imaging.get("mcta_raw_url"),
        "processed_image_urls": imaging.get("processed_image_urls") or [],
        "stroke_analysis_urls": imaging.get("stroke_analysis_urls") or [],
        "created_at": imaging.get("created_at"),
        "updated_at": imaging.get("updated_at"),
        "legacy_source": "patient_imaging",
    }


def build_quality_control(imaging: Optional[JsonDict], run: Optional[JsonDict]) -> JsonDict:
    context = build_imaging_context(imaging, run)
    modalities = set(context.get("available_modalities") or [])
    missing_core = [item for item in CORE_MODALITIES if item not in modalities]
    missing_phase = [item for item in MCTA_PHASES if item not in modalities]
    has_any_cta = any(item in modalities for item in MCTA_PHASES)
    has_ctp = all(item in modalities for item in PERFUSION_MODALITIES)
    blocking_required = bool(missing_core)
    warning_messages = []
    if missing_core:
        warning_messages.append("missing_ncct")
    if not has_any_cta:
        warning_messages.append("missing_cta_or_mcta")
    if missing_phase and has_any_cta:
        warning_messages.append("incomplete_mcta_phases")
    qc_score = 1.0
    if missing_core:
        qc_score -= 0.6
    if not has_any_cta:
        qc_score -= 0.2
    elif missing_phase:
        qc_score -= 0.1
    if not has_ctp:
        qc_score -= 0.05
    qc_score = max(0.0, round(qc_score, 4))
    status = "failed" if blocking_required else ("warning" if warning_messages else "passed")
    return {
        "qc_status": status,
        "qc_score": qc_score,
        "qc_file_readable": None,
        "qc_modality_complete": not missing_core and has_any_cta,
        "qc_scan_coverage": "unknown",
        "qc_slice_thickness_status": "unknown",
        "qc_motion_artifact_level": "unknown",
        "qc_metal_artifact_level": "unknown",
        "qc_contrast_phase_status": "complete" if not missing_phase else "incomplete",
        "qc_missing_phase": missing_phase,
        "qc_warning_message": ";".join(warning_messages),
        "qc_affected_nodes": ["generate_ctp_maps", "run_stroke_analysis"] if warning_messages else [],
        "qc_blocking_required": blocking_required,
        "qc_review_required": bool(warning_messages),
        "qc_review_reason": ";".join(warning_messages),
        "available_modalities": sorted(modalities),
    }


def build_confidence_summary(
    *,
    run: Optional[JsonDict] = None,
    events: Optional[Iterable[JsonDict]] = None,
    dag: Optional[JsonDict] = None,
    report_payload: Optional[JsonDict] = None,
) -> JsonDict:
    nodes = _as_list(_as_dict(dag).get("nodes"))
    node_items = []
    for node in nodes:
        node = _as_dict(node)
        output_payload = _as_dict(node.get("output_payload"))
        raw_score = _first(
            node.get("confidence"),
            node.get("confidence_score"),
            output_payload.get("confidence_score"),
            output_payload.get("confidence"),
            output_payload.get("support_rate"),
        )
        score = _normalize_confidence(raw_score)
        method = "legacy_output_confidence"
        skill_id = skill_id_for_tool(_first(node.get("step_key"), node.get("id"), default=""))
        skill = get_skill_by_id(skill_id) or {}
        if skill.get("confidence_method"):
            method = str(skill.get("confidence_method"))
        threshold = skill.get("confidence_threshold")
        review_required = bool(
            threshold is not None and score is not None and score < float(threshold)
        )
        node_items.append(
            {
                "node_id": _first(node.get("id"), node.get("step_key"), default=""),
                "skill_id": skill_id,
                "confidence_score": score,
                "confidence_method": method,
                "confidence_threshold": threshold,
                "top1_prob": output_payload.get("top1_prob"),
                "top2_prob": output_payload.get("top2_prob"),
                "top1_top2_margin": output_payload.get("top1_top2_margin"),
                "calibrated_prob": output_payload.get("calibrated_prob"),
                "uncertainty_score": output_payload.get("uncertainty_score"),
                "evidence_completeness": output_payload.get("evidence_completeness"),
                "review_required": review_required,
                "review_reason": "low_confidence" if review_required else "",
            }
        )

    payload = _as_dict(report_payload)
    traceability = _as_dict(payload.get("traceability"))
    evidence_items = _as_list(payload.get("evidence_items"))
    evidence_completeness = _first(
        traceability.get("coverage"),
        payload.get("evidence_completeness"),
        1.0 if evidence_items else None,
    )
    report_score = _normalize_confidence(evidence_completeness)
    return {
        "items": node_items,
        "report_generation": {
            "confidence_score": report_score,
            "confidence_method": "evidence_completeness_not_llm_confidence",
            "confidence_threshold": 0.85,
            "evidence_completeness": report_score,
            "review_required": bool(report_score is not None and report_score < 0.85),
            "review_reason": "evidence_gap" if report_score is not None and report_score < 0.85 else "",
        },
    }


def build_skill_invocations(
    *,
    run: Optional[JsonDict] = None,
    events: Optional[Iterable[JsonDict]] = None,
) -> List[JsonDict]:
    run = _as_dict(run)
    run_id = _text(run.get("run_id"))
    case_id = _text(_first(run.get("file_id"), _as_dict(run.get("planner_input")).get("file_id")))
    invocations: List[JsonDict] = []
    seen = set()
    for event in events or []:
        event = _as_dict(event)
        tool_name = _first(event.get("tool_name"), event.get("node_name"), default="")
        if not tool_name:
            continue
        event_id = _text(event.get("event_id"))
        invocation_id = event_id or f"inv:{run_id}:{event.get('event_seq') or len(invocations) + 1}"
        seen.add(invocation_id)
        output_payload = _as_dict(event.get("output_ref"))
        invocations.append(
            SkillInvocationView(
                invocation_id=invocation_id,
                skill_id=skill_id_for_tool(tool_name),
                agent_session_id=run_id,
                case_id=case_id,
                input_payload=_as_dict(event.get("input_ref")),
                output_payload=output_payload,
                status=_text(event.get("status"), "unknown"),
                latency_ms=event.get("latency_ms"),
                error_code=event.get("error_code"),
                error_message=event.get("error_message") or output_payload.get("error_message"),
                evidence_used=_extract_evidence_ids(output_payload),
                confidence=_normalize_confidence(_first(event.get("confidence"), output_payload.get("confidence"), output_payload.get("confidence_score"))),
                created_at=event.get("timestamp"),
            ).to_dict()
        )

    for index, result in enumerate(_as_list(run.get("tool_results")), start=1):
        result = _as_dict(result)
        tool_name = _first(result.get("tool_name"), result.get("name"), result.get("step_key"), default="")
        if not tool_name:
            continue
        invocation_id = _text(result.get("invocation_id"), f"tool_result:{run_id}:{index}")
        if invocation_id in seen:
            continue
        invocations.append(
            SkillInvocationView(
                invocation_id=invocation_id,
                skill_id=skill_id_for_tool(tool_name),
                agent_session_id=run_id,
                case_id=case_id,
                input_payload=_as_dict(result.get("input_payload")),
                output_payload=_as_dict(_first(result.get("output_payload"), result.get("structured_output"), result, default={})),
                status=_text(result.get("status"), "unknown"),
                latency_ms=result.get("latency_ms"),
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
                evidence_used=_extract_evidence_ids(result),
                confidence=_normalize_confidence(_first(result.get("confidence"), result.get("confidence_score"))),
                created_at=result.get("created_at") or result.get("timestamp"),
            ).to_dict()
        )
    return invocations


def _node_failure_reason(node: JsonDict) -> str:
    status = _text(node.get("status")).lower()
    if status in {"failed", "error"}:
        return _first(node.get("error_code"), node.get("message"), "system_error", default="system_error")
    score = _normalize_confidence(_first(node.get("confidence"), node.get("confidence_score")))
    if score is not None and score < 0.7:
        return "low_confidence"
    return ""


def _fallback_for_failure(reason: str) -> str:
    key = "system_error"
    if "modality" in reason or "missing" in reason:
        key = "missing_modality"
    elif "confidence" in reason:
        key = "low_confidence"
    elif "rag" in reason or "evidence" in reason:
        key = "rag_failed"
    return str(FAILURE_POLICIES.get(key, {}).get("fallback_strategy") or "show_partial_results")


def build_cockpit_view_model(
    *,
    run: Optional[JsonDict] = None,
    events: Optional[Iterable[JsonDict]] = None,
    dag: Optional[JsonDict] = None,
    bundle_id: str = "",
    case_id: str = "",
) -> JsonDict:
    run = _as_dict(run)
    dag = _as_dict(dag)
    nodes = []
    for raw_node in _as_list(dag.get("nodes")):
        node = _as_dict(raw_node)
        node_id = _text(_first(node.get("id"), node.get("step_key"), default=""))
        tool_name = _text(_first(node.get("step_key"), node_id))
        failure_reason = _node_failure_reason(node)
        output_payload = _as_dict(node.get("output_payload"))
        evidence_ids = _extract_evidence_ids(output_payload)
        risk_level = _text(_first(node.get("risk_level"), output_payload.get("risk_level")), "unknown")
        confidence = _normalize_confidence(
            _first(node.get("confidence"), node.get("confidence_score"), output_payload.get("confidence"), output_payload.get("confidence_score"))
        )
        review_status = "required" if failure_reason or risk_level in {"high", "medium"} else "not_required"
        nodes.append(
            CockpitNodeView(
                node_id=node_id,
                node_name=_text(_first(node.get("title"), node_id)),
                node_layer=_text(_first(node.get("stage"), node.get("lane")), "system_execution"),
                assigned_agent=_text(_first(output_payload.get("agent_name"), node.get("agent_name")), "runtime_agent"),
                called_skill_id=skill_id_for_tool(tool_name),
                node_status=_text(node.get("status"), "pending"),
                runtime_ms=node.get("latency_ms"),
                confidence_score=confidence,
                failure_reason=failure_reason or None,
                fallback_strategy=_fallback_for_failure(failure_reason) if failure_reason else None,
                evidence_ids=evidence_ids,
                review_status=review_status,
                risk_level=risk_level,
                input_summary=_text(_first(node.get("message"), "")),
                output_summary=_text(_first(node.get("message"), output_payload.get("message"), output_payload.get("summary"), "")),
            ).to_dict()
        )

    completed = len([n for n in nodes if n.get("node_status") in {"completed", "succeeded", "success"}])
    failed = len([n for n in nodes if n.get("node_status") in {"failed", "error"}])
    review_required = any(n.get("review_status") == "required" for n in nodes)
    task_id = f"task:{case_id or run.get('file_id') or 'unknown'}"
    task = CockpitTaskView(
        task_id=task_id,
        bundle_id=bundle_id,
        case_id=case_id or _text(run.get("file_id")),
        agent_session_id=_text(run.get("run_id")),
        task_status=_text(run.get("status"), "unknown"),
        node_count=len(nodes),
        completed_node_count=completed,
        failed_node_count=failed,
        review_required=review_required,
        nodes=nodes,
    ).to_dict()
    return {
        "cockpit_task_view": task,
        "cockpit_node_view": nodes,
        "risk_panel": build_risk_panel(nodes),
        "evidence_panel": build_evidence_panel(nodes),
    }


def build_risk_panel(nodes: Iterable[JsonDict]) -> JsonDict:
    risk_items = []
    for node in nodes:
        if node.get("risk_level") in {"high", "medium"} or node.get("failure_reason"):
            risk_items.append(
                {
                    "node_id": node.get("node_id"),
                    "risk_level": node.get("risk_level"),
                    "failure_reason": node.get("failure_reason"),
                    "fallback_strategy": node.get("fallback_strategy"),
                    "review_status": node.get("review_status"),
                }
            )
    return {"risk_count": len(risk_items), "items": risk_items}


def build_evidence_panel(nodes: Iterable[JsonDict]) -> JsonDict:
    items = []
    for node in nodes:
        evidence_ids = node.get("evidence_ids") or []
        if evidence_ids:
            items.append({"node_id": node.get("node_id"), "evidence_ids": evidence_ids})
    return {"evidence_binding_count": len(items), "items": items}


def build_algorithm_results(patient: Optional[JsonDict], imaging: Optional[JsonDict], report_payload: Optional[JsonDict]) -> JsonDict:
    patient = _as_dict(patient)
    imaging = _as_dict(imaging)
    analysis = _as_dict(imaging.get("analysis_result"))
    payload = _as_dict(report_payload)
    return {
        "legacy_patient_info_metrics": {
            "core_infarct_volume": patient.get("core_infarct_volume"),
            "penumbra_volume": patient.get("penumbra_volume"),
            "mismatch_ratio": patient.get("mismatch_ratio"),
            "confidence_score": _normalize_confidence(patient.get("confidence_score")),
            "analysis_status": patient.get("analysis_status"),
        },
        "stroke_analysis_result": {
            "core_volume_ml": _first(analysis.get("core_volume_ml"), analysis.get("core_infarct_volume"), patient.get("core_infarct_volume")),
            "penumbra_volume_ml": _first(analysis.get("penumbra_volume_ml"), analysis.get("penumbra_volume"), patient.get("penumbra_volume")),
            "mismatch_ratio": _first(analysis.get("mismatch_ratio"), patient.get("mismatch_ratio")),
            "has_mismatch": analysis.get("has_mismatch"),
            "total_slices": analysis.get("total_slices"),
            "legacy_source": "patient_imaging.analysis_result",
        },
        "ncct_classification_result": {
            "predicted_label": payload.get("three_class_label"),
            "predicted_label_cn": payload.get("three_class_label_cn"),
            "confidence_score": _normalize_confidence(payload.get("three_class_confidence")),
            "legacy_source": "report_payload",
        },
        "vessel_occlusion_result": {
            "predicted_label": payload.get("vessel_occlusion_class_result"),
            "legacy_source": "report_payload",
        },
    }


def build_report_evidence(report_payload: Optional[JsonDict], run: Optional[JsonDict]) -> JsonDict:
    payload = _extract_report_payload(run, report_payload)
    final_report = _as_dict(payload.get("final_report"))
    evidence_items = _as_list(payload.get("evidence_items"))
    evidence_map = _as_dict(payload.get("evidence_map"))
    traceability = _as_dict(payload.get("traceability"))
    sections = []
    for key in ("summary", "key_findings", "risk_level", "next_actions"):
        if key in final_report:
            sections.append({"section_id": key, "section_type": key, "content": final_report.get(key)})
    if not sections and payload:
        sections.append(
            {
                "section_id": "legacy_report",
                "section_type": "legacy_report",
                "content": _first(payload.get("report"), payload.get("summary"), final_report, default=""),
            }
        )

    bindings = []
    for claim_id, item in evidence_map.items():
        item = _as_dict(item)
        bindings.append(
            {
                "claim_id": claim_id,
                "claim_text": item.get("claim_text") or claim_id,
                "claim_source_type": item.get("source_type") or "legacy_evidence_map",
                "source_result_id": item.get("source_result_id"),
                "evidence_ids": item.get("evidence_ids") or [],
                "evidence_completeness": item.get("evidence_completeness"),
                "guideline_support_level": item.get("guideline_support_level"),
                "conflict_status": item.get("conflict_status") or "unknown",
                "doctor_review_required": bool(item.get("doctor_review_required", False)),
                "doctor_final_decision": item.get("doctor_final_decision"),
            }
        )

    evidence_completeness = _normalize_confidence(
        _first(traceability.get("coverage"), payload.get("evidence_completeness"), 1.0 if evidence_items else None)
    )
    return {
        "structured_findings": final_report,
        "report_text": _first(payload.get("final_confirmed_report"), payload.get("report"), final_report.get("summary"), default=""),
        "evidence_completeness": evidence_completeness,
        "severe_conflict_exists": bool(payload.get("severe_conflict_exists", False)),
        "submit_allowed": not bool(payload.get("severe_conflict_exists", False)),
        "report_sections": sections,
        "evidence_bindings": bindings,
        "evidence_items": evidence_items,
    }


def build_consistency_checks(validation: Optional[JsonDict], report_payload: Optional[JsonDict]) -> JsonDict:
    validation = _as_dict(validation)
    report_payload = _as_dict(report_payload)
    conflict_items = []
    for key in ("icv", "ekv", "consensus"):
        payload = _as_dict(validation.get(key))
        status = _text(_first(payload.get("status"), payload.get("verdict"), payload.get("decision")))
        if status and status not in {"passed", "success", "supported", "ok", "consistent"}:
            conflict_items.append({"check_type": key, "status": status, "payload": payload})
    if report_payload.get("severe_conflict_exists"):
        conflict_items.append({"check_type": "report_conflict", "status": "failed"})
    return {
        "check_status": "warning" if conflict_items else "unknown" if not validation else "passed",
        "conflict_count": len(conflict_items),
        "conflicts": conflict_items,
    }


def build_clinical_decision_bundle(
    *,
    patient: Optional[JsonDict] = None,
    imaging: Optional[JsonDict] = None,
    run: Optional[JsonDict] = None,
    events: Optional[Iterable[JsonDict]] = None,
    dag: Optional[JsonDict] = None,
    validation: Optional[JsonDict] = None,
    report_payload: Optional[JsonDict] = None,
    source_tag: str = "compat",
) -> JsonDict:
    run = _as_dict(run)
    imaging_context = build_imaging_context(imaging, run)
    case_id = _text(_first(imaging_context.get("case_id"), run.get("file_id"), "unknown"))
    patient_id = _first(imaging_context.get("patient_id"), _as_dict(patient).get("id"), run.get("patient_id"))
    run_id = _text(run.get("run_id"))
    bundle_id = _bundle_id(patient_id, case_id, run_id)
    payload = _extract_report_payload(run, report_payload)
    dag = _as_dict(dag)
    cockpit_view = build_cockpit_view_model(
        run=run,
        events=events,
        dag=dag,
        bundle_id=bundle_id,
        case_id=case_id,
    )
    bundle = ClinicalDecisionBundle(
        bundle_id=bundle_id,
        case_id=case_id,
        patient_id=patient_id,
        case_context=build_case_context(patient, run),
        imaging_context=imaging_context,
        quality_control=build_quality_control(imaging, run),
        clinical_task_dag={
            "dag_id": f"dag:{case_id}",
            "dag_type": "clinical_task_and_system_execution",
            "legacy_dag": dag,
            "cockpit_task_view": cockpit_view.get("cockpit_task_view"),
        },
        system_execution_trace={
            "agent_session_id": run_id,
            "run_status": run.get("status"),
            "events": list(events or []),
            "skill_invocations": build_skill_invocations(run=run, events=events),
        },
        algorithm_results=build_algorithm_results(patient, imaging, payload),
        confidence_summary=build_confidence_summary(
            run=run,
            events=events,
            dag=dag,
            report_payload=payload,
        ),
        consistency_checks=build_consistency_checks(validation, payload),
        report=build_report_evidence(payload, run),
        doctor_review=_as_dict(run.get("review_state")) or _as_dict(payload.get("review_state")),
        ai_qa={
            "question_answer": payload.get("question_answer"),
            "answer_evidence_ledger": payload.get("answer_evidence_ledger"),
            "answer_metrics": payload.get("answer_metrics"),
        },
        audit={
            "source_tag": source_tag,
            "generated_from": [
                "patient_info",
                "patient_imaging",
                "agent_runtime",
                "report_payload",
            ],
            "persisted": False,
        },
    ).to_dict()
    bundle["cockpit_view"] = cockpit_view
    bundle["failure_policies"] = FAILURE_POLICIES
    return bundle
