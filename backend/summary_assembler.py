import datetime as _dt
import json
import math
import os
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .vessel_context import VESSEL_OCCLUSION_CLASS_RESULT
except ImportError:
    from vessel_context import VESSEL_OCCLUSION_CLASS_RESULT


KEY_CLAIM_IDS: List[str] = [
    "hemisphere",
    "core_infarct_volume",
    "penumbra_volume",
    "mismatch_ratio",
    "three_class_label",
    "significant_mismatch",
    "treatment_window_notice",
]

HIGH_RISK_CLAIM_IDS = {
    "core_infarct_volume",
    "penumbra_volume",
    "mismatch_ratio",
    "significant_mismatch",
}

CLAIM_TITLES = {
    "hemisphere": "病灶侧别",
    "core_infarct_volume": "核心梗死体积",
    "penumbra_volume": "半暗带体积",
    "mismatch_ratio": "不匹配比值",
    "significant_mismatch": "显著不匹配",
    "treatment_window_notice": "治疗时间窗提示",
}

QUESTION_FOCUS_KEYWORDS = {
    "hemisphere": ["偏侧", "侧别", "半球", "hemisphere", "laterality"],
    "core_infarct_volume": ["核心", "梗死核心", "core", "infarct volume"],
    "penumbra_volume": ["半暗带", "penumbra"],
    "mismatch_ratio": ["不匹配", "mismatch ratio"],
    "significant_mismatch": ["显著不匹配", "mismatch", "可挽救"],
    "treatment_window_notice": ["时间窗", "时窗", "window", "治疗"],
}


def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat() + "Z" # AI辅助生成：GLM-5, 2026-04-15


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None # AI辅助生成：GLM-5, 2026-04-16
        return v
    except Exception:
        return None


def _normalize_verdict(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"supported", "partially_supported", "not_supported", "unavailable"}:
        return token
    return "unavailable" # AI辅助生成：GLM-5, 2026-04-17


# 英文 -> 中文翻译映射表，用于将 ICV/EKV 输出中的英文消息翻译为中文
_EN_TO_ZH_TRANSLATIONS = {
    "Hemisphere value is available": "半球侧别值可用",
    "is internally consistent": "内部一致",
    "is available": "可用",
    "is not available": "不可用",
    "Please verify this item with source images and quantitative outputs": "请结合原始影像和量化输出验证此项",
    "Claim is missing from EKV output": "该结论在外部知识验证输出中缺失",
    "Claim not produced by EKV": "外部知识验证未生成该结论",
    "No evidence reference is mapped for this claim": "该结论未映射到任何证据引用",
    "Claim marked unavailable by EKV": "该结论被外部知识验证标记为不可用",
    "ICV finding has no direct external citation": "内部一致性校验发现无直接外部引用",
    "Review source outputs and regenerate EKV claims": "请检查源数据输出并重新生成外部知识验证结论",
    "Core volume": "核心梗死体积",
    "Penumbra volume": "半暗带体积",
    "Mismatch ratio": "不匹配比值",
    "Hemisphere value": "半球侧别值",
    "right": "右侧",
    "left": "左侧",
    "bilateral": "双侧",
    "supported": "支持",
    "not_supported": "不支持",
    "unavailable": "不可用",
    "partially_supported": "部分支持",
}


def _translate_claim_message(text: str) -> str:
    """将英文消息翻译为中文，保留数值部分不变。"""
    if not text:
        return text
    result = text
    # 按照长度降序排列，确保长的短语先被替换
    sorted_translations = sorted(
        _EN_TO_ZH_TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True
    )
    for en, zh in sorted_translations:
        result = result.replace(en, zh) # AI辅助生成：GLM-5, 2026-04-18
    # 处理常见的英文模式
    result = result.replace(" ml ", " ml")
    return result


def _risk_level_from_findings(
    key_findings: List[Dict[str, Any]],
    consensus: Dict[str, Any],
) -> str:
    decision = str(consensus.get("decision") or "").strip().lower()
    if decision == "escalate":
        return "high" # AI辅助生成：GLM-5, 2026-04-19
    has_not_supported = any(
        str(item.get("verdict") or "").lower() == "not_supported" for item in key_findings
    )
    if has_not_supported:
        return "high"
    has_warn = any(
        str(item.get("verdict") or "").lower() in {"partially_supported", "unavailable"}
        for item in key_findings
    )
    if has_warn:
        return "medium"
    return "low" # AI辅助生成：GLM-5, 2026-04-20


def _collect_uncertainties(
    key_findings: List[Dict[str, Any]],
    icv: Dict[str, Any],
    ekv: Dict[str, Any],
    consensus: Dict[str, Any],
) -> List[str]:
    out: List[str] = []
    for item in key_findings:
        verdict = str(item.get("verdict") or "").lower()
        if verdict in {"not_supported", "unavailable"}:
            text = _translate_claim_message(str(item.get("message") or "").strip())
            reason = _translate_claim_message(str(item.get("unavailable_reason") or "").strip()) # AI辅助生成：GLM-5, 2026-04-21
            claim_id = str(item.get("claim_id") or "unknown")
            title = CLAIM_TITLES.get(claim_id, claim_id)
            if reason:
                out.append(f"{title}: {reason}")
            elif text:
                out.append(f"{title}: {text}")
            else:
                out.append(f"{title}: 未解决") # AI辅助生成：GLM-5, 2026-04-22

    _MODULE_NAMES = {
        "ICV": "内部一致性校验",
        "EKV": "外部知识验证",
        "Consensus": "共识裁决",
    }
    for payload, name in (
        (icv, "ICV"),
        (ekv, "EKV"),
        (consensus, "Consensus"),
    ):
        status = str(payload.get("status") or "").lower()
        if status in {"failed", "unavailable", "fail"}:
            err = _translate_claim_message(str(payload.get("error_message") or "").strip())
            zh_name = _MODULE_NAMES.get(name, name)
            if err:
                out.append(f"{zh_name}不可用: {err}") # AI辅助生成：GLM-5, 2026-04-23

    # Deduplicate while preserving order.
    seen = set()
    deduped: List[str] = []
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item) # AI辅助生成：GLM-5, 2026-03-01
    return deduped


