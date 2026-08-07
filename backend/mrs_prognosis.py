"""StrokeClaw adapter for the two fixed 90-day mRS research MVP bundles."""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_BUNDLE = PROJECT_ROOT / "outputs" / "mrs_model" / "mrs_baseline_mvp.pt"
DEFAULT_UPDATE24H_BUNDLE = PROJECT_ROOT / "outputs" / "mrs_model" / "mrs_update24h_mvp.pt"

_MODEL_CACHE: dict[tuple[str, str], tuple[int, Any]] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _first(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return None


def _finite_number(value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _gender(value: Any) -> Any:
    token = str(value or "").strip().lower()
    if token in {"男", "m", "male", "1"}:
        return "M"
    if token in {"女", "f", "female", "0", "2"}:
        return "F"
    return value


def has_observed_nihss_24h(source: Mapping[str, Any]) -> bool:
    value = _first(
        source,
        (
            "NIHSS 24 HOURS",
            "nihss_24h",
            "nihss_24_hours",
            "nihss24",
            "nihss_24_hour",
            "followup_nihss_24h",
        ),
    )
    return _finite_number(value, minimum=0.0, maximum=42.0) is not None


def build_mrs_record(
    *,
    run: Mapping[str, Any],
    patient_data: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """Map real StrokeClaw fields to the immutable mRS V0.2 schema.

    Onset-to-admission is intentionally not reused as onset-to-CT.
    """

    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), Mapping) else {}
    explicit = planner_input.get("mrs_clinical_record")
    explicit = explicit if isinstance(explicit, Mapping) else {}
    patient = patient_data if isinstance(patient_data, Mapping) else {}
    combined = {**patient, **explicit}

    record = {
        "patient_key": str(
            _first(combined, ("patient_key", "clinical_patient_id"))
            or planner_input.get("patient_id")
            or run.get("patient_id")
            or ""
        ),
        "Gender": _gender(_first(combined, ("Gender", "patient_sex", "sex", "gender"))),
        "Age": _first(combined, ("Age", "patient_age", "age")),
        "NIHSS Baseline": _first(
            combined,
            ("NIHSS Baseline", "admission_nihss", "baseline_nihss", "nihss_baseline"),
        ),
        "NIHSS 24 HOURS": _first(
            combined,
            (
                "NIHSS 24 HOURS",
                "nihss_24h",
                "nihss_24_hours",
                "nihss24",
                "nihss_24_hour",
                "followup_nihss_24h",
            ),
        ),
    }
    onset_hours = _first(
        combined,
        ("onset_to_ct_hours", "onset_to_ct_time_hours", "onset_ct_hours"),
    )
    if onset_hours not in (None, ""):
        record["onset_to_ct_hours"] = onset_hours
    elif "Onset to CT time" in combined:
        record["Onset to CT time"] = combined.get("Onset to CT time")
    observed_24h = has_observed_nihss_24h(record)
    if not observed_24h:
        record["NIHSS 24 HOURS"] = None
    return record, observed_24h


def load_nifti_ncct_slices(path: str | Path) -> tuple[list[np.ndarray], list[str], list[str]]:
    """Decode one online NCCT NIfTI into axial 2-D slices without altering source data."""

    try:
        import nibabel as nib
    except Exception as exc:  # pragma: no cover - exercised in dependency failure tests
        raise RuntimeError(f"nibabel unavailable: {exc}") from exc

    source = Path(path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"NCCT NIfTI does not exist: {source}")
    image = nib.load(str(source))
    volume = np.asarray(image.dataobj, dtype=np.float32)
    volume = np.squeeze(volume)
    single_slice_input = volume.ndim == 2
    if single_slice_input:
        volume = volume[:, :, np.newaxis]
    if volume.ndim != 3:
        raise ValueError(f"NCCT NIfTI must resolve to 2-D or 3-D, got {volume.shape}")
    warnings: list[str] = [
        "online NCCT was decoded from NIfTI into axial slices; source geometry was not modified"
    ]
    if single_slice_input:
        warnings.append("single-slice 2-D NCCT was treated as one axial slice")
    arrays: list[np.ndarray] = []
    labels: list[str] = []
    for index in range(volume.shape[2]):
        slice_array = np.asarray(volume[:, :, index], dtype=np.float32)
        if not np.isfinite(slice_array).all():
            warnings.append(f"slice {index}: NaN/Inf rejected")
            continue
        lower = float(np.percentile(slice_array, 2))
        upper = float(np.percentile(slice_array, 98))
        if upper - lower < 1e-6:
            lower = float(slice_array.min())
            upper = float(slice_array.max())
        if upper - lower < 1e-6:
            normalized = np.zeros_like(slice_array, dtype=np.float32)
        else:
            normalized = np.clip(
                (slice_array - lower) / (upper - lower), 0.0, 1.0
            ).astype(np.float32)
        arrays.append(normalized)
        labels.append(f"{source.name}#slice_{index:03d}")
    if not arrays:
        raise ValueError("NCCT NIfTI contains no finite axial slices")
    warnings.append(
        "online NCCT used the training-compatible per-slice 2%-98% normalization"
    )
    return arrays, labels, warnings


def _load_model(path: str | Path, *, device: str = "auto"):
    from mrs_prediction.inference import MRSMVPEnsemble

    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"MVP bundle does not exist: {resolved}")
    mtime = resolved.stat().st_mtime_ns
    cache_key = (str(resolved), str(device))
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]
    model = MRSMVPEnsemble(resolved, device=device)
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[cache_key] = (mtime, model)
    return model


