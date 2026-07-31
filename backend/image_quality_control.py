"""Rule-based NIfTI image quality control for the StrokeClaw runtime.

The checks in this module are engineering safeguards.  In particular, motion
and missing-slice findings are heuristic warnings and are not diagnoses.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import numpy as np

try:
    import nibabel as nib
    from nibabel.affines import voxel_sizes
except Exception:  # pragma: no cover - exercised through the unavailable contract
    nib = None
    voxel_sizes = None


JsonDict = Dict[str, Any]
CTA_MODALITIES = ("mcta", "vcta", "dcta")
PERFUSION_MODALITIES = ("cbf", "cbv", "tmax")
KNOWN_MODALITIES = ("ncct",) + CTA_MODALITIES + PERFUSION_MODALITIES
SEVERITY_PENALTY = {"critical": 0.40, "high": 0.20, "medium": 0.08}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    fallback = "1" if default else "0"
    return str(os.getenv(name, fallback)).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


@dataclass(frozen=True)
class ImageQualityConfig:
    enabled: bool = True
    allow_single_slice: bool = True
    max_slice_thickness_mm: float = 5.0
    min_coverage_mm: float = 120.0
    min_valid_slices: int = 10
    min_finite_ratio: float = 0.999
    motion_warn_bad_pair_ratio: float = 0.10
    motion_fail_bad_pair_ratio: float = 0.25
    motion_max_shift_mm: float = 3.0
    motion_min_correlation: float = 0.60
    geometry_spacing_rtol: float = 0.01
    geometry_spacing_atol_mm: float = 0.01
    geometry_orientation_tolerance_deg: float = 1.0
    geometry_affine_atol_mm: float = 1.0

    @classmethod
    def from_env(cls) -> "ImageQualityConfig":
        return cls(
            enabled=_env_bool("IMAGE_QC_ENABLED", True),
            allow_single_slice=_env_bool("IMAGE_QC_ALLOW_SINGLE_SLICE", True),
            max_slice_thickness_mm=_env_float(
                "IMAGE_QC_MAX_SLICE_THICKNESS_MM", 5.0
            ),
            min_coverage_mm=_env_float("IMAGE_QC_MIN_COVERAGE_MM", 120.0),
            min_valid_slices=_env_int("IMAGE_QC_MIN_VALID_SLICES", 10),
            min_finite_ratio=_env_float("IMAGE_QC_MIN_FINITE_RATIO", 0.999),
            motion_warn_bad_pair_ratio=_env_float(
                "IMAGE_QC_MOTION_WARN_BAD_PAIR_RATIO", 0.10
            ),
            motion_fail_bad_pair_ratio=_env_float(
                "IMAGE_QC_MOTION_FAIL_BAD_PAIR_RATIO", 0.25
            ),
            motion_max_shift_mm=_env_float(
                "IMAGE_QC_MOTION_MAX_SHIFT_MM", 3.0
            ),
            motion_min_correlation=_env_float(
                "IMAGE_QC_MOTION_MIN_CORRELATION", 0.60
            ),
            geometry_affine_atol_mm=_env_float(
                "IMAGE_QC_GEOMETRY_AFFINE_ATOL_MM", 1.0
            ),
        )


def _normalize_modalities(values: Iterable[object] | None) -> list[str]:
    aliases = {"mcat": "mcta", "vcat": "vcta", "dcat": "dcta"}
    result: list[str] = []
    for value in values or []:
        token = str(value or "").strip().lower()
        token = aliases.get(token, token)
        if token in KNOWN_MODALITIES and token not in result:
            result.append(token)
    return result


def _normalize_paths(paths: Mapping[str, Any] | None) -> Dict[str, str]:
    field_aliases = {
        "ncct_file": "ncct",
        "mcta_file": "mcta",
        "vcta_file": "vcta",
        "dcta_file": "dcta",
        "cbf_file": "cbf",
        "cbv_file": "cbv",
        "tmax_file": "tmax",
    }
    normalized: Dict[str, str] = {}
    for raw_key, raw_value in (paths or {}).items():
        key = field_aliases.get(str(raw_key).strip().lower(), str(raw_key).strip().lower())
        if key not in KNOWN_MODALITIES:
            continue
        if isinstance(raw_value, dict):
            value = raw_value.get("path")
        else:
            value = raw_value
        path = str(value or "").strip()
        if path:
            normalized[key] = path
    return normalized


def required_modalities(imaging_path: str, available_modalities: Iterable[object]) -> list[str]:
    path = str(imaging_path or "").strip().lower()
    available = _normalize_modalities(available_modalities)
    if path == "ncct_only":
        return ["ncct"]
    if path == "ncct_single_phase_cta":
        selected = next((item for item in CTA_MODALITIES if item in available), None)
        return ["ncct"] + ([selected] if selected else [])
    if path == "ncct_mcta":
        return ["ncct", *CTA_MODALITIES]
    if path == "ncct_mcta_ctp":
        return ["ncct", *CTA_MODALITIES, *PERFUSION_MODALITIES]
    return ["ncct"]


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    modality: Optional[str] = None,
    metric: Any = None,
    threshold: Any = None,
    overrideable: bool = True,
) -> JsonDict:
    return {
        "code": code,
        "severity": severity,
        "modality": modality,
        "metric": metric,
        "threshold": threshold,
        "message": message,
        "overrideable": bool(overrideable),
    }


def _as_3d(img: Any) -> Tuple[Optional[np.ndarray], Optional[str]]:
    try:
        data = np.asanyarray(img.dataobj)
    except Exception as exc:
        return None, type(exc).__name__
    if data.ndim == 4 and data.shape[3] > 0:
        data = data[..., 0]
    elif data.ndim == 2:
        data = data[:, :, np.newaxis]
    if data.ndim != 3:
        return None, f"unsupported_ndim_{data.ndim}"
    return np.asarray(data), None


def _orientation_matrix(affine: np.ndarray) -> np.ndarray:
    axes = np.asarray(affine, dtype=float)[:3, :3]
    lengths = np.linalg.norm(axes, axis=0)
    lengths[lengths == 0] = 1.0
    return axes / lengths


def _orientation_delta_degrees(a: np.ndarray, b: np.ndarray) -> float:
    oa = _orientation_matrix(a)
    ob = _orientation_matrix(b)
    dots = np.clip(np.abs(np.sum(oa * ob, axis=0)), -1.0, 1.0)
    return float(np.max(np.degrees(np.arccos(dots))))


def _downsample_2d(data: np.ndarray, max_size: int = 128) -> np.ndarray:
    sx = max(1, int(math.ceil(data.shape[0] / max_size)))
    sy = max(1, int(math.ceil(data.shape[1] / max_size)))
    return np.asarray(data[::sx, ::sy], dtype=np.float32)


def _normalized_slice(data: np.ndarray, low: float, high: float) -> np.ndarray:
    sampled = _downsample_2d(data)
    sampled = np.nan_to_num(sampled, nan=low, posinf=high, neginf=low)
    sampled = np.clip(sampled, low, high)
    scale = max(high - low, 1e-6)
    return (sampled - low) / scale


def _phase_shift_and_correlation(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
    fa = np.fft.fft2(a - float(np.mean(a)))
    fb = np.fft.fft2(b - float(np.mean(b)))
    cross = fa * np.conj(fb)
    magnitude = np.abs(cross)
    cross = cross / np.where(magnitude > 1e-8, magnitude, 1.0)
    corr_surface = np.abs(np.fft.ifft2(cross))
    peak = np.unravel_index(int(np.argmax(corr_surface)), corr_surface.shape)
    shift = np.asarray(peak, dtype=float)
    for idx, size in enumerate(corr_surface.shape):
        if shift[idx] > size / 2:
            shift[idx] -= size
    aligned = np.roll(b, tuple(int(round(value)) for value in shift), axis=(0, 1))
    avec = (a - float(np.mean(a))).ravel()
    bvec = (aligned - float(np.mean(aligned))).ravel()
    denom = float(np.linalg.norm(avec) * np.linalg.norm(bvec))
    correlation = float(np.dot(avec, bvec) / denom) if denom > 1e-8 else 1.0
    return float(shift[0]), float(shift[1]), correlation


def _slice_quality(data: np.ndarray) -> JsonDict:
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return {"occupied": [], "interior_blank_indices": [], "range": 0.0}
    low, high = np.percentile(finite, [1.0, 99.0])
    dynamic = float(high - low)
    occupied: list[bool] = []
    for index in range(data.shape[2]):
        plane = np.asarray(data[:, :, index])
        valid = plane[np.isfinite(plane)]
        if valid.size == 0:
            occupied.append(False)
            continue
        plane_std = float(np.std(valid))
        foreground = float(np.mean(valid > (low + 0.05 * max(dynamic, 1e-6))))
        occupied.append(plane_std > max(1e-6, dynamic * 0.005) and foreground >= 0.005)
    indices = [idx for idx, value in enumerate(occupied) if value]
    interior: list[int] = []
    if indices:
        interior = [idx for idx in range(indices[0], indices[-1] + 1) if not occupied[idx]]
    jump_pairs: list[list[int]] = []
    if len(indices) >= 3 and dynamic > 1e-6:
        distances: list[float] = []
        pairs: list[tuple[int, int]] = []
        previous_index = None
        previous_plane = None
        for index in indices:
            plane = _normalized_slice(data[:, :, index], float(low), float(high))
            if previous_plane is not None and previous_index is not None and index == previous_index + 1:
                distances.append(float(np.mean(np.abs(plane - previous_plane))))
                pairs.append((previous_index, index))
            previous_index = index
            previous_plane = plane
        if distances:
            median = float(np.median(distances))
            mad = float(np.median(np.abs(np.asarray(distances) - median)))
            threshold = max(0.20, median + 6.0 * max(mad, 1e-6))
            jump_pairs = [
                [int(pair[0]), int(pair[1])]
                for pair, distance in zip(pairs, distances)
                if distance > threshold
            ]
    return {
        "occupied": occupied,
        "interior_blank_indices": interior,
        "abnormal_jump_pairs": jump_pairs,
        "range": round(dynamic, 6),
        "percentile_low": round(float(low), 6),
        "percentile_high": round(float(high), 6),
    }


def _motion_check(
    data: np.ndarray,
    zooms: Tuple[float, float, float],
    config: ImageQualityConfig,
) -> JsonDict:
    quality = _slice_quality(data)
    valid_indices = [idx for idx, value in enumerate(quality["occupied"]) if value]
    if len(valid_indices) < 5:
        return {
            "level": "unknown",
            "bad_pair_ratio": None,
            "bad_pairs": 0,
            "evaluated_pairs": 0,
        }
    trim = max(1, int(len(valid_indices) * 0.10))
    central = valid_indices[trim:-trim] if len(valid_indices) > trim * 2 + 2 else valid_indices
    low = float(quality["percentile_low"])
    high = float(quality["percentile_high"])
    bad_pairs = 0
    evaluated = 0
    max_shift = 0.0
    min_corr = 1.0
    previous = None
    previous_index = None
    for index in central:
        current = _normalized_slice(data[:, :, index], low, high)
        if previous is not None and previous_index is not None and index == previous_index + 1:
            shift_x, shift_y, correlation = _phase_shift_and_correlation(previous, current)
            scale_x = data.shape[0] / current.shape[0]
            scale_y = data.shape[1] / current.shape[1]
            shift_mm = math.sqrt(
                (shift_x * scale_x * zooms[0]) ** 2
                + (shift_y * scale_y * zooms[1]) ** 2
            )
            max_shift = max(max_shift, float(shift_mm))
            min_corr = min(min_corr, float(correlation))
            if shift_mm > config.motion_max_shift_mm or correlation < config.motion_min_correlation:
                bad_pairs += 1
            evaluated += 1
        previous = current
        previous_index = index
    if evaluated == 0:
        level = "unknown"
        ratio = None
    else:
        ratio = bad_pairs / evaluated
        if ratio >= config.motion_fail_bad_pair_ratio:
            level = "severe"
        elif ratio >= config.motion_warn_bad_pair_ratio:
            level = "moderate"
        elif bad_pairs:
            level = "mild"
        else:
            level = "none"
    return {
        "level": level,
        "bad_pair_ratio": round(ratio, 6) if ratio is not None else None,
        "bad_pairs": bad_pairs,
        "evaluated_pairs": evaluated,
        "max_shift_mm": round(max_shift, 4),
        "min_correlation": round(min_corr, 6) if evaluated else None,
    }


def _geometry_check(
    loaded: Mapping[str, JsonDict],
    group: Iterable[str],
    config: ImageQualityConfig,
    findings: list[JsonDict],
    *,
    in_plane_only: bool = False,
) -> JsonDict:
    present = [item for item in group if item in loaded]
    if len(present) < 2:
        return {"status": "unknown", "modalities": present, "comparisons": []}
    reference_name = present[0]
    reference = loaded[reference_name]
    comparisons = []
    status = "matched"
    for name in present[1:]:
        candidate = loaded[name]
        compared_axes = slice(0, 2) if in_plane_only else slice(0, 3)
        shape_match = tuple(reference["shape"][compared_axes]) == tuple(
            candidate["shape"][compared_axes]
        )
        spacing_match = bool(
            np.allclose(
                reference["zooms"][compared_axes],
                candidate["zooms"][compared_axes],
                rtol=config.geometry_spacing_rtol,
                atol=config.geometry_spacing_atol_mm,
            )
        )
        reference_orientation = _orientation_matrix(reference["affine"])
        candidate_orientation = _orientation_matrix(candidate["affine"])
        axis_count = 2 if in_plane_only else 3
        dots = np.clip(
            np.abs(
                np.sum(
                    reference_orientation[:, :axis_count]
                    * candidate_orientation[:, :axis_count],
                    axis=0,
                )
            ),
            -1.0,
            1.0,
        )
        angle = float(np.max(np.degrees(np.arccos(dots))))
        orientation_match = angle <= config.geometry_orientation_tolerance_deg
        affine_match = (
            None
            if in_plane_only
            else bool(
                np.allclose(
                    reference["affine"],
                    candidate["affine"],
                    rtol=0.001,
                    atol=config.geometry_affine_atol_mm,
                )
            )
        )
        comparison = {
            "reference": reference_name,
            "modality": name,
            "shape_match": shape_match,
            "spacing_match": spacing_match,
            "orientation_delta_deg": round(angle, 6),
            "orientation_match": orientation_match,
            "affine_match": affine_match,
            "comparison_mode": "in_plane" if in_plane_only else "volume",
        }
        comparisons.append(comparison)
        geometry_matches = shape_match and spacing_match and orientation_match
        if not in_plane_only:
            geometry_matches = geometry_matches and bool(affine_match)
        if not geometry_matches:
            status = "mismatched"
            findings.append(
                _finding(
                    "required_geometry_mismatch",
                    "critical",
                    f"{name} 与 {reference_name} 的必需空间几何不一致",
                    modality=name,
                    metric=comparison,
                    threshold={
                        "spacing_rtol": config.geometry_spacing_rtol,
                        "orientation_deg": config.geometry_orientation_tolerance_deg,
                        "affine_atol_mm": config.geometry_affine_atol_mm,
                    },
                    overrideable=False,
                )
            )
    return {"status": status, "modalities": present, "comparisons": comparisons}


def _fingerprint(result: JsonDict) -> str:
    payload = {key: value for key, value in result.items() if key not in {"qc_fingerprint", "review_override"}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_image_quality_control(
    nifti_paths: Mapping[str, Any] | None,
    available_modalities: Iterable[object] | None,
    imaging_path: str,
    *,
    config: Optional[ImageQualityConfig] = None,
) -> JsonDict:
    config = config or ImageQualityConfig.from_env()
    modalities = _normalize_modalities(available_modalities)
    paths = _normalize_paths(nifti_paths)
    required = required_modalities(imaging_path, modalities)
    findings: list[JsonDict] = []
    checks: JsonDict = {"files": {}, "coverage": {}, "motion": {}, "geometry": {}}
    loaded: Dict[str, JsonDict] = {}

    if not config.enabled:
        result = {
            "schema_version": "1.0",
            "qc_status": "warning",
            "qc_score": 0.92,
            "qc_method": "rule_based_nifti_qc_disabled",
            "qc_input_mode": None,
            "qc_not_applicable_checks": [],
            "qc_file_readable": None,
            "qc_modality_complete": all(item in modalities for item in required),
            "qc_scan_coverage": "unknown",
            "qc_slice_thickness_status": "unknown",
            "qc_motion_artifact_level": "unknown",
            "qc_missing_slice_status": "unknown",
            "qc_geometry_status": "unknown",
            "qc_warning_message": "image_quality_control_disabled",
            "qc_affected_nodes": [],
            "qc_blocking_required": False,
            "qc_review_required": False,
            "qc_review_reason": "",
            "findings": [_finding("qc_disabled", "medium", "图像质控已由配置禁用")],
            "checks": checks,
            "limitations": ["质控已禁用，不能证明影像质量合格"],
            "review_override": None,
            "available_modalities": modalities,
            "required_modalities": required,
        }
        result["qc_fingerprint"] = _fingerprint(result)
        return result

    for modality in required:
        if modality not in modalities or modality not in paths:
            findings.append(
                _finding(
                    "required_modality_missing",
                    "critical",
                    f"缺少必需模态 {modality}",
                    modality=modality,
                    overrideable=False,
                )
            )

    if str(imaging_path or "").strip().lower() == "ncct_single_phase_cta" and len(required) == 1:
        findings.append(
            _finding(
                "single_phase_cta_missing",
                "critical",
                "单期 CTA 路径没有可用 CTA 文件",
                overrideable=False,
            )
        )

    if nib is None or voxel_sizes is None:
        findings.append(
            _finding(
                "nibabel_unavailable",
                "critical",
                "NiBabel 不可用，无法执行 NIfTI 质控",
                overrideable=False,
            )
        )
    else:
        for modality, path in paths.items():
            file_check: JsonDict = {"present": True, "readable": False}
            checks["files"][modality] = file_check
            if not os.path.isfile(path):
                findings.append(
                    _finding(
                        "file_not_found",
                        "critical",
                        f"{modality} 文件不存在",
                        modality=modality,
                        overrideable=False,
                    )
                )
                continue
            if not path.lower().endswith((".nii", ".nii.gz")):
                findings.append(
                    _finding(
                        "unsupported_file_type",
                        "critical",
                        f"{modality} 不是受支持的 NIfTI 文件",
                        modality=modality,
                        overrideable=False,
                    )
                )
                continue
            try:
                img = nib.load(path)
                data, data_error = _as_3d(img)
                if data is None:
                    findings.append(
                        _finding(
                            "unsupported_dimension",
                            "critical",
                            f"{modality} NIfTI 维度非法（{data_error or 'invalid_data'}）",
                            modality=modality,
                            overrideable=False,
                        )
                    )
                    continue
            except Exception as exc:
                findings.append(
                    _finding(
                        "nifti_unreadable",
                        "critical",
                        f"{modality} NIfTI 无法读取（{type(exc).__name__}）",
                        modality=modality,
                        overrideable=False,
                    )
                )
                continue

            finite_ratio = float(np.mean(np.isfinite(data))) if data.size else 0.0
            finite = data[np.isfinite(data)]
            dynamic_range = float(np.ptp(finite)) if finite.size else 0.0
            spatial_units = str((img.header.get_xyzt_units() or (None,))[0] or "unknown")
            affine = np.asarray(img.affine, dtype=float)
            affine_trustworthy = bool(
                np.all(np.isfinite(affine))
                and abs(float(np.linalg.det(affine[:3, :3]))) > 1e-8
            )
            zoom = tuple(float(value) for value in voxel_sizes(affine)[:3])
            file_check.update(
                {
                    "readable": True,
                    "shape": [int(value) for value in data.shape],
                    "finite_ratio": round(finite_ratio, 6),
                    "dynamic_range": round(dynamic_range, 6),
                    "spatial_units": spatial_units,
                    "voxel_sizes": [round(value, 6) for value in zoom],
                    "affine_trustworthy": affine_trustworthy,
                }
            )
            loaded[modality] = {
                "img": img,
                "data": data,
                "shape": tuple(data.shape),
                "affine": affine,
                "zooms": zoom,
                "units": spatial_units,
            }
            if 1 < data.shape[2] < config.min_valid_slices:
                findings.append(
                    _finding(
                        "too_few_slices",
                        "critical",
                        f"{modality} 有效层数不足",
                        modality=modality,
                        metric=int(data.shape[2]),
                        threshold=config.min_valid_slices,
                        overrideable=False,
                    )
                )
            if not affine_trustworthy:
                findings.append(
                    _finding(
                        "affine_untrustworthy",
                        "critical",
                        f"{modality} affine 不可信，无法安全解释空间几何",
                        modality=modality,
                        overrideable=False,
                    )
                )
            if finite_ratio < config.min_finite_ratio:
                findings.append(
                    _finding(
                        "non_finite_voxels",
                        "critical",
                        f"{modality} 包含过多 NaN/Inf",
                        modality=modality,
                        metric=round(finite_ratio, 6),
                        threshold=config.min_finite_ratio,
                        overrideable=False,
                    )
                )
            if dynamic_range <= 1e-6:
                findings.append(
                    _finding(
                        "empty_or_constant_volume",
                        "critical",
                        f"{modality} 体数据为空或近似常量",
                        modality=modality,
                        metric=round(dynamic_range, 6),
                        overrideable=False,
                    )
                )

    required_loaded = {item: loaded[item] for item in required if item in loaded}
    required_depths = {
        item: int(value["shape"][2]) for item, value in required_loaded.items()
    }
    input_mode = "invalid_mixed"
    not_applicable_checks: list[str] = []
    if required and len(required_loaded) == len(required):
        depths = list(required_depths.values())
        if config.allow_single_slice and all(value == 1 for value in depths):
            input_mode = "single_slice"
            not_applicable_checks = [
                "axial_coverage",
                "internal_missing_slices",
                "inter_slice_motion",
            ]
            findings.append(
                _finding(
                    "single_slice_limited_assessment",
                    "medium",
                    "单层影像无法执行三维覆盖、疑似缺片及跨层运动评估",
                    metric=required_depths,
                )
            )
        elif all(value >= config.min_valid_slices for value in depths):
            input_mode = "volume"
        else:
            findings.append(
                _finding(
                    "invalid_slice_stack_configuration",
                    "critical",
                    "必需模态存在单层/多层混合或疑似截断体数据",
                    metric=required_depths,
                    threshold={
                        "single_slice": 1 if config.allow_single_slice else None,
                        "minimum_volume_slices": config.min_valid_slices,
                    },
                    overrideable=False,
                )
            )
    checks["input_mode"] = {
        "mode": input_mode,
        "required_depths": required_depths,
        "allow_single_slice": config.allow_single_slice,
        "minimum_volume_slices": config.min_valid_slices,
    }

    ncct = loaded.get("ncct")
    slice_thickness_status = "unknown"
    coverage_status = "unknown"
    missing_slice_status = "unknown"
    if ncct:
        z_spacing = float(ncct["zooms"][2])
        coverage_mm = float(ncct["shape"][2] * z_spacing)
        quality = _slice_quality(ncct["data"])
        blanks = list(quality["interior_blank_indices"])
        jump_pairs = list(quality.get("abnormal_jump_pairs") or [])
        checks["coverage"] = {
            "slice_thickness": round(z_spacing, 6),
            "coverage_mm": round(coverage_mm, 4),
            "num_slices": int(ncct["shape"][2]),
            "spatial_units": ncct["units"],
            "interior_blank_indices": blanks,
            "abnormal_jump_pairs": jump_pairs,
        }
        if ncct["units"] != "mm":
            findings.append(
                _finding(
                    "spatial_units_unknown",
                    "medium",
                    "NCCT 空间单位不是明确的 mm，层厚和覆盖无法可靠判定",
                    modality="ncct",
                    metric=ncct["units"],
                )
            )
        else:
            slice_thickness_status = "normal" if z_spacing <= config.max_slice_thickness_mm else "abnormal"
            if input_mode == "volume":
                coverage_status = "complete" if coverage_mm >= config.min_coverage_mm else "incomplete"
            if slice_thickness_status == "abnormal":
                findings.append(
                    _finding(
                        "slice_thickness_abnormal",
                        "high",
                        "NCCT 重建层厚超过配置上限",
                        modality="ncct",
                        metric=round(z_spacing, 6),
                        threshold=config.max_slice_thickness_mm,
                    )
                )
            if input_mode == "volume" and coverage_status == "incomplete":
                findings.append(
                    _finding(
                        "scan_coverage_incomplete",
                        "high",
                        "NCCT 轴向覆盖范围不足",
                        modality="ncct",
                        metric=round(coverage_mm, 4),
                        threshold=config.min_coverage_mm,
                    )
                )
        suspicious_missing_count = len(blanks) + len(jump_pairs)
        if suspicious_missing_count >= 2:
            missing_slice_status = "suspected_multiple"
            findings.append(
                _finding(
                    "suspected_missing_slices",
                    "high",
                    "NCCT 体数据内部存在多个近空白切片或异常跳变，疑似图像缺失",
                    modality="ncct",
                    metric={"blank_slices": blanks, "abnormal_jump_pairs": jump_pairs},
                    threshold=2,
                )
            )
        elif suspicious_missing_count == 1:
            missing_slice_status = "suspected_single"
            findings.append(
                _finding(
                    "suspected_missing_slice",
                    "medium",
                    "NCCT 体数据内部存在一个近空白切片或异常跳变",
                    modality="ncct",
                    metric={"blank_slices": blanks, "abnormal_jump_pairs": jump_pairs},
                    threshold=1,
                )
            )
        else:
            missing_slice_status = "none_suspected"

    if input_mode == "single_slice":
        coverage_status = "not_applicable"
        missing_slice_status = "not_applicable"
        checks["coverage"]["not_applicable_reason"] = "single_slice_input"

    motion_levels = []
    for modality in ("ncct", *CTA_MODALITIES):
        item = loaded.get(modality)
        if not item:
            continue
        if input_mode == "single_slice":
            checks["motion"][modality] = {
                "level": "not_applicable",
                "reason": "single_slice_input",
                "bad_pair_ratio": None,
                "bad_pairs": 0,
                "evaluated_pairs": 0,
            }
            continue
        if input_mode != "volume":
            continue
        motion = _motion_check(item["data"], item["zooms"], config)
        checks["motion"][modality] = motion
        motion_levels.append(motion["level"])
        if motion["level"] == "severe":
            findings.append(
                _finding(
                    "suspected_motion_artifact_severe",
                    "high",
                    f"{modality} 疑似存在严重运动伪影",
                    modality=modality,
                    metric=motion.get("bad_pair_ratio"),
                    threshold=config.motion_fail_bad_pair_ratio,
                )
            )
        elif motion["level"] == "moderate":
            findings.append(
                _finding(
                    "suspected_motion_artifact_moderate",
                    "medium",
                    f"{modality} 疑似存在中度运动伪影",
                    modality=modality,
                    metric=motion.get("bad_pair_ratio"),
                    threshold=config.motion_warn_bad_pair_ratio,
                )
            )

    path_token = str(imaging_path or "").strip().lower()
    if path_token in {"ncct_mcta", "ncct_mcta_ctp"}:
        checks["geometry"]["mcta"] = _geometry_check(
            loaded,
            ("ncct", *CTA_MODALITIES),
            config,
            findings,
            in_plane_only=input_mode == "single_slice",
        )
    if path_token == "ncct_mcta_ctp":
        checks["geometry"]["ctp"] = _geometry_check(
            loaded,
            PERFUSION_MODALITIES,
            config,
            findings,
            in_plane_only=input_mode == "single_slice",
        )

    severity_order = {"none": 0, "mild": 1, "moderate": 2, "severe": 3, "unknown": -1}
    known_motion = [level for level in motion_levels if level != "unknown"]
    motion_level = (
        "not_applicable"
        if input_mode == "single_slice"
        else max(known_motion, key=lambda item: severity_order[item])
        if known_motion
        else "unknown"
    )
    geometry_statuses = [
        item.get("status") for item in checks["geometry"].values() if isinstance(item, dict)
    ]
    geometry_status = "mismatched" if "mismatched" in geometry_statuses else ("matched" if geometry_statuses else "unknown")
    severities = {item["severity"] for item in findings}
    if severities.intersection({"critical", "high"}):
        status = "failed"
    elif "medium" in severities:
        status = "warning"
    else:
        status = "passed"
    score = max(0.0, round(1.0 - sum(SEVERITY_PENALTY.get(item["severity"], 0.0) for item in findings), 4))
    affected = []
    if status != "passed":
        affected.extend(["three_class", "vessel_occlusion", "generate_ctp_maps", "run_stroke_analysis"])
    warnings = [item["code"] for item in findings]
    result = {
        "schema_version": "1.0",
        "qc_status": status,
        "qc_score": score,
        "qc_method": "rule_based_nifti_qc",
        "qc_input_mode": input_mode,
        "qc_not_applicable_checks": not_applicable_checks,
        "qc_file_readable": all(modality in loaded for modality in required),
        "qc_modality_complete": all(modality in modalities and modality in paths for modality in required),
        "qc_scan_coverage": coverage_status,
        "qc_slice_thickness_status": slice_thickness_status,
        "qc_motion_artifact_level": motion_level,
        "qc_missing_slice_status": missing_slice_status,
        "qc_geometry_status": geometry_status,
        "qc_warning_message": ";".join(warnings),
        "qc_affected_nodes": list(dict.fromkeys(affected)),
        "qc_blocking_required": status == "failed",
        "qc_review_required": status == "failed",
        "qc_review_reason": ";".join(warnings) if status == "failed" else "",
        "findings": findings,
        "checks": checks,
        "limitations": [
            "运动伪影与疑似缺片为工程启发式结果，不是临床诊断",
            "NIfTI 不包含完整逐帧 DICOM 实例关系，不能精确证明缺失切片编号",
        ],
        "review_override": None,
        "available_modalities": modalities,
        "required_modalities": required,
    }
    if input_mode == "single_slice":
        result["limitations"].append(
            "单层输入无法评估轴向覆盖、内部缺片或跨层运动伪影"
        )
    result["qc_fingerprint"] = _fingerprint(result)
    return result


def has_non_overrideable_failure(result: Mapping[str, Any] | None) -> bool:
    return any(
        not bool(item.get("overrideable", True))
        and str(item.get("severity") or "") in {"critical", "high"}
        for item in ((result or {}).get("findings") or [])
        if isinstance(item, dict)
    )


def apply_quality_review(
    result: Mapping[str, Any],
    *,
    decision: str,
    reviewer: str,
    comment: str,
    reviewed_at: str,
) -> JsonDict:
    reviewed = json.loads(json.dumps(dict(result), ensure_ascii=False))
    reviewed["review_override"] = {
        "decision": decision,
        "reviewer": reviewer,
        "comment": comment,
        "reviewed_at": reviewed_at,
        "original_qc_status": reviewed.get("qc_status"),
    }
    return reviewed
