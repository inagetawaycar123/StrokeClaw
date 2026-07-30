from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple


JsonDict = Dict[str, any]

PERFUSION_MODALITIES = ("cbf", "cbv", "tmax")
MCTA_PHASES = ("mcta", "vcta", "dcta")
CORE_MODALITIES = ("ncct",)
ALL_MODALITIES = ("ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax")

MIN_NCCT_SLICES = 10
MIN_COVERAGE_MM = 120.0
MAX_SLICE_THICKNESS_MM = 5.0
ENHANCEMENT_LOW_HU = 100
ENHANCEMENT_FAIL_HU = 50
NOISE_HU_STD_HIGH = 80
NOISE_HU_STD_MODERATE = 50


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve_nifti_path(file_id: str, modality: str) -> Optional[str]:
    uploads_dir = os.path.join(_project_root(), "static", "uploads")
    for ext in (".nii.gz", ".nii"):
        path = os.path.join(uploads_dir, f"{file_id}_{modality}{ext}")
        if os.path.exists(path):
            return path
    return None


def _load_nifti_safe(path: str) -> Tuple[Optional[any], Optional[str]]:
    try:
        import nibabel as nib
        img = nib.load(path)
        return img, None
    except Exception as e:
        return None, str(e)


def check_file_readable(nifti_paths: Dict[str, str]) -> JsonDict:
    unreadable = {}
    readable_map = {}
    loaded_images = {}
    too_few_slices = {}
    for modality, path in nifti_paths.items():
        if not path or not os.path.exists(path):
            unreadable[modality] = "path_not_found"
            readable_map[modality] = False
            continue
        img, err = _load_nifti_safe(path)
        if img is None:
            unreadable[modality] = err or "unknown_error"
            readable_map[modality] = False
        else:
            readable_map[modality] = True
            loaded_images[modality] = img
            try:
                num_slices = int(img.shape[2]) if len(img.shape) >= 3 else 1
                if num_slices < MIN_NCCT_SLICES:
                    too_few_slices[modality] = num_slices
            except Exception:
                too_few_slices[modality] = "unknown"
    all_readable = all(readable_map.get(m, False) for m in nifti_paths)
    ncct_readable = readable_map.get("ncct", False)
    return {
        "qc_file_readable": all_readable,
        "ncct_readable": ncct_readable,
        "unreadable_modalities": unreadable,
        "too_few_slices": too_few_slices,
        "_loaded_images": loaded_images,
    }


def check_modality_complete(available_modalities: List[str]) -> JsonDict:
    modalities = set(m.lower() for m in available_modalities)
    missing_core = [m for m in CORE_MODALITIES if m not in modalities]
    missing_phase = [m for m in MCTA_PHASES if m not in modalities]
    has_any_cta = any(m in modalities for m in MCTA_PHASES)
    has_ctp = all(m in modalities for m in PERFUSION_MODALITIES)
    missing_perfusion = [m for m in PERFUSION_MODALITIES if m not in modalities]
    blocking_required = bool(missing_core)
    return {
        "missing_core": missing_core,
        "missing_phase": missing_phase,
        "missing_perfusion": missing_perfusion,
        "has_any_cta": has_any_cta,
        "has_ctp": has_ctp,
        "qc_modality_complete": not missing_core and has_any_cta,
        "qc_blocking_required": blocking_required,
    }


def _compute_brain_area_variation(data: any) -> Optional[float]:
    import numpy as np
    if data.ndim < 3 or data.shape[2] < 5:
        return None
    areas = []
    for z in range(data.shape[2]):
        brain_mask = data[:, :, z] > 20
        area = float(np.sum(brain_mask))
        if area > 0:
            areas.append(area)
    if len(areas) < 3:
        return None
    cv = float(np.std(areas) / np.mean(areas))
    return cv


