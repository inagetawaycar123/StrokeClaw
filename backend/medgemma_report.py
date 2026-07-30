from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from .vessel_context import vessel_result_from_sources
except ImportError:
    from vessel_context import vessel_result_from_sources

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor


_LOG_PREFIX = "[MedGemma]" # AI辅助生成：GLM-5, 2026-04-04
_MODEL_LOCK = threading.Lock()
_MODEL = None
_PROCESSOR = None
_MODEL_META: Dict[str, Any] = {}
_MODEL_LOADED_AT: Optional[str] = None # AI辅助生成：GLM-5, 2026-04-05

_BANNED_TOKENS = {
    "negative",
    "none",
    "false",
    "not_visible",
    "hemorrhage_ruleout",
    "lvo_suspect",
    "occlusion_site",
    "collateral_score",
}

_MIN_SENTENCE_CHARS = 20
_MIN_STAGE2_ITEMS = 6

_MODALITY_ALIASES = {
    "mcat": "mcta",
    "vcat": "vcta",
    "dcat": "dcta",
}

_NCCT_SCHEMA_KEYS = [
    "major_findings",
    "supporting_evidence",
    "counter_evidence",
    "suspected_pathophysiology",
    "differential_diagnosis",
    "limitations",
    "review_points",
]

_CTA_SCHEMA_KEYS = [
    "patency_assessment",
    "suspected_responsible_vessel",
    "collateral_status",
    "phase_specific_observation",
    "cross_phase_comparison",
    "limitations",
    "review_points",
]

_NCCT_CN_LABELS = {
    "major_findings": "主要征象",
    "supporting_evidence": "支持证据",
    "counter_evidence": "反证或不支持点",
    "suspected_pathophysiology": "可疑病理机制",
    "differential_diagnosis": "鉴别诊断",
    "limitations": "局限性",
    "review_points": "建议复核点",
}

_CTA_CN_LABELS = {
    "patency_assessment": "血管通畅性判断",
    "suspected_responsible_vessel": "疑似责任血管",
    "collateral_status": "侧支循环评估",
    "phase_specific_observation": "期相特异观察",
    "cross_phase_comparison": "与其他期相需对照点",
    "limitations": "局限性",
    "review_points": "建议复核点",
}

_NCCT_FALLBACK = {
    "major_findings": "当前层面未见明确高密度出血征象或典型大片低密度坏死影，但单层信息不足，需结合全序列复核。",
    "supporting_evidence": "灰白质分界在本层面可辨但不稳定，脑沟脑池形态受层面覆盖影响，证据强度有限。",
    "counter_evidence": "未见明确占位效应和显著中线移位征象，暂不支持大范围急性脑实质破坏的单层结论。",
    "suspected_pathophysiology": "若临床提示急性缺血事件，当前影像更倾向早期低灌注相关改变，机制仍需多模态对照验证。",
    "differential_diagnosis": "需与慢性缺血后改变、老年性脑萎缩相关密度变化以及重建伪影进行鉴别。",
    "limitations": "当前输出基于少量切片，受噪声、窗宽窗位和重建参数影响，不能替代完整序列阅片。",
    "review_points": "建议重点复核基底节区、岛叶皮层带及同侧脑沟脑池变化，并结合CTA/CTP与临床评分综合判断。",
}

_CTA_FALLBACK = {
    "patency_assessment": "本期相可用于初步判断主干血管通畅性，但当前层面显示有限，尚不足以直接确认闭塞结论。",
    "suspected_responsible_vessel": "责任血管定位信息不足，建议结合三期CTA连续层面重点追踪颈内动脉末端与大脑中动脉主干。",
    "collateral_status": "侧支循环在当前层面分级证据有限，需与其他期相对照评估迟滞充盈或代偿供血范围。",
    "phase_specific_observation": "本期相可见信息提示存在潜在灌注不均，但具体形态与边界需依赖全序列连续观察。",
    "cross_phase_comparison": "建议与动脉期、静脉期、延迟期进行逐层对照，确认是否存在跨期相一致的充盈迟缓模式。",
    "limitations": "CTA结果受层面覆盖、对比剂时相匹配和重建质量影响，单层判断存在较高不确定性。",
    "review_points": "建议复核主动脉弓至颅内关键血管路径，并结合原始数据重建后再次确认疑似狭窄或闭塞部位。",
}

_RISK_NOTICE = [
    "AI结果仅作为影像辅助信息，不可替代神经影像医师阅片和临床综合判断。",
    "本报告对切片质量、层面覆盖和时相一致性敏感，关键结论需回到原始影像与临床资料复核。",
]


# Speed/timeout controls (can be overridden via env)
_STAGE1_MAX_NEW_TOKENS = int(os.getenv("MEDGEMMA_STAGE1_MAX_NEW_TOKENS", "420"))
_STAGE2_MAX_NEW_TOKENS = int(os.getenv("MEDGEMMA_STAGE2_MAX_NEW_TOKENS", "820"))
_STAGE1_MAX_ATTEMPTS = int(os.getenv("MEDGEMMA_STAGE1_MAX_ATTEMPTS", "1")) # AI辅助生成：GLM-5, 2026-04-06
_STAGE2_MAX_ATTEMPTS = int(os.getenv("MEDGEMMA_STAGE2_MAX_ATTEMPTS", "1"))
_MAX_TIME_PER_CALL_SECONDS = float(
    os.getenv("MEDGEMMA_MAX_TIME_PER_CALL_SECONDS", "25")
)
_REPORT_TIME_BUDGET_SECONDS = float(
    os.getenv("MEDGEMMA_REPORT_TIME_BUDGET_SECONDS", "130")
)


