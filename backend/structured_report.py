from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from .vessel_context import vessel_result_from_sources
except ImportError:
    from vessel_context import vessel_result_from_sources


SCHEMA_VERSION = "2.0"
EVIDENCE_TYPES = {
    "patient_data",
    "imaging_finding",
    "algorithm_output",
    "clinical_rule",
    "guideline",
    "agent_reasoning",
    "clinician_confirmation",
}
RULE_RESULTS = {"met", "not_met", "unknown", "conflict", "not_applicable"}

REVIEW_SECTION_BY_DOMAIN = {
    "patient": "patient_context",
    "imaging": "imaging_summary",
    "ctp": "ctp_quant",
    "assessment": "question_answer",
    "risk": "risk_uncertainty",
    "recommendation": "next_steps",
    "evidence": "evidence_trace",
}


def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_confidence(value: Any) -> Optional[float]:
    parsed = _safe_float(value)
    if parsed is None or parsed < 0 or parsed > 1:
        return None
    return round(parsed, 4)


def _stable_id(prefix: str, *parts: Any) -> str:
    normalized = "|".join(
        json.dumps(part, ensure_ascii=False, sort_keys=True, default=str)
        if isinstance(part, (dict, list, tuple))
        else str(part or "")
        for part in parts
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _normalize_sex(value: Any) -> Optional[str]:
    token = str(value or "").strip().lower()
    if token in {"男", "male", "m"}:
        return "male"
    if token in {"女", "female", "f"}:
        return "female"
    return token or None


def _format_number(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "未获得"
    return f"{value:.{digits}f}"


def _format_perfusion_summary(
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
) -> Optional[str]:
    parts: List[str] = []
    if core is not None:
        parts.append(f"Core {_format_number(core)} mL")
    if penumbra is not None:
        parts.append(f"Penumbra {_format_number(penumbra)} mL")
    if mismatch is not None:
        parts.append(f"Mismatch {_format_number(mismatch)}")
    return " · ".join(parts) or None


def _review_sections(review_state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("section_id") or ""): item
        for item in _as_list(review_state.get("sections"))
        if isinstance(item, dict) and item.get("section_id")
    }


def _review_status(
    section_map: Dict[str, Dict[str, Any]], section_id: str
) -> Dict[str, Any]:
    section = section_map.get(section_id) or {}
    status = str(section.get("review_status") or "pending").strip().lower()
    if status not in {"pending", "confirmed", "needs_edit"}:
        status = "pending"
    return {
        "review_status": status,
        "clinician_confirmed": True if status == "confirmed" else False,
        "review_section_id": section_id,
        "clinician_note": str(section.get("doctor_note") or "").strip() or None,
        "reviewed_at": section.get("updated_at"),
    }


def _clinical_value(
    *,
    field_id: str,
    display_name: str,
    value: Any,
    unit: str,
    value_type: str,
    source_type: str,
    source_module: str,
    source_record: str,
    acquired_at: Any,
    section_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    is_missing = value is None or value == ""
    item = {
        "field_id": field_id,
        "standard_name": field_id,
        "display_name": display_name,
        "value": None if is_missing else value,
        "unit": unit,
        "value_type": value_type,
        "status": "missing" if is_missing else "present",
        "is_missing": is_missing,
        "source_type": source_type,
        "source_module": source_module,
        "source_record": source_record,
        "acquired_at": acquired_at,
        "confidence": None,
    }
    item.update(_review_status(section_map, REVIEW_SECTION_BY_DOMAIN["patient"]))
    return item


def _evidence_item(
    *,
    evidence_type: str,
    display_name: str,
    value: Any = None,
    unit: str = "",
    source_module: str,
    source_record: str,
    confidence: Any = None,
    generated_at: Any = None,
    source_ref: str = "",
    document_title: str = "",
    document_version: str = "",
    page: Any = None,
    snippet: str = "",
    binding_status: str = "bound",
    legacy_aliases: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    normalized_type = (
        evidence_type if evidence_type in EVIDENCE_TYPES else "agent_reasoning"
    )
    evidence_id = _stable_id(
        "ev",
        normalized_type,
        source_module,
        source_record,
        source_ref,
        page,
        display_name,
    )
    return {
        "evidence_id": evidence_id,
        "legacy_aliases": [str(x) for x in (legacy_aliases or []) if str(x)],
        "evidence_type": normalized_type,
        "display_name": display_name,
        "value": value,
        "unit": unit,
        "source_module": source_module,
        "source_record": source_record,
        "confidence": _safe_confidence(confidence),
        "generated_at": generated_at,
        "source_ref": source_ref or None,
        "document_title": document_title or None,
        "document_version": document_version or None,
        "page": page,
        "snippet": snippet or None,
        "binding_status": binding_status,
        "clinician_confirmed": False,
    }


def _metric(
    *,
    metric_id: str,
    display_name: str,
    value: Optional[float],
    unit: str,
    source_module: str,
    source_record: str,
    evidence_id: Optional[str],
    section_map: Dict[str, Dict[str, Any]],
    confidence: Any = None,
    operator: Optional[str] = None,
    reference_value: Optional[float] = None,
    evaluation: str = "unknown",
) -> Dict[str, Any]:
    item = {
        "metric_id": metric_id,
        "display_name": display_name,
        "value": value,
        "unit": unit,
        "status": "missing" if value is None else "present",
        "reference_operator": operator,
        "reference_value": reference_value,
        "evaluation": evaluation if value is not None else "unknown",
        "source_type": "algorithm_output",
        "source_module": source_module,
        "source_record": source_record,
        "confidence": _safe_confidence(confidence),
        "evidence_ids": [evidence_id] if evidence_id else [],
    }
    item.update(_review_status(section_map, REVIEW_SECTION_BY_DOMAIN["ctp"]))
    return item


def _rule(
    *,
    rule_id: str,
    rule_name: str,
    input_value: Optional[float],
    operator: str,
    threshold: Optional[float],
    result: str,
    clinical_meaning: str,
    evidence_ids: Sequence[str],
    section_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_result = result if result in RULE_RESULTS else "unknown"
    source = {
        "type": "internal_rule",
        "title": "StrokeClaw 内部卒中规则集",
        "version": "v1",
        "section": rule_id,
        "guideline_bound": False,
    }
    item = {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "input_value": input_value,
        "operator": operator,
        "threshold": threshold,
        "result": normalized_result,
        "clinical_meaning": clinical_meaning,
        "source": source,
        "evidence_ids": list(evidence_ids),
        "requires_clinician_review": True,
    }
    item.update(_review_status(section_map, REVIEW_SECTION_BY_DOMAIN["ctp"]))
    return item


def _issue(
    *,
    issue_id: str,
    field: str,
    status: str,
    message: str,
    impact: str,
    recommended_action: str,
    severity: str = "medium",
) -> Dict[str, Any]:
    return {
        "issue_id": issue_id,
        "field": field,
        "status": status,
        "message": message,
        "impact": impact,
        "recommended_action": recommended_action,
        "severity": severity,
        "requires_clinician_review": True,
        "review_section_id": REVIEW_SECTION_BY_DOMAIN["risk"],
    }


def _claim(
    *,
    claim_id: str,
    claim: str,
    claim_type: str,
    support_status: str,
    evidence_ids: Sequence[str],
    limitations: Sequence[str],
    section_map: Dict[str, Dict[str, Any]],
    review_domain: str,
) -> Dict[str, Any]:
    item = {
        "claim_id": claim_id,
        "claim": claim,
        "claim_type": claim_type,
        "support_status": support_status,
        "evidence_ids": list(dict.fromkeys(str(x) for x in evidence_ids if str(x))),
        "limitations": [str(x) for x in limitations if str(x)],
        "requires_clinician_review": True,
    }
    item.update(
        _review_status(
            section_map,
            REVIEW_SECTION_BY_DOMAIN.get(
                review_domain, REVIEW_SECTION_BY_DOMAIN["assessment"]
            ),
        )
    )
    return item


def _extract_context(
    patient_context: Dict[str, Any], report_payload: Dict[str, Any]
) -> Dict[str, Any]:
    context = _as_dict(patient_context)
    context_struct = _as_dict(context.get("context_struct"))
    patient = _as_dict(context_struct.get("patient"))
    imaging = _as_dict(context_struct.get("imaging"))
    ctp = _as_dict(context_struct.get("ctp"))
    sections = _as_dict(report_payload.get("sections"))
    report_ctp = _as_dict(sections.get("ctp"))
    context_three_class = _as_dict(context.get("three_class_result"))
    payload_three_class = _as_dict(report_payload.get("three_class_result"))
    safety_gate = _as_dict(
        _first_present(
            context.get("safety_gate"),
            context_three_class.get("safety_gate"),
            report_payload.get("safety_gate"),
            payload_three_class.get("safety_gate"),
            _as_dict(sections.get("ncct")).get("safety_gate"),
        )
    )

    return {
        "age": _first_present(
            context.get("patient_age"),
            context.get("age"),
            patient.get("patient_age"),
            patient.get("age"),
            report_payload.get("patient_age"),
        ),
        "sex": _normalize_sex(
            _first_present(
                context.get("patient_sex"),
                context.get("sex"),
                patient.get("patient_sex"),
                patient.get("sex"),
                report_payload.get("patient_sex"),
            )
        ),
        "nihss": _safe_float(
            _first_present(
                context.get("admission_nihss"),
                patient.get("admission_nihss"),
                report_payload.get("admission_nihss"),
            )
        ),
        "onset_hours": _safe_float(
            _first_present(
                context.get("onset_to_admission_hours"),
                patient.get("onset_to_admission_hours"),
                report_payload.get("onset_to_admission_hours"),
            )
        ),
        "hemisphere": _first_present(
            context.get("hemisphere"),
            imaging.get("hemisphere"),
            report_payload.get("hemisphere"),
        ),
        "modalities": _first_present(
            context.get("available_modalities"),
            imaging.get("available_modalities"),
            report_payload.get("modalities"),
        )
        or [],
        "core": _safe_float(
            _first_present(
                ctp.get("core_infarct_volume"),
                report_payload.get("core_infarct_volume"),
                report_ctp.get("core_infarct_volume"),
                context.get("core_infarct_volume"),
            )
        ),
        "penumbra": _safe_float(
            _first_present(
                ctp.get("penumbra_volume"),
                report_payload.get("penumbra_volume"),
                report_ctp.get("penumbra_volume"),
                context.get("penumbra_volume"),
            )
        ),
        "mismatch": _safe_float(
            _first_present(
                ctp.get("mismatch_ratio"),
                report_payload.get("mismatch_ratio"),
                report_ctp.get("mismatch_ratio"),
                context.get("mismatch_ratio"),
            )
        ),
        "ncct_label": _first_present(
            context.get("three_class_label"),
            context_three_class.get("three_class_label"),
            report_payload.get("three_class_label"),
            payload_three_class.get("three_class_label"),
        ),
        "ncct_label_cn": _first_present(
            context.get("three_class_label_cn"),
            context_three_class.get("three_class_label_cn"),
            report_payload.get("three_class_label_cn"),
            payload_three_class.get("three_class_label_cn"),
        ),
        "ncct_confidence": _safe_confidence(
            _first_present(
                context.get("three_class_confidence"),
                context_three_class.get("three_class_confidence"),
                report_payload.get("three_class_confidence"),
                payload_three_class.get("three_class_confidence"),
            )
        ),
        "safety_gate": safety_gate,
        "acquired_at": _first_present(
            context.get("acquired_at"),
            context.get("updated_at"),
            report_payload.get("generated_at"),
        ),
    }


def _append_unique_evidence(
    catalog: List[Dict[str, Any]],
    lookup: Dict[str, Dict[str, Any]],
    item: Dict[str, Any],
) -> str:
    evidence_id = str(item.get("evidence_id") or "")
    if evidence_id and evidence_id not in lookup:
        catalog.append(item)
        lookup[evidence_id] = item
    return evidence_id


def _legacy_guideline_evidence(
    report_payload: Dict[str, Any],
    catalog: List[Dict[str, Any]],
    lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    claim_map: Dict[str, List[str]] = {}
    for raw in _as_list(report_payload.get("evidence_items")):
        if not isinstance(raw, dict):
            continue
        source_type = str(raw.get("source_type") or "").strip().lower()
        is_stub = source_type in {"guideline_stub", "stub"} or str(
            raw.get("source_ref") or ""
        ).startswith(("kb://", "internal_guideline:"))
        evidence = _evidence_item(
            evidence_type="guideline",
            display_name=str(
                raw.get("doc_name")
                or raw.get("claim")
                or raw.get("source_ref")
                or "指南证据"
            ),
            source_module="EKV",
            source_record=str(raw.get("claim_id") or raw.get("source_ref") or ""),
            generated_at=raw.get("timestamp"),
            source_ref=str(raw.get("source_ref") or ""),
            document_title=str(raw.get("doc_name") or ""),
            document_version=str(raw.get("version") or ""),
            page=raw.get("page"),
            snippet=str(raw.get("snippet") or ""),
            binding_status="unbound" if is_stub else "bound",
            legacy_aliases=[str(raw.get("evidence_id") or "")],
        )
        evidence_id = _append_unique_evidence(catalog, lookup, evidence)
        claim_id = str(raw.get("claim_id") or "").strip()
        if claim_id and evidence_id:
            claim_map.setdefault(claim_id, []).append(evidence_id)
    return claim_map


def _collect_existing_uncertainties(report_payload: Dict[str, Any]) -> List[str]:
    final_report = _as_dict(report_payload.get("final_report"))
    values = _as_list(final_report.get("uncertainties"))
    return [str(x).strip() for x in values if str(x).strip()]


def build_structured_report_v2(
    *,
    run_id: str,
    file_id: str,
    report_payload: Optional[Dict[str, Any]],
    patient_context: Optional[Dict[str, Any]] = None,
    icv: Optional[Dict[str, Any]] = None,
    ekv: Optional[Dict[str, Any]] = None,
    consensus: Optional[Dict[str, Any]] = None,
    review_state: Optional[Dict[str, Any]] = None,
    legacy_report_text: str = "",
) -> Dict[str, Any]:
    payload = _as_dict(report_payload)

    review = (
        _as_dict(review_state)
        or _as_dict(payload.get("review_state"))
    )
    section_map = _review_sections(review)
    data = _extract_context(_as_dict(patient_context), payload)
    generated_at = _first_present(
        payload.get("generated_at"),
        _as_dict(payload.get("meta")).get("timestamp"),
        _now_iso(),
    )

    patient_fields = [
        _clinical_value(
            field_id="age",
            display_name="年龄",
            value=_safe_float(data["age"]),
            unit="岁",
            value_type="number",
            source_type="patient_data",
            source_module="patient_info",
            source_record="patient_info.patient_age",
            acquired_at=data["acquired_at"],
            section_map=section_map,
        ),
        _clinical_value(
            field_id="sex",
            display_name="性别",
            value=data["sex"],
            unit="",
            value_type="code",
            source_type="patient_data",
            source_module="patient_info",
            source_record="patient_info.patient_sex",
            acquired_at=data["acquired_at"],
            section_map=section_map,
        ),
        _clinical_value(
            field_id="onset_to_admission_hours",
            display_name="发病至入院",
            value=round(data["onset_hours"], 2)
            if data["onset_hours"] is not None
            else None,
            unit="h",
            value_type="number",
            source_type="patient_data",
            source_module="patient_context",
            source_record="onset_exact_time->admission_time",
            acquired_at=data["acquired_at"],
            section_map=section_map,
        ),
        _clinical_value(
            field_id="admission_nihss",
            display_name="入院 NIHSS",
            value=data["nihss"],
            unit="分",
            value_type="number",
            source_type="patient_data",
            source_module="patient_info",
            source_record="patient_info.admission_nihss",
            acquired_at=data["acquired_at"],
            section_map=section_map,
        ),
    ]

    catalog: List[Dict[str, Any]] = []
    evidence_lookup: Dict[str, Dict[str, Any]] = {}
    evidence_by_field: Dict[str, str] = {}
    for field in patient_fields:
        if field["is_missing"]:
            continue
        ev = _evidence_item(
            evidence_type="patient_data",
            display_name=field["display_name"],
            value=field["value"],
            unit=field["unit"],
            source_module=field["source_module"],
            source_record=field["source_record"],
            generated_at=field["acquired_at"],
        )
        evidence_by_field[field["field_id"]] = _append_unique_evidence(
            catalog, evidence_lookup, ev
        )

    metric_specs = [
        (
            "core_infarct_volume",
            "核心梗死体积",
            data["core"],
            "mL",
            "<",
            70.0,
            (
                "below_threshold"
                if data["core"] is not None and data["core"] < 70
                else "above_or_equal_threshold"
                if data["core"] is not None
                else "unknown"
            ),
        ),
        (
            "penumbra_volume",
            "半暗带体积",
            data["penumbra"],
            "mL",
            None,
            None,
            "observed" if data["penumbra"] is not None else "unknown",
        ),
        (
            "mismatch_ratio",
            "不匹配比值",
            data["mismatch"],
            "",
            ">",
            1.8,
            (
                "above_threshold"
                if data["mismatch"] is not None and data["mismatch"] > 1.8
                else "not_above_threshold"
                if data["mismatch"] is not None
                else "unknown"
            ),
        ),
    ]
    metrics: List[Dict[str, Any]] = []
    for metric_id, display, value, unit, operator, reference, evaluation in metric_specs:
        ev_id = None
        if value is not None:
            ev = _evidence_item(
                evidence_type="algorithm_output",
                display_name=display,
                value=value,
                unit=unit,
                source_module="StrokeAnalysisAgent",
                source_record=f"run_stroke_analysis.{metric_id}",
                generated_at=generated_at,
            )
            ev_id = _append_unique_evidence(catalog, evidence_lookup, ev)
        metrics.append(
            _metric(
                metric_id=metric_id,
                display_name=display,
                value=value,
                unit=unit,
                source_module="StrokeAnalysisAgent",
                source_record=f"run_stroke_analysis.{metric_id}",
                evidence_id=ev_id,
                section_map=section_map,
                operator=operator,
                reference_value=reference,
                evaluation=evaluation,
            )
        )
        if ev_id:
            evidence_by_field[metric_id] = ev_id

    vessel = vessel_result_from_sources(_as_dict(patient_context), payload)
    vessel_status = str(vessel.get("status") or "unavailable").lower()
    vessel_label = (
        str(vessel.get("vessel_occlusion_class_result") or "").strip() or None
    )
    vessel_confidence = _safe_confidence(vessel.get("confidence"))

    imaging_findings: List[Dict[str, Any]] = []
    ncct_label = data["ncct_label_cn"] or data["ncct_label"]
    if ncct_label:
        ev = _evidence_item(
            evidence_type="algorithm_output",
            display_name="NCCT 三分类结果",
            value=ncct_label,
            source_module="NCCTThreeClassAgent",
            source_record="three_class.predicted_label",
            confidence=data["ncct_confidence"],
            generated_at=generated_at,
        )
        ev_id = _append_unique_evidence(catalog, evidence_lookup, ev)
        evidence_by_field["ncct_classification"] = ev_id
        finding = {
            "finding_id": "ncct_classification",
            "display_name": "NCCT 三分类",
            "value": ncct_label,
            "status": "completed",
            "source_type": "algorithm_output",
            "source_module": "NCCTThreeClassAgent",
            "confidence": data["ncct_confidence"],
            "evidence_ids": [ev_id],
            "limitations": [],
            "requires_clinician_review": True,
        }
    else:
        ncct_missing_ev = _evidence_item(
            evidence_type="algorithm_output",
            display_name="NCCT 三分类运行状态",
            value=None,
            source_module="NCCTThreeClassAgent",
            source_record="three_class.predicted_label",
            generated_at=generated_at,
            snippet="未获得有效 NCCT 三分类结果。",
            binding_status="missing",
        )
        ncct_missing_ev_id = _append_unique_evidence(
            catalog, evidence_lookup, ncct_missing_ev
        )
        finding = {
            "finding_id": "ncct_classification",
            "display_name": "NCCT 三分类",
            "value": None,
            "status": "missing",
            "source_type": "algorithm_output",
            "source_module": "NCCTThreeClassAgent",
            "confidence": None,
            "evidence_ids": [ncct_missing_ev_id],
            "limitations": ["未获得有效 NCCT 三分类结果。"],
            "requires_clinician_review": True,
        }
    finding.update(
        _review_status(section_map, REVIEW_SECTION_BY_DOMAIN["imaging"])
    )
    imaging_findings.append(finding)

    if vessel_status == "completed" and vessel_label:
        ev = _evidence_item(
            evidence_type="algorithm_output",
            display_name="血管闭塞分类",
            value=vessel_label,
            source_module="VesselOcclusionAgent",
            source_record="vessel_occlusion.vessel_occlusion_class_result",
            confidence=vessel_confidence,
            generated_at=generated_at,
        )
        vessel_ev_id = _append_unique_evidence(catalog, evidence_lookup, ev)
        evidence_by_field["vessel_occlusion_class"] = vessel_ev_id
    else:
        vessel_ev_id = None
        vessel_missing_ev = _evidence_item(
            evidence_type="algorithm_output",
            display_name="血管闭塞分类运行状态",
            value=None,
            source_module="VesselOcclusionAgent",
            source_record="vessel_occlusion.vessel_occlusion_class_result",
            generated_at=generated_at,
            snippet="未获得有效血管闭塞分类结果。",
            binding_status="missing",
        )
        vessel_missing_ev_id = _append_unique_evidence(
            catalog, evidence_lookup, vessel_missing_ev
        )
    vessel_finding = {
        "finding_id": "vessel_occlusion_class",
        "display_name": "血管闭塞分类",
        "value": vessel_label,
        "status": "completed" if vessel_ev_id else "missing",
        "source_type": "algorithm_output",
        "source_module": "VesselOcclusionAgent",
        "confidence": vessel_confidence,
        "evidence_ids": (
            [vessel_ev_id] if vessel_ev_id else [vessel_missing_ev_id]
        ),
        "limitations": []
        if vessel_ev_id
        else ["未获得有效血管闭塞分类结果。"],
        "requires_clinician_review": True,
    }
    vessel_finding.update(
        _review_status(section_map, REVIEW_SECTION_BY_DOMAIN["imaging"])
    )
    imaging_findings.append(vessel_finding)

    modalities = [
        str(x).strip().lower()
        for x in data["modalities"]
        if str(x).strip()
    ] if isinstance(data["modalities"], list) else []
    safety_gate = _as_dict(data.get("safety_gate"))
    safety_blocked = bool(safety_gate.get("blocked"))
    perfusion_metrics_value = _format_perfusion_summary(
        data["core"], data["penumbra"], data["mismatch"]
    )
    perfusion_modalities_value = ", ".join(
        x.upper() for x in modalities if x in {"cbf", "cbv", "tmax", "ctp"}
    ) or None
    if safety_blocked:
        perfusion_status = "skipped"
        perfusion_value = "因疑似出血安全门控未执行"
    elif perfusion_metrics_value:
        perfusion_status = "completed"
        perfusion_value = perfusion_metrics_value
    elif perfusion_modalities_value:
        perfusion_status = "completed"
        perfusion_value = perfusion_modalities_value
    else:
        perfusion_status = "not_run"
        perfusion_value = None
    perfusion_finding = {
        "finding_id": "perfusion_analysis",
        "display_name": "灌注分析",
        "value": perfusion_value,
        "status": perfusion_status,
        "source_type": "algorithm_output",
        "source_module": "CTPAnalysisAgent",
        "confidence": None,
        "evidence_ids": [] if safety_blocked else [
            evidence_by_field[x]
            for x in (
                "core_infarct_volume",
                "penumbra_volume",
                "mismatch_ratio",
            )
            if x in evidence_by_field
        ],
        "limitations": (
            [str(safety_gate.get("reason") or "因 NCCT 安全门控跳过。")]
            if safety_blocked
            else (
                []
                if perfusion_status == "completed"
                else ["未运行或未获得灌注分析结果。"]
            )
        ),
        "requires_clinician_review": True,
    }
    perfusion_finding.update(
        _review_status(section_map, REVIEW_SECTION_BY_DOMAIN["imaging"])
    )
    imaging_findings.append(perfusion_finding)

    report_sections = _as_dict(payload.get("sections"))
    cta_sections = _as_list(report_sections.get("cta"))
    cta_modalities = [
        item for item in modalities if item in {"cta", "mcta", "vcta", "dcta"}
    ]
    if cta_sections or cta_modalities:
        cta_titles = [
            str(item.get("title") or "").strip()
            for item in cta_sections
            if isinstance(item, dict) and str(item.get("title") or "").strip()
        ]
        cta_ev = _evidence_item(
            evidence_type="imaging_finding",
            display_name="CTA / 多期 CTA 观察",
            value="、".join(cta_titles) or "已获得 CTA 模态",
            source_module="Report_Generation" if cta_sections else "detect_modalities",
            source_record=(
                "report_payload.sections.cta"
                if cta_sections
                else "available_modalities.cta"
            ),
            generated_at=generated_at,
        )
        cta_ev_id = _append_unique_evidence(catalog, evidence_lookup, cta_ev)
        cta_finding = {
            "finding_id": "cta_assessment",
            "display_name": "CTA / 多期 CTA",
            "value": "、".join(cta_titles) or "已获得影像，等待结构化观察",
            "status": "completed" if cta_sections else "unknown",
            "source_type": "imaging_finding",
            "source_module": "Report_Generation" if cta_sections else "detect_modalities",
            "confidence": None,
            "evidence_ids": [cta_ev_id],
            "limitations": []
            if cta_sections
            else ["仅确认已上传 CTA 模态，未获得结构化模型观察。"],
            "requires_clinician_review": True,
        }
        cta_finding.update(
            _review_status(section_map, REVIEW_SECTION_BY_DOMAIN["imaging"])
        )
        imaging_findings.append(cta_finding)

    for modality in ("cbf", "cbv", "tmax"):
        if modality not in modalities:
            continue
        modality_ev = _evidence_item(
            evidence_type="imaging_finding",
            display_name=f"{modality.upper()} 数据可用",
            value=modality.upper(),
            source_module="detect_modalities",
            source_record=f"available_modalities.{modality}",
            generated_at=generated_at,
        )
        modality_ev_id = _append_unique_evidence(
            catalog, evidence_lookup, modality_ev
        )
        modality_finding = {
            "finding_id": f"{modality}_availability",
            "display_name": f"{modality.upper()} 灌注图",
            "value": "已纳入本轮分析",
            "status": "completed",
            "source_type": "imaging_finding",
            "source_module": "detect_modalities",
            "confidence": None,
            "evidence_ids": [modality_ev_id],
            "limitations": ["具体影像征象需结合原始灌注图人工复核。"],
            "requires_clinician_review": True,
        }
        modality_finding.update(
            _review_status(section_map, REVIEW_SECTION_BY_DOMAIN["imaging"])
        )
        imaging_findings.append(modality_finding)

    rules: List[Dict[str, Any]] = []
    mismatch_result = (
        "met"
        if data["mismatch"] is not None and data["mismatch"] > 1.8
        else "not_met"
        if data["mismatch"] is not None
        else "unknown"
    )
    rules.append(
        _rule(
            rule_id="CTP_MISMATCH_RATIO_1_8_V1",
            rule_name="灌注不匹配比值评估",
            input_value=data["mismatch"],
            operator=">",
            threshold=1.8,
            result=mismatch_result,
            clinical_meaning=(
                "提示存在具有临床意义的灌注不匹配，需结合血管、时间窗和出血风险进一步评估。"
                if mismatch_result == "met"
                else "不支持显著灌注不匹配。"
                if mismatch_result == "not_met"
                else "缺少不匹配比值，无法评估。"
            ),
            evidence_ids=[evidence_by_field.get("mismatch_ratio")]
            if evidence_by_field.get("mismatch_ratio")
            else [],
            section_map=section_map,
        )
    )
    core_result = (
        "met"
        if data["core"] is not None and data["core"] < 70
        else "not_met"
        if data["core"] is not None
        else "unknown"
    )
    rules.append(
        _rule(
            rule_id="CTP_CORE_VOLUME_70ML_V1",
            rule_name="核心梗死体积高负荷复核",
            input_value=data["core"],
            operator="<",
            threshold=70.0,
            result=core_result,
            clinical_meaning=(
                "核心梗死体积未达到当前内部规则的高负荷界值。"
                if core_result == "met"
                else "核心梗死体积达到或超过高负荷界值，需谨慎复核。"
                if core_result == "not_met"
                else "缺少核心梗死体积，无法评估。"
            ),
            evidence_ids=[evidence_by_field.get("core_infarct_volume")]
            if evidence_by_field.get("core_infarct_volume")
            else [],
            section_map=section_map,
        )
    )
    onset = data["onset_hours"]
    early_result = (
        "met" if onset is not None and onset <= 6 else "not_met" if onset is not None else "unknown"
    )
    rules.append(
        _rule(
            rule_id="ONSET_TO_ADMISSION_6H_V1",
            rule_name="早期时间窗提示",
            input_value=onset,
            operator="<=",
            threshold=6.0,
            result=early_result,
            clinical_meaning=(
                "处于当前内部规则的早期时间窗。"
                if early_result == "met"
                else "不处于早期时间窗，需继续评估选择性时间窗。"
                if early_result == "not_met"
                else "缺少时间信息，无法评估。"
            ),
            evidence_ids=[evidence_by_field.get("onset_to_admission_hours")]
            if evidence_by_field.get("onset_to_admission_hours")
            else [],
            section_map=section_map,
        )
    )
    extended_result = (
        "not_applicable"
        if onset is not None and onset <= 6
        else "met"
        if onset is not None and onset <= 24
        else "not_met"
        if onset is not None
        else "unknown"
    )
    rules.append(
        _rule(
            rule_id="ONSET_TO_ADMISSION_24H_SELECTIVE_V1",
            rule_name="选择性延长时间窗提示",
            input_value=onset,
            operator="<=",
            threshold=24.0,
            result=extended_result,
            clinical_meaning=(
                "可进入选择性延长时间窗评估，但不能据此直接形成治疗结论。"
                if extended_result == "met"
                else "已满足早期时间窗，本规则不适用。"
                if extended_result == "not_applicable"
                else "超出当前内部规则时间范围。"
                if extended_result == "not_met"
                else "缺少时间信息，无法评估。"
            ),
            evidence_ids=[evidence_by_field.get("onset_to_admission_hours")]
            if evidence_by_field.get("onset_to_admission_hours")
            else [],
            section_map=section_map,
        )
    )

    for rule in rules:
        ev = _evidence_item(
            evidence_type="clinical_rule",
            display_name=rule["rule_name"],
            value=rule["result"],
            source_module="StrokeClawRuleEngine",
            source_record=rule["rule_id"],
            generated_at=generated_at,
            snippet=rule["clinical_meaning"],
        )
        ev_id = _append_unique_evidence(catalog, evidence_lookup, ev)
        rule["evidence_ids"] = list(
            dict.fromkeys([*rule["evidence_ids"], ev_id])
        )

    guideline_by_claim = _legacy_guideline_evidence(
        payload, catalog, evidence_lookup
    )

    missing: List[Dict[str, Any]] = []
    for field in patient_fields:
        if field["is_missing"]:
            missing.append(
                _issue(
                    issue_id=f"missing_{field['field_id']}",
                    field=field["field_id"],
                    status="missing",
                    message=f"{field['display_name']}缺失。",
                    impact="可能限制临床规则和风险评估。",
                    recommended_action=f"请核对并补充{field['display_name']}。",
                    severity="medium",
                )
            )
    for metric in metrics:
        if metric["status"] == "missing" and not safety_blocked:
            missing.append(
                _issue(
                    issue_id=f"missing_{metric['metric_id']}",
                    field=metric["metric_id"],
                    status="missing",
                    message=f"{metric['display_name']}缺失。",
                    impact="无法完成相应灌注定量评估。",
                    recommended_action="请核对分析任务和原始灌注图。",
                    severity="medium",
                )
            )
    if not ncct_label:
        missing.append(
            _issue(
                issue_id="missing_ncct_classification",
                field="ncct_classification",
                status="missing",
                message="NCCT 分类结果缺失。",
                impact="无法确认 NCCT 分类模型输出。",
                recommended_action="请结合原始 NCCT 和三分类任务结果复核。",
                severity="medium",
            )
        )
    if not vessel_ev_id and not safety_blocked:
        missing.append(
            _issue(
                issue_id="missing_vessel_occlusion_class",
                field="vessel_occlusion_class",
                status="missing",
                message="血管闭塞分类结果缺失。",
                impact="无法完整评估大血管闭塞证据和血管内治疗条件。",
                recommended_action="结合原始 CTA/MRA 或后续血管影像进一步确认。",
                severity="high",
            )
        )

    warnings: List[Dict[str, Any]] = []
    for finding in _as_list(_as_dict(icv or payload.get("icv")).get("findings")):
        if not isinstance(finding, dict):
            continue
        status = str(finding.get("status") or "").lower()
        if status not in {"warn", "fail"}:
            continue
        warnings.append(
            _issue(
                issue_id=f"icv_{finding.get('id') or len(warnings) + 1}",
                field=str(finding.get("id") or "icv"),
                status="conflict" if status == "fail" else "warning",
                message=str(finding.get("message") or "内部一致性校验提示异常。"),
                impact="可能影响报告结论可信度。",
                recommended_action=str(
                    finding.get("suggested_action") or "请复核源数据和分析结果。"
                ),
                severity="high" if status == "fail" else "medium",
            )
        )
    consensus_payload = _as_dict(consensus or payload.get("consensus"))
    for index, conflict in enumerate(_as_list(consensus_payload.get("conflicts"))):
        if not isinstance(conflict, dict):
            continue
        warnings.append(
            _issue(
                issue_id=f"consensus_conflict_{index + 1}",
                field=str(conflict.get("claim_id") or "consensus"),
                status="conflict",
                message=str(
                    conflict.get("message")
                    or conflict.get("summary")
                    or "多个模块结果存在冲突。"
                ),
                impact="冲突未解决前不能形成确定性临床结论。",
                recommended_action=str(
                    conflict.get("suggested_action") or "请由临床医生人工裁决。"
                ),
                severity="high",
            )
        )
    for finding in imaging_findings:
        confidence = finding.get("confidence")
        if confidence is not None and confidence < 0.5:
            warnings.append(
                _issue(
                    issue_id=f"low_confidence_{finding['finding_id']}",
                    field=finding["finding_id"],
                    status="low_confidence",
                    message=f"{finding['display_name']}模型置信度较低。",
                    impact="该模型输出不能单独支持临床判断。",
                    recommended_action="请结合原始影像和人工阅片复核。",
                    severity="medium",
                )
            )
    if safety_blocked:
        warnings.append(
            _issue(
                issue_id="ncct_safety_gate_blocked",
                field="ncct_classification",
                status="review_required",
                message=str(
                    safety_gate.get("reason")
                    or "NCCT 三分类提示疑似脑出血，已阻断后续分析。"
                ),
                impact="不能继续使用缺血性卒中灌注链形成治疗判断。",
                recommended_action="请医生复核原始 NCCT 并完成强制签核。",
                severity="high",
            )
        )

    mismatch_rule = next(
        rule for rule in rules if rule["rule_id"] == "CTP_MISMATCH_RATIO_1_8_V1"
    )
    core_rule = next(
        rule for rule in rules if rule["rule_id"] == "CTP_CORE_VOLUME_70ML_V1"
    )
    time_rule = next(
        rule
        for rule in rules
        if rule["rule_id"] == "ONSET_TO_ADMISSION_6H_V1"
    )
    guideline_ids = list(
        dict.fromkeys(
            guideline_by_claim.get("significant_mismatch", [])
            + guideline_by_claim.get("treatment_window_notice", [])
        )
    )
    bound_guideline_ids = [
        evidence_id
        for evidence_id in guideline_ids
        if _as_dict(evidence_lookup.get(evidence_id)).get("binding_status") == "bound"
    ]

    assessment: List[Dict[str, Any]] = []
    if mismatch_rule["result"] == "met":
        assessment.append(
            _claim(
                claim_id="claim_significant_mismatch",
                claim="灌注定量提示存在具有临床意义的不匹配。",
                claim_type="clinical_assessment",
                support_status="supported",
                evidence_ids=mismatch_rule["evidence_ids"] + bound_guideline_ids,
                limitations=[],
                section_map=section_map,
                review_domain="assessment",
            )
        )
    elif mismatch_rule["result"] == "not_met":
        assessment.append(
            _claim(
                claim_id="claim_no_significant_mismatch",
                claim="当前不匹配比值不支持显著灌注不匹配。",
                claim_type="clinical_assessment",
                support_status="supported",
                evidence_ids=mismatch_rule["evidence_ids"],
                limitations=[],
                section_map=section_map,
                review_domain="assessment",
            )
        )

    evt_inputs_available = (
        mismatch_rule["result"] == "met"
        and core_rule["result"] == "met"
        and time_rule["result"] in {"met", "not_met"}
    )
    if evt_inputs_available:
        evt_limitations = []
        evt_status = "supported"
        if not vessel_ev_id:
            evt_limitations.append("血管闭塞分类结果缺失。")
            evt_status = "partially_supported"
        if not bound_guideline_ids:
            evt_limitations.append("指南证据未绑定。")
            evt_status = "partially_supported"
        assessment.append(
            _claim(
                claim_id="claim_evt_further_evaluation",
                claim=(
                    "当前影像及时间窗信息提示患者可能具备进一步评估机械取栓的条件，"
                    "仍需结合责任血管、CTA/MRA、出血风险、基础状态及卒中团队意见综合判断。"
                ),
                claim_type="clinical_assessment",
                support_status=evt_status,
                evidence_ids=list(
                    dict.fromkeys(
                        mismatch_rule["evidence_ids"]
                        + core_rule["evidence_ids"]
                        + time_rule["evidence_ids"]
                        + ([vessel_ev_id] if vessel_ev_id else [])
                        + bound_guideline_ids
                    )
                ),
                limitations=evt_limitations,
                section_map=section_map,
                review_domain="assessment",
            )
        )

    recommendations = [
        {
            **_claim(
                claim_id="recommendation_clinician_review",
                claim="由卒中团队结合原始影像、禁忌证和患者基础状态完成最终临床决策。",
                claim_type="recommendation",
                support_status="supported",
                evidence_ids=[
                    item
                    for claim in assessment
                    for item in claim.get("evidence_ids", [])
                ],
                limitations=["本报告不能替代临床医生最终判断。"],
                section_map=section_map,
                review_domain="recommendation",
            ),
            "priority": "high",
            "action_type": "clinician_review",
        }
    ]
    if not vessel_ev_id:
        recommendations.append(
            {
                **_claim(
                    claim_id="recommendation_vessel_review",
                    claim="优先复核 CTA/MRA 责任血管及闭塞状态。",
                    claim_type="recommendation",
                    support_status="supported",
                    evidence_ids=[vessel_missing_ev_id],
                    limitations=["当前血管分类结果缺失。"],
                    section_map=section_map,
                    review_domain="recommendation",
                ),
                "priority": "high",
                "action_type": "additional_review",
            }
        )

    evidence_chain = assessment + recommendations
    existing_uncertainties = _collect_existing_uncertainties(payload)
    uncertainties = [
        _issue(
            issue_id=f"uncertainty_{index + 1}",
            field="report",
            status="uncertain",
            message=text,
            impact="可能影响报告结论的完整性。",
            recommended_action="请结合原始数据和临床信息复核。",
            severity="medium",
        )
        for index, text in enumerate(existing_uncertainties)
    ]
    unbound_guideline_count = sum(
        1
        for item in catalog
        if item.get("evidence_type") == "guideline"
        and item.get("binding_status") != "bound"
    )
    if unbound_guideline_count or (
        evt_inputs_available and not bound_guideline_ids
    ):
        uncertainties.append(
            _issue(
                issue_id="unbound_guideline_evidence",
                field="guideline_evidence",
                status="unbound",
                message="部分结论的指南证据未绑定。",
                impact="这些引用不能作为已核验的指南依据。",
                recommended_action="请补充经审核的文档、版本、章节和页码。",
                severity="medium",
            )
        )

    summary_lines = []
    if data["mismatch"] is not None:
        summary_lines.append(
            f"不匹配比值 {_format_number(data['mismatch'])}"
            + (
                " 高于内部规则阈值 1.80。"
                if mismatch_result == "met"
                else " 未高于内部规则阈值 1.80。"
            )
        )
    if data["core"] is not None and data["penumbra"] is not None:
        summary_lines.append(
            f"核心梗死体积 {_format_number(data['core'])} mL，"
            f"半暗带体积 {_format_number(data['penumbra'])} mL。"
        )
    if not vessel_ev_id:
        summary_lines.append("血管闭塞分类结果缺失，取栓相关判断必须进一步复核。")
    if not summary_lines:
        summary_lines.append("当前结构化数据不足，无法形成完整的确定性摘要。")

    report_lines = [
        str(item).strip()
        for item in _as_list(payload.get("summary_findings"))
        if str(item).strip()
    ][:3]
    question_answer = _as_dict(payload.get("question_answer"))
    baichuan_answer = (
        str(question_answer.get("direct_answer") or "").strip()
        if question_answer.get("llm_enhanced") is True
        else ""
    )
    ai_supplement = baichuan_answer or (
        " ".join(report_lines) if report_lines else None
    )
    claim_alias_map = {
        "significant_mismatch": "claim_significant_mismatch",
        "treatment_window_notice": "claim_evt_further_evaluation",
        "mismatch_ratio": "claim_significant_mismatch",
    }
    valid_claim_ids = {claim["claim_id"] for claim in assessment}
    ai_claim_ids = []
    for raw_claim_id in _as_list(question_answer.get("llm_claim_ids")):
        mapped_claim_id = claim_alias_map.get(
            str(raw_claim_id), str(raw_claim_id)
        )
        if mapped_claim_id in valid_claim_ids and mapped_claim_id not in ai_claim_ids:
            ai_claim_ids.append(mapped_claim_id)
    if ai_supplement:
        ev = _evidence_item(
            evidence_type="agent_reasoning",
            display_name="AI 综合影像说明",
            value=ai_supplement,
            source_module="Baichuan" if baichuan_answer else "Report_Generation",
            source_record=(
                "report_payload.question_answer"
                if baichuan_answer
                else "report_payload.summary_findings"
            ),
            generated_at=generated_at,
            binding_status="supplemental",
        )
        _append_unique_evidence(catalog, evidence_lookup, ev)

    bound_evidence_ids = {
        item["evidence_id"]
        for item in catalog
        if item.get("binding_status") == "bound"
        and item.get("evidence_type") != "agent_reasoning"
    }
    mapped_claims = sum(
        1
        for claim in evidence_chain
        if any(evidence_id in bound_evidence_ids for evidence_id in claim["evidence_ids"])
    )
    evidence_coverage = (
        round(mapped_claims / len(evidence_chain), 4) if evidence_chain else 1.0
    )

    risk_level = str(
        _as_dict(payload.get("final_report")).get("risk_level") or ""
    ).lower()
    if risk_level not in {"low", "medium", "high"}:
        if any(item["severity"] == "high" for item in warnings + missing):
            risk_level = "high"
        elif warnings or missing or uncertainties:
            risk_level = "medium"
        else:
            risk_level = "low"
    urgency = (
        "urgent"
        if risk_level == "high"
        else "attention"
        if risk_level == "medium"
        else "routine"
    )
    has_structured_fact = any(
        item.get("value") is not None
        for item in [*patient_fields, *metrics, *imaging_findings]
    )
    legacy_mode = not bool(
        patient_context
        or has_structured_fact
        or payload.get("final_report")
        or payload.get("evidence_items")
    ) and bool(legacy_report_text)

    field_review_map = {
        item["field_id"]: {
            "section_id": item["review_section_id"],
            "status": item["review_status"],
            "clinician_confirmed": item["clinician_confirmed"],
        }
        for item in patient_fields
    }
    field_review_map.update(
        {
            item["metric_id"]: {
                "section_id": item["review_section_id"],
                "status": item["review_status"],
                "clinician_confirmed": item["clinician_confirmed"],
            }
            for item in metrics
        }
    )
    claim_review_map = {
        item["claim_id"]: {
            "section_id": item["review_section_id"],
            "status": item["review_status"],
            "clinician_confirmed": item["clinician_confirmed"],
        }
        for item in evidence_chain
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "report_meta": {
            "schema_version": SCHEMA_VERSION,
            "report_id": _stable_id("report", run_id, file_id),
            "run_id": run_id or None,
            "file_id": file_id or None,
            "generated_at": generated_at,
            "risk_level": risk_level,
            "urgency": urgency,
            "requires_clinician_review": True,
            "review_status": (
                "confirmed" if review.get("all_confirmed") else "pending"
            ),
            "legacy_mode": legacy_mode,
            "evidence_coverage": evidence_coverage,
        },
        "patient_summary": {"fields": patient_fields},
        "clinical_context": {
            "available_modalities": modalities,
            "hemisphere": data["hemisphere"],
            "fields": [],
        },
        "quality_control": _as_dict(payload.get("quality_control_result")),
        "imaging_findings": imaging_findings,
        "quantitative_metrics": metrics,
        "rule_evaluations": rules,
        "evidence_chain": evidence_chain,
        "evidence_catalog": catalog,
        "clinical_assessment": assessment,
        "recommendations": recommendations,
        "warnings": warnings,
        "missing_information": missing,
        "uncertainties": uncertainties,
        "narrative_summary": {
            "deterministic_summary": " ".join(summary_lines),
            "ai_supplement": ai_supplement,
            "generation_mode": (
                "deterministic_with_ai_supplement"
                if ai_supplement
                else "deterministic"
            ),
            "claim_ids": ai_claim_ids,
            "legacy_text": legacy_report_text if legacy_mode else None,
        },
        "clinician_review": {
            "overall_status": (
                "confirmed" if review.get("all_confirmed") else "pending"
            ),
            "sections": _as_list(review.get("sections")),
            "field_confirmation_map": field_review_map,
            "claim_confirmation_map": claim_review_map,
            "updated_at": review.get("updated_at")
            or payload.get("review_updated_at"),
        },
    }


def ensure_structured_report_v2(
    report_payload: Optional[Dict[str, Any]],
    *,
    run_id: str = "",
    file_id: str = "",
    patient_context: Optional[Dict[str, Any]] = None,
    legacy_report_text: str = "",
) -> Dict[str, Any]:
    payload = dict(_as_dict(report_payload))
    payload["structured_report_v2"] = build_structured_report_v2(
        run_id=run_id,
        file_id=file_id,
        report_payload=payload,
        patient_context=patient_context,
        icv=_as_dict(payload.get("icv")),
        ekv=_as_dict(payload.get("ekv")),
        consensus=_as_dict(payload.get("consensus")),
        review_state=_as_dict(payload.get("review_state")),
        legacy_report_text=legacy_report_text,
    )
    return payload