def check_scan_coverage(loaded_images: Dict[str, any]) -> JsonDict:
    ncct_img = loaded_images.get("ncct")
    if ncct_img is None:
        return {
            "qc_scan_coverage": "unknown",
            "qc_slice_thickness_status": "unknown",
            "qc_brain_area_variation": "unknown",
            "coverage_mm": None,
            "num_slices": None,
            "slice_thickness": None,
        }
    try:
        shape = ncct_img.shape
        pixdim = ncct_img.header.get_zooms()
        num_slices = int(shape[2]) if len(shape) >= 3 else 1
        slice_thickness = float(pixdim[2]) if len(pixdim) >= 3 else 1.0
        coverage_mm = num_slices * slice_thickness
        coverage_status = "complete" if coverage_mm >= MIN_COVERAGE_MM else "incomplete"
        slice_thickness_status = "normal" if slice_thickness <= MAX_SLICE_THICKNESS_MM else "abnormal"
        data = ncct_img.get_fdata()
        brain_cv = _compute_brain_area_variation(data)
        brain_area_ok = "normal" if brain_cv is None or brain_cv < 0.5 else "abnormal"
        return {
            "qc_scan_coverage": coverage_status,
            "qc_slice_thickness_status": slice_thickness_status,
            "qc_brain_area_variation": brain_area_ok,
            "brain_area_cv": round(brain_cv, 4) if brain_cv is not None else None,
            "coverage_mm": round(coverage_mm, 2),
            "num_slices": num_slices,
            "slice_thickness": round(slice_thickness, 4),
        }
    except Exception:
        return {
            "qc_scan_coverage": "unknown",
            "qc_slice_thickness_status": "unknown",
            "qc_brain_area_variation": "unknown",
            "coverage_mm": None,
            "num_slices": None,
            "slice_thickness": None,
        }


def check_artifacts(loaded_images: Dict[str, any]) -> JsonDict:
    motion_level = "unknown"
    metal_level = "unknown"
    noise_level = "unknown"
    ncct_img = loaded_images.get("ncct")
    if ncct_img is None:
        return {
            "qc_motion_artifact_level": motion_level,
            "qc_metal_artifact_level": metal_level,
            "qc_noise_level": noise_level,
            "motion_score": None,
            "metal_score": None,
            "noise_hu_std": None,
        }
    try:
        import numpy as np
        data = ncct_img.get_fdata()
        data_flat = data.flatten()
        hu_high = float(np.percentile(data_flat, 99.9))
        metal_ratio = float(np.mean(data_flat > 2000)) if data_flat.size > 0 else 0.0
        if metal_ratio > 0.01:
            metal_level = "severe"
        elif metal_ratio > 0.001:
            metal_level = "moderate"
        elif hu_high > 1500:
            metal_level = "mild"
        else:
            metal_level = "none"
        motion_score = 0.0
        if data.ndim >= 3 and data.shape[2] >= 3:
            slice_means = [float(np.mean(data[:, :, z])) for z in range(data.shape[2])]
            diffs = [abs(slice_means[i] - slice_means[i - 1]) for i in range(1, len(slice_means))]
            if diffs:
                mean_diff = np.mean(diffs)
                std_diff = np.std(diffs)
                motion_score = float(mean_diff + std_diff)
                if motion_score > 30:
                    motion_level = "severe"
                elif motion_score > 15:
                    motion_level = "moderate"
                elif motion_score > 8:
                    motion_level = "mild"
                else:
                    motion_level = "none"
        brain_mask = data_flat[data_flat > 20]
        noise_hu_std = float(np.std(brain_mask)) if len(brain_mask) > 0 else 0.0
        if noise_hu_std > NOISE_HU_STD_HIGH:
            noise_level = "severe"
        elif noise_hu_std > NOISE_HU_STD_MODERATE:
            noise_level = "moderate"
        else:
            noise_level = "normal"
        return {
            "qc_motion_artifact_level": motion_level,
            "qc_metal_artifact_level": metal_level,
            "qc_noise_level": noise_level,
            "motion_score": round(motion_score, 4) if motion_score else None,
            "metal_score": round(metal_ratio, 6),
            "noise_hu_std": round(noise_hu_std, 4),
        }
    except Exception:
        return {
            "qc_motion_artifact_level": "unknown",
            "qc_metal_artifact_level": "unknown",
            "qc_noise_level": "unknown",
            "motion_score": None,
            "metal_score": None,
            "noise_hu_std": None,
        }


def _estimate_enhancement_quality(loaded_images: Dict[str, any]) -> JsonDict:
    import numpy as np
    cta_candidates = [m for m in MCTA_PHASES if m in loaded_images]
    if not cta_candidates:
        return {"enhancement_quality": "unknown", "mean_arterial_hu": None}
    best_img = None
    for m in cta_candidates:
        img = loaded_images.get(m)
        if img is not None:
            best_img = img
            break
    if best_img is None:
        return {"enhancement_quality": "unknown", "mean_arterial_hu": None}
    try:
        data = best_img.get_fdata()
        data_flat = data.flatten()
        high_hu = data_flat[(data_flat > 100) & (data_flat < 600)]
        if len(high_hu) == 0:
            return {"enhancement_quality": "failed", "mean_arterial_hu": None}
        mean_hu = float(np.mean(high_hu))
        if mean_hu < ENHANCEMENT_FAIL_HU:
            quality = "failed"
        elif mean_hu < ENHANCEMENT_LOW_HU:
            quality = "weak"
        else:
            quality = "good"
        return {"enhancement_quality": quality, "mean_arterial_hu": round(mean_hu, 2)}
    except Exception:
        return {"enhancement_quality": "unknown", "mean_arterial_hu": None}


