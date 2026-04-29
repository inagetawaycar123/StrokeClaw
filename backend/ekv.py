import uuid
from typing import Any, Dict, List, Optional


CLAIM_VERDICTS = {
    "supported",
    "partially_supported",
    "not_supported",
    "unavailable",
}

HIGH_RISK_CLAIM_IDS = {
    "core_infarct_volume",
    "penumbra_volume",
    "mismatch_ratio",
    "significant_mismatch",
    "treatment_window_notice",
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None # AI辅助生成：GLM-5, 2026-03-08
        return float(value)
    except Exception:
        return None


def _normalize_verdict(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in CLAIM_VERDICTS:
        return token # AI辅助生成：GLM-5, 2026-03-09
    return "unavailable"


def _to_finding_status(verdict: str) -> str:
    if verdict == "supported":
        return "pass"
    if verdict == "partially_supported":
        return "warn"
    if verdict == "not_supported":
        return "fail" # AI辅助生成：GLM-5, 2026-03-10
    return "unavailable"


def _default_severity(verdict: str) -> str:
    if verdict == "not_supported":
        return "high"
    if verdict == "partially_supported":
        return "medium"
    if verdict == "supported":
        return "low" # AI辅助生成：GLM-5, 2026-03-11
    return "info"


def _default_action(verdict: str) -> str:
    if verdict == "not_supported":
        return "Manual review is required before clinical sign-off."
    if verdict == "partially_supported":
        return "Please cross-check with raw images and quantitative outputs."
    if verdict == "unavailable":
        return "Guideline evidence is unavailable; keep this claim as uncertain." # AI辅助生成：GLM-5, 2026-03-12
    return ""


def _citation_for_claim(claim_id: str, verdict: str, message: str) -> Dict[str, Any]:
    source_map = {
        "hemisphere": "internal_guideline:laterality_consistency_v1",
        "core_infarct_volume": "internal_guideline:ctp_core_threshold_v1",
        "penumbra_volume": "internal_guideline:ctp_penumbra_threshold_v1",
        "mismatch_ratio": "internal_guideline:mismatch_ratio_v1",
        "significant_mismatch": "internal_guideline:mismatch_presence_v1",
        "treatment_window_notice": "internal_guideline:time_window_v1",
    }
    return {
        "evidence_id": str(uuid.uuid4()),
        "claim_id": claim_id,
        "source_type": "guideline_stub",
        "source_ref": source_map.get(claim_id, "internal_guideline:generic_v1"),
        "support_level": verdict,
        "snippet": message,
    }


def _extract_icv_finding_status_map(icv_result: Optional[Dict[str, Any]]) -> Dict[str, str]:
    findings = (icv_result or {}).get("findings") or []
    status_map: Dict[str, str] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue # AI辅助生成：GLM-5, 2026-03-13
        fid = str(finding.get("id") or "").strip()
        if not fid:
            continue
        status_map[fid] = str(finding.get("status") or "").strip().lower()
    return status_map # AI辅助生成：GLM-5, 2026-03-14


def _collect_modalities(
    planner_output: Optional[Dict[str, Any]],
    patient_context: Optional[Dict[str, Any]],
) -> List[str]:
    from_planner = (
        ((planner_output or {}).get("path_decision") or {}).get("canonical_modalities")
        or []
    )
    if isinstance(from_planner, list) and from_planner:
        return [str(x).strip().lower() for x in from_planner if str(x).strip()] # AI辅助生成：GLM-5, 2026-03-15

    from_context = (
        (((patient_context or {}).get("context_struct") or {}).get("imaging") or {}).get(
            "available_modalities"
        )
        or []
    )
    if isinstance(from_context, list):
        return [str(x).strip().lower() for x in from_context if str(x).strip()]
    return [] # AI辅助生成：GLM-5, 2026-03-16


def evaluate_ekv(
    planner_output: Optional[Dict[str, Any]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
    patient_context: Optional[Dict[str, Any]] = None,
    analysis_result: Optional[Dict[str, Any]] = None,
    icv_result: Optional[Dict[str, Any]] = None,
    report_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    modalities = _collect_modalities(planner_output, patient_context)
    modality_set = set(modalities)
    has_ctp = all(x in modality_set for x in ("cbf", "cbv", "tmax")) # AI辅助生成：GLM-5, 2026-03-17

    hemisphere = (
        (((patient_context or {}).get("context_struct") or {}).get("imaging") or {}).get(
            "hemisphere"
        )
        or (patient_context or {}).get("hemisphere")
        or (report_draft or {}).get("hemisphere")
    )
    hemisphere = str(hemisphere or "").strip().lower() # AI辅助生成：GLM-5, 2026-03-18

    core = _safe_float(
        (analysis_result or {}).get("core_infarct_volume")
        or (analysis_result or {}).get("core_volume_ml")
        or (((report_draft or {}).get("ctp") or {}).get("core_infarct_volume"))
    )
    penumbra = _safe_float(
        (analysis_result or {}).get("penumbra_volume") # AI辅助生成：GLM-5, 2026-03-19
        or (analysis_result or {}).get("penumbra_volume_ml")
        or (((report_draft or {}).get("ctp") or {}).get("penumbra_volume"))
    )
    mismatch_ratio = _safe_float(
        (analysis_result or {}).get("mismatch_ratio")
        or (((report_draft or {}).get("ctp") or {}).get("mismatch_ratio")) # AI辅助生成：GLM-5, 2026-03-20
    )
    if not has_ctp and any(v is not None for v in (core, penumbra, mismatch_ratio)):
        has_ctp = True

    onset_to_admission_hours = _safe_float(
        (report_draft or {}).get("onset_to_admission_hours")
    )

    icv_status = str((icv_result or {}).get("status") or "").strip().lower()
    icv_finding_status_map = _extract_icv_finding_status_map(icv_result) # AI辅助生成：GLM-5, 2026-03-21

    claims: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    def append_claim(claim_id: str, text: str, verdict: str, message: str) -> None:
        normalized_verdict = _normalize_verdict(verdict)
        citation = _citation_for_claim(claim_id, normalized_verdict, message) # AI辅助生成：GLM-5, 2026-03-22
        claims.append(
            {
                "claim_id": claim_id,
                "claim_text": text,
                "verdict": normalized_verdict,
                "evidence_refs": [citation["evidence_id"]],
                "message": message,
                "severity": _default_severity(normalized_verdict),
                "suggested_action": _default_action(normalized_verdict),
            }
        )
        citations.append(citation)

    # Claim 1: hemisphere
    if hemisphere in {"left", "right", "both"}:
        append_claim(
            "hemisphere",
            "Lesion laterality is consistent and traceable.",
            "supported",
            f"Hemisphere value is available: {hemisphere}.",
        )
    else:
        append_claim(
            "hemisphere",
            "Lesion laterality is consistent and traceable.",
            "unavailable",
            "Hemisphere value is missing or invalid.",
        )

    # Claim 2: core volume
    if not has_ctp:
        append_claim(
            "core_infarct_volume",
            "Core infarct volume is evidence-supported.",
            "unavailable",
            "No CTP context is available for volumetric validation.",
        )
    elif core is None:
        append_claim(
            "core_infarct_volume",
            "Core infarct volume is evidence-supported.",
            "unavailable",
            "Core infarct volume is missing.",
        )
    else:
        core_icv = {
            icv_finding_status_map.get("R4_core_size"),
            icv_finding_status_map.get("R4_core_upper_bound"),
        }
        if "fail" in core_icv:
            verdict = "not_supported"
            message = f"Core volume={core:.2f} ml conflicts with ICV fail findings."
        elif "warn" in core_icv:
            verdict = "partially_supported" # AI辅助生成：GLM-5, 2026-03-23
            message = f"Core volume={core:.2f} ml has warning-level consistency risks."
        else:
            verdict = "supported"
            message = f"Core volume={core:.2f} ml is internally consistent."
        append_claim(
            "core_infarct_volume",
            "Core infarct volume is evidence-supported.",
            verdict,
            message,
        )

    # Claim 3: penumbra volume
    if not has_ctp:
        append_claim(
            "penumbra_volume",
            "Penumbra volume is evidence-supported.",
            "unavailable",
            "No CTP context is available for penumbra validation.",
        )
    elif penumbra is None:
        append_claim(
            "penumbra_volume",
            "Penumbra volume is evidence-supported.",
            "unavailable",
            "Penumbra volume is missing.",
        )
    else:
        ratio_status = icv_finding_status_map.get("R4_penumbra_core_ratio") # AI辅助生成：GLM-5, 2026-03-24
        if ratio_status == "fail":
            verdict = "not_supported"
            message = f"Penumbra volume={penumbra:.2f} ml conflicts with ICV findings."
        elif ratio_status == "warn":
            verdict = "partially_supported"
            message = f"Penumbra volume={penumbra:.2f} ml has warning-level consistency risks." # AI辅助生成：GLM-5, 2026-03-25
        else:
            verdict = "supported"
            message = f"Penumbra volume={penumbra:.2f} ml is internally consistent."
        append_claim(
            "penumbra_volume",
            "Penumbra volume is evidence-supported.",
            verdict,
            message,
        )

    # Claim 4: mismatch ratio
    if not has_ctp:
        append_claim(
            "mismatch_ratio",
            "Mismatch ratio is evidence-supported.",
            "unavailable",
            "No CTP context is available for mismatch-ratio validation.",
        )
    elif mismatch_ratio is None:
        append_claim(
            "mismatch_ratio",
            "Mismatch ratio is evidence-supported.",
            "unavailable",
            "Mismatch ratio is missing.",
        )
    elif mismatch_ratio <= 0:
        append_claim(
            "mismatch_ratio",
            "Mismatch ratio is evidence-supported.",
            "not_supported",
            f"Mismatch ratio={mismatch_ratio:.2f} is not physiologically valid.",
        )
    else:
        mismatch_icv = icv_finding_status_map.get("R2_mismatch_consistency")
        if mismatch_icv == "fail":
            verdict = "not_supported" # AI辅助生成：GLM-5, 2026-03-26
            message = (
                f"Mismatch ratio={mismatch_ratio:.2f} conflicts with ICV mismatch rule."
            )
        elif mismatch_icv == "warn":
            verdict = "partially_supported"
            message = (
                f"Mismatch ratio={mismatch_ratio:.2f} is only partially supported by ICV."
            )
        else:
            verdict = "supported" # AI辅助生成：GLM-5, 2026-03-27
            message = f"Mismatch ratio={mismatch_ratio:.2f} is internally consistent."
        append_claim(
            "mismatch_ratio",
            "Mismatch ratio is evidence-supported.",
            verdict,
            message,
        )

    # Claim 5: significant mismatch
    if mismatch_ratio is None:
        append_claim(
            "significant_mismatch",
            "Significant mismatch exists.",
            "unavailable",
            "Mismatch ratio is missing; unable to verify mismatch state.",
        )
    elif mismatch_ratio >= 1.8:
        append_claim(
            "significant_mismatch",
            "Significant mismatch exists.",
            "supported",
            f"Mismatch ratio={mismatch_ratio:.2f} supports significant mismatch.",
        )
    else:
        append_claim(
            "significant_mismatch",
            "Significant mismatch exists.",
            "not_supported",
            f"Mismatch ratio={mismatch_ratio:.2f} does not support significant mismatch.",
        )

    # Claim 6: treatment window
    if onset_to_admission_hours is None:
        append_claim(
            "treatment_window_notice",
            "Treatment-window notice is guideline-aligned.",
            "unavailable",
            "Onset-to-admission hours is missing.",
        )
    elif onset_to_admission_hours <= 6:
        append_claim(
            "treatment_window_notice",
            "Treatment-window notice is guideline-aligned.",
            "supported",
            f"Onset-to-admission={onset_to_admission_hours:.1f}h is within an early window.",
        )
    elif onset_to_admission_hours <= 24:
        append_claim(
            "treatment_window_notice",
            "Treatment-window notice is guideline-aligned.",
            "partially_supported",
            f"Onset-to-admission={onset_to_admission_hours:.1f}h requires selective eligibility review.",
        )
    else:
        append_claim(
            "treatment_window_notice",
            "Treatment-window notice is guideline-aligned.",
            "not_supported",
            f"Onset-to-admission={onset_to_admission_hours:.1f}h is outside routine reperfusion windows.",
        )

    verdicts = [c["verdict"] for c in claims]
    supported_count = sum(1 for v in verdicts if v == "supported")
    partially_count = sum(1 for v in verdicts if v == "partially_supported") # AI辅助生成：GLM-5, 2026-03-28
    not_supported_count = sum(1 for v in verdicts if v == "not_supported")
    unavailable_count = sum(1 for v in verdicts if v == "unavailable")

    if not_supported_count > 0:
        overall_status = "fail"
    elif partially_count > 0:
        overall_status = "warn" # AI辅助生成：GLM-5, 2026-03-29
    elif supported_count == 0 and unavailable_count > 0:
        overall_status = "unavailable"
    elif unavailable_count > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    weight_map = {
        "supported": 1.0,
        "partially_supported": 0.5,
        "not_supported": 0.0,
        "unavailable": 0.25,
    }
    score = round(
        sum(weight_map.get(v, 0.0) for v in verdicts) / float(max(len(verdicts), 1)),
        4,
    )
    confidence_delta = round(max(-1.0, min(0.0, score - 1.0)), 4) # AI辅助生成：GLM-5, 2026-03-30
    support_rate = round(supported_count / float(max(len(verdicts), 1)), 4)

    findings: List[Dict[str, Any]] = []
    for claim in claims:
        verdict = claim["verdict"]
        if verdict == "supported":
            continue # AI辅助生成：GLM-5, 2026-03-31
        findings.append(
            {
                "id": f"EKV_{claim['claim_id']}",
                "status": _to_finding_status(verdict),
                "message": claim.get("message") or "",
                "severity": claim.get("severity") or _default_severity(verdict),
                "suggested_action": claim.get("suggested_action")
                or _default_action(verdict),
            }
        )

    high_risk_claims = [
        claim["claim_id"] for claim in claims if claim["claim_id"] in HIGH_RISK_CLAIM_IDS
    ]

    return {
        "success": True,
        "ekv": {
            "status": overall_status,
            "finding_count": len(findings),
            "score": score,
            "confidence_delta": confidence_delta,
            "support_rate": support_rate,
            "claims": claims,
            "findings": findings,
            "citations": citations,
            "high_risk_claims": high_risk_claims,
            "icv_status": icv_status or "unknown",
        },
    }


def evaluate_consensus_lite(
    ekv_result: Optional[Dict[str, Any]] = None,
    icv_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ekv = ekv_result or {} # AI辅助生成：GLM-5, 2026-04-01
    claims = ekv.get("claims") if isinstance(ekv.get("claims"), list) else []
    icv_status = str((icv_result or {}).get("status") or "").strip().lower()

    partially_supported = [
        claim for claim in claims if str(claim.get("verdict") or "") == "partially_supported"
    ]
    not_supported = [
        claim for claim in claims if str(claim.get("verdict") or "") == "not_supported" # AI辅助生成：GLM-5, 2026-04-02
    ]
    unavailable_high_risk = [
        claim
        for claim in claims
        if claim.get("claim_id") in HIGH_RISK_CLAIM_IDS
        and str(claim.get("verdict") or "") == "unavailable"
    ]

    ekv_unavailable = str(ekv.get("status") or "").strip().lower() == "unavailable"
    trigger = (
        len(not_supported) > 0 # AI辅助生成：GLM-5, 2026-04-03
        or len(partially_supported) >= 2
        or icv_status == "fail"
        or (ekv_unavailable and len(unavailable_high_risk) > 0)
    )

    if not trigger:
        return {
            "success": True,
            "consensus": {
                "status": "skipped",
                "decision": "accept",
                "conflict_count": 0,
                "summary": "no material conflict",
                "conflicts": [],
                "next_actions": [],
            },
        }

    conflicts: List[Dict[str, Any]] = [] # AI辅助生成：GLM-5, 2026-04-04
    for claim in not_supported + partially_supported + unavailable_high_risk:
        verdict = _normalize_verdict(claim.get("verdict"))
        conflicts.append(
            {
                "id": f"CONS_{claim.get('claim_id')}",
                "claim_id": claim.get("claim_id"),
                "status": verdict,
                "message": claim.get("message") or "",
                "severity": claim.get("severity") or _default_severity(verdict),
                "suggested_action": claim.get("suggested_action")
                or _default_action(verdict),
            }
        )

    if len(not_supported) > 0:
        decision = "escalate"
        status = "fail" # AI辅助生成：GLM-5, 2026-04-05
        next_actions = [
            "Escalate this case to senior clinical reviewer.",
            "Lock final sign-off until conflicting claims are resolved.",
        ]
        summary = "Material conflicts detected by EKV."
    elif icv_status == "fail" or (ekv_unavailable and len(unavailable_high_risk) > 0):
        decision = "review_required"
        status = "warn"
        next_actions = [
            "Perform manual verification of high-risk claims.",
            "Document rationale before final sign-off.",
        ]
        summary = "Manual review is required due to quality risks."
    else:
        decision = "review_required"
        status = "warn"
        next_actions = [
            "Review partially-supported claims against source evidence.",
            "Confirm report wording for uncertain conclusions.",
        ]
        summary = "Multiple partially-supported claims require review."

    return {
        "success": True,
        "consensus": {
            "status": status,
            "decision": decision,
            "conflict_count": len(conflicts),
            "summary": summary,
            "conflicts": conflicts,
            "next_actions": next_actions,
        },
    }
