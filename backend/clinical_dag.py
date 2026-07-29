"""Server-owned clinical DAG descriptions for pre-execution review.

The descriptor intentionally contains metadata only.  It does not execute
models, Agent tools, or the inactive collateral-circulation capability.
"""

from __future__ import annotations

import copy
from typing import Dict, Iterable, List


MODALITY_ALIASES = {
    "mcat": "mcta",
    "vcat": "vcta",
    "dcat": "dcta",
}
VALID_MODALITIES = frozenset({"ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"})


def normalize_modalities(modalities: Iterable[object] | None) -> List[str]:
    """Return unique canonical modality names in their original order."""

    normalized: List[str] = []
    for item in modalities or []:
        raw = str(item or "").strip().lower()
        key = MODALITY_ALIASES.get(raw, raw)
        if key and key not in normalized:
            normalized.append(key)
    return normalized


def _node(
    node_id: str,
    title: str,
    *,
    agent: str,
    skill_id: str,
    status: str = "planned",
    doctor_review_required: bool = False,
) -> Dict[str, object]:
    return {
        "id": node_id,
        "title": title,
        "agent": agent,
        "skill_id": skill_id,
        "status": status,
        "active": status != "inactive",
        "doctor_review_required": doctor_review_required,
    }


BASE_NODES = {
    "image_qc": _node(
        "image_qc",
        "影像输入质控",
        agent="Imaging Executor",
        skill_id="SKILL_IMG_QC",
        doctor_review_required=True,
    ),
    "ncct_triage": _node(
        "ncct_triage",
        "NCCT 三分类与出血门控",
        agent="Imaging Executor",
        skill_id="SKILL_NCCT_TRIAGE",
        doctor_review_required=True,
    ),
    "vessel_occlusion": _node(
        "vessel_occlusion",
        "血管闭塞三分类",
        agent="Imaging Executor",
        skill_id="SKILL_VESSEL_OCCLUSION",
        doctor_review_required=True,
    ),
    "pseudo_ctp": _node(
        "pseudo_ctp",
        "生成 CBF / CBV / Tmax",
        agent="Imaging Executor",
        skill_id="SKILL_PSEUDO_CTP",
        doctor_review_required=True,
    ),
    "ctp_review": _node(
        "ctp_review",
        "使用已上传真实 CTP",
        agent="Imaging Executor",
        skill_id="SKILL_IMG_QC",
        doctor_review_required=True,
    ),
    "collateral_score": _node(
        "collateral_score",
        "侧支循环评估（能力预留）",
        agent="Vascular Agent",
        skill_id="SKILL_COLLATERAL_SCORE",
        status="inactive",
        doctor_review_required=True,
    ),
    "stroke_analysis": _node(
        "stroke_analysis",
        "缺血核心 / 半暗带量化",
        agent="Imaging Executor",
        skill_id="SKILL_STROKE_ANALYSIS",
        doctor_review_required=True,
    ),
    "internal_check": _node(
        "internal_check",
        "院内一致性核验",
        agent="Logic Reviewer",
        skill_id="SKILL_INTERNAL_CHECK",
        doctor_review_required=True,
    ),
    "guideline_check": _node(
        "guideline_check",
        "指南证据核验",
        agent="Guideline Fact Agent",
        skill_id="SKILL_GUIDELINE_CHECK",
        doctor_review_required=True,
    ),
    "report": _node(
        "report",
        "百川 M3 结构化报告",
        agent="Clinical Summary Agent",
        skill_id="SKILL_REPORT_GEN",
        doctor_review_required=True,
    ),
}