def check_contrast_phase(
    missing_phase: List[str],
    has_any_cta: bool,
    loaded_images: Optional[Dict[str, any]] = None,
) -> JsonDict:
    result = {
        "qc_contrast_phase_status": "complete" if not missing_phase else "incomplete",
        "qc_missing_phase": missing_phase,
    }
    if loaded_images and has_any_cta:
        enh = _estimate_enhancement_quality(loaded_images)
        result["qc_enhancement_quality"] = enh.get("enhancement_quality", "unknown")
        result["mean_arterial_hu"] = enh.get("mean_arterial_hu")
    else:
        result["qc_enhancement_quality"] = "unknown"
        result["mean_arterial_hu"] = None
    return result


def compute_aggregate_score(
    file_check: JsonDict,
    modality_check: JsonDict,
    coverage_check: JsonDict,
    artifact_check: JsonDict,
    contrast_check: JsonDict,
) -> float:
    score = 1.0
    unreadable = file_check.get("unreadable_modalities", {})
    if unreadable and "ncct" in unreadable:
        score -= 0.4
    if file_check.get("too_few_slices"):
        score -= 0.2
    if modality_check.get("missing_core"):
        score -= 0.4
    if modality_check.get("missing_phase") and modality_check.get("has_any_cta"):
        score -= 0.1
    if not modality_check.get("has_any_cta"):
        score -= 0.2
    if not modality_check.get("has_ctp"):
        score -= 0.05
    if coverage_check.get("qc_scan_coverage") == "incomplete":
        score -= 0.15
    if coverage_check.get("qc_brain_area_variation") == "abnormal":
        score -= 0.05
    motion = artifact_check.get("qc_motion_artifact_level", "unknown")
    if motion == "severe":
        score -= 0.15
    elif motion == "moderate":
        score -= 0.08
    metal = artifact_check.get("qc_metal_artifact_level", "unknown")
    if metal == "severe":
        score -= 0.15
    elif metal == "moderate":
        score -= 0.08
    noise = artifact_check.get("qc_noise_level", "unknown")
    if noise == "severe":
        score -= 0.10
    elif noise == "moderate":
        score -= 0.05
    enhancement = contrast_check.get("qc_enhancement_quality", "unknown")
    if enhancement == "failed":
        score -= 0.2
    elif enhancement == "weak":
        score -= 0.1
    return max(0.0, round(score, 4))


def compute_qc_status(
    score: float,
    blocking_required: bool,
) -> str:
    if blocking_required:
        return "failed"
    if score < 0.6:
        return "failed"
    if score < 1.0:
        return "warning"
    return "passed"


def build_warning_messages(
    file_check: JsonDict,
    modality_check: JsonDict,
    coverage_check: JsonDict,
    artifact_check: JsonDict,
    contrast_check: JsonDict,
) -> List[str]:
    warnings = []
    unreadable = file_check.get("unreadable_modalities", {})
    if unreadable:
        for mod, err in unreadable.items():
            warnings.append(f"{mod}_unreadable")
    if file_check.get("too_few_slices"):
        for mod, n in file_check["too_few_slices"].items():
            warnings.append(f"{mod}_too_few_slices:{n}")
    if modality_check.get("missing_core"):
        warnings.append("missing_ncct")
    if not modality_check.get("has_any_cta"):
        warnings.append("missing_cta_or_mcta")
    if modality_check.get("missing_phase") and modality_check.get("has_any_cta"):
        warnings.append("incomplete_mcta_phases")
    if coverage_check.get("qc_scan_coverage") == "incomplete":
        warnings.append("scan_coverage_incomplete")
    if coverage_check.get("qc_brain_area_variation") == "abnormal":
        warnings.append("brain_area_variation_abnormal")
    motion = artifact_check.get("qc_motion_artifact_level", "unknown")
    if motion in ("moderate", "severe"):
        warnings.append(f"motion_artifact_{motion}")
    metal = artifact_check.get("qc_metal_artifact_level", "unknown")
    if metal in ("moderate", "severe"):
        warnings.append(f"metal_artifact_{metal}")
    noise = artifact_check.get("qc_noise_level", "unknown")
    if noise in ("moderate", "severe"):
        warnings.append(f"excessive_noise_{noise}")
    enhancement = contrast_check.get("qc_enhancement_quality", "unknown")
    if enhancement == "failed":
        warnings.append("cta_enhancement_failed")
    elif enhancement == "weak":
        warnings.append("cta_enhancement_weak")
    return warnings


