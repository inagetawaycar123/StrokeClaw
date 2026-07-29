"""Provider-neutral report generation backed by the Baichuan M3 API.

This module intentionally has no torch/transformers dependency.  It accepts
only structured algorithm outputs; original images and local file paths are
never sent to the external report provider.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

try:
    from .vessel_context import vessel_result_from_sources
except ImportError:  # pragma: no cover - direct-script compatibility
    from vessel_context import vessel_result_from_sources


DEFAULT_BAICHUAN_API_URL = "https://api.baichuan-ai.com/v1/chat/completions"
DEFAULT_BAICHUAN_MODEL = "Baichuan-M3"
_MODALITY_ALIASES = {"mcat": "mcta", "vcat": "vcta", "dcat": "dcta"}
_RISK_NOTICE = [
    "AI结果仅作为影像辅助信息，不可替代神经影像医师阅片和临床综合判断。",
    "关键结论需回到原始影像、算法输出和临床资料进行医生复核。",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_results_dir() -> Path:
    configured = str(os.environ.get("REPORT_RESULTS_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_project_root() / "runtime" / "reports").resolve()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_modalities(raw_modalities: Any) -> List[str]:
    if raw_modalities is None:
        return []
    if isinstance(raw_modalities, str):
        candidates = re.findall(r"[A-Za-z0-9_]+", raw_modalities)
    else:
        try:
            candidates = list(raw_modalities)
        except TypeError:
            candidates = []

    normalized: List[str] = []
    for item in candidates:
        token = _MODALITY_ALIASES.get(str(item).strip().lower(), str(item).strip().lower())
        if token and token not in normalized:
            normalized.append(token)
    return sorted(normalized)


def infer_modalities_from_files(file_id: str) -> List[str]:
    """Infer modalities from local filenames without returning any path."""
    if not file_id:
        return []
    safe_file_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(file_id))
    uploads_dir = _project_root() / "static" / "uploads"
    found = []
    for modality in ("ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"):
        if any((uploads_dir / f"{safe_file_id}_{modality}{ext}").exists() for ext in (".nii.gz", ".nii")):
            found.append(modality)
    return sorted(found)


def resolve_modality_combo(modalities: List[str]) -> Tuple[bool, Optional[str]]:
    mods = set(modalities)
    if "ncct" not in mods:
        return False, None
    has_cta = any(item in mods for item in ("mcta", "vcta", "dcta"))
    has_three_phase = all(item in mods for item in ("mcta", "vcta", "dcta"))
    has_ctp = all(item in mods for item in ("cbf", "cbv", "tmax"))
    if has_three_phase:
        return True, "NCCT_MCTA_CTP" if has_ctp else "NCCT_MCTA"
    if has_cta:
        return True, "NCCT_SINGLE_CTA"
    return True, "NCCT_ONLY"


def _ctp_values(
    structured_data: Dict[str, Any], imaging_data: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Prefer current case analysis values over legacy patient-level fields."""

    def pick_float(*candidates: Any) -> Optional[float]:
        for value in candidates:
            parsed = _safe_float(value)
            if parsed is not None:
                return parsed
        return None

    analysis_result = _as_dict(_as_dict(imaging_data).get("analysis_result"))
    volume_analysis = _as_dict(analysis_result.get("volume_analysis"))
    mismatch_analysis = _as_dict(analysis_result.get("mismatch_analysis"))
    report_summary = _as_dict(_as_dict(analysis_result.get("report")).get("summary"))
    core = pick_float(
        analysis_result.get("core_volume_ml"),
        volume_analysis.get("core_volume_ml"),
        report_summary.get("core_volume_ml"),
        structured_data.get("core_infarct_volume"),
    )
    penumbra = pick_float(
        analysis_result.get("penumbra_volume_ml"),
        volume_analysis.get("penumbra_volume_ml"),
        report_summary.get("penumbra_volume_ml"),
        structured_data.get("penumbra_volume"),
    )
    mismatch = pick_float(
        analysis_result.get("mismatch_ratio"),
        volume_analysis.get("mismatch_ratio"),
        mismatch_analysis.get("mismatch_ratio"),
        report_summary.get("mismatch_ratio"),
        structured_data.get("mismatch_ratio"),
    )
    return core, penumbra, mismatch