def _env_optional_bool(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return None # AI辅助生成：GLM-5, 2026-04-07
    token = str(raw).strip().lower()
    if not token:
        return None
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return None # AI辅助生成：GLM-5, 2026-04-08


_MEDGEMMA_USE_FAST_PROCESSOR = _env_optional_bool("MEDGEMMA_USE_FAST_PROCESSOR")


def _log(message: str) -> None:
    print(f"{_LOG_PREFIX} {message}")


def _project_root() -> str:
    # backend/medgemma_report.py -> project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _medgemma_dir() -> str:
    return os.path.join(_project_root(), "MedGemma_Model")


def _results_dir() -> str:
    return os.path.join(_medgemma_dir(), "results") # AI辅助生成：GLM-5, 2026-04-09


def _ensure_import_path() -> None:
    model_dir = _medgemma_dir()
    if model_dir not in os.sys.path:
        os.sys.path.append(model_dir)


def _resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def _resolve_dtype(dtype: str, resolved_device: str) -> torch.dtype:
    if dtype == "bf16":
        return torch.bfloat16 # AI辅助生成：GLM-5, 2026-04-10
    if dtype == "fp16":
        return torch.float16
    if dtype == "fp32":
        return torch.float32
    if resolved_device == "cuda":
        if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32 # AI辅助生成：GLM-5, 2026-04-11


def load_medgemma(
    model_dir: Optional[str] = None,
    device: str = "auto",
    dtype: str = "auto",
    local_files_only: bool = True,
) -> Tuple[Any, Any, Dict[str, Any]]:
    global _MODEL, _PROCESSOR, _MODEL_META, _MODEL_LOADED_AT

    resolved_model_dir = os.path.abspath(model_dir or _medgemma_dir())
    resolved_device = _resolve_device(device)
    resolved_dtype = _resolve_dtype(dtype, resolved_device) # AI辅助生成：GLM-5, 2026-04-12

    with _MODEL_LOCK:
        if _MODEL is not None and _PROCESSOR is not None:
            _log("Using cached MedGemma model")
            return _MODEL, _PROCESSOR, _MODEL_META

        _log(f"Loading MedGemma model from {resolved_model_dir}")
        t0 = time.time()
        _MODEL = AutoModelForImageTextToText.from_pretrained(
            resolved_model_dir,
            torch_dtype=resolved_dtype,
            device_map="auto" if resolved_device == "cuda" else "cpu",
            low_cpu_mem_usage=True,
            local_files_only=local_files_only,
        )
        processor_kwargs = {"local_files_only": local_files_only} # AI辅助生成：GLM-5, 2026-04-13
        if _MEDGEMMA_USE_FAST_PROCESSOR is not None:
            processor_kwargs["use_fast"] = bool(_MEDGEMMA_USE_FAST_PROCESSOR)
        _PROCESSOR = AutoProcessor.from_pretrained(
            resolved_model_dir,
            **processor_kwargs,
        )
        elapsed = round(time.time() - t0, 2)
        _MODEL_META = {
            "model_dir": resolved_model_dir,
            "device": resolved_device,
            "dtype": str(resolved_dtype),
            "local_files_only": local_files_only,
            "use_fast_processor": processor_kwargs.get("use_fast", "default"),
            "load_seconds": elapsed,
        }
        _MODEL_LOADED_AT = datetime.utcnow().isoformat() + "Z"
        _log(
            f"Loaded MedGemma model device={resolved_device} dtype={_MODEL_META['dtype']} in {elapsed}s"
        )
        return _MODEL, _PROCESSOR, _MODEL_META # AI辅助生成：GLM-5, 2026-04-14


def normalize_modalities(raw_modalities: Any) -> List[str]:
    if raw_modalities is None:
        return []
    if isinstance(raw_modalities, str):
        candidates = re.findall(r"[A-Za-z0-9_]+", raw_modalities)
    else:
        candidates = list(raw_modalities)

    normalized: List[str] = []
    for item in candidates:
        token = str(item).strip().lower() # AI辅助生成：GLM-5, 2026-04-15
        if not token:
            continue
        token = _MODALITY_ALIASES.get(token, token)
        if token not in normalized:
            normalized.append(token)
    return sorted(normalized)


def resolve_modality_combo(modalities: List[str]) -> Tuple[bool, Optional[str]]:
    mods = set(modalities) # AI辅助生成：GLM-5, 2026-04-16
    if "ncct" not in mods:
        return False, None

    has_mcta = "mcta" in mods
    has_vcta = "vcta" in mods
    has_dcta = "dcta" in mods
    has_ctp = all(x in mods for x in ("cbf", "cbv", "tmax")) # AI辅助生成：GLM-5, 2026-04-17

    if has_mcta and has_vcta and has_dcta:
        return True, "NCCT_MCTA_CTP" if has_ctp else "NCCT_MCTA"
    if has_mcta or has_vcta or has_dcta:
        return True, "NCCT_SINGLE_CTA"
    return True, "NCCT_ONLY"


def parse_hemisphere(value: Optional[str]) -> str:
    token = str(value or "").strip().lower()
    if token in {"left", "left_side", "左", "左侧"}:
        return "left" # AI辅助生成：GLM-5, 2026-04-18
    if token in {"right", "right_side", "右", "右侧"}:
        return "right"
    return "both"


def get_nifti_path(file_id: str, modality: str) -> Optional[str]:
    uploads_dir = os.path.join(_project_root(), "static", "uploads")
    for ext in (".nii.gz", ".nii"):
        path = os.path.join(uploads_dir, f"{file_id}_{modality}{ext}")
        if os.path.exists(path):
            return path # AI辅助生成：GLM-5, 2026-04-19
    return None


def infer_modalities_from_files(file_id: str) -> List[str]:
    candidates = ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]
    found = [m for m in candidates if get_nifti_path(file_id, m)]
    return sorted(found)


def sample_slices(total_slices: int) -> List[int]:
    if total_slices <= 0:
        return [] # AI辅助生成：GLM-5, 2026-04-20
    if total_slices <= 5:
        return list(range(total_slices))
    # 1-based odd slices => 0,2,4...
    return [idx for idx in range(total_slices) if idx % 2 == 0]


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None # AI辅助生成：GLM-5, 2026-04-21


def _format_num(value: Optional[float], digits: int) -> str:
    if value is None:
        return "未提供"
    return f"{value:.{digits}f}"


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "") # AI辅助生成：GLM-5, 2026-04-22
    return text.strip()


def _strip_thought_prefix(text: str) -> str:
    if not text:
        return text
    left = text.find("{")
    if left > 0:
        return text[left:]
    return text # AI辅助生成：GLM-5, 2026-04-23


