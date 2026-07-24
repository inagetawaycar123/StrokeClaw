"""Privacy-minimized, deterministic context extraction for KG routing."""

import re
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple


TASK_ALIASES = {
    "detect_modalities": ("modality_detection",),
    "load_patient_context": ("case_intake_parse", "image_quality_control"),
    "vessel_occlusion": ("vessel_occlusion_classification",),
    "generate_ctp_maps": ("generate_ctp_maps", "pseudo_ctp_generation"),
    "run_stroke_analysis": ("stroke_analysis",),
    "generate_medgemma_report": ("report_generation",),
    "human_confirm": ("doctor_review",),
    "human_review": ("doctor_review",),
}

_TEXT_KEYS = {
    "analysis",
    "conclusion",
    "diagnosis",
    "findings",
    "impression",
    "message",
    "result_summary",
    "summary",
}

_SIGNALS: Sequence[Tuple[Tuple[str, ...], Tuple[str, ...]]] = (
    (("hemorrhage", "intracranial hemorrhage", "脑出血", "颅内出血", "出血"), ("hemorrhage", "脑出血")),
    (("ischemia", "infarct", "脑缺血", "脑梗死", "缺血"), ("ischemia", "脑缺血")),
    (("large vessel", "large-vessel", "lvo", "大血管"), ("large vessel", "lvo", "大血管")),
    (("medium vessel", "medium-vessel", "mevo", "中血管"), ("medium vessel", "mevo", "中血管")),
    (("penumbra", "半暗带"), ("penumbra", "半暗带")),
    (("mismatch", "不匹配"), ("mismatch", "不匹配")),
    (("infarct core", "ischemic core", "核心梗死", "核心区"), ("core", "核心区")),
    (("conflict", "inconsistent", "冲突", "不一致", "矛盾"), ("conflict", "冲突")),
    (("review_required", "需复核", "待复核"), ("review_required", "需复核")),
)

_UNCERTAIN_PREFIXES = (
    r"是否(?:有|存在)?",
    r"有无",
    r"不能排除",
    r"无法排除",
    r"不排除",
    r"尚不能除外",
    r"cannot\s+(?:exclude|rule\s+out)",
    r"could\s+not\s+exclude",
)
_NEGATIVE_PREFIXES = (
    r"未见",
    r"未发现",
    r"未提示",
    r"无",
    r"无明显",
    r"无证据",
    r"否认",
    r"排除",
    r"不支持",
    r"no\s+(?:evidence\s+of\s+)?",
    r"without",
    r"negative\s+for",
    r"ruled\s+out",
)


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"\s+", " ", text).strip()


def _append_unique(target: List[str], values: Iterable[Any]) -> None:
    for value in values or []:
        token = _normalize_text(value)
        if token and token not in target:
            target.append(token)


def _canonical_task_keys(raw_keys: Iterable[Any]) -> List[str]:
    output: List[str] = []
    for raw_key in raw_keys or []:
        key = _normalize_text(raw_key)
        if not key:
            continue
        _append_unique(output, [key])
        _append_unique(output, TASK_ALIASES.get(key, ()))
    return output