def _resolve_ncct(structured_data: Dict[str, Any], imaging_data: Dict[str, Any]) -> Dict[str, Any]:
    sources = [
        structured_data,
        _as_dict(imaging_data.get("three_class_summary")),
        _as_dict(imaging_data.get("analysis_result")),
        imaging_data,
    ]
    label = None
    label_cn = None
    confidence = None
    status = None
    class_counts = None
    total_slices = None
    safety_gate = None
    for source in sources:
        candidates = [
            source,
            _as_dict(source.get("three_class_summary")),
            _as_dict(source.get("three_class_result")),
            _as_dict(source.get("output")),
        ]
        for candidate in candidates:
            label = label or _first_present(
                candidate.get("three_class_label"),
                candidate.get("predicted_label"),
                candidate.get("pred_label"),
            )
            label_cn = label_cn or _first_present(
                candidate.get("three_class_label_cn"),
                candidate.get("predicted_label_cn"),
                candidate.get("label_cn"),
            )
            if confidence is None:
                confidence = _safe_float(
                    _first_present(
                        candidate.get("three_class_confidence"),
                        candidate.get("confidence"),
                    )
                )
            status = status or candidate.get("status")
            if class_counts is None and isinstance(
                candidate.get("class_counts"), dict
            ):
                class_counts = dict(candidate.get("class_counts"))
            if total_slices is None:
                total_slices = candidate.get("total_slices")
            if safety_gate is None and isinstance(
                candidate.get("safety_gate"), dict
            ):
                safety_gate = dict(candidate.get("safety_gate"))
        if label or label_cn:
            break
    completed = bool(label or label_cn)
    normalized_label = str(label).strip().lower() if label else None
    if not isinstance(safety_gate, dict):
        blocked = normalized_label == "hemo" or not completed
        safety_gate = {
            "blocked": blocked,
            "reason_code": (
                "NCCT_SUSPECTED_HEMORRHAGE"
                if normalized_label == "hemo"
                else ("NCCT_CLASSIFICATION_UNAVAILABLE" if not completed else None)
            ),
            "reason": (
                "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析"
                if normalized_label == "hemo"
                else ("NCCT 三分类没有产生有效结果" if not completed else None)
            ),
            "requires_clinician_review": blocked,
        }
    return {
        "status": "completed" if completed else str(status or "unavailable"),
        "three_class_label": normalized_label,
        "three_class_label_cn": str(label_cn).strip() if label_cn else None,
        "three_class_confidence": confidence,
        "class_counts": class_counts
        or {"normal": 0, "hemo": 0, "infarct": 0},
        "total_slices": int(total_slices or 0),
        "safety_gate": safety_gate,
    }


def _redact_known_identifiers(text: Any, structured_data: Dict[str, Any], file_id: str) -> str:
    redacted = str(text or "")
    identifiers = [
        structured_data.get("id"),
        structured_data.get("ID"),
        structured_data.get("patient_id"),
        structured_data.get("patient_name"),
        structured_data.get("name"),
        structured_data.get("file_id"),
        file_id,
    ]
    for value in identifiers:
        token = str(value or "").strip()
        if token:
            redacted = redacted.replace(token, "[已去标识]")
    return redacted