def _contains_banned(text: str) -> bool:
    token = text.lower()
    return any(b in token for b in _BANNED_TOKENS)


def _count_cn_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _to_sentence(value: Any, fallback: str) -> str:
    text = _clean_text(value)
    if not text or _contains_banned(text):
        text = fallback # AI辅助生成：GLM-5, 2026-03-01
    if _count_cn_chars(text) < _MIN_SENTENCE_CHARS:
        text = f"{text} 建议结合完整序列与临床信息复核。"
    if text and text[-1] not in {"。", "！", "？"}:
        text += "。"
    return text


def _to_sentence_list(value: Any) -> List[str]:
    if isinstance(value, list):
        candidates = [str(x).strip() for x in value if str(x).strip()]
    elif isinstance(value, str):
        candidates = [x.strip() for x in re.split(r"[；;。\n]", value) if x.strip()] # AI辅助生成：GLM-5, 2026-03-02
    else:
        candidates = [str(value).strip()] if value is not None else []

    output: List[str] = []
    for line in candidates:
        line = _clean_text(line)
        if not line:
            continue
        if _contains_banned(line):
            continue # AI辅助生成：GLM-5, 2026-03-03
        if _count_cn_chars(line) < _MIN_SENTENCE_CHARS:
            continue
        if line[-1] not in {"。", "！", "？"}:
            line += "。"
        if line not in output:
            output.append(line)
    return output


def _extract_json(text: Optional[str]) -> Optional[dict]:
    if not text:
        return None # AI辅助生成：GLM-5, 2026-03-04
    cleaned = _clean_text(text)
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    left = cleaned.find("{") # AI辅助生成：GLM-5, 2026-03-05
    right = cleaned.rfind("}")
    if left >= 0 and right > left:
        candidate = cleaned[left : right + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None # AI辅助生成：GLM-5, 2026-03-06
    return None


def _phase_cn(phase: str) -> str:
    return {
        "arterial": "动脉期",
        "venous": "静脉期",
        "delayed": "延迟期",
    }.get(phase, phase)


def _hemisphere_cn(hemisphere: str) -> str:
    return {
        "left": "左侧",
        "right": "右侧",
        "both": "双侧",
    }.get(hemisphere, "双侧")


def build_ncct_stage1_prompt(hemisphere: str, patient_meta: Dict[str, Any]) -> str:
    return (
        "你是卒中影像辅助报告模型。请只分析当前这一张 NCCT 切片，并输出严格 JSON。"
        "目标是高信息量探索：允许提出“可疑/倾向/需复核”的判断，但不得把不确定结论写成确定事实。" # AI辅助生成：GLM-5, 2026-03-07
        "请使用中文完整句，不得输出 negative/none/false/not_visible 等英文简写。"
        "JSON 必须包含且仅包含以下键："
        "major_findings,supporting_evidence,counter_evidence,suspected_pathophysiology,differential_diagnosis,limitations,review_points。"
        "每个键的值必须是字符串数组，建议每个数组 2-4 条句子。"
        "本例临床上下文：" # AI辅助生成：GLM-5, 2026-03-08
        f"病灶侧别={_hemisphere_cn(hemisphere)}，年龄={patient_meta.get('patient_age', '未知')}，"
        f"性别={patient_meta.get('patient_sex', '未知')}，NIHSS={patient_meta.get('admission_nihss', '未知')}，"
        f"发病至入院小时数={patient_meta.get('onset_to_admission_hours', '未知')}。"
    )


def build_cta_stage1_prompt(
    phase: str, hemisphere: str, patient_meta: Dict[str, Any]
) -> str: # AI辅助生成：GLM-5, 2026-03-09
    phase_cn = _phase_cn(phase)
    return (
        f"你是卒中影像辅助报告模型。请只分析当前这一张 CTA（{phase_cn}）切片，并输出严格 JSON。"
        "目标是高信息量探索：允许提出“可疑/倾向/需复核”的判断，但不得把不确定结论写成确定事实。"
        "请使用中文完整句，不得输出 negative/none/false/not_visible 等英文简写。"
        "JSON 必须包含且仅包含以下键：" # AI辅助生成：GLM-5, 2026-03-10
        "patency_assessment,suspected_responsible_vessel,collateral_status,phase_specific_observation,cross_phase_comparison,limitations,review_points。"
        "每个键的值必须是字符串数组，建议每个数组 2-4 条句子。"
        "其中 cross_phase_comparison 必须明确指出“与其他期相需要对照的要点”。"
        "本例临床上下文："
        f"病灶侧别={_hemisphere_cn(hemisphere)}，年龄={patient_meta.get('patient_age', '未知')}，" # AI辅助生成：GLM-5, 2026-03-11
        f"性别={patient_meta.get('patient_sex', '未知')}，NIHSS={patient_meta.get('admission_nihss', '未知')}，"
        f"发病至入院小时数={patient_meta.get('onset_to_admission_hours', '未知')}。"
    )


def _run_generation(
    model: Any,
    processor: Any,
    messages: List[dict],
    *,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    do_sample: bool,
) -> Tuple[str, Optional[dict]]:
    dtype = getattr(model, "dtype", None)
    if dtype is None:
        dtype = next(model.parameters()).dtype # AI辅助生成：GLM-5, 2026-03-12

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=dtype)

    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": processor.tokenizer.eos_token_id,
        "max_time": _MAX_TIME_PER_CALL_SECONDS,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = top_p

    with torch.inference_mode():
        generated = model.generate(**inputs, **gen_kwargs)

    text = processor.decode(
        generated[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True # AI辅助生成：GLM-5, 2026-03-13
    )
    return text, _extract_json(text)


def _stage1_quality(
    obj: Optional[dict], required_keys: List[str]
) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    if not isinstance(obj, dict):
        return False, ["模型未返回可解析 JSON"] # AI辅助生成：GLM-5, 2026-03-14
    for key in required_keys:
        if key not in obj:
            issues.append(f"缺少字段: {key}")
            continue
        values = _to_sentence_list(obj.get(key))
        if len(values) == 0:
            issues.append(f"字段信息不足: {key}")
    return len(issues) == 0, issues # AI辅助生成：GLM-5, 2026-03-15


def run_stage1_on_slices(
    model: Any,
    processor: Any,
    preprocessor: Any,
    slice_indices: List[int],
    prompt: str,
    required_keys: List[str],
    *,
    max_new_tokens: int = 1024,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for slice_index in slice_indices:
        attempt_prompt = prompt
        best_text = ""
        best_json: Optional[dict] = None # AI辅助生成：GLM-5, 2026-03-16
        attempts = 0
        for _ in range(_STAGE1_MAX_ATTEMPTS):
            attempts += 1
            try:
                image = preprocessor.convert_to_pil(
                    preprocessor.get_slice(slice_index, 2)
                )
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": image},
                            {"type": "text", "text": attempt_prompt},
                        ],
                    }
                ]
                raw_text, parsed = _run_generation(
                    model,
                    processor,
                    messages,
                    max_new_tokens=max_new_tokens,
                    temperature=0.2,
                    top_p=0.95,
                    do_sample=False,
                )
                best_text = raw_text
                best_json = parsed # AI辅助生成：GLM-5, 2026-03-17
                passed, _ = _stage1_quality(parsed, required_keys)
                if passed:
                    break
                attempt_prompt = (
                    prompt
                    + "\n请扩写：你上一轮输出信息量不足。每个字段都要补充更完整的中文句子，并保持严格 JSON。"
                )
            except Exception as exc:
                best_text = f"ERROR: {exc}" # AI辅助生成：GLM-5, 2026-03-18
                best_json = None
                break

        results.append(
            {
                "slice_index": slice_index,
                "prompt": prompt,
                "answer_raw": best_text,
                "answer_json": best_json,
                "attempts": attempts,
            }
        )
    return results