def _walk_scalars(value: Any, path: Tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_scalars(item, path + (_normalize_text(key),))
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_scalars(item, path)
        return
    if value not in (None, ""):
        yield path, value


def _polarity(text: str, start: int) -> str:
    prefix = text[max(0, start - 32) : start]
    if any(re.search(pattern + r".{0,6}$", prefix) for pattern in _UNCERTAIN_PREFIXES):
        return "uncertain"
    if any(re.search(pattern + r".{0,6}$", prefix) for pattern in _NEGATIVE_PREFIXES):
        return "negative"
    return "positive"


def _extract_text_signals(
    value: Any,
    positive: List[str],
    negative: List[str],
    uncertain: List[str],
) -> None:
    text = _normalize_text(value)
    if not text:
        return
    for aliases, outputs in _SIGNALS:
        for alias in aliases:
            start = 0
            while True:
                match_index = text.find(_normalize_text(alias), start)
                if match_index < 0:
                    break
                polarity = _polarity(text, match_index)
                destination = (
                    negative
                    if polarity == "negative"
                    else uncertain
                    if polarity == "uncertain"
                    else positive
                )
                _append_unique(destination, outputs)
                start = match_index + max(1, len(alias))


def _is_positive_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    text = _normalize_text(value)
    return text not in {"", "0", "false", "none", "null", "negative", "normal", "no"}


def _extract_structured_signal(
    path: Tuple[str, ...],
    value: Any,
    positive: List[str],
    negative: List[str],
    uncertain: List[str],
) -> None:
    if not path:
        return
    key = path[-1]
    path_text = ".".join(path)
    normalized_value = _normalize_text(value)

    if any(token in key for token in ("core_volume", "core_infarct", "ischemic_core")):
        if _is_positive_value(value):
            _append_unique(positive, ("core", "核心区"))
    if "penumbra" in key and _is_positive_value(value):
        _append_unique(positive, ("penumbra", "半暗带"))
    if "mismatch" in key and _is_positive_value(value):
        _append_unique(positive, ("mismatch", "不匹配"))
    if "review_required" in key and _is_positive_value(value):
        _append_unique(positive, ("review_required", "需复核"))
    if ("conflict" in key or "inconsistent" in key) and _is_positive_value(value):
        _append_unique(positive, ("conflict", "冲突"))

    label_like = any(
        token in key
        for token in (
            "class_result",
            "classification",
            "diagnosis",
            "label",
            "predicted_class",
            "predicted_label",
            "verdict",
        )
    )
    if label_like:
        if any(token in normalized_value for token in ("hemo", "hemorrhage", "脑出血", "颅内出血")):
            _append_unique(positive, ("hemorrhage", "脑出血"))
        elif any(token in normalized_value for token in ("infarct", "ischemia", "脑缺血", "脑梗死")):
            _append_unique(positive, ("ischemia", "脑缺血"))
        elif normalized_value in {"normal", "正常"}:
            _append_unique(positive, ("normal",))

        if "vessel" in path_text or "occlusion" in path_text or "血管" in path_text:
            if any(token in normalized_value for token in ("large vessel", "large_vessel", "lvo", "大血管")):
                _append_unique(positive, ("large vessel", "lvo", "大血管"))
            elif any(token in normalized_value for token in ("medium vessel", "medium_vessel", "mevo", "中血管")):
                _append_unique(positive, ("medium vessel", "mevo", "中血管"))

    if key in _TEXT_KEYS and isinstance(value, str):
        _extract_text_signals(value, positive, negative, uncertain)


def _default_modality_normalizer(values: Iterable[Any]) -> List[str]:
    return [_normalize_text(value) for value in values or [] if _normalize_text(value)]


def build_run_context(
    run: Dict[str, Any],
    events: Iterable[Dict[str, Any]],
    current_dag_node: str = "",
    question: str = "",
    modality_normalizer: Callable[[Iterable[Any]], List[str]] = None,
) -> Dict[str, Any]:
    """Return only task features required for deterministic KG routing."""
    run = run if isinstance(run, dict) else {}
    event_items = [item for item in events or [] if isinstance(item, dict)]
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), dict) else {}
    normalize_modalities = modality_normalizer or _default_modality_normalizer
    modalities = normalize_modalities(planner_input.get("available_modalities") or [])

    raw_task_keys: List[str] = []
    for collection in (run.get("steps") or [], run.get("tool_results") or [], event_items):
        for item in collection:
            if not isinstance(item, dict):
                continue
            key = str(
                item.get("key")
                or item.get("tool_name")
                or item.get("node_name")
                or ""
            ).strip()
            if key:
                raw_task_keys.append(key)
    if current_dag_node:
        raw_task_keys.append(current_dag_node)
    task_keys = _canonical_task_keys(raw_task_keys)
    normalized_raw_task_keys: List[str] = []
    _append_unique(normalized_raw_task_keys, raw_task_keys)

    result_terms: List[str] = []
    negative_result_terms: List[str] = []
    uncertain_result_terms: List[str] = []
    original_question = str(
        planner_input.get("question") or planner_input.get("goal_question") or ""
    ).strip()
    effective_question = str(question or original_question or "").strip()
    signal_sources = [
        run.get("result") or {},
        run.get("tool_results") or [],
        event_items,
    ]
    for source in signal_sources:
        for path, value in _walk_scalars(source):
            _extract_structured_signal(
                path,
                value,
                result_terms,
                negative_result_terms,
                uncertain_result_terms,
            )
    if effective_question:
        _extract_text_signals(
            effective_question,
            result_terms,
            negative_result_terms,
            uncertain_result_terms,
        )

    risk_terms: List[str] = []
    for event in event_items:
        level = _normalize_text(event.get("risk_level"))
        if level in {"high", "medium"}:
            _append_unique(risk_terms, (level,))
    if "conflict" in result_terms or "冲突" in result_terms:
        _append_unique(risk_terms, ("conflict", "冲突"))
    if "review_required" in result_terms or "需复核" in result_terms:
        _append_unique(risk_terms, ("review_required", "需复核"))

    return {
        "run_id": str(run.get("run_id") or "").strip(),
        "modalities": modalities,
        "task_keys": task_keys,
        "raw_task_keys": normalized_raw_task_keys,
        "result_terms": result_terms,
        "negative_result_terms": negative_result_terms,
        "uncertain_result_terms": uncertain_result_terms,
        "risk_terms": risk_terms,
        "original_question": original_question,
    }