def compute_affected_nodes(
    modality_check: JsonDict,
    coverage_check: JsonDict,
    artifact_check: JsonDict,
    contrast_check: JsonDict,
) -> List[str]:
    affected = []
    if not modality_check.get("has_ctp") or coverage_check.get("qc_scan_coverage") == "incomplete":
        affected.append("generate_ctp_maps")
        affected.append("run_stroke_analysis")
    motion = artifact_check.get("qc_motion_artifact_level", "unknown")
    metal = artifact_check.get("qc_metal_artifact_level", "unknown")
    noise = artifact_check.get("qc_noise_level", "unknown")
    enhancement = contrast_check.get("qc_enhancement_quality", "unknown")
    if motion in ("moderate", "severe") or metal in ("moderate", "severe") or noise in ("moderate", "severe"):
        affected.append("vessel_occlusion")
        affected.append("run_stroke_analysis")
    if enhancement in ("failed", "weak"):
        affected.append("vessel_occlusion")
        affected.append("generate_ctp_maps")
        affected.append("run_stroke_analysis")
    return list(dict.fromkeys(affected))


def run_full_qc(
    nifti_paths: Dict[str, str],
    available_modalities: List[str],
) -> JsonDict:
    file_check = check_file_readable(nifti_paths)
    loaded_images = file_check.pop("_loaded_images", {})
    modality_check = check_modality_complete(available_modalities)
    coverage_check = check_scan_coverage(loaded_images)
    artifact_check = check_artifacts(loaded_images)
    contrast_check = check_contrast_phase(
        modality_check.get("missing_phase", []),
        modality_check.get("has_any_cta", False),
        loaded_images=loaded_images,
    )
    score = compute_aggregate_score(file_check, modality_check, coverage_check, artifact_check, contrast_check)
    warnings = build_warning_messages(file_check, modality_check, coverage_check, artifact_check, contrast_check)
    blocking = modality_check.get("qc_blocking_required", False)
    status = compute_qc_status(score, blocking)
    affected = compute_affected_nodes(modality_check, coverage_check, artifact_check, contrast_check)
    review_required = bool(warnings) or blocking
    return {
        "qc_status": status,
        "qc_score": score,
        "qc_file_readable": file_check.get("qc_file_readable", False),
        "qc_modality_complete": modality_check.get("qc_modality_complete", False),
        "qc_scan_coverage": coverage_check.get("qc_scan_coverage", "unknown"),
        "qc_slice_thickness_status": coverage_check.get("qc_slice_thickness_status", "unknown"),
        "qc_brain_area_variation": coverage_check.get("qc_brain_area_variation", "unknown"),
        "qc_motion_artifact_level": artifact_che…ê    Ä	ï\Å	ï\Å	ï\¹           À %P  ¶           ¶      Á c o n f t e s t . c p y t h o Á n - 3 1 1 - p y t e s t - 9 . Á 0 . 2 . p y c                 …—V    Ä	ï\Å	ï\Å	ï\À           À 7:Ý  ü>          Ž ü>      Á t e s t _ f i e l d _ c o m p Á a t _ a d a p t e r s . c p y Á t h o n - 3 1 1 - p y t e s t Á - 9 . 0 . 2 . p y c           …Êu    ö	ï\÷	ï\÷	ï\s           À 4vø  V$          œ V$      Á t e s t _ a g e n t _ l o o p Á _ m o d u l e s . c p y t h o Á n - 3 1 1 - p y t e s t - 9 . Á 0 . 2 . p y c                 ¥Þ    ö	ï\÷	ï\÷	ï\Œ           @ ?zÄ  §5          ª §5      A t e s t _ c h a t _ p a t i e A n t _ i d _ c o m m a n d . c A p y t h o n - 3 1 1 - p y t e A s t - 9 . 0 . 2 . p y c . 2 9 A 3 8 8                         …u    ö	ï\÷	ï\÷	ï\Œ           À 9¹Y  §5          ª §5      Á t e s t _ c h a t _ p a t i e Á n t _ i d _ c o m m a n d . c Á p y t h o n - 3 1 1 - p y t e Á s t - 9 . 0 . 2 . p y c       ÇÀ    ö	ï\÷	ï\÷	ï\           @ >Êi  \          « \      A t e s t _ c o m p a t _ r o u A t e s _ c o n t r a c t . c p A y t h o n - 3 1 1 - p y t e