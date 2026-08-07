"""Validation-only temperature scaling for binary logits."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar


def sigmoid(values: Any) -> np.ndarray:
    logits = np.asarray(values, dtype=np.float64)
    positive = logits >= 0
    result = np.empty_like(logits, dtype=np.float64)
    result[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exponential = np.exp(logits[~positive])
    result[~positive] = exponential / (1.0 + exponential)
    return result


def binary_log_loss_from_logits(logits: Any, labels: Any) -> float:
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    if z.shape != y.shape or z.size == 0:
        raise ValueError("logits and labels must have the same non-empty shape")
    return float(np.mean(np.logaddexp(0.0, z) - y * z))


def fit_temperature(logits: Any, labels: Any) -> float:
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    if z.shape != y.shape or z.size == 0:
        raise ValueError("Temperature scaling requires aligned validation logits and labels")
    if np.unique(y).tolist() != [0.0, 1.0]:
        raise ValueError("Temperature scaling validation labels must contain both classes")

    def objective(log_temperature: float) -> float:
        temperature = float(np.exp(log_temperature))
        return binary_log_loss_from_logits(z / temperature, y)

    result = minimize_scalar(
        objective,
        bounds=(float(np.log(0.05)), float(np.log(20.0))),
        method="bounded",
        options={"xatol": 1e-6, "maxiter": 500},
    )
    if not result.success or not np.isfinite(result.fun):
        raise RuntimeError(f"Temperature scaling failed: {result.message}")
    temperature = float(np.exp(result.x))
    if not np.isfinite(temperature) or temperature <= 0:
        raise RuntimeError(f"Temperature scaling returned invalid value {temperature}")
    return temperature


def calibrated_probability(logits: Any, temperature: float) -> np.ndarray:
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be positive and finite")
    return sigmoid(np.asarray(logits, dtype=np.float64) / float(temperature))