def _doctor_review(result: Mapping[str, Any], *, fallback_used: bool) -> dict[str, Any]:
    confidence = result.get("confidence") if isinstance(result.get("confidence"), Mapping) else {}
    prediction = result.get("prediction") if isinstance(result.get("prediction"), Mapping) else {}
    quality = result.get("data_quality") if isinstance(result.get("data_quality"), Mapping) else {}
    items = ["该结果为研究型MVP辅助风险分层，尚未完成外部验证，不替代医生综合判断。"]
    if confidence.get("level") == "low":
        items.append("模型置信度较低，不建议单独依据该结果进行风险分层。")
    try:
        if abs(float(prediction.get("poor_prognosis_risk")) - float(prediction.get("decision_threshold"))) < 0.05:
            items.append("结果接近决策阈值，请重点人工复核。")
    except Exception:
        pass
    missing = list(quality.get("missing_clinical_fields") or [])
    if missing:
        items.append("请补充或核对缺失临床字段：" + "、".join(str(item) for item in missing))
    if quality.get("image_quality_warnings"):
        items.append("存在影像质量或读取提示，请复核NCCT输入。")
    if fallback_used:
        items.append("24小时更新模型加载失败，本次已显式降级为首诊初步评估。")
    return {
        "review_level": "focused_review" if len(items) > 1 else "routine_review",
        "items": items,
    }


def _unavailable_result(
    *,
    run: Mapping[str, Any],
    requested_mode: str,
    error_code: str,
    message: str,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), Mapping) else {}
    return {
        "status": "unavailable",
        "patient_id": planner_input.get("patient_id") or run.get("patient_id"),
        "file_id": planner_input.get("file_id") or run.get("file_id"),
        "run_id": run.get("run_id") or run.get("id"),
        "result_mode": requested_mode,
        "display_mode": "24小时更新评估" if requested_mode == "update_24h" else "首诊初步评估",
        "error_code": error_code,
        "message": message,
        "prediction": None,
        "key_evidence": {"clinical": [], "imaging": []},
        "confidence": {"level": "unavailable", "ensemble_std": None, "reasons": [message]},
        "data_quality": {"missing_clinical_fields": [], "image_quality_warnings": []},
        "doctor_review_recommendation": {
            "review_level": "unavailable",
            "items": ["模型结果不可用，请勿使用启发式结果替代。"],
        },
        "model": {
            "model_version": None,
            "release_status": None,
            "external_validation_completed": False,
            "online_loading_permitted": False,
            "is_real_inference": False,
        },
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "input_provenance": {"nihss_24h_observed": requested_mode == "update_24h"},
    }


