from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence


EXPECTED_CLASS_NAMES = ("hemo", "infarct", "normal")
LABEL_CN = {
    "normal": "正常",
    "hemo": "脑出血",
    "infarct": "脑缺血",
}


def _safe_probability(value: Any, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid probability: {field_name}") from exc
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"Probability outside [0, 1]: {field_name}")
    return parsed


def _validated_class_names(class_names: Iterable[Any] | None) -> List[str]:
    names = [str(item or "").strip().lower() for item in (class_names or [])]
    if set(names) != set(EXPECTED_CLASS_NAMES) or len(names) != len(
        EXPECTED_CLASS_NAMES
    ):
        raise ValueError(
            "NCCT checkpoint classes must be exactly: hemo, infarct, normal"
        )
    return names


def predictions_from_probabilities(
    predictions: Sequence[Dict[str, Any]],
    class_names: Iterable[Any] | None = None,
) -> List[Dict[str, Any]]:
    """Return prediction rows whose labels are derived from real probabilities."""

    names = _validated_class_names(class_names or EXPECTED_CLASS_NAMES)
    normalized: List[Dict[str, Any]] = []
    for index, raw_row in enumerate(predictions or []):
        if not isinstance(raw_row, dict):
            raise ValueError(f"Invalid NCCT prediction row at index {index}")
        probabilities = {
            name: _safe_probability(
                raw_row.get(f"prob_{name}"), f"prob_{name}[{index}]"
            )
            for name in names
        }
        label = max(names, key=lambda name: probabilities[name])
        row = dict(raw_row)
        row["pred_label"] = label
        row["confidence"] = probabilities[label]
        for name, value in probabilities.items():
            row[f"prob_{name}"] = value
        normalized.append(row)
    if not normalized:
        raise ValueError("No valid NCCT predictions")
    return normalized


def unavailable_three_class_result(
    *,
    status: str = "failed",
    reason_code: str = "NCCT_CLASSIFICATION_UNAVAILABLE",
    reason: str = "NCCT 三分类没有产生有效结果",
) -> Dict[str, Any]:
    return {
        "status": status,
        "three_class_label": None,
        "three_class_label_cn": None,
        "three_class_confidence": None,
        "class_counts": {name: 0 for name in EXPECTED_CLASS_NAMES},
        "total_slices": 0,
        "aggregation_rule": "hemo_any_else_majority_infarct_tie_break",
        "safety_gate": {
            "blocked": True,
            "reason_code": reason_code,
            "reason": reason,
            "requires_clinician_review": True,
        },
    }


def aggregate_three_class_predictions(
    predictions: Sequence[Dict[str, Any]],
    class_names: Iterable[Any] | None = None,
) -> Dict[str, Any]:
    """Aggregate slice predictions into one conservative case-level result."""

    rows = predictions_from_probabilities(
        predictions, class_names or EXPECTED_CLASS_NAMES
    )
    counts = {name: 0 for name in EXPECTED_CLASS_NAMES}
    for row in rows:
        counts[row["pred_label"]] += 1

    if counts["hemo"] > 0:
        case_label = "hemo"
        relevant = [
            _safe_probability(row.get("prob_hemo"), "prob_hemo")
            for row in rows
            if row.get("pred_label") == "hemo"
        ]
        confidence = max(relevant)
    else:
        # Safety-conscious tie-break: infarct wins a tie with normal.
        case_label = max(
            ("infarct", "normal"),
            key=lambda name: (counts[name], 1 if name == "infarct" else 0),
        )
        relevant = [
            _safe_probability(row.get(f"prob_{case_label}"), f"prob_{case_label}")
            for row in rows
            if row.get("pred_label") == case_label
        ]
        confidence = sum(relevant) / len(relevant)

    blocked = case_label == "hemo"
    return {
        "status": "completed",
        "three_class_label": case_label,
        "three_class_label_cn": LABEL_CN[case_label],
        "three_class_confidence": round(float(confidence), 6),
        "class_counts": counts,
        "total_slices": len(rows),
        "aggregation_rule": "hemo_any_else_majority_infarct_tie_break",
        "safety_gate": {
            "blocked": blocked,
            "reason_code": "NCCT_SUSPECTED_HEMORRHAGE" if blocked else None,
            "reason": "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析"
            if blocked
            else None,
            "requires_clinician_review": blocked,
        },
    }