def _prompt_context(
    structured_data: Dict[str, Any],
    imaging_data: Dict[str, Any],
    file_id: str,
    modalities: List[str],
    ncct: Dict[str, Any],
    vessel: Dict[str, Any],
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
) -> Dict[str, Any]:
    safety_gate = _as_dict(ncct.get("safety_gate"))
    gate_blocked = bool(safety_gate.get("blocked"))
    return {
        "patient_context": {
            "age": structured_data.get("patient_age"),
            "sex": structured_data.get("patient_sex"),
            "admission_nihss": structured_data.get("admission_nihss"),
            "onset_to_admission_hours": structured_data.get("onset_to_admission_hours"),
            "hemisphere": structured_data.get("hemisphere"),
        },
        "available_modalities": modalities,
        "ncct_three_class": ncct,
        "vessel_occlusion": {
            "status": vessel.get("status"),
            "class_result": vessel.get("vessel_occlusion_class_result"),
            "confidence": vessel.get("confidence"),
        },
        "ctp_quantification": {
            "status": "skipped" if gate_blocked else "available",
            "reason": safety_gate.get("reason") if gate_blocked else None,
            "core_infarct_volume_ml": None if gate_blocked else core,
            "penumbra_volume_ml": None if gate_blocked else penumbra,
            "mismatch_ratio": None if gate_blocked else mismatch,
        },
        "clinical_question": _redact_known_identifiers(
            _first_present(
                structured_data.get("question"),
                structured_data.get("goal_question"),
                "",
            ),
            structured_data,
            file_id,
        ),
    }


