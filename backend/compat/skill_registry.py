from __future__ import annotations

import copy
from typing import Dict, List, Optional


SKILL_REGISTRY: List[Dict[str, object]] = [
    {
        "skill_id": "SKILL_IMG_QC",
        "skill_name": "image_quality_control",
        "skill_type": "quality_control",
        "owner_agent": "Imaging Executor",
        "clinical_task": "image_input_validation",
        "required_input": ["case_id", "available_modalities"],
        "main_output": ["qc_status", "qc_score", "qc_review_required"],
        "confidence_method": "rule_based_quality_score",
        "confidence_threshold": 0.8,
        "failure_strategy": "block_if_ncct_missing_or_unreadable",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_MODALITY_ID",
        "skill_name": "modality_identification",
        "skill_type": "preprocess",
        "owner_agent": "Triage Planner",
        "clinical_task": "detect_input_modalities",
        "required_input": ["uploaded_files"],
        "main_output": ["available_modalities", "missing_modalities"],
        "confidence_method": "filename_and_metadata_rule",
        "confidence_threshold": 0.9,
        "failure_strategy": "continue_with_detected_modalities",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": False,
    },
    {
        "skill_id": "SKILL_NCCT_TRIAGE",
        "skill_name": "ncct_three_class_triage",
        "skill_type": "algorithm",
        "owner_agent": "Imaging Executor",
        "clinical_task": "ncct_normal_hemorrhage_ischemia",
        "required_input": ["ncct_series"],
        "main_output": ["predicted_label", "confidence_score", "heatmap_uri"],
        "confidence_method": "softmax_top1_probability",
        "confidence_threshold": 0.75,
        "failure_strategy": "continue_with_warning_and_review",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_VESSEL_OCCLUSION",
        "skill_name": "vessel_occlusion_three_class",
        "skill_type": "algorithm",
        "owner_agent": "Imaging Executor",
        "clinical_task": "vessel_occlusion_detection",
        "required_input": ["cta_or_mcta_series"],
        "main_output": ["predicted_label", "occlusion_segment", "confidence_score"],
        "confidence_method": "softmax_top1_probability_plus_margin",
        "confidence_threshold": 0.7,
        "failure_strategy": "fallback_to_manual_review",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_PSEUDO_CTP",
        "skill_name": "pseudo_ctp_generation",
        "skill_type": "algorithm",
        "owner_agent": "Imaging Executor",
        "clinical_task": "generate_perfusion_maps",
        "required_input": ["ncct_series", "cta_or_mcta_series"],
        "main_output": ["cbf_map_uri", "cbv_map_uri", "tmax_map_uri"],
        "confidence_method": "input_completeness_and_generation_quality",
        "confidence_threshold": 0.75,
        "failure_strategy": "use_available_ctp_or_skip_with_warning",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_STROKE_ANALYSIS",
        "skill_name": "stroke_auto_analysis",
        "skill_type": "algorithm",
        "owner_agent": "Imaging Executor",
        "clinical_task": "core_penumbra_mismatch_analysis",
        "required_input": ["perfusion_maps_or_ctp"],
        "main_output": ["core_volume_ml", "penumbra_volume_ml", "mismatch_ratio"],
        "confidence_method": "segmentation_quality_and_threshold_stability",
        "confidence_threshold": 0.75,
        "failure_strategy": "show_partial_quantification_and_review",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_INTERNAL_CHECK",
        "skill_name": "internal_consistency_check",
        "skill_type": "validation",
        "owner_agent": "Logic Reviewer",
        "clinical_task": "cross_result_consistency",
        "required_input": ["algorithm_results", "report_sections"],
        "main_output": ["conflict_status", "conflict_items", "blocking_required"],
        "confidence_method": "rule_coverage",
        "confidence_threshold": 0.8,
        "failure_strategy": "require_review_for_high_severity_conflict",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_GUIDELINE_CHECK",
        "skill_name": "external_guideline_check",
        "skill_type": "validation",
        "owner_agent": "Guideline Fact Agent",
        "clinical_task": "guideline_and_evidence_alignment",
        "required_input": ["claims", "evidence_items"],
        "main_output": ["guideline_support_level", "unsupported_claims"],
        "confidence_method": "evidence_completeness",
        "confidence_threshold": 0.8,
        "failure_strategy": "continue_with_evidence_gap_warning",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_REPORT_GEN",
        "skill_name": "structured_report_generation",
        "skill_type": "generation",
        "owner_agent": "Clinical Summary Agent",
        "clinical_task": "draft_structured_stroke_report",
        "required_input": ["case_context", "algorithm_results", "evidence_items"],
        "main_output": ["report_text", "report_sections", "evidence_bindings"],
        "confidence_method": "evidence_completeness_not_llm_confidence",
        "confidence_threshold": 0.85,
        "failure_strategy": "draft_only_until_reviewed",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": True,
    },
    {
        "skill_id": "SKILL_AI_QA",
        "skill_name": "clinical_ai_qa",
        "skill_type": "qa",
        "owner_agent": "Evidence Agent",
        "clinical_task": "case_grounded_question_answering",
        "required_input": ["question", "case_context", "evidence_items"],
        "main_output": ["answer", "answer_evidence_ledger"],
        "confidence_method": "answer_evidence_coverage",
        "confidence_threshold": 0.8,
        "failure_strategy": "answer_with_limitations_or_refuse",
        "version": "0.1.0",
        "status": "active",
        "doctor_review_required": False,
    },
]


TOOL_TO_SKILL_ID = {
    "detect_modalities": "SKILL_MODALITY_ID",
    "load_patient_context": "SKILL_IMG_QC",
    "three_class": "SKILL_NCCT_TRIAGE",
    "ncct_triage": "SKILL_NCCT_TRIAGE",
    "run_ncct_classification": "SKILL_NCCT_TRIAGE",
    "vessel_occlusion": "SKILL_VESSEL_OCCLUSION",
    "run_vessel_occlusion_classification": "SKILL_VESSEL_OCCLUSION",
    "generate_ctp_maps": "SKILL_PSEUDO_CTP",
    "ctp_generate": "SKILL_PSEUDO_CTP",
    "run_stroke_analysis": "SKILL_STROKE_ANALYSIS",
    "icv": "SKILL_INTERNAL_CHECK",
    "consensus_lite": "SKILL_INTERNAL_CHECK",
    "ekv": "SKILL_GUIDELINE_CHECK",
    "generate_medgemma_report": "SKILL_REPORT_GEN",
    "clinical_ai_qa": "SKILL_AI_QA",
}


def get_skill_registry() -> List[Dict[str, object]]:
    return copy.deepcopy(SKILL_REGISTRY)


def get_skill_by_id(skill_id: str) -> Optional[Dict[str, object]]:
    key = str(skill_id or "").strip()
    for item in SKILL_REGISTRY:
        if item.get("skill_id") == key:
            return copy.deepcopy(item)
    return None


def skill_id_for_tool(tool_name: str) -> str:
    key = str(tool_name or "").strip()
    return TOOL_TO_SKILL_ID.get(key, "SKILL_UNKNOWN")