def _completed_result(
    *,
    run: Mapping[str, Any],
    inference: Mapping[str, Any],
    result_mode: str,
    observed_24h: bool,
    fallback_used: bool,
    fallback_reason: str | None,
    adapter_warnings: Sequence[str],
) -> dict[str, Any]:
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), Mapping) else {}
    prediction = dict(inference.get("prediction") or {})
    predicted_class = int(prediction.get("predicted_class"))
    prediction["class_name"] = (
        "mRS 3-6 / 不良预后" if predicted_class == 1 else "mRS 0-2 / 良好预后"
    )
    confidence = dict(inference.get("confidence") or {})
    confidence["ensemble_std"] = confidence.pop("ensemble_probability_std", None)
    quality = dict(inference.get("data_quality") or {})
    quality["image_quality_warnings"] = list(quality.get("image_quality_warnings") or []) + list(adapter_warnings)
    if adapter_warnings and confidence.get("level") == "high":
        confidence["level"] = "medium"
        confidence.setdefault("reasons", []).append("online NIfTI slice adapter used")
    bundle_model = inference.get("model") if isinstance(inference.get("model"), Mapping) else {}
    output = {
        "status": "completed",
        "patient_id": planner_input.get("patient_id") or run.get("patient_id"),
        "file_id": planner_input.get("file_id") or run.get("file_id"),
        "run_id": run.get("run_id") or run.get("id"),
        "result_mode": result_mode,
        "display_mode": "24小时更新评估" if result_mode == "update_24h" else "首诊初步评估",
        "prediction": prediction,
        "key_evidence": dict(inference.get("key_evidence") or {"clinical": [], "imaging": []}),
        "confidence": confidence,
        "data_quality": quality,
        "model": {
            "model_version": bundle_model.get("version"),
            "bundle_version": bundle_model.get("bundle_version"),
            "release_status": bundle_model.get("release_status"),
            "external_validation_completed": False,
            "online_loading_permitted": True,
            "is_real_inference": bundle_model.get("is_real_inference") is True,
            "production_approved": False,
        },
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "input_provenance": {
            "nihss_24h_observed": bool(observed_24h),
            "requested_mode": "update_24h" if observed_24h else "baseline",
        },
    }
    output["doctor_review_recommendation"] = _doctor_review(output, fallback_used=fallback_used)
    return output


def run_mrs_prognosis_prediction(
    *,
    run: Mapping[str, Any],
    patient_data: Mapping[str, Any] | None,
    ncct_path: str | Path | None = None,
    baseline_bundle: str | Path = DEFAULT_BASELINE_BUNDLE,
    update24h_bundle: str | Path = DEFAULT_UPDATE24H_BUNDLE,
    device: str | None = None,
) -> dict[str, Any]:
    """Route and execute one real mRS MVP inference for the current case."""

    record, observed_24h = build_mrs_record(run=run, patient_data=patient_data)
    requested_mode = "update_24h" if observed_24h else "baseline"
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), Mapping) else {}
    selected_device = device or os.getenv("MRS_INFERENCE_DEVICE", "auto")
    image_files = planner_input.get("mrs_image_files")
    image_files = list(image_files) if isinstance(image_files, (list, tuple)) else None
    image_root = planner_input.get("mrs_image_root")
    arrays = None
    labels = None
    adapter_warnings: list[str] = []

    fallback_used = False
    fallback_reason = None
    mode = requested_mode
    bundle_path = update24h_bundle if mode == "update_24h" else baseline_bundle
    try:
        model = _load_model(bundle_path, device=selected_device)
    except Exception as exc:
        if requested_mode != "update_24h":
            return _unavailable_result(
                run=run,
                requested_mode=requested_mode,
                error_code="MRS_BUNDLE_LOAD_FAILED",
                message=str(exc),
            )
        fallback_used = True
        fallback_reason = str(exc)
        mode = "baseline"
        try:
            model = _load_model(baseline_bundle, device=selected_device)
        except Exception as baseline_exc:
            return _unavailable_result(
                run=run,
                requested_mode=requested_mode,
                error_code="MRS_FALLBACK_BUNDLE_LOAD_FAILED",
                message=str(baseline_exc),
                fallback_used=True,
                fallback_reason=fallback_reason,
            )

    if mode == "update_24h" and image_files is None:
        if not ncct_path:
            return _unavailable_result(
                run=run,
                requested_mode=requested_mode,
                error_code="MRS_NCCT_INPUT_MISSING",
                message="update_24h模型需要当前病例NCCT输入",
            )
        try:
            arrays, labels, adapter_warnings = load_nifti_ncct_slices(ncct_path)
        except Exception as exc:
            return _unavailable_result(
                run=run,
                requested_mode=requested_mode,
                error_code="MRS_NCCT_PREPROCESSING_FAILED",
                message=str(exc),
            )

    inference = model.predict(
        record,
        image_root=image_root,
        image_files=image_files if mode == "update_24h" else None,
        image_arrays=arrays if mode == "update_24h" else None,
        image_source_files=labels if mode == "update_24h" else None,
    )
    if inference.get("status") != "success":
        return _unavailable_result(
            run=run,
            requested_mode=mode,
            error_code=str(inference.get("error_code") or "MRS_INFERENCE_FAILED"),
            message=str(inference.get("message") or "mRS模型推理失败"),
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
    return _completed_result(
        run=run,
        inference=inference,
        result_mode=mode,
        observed_24h=observed_24h,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        adapter_warnings=adapter_warnings,
    )
