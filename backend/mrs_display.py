from __future__ import annotations

import math
from typing import Any, Dict, Mapping


_CONFIDENCE_LEVELS = {"high", "medium", "low"}


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _safe_probability(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0 or parsed > 1:
        return None
    return round(parsed, 6)


def _safe_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unavailable(raw: Mapping[str, Any] | None = None, reason: str = "") -> Dict[str, Any]:
    source = _as_dict(raw)
    message = reason or _text(source.get("message")) or "未生成 90 天 mRS 预测结果。"
    return {
        "status": "unavailable",
        "result_mode": _text(source.get("result_mode")) or None,
        "display_mode": _text(source.get("display_mode")) or None,
        "prediction": None,
        "confidence": {
            "level": "unavailable",
            "ensemble_std": None,
            "threshold_margin": None,
            "reasons": [message],
        },
        "key_evidence": {
            "clinical": [],
            "imaging": [],
            "attribution_notice": "模型归因不代表因果关系。",
        },
        "data_quality": {
            "missing_clinical_fields": [],
            "image_quality_warnings": [],
        },
        "doctor_review_recommendation": {
            "review_level": "unavailable",
            "items": ["模型结果不可用，请勿使用启发式结果替代。"],
        },
        "model": {
            "model_version": None,
            "bundle_version": None,
            "release_status": None,
            "external_validation_completed": False,
            "production_approved": False,
            "probability_calibrated": None,
        },
        "fallback_used": bool(source.get("fallback_used")),
        "fallback_reason": _text(source.get("fallback_reason")) or None,
        "deterministic_summary": message,
        "limitations": [
            "当前没有可用于展示的有效 90 天功能预后预测。",
            "不得将缺失结果替换为 0% 或启发式概率。",
        ],
    }


def normalize_mrs_prognosis_result(raw_result: Any) -> Dict[str, Any]:
    """Validate and sanitize the research MVP output for UI/report use.

    Patient identifiers, file paths, raw logits and source filenames are not
    copied into this contract.
    """

    raw = _as_dict(raw_result)
    if _text(raw.get("status")).lower() != "completed":
        return _unavailable(raw)

    prediction = _as_dict(raw.get("prediction"))
    good = _safe_probability(prediction.get("good_prognosis_probability"))
    poor = _safe_probability(prediction.get("poor_prognosis_risk"))
    threshold = _safe_probability(prediction.get("decision_threshold"))
    try:
        predicted_class = int(prediction.get("predicted_class"))
    except (TypeError, ValueError):
        predicted_class = -1

    if good is None or poor is None or threshold is None:
        return _unavailable(raw, "90 天 mRS 预测概率或决策阈值无效。")
    if abs((good + poor) - 1.0) > 0.02:
        return _unavailable(raw, "90 天 mRS 两类预测概率不互补。")
    expected_class = int(poor >= threshold)
    if predicted_class not in {0, 1} or predicted_class != expected_class:
        return _unavailable(raw, "90 天 mRS 预测类别与决策阈值不一致。")

    class_name = _text(prediction.get("class_name"))
    expected_name = "mRS 3-6 / 不良预后" if predicted_class == 1 else "mRS 0-2 / 良好预后"
    if not class_name or ("mRS 3-6" not in class_name and "mRS 0-2" not in class_name):
        class_name = expected_name
    elif (predicted_class == 1 and "mRS 3-6" not in class_name) or (
        predicted_class == 0 and "mRS 0-2" not in class_name
    ):
        return _unavailable(raw, "90 天 mRS 预测类别名称与模型类别不一致。")
    class_name = expected_name

    confidence_raw = _as_dict(raw.get("confidence"))
    confidence_level = _text(confidence_raw.get("level")).lower()
    if confidence_level not in _CONFIDENCE_LEVELS:
        confidence_level = "unknown"
    ensemble_std = _safe_number(
        confidence_raw.get("ensemble_std")
        if confidence_raw.get("ensemble_std") is not None
        else confidence_raw.get("ensemble_probability_std")
    )
    threshold_margin = _safe_number(confidence_raw.get("threshold_margin"))

    clinical = []
    for item in _as_list(_as_dict(raw.get("key_evidence")).get("clinical"))[:3]:
        if not isinstance(item, Mapping):
            continue
        clinical.append(
            {
                "feature": _text(item.get("feature")) or None,
                "display_name": _text(item.get("display_name")) or _text(item.get("feature")) or "临床因素",
                "value": _safe_number(item.get("value")),
                "contribution": _safe_number(item.get("contribution")),
                "direction": _text(item.get("direction")) or "unknown",
                "attribution_method": _text(item.get("attribution_method")) or None,
            }
        )

    imaging = []
    for index, item in enumerate(
        _as_list(_as_dict(raw.get("key_evidence")).get("imaging"))[:3], start=1
    ):
        if not isinstance(item, Mapping):
            continue
        imaging.append(
            {
                "region_label": f"NCCT 关注区域 {index}",
                "channel": _text(item.get("channel")) or "NCCT",
                "attention_score": _safe_probability(item.get("attention_score")),
                "contribution_direction": _text(item.get("contribution_direction")) or "unknown",
                "interpretation": _text(item.get("interpretation"))
                or "模型关注区域；attention 不代表因果贡献或确定病灶。",
            }
        )

    quality_raw = _as_dict(raw.get("data_quality"))
    review_raw = _as_dict(raw.get("doctor_review_recommendation"))
    model_raw = _as_dict(raw.get("model"))
    display_mode = _text(raw.get("display_mode")) or (
        "24小时更新评估" if _text(raw.get("result_mode")) == "update_24h" else "首诊初步评估"
    )
    confidence_cn = {
        "high": "高",
        "medium": "中",
        "low": "低",
        "unknown": "未知",
    }[confidence_level]
    class_cn = "不良预后" if predicted_class == 1 else "良好预后"
    deterministic_summary = (
        f"{display_mode}模型预测 90 天 mRS 0-2 概率为 {good * 100:.1f}%，"
        f"mRS 3-6 风险为 {poor * 100:.1f}%，当前预测为{class_cn}，"
        f"模型置信度为{confidence_cn}。"
    )
    return {
        "status": "completed",
        "result_mode": _text(raw.get("result_mode")) or None,
        "display_mode": display_mode,
        "prediction": {
            "good_prognosis_probability": good,
            "poor_prognosis_risk": poor,
            "predicted_class": predicted_class,
            "class_name": class_name,
            "decision_threshold": threshold,
            "probability_calibrated": prediction.get("probability_calibrated") is True,
        },
        "confidence": {
            "level": confidence_level,
            "ensemble_std": ensemble_std,
            "threshold_margin": threshold_margin,
            "reasons": [_text(item) for item in _as_list(confidence_raw.get("reasons")) if _text(item)],
        },
        "key_evidence": {
            "clinical": clinical,
            "imaging": imaging,
            "attribution_notice": _text(_as_dict(raw.get("key_evidence")).get("attribution_notice"))
            or "模型归因不代表因果关系。",
        },
        "data_quality": {
            "missing_clinical_fields": [
                _text(item)
                for item in _as_list(quality_raw.get("missing_clinical_fields"))
                if _text(item)
            ],
            "image_quality_warnings": [
                _text(item)
                for item in _as_list(quality_raw.get("image_quality_warnings"))
                if _text(item)
            ],
        },
        "doctor_review_recommendation": {
            "review_level": _text(review_raw.get("review_level")) or "routine_review",
            "items": [_text(item) for item in _as_list(review_raw.get("items")) if _text(item)],
        },
        "model": {
            "model_version": _text(model_raw.get("model_version")) or None,
            "bundle_version": _text(model_raw.get("bundle_version")) or None,
            "release_status": _text(model_raw.get("release_status")) or None,
            "external_validation_completed": model_raw.get("external_validation_completed") is True,
            "production_approved": model_raw.get("production_approved") is True,
            "probability_calibrated": prediction.get("probability_calibrated") is True,
        },
        "fallback_used": bool(raw.get("fallback_used")),
        "fallback_reason": _text(raw.get("fallback_reason")) or None,
        "deterministic_summary": deterministic_summary,
        "limitations": [
            "该输出仅提供 mRS 0-2 与 mRS 3-6 两组概率，不代表具体 mRS 分数。",
            "该研究型 MVP 尚未完成外部验证，也未获准用于临床生产决策。",
            "模型归因不代表因果关系，最终判断需由医生结合完整临床资料作出。",
        ],
    }


def mrs_prompt_context(raw_result: Any) -> Dict[str, Any]:
    """Return only de-identified mRS facts suitable for an external prompt."""

    normalized = normalize_mrs_prognosis_result(raw_result)
    if normalized.get("status") != "completed":
        return {"status": "unavailable", "message": normalized["deterministic_summary"]}
    return normalized
