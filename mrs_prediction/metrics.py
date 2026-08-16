"""Binary prognosis metrics and curve data without test-set tuning."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import rankdata


def _arrays(labels: Any, probabilities: Any) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(labels, dtype=np.int64).reshape(-1)
    p = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    if y.size == 0 or y.shape != p.shape:
        raise ValueError("labels and probabilities must be non-empty one-dimensional arrays")
    if set(y.tolist()) - {0, 1}:
        raise ValueError("labels must contain only 0 and 1")
    if not np.isfinite(p).all():
        raise ValueError("probabilities contain NaN or Inf")
    return y, np.clip(p, 0.0, 1.0)


def require_both_classes(labels: Any, context: str) -> None:
    unique = np.unique(np.asarray(labels, dtype=np.int64))
    if unique.tolist() != [0, 1]:
        raise ValueError(f"{context} must contain both classes; got {unique.tolist()}")


def roc_auc(labels: Any, probabilities: Any) -> float:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "ROC-AUC labels")
    positive = y == 1
    n_pos = int(positive.sum())
    n_neg = int((~positive).sum())
    ranks = rankdata(p, method="average")
    auc = (float(ranks[positive].sum()) - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def average_precision(labels: Any, probabilities: Any) -> float:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "PR-AUC labels")
    order = np.argsort(-p, kind="mergesort")
    sorted_y = y[order]
    true_positives = np.cumsum(sorted_y == 1)
    ranks = np.arange(1, len(y) + 1)
    precision = true_positives / ranks
    return float(precision[sorted_y == 1].mean())


def expected_calibration_error(labels: Any, probabilities: Any, bins: int = 10) -> float:
    y, p = _arrays(labels, probabilities)
    if bins < 2:
        raise ValueError("ECE requires at least two bins")
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for index in range(bins):
        if index == bins - 1:
            selected = (p >= edges[index]) & (p <= edges[index + 1])
        else:
            selected = (p >= edges[index]) & (p < edges[index + 1])
        if selected.any():
            result += float(selected.mean()) * abs(float(p[selected].mean()) - float(y[selected].mean()))
    return float(result)


def calibration_curve(labels: Any, probabilities: Any, bins: int = 10) -> dict[str, list[float]]:
    y, p = _arrays(labels, probabilities)
    edges = np.linspace(0.0, 1.0, bins + 1)
    predicted: list[float] = []
    observed: list[float] = []
    counts: list[int] = []
    for index in range(bins):
        selected = (p >= edges[index]) & (
            p <= edges[index + 1] if index == bins - 1 else p < edges[index + 1]
        )
        if selected.any():
            predicted.append(float(p[selected].mean()))
            observed.append(float(y[selected].mean()))
            counts.append(int(selected.sum()))
    return {"mean_predicted": predicted, "fraction_positive": observed, "counts": counts}


def select_youden_threshold(labels: Any, probabilities: Any) -> float:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "Youden validation labels")
    candidates = np.unique(np.concatenate(([0.0], p, [1.0])))
    best: tuple[float, float, float] | None = None
    best_threshold = 0.5
    for threshold in candidates:
        predicted = p >= threshold
        tp = int(((y == 1) & predicted).sum())
        tn = int(((y == 0) & ~predicted).sum())
        sensitivity = tp / int((y == 1).sum())
        specificity = tn / int((y == 0).sum())
        score = sensitivity + specificity - 1.0
        tie_key = (score, -abs(float(threshold) - 0.5), float(threshold))
        if best is None or tie_key > best:
            best = tie_key
            best_threshold = float(threshold)
    return best_threshold


def binary_metrics(
    labels: Any,
    probabilities: Any,
    *,
    threshold: float,
    ece_bins: int = 10,
) -> dict[str, Any]:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "Evaluation labels")
    predicted = (p >= float(threshold)).astype(np.int64)
    tp = int(((y == 1) & (predicted == 1)).sum())
    tn = int(((y == 0) & (predicted == 0)).sum())
    fp = int(((y == 0) & (predicted == 1)).sum())
    fn = int(((y == 1) & (predicted == 0)).sum())
    divide = lambda numerator, denominator: float(numerator / denominator) if denominator else 0.0
    sensitivity = divide(tp, tp + fn)
    specificity = divide(tn, tn + fp)
    precision = divide(tp, tp + fp)
    npv = divide(tn, tn + fn)
    return {
        "patient_count": int(len(y)),
        "label_0": int((y == 0).sum()),
        "label_1": int((y == 1).sum()),
        "roc_auc": roc_auc(y, p),
        "pr_auc": average_precision(y, p),
        "accuracy": float((predicted == y).mean()),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "recall": sensitivity,
        "f1": divide(2 * precision * sensitivity, precision + sensitivity),
        "ppv": precision,
        "npv": npv,
        "brier_score": float(np.mean((p - y) ** 2)),
        "expected_calibration_error": expected_calibration_error(y, p, bins=ece_bins),
        "threshold": float(threshold),
        "confusion_matrix": [[tn, fp], [fn, tp]],
    }


def roc_curve_points(labels: Any, probabilities: Any) -> dict[str, list[float]]:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "ROC curve labels")
    thresholds = np.concatenate(([np.inf], np.unique(p)[::-1], [-np.inf]))
    fpr: list[float] = []
    tpr: list[float] = []
    for threshold in thresholds:
        predicted = p >= threshold
        tpr.append(float(((y == 1) & predicted).sum() / (y == 1).sum()))
        fpr.append(float(((y == 0) & predicted).sum() / (y == 0).sum()))
    return {"fpr": fpr, "tpr": tpr}


def pr_curve_points(labels: Any, probabilities: Any) -> dict[str, list[float]]:
    y, p = _arrays(labels, probabilities)
    require_both_classes(y, "PR curve labels")
    order = np.argsort(-p, kind="mergesort")
    sorted_y = y[order]
    tp = np.cumsum(sorted_y == 1)
    fp = np.cumsum(sorted_y == 0)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / int((y == 1).sum())
    return {
        "precision": [1.0, *precision.astype(float).tolist()],
        "recall": [0.0, *recall.astype(float).tolist()],
    }