def _build_prompt(context: Dict[str, Any], output_format: str) -> str:
    requested = "严格 JSON 对象" if str(output_format).lower() == "json" else "Markdown"
    return (
        "请根据以下已经去标识化的卒中病例结构化数据生成影像辅助报告。\n"
        f"输出格式：{requested}。\n"
        "要求：只使用已提供的算法和临床字段；缺失内容必须明确写为“未提供/不可用”；"
        "不得推断原始影像中未被算法确认的征象；不得给出确定性治疗指令；"
        "结尾必须提示医生结合原始影像和临床资料复核。\n"
        "结构化数据：\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    )


def _extract_response_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = _first_present(message.get("content"), choice.get("text"))
        if content is not None:
            return str(content).strip()
    if payload.get("content") is not None:
        return str(payload.get("content")).strip()
    data = payload.get("data")
    if isinstance(data, dict) and data.get("content") is not None:
        return str(data.get("content")).strip()
    return ""


def _local_identity(structured_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "patient_id": _first_present(
            structured_data.get("id"),
            structured_data.get("ID"),
            structured_data.get("patient_id"),
        ),
        "patient_name": _first_present(
            structured_data.get("patient_name"),
            structured_data.get("name"),
        ),
    }


def _restore_identity(report: str, output_format: str, identity: Dict[str, Any]) -> str:
    clean_identity = {key: value for key, value in identity.items() if value not in (None, "")}
    if not clean_identity:
        return report
    if str(output_format).lower() == "json":
        try:
            parsed = json.loads(report)
        except (TypeError, ValueError):
            parsed = {"report": report}
        if not isinstance(parsed, dict):
            parsed = {"report": parsed}
        return json.dumps({**clean_identity, **parsed}, ensure_ascii=False, indent=2)

    lines = ["## 患者信息"]
    if clean_identity.get("patient_id") is not None:
        lines.append(f"- 患者ID：{clean_identity['patient_id']}")
    if clean_identity.get("patient_name") is not None:
        lines.append(f"- 姓名：{clean_identity['patient_name']}")
    return "\n".join(lines) + "\n\n" + str(report or "").strip()


def _format_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "未提供"
    if isinstance(value, float):
        rendered = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        rendered = str(value)
    return f"{rendered}{suffix}"


def generate_mock_report(
    structured_data: Dict[str, Any],
    modalities: List[str],
    ncct: Dict[str, Any],
    vessel: Dict[str, Any],
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
    output_format: str = "markdown",
) -> str:
    safety_gate = _as_dict(ncct.get("safety_gate"))
    gate_blocked = bool(safety_gate.get("blocked"))
    document = {
        "检查方法": modalities or ["未提供"],
        "NCCT三分类": {
            "状态": ncct.get("status"),
            "类别": _first_present(ncct.get("three_class_label_cn"), ncct.get("three_class_label")),
            "置信度": ncct.get("three_class_confidence"),
        },
        "血管闭塞评估": {
            "状态": vessel.get("status"),
            "类别": vessel.get("vessel_occlusion_class_result"),
            "置信度": vessel.get("confidence"),
        },
        "CTP定量": {
            "状态": "因 NCCT 安全门控跳过" if gate_blocked else "已完成",
            "原因": safety_gate.get("reason") if gate_blocked else None,
            "核心梗死体积_ml": core,
            "半暗带体积_ml": penumbra,
            "不匹配比值": mismatch,
        },
        "诊断意见": "未配置百川 M3 API，当前内容为规则化草稿，不得作为真实模型结论。",
        "复核提示": _RISK_NOTICE,
    }
    if str(output_format).lower() == "json":
        return json.dumps(document, ensure_ascii=False, indent=2)
    ctp_lines = (
        [f"- 灌注分析：{safety_gate.get('reason') or '因 NCCT 安全门控跳过'}"]
        if gate_blocked
        else [
            f"- 核心梗死体积：{_format_value(core, ' ml')}",
            f"- 半暗带体积：{_format_value(penumbra, ' ml')}",
            f"- 不匹配比值：{_format_value(mismatch)}",
        ]
    )
    return "\n".join(
        [
            "# 卒中影像辅助报告（本地降级草稿）",
            "",
            f"- 检查模态：{', '.join(modalities) if modalities else '未提供'}",
            f"- NCCT 三分类：{_first_present(ncct.get('three_class_label_cn'), ncct.get('three_class_label'), '不可用')}",
            f"- 血管闭塞分类：{_first_present(vessel.get('vessel_occlusion_class_result'), '不可用')}",
            *ctp_lines,
            "",
            "未配置百川 M3 API，当前内容为规则化草稿，不得作为真实模型结论。",
            *[f"- {item}" for item in _RISK_NOTICE],
        ]
    )


def _summary_findings(
    ncct: Dict[str, Any],
    vessel: Dict[str, Any],
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
) -> List[str]:
    findings = []
    ncct_label = _first_present(ncct.get("three_class_label_cn"), ncct.get("three_class_label"))
    if ncct_label:
        findings.append(f"NCCT 三分类结果：{ncct_label}。")
    else:
        findings.append("NCCT 三分类结果不可用，需医生复核原始影像。")
    vessel_label = vessel.get("vessel_occlusion_class_result")
    if vessel_label:
        findings.append(f"血管闭塞分类结果：{vessel_label}。")
    else:
        findings.append("血管闭塞分类结果不可用。")
    gate = _as_dict(ncct.get("safety_gate"))
    if gate.get("blocked"):
        findings.append(
            str(gate.get("reason") or "已由 NCCT 安全门控阻断后续 AIS/灌注分析。")
        )
    elif any(value is not None for value in (core, penumbra, mismatch)):
        findings.append(
            "CTP 定量：核心梗死体积 "
            f"{_format_value(core, ' ml')}，半暗带体积 {_format_value(penumbra, ' ml')}，"
            f"不匹配比值 {_format_value(mismatch)}。"
        )
    return findings


def _build_report_payload(
    structured_data: Dict[str, Any],
    modalities: List[str],
    combo: Optional[str],
    ncct: Dict[str, Any],
    vessel: Dict[str, Any],
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
    report: str,
    is_mock: bool,
    model: str,
) -> Dict[str, Any]:
    identity = _local_identity(structured_data)
    cta_data = {
        "status": vessel.get("status") or "unavailable",
        "vessel_occlusion_class_result": vessel.get("vessel_occlusion_class_result"),
        "confidence": vessel.get("confidence"),
    }
    safety_gate = _as_dict(ncct.get("safety_gate"))
    gate_blocked = bool(safety_gate.get("blocked"))
    show_ctp = (not gate_blocked) and any(
        value is not None for value in (core, penumbra, mismatch)
    )
    payload = {
        "provider": "local_fallback" if is_mock else "baichuan_m3",
        "provider_model": model,
        "is_mock": bool(is_mock),
        "modalities": modalities,
        "combo": combo,
        "sections": {
            "ncct": dict(ncct),
            "cta": [{"title": "血管闭塞分类", "data": cta_data}],
            "ctp": {
                "enabled": show_ctp,
                "status": "skipped" if gate_blocked else (
                    "completed" if show_ctp else "not_run"
                ),
                "reason": safety_gate.get("reason") if gate_blocked else None,
                "core_infarct_volume": core,
                "penumbra_volume": penumbra,
                "mismatch_ratio": mismatch,
            },
        },
        "summary_findings": _summary_findings(ncct, vessel, core, penumbra, mismatch),
        "risk_notice": list(_RISK_NOTICE),
        "quality_checks": {
            "passed": not gate_blocked,
            "issues": (
                [str(safety_gate.get("reason"))]
                if gate_blocked
                else ([] if not is_mock else ["BAICHUAN_API_KEY 未配置，使用本地降级草稿"])
            ),
        },
        "ncct_enhanced": [],
        "cta_enhanced": {"arterial": [], "venous": [], "delayed": []},
        "ctp_enhanced": None,
        "report": report,
        "goal_question": _first_present(
            structured_data.get("goal_question"), structured_data.get("question"), ""
        ),
        "question": _first_present(
            structured_data.get("question"), structured_data.get("goal_question"), ""
        ),
        "patient_age": structured_data.get("patient_age"),
        "patient_sex": structured_data.get("patient_sex"),
        "admission_nihss": structured_data.get("admission_nihss"),
        "onset_to_admission_hours": structured_data.get("onset_to_admission_hours"),
        "hemisphere": structured_data.get("hemisphere"),
        "core_infarct_volume": core,
        "penumbra_volume": penumbra,
        "mismatch_ratio": mismatch,
        "three_class_status": ncct.get("status"),
        "three_class_label": ncct.get("three_class_label"),
        "three_class_label_cn": ncct.get("three_class_label_cn"),
        "three_class_confidence": ncct.get("three_class_confidence"),
        "three_class_result": dict(ncct),
        "safety_gate": dict(ncct.get("safety_gate") or {}),
        "vessel_occlusion_result": vessel,
        "vessel_occlusion_status": vessel.get("status"),
        "vessel_occlusion_class_result": vessel.get("vessel_occlusion_class_result"),
        "vessel_occlusion_confidence": vessel.get("confidence"),
        **identity,
    }
    return payload


def _write_result_json(
    results_dir: Path,
    file_id: str,
    output_format: str,
    report: str,
    report_payload: Dict[str, Any],
    model: str,
    elapsed_seconds: float,
) -> str:
    resolved_dir = results_dir.expanduser().resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    safe_file_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(file_id or "unknown"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    result_path = resolved_dir / f"baichuan_report_{safe_file_id}_{timestamp}.json"
    document = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_id": str(file_id),
            "provider": report_payload.get("provider"),
            "model": model,
            "elapsed_seconds": elapsed_seconds,
            "format": output_format,
        },
        "report_payload": report_payload,
        "markdown": report if str(output_format).lower() != "json" else None,
        "report": report,
    }
    temp_path = result_path.with_suffix(result_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(temp_path), str(result_path))
    return str(result_path)