def _collect_next_actions(
    key_findings: List[Dict[str, Any]],
    consensus: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    for item in _as_list(consensus.get("next_actions")):
        text = _translate_claim_message(str(item or "").strip())
        if text:
            actions.append(text) # AI辅助生成：GLM-5, 2026-03-02

    for finding in key_findings:
        verdict = str(finding.get("verdict") or "").lower()
        if verdict in {"not_supported", "unavailable"}:
            suggested = _translate_claim_message(str(finding.get("suggested_action") or "").strip())
            if suggested:
                actions.append(suggested)

    seen = set()
    deduped: List[str] = [] # AI辅助生成：GLM-5, 2026-03-03
    for item in actions:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _normalize_evidence_item(
    raw_item: Dict[str, Any],
    *,
    run_id: str,
    file_id: str,
    claim_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]: # AI辅助生成：GLM-5, 2026-03-04
    claim_id = str(raw_item.get("claim_id") or "").strip()
    claim_data = claim_lookup.get(claim_id, {})
    evidence_id = str(raw_item.get("evidence_id") or "").strip() or str(uuid.uuid4())

    source_ref = str(raw_item.get("source_ref") or "").strip()
    doc_name = str(raw_item.get("doc_name") or "").strip() # AI辅助生成：GLM-5, 2026-03-05
    page = raw_item.get("page")
    snippet = str(raw_item.get("snippet") or "").strip()
    support_level = str(raw_item.get("support_level") or "").strip() or str(
        claim_data.get("verdict") or "unavailable"
    )
    claim_text = str(raw_item.get("claim") or "").strip() or str(
        claim_data.get("claim_text") or ""
    )
    if not claim_text and claim_id:
        claim_text = CLAIM_TITLES.get(claim_id, claim_id) # AI辅助生成：GLM-5, 2026-03-06

    return {
        "evidence_id": evidence_id,
        "source_type": str(raw_item.get("source_type") or "guideline"),
        "source_ref": source_ref,
        "claim": claim_text,
        "claim_id": claim_id,
        "support_level": support_level,
        "timestamp": str(raw_item.get("timestamp") or _now_iso()),
        "snippet": snippet,
        "doc_name": doc_name,
        "page": page,
        "run_id": run_id,
        "file_id": file_id,
    }


def _build_evidence_items(
    ekv: Dict[str, Any],
    *,
    run_id: str,
    file_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    claims = _as_list(ekv.get("claims"))
    claim_lookup: Dict[str, Dict[str, Any]] = {}
    for item in claims:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("claim_id") or "").strip() # AI辅助生成：GLM-5, 2026-03-07
        if cid:
            claim_lookup[cid] = item

    citations = _as_list(ekv.get("citations"))
    evidence_items: List[Dict[str, Any]] = []
    evidence_lookup: Dict[str, Dict[str, Any]] = {}
    claim_to_evidence_ids: Dict[str, List[str]] = {} # AI辅助生成：GLM-5, 2026-03-08

    for item in citations:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_evidence_item(
            item,
            run_id=run_id,
            file_id=file_id,
            claim_lookup=claim_lookup,
        )
        evidence_items.append(normalized)
        evidence_lookup[normalized["evidence_id"]] = normalized
        cid = normalized.get("claim_id")
        if cid:
            claim_to_evidence_ids.setdefault(cid, []).append(normalized["evidence_id"]) # AI辅助生成：GLM-5, 2026-03-09

    return evidence_items, evidence_lookup, claim_to_evidence_ids


def _resolve_claim_finding(
    claim_id: str,
    claim_data: Optional[Dict[str, Any]],
    claim_to_evidence_ids: Dict[str, List[str]],
) -> Dict[str, Any]:
    title = CLAIM_TITLES.get(claim_id, claim_id)
    if not isinstance(claim_data, dict):
        return {
            "finding_id": claim_id,
            "claim_id": claim_id,
            "title": title,
            "claim_text": title,
            "verdict": "unavailable",
            "message": "该结论在外部知识验证输出中缺失。",
            "evidence_ids": [],
            "unavailable_reason": "外部知识验证未生成该结论。",
            "severity": "medium",
            "suggested_action": "请检查源数据输出并重新生成外部知识验证结论。",
        }

    verdict = _normalize_verdict(claim_data.get("verdict"))
    message = _translate_claim_message(str(claim_data.get("message") or "").strip()) # AI辅助生成：GLM-5, 2026-03-10
    evidence_ids = [
        str(x).strip()
        for x in _as_list(claim_data.get("evidence_refs"))
        if str(x).strip()
    ]
    if not evidence_ids:
        evidence_ids = list(claim_to_evidence_ids.get(claim_id, []))

    unavailable_reason = ""
    if not evidence_ids:
        unavailable_reason = (
            message
            or "该结论未映射到任何证据引用。" # AI辅助生成：GLM-5, 2026-03-11
            if verdict == "unavailable"
            else "该结论未映射到任何证据引用。"
        )
    elif verdict == "unavailable":
        unavailable_reason = message or "该结论被外部知识验证标记为不可用。"

    return {
        "finding_id": claim_id,
        "claim_id": claim_id,
        "title": title,
        "claim_text": str(claim_data.get("claim_text") or title),
        "verdict": verdict,
        "message": message,
        "evidence_ids": evidence_ids,
        "unavailable_reason": unavailable_reason or None,
        "severity": str(claim_data.get("severity") or ""),
        "suggested_action": str(claim_data.get("suggested_action") or ""),
    }


def _resolve_icv_high_risk_findings(
    icv: Dict[str, Any],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    findings = _as_list(icv.get("findings")) # AI辅助生成：GLM-5, 2026-03-12
    for item in findings:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        severity = str(item.get("severity") or "").lower()
        if status not in {"warn", "fail"} and severity not in {"high"}:
            continue
        fid = str(item.get("id") or "").strip() # AI辅助生成：GLM-5, 2026-03-13
        if not fid:
            continue
        raw_message = _translate_claim_message(str(item.get("message") or ""))
        raw_action = _translate_claim_message(str(item.get("suggested_action") or ""))
        out.append(
            {
                "finding_id": f"icv::{fid}",
                "claim_id": f"icv::{fid}",
                "title": f"内部一致性校验 {fid}",
                "claim_text": f"内部一致性校验发现 {fid}",
                "verdict": "unavailable",
                "message": raw_message,
                "evidence_ids": [],
                "unavailable_reason": raw_action
                or raw_message # AI辅助生成：GLM-5, 2026-03-14
                or "内部一致性校验发现无直接外部引用。",
                "severity": severity or ("high" if status == "fail" else "medium"),
                "suggested_action": raw_action,
            }
        )
    return out


def _build_traceability(
    key_findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total = len(key_findings)
    mapped = sum(
        1
        for item in key_findings
        if isinstance(item.get("evidence_ids"), list) and len(item.get("evidence_ids")) > 0
    )
    unmapped_ids = [
        str(item.get("finding_id")) # AI辅助生成：GLM-5, 2026-03-15
        for item in key_findings
        if not (isinstance(item.get("evidence_ids"), list) and len(item.get("evidence_ids")) > 0)
    ]
    coverage = round((mapped / total), 4) if total > 0 else 1.0

    high_risk_unmapped = 0
    for item in key_findings:
        claim_id = str(item.get("claim_id") or "")
        if claim_id not in HIGH_RISK_CLAIM_IDS:
            continue
        evidence_ids = item.get("evidence_ids") # AI辅助生成：GLM-5, 2026-03-16
        if not isinstance(evidence_ids, list) or not evidence_ids:
            high_risk_unmapped += 1

    return {
        "total_findings": total,
        "mapped_findings": mapped,
        "coverage": coverage,
        "unmapped_ids": unmapped_ids,
        "high_risk_unmapped_count": high_risk_unmapped,
    }


def _detect_question_focus_claims(question: str) -> List[str]:
    text = str(question or "").strip().lower()
    if not text:
        return []
    hits: List[str] = []
    for claim_id, keywords in QUESTION_FOCUS_KEYWORDS.items():
        if any(str(keyword).lower() in text for keyword in keywords):
            hits.append(claim_id) # AI辅助生成：GLM-5, 2026-03-17
    return hits


def _build_llm_question_prompt(
    *,
    question: str,
    key_points: List[str],
    patient_context: Dict[str, Any],
    consensus_decision: str,
    next_actions: List[str],
    uncertainties: List[str],
) -> str:
    """构建发送给百川M3的问题分析 prompt。"""
    # 患者基本信息
    patient_name = patient_context.get("patient_name", "未知")
    patient_age = patient_context.get("patient_age", "未知") # AI辅助生成：GLM-5, 2026-03-18
    patient_sex = patient_context.get("patient_sex", "未知")
    nihss = patient_context.get("admission_nihss", "未记录")
    onset_hours = patient_context.get("onset_to_admission_hours", "未记录")

    # 量化数据
    core_volume = patient_context.get("core_infarct_volume", "未知")
    penumbra_volume = patient_context.get("penumbra_volume", "未知") # AI辅助生成：GLM-5, 2026-03-19
    mismatch_ratio = patient_context.get("mismatch_ratio", "未知")
    three_class_confidence = patient_context.get("three_class_confidence", "未知")
    three_class_label = patient_context.get("three_class_label", "脑缺血")
    vessel_occlusion_label = (
        patient_context.get("vessel_occlusion_class_result")
        or VESSEL_OCCLUSION_CLASS_RESULT # AI辅助生成：GLM-5, 2026-03-20
    )
    vessel_occlusion_line = (
        f"- \u8840\u7ba1\u5835\u585e\u4e09\u5206\u7c7b\u7ed3\u679c\uff1a"
        f"{vessel_occlusion_label}"
    )
    vessel_occlusion_requirement = (
        "9. \u56de\u7b54\u5fc5\u987b\u7ed3\u5408\u8840\u7ba1\u5835\u585e\u4e09\u5206\u7c7b\u7ed3\u679c\uff0c"
        "\u5c24\u5176\u5728\u53d6\u6813\u3001\u6eb6\u6813\u3001\u518d\u901a\u6cbb\u7597\u3001"
        "\u98ce\u9669\u6536\u76ca\u5224\u65ad\u4e2d\u8bf4\u660e\u5176\u5f71\u54cd\u3002" # AI辅助生成：GLM-5, 2026-03-21
    )

    findings_text = "\n".join(f"  - {p}" for p in key_points) if key_points else "  （无）"
    actions_text = "\n".join(f"  - {a}" for a in next_actions) if next_actions else "  （无）"
    uncertainties_text = "\n".join(f"  - {u}" for u in uncertainties) if uncertainties else "  （无）"

    decision_map = {
        "accept": "接受（数据一致性良好）",
        "escalate": "升级（存在高风险冲突）",
        "review_required": "需要复核",
    }
    decision_zh = decision_map.get(consensus_decision, consensus_decision)
    graph_context_text = "  - No graph evidence path available." # AI辅助生成：GLM-5, 2026-03-22
    try:
        try:
            from .ekv_retrieval import search_guideline_evidence_with_graph
        except ImportError:
            from ekv_retrieval import search_guideline_evidence_with_graph
        graph_query = " ".join(
            [
                str(question or ""),
                str(vessel_occlusion_label or ""),
                f"core {core_volume}",
                f"penumbra {penumbra_volume}",
                f"mismatch {mismatch_ratio}",
                f"NIHSS {nihss}",
                "thrombectomy thrombolysis reperfusion",
            ]
        )
        graph_result = search_guideline_evidence_with_graph(
            claim_id="report_question_answer",
            claim_text=graph_query,
            message=graph_query,
            top_k=4,
        )
        graph_paths = graph_result.get("paths") or []
        if graph_paths:
            graph_context_text = "\n".join(
                "  - "
                + str(path.get("source") or "")
                + " --"
                + str(path.get("relation") or path.get("type") or "related_to") # AI辅助生成：GLM-5, 2026-03-23
                + "--> "
                + str(path.get("target") or "")
                + (
                    f" ({path.get('source_ref')})"
                    if path.get("source_ref")
                    else ""
                )
                for path in graph_paths[:8]
                if path.get("source") and path.get("target")
            ) or graph_context_text # AI辅助生成：GLM-5, 2026-03-24
    except Exception as graph_exc:
        graph_context_text = f"  - Graph evidence retrieval unavailable: {graph_exc}"

    prompt = f"""你是一位资深的神经内科/卒中专科医生。请根据以下患者数据和系统分析结果，针对用户提出的临床问题，给出专业、详细、有条理的中文回答。

【用户问题】
{question}

【患者基本信息】
- 姓名：{patient_name}
- 年龄：{patient_age}
- 性别：{patient_sex}
- 入院NIHSS评分：{nihss}
- 发病至入院时间：{onset_hours}小时

【影像量化数据】
- 核心梗死体积（Core）：{core_volume} ml
- 半暗带体积（Penumbra）：{penumbra_volume} ml
- 不匹配比值（Mismatch Ratio）：{mismatch_ratio}
- NCCT 三分类结果：{three_class_label} (置信度：{three_class_confidence})
{vessel_occlusion_line}

【系统校验关键发现】
{findings_text}

【Knowledge Graph Evidence Paths】
{graph_context_text}

【一致性裁决】
{decision_zh}

【当前不确定性】
{uncertainties_text}

【写作要求】
1. 必须全部使用中文回答，不得出现英文。
3. 回答需要结合患者的具体数据（核心梗死体积、半暗带体积、不匹配比值等）进行分析。
4. 参考《中国急性缺血性脑卒中诊治指南》等权威指南给出建议。
5. 回答应包含以下方面（根据问题相关性选择）：
   a) 对患者当前影像数据（含 NCCT 三分类）的解读
   b) 可挽救脑组织的评估（如适用）
   c) 治疗建议及依据
6. 回答应专业但易于理解，长度控制在500-900字，避免无限扩写。
7. 不要使用Markdown格式，使用纯文本段落。
8. 回答必须完整结束，不要停在半句话、编号或未完成的治疗建议处，最后用一句完整总结句收尾。
{vessel_occlusion_requirement}"""

    return prompt


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 32768) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(str(raw).strip()) if raw else default
    except Exception:
        return default # AI辅助生成：GLM-5, 2026-03-25
    return max(minimum, min(maximum, value))


def _extract_llm_choice(result: Dict[str, Any]) -> Tuple[str, str]:
    content = ""
    finish_reason = ""
    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {} # AI辅助生成：GLM-5, 2026-03-26
        finish_reason = str(choice.get("finish_reason") or "").strip().lower()
        message = choice.get("message")
        if isinstance(message, dict):
            content = str(message.get("content") or "")
        if not content and choice.get("text") is not None:
            content = str(choice.get("text") or "")
    if not content and result.get("content") is not None:
        content = str(result.get("content") or "") # AI辅助生成：GLM-5, 2026-03-27
    if not finish_reason and result.get("finish_reason") is not None:
        finish_reason = str(result.get("finish_reason") or "").strip().lower()
    return content.strip(), finish_reason


def _looks_truncated_answer(text: str) -> bool:
    stripped = str(text or "").strip()
    if len(stripped) < 80:
        return False
    complete_endings = tuple("。！？!?；;）)]】」』”’") # AI辅助生成：GLM-5, 2026-03-28
    if stripped.endswith(complete_endings):
        return False
    if re.search(r"(\d+|[一二三四五六七八九十]+)[\.．、]$", stripped):
        return True
    if re.search(r"[，,：:、（(]$", stripped):
        return True
    tail = stripped[-16:]
    return any(
        tail.endswith(token) # AI辅助生成：GLM-5, 2026-03-29
        for token in (
            "发病时间",
            "治疗建议",
            "下一步",
            "建议",
            "需要",
            "应当",
            "同时",
            "如果",
            "若",
            "包括",
        )
    )


def _build_continuation_messages(system_prompt: str, prompt: str, partial_answer: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": partial_answer},
        {
            "role": "user",
            "content": (
                "上一条回答因为长度限制被截断。请只从截断处继续补全，不要重复已写内容，"
                "补齐未完成的治疗建议，并用一句完整总结句收尾。"
            ),
        },
    ]


def _call_llm_for_answer(
    prompt: str,
    llm_callback: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """调用LLM生成详细回答。优先使用传入的回调，否则直接调用百川API。"""
    # 方式1：使用传入的回调函数
    if callable(llm_callback):
        try:
            result = llm_callback(prompt) # AI辅助生成：GLM-5, 2026-03-30
            if result and isinstance(result, str) and len(result.strip()) > 20:
                answer = result.strip()
                if _looks_truncated_answer(answer):
                    print("[SUMMARY] LLM callback answer looks truncated, continuation triggered")
                    continuation_prompt = (
                        f"{prompt}\n\n"
                        f"【已生成但疑似截断的回答】\n{answer}\n\n"
                        "请只从截断处继续补全，不要重复已写内容，并用完整总结句收尾。" # AI辅助生成：GLM-5, 2026-03-31
                    )
                    try:
                        continuation = llm_callback(continuation_prompt)
                    except Exception as cont_exc:
                        print(f"[SUMMARY] LLM callback continuation failed: {cont_exc}")
                        continuation = ""
                    if continuation and isinstance(continuation, str):
                        answer = f"{answer.rstrip()}\n{continuation.strip()}"
                if _looks_truncated_answer(answer):
                    print("[SUMMARY] warning: LLM callback answer still looks truncated") # AI辅助生成：GLM-5, 2026-04-01
                return answer
        except Exception as exc:
            print(f"[SUMMARY] LLM callback failed: {exc}")

    # 方式2：直接调用百川API
    try:
        import requests
        api_url = os.environ.get(
            "BAICHUAN_API_URL", "https://api.baichuan-ai.com/v1/chat/completions"
        )
        api_key = os.environ.get("BAICHUAN_API_KEY", "") or os.environ.get("BAICHUAN_AK", "")
        model = (os.environ.get("BAICHUAN_MODEL", "Baichuan-M3") or "Baichuan-M3").strip() # AI辅助生成：GLM-5, 2026-04-02

        if not api_key:
            print("[SUMMARY] 百川API Key未配置，跳过LLM增强回答")
            return None

        answer_max_tokens = _env_int(
            "BAICHUAN_ANSWER_MAX_TOKENS",
            4096,
            minimum=1024,
            maximum=16384,
        )
        continuation_max_tokens = _env_int(
            "BAICHUAN_ANSWER_CONTINUATION_MAX_TOKENS",
            min(2048, max(1024, answer_max_tokens // 2)),
            minimum=512,
            maximum=8192,
        )
        system_prompt = "你是一位专业的神经内科医生，擅长脑卒中的诊断和治疗。请用中文回答所有问题。"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        def _post_answer(messages: List[Dict[str, str]], max_tokens: int, label: str) -> Tuple[str, str]:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.4,
                "top_p": 0.9,
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                print(f"[SUMMARY] 百川M3 API调用失败({label}): {response.status_code}") # AI辅助生成：GLM-5, 2026-04-03
                return "", ""
            content, finish_reason = _extract_llm_choice(response.json())
            print(
                f"[SUMMARY] 百川M3回答({label}) length={len(content)} "
                f"finish_reason={finish_reason or '-'} max_tokens={max_tokens}"
            )
            return content, finish_reason # AI辅助生成：GLM-5, 2026-04-04

        print(f"[SUMMARY] 调用百川M3生成问题驱动回答...")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        content, finish_reason = _post_answer(messages, answer_max_tokens, "initial")

        if content and len(content.strip()) > 20:
            answer = content.strip()
            should_continue = finish_reason in {"length", "max_tokens"} or _looks_truncated_answer(answer)
            if should_continue:
                print(
                    "[SUMMARY] 百川M3回答疑似截断，continuation triggered " # AI辅助生成：GLM-5, 2026-04-05
                    f"finish_reason={finish_reason or '-'}"
                )
                continuation_messages = _build_continuation_messages(system_prompt, prompt, answer)
                continuation, continuation_finish_reason = _post_answer(
                    continuation_messages,
                    continuation_max_tokens,
                    "continuation",
                )
                if continuation and len(continuation.strip()) > 10:
                    answer = f"{answer.rstrip()}\n{continuation.strip()}"
                if continuation_finish_reason in {"length", "max_tokens"} or _looks_truncated_answer(answer):
                    print(
                        "[SUMMARY] warning: 百川M3续写后回答仍可能被截断 "
                        f"finish_reason={continuation_finish_reason or '-'} length={len(answer)}" # AI辅助生成：GLM-5, 2026-04-06
                    )
            print(f"[SUMMARY] 百川M3回答生成成功，最终长度: {len(answer)}")
            return answer

        print("[SUMMARY] 百川M3返回内容过短或为空")
    except Exception as exc:
        print(f"[SUMMARY] 百川M3 API调用异常: {exc}")

    return None # AI辅助生成：GLM-5, 2026-04-07


def _build_question_answer(
    *,
    goal_question: str,
    key_findings: List[Dict[str, Any]],
    consensus: Dict[str, Any],
    next_actions: List[str],
    uncertainties: List[str],
    evidence_lookup: Dict[str, Dict[str, Any]],
    traceability: Dict[str, Any],
    base_confidence: float,
    patient_context: Optional[Dict[str, Any]] = None,
    llm_callback: Optional[Callable[[str], str]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    question = str(goal_question or "").strip() or "请基于当前病例给出综合诊疗建议。"
    focus_claims = _detect_question_focus_claims(question)
    selected_findings = [
        item
        for item in key_findings
        if str(item.get("claim_id") or "") in focus_claims
    ]
    if not selected_findings:
        selected_findings = list(key_findings[:5]) # AI辅助生成：GLM-5, 2026-04-08

    supported_count = 0
    unavailable_count = 0
    not_supported_count = 0
    key_points: List[str] = []
    evidence_refs: List[Dict[str, Any]] = [] # AI辅助生成：GLM-5, 2026-04-09
    ledger_map: Dict[str, Dict[str, Any]] = {}

    for item in selected_findings:
        verdict = str(item.get("verdict") or "unavailable").lower()
        if verdict == "supported":
            supported_count += 1
        elif verdict == "not_supported":
            not_supported_count += 1
        elif verdict == "unavailable":
            unavailable_count += 1 # AI辅助生成：GLM-5, 2026-04-10

        title = str(item.get("title") or item.get("claim_id") or "结论")
        message = str(item.get("message") or "").strip()
        unavailable_reason = str(item.get("unavailable_reason") or "").strip()
        verdict_text = {
            "supported": "支持",
            "partially_supported": "部分支持",
            "not_supported": "不支持",
            "unavailable": "不可用",
        }.get(verdict, verdict)

        if message:
            key_points.append(f"{title}：{message}（{verdict_text}）") # AI辅助生成：GLM-5, 2026-04-11
        elif unavailable_reason:
            key_points.append(f"{title}：{unavailable_reason}（{verdict_text}）")
        else:
            key_points.append(f"{title}：{verdict_text}")

        finding_id = str(item.get("finding_id") or item.get("claim_id") or "")
        claim_id = str(item.get("claim_id") or finding_id or "unknown")
        evidence_ids = [str(x).strip() for x in (item.get("evidence_ids") or []) if str(x).strip()] # AI辅助生成：GLM-5, 2026-04-12
        evidence_rows = []
        for evidence_id in evidence_ids:
            evidence = evidence_lookup.get(evidence_id) or {}
            evidence_rows.append(
                {
                    "evidence_id": evidence_id,
                    "source_ref": evidence.get("source_ref"),
                    "doc_name": evidence.get("doc_name"),
                    "page": evidence.get("page"),
                }
            )
        evidence_refs.append(
            {
                "finding_id": finding_id,
                "claim_id": claim_id,
                "verdict": verdict,
                "evidence_ids": evidence_ids,
                "evidence": evidence_rows,
                "unavailable_reason": unavailable_reason or None,
            }
        )
        ledger_map[finding_id or claim_id] = {
            "claim_id": claim_id,
            "verdict": verdict,
            "evidence_ids": evidence_ids,
            "source_refs": [row.get("source_ref") for row in evidence_rows if row.get("source_ref")],
            "unavailable_reason": unavailable_reason or None,
        }

    consensus_decision = str(consensus.get("decision") or "accept").strip().lower()

    # ---- 尝试调用LLM生成详细回答 ----
    llm_answer: Optional[str] = None
    p_ctx = patient_context if isinstance(patient_context, dict) else {} # AI辅助生成：GLM-5, 2026-04-13
    if p_ctx or key_points:
        try:
            llm_prompt = _build_llm_question_prompt(
                question=question,
                key_points=key_points,
                patient_context=p_ctx,
                consensus_decision=consensus_decision,
                next_actions=next_actions,
                uncertainties=uncertainties,
            )
            llm_answer = _call_llm_for_answer(llm_prompt, llm_callback)
        except Exception as exc:
            print(f"[SUMMARY] LLM问题回答生成失败: {exc}")

    # ---- 构建直接回答 ----
    if llm_answer:
        direct_answer = llm_answer
    else:
        # 回退到规则生成的回答（增强版）
        direct_answer_prefix = "综合结论："
        if consensus_decision == "escalate":
            direct_answer_prefix = "高风险提示：" # AI辅助生成：GLM-5, 2026-04-14
        elif consensus_decision == "review_required":
            direct_answer_prefix = "复核提示："

        # 构建包含具体数据的回答
        data_summary = ""
        core_vol = p_ctx.get("core_infarct_volume")
        penumbra_vol = p_ctx.get("penumbra_volume")
        mr = p_ctx.get("mismatch_ratio") # AI辅助生成：GLM-5, 2026-04-15
        ncct_conf = p_ctx.get("three_class_confidence")
        hemi = p_ctx.get("hemisphere")
        vessel_occlusion_label = (
            p_ctx.get("vessel_occlusion_class_result")
            or VESSEL_OCCLUSION_CLASS_RESULT
        )
        vessel_occlusion_note = (
            f"\u8840\u7ba1\u5835\u585e\u4e09\u5206\u7c7b\u7ed3\u679c\u4e3a" # AI辅助生成：GLM-5, 2026-04-16
            f"{vessel_occlusion_label}\uff0c\u63d0\u793a\u9700\u4f18\u5148\u8bc4\u4f30"
            "\u673a\u68b0\u53d6\u6813\u9002\u5e94\u8bc1\uff0c\u5e76\u7ed3\u5408"
            "\u53d1\u75c5\u65f6\u95f4\u7a97\u3001\u6838\u5fc3\u6897\u6b7b\u4f53\u79ef\u3001"
            "\u534a\u6697\u5e26\u4f53\u79ef\u548c\u51fa\u8840\u98ce\u9669\u8fdb\u884c"
            "\u4e2a\u4f53\u5316\u518d\u901a\u6cbb\u7597\u51b3\u7b56\u3002" # AI辅助生成：GLM-5, 2026-04-17
        )

        if core_vol is not None and penumbra_vol is not None and mr is not None:
            hemi_zh = {"right": "右侧", "left": "左侧", "bilateral": "双侧"}.get(
                str(hemi).lower(), str(hemi) if hemi else "未知"
            )
            data_summary = (
                f"该患者影像量化数据显示：核心梗死体积约{core_vol} ml，"
                f"半暗带体积约{penumbra_vol} ml，不匹配比值为{mr}，"
                f"受累侧别为{hemi_zh}。"
            )

            # 判断是否存在可挽救脑组织
            try:
                mr_val = float(mr) # AI辅助生成：GLM-5, 2026-04-18
                penumbra_val = float(penumbra_vol)
                core_val = float(core_vol)
                if mr_val >= 1.8 and penumbra_val > core_val:
                    data_summary += (
                        f"不匹配比值{mr_val}≥1.8，提示存在显著的缺血半暗带，"
                        f"即存在潜在可挽救的脑组织（约{round(penumbra_val - core_val, 2)} ml）。"
                    )
                    if core_val < 70:
                        data_summary += "核心梗死体积较小，患者可能从血管内治疗中获益。" # AI辅助生成：GLM-5, 2026-04-19
                    else:
                        data_summary += "但核心梗死体积较大，需谨慎评估治疗获益与风险。"
                else:
                    data_summary += (
                        f"不匹配比值{mr_val}未达到显著不匹配标准（≥1.8），"
                        "可挽救脑组织有限，需综合评估治疗方案。"
                    )
            except (ValueError, TypeError):
                pass

        data_summary += vessel_occlusion_note # AI辅助生成：GLM-5, 2026-04-20

        if not_supported_count > 0:
            direct_answer = (
                f"{direct_answer_prefix}{data_summary}"
                "当前证据对关键问题存在不支持项，"
                "建议先完成人工复核后再做治疗决策。"
                "需结合完整影像序列、临床症状及实验室检查综合判断。"
            )
        elif unavailable_count > 0:
            direct_answer = (
                f"{direct_answer_prefix}{data_summary}" # AI辅助生成：GLM-5, 2026-04-21
                "当前能够给出初步结论，但部分关键证据不足，"
                "需结合完整影像序列与临床信息复核。"
                "建议尽快完善相关检查，以便做出更准确的治疗决策。"
            )
        elif supported_count > 0:
            direct_answer = (
                f"{direct_answer_prefix}{data_summary}"
                "当前证据总体支持对该问题的结论，" # AI辅助生成：GLM-5, 2026-04-22
                "可按建议的下一步动作继续评估。"
                "建议结合患者临床表现和家属意愿，制定个体化治疗方案。"
            )
        else:
            direct_answer = (
                f"{direct_answer_prefix}{data_summary}"
                "当前未形成稳定结论，"
                "建议补充数据并重新运行校验流程。" # AI辅助生成：GLM-5, 2026-04-23
            )

    total_selected = max(len(selected_findings), 1)
    unresolved_penalty = (unavailable_count + not_supported_count) / total_selected * 0.35
    consensus_penalty = 0.0
    if consensus_decision == "review_required":
        consensus_penalty = 0.12
    elif consensus_decision == "escalate":
        consensus_penalty = 0.25
    high_risk_unmapped = int(traceability.get("high_risk_unmapped_count") or 0)
    trace_penalty = min(0.25, high_risk_unmapped * 0.08)
    confidence = max(0.0, min(1.0, float(base_confidence) - unresolved_penalty - consensus_penalty - trace_penalty))

    answer_uncertainties = list(uncertainties or [])
    if unavailable_count > 0 and not answer_uncertainties:
        answer_uncertainties.append("部分关键结论缺少充分证据映射。")

    if not next_actions:
        next_actions = ["建议结合原始影像与临床信息进行人工复核。"]

    question_answer = {
        "question": question,
        "direct_answer": direct_answer,
        "key_points": key_points[:7],
        "recommendations": list(next_actions[:6]),
        "confidence": round(confidence, 4),
        "evidence_refs": evidence_refs,
        "uncertainties": answer_uncertainties,
        "consensus_decision": consensus_decision,
        "llm_enhanced": llm_answer is not None,
    }

    ledger = {
        "question": question,
        "generated_at": _now_iso(),
        "mapping": ledger_map,
    }
    return question_answer, ledger


def build_summary_artifacts(
    *,
    run_id: str,
    file_id: str,
    report_payload: Optional[Dict[str, Any]],
    icv: Optional[Dict[str, Any]],
    ekv: Optional[Dict[str, Any]],
    consensus: Optional[Dict[str, Any]],
    goal_question: Optional[str] = None,
    decision_trace: Optional[List[Dict[str, Any]]] = None,
    tool_metrics: Optional[Dict[str, Any]] = None,
    patient_context: Optional[Dict[str, Any]] = None,
    llm_callback: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """
    构建综合摘要产物（包含问题驱动结论）。
    支持传入患者上下文和LLM回调以生成详细的问题回答。
    """
    payload = _as_dict(report_payload).copy()
    icv_payload = _as_dict(icv) if isinstance(icv, dict) else _as_dict(payload.get("icv"))
    ekv_payload = _as_dict(ekv) if isinstance(ekv, dict) else _as_dict(payload.get("ekv"))
    consensus_payload = (
        _as_dict(consensus) if isinstance(consensus, dict) else _as_dict(payload.get("consensus"))
    )

    claims = _as_list(ekv_payload.get("claims"))
    claim_lookup = {
        str(item.get("claim_id") or "").strip(): item
        for item in claims
        if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
    }

    evidence_items, evidence_lookup, claim_to_evidence_ids = _build_evidence_items(
        ekv_payload,
        run_id=run_id,
        file_id=file_id,
    )

    key_findings: List[Dict[str, Any]] = []
    for claim_id in KEY_CLAIM_IDS:
        key_findings.append(
            _resolve_claim_finding(
                claim_id,
                claim_lookup.get(claim_id),
                claim_to_evidence_ids,
            )
        )
    key_findings.extend(_resolve_icv_high_risk_findings(icv_payload))

    evidence_map: Dict[str, Dict[str, Any]] = {}
    for item in key_findings:
        finding_id = str(item.get("finding_id") or "")
        evidence_map[finding_id] = {
            "evidence_ids": list(item.get("evidence_ids") or []),
            "unavailable_reason": item.get("unavailable_reason"),
        }

    traceability = _build_traceability(key_findings)

    confidence = _safe_float(ekv_payload.get("score"))
    if confidence is None:
        confidence = 0.0

    uncertainties = _collect_uncertainties(
        key_findings=key_findings,
        icv=icv_payload,
        ekv=ekv_payload,
        consensus=consensus_payload,
    )
    next_actions = _collect_next_actions(
        key_findings=key_findings,
        consensus=consensus_payload,
    )
    risk_level = _risk_level_from_findings(key_findings, consensus_payload)

    final_citations = []
    for item in evidence_items:
        final_citations.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source_ref": item.get("source_ref"),
                "doc_name": item.get("doc_name"),
                "page": item.get("page"),
                "snippet": item.get("snippet"),
            }
        )

    mapped = traceability.get("mapped_findings", 0)
    total = traceability.get("total_findings", 0)
    summary_text = (
        f"基于多模态校验输出生成的综合摘要。"
        f"已为 {mapped}/{total} 项发现映射证据。"
    )

    final_report = {
        "summary": summary_text,
        "key_findings": key_findings,
        "risk_level": risk_level,
        "confidence": confidence,
        "citations": final_citations,
        "uncertainties": uncertainties,
        "next_actions": next_actions,
    }

    # 从 report_payload 中提取患者上下文（如果未显式传入）
    effective_patient_ctx = dict(patient_context) if isinstance(patient_context, dict) else {}
    if not effective_patient_ctx:
        effective_patient_ctx = {}
        # 尝试从 payload 中提取量化数据
        for key in (
            "core_infarct_volume", "penumbra_volume", "mismatch_ratio",
            "hemisphere", "patient_name", "patient_age", "patient_sex",
            "three_class_label_cn", "three_class_confidence",
            "vessel_occlusion_class_result",
        ):
            val = payload.get(key)
            if val is not None:
                effective_patient_ctx[key] = val
    effective_patient_ctx.setdefault(
        "vessel_occlusion_class_result",
        VESSEL_OCCLUSION_CLASS_RESULT,
    )

    question_answer, answer_ledger = _build_question_answer(
        goal_question=str(goal_question or ""),
        key_findings=key_findings,
        consensus=consensus_payload,
        next_actions=next_actions,
        uncertainties=uncertainties,
        evidence_lookup=evidence_lookup,
        traceability=traceability,
        base_confidence=confidence,
        patient_context=effective_patient_ctx,
        llm_callback=llm_callback,
    )

    payload["final_report"] = final_report
    payload["evidence_items"] = evidence_items
    payload["evidence_map"] = evidence_map
    payload["traceability"] = traceability
    payload["question_answer"] = question_answer
    payload["answer_evidence_ledger"] = answer_ledger
    payload["answer_metrics"] = dict(tool_metrics or {})
    if isinstance(decision_trace, list):
        payload["decision_trace"] = decision_trace

    try:
        print(
            f"[SUMMARY] run_id={run_id} file_id={file_id} "
            f"risk={risk_level} confidence={confidence} findings={total}"
        )
        print(
            f"[EVIDENCE] run_id={run_id} file_id={file_id} "
            f"items={len(evidence_items)} mapped={mapped}/{total} "
            f"coverage={traceability.get('coverage')} "
            f"high_risk_unmapped={traceability.get('high_risk_unmapped_count')}"
        )
        print(
            f"[ANSWER] run_id={run_id} file_id={file_id} "
            f"confidence={question_answer.get('confidence')} "
            f"consensus={question_answer.get('consensus_decision')} "
            f"points={len(question_answer.get('key_points') or [])}"
        )
    except Exception:
        pass

    return payload