PATH_CONFIGS = {
    "ncct_only": {
        "label": "NCCT-only",
        "note": "仅执行 NCCT 分诊、安全核验和报告；不执行血管或灌注分析。",
        "columns": [["image_qc"], ["ncct_triage"], ["internal_check", "guideline_check"], ["report"]],
        "edges": [
            ("image_qc", "ncct_triage"),
            ("ncct_triage", "internal_check"),
            ("ncct_triage", "guideline_check"),
            ("internal_check", "report"),
            ("guideline_check", "report"),
        ],
    },
    "ncct_single_phase_cta": {
        "label": "NCCT + 单期 CTA",
        "note": "执行 NCCT 分诊与血管闭塞分类；不生成伪 CTP 或执行灌注量化。",
        "columns": [
            ["image_qc"],
            ["ncct_triage"],
            ["vessel_occlusion"],
            ["internal_check", "guideline_check"],
            ["report"],
        ],
        "edges": [
            ("image_qc", "ncct_triage"),
            ("ncct_triage", "vessel_occlusion"),
            ("vessel_occlusion", "internal_check"),
            ("vessel_occlusion", "guideline_check"),
            ("internal_check", "report"),
            ("guideline_check", "report"),
        ],
    },
    "ncct_mcta": {
        "label": "NCCT + 三期 mCTA",
        "note": "审批后串行生成 CBF/CBV/Tmax；侧支循环节点仅为 inactive 能力展示。",
        "columns": [
            ["image_qc"],
            ["ncct_triage"],
            ["vessel_occlusion", "pseudo_ctp"],
            ["collateral_score", "stroke_analysis"],
            ["internal_check", "guideline_check"],
            ["report"],
        ],
        "edges": [
            ("image_qc", "ncct_triage"),
            ("ncct_triage", "vessel_occlusion"),
            ("ncct_triage", "pseudo_ctp"),
            ("vessel_occlusion", "collateral_score"),
            ("pseudo_ctp", "stroke_analysis"),
            ("collateral_score", "internal_check"),
            ("stroke_analysis", "internal_check"),
            ("stroke_analysis", "guideline_check"),
            ("internal_check", "report"),
            ("guideline_check", "report"),
        ],
    },
    "ncct_mcta_ctp": {
        "label": "NCCT + 三期 mCTA + 真实 CTP",
        "note": "使用上传的 CBF/CBV/Tmax，跳过伪 CTP 生成；侧支循环节点不会执行算法。",
        "columns": [
            ["image_qc"],
            ["ncct_triage"],
            ["vessel_occlusion", "ctp_review"],
            ["collateral_score", "stroke_analysis"],
            ["internal_check", "guideline_check"],
            ["report"],
        ],
        "edges": [
            ("image_qc", "ncct_triage"),
            ("ncct_triage", "vessel_occlusion"),
            ("ncct_triage", "ctp_review"),
            ("vessel_occlusion", "collateral_score"),
            ("ctp_review", "stroke_analysis"),
            ("collateral_score", "internal_check"),
            ("stroke_analysis", "internal_check"),
            ("stroke_analysis", "guideline_check"),
            ("internal_check", "report"),
            ("guideline_check", "report"),
        ],
    },
}


def _path_for_modalities(modality_set: set[str]) -> str | None:
    if {"ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"}.issubset(modality_set):
        return "ncct_mcta_ctp"
    if {"ncct", "mcta", "vcta", "dcta"}.issubset(modality_set):
        return "ncct_mcta"
    single_phase_hits = modality_set.intersection({"mcta", "vcta", "dcta"})
    if "ncct" in modality_set and len(single_phase_hits) == 1 and len(modality_set) == 2:
        return "ncct_single_phase_cta"
    if modality_set == {"ncct"}:
        return "ncct_only"
    return None


def build_clinical_dag(modalities: Iterable[object] | None) -> Dict[str, object]:
    """Build a deterministic, JSON-serializable review descriptor."""

    canonical = normalize_modalities(modalities)
    modality_set = set(canonical)
    unknown = sorted(modality_set.difference(VALID_MODALITIES))
    path = None if unknown else _path_for_modalities(modality_set)
    stable_modalities = sorted(modality_set)
    stable_path = path or "unsupported"
    dag_id = f"clinical:{stable_path}:{'+'.join(stable_modalities) or 'unknown'}"
    if not path:
        return {
            "schema_version": "1.0",
            "dag_id": dag_id,
            "path": None,
            "label": "不支持的影像组合",
            "note": "请重新上传受支持的 NCCT/CTA/CTP 组合。",
            "valid": False,
            "error": "Invalid or unsupported modality combination",
            "unknown_modalities": unknown,
            "available_modalities": stable_modalities,
            "nodes": [],
            "edges": [],
            "columns": [],
        }

    config = PATH_CONFIGS[path]
    node_ids = [node_id for column in config["columns"] for node_id in column]
    return {
        "schema_version": "1.0",
        "dag_id": dag_id,
        "path": path,
        "label": config["label"],
        "note": config["note"],
        "valid": True,
        "error": None,
        "unknown_modalities": [],
        "available_modalities": stable_modalities,
        "nodes": [copy.deepcopy(BASE_NODES[node_id]) for node_id in node_ids],
        "edges": [
            {"from": source, "to": target} for source, target in config["edges"]
        ],
        "columns": copy.deepcopy(config["columns"]),
    }
