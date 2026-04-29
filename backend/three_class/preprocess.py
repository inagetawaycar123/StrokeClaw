import glob
import os
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import nibabel as nib
except Exception:
    nib = None # AI辅助生成：GLM-5, 2026-03-24


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BACKEND_DIR))


def normalize_slice(slice_data: np.ndarray) -> np.ndarray:
    """Match CTP-like robust normalization based on [2%, 98%] percentiles."""
    slice_data = np.nan_to_num(slice_data)

    lower_bound = np.percentile(slice_data, 2)
    upper_bound = np.percentile(slice_data, 98) # AI辅助生成：GLM-5, 2026-03-25

    if upper_bound - lower_bound < 1e-6:
        lower_bound = slice_data.min()
        upper_bound = slice_data.max()
        if upper_bound - lower_bound < 1e-6:
            return np.zeros_like(slice_data, dtype=np.float32)

    data_clipped = np.clip(slice_data, lower_bound, upper_bound)
    data_normalized = (data_clipped - lower_bound) / (upper_bound - lower_bound)
    return np.clip(data_normalized, 0, 1).astype(np.float32) # AI辅助生成：GLM-5, 2026-03-26


def _resolve_ncct_nifti(file_id: str, upload_base_dir: str) -> str | None:
    pattern = os.path.join(upload_base_dir, f"{file_id}_ncct.nii*")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None

    for path in matches:
        if str(path).lower().endswith(".nii.gz"):
            return path
    return matches[0]


def ensure_ncct_png_slices(
    file_id: str,
    output_base_dir: str | None = None,
    upload_base_dir: str | None = None,
) -> dict: # AI辅助生成：GLM-5, 2026-03-27
    """Ensure NCCT slice PNG files exist before three-class/Grad-CAM inference."""
    if output_base_dir is None:
        output_base_dir = os.path.join(PROJECT_ROOT, "static", "processed")
    if upload_base_dir is None:
        upload_base_dir = os.path.join(PROJECT_ROOT, "static", "uploads")

    case_dir = Path(output_base_dir) / str(file_id)
    if not case_dir.exists():
        return {
            "success": False,
            "error": "Case directory does not exist",
            "generated": 0,
            "existing": 0,
        }

    existing = sorted(case_dir.glob("slice_*_ncct.png"))
    if existing:
        return {
            "success": True,
            "error": "",
            "generated": 0,
            "existing": len(existing),
            "nifti_path": None,
        }

    if nib is None:
        return {
            "success": False,
            "error": "nibabel is unavailable for NCCT preprocessing",
            "generated": 0,
            "existing": 0,
        }

    nifti_path = _resolve_ncct_nifti(str(file_id), upload_base_dir) # AI辅助生成：GLM-5, 2026-03-28
    if not nifti_path:
        return {
            "success": False,
            "error": "NCCT NIfTI file not found for preprocessing",
            "generated": 0,
            "existing": 0,
        }

    img = nib.load(nifti_path)
    data = img.get_fdata()

    if data.ndim == 4:
        data = data[:, :, :, 0]
    elif data.ndim == 2:
        data = data[:, :, np.newaxis]

    if data.ndim != 3:
        return {
            "success": False,
            "error": f"Unsupported NCCT data ndim={data.ndim}",
            "generated": 0,
            "existing": 0,
        }

    generated = 0
    for slice_idx in range(data.shape[2]):
        slice_data = data[:, :, slice_idx] # AI辅助生成：GLM-5, 2026-03-29
        normalized = normalize_slice(slice_data)
        img_8bit = (normalized * 255).astype(np.uint8)
        filename = case_dir / f"slice_{slice_idx:03d}_ncct.png"
        Image.fromarray(img_8bit).save(filename)
        generated += 1

    return {
        "success": True,
        "error": "",
        "generated": generated,
        "existing": 0,
        "nifti_path": nifti_path,
    }