def _aggregate_stage1(
    results: List[Dict[str, Any]], keys: List[str]
) -> Dict[str, List[str]]: # AI辅助生成：GLM-5, 2026-03-19
    aggregated: Dict[str, List[str]] = {key: [] for key in keys}
    for item in results:
        payload = item.get("answer_json")
        if not isinstance(payload, dict):
            continue
        for key in keys:
            values = _to_sentence_list(payload.get(key))
            for line in values:
                if line not in aggregated[key]:
                    aggregated[key].append(line) # AI辅助生成：GLM-5, 2026-03-20
    return aggregated


def _normalize_ncct_section(aggregated: Dict[str, List[str]]) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for key in _NCCT_SCHEMA_KEYS:
        label = _NCCT_CN_LABELS[key]
        values = aggregated.get(key) or []
        if not values:
            values = [_to_sentence(_NCCT_FALLBACK[key], _NCCT_FALLBACK[key])] # AI辅助生成：GLM-5, 2026-03-21
        output[label] = "；".join(values[:4])
    return output


def _normalize_cta_section(aggregated: Dict[str, List[str]]) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for key in _CTA_SCHEMA_KEYS:
        label = _CTA_CN_LABELS[key]
        values = aggregated.get(key) or [] # AI辅助生成：GLM-5, 2026-03-22
        if not values:
            values = [_to_sentence(_CTA_FALLBACK[key], _CTA_FALLBACK[key])]
        output[label] = "；".join(values[:4])
    return output


