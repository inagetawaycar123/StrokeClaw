"""Shared vessel-occlusion result contract and safe compatibility helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


VESSEL_OCCLUSION_UNAVAILABLE_TEXT = "未获得模型结果"
# Backward-compatible display fallback. It must never imply a positive LVO result.
VESSEL_OCCLUSION_CLASS_RESULT = VESSEL_OCCLUSION_UNAVAILABLE_TEXT
VESSEL_CLASS_KEYS = ("Class_0", "Class_1_LVO", "Class_2_MEVO")
VESSEL_RESULT_STATUSES = {"completed", "failed", "unavailable"}


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return max(0, int(default or 0))


def empty_vessel_occlusion_result(
    status: str = "unavailable",
    *,
    total_slices: int = 0,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    failures: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_status = str(status or "unavailable").strip().lower()
    if normalized_status not in VESSEL_RESULT_STATUSES:
        normalized_status = "unavailable"
    return {
        "status": normalized_status,
        "vessel_occlusion_class_result": None,
        "predicted_class": None,
        "confidence": None,
        "class_counts": {key: 0 for key in VESSEL_CLASS_KEYS},
        "total_slices": _nonnegative_int(total_slices),
        "valid_predictions": 0,
        "error_code": str(error_code) if error_code else None,
        "error_message": str(error_message) if error_message else None,
        "failures": [dict(item) for item in (failures or []) if isinstance(item, dict)],
    }


def normalize_vessel_occlusion_result(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return empty_vessel_occlusion_result()

    source = payload.get("vessel_occlusion_result")
    if isinstance(source, dict):
        payload = source

    raw_label = payload.get("vessel_occlusion_class_result") or payload.get("predicted_label")
    label = str(raw_label).strip() if raw_label is not None else ""
    if label == VESSEL_OCCLUSION_UNAVAILABLE_TEXT:
        label = ""

    counts_payload = payload.get("class_counts")
    normalized_counts = {key: 0 for key in VESSEL_CLASS_KEYS}
    if isinstance(counts_payload, dict):
        normalized_counts = {
            key: _nonnegative_int(counts_payload.get(key)) for key in VESSEL_CLASS_KEYS
        }
    valid_predictions = _nonnegative_int(payload.get("valid_predictions"))
    predicted_class = payload.get("predicted_class")
    has_prediction_evidence = (
        predicted_class in VESSEL_CLASS_KEYS
        or valid_predictions > 0
        or any(count > 0 for count in normalized_counts.values())
    )

    raw_status = str(payload.get("status") or "").strip().lower()
    if raw_status not in VESSEL_RESULT_STATUSES:
        # A legacy label by itself may be the former hard-coded LVO fallback.
        raw_status = "completed" if label and has_prediction_evidence else "unavailable"

    result = empty_vessel_occlusion_result(
        raw_status,
        total_slices=payload.get("total_slices") or 0,
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message") or payload.get("fallback_reason"),
        failures=payload.get("failures") if isinstance(payload.get("failures"), list) else [],
    )

    result["class_counts"] = normalized_counts
    result["valid_predictions"] = valid_predictions

    if result["status"] == "completed" and predicted_class in VESSEL_CLASS_KEYS:
        result["predicted_class"] = predicted_class

    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError):
        confidence = None
    if (
        result["status"] == "completed"
        and confidence is not None
        and 0.0 <= confidence <= 1.0
    ):
        result["confidence"] = confidence

    if result["status"] == "completed" and label and has_prediction_evidence:
        result["vessel_occlusion_class_result"] = label
    elif result["status"] == "completed":
        result["status"] = "failed"
        result["predicted_class"] = None
        result["confidence"] = None
        result["error_code"] = result["error_code"] or "MODEL_RESULT_INVALID"
        result["error_message"] = result["error_message"] or (
            "Model completed without a class label or successful prediction evidence"
        )

    if result["status"] != "completed":
        result["predicted_class"] = None
        result["confidence"] = None
        result["class_counts"] = {key: 0 for key in VESSEL_CLASS_KEYS}
        result["valid_predictions"] = 0

    return result


def vessel_result_from_sources(*sources: Any) -> Dict[str, Any]:
    """Return the first explicit vessel result, without inventing a class label."""
    for source in sources:
        if not isinstance(source, dict):
            continue
        candidate = source.get("vessel_occlusion_result")
        if isinstance(candidate, dict):
            return normalize_vessel_occlusion_result(candidate)
        if any(
            key in source
            for key in (
                "vessel_occlusion_class_result",
                "vessel_occlusion_status",
                "predicted_class",
            )
        ):
            enriched = dict(source)
            if "status" not in enriched and enriched.get("vessel_occlusion_status"):
                enriched["status"] = enriched.get("vessel_occlusion_status")
            return normalize_vessel_occlusion_result(enriched)
    return empty_vessel_occlusion_result()


def vessel_occlusion_context(result: Any = None) -> Dict[str, Any]:
    normalized = normalize_vessel_occlusion_result(result)
    return {
        "vessel_occlusion_result": normalized,
        "vessel_occlusion_status": normalized["status"],
        "vessel_occlusion_class_result": normalized["vessel_occlusion_class_result"],
        "vessel_occlusion_confidence": normalized["confidence"],
    }


def vessel_result_display_label(result: Any) -> str:
    normalized = normalize_vessel_occlusion_result(result)
    return normalized.get("vessel_occlusion_class_result") or VESSEL_OCCLUSION_UNAVAILABLE_TEXT