def generate_report(
    structured_data: Dict[str, Any],
    imaging_data: Optional[Dict[str, Any]],
    file_id: str,
    output_format: str = "markdown",
    results_dir: Optional[str] = None,
    *,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    http_post: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    started_at = time.time()
    structured = _as_dict(structured_data)
    imaging = _as_dict(imaging_data)
    requested_format = str(output_format or "markdown").strip().lower()
    if requested_format not in {"markdown", "json"}:
        requested_format = "markdown"
    if not file_id:
        return {"success": False, "error": "missing file_id", "format": requested_format}

    modalities = normalize_modalities(imaging.get("available_modalities"))
    if not modalities:
        modalities = normalize_modalities(structured.get("available_modalities"))
    if not modalities:
        modalities = infer_modalities_from_files(file_id)
    _, combo = resolve_modality_combo(modalities)
    core, penumbra, mismatch = _ctp_values(structured, imaging)
    ncct = _resolve_ncct(structured, imaging)
    vessel = vessel_result_from_sources(structured, imaging)
    selected_model = str(model or os.environ.get("BAICHUAN_MODEL") or DEFAULT_BAICHUAN_MODEL).strip()
    selected_url = str(api_url or os.environ.get("BAICHUAN_API_URL") or DEFAULT_BAICHUAN_API_URL).strip()
    selected_key = (
        api_key
        if api_key is not None
        else os.environ.get("BAICHUAN_API_KEY") or os.environ.get("BAICHUAN_AK") or ""
    )

    is_mock = not bool(str(selected_key).strip())
    warning = None
    if is_mock:
        provider_report = generate_mock_report(
            structured,
            modalities,
            ncct,
            vessel,
            core,
            penumbra,
            mismatch,
            requested_format,
        )
        warning = "使用本地降级草稿，请配置 BAICHUAN_API_KEY 环境变量"
    else:
        prompt_context = _prompt_context(
            structured, imaging, file_id, modalities, ncct, vessel, core, penumbra, mismatch
        )
        prompt = _build_prompt(prompt_context, requested_format)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {str(selected_key).strip()}",
        }
        request_payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是卒中影像报告助手，只能依据给定结构化证据起草供医生复核的报告。",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.3,
            "top_p": 0.9,
        }
        post = http_post or requests.post
        try:
            response = post(selected_url, headers=headers, json=request_payload, timeout=60)
        except requests.exceptions.Timeout:
            print(f"[BaichuanReport] timeout model={selected_model}")
            return {
                "success": False,
                "error": "百川 M3 API 调用超时",
                "format": requested_format,
            }
        except requests.exceptions.RequestException as exc:
            print(f"[BaichuanReport] request_failed model={selected_model} type={type(exc).__name__}")
            return {
                "success": False,
                "error": f"百川 M3 API 请求失败: {type(exc).__name__}",
                "format": requested_format,
            }
        except Exception as exc:
            print(f"[BaichuanReport] request_failed model={selected_model} type={type(exc).__name__}")
            return {
                "success": False,
                "error": f"百川 M3 API 请求失败: {type(exc).__name__}",
                "format": requested_format,
            }

        print(
            f"[BaichuanReport] response model={selected_model} "
            f"status={getattr(response, 'status_code', 'unknown')}"
        )
        if getattr(response, "status_code", None) != 200:
            return {
                "success": False,
                "error": f"百川 M3 API 调用失败: HTTP {getattr(response, 'status_code', 'unknown')}",
                "format": requested_format,
            }
        try:
            response_payload = response.json()
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "百川 M3 API 返回了无效 JSON",
                "format": requested_format,
            }
        provider_report = _extract_response_content(response_payload)
        if not provider_report:
            return {
                "success": False,
                "error": "百川 M3 API 返回空报告",
                "format": requested_format,
            }
        print(
            f"[BaichuanReport] completed model={selected_model} "
            f"chars={len(provider_report)} elapsed={round(time.time() - started_at, 2)}s"
        )

    report = _restore_identity(provider_report, requested_format, _local_identity(structured))
    report_payload = _build_report_payload(
        structured,
        modalities,
        combo,
        ncct,
        vessel,
        core,
        penumbra,
        mismatch,
        report,
        is_mock,
        selected_model,
    )
    elapsed = round(time.time() - started_at, 2)
    try:
        json_path = _write_result_json(
            Path(results_dir).resolve() if results_dir else default_results_dir(),
            file_id,
            requested_format,
            report,
            report_payload,
            selected_model,
            elapsed,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"报告结果保存失败: {type(exc).__name__}",
            "format": requested_format,
        }
    return {
        "success": True,
        "format": requested_format,
        "report": report,
        "report_payload": report_payload,
        "json_path": json_path,
        "is_mock": is_mock,
        "warning": warning,
    }


__all__ = [
    "_ctp_values",
    "default_results_dir",
    "generate_mock_report",
    "generate_report",
    "infer_modalities_from_files",
    "normalize_modalities",
    "resolve_modality_combo",
]