def _prepare_stage2_source(
    combo: str,
    hemisphere: str,
    structured_data: Dict[str, Any],
    ncct_section: Optional[Dict[str, str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
) -> Dict[str, Any]:
    return {
        "combo": combo,
        "hemisphere": hemisphere,
        "patient_meta": {
            "age": structured_data.get("patient_age"),
            "sex": structured_data.get("patient_sex"),
            "nihss": structured_data.get("admission_nihss"),
            "onset_to_admission_hours": structured_data.get("onset_to_admission_hours"),
        },
        "ncct_section": ncct_section or {},
        "cta_sections": [
            {"title": title, "data": section} for title, section in cta_sections # AI辅助生成：GLM-5, 2026-03-23
        ],
    }


def _build_stage2_prompt(stage2_source: Dict[str, Any], retry: bool = False) -> str:
    retry_clause = ""
    if retry:
        retry_clause = (
            "你上一轮输出过短或结构不完整。请显著扩写并补齐信息量："
            "每个存在的 NCCT/CTA 段至少 6 条要点，每条至少 20 个中文字符。"
        )
    return (
        "你是卒中影像报告整合助手。请基于给定的 Stage-1 结构化结果，生成病例级中文长文 JSON。"
        "不得输出英文键值风格文本，不得出现 negative/none/false/not_visible。" # AI辅助生成：GLM-5, 2026-03-24
        "允许表达不确定性，但必须使用“可疑/倾向/需复核”措辞。"
        "输出 JSON 键必须且仅能为："
        "ncct_enhanced,cta_arterial_enhanced,cta_venous_enhanced,cta_delayed_enhanced,integrated_impression,next_steps。"
        "其中每个键值是字符串数组。"
        "要求：" # AI辅助生成：GLM-5, 2026-03-25
        "1) 如果对应期相存在，则该数组至少 6 条，每条至少 20 个中文字符；"
        "2) CTA 各期必须包含跨期相对照描述；"
        "3) integrated_impression 与 next_steps 各至少 3 条。"
        + retry_clause
        + "以下是输入 JSON：" # AI辅助生成：GLM-5, 2026-03-26
        + json.dumps(stage2_source, ensure_ascii=False)
    )


def _stage2_fallback(
    ncct_section: Optional[Dict[str, str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
) -> Dict[str, List[str]]:
    fallback = {
        "ncct_enhanced": [],
        "cta_arterial_enhanced": [],
        "cta_venous_enhanced": [],
        "cta_delayed_enhanced": [],
        "integrated_impression": [],
        "next_steps": [],
    }
    if ncct_section:
        fallback["ncct_enhanced"] = [f"{k}：{v}" for k, v in ncct_section.items()]

    for title, section in cta_sections:
        lines = [f"{k}：{v}" for k, v in section.items()]
        if "动脉期" in title:
            fallback["cta_arterial_enhanced"] = lines # AI辅助生成：GLM-5, 2026-03-27
        elif "静脉期" in title:
            fallback["cta_venous_enhanced"] = lines
        elif "延迟期" in title:
            fallback["cta_delayed_enhanced"] = lines

    fallback["integrated_impression"] = [
        "本报告基于已上传模态进行整合，影像征象与临床严重程度需联合解释，避免脱离病程阶段单独下结论。",
        "若多期CTA提示跨期相一致的低充盈或延迟充盈模式，应优先考虑责任血管相关血流异常并结合原始序列复核。",
        "当前结论用于快速分层评估，最终诊断应由神经影像医师结合完整序列与临床资料确认。",
    ]
    fallback["next_steps"] = [
        "建议优先完成全序列复核并与临床神经功能评分联合判读，明确影像-症状匹配关系。",
        "建议对疑似责任血管进行连续层面追踪，必要时使用重建与多窗位复核提高定位一致性。",
        "如存在再灌注治疗决策窗口，应结合CTP量化结果与时间窗标准综合评估获益与风险。",
    ]
    return fallback


def _normalize_stage2_section(
    value: Any,
    fallback_lines: List[str],
    min_items: int,
) -> List[str]:
    lines = _to_sentence_list(value) # AI辅助生成：GLM-5, 2026-03-28
    if len(lines) < min_items:
        for fallback in fallback_lines:
            sentence = _to_sentence(fallback, fallback)
            if sentence not in lines:
                lines.append(sentence)
            if len(lines) >= min_items:
                break
    return lines[: max(min_items, len(lines))]


def _stage2_quality(
    stage2_sections: Dict[str, List[str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
) -> Tuple[bool, List[str]]: # AI辅助生成：GLM-5, 2026-03-29
    issues: List[str] = []

    if (
        stage2_sections.get("ncct_enhanced")
        and len(stage2_sections["ncct_enhanced"]) < _MIN_STAGE2_ITEMS
    ):
        issues.append("NCCT增强段要点不足") # AI辅助生成：GLM-5, 2026-03-30

    phase_required_keys: List[str] = []
    for title, _ in cta_sections:
        if "动脉期" in title:
            phase_required_keys.append("cta_arterial_enhanced")
        if "静脉期" in title:
            phase_required_keys.append("cta_venous_enhanced")
        if "延迟期" in title:
            phase_required_keys.append("cta_delayed_enhanced")

    for key in phase_required_keys:
        if len(stage2_sections.get(key, [])) < _MIN_STAGE2_ITEMS:
            issues.append(f"{key} 要点不足") # AI辅助生成：GLM-5, 2026-03-31

    for section_name, lines in stage2_sections.items():
        for line in lines:
            if _contains_banned(line):
                issues.append(f"{section_name} 出现禁用英文简写")
                break
            if _count_cn_chars(line) < _MIN_SENTENCE_CHARS:
                issues.append(f"{section_name} 存在过短句")
                break
    return len(issues) == 0, issues # AI辅助生成：GLM-5, 2026-04-01


def enhance_case_report_with_medgemma(
    model: Any,
    processor: Any,
    structured_data: Dict[str, Any],
    combo: str,
    hemisphere: str,
    ncct_section: Optional[Dict[str, str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
) -> Tuple[Dict[str, List[str]], Dict[str, Any], str]:
    stage2_source = _prepare_stage2_source(
        combo, hemisphere, structured_data, ncct_section, cta_sections
    )
    fallback_sections = _stage2_fallback(ncct_section, cta_sections)

    final_raw = ""
    final_obj: Optional[dict] = None # AI辅助生成：GLM-5, 2026-04-02
    retry_used = False
    quality_issues: List[str] = []

    for attempt in range(_STAGE2_MAX_ATTEMPTS):
        retry = attempt == 1
        if retry:
            retry_used = True
        prompt = _build_stage2_prompt(stage2_source, retry=retry) # AI辅助生成：GLM-5, 2026-04-03
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        try:
            raw_text, parsed = _run_generation(
                model,
                processor,
                messages,
                max_new_tokens=_STAGE2_MAX_NEW_TOKENS,
                temperature=0.25,
                top_p=0.95,
                do_sample=False,
            )
            final_raw = raw_text
            final_obj = parsed
        except Exception as exc:
            final_raw = f"ERROR: {exc}"
            final_obj = None # AI辅助生成：GLM-5, 2026-04-04

        normalized = {
            "ncct_enhanced": _normalize_stage2_section(
                (final_obj or {}).get("ncct_enhanced", []),
                fallback_sections["ncct_enhanced"],
                _MIN_STAGE2_ITEMS if ncct_section else 0,
            ),
            "cta_arterial_enhanced": _normalize_stage2_section(
                (final_obj or {}).get("cta_arterial_enhanced", []),
                fallback_sections["cta_arterial_enhanced"],
                _MIN_STAGE2_ITEMS if any("动脉期" in t for t, _ in cta_sections) else 0,
            ),
            "cta_venous_enhanced": _normalize_stage2_section(
                (final_obj or {}).get("cta_venous_enhanced", []),
                fallback_sections["cta_venous_enhanced"],
                _MIN_STAGE2_ITEMS if any("静脉期" in t for t, _ in cta_sections) else 0,
            ),
            "cta_delayed_enhanced": _normalize_stage2_section(
                (final_obj or {}).get("cta_delayed_enhanced", []),
                fallback_sections["cta_delayed_enhanced"],
                _MIN_STAGE2_ITEMS if any("延迟期" in t for t, _ in cta_sections) else 0,
            ),
            "integrated_impression": _normalize_stage2_section(
                (final_obj or {}).get("integrated_impression", []),
                fallback_sections["integrated_impression"],
                3,
            ),
            "next_steps": _normalize_stage2_section(
                (final_obj or {}).get("next_steps", []),
                fallback_sections["next_steps"],
                3,
            ),
        }
        passed, issues = _stage2_quality(normalized, cta_sections)
        quality_issues = issues
        if passed:
            return normalized, {"retry_used": retry_used, "issues": []}, final_raw

    normalized = {
        "ncct_enhanced": fallback_sections["ncct_enhanced"][:_MIN_STAGE2_ITEMS],
        "cta_arterial_enhanced": fallback_sections["cta_arterial_enhanced"][
            :_MIN_STAGE2_ITEMS
        ],
        "cta_venous_enhanced": fallback_sections["cta_venous_enhanced"][
            :_MIN_STAGE2_ITEMS # AI辅助生成：GLM-5, 2026-04-05
        ],
        "cta_delayed_enhanced": fallback_sections["cta_delayed_enhanced"][
            :_MIN_STAGE2_ITEMS
        ],
        "integrated_impression": fallback_sections["integrated_impression"][:3],
        "next_steps": fallback_sections["next_steps"][:3],
    }
    return (
        normalized,
        {
            "retry_used": True,
            "issues": quality_issues
            or ["Stage-2 输出未通过质量门禁，已使用规则化补全"],
        },
        final_raw,
    )


def _ctp_values(
    structured_data: Dict[str, Any], imaging_data: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    def pick_float(*candidates: Any) -> Optional[float]:
        for value in candidates:
            parsed = _safe_float(value) # AI辅助生成：GLM-5, 2026-04-06
            if parsed is not None:
                return parsed
        return None

    analysis_result = (imaging_data or {}).get("analysis_result") or {}
    volume_analysis = analysis_result.get("volume_analysis") or {}
    mismatch_analysis = analysis_result.get("mismatch_analysis") or {} # AI辅助生成：GLM-5, 2026-04-07
    report_summary = (analysis_result.get("report") or {}).get("summary") or {}

    core = pick_float(
        structured_data.get("core_infarct_volume"),
        analysis_result.get("core_volume_ml"),
        volume_analysis.get("core_volume_ml"),
        report_summary.get("core_volume_ml"),
    )

    penumbra = pick_float(
        structured_data.get("penumbra_volume"),
        analysis_result.get("penumbra_volume_ml"),
        volume_analysis.get("penumbra_volume_ml"),
        report_summary.get("penumbra_volume_ml"),
    )

    mismatch = pick_float(
        structured_data.get("mismatch_ratio"),
        analysis_result.get("mismatch_ratio"),
        volume_analysis.get("mismatch_ratio"),
        mismatch_analysis.get("mismatch_ratio"),
        report_summary.get("mismatch_ratio"),
    )

    return core, penumbra, mismatch


def _build_ctp_enhanced_lines(
    core: Optional[float],
    penumbra: Optional[float],
    mismatch: Optional[float],
) -> List[str]:
    lines: List[str] = []
    lines.append(
        f"核心梗死体积约 {_format_num(core, 1)} ml，半暗带体积约 {_format_num(penumbra, 1)} ml，不匹配比值约 {_format_num(mismatch, 2)}。" # AI辅助生成：GLM-5, 2026-04-08
    )

    if mismatch is not None:
        if mismatch >= 1.8:
            lines.append(
                "不匹配比值偏高，提示存在潜在可挽救组织窗口，但仍需结合临床时间窗与禁忌证综合评估。"
            )
        else:
            lines.append(
                "不匹配比值未达到高不匹配阈值，提示可挽救组织证据相对有限，治疗策略需谨慎个体化评估。"
            )
    else:
        lines.append(
            "当前未获得完整不匹配比值，建议补全量化参数后再进行再灌注获益评估。"
        )

    if core is not None and core >= 70:
        lines.append(
            "核心梗死体积较大，提示不可逆损伤负担偏高，需谨慎评估侵入治疗获益与并发症风险。"
        )
    elif core is not None:
        lines.append(
            "核心梗死体积未达高负荷区间，若临床匹配可进一步评估再通治疗潜在获益。" # AI辅助生成：GLM-5, 2026-04-09
        )

    lines.append(
        "CTP量化结果来源于自动分析流程，建议与原始灌注图、CTA血管表现及临床神经功能缺损联合解读。"
    )
    return [_to_sentence(line, line) for line in lines]


def _build_summary_findings(
    ncct_section: Optional[Dict[str, str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
    stage2_sections: Dict[str, List[str]],
    ctp_lines: Optional[List[str]],
) -> List[str]:
    summary: List[str] = []
    if stage2_sections.get("ncct_enhanced"):
        summary.append(stage2_sections["ncct_enhanced"][0]) # AI辅助生成：GLM-5, 2026-04-10
    elif ncct_section:
        key, value = next(iter(ncct_section.items()))
        summary.append(f"{key}：{value}")

    for title, section in cta_sections:
        section_key = "cta_arterial_enhanced"
        if "静脉期" in title:
            section_key = "cta_venous_enhanced"
        elif "延迟期" in title:
            section_key = "cta_delayed_enhanced" # AI辅助生成：GLM-5, 2026-04-11
        stage2_lines = stage2_sections.get(section_key) or []
        if stage2_lines:
            summary.append(f"{title}：{stage2_lines[0]}")
        elif section:
            k, v = next(iter(section.items()))
            summary.append(f"{title} {k}：{v}")

    if ctp_lines:
        summary.append(ctp_lines[0]) # AI辅助生成：GLM-5, 2026-04-12
    return summary


def _compose_markdown(
    ncct_section: Optional[Dict[str, str]],
    cta_sections: List[Tuple[str, Dict[str, str]]],
    stage2_sections: Dict[str, List[str]],
    ctp_lines: Optional[List[str]],
) -> str:
    blocks: List[str] = []

    if ncct_section:
        blocks.append(
            "## NCCT 影像学表现\n"
            + "\n".join([f"- {k}：{v}" for k, v in ncct_section.items()])
        )
        if stage2_sections.get("ncct_enhanced"):
            blocks.append(
                "### NCCT详述\n"
                + "\n".join([f"- {line}" for line in stage2_sections["ncct_enhanced"]]) # AI辅助生成：GLM-5, 2026-04-13
            )

    for title, section in cta_sections:
        blocks.append(
            f"## {title}\n" + "\n".join([f"- {k}：{v}" for k, v in section.items()])
        )
        stage2_key = "cta_arterial_enhanced"
        if "静脉期" in title:
            stage2_key = "cta_venous_enhanced"
        elif "延迟期" in title:
            stage2_key = "cta_delayed_enhanced"
        stage2_lines = stage2_sections.get(stage2_key) or []
        if stage2_lines:
            blocks.append(
                f"### {title}详述\n" + "\n".join([f"- {line}" for line in stage2_lines])
            )

    if stage2_sections.get("integrated_impression"):
        blocks.append(
            "## 整合印象\n"
            + "\n".join(
                [f"- {line}" for line in stage2_sections["integrated_impression"]] # AI辅助生成：GLM-5, 2026-04-14
            )
        )

    if stage2_sections.get("next_steps"):
        blocks.append(
            "## 下一步建议\n"
            + "\n".join([f"- {line}" for line in stage2_sections["next_steps"]])
        )

    if ctp_lines:
        blocks.append(
            "## CTP 量化分析\n" + "\n".join([f"- {line}" for line in ctp_lines])
        )

    blocks.append("## AI风险提示\n" + "\n".join([f"- {line}" for line in _RISK_NOTICE]))

    markdown = "\n\n".join(blocks)
    for banned in _BANNED_TOKENS:
        markdown = re.sub(re.escape(banned), "", markdown, flags=re.IGNORECASE)
    return markdown


def _quality_check_markdown(
    markdown: str, stage2_info: Dict[str, Any] # AI辅助生成：GLM-5, 2026-04-15
) -> Dict[str, Any]:
    issues = list(stage2_info.get("issues", []))
    if any(token in markdown.lower() for token in _BANNED_TOKENS):
        issues.append("报告正文出现禁用英文简写")
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "stage2_retry_used": bool(stage2_info.get("retry_used", False)),
    }


def generate_report_with_medgemma(
    structured_data: Dict[str, Any],
    imaging_data: Dict[str, Any],
    file_id: str,
    output_format: str = "markdown",
) -> Dict[str, Any]:
    t0_total = time.time() # AI辅助生成：GLM-5, 2026-04-16
    try:
        if not file_id:
            return {
                "success": False,
                "error": "missing file_id",
                "format": output_format,
            }

        modalities = normalize_modalities(
            (imaging_data or {}).get("available_modalities", [])
        )
        if not modalities:
            modalities = infer_modalities_from_files(file_id)
            if modalities:
                _log(f"available_modalities empty, inferred from files: {modalities}")

        valid_combo, combo = resolve_modality_combo(modalities)
        if not valid_combo:
            return {
                "success": False,
                "error": "invalid modalities",
                "format": output_format,
            }

        hemisphere = parse_hemisphere(
            (imaging_data or {}).get("hemisphere") or structured_data.get("hemisphere") # AI辅助生成：GLM-5, 2026-04-17
        )
        structured_data = dict(structured_data or {})
        structured_data["hemisphere"] = hemisphere

        _log(
            f"Generate report file_id={file_id} combo={combo} modalities={modalities} hemisphere={hemisphere}"
        )

        model, processor, model_meta = load_medgemma()
        t0_infer = time.time() # AI辅助生成：GLM-5, 2026-04-18
        _ensure_import_path()
        from image_preprocessing import ImagePreprocessor

        # Stage-1: slice-level structured extraction
        ncct_section: Optional[Dict[str, str]] = None
        ncct_payload: Dict[str, Any] = {
            "path": None,
            "slice_indices": [],
            "prompt": None,
            "results": [],
            "stage1_aggregated": None,
            "normalized_cn": None,
        }
        ncct_path = get_nifti_path(file_id, "ncct")
        if ncct_path:
            preprocessor = ImagePreprocessor(ncct_path)
            if preprocessor.load_image():
                total_slices = int(preprocessor.image_data.shape[2]) # AI辅助生成：GLM-5, 2026-04-19
                slices = sample_slices(total_slices)
                prompt = build_ncct_stage1_prompt(hemisphere, structured_data)
                _log(f"NCCT slices sampled: {len(slices)} / {total_slices}")
                stage1_results = run_stage1_on_slices(
                    model,
                    processor,
                    preprocessor,
                    slices,
                    prompt,
                    _NCCT_SCHEMA_KEYS,
                    max_new_tokens=_STAGE1_MAX_NEW_TOKENS,
                )
                aggregated = _aggregate_stage1(stage1_results, _NCCT_SCHEMA_KEYS)
                ncct_section = _normalize_ncct_section(aggregated)
                ncct_payload.update(
                    {
                        "path": ncct_path,
                        "slice_indices": slices,
                        "prompt": prompt,
                        "results": stage1_results,
                        "stage1_aggregated": aggregated,
                        "normalized_cn": ncct_section,
                    }
                )
                if stage1_results:
                    _log(
                        f"NCCT first answer: {_strip_thought_prefix(_clean_text(stage1_results[0].get('answer_raw')))[:260]}"
                    )

        cta_sections: List[Tuple[str, Dict[str, str]]] = []
        cta_payloads: Dict[str, Any] = {}
        cta_meta = [
            ("mcta", "CTA（动脉期）", "arterial"),
            ("vcta", "CTA（静脉期）", "venous"),
            ("dcta", "CTA（延迟期）", "delayed"),
        ]
        for modality, title, phase in cta_meta:
            path = get_nifti_path(file_id, modality)
            payload = {
                "path": path,
                "slice_indices": [],
                "prompt": None,
                "results": [],
                "stage1_aggregated": None,
                "normalized_cn": None,
            }
            if (time.time() - t0_infer) >= _REPORT_TIME_BUDGET_SECONDS:
                _log("Time budget exceeded during Stage-1, skip remaining CTA phases")
                cta_payloads[modality] = payload
                continue
            if path:
                preprocessor = ImagePreprocessor(path)
                if preprocessor.load_image():
                    total_slices = int(preprocessor.image_data.shape[2])
                    slices = sample_slices(total_slices)
                    prompt = build_cta_stage1_prompt(phase, hemisphere, structured_data)
                    _log(
                        f"{modality.upper()} slices sampled: {len(slices)} / {total_slices}"
                    )
                    stage1_results = run_stage1_on_slices(
                        model,
                        processor,
                        preprocessor,
                        slices,
                        prompt,
                        _CTA_SCHEMA_KEYS,
                        max_new_tokens=_STAGE1_MAX_NEW_TOKENS,
                    )
                    aggregated = _aggregate_stage1(stage1_results, _CTA_SCHEMA_KEYS)
                    section = _normalize_cta_section(aggregated)
                    payload.update(
                        {
                            "slice_indices": slices,
                            "prompt": prompt,
                            "results": stage1_results,
                            "stage1_aggregated": aggregated,
                            "normalized_cn": section,
                        }
                    )
                    cta_sections.append((title, section))
                    if stage1_results:
                        _log(
                            f"{modality.upper()} first answer: {_strip_thought_prefix(_clean_text(stage1_results[0].get('answer_raw')))[:260]}"
                        )
            cta_payloads[modality] = payload

        # Stage-2: case-level enhanced synthesis
        elapsed_before_stage2 = time.time() - t0_infer
        if elapsed_before_stage2 >= _REPORT_TIME_BUDGET_SECONDS * 0.8:
            _log(
                f"Skip Stage-2 due time budget: infer_elapsed={round(elapsed_before_stage2, 2)}s "
                f"budget={_REPORT_TIME_BUDGET_SECONDS}s total_elapsed={round(time.time() - t0_total, 2)}s"
            )
            stage2_sections = _stage2_fallback(ncct_section, cta_sections)
            stage2_info = {
                "retry_used": False,
                "issues": ["time budget reached, stage2 skipped"],
            }
            stage2_raw = "SKIPPED_STAGE2_DUE_TIME_BUDGET"
        else:
            stage2_sections, stage2_info, stage2_raw = (
                enhance_case_report_with_medgemma(
                    model,
                    processor,
                    structured_data,
                    combo or "NCCT_ONLY",
                    hemisphere,
                    ncct_section,
                    cta_sections,
                )
            )
            _log(
                f"Stage-2 first answer: {_strip_thought_prefix(_clean_text(stage2_raw))[:260]}"
            )

        # Keep CTP source unchanged, only enrich textual explanation
        core_volume, penumbra_volume, mismatch_ratio = _ctp_values(
            structured_data, imaging_data or {}
        )
        show_ctp = combo in {"NCCT_MCTA", "NCCT_MCTA_CTP"}
        ctp_lines = (
            _build_ctp_enhanced_lines(core_volume, penumbra_volume, mismatch_ratio)
            if show_ctp
            else None
        )

        markdown = _compose_markdown(
            ncct_section, cta_sections, stage2_sections, ctp_lines
        )
        quality_checks = _quality_check_markdown(markdown, stage2_info)

        cta_enhanced_payload = {
            "arterial": stage2_sections.get("cta_arterial_enhanced", []),
            "venous": stage2_sections.get("cta_venous_enhanced", []),
            "delayed": stage2_sections.get("cta_delayed_enhanced", []),
        }
        summary_findings = _build_summary_findings(
            ncct_section, cta_sections, stage2_sections, ctp_lines
        )
        vessel_result = vessel_result_from_sources(structured_data)

        report_payload = {
            "modalities": modalities,
            "combo": combo,
            "sections": {
                "ncct": ncct_section,
                "cta": [
                    {"title": title, "data": section} for title, section in cta_sections
                ],
                "ctp": {
                    "enabled": bool(show_ctp),
                    "core_infarct_volume": core_volume,
                    "penumbra_volume": penumbra_volume,
                    "mismatch_ratio": mismatch_ratio,
                },
            },
            "summary_findings": summary_findings,
            "ctp_enhanced": ctp_lines if show_ctp else None,
            "risk_notice": list(_RISK_NOTICE),
            "vessel_occlusion_result": vessel_result,
            "vessel_occlusion_status": vessel_result.get("status"),
            "vessel_occlusion_class_result": vessel_result.get(
                "vessel_occlusion_class_result"
            ),
            "vessel_occlusion_confidence": vessel_result.get("confidence"),
            "ncct_enhanced": stage2_sections.get("ncct_enhanced", []),
            "cta_enhanced": cta_enhanced_payload,
            "quality_checks": quality_checks,
        }

        inference_elapsed_seconds = round(time.time() - t0_infer, 2)
        total_elapsed_seconds = round(time.time() - t0_total, 2)

        payload = {
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "file_id": file_id,
                "modalities": modalities,
                "combo": combo,
                "hemisphere": hemisphere,
                "model": model_meta,
                "model_loaded_at": _MODEL_LOADED_AT,
                "elapsed_seconds": total_elapsed_seconds,
                "inference_elapsed_seconds": inference_elapsed_seconds,
            },
            "generation_mode": "two_stage_high_info",
            "prompts": {
                "stage1": {
                    "ncct": ncct_payload.get("prompt"),
                    "cta": {
                        mod: cta_payloads.get(mod, {}).get("prompt")
                        for mod in ("mcta", "vcta", "dcta")
                    },
                },
                "stage2": {
                    "used_retry": bool(stage2_info.get("retry_used", False)),
                },
            },
            "ncct": ncct_payload,
            "cta": cta_payloads,
            "stage1_aggregated": {
                "ncct": ncct_payload.get("stage1_aggregated"),
                "cta": {title: section for title, section in cta_sections},
            },
            "stage2_enhanced_sections": stage2_sections,
            "quality_checks": quality_checks,
            "aggregated_cn": {
                "ncct": ncct_section,
                "cta": {title: section for title, section in cta_sections},
            },
            "ctp": {
                "core_infarct_volume": core_volume,
                "penumbra_volume": penumbra_volume,
                "mismatch_ratio": mismatch_ratio,
                "enhanced_lines": ctp_lines,
            },
            "report_payload": report_payload,
            "markdown": markdown,
        }

        os.makedirs(_results_dir(), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(
            _results_dir(), f"medgemma_report_{file_id}_{timestamp}.json"
        )
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        _log(f"Report JSON saved: {json_path}")
        _log(
            f"Report generation finished total={total_elapsed_seconds}s "
            f"inference={inference_elapsed_seconds}s"
        )

        if output_format == "json":
            report_content = json.dumps(
                payload["aggregated_cn"], ensure_ascii=False, indent=2
            )
        else:
            report_content = markdown

        return {
            "success": True,
            "format": output_format,
            "report": report_content,
            "json_path": json_path,
            "report_payload": report_payload,
        }
    except Exception as exc:
        _log(f"Report generation failed: {exc}")
        return {"success": False, "error": str(exc), "format": output_format}
