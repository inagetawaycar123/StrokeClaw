from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from backend.image_quality_control import (
    ImageQualityConfig,
    apply_quality_review,
    has_non_overrideable_failure,
    required_modalities,
    run_image_quality_control,
)


def _volume(shape=(32, 32, 30)) -> np.ndarray:
    x, y = np.mgrid[-1:1 : complex(shape[0]), -1:1 : complex(shape[1])]
    base = np.exp(-4 * (x**2 + y**2)) * 100
    return np.stack([base + index * 0.02 for index in range(shape[2])], axis=2).astype(
        np.float32
    )


def _write_nifti(
    path: Path,
    *,
    data: np.ndarray | None = None,
    spacing=(1.0, 1.0, 4.0),
    units="mm",
) -> str:
    payload = _volume() if data is None else np.asarray(data, dtype=np.float32)
    affine = np.diag([*spacing, 1.0])
    image = nib.Nifti1Image(payload, affine)
    if units is not None:
        image.header.set_xyzt_units(units)
    nib.save(image, str(path))
    return str(path)


def _config(**changes) -> ImageQualityConfig:
    values = ImageQualityConfig().__dict__ | changes
    return ImageQualityConfig(**values)


def _codes(result):
    return {item["code"] for item in result["findings"]}


def test_good_3d_and_first_frame_4d_are_accepted(tmp_path):
    ncct = _write_nifti(tmp_path / "ncct.nii.gz")
    result = run_image_quality_control(
        {"ncct": ncct}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_status"] == "passed"
    assert result["qc_file_readable"] is True
    assert result["qc_scan_coverage"] == "complete"
    assert result["qc_slice_thickness_status"] == "normal"
    assert len(result["qc_fingerprint"]) == 64

    four_d = _write_nifti(
        tmp_path / "ncct-4d.nii.gz", data=np.stack([_volume(), _volume()], axis=3)
    )
    accepted = run_image_quality_control(
        {"ncct": four_d}, ["ncct"], "ncct_only", config=_config()
    )
    assert accepted["qc_file_readable"] is True
    assert "nifti_unreadable" not in _codes(accepted)


@pytest.mark.parametrize("thickness,expected", [(5.0, "normal"), (5.1, "abnormal")])
def test_slice_thickness_boundary(tmp_path, thickness, expected):
    ncct = _write_nifti(tmp_path / f"ncct-{thickness}.nii.gz", spacing=(1, 1, thickness))
    result = run_image_quality_control(
        {"ncct": ncct}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_slice_thickness_status"] == expected
    assert result["qc_status"] == ("passed" if thickness == 5.0 else "failed")


def test_structural_errors_are_non_overrideable(tmp_path):
    missing = run_image_quality_control(
        {"ncct": str(tmp_path / "missing.nii.gz")},
        ["ncct"],
        "ncct_only",
        config=_config(),
    )
    assert missing["qc_status"] == "failed"
    assert missing["qc_blocking_required"] is True
    assert has_non_overrideable_failure(missing) is True
    assert "file_not_found" in _codes(missing)

    invalid = _write_nifti(
        tmp_path / "invalid.nii.gz", data=np.ones((4, 4, 4, 2, 2))
    )
    result = run_image_quality_control(
        {"ncct": invalid}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_status"] == "failed"
    assert "unsupported_dimension" in _codes(result)


def test_two_dimensional_nifti_is_normalized_to_single_slice(tmp_path):
    data = _volume((32, 32, 1))[:, :, 0]
    path = _write_nifti(tmp_path / "ncct-2d.nii.gz", data=data)
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )

    assert result["qc_input_mode"] == "single_slice"
    assert result["checks"]["files"]["ncct"]["shape"] == [32, 32, 1]
    assert result["qc_status"] == "warning"
    assert result["qc_blocking_required"] is False
    assert result["qc_review_required"] is False
    assert result["qc_scan_coverage"] == "not_applicable"
    assert result["qc_motion_artifact_level"] == "not_applicable"
    assert result["qc_missing_slice_status"] == "not_applicable"
    assert result["qc_not_applicable_checks"] == [
        "axial_coverage",
        "internal_missing_slices",
        "inter_slice_motion",
    ]
    assert "single_slice_limited_assessment" in _codes(result)
    assert has_non_overrideable_failure(result) is False


@pytest.mark.parametrize(
    "imaging_path,modalities",
    [
        ("ncct_only", ["ncct"]),
        ("ncct_single_phase_cta", ["ncct", "mcta"]),
        ("ncct_mcta", ["ncct", "mcta", "vcta", "dcta"]),
        (
            "ncct_mcta_ctp",
            ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"],
        ),
    ],
)
def test_all_business_paths_accept_consistent_single_slice_inputs(
    tmp_path, imaging_path, modalities
):
    paths = {
        modality: _write_nifti(
            tmp_path / f"{imaging_path}-{modality}.nii.gz",
            data=_volume((24, 24, 1)),
        )
        for modality in modalities
    }
    result = run_image_quality_control(
        paths, modalities, imaging_path, config=_config()
    )

    assert result["qc_input_mode"] == "single_slice"
    assert result["qc_status"] == "warning"
    assert result["qc_blocking_required"] is False
    assert "invalid_slice_stack_configuration" not in _codes(result)
    if imaging_path in {"ncct_mcta", "ncct_mcta_ctp"}:
        assert result["checks"]["geometry"]["mcta"]["status"] == "matched"
        assert all(
            item["comparison_mode"] == "in_plane"
            for item in result["checks"]["geometry"]["mcta"]["comparisons"]
        )


def test_single_slice_unknown_units_warn_without_blocking(tmp_path):
    path = _write_nifti(
        tmp_path / "single-unknown-units.nii.gz",
        data=_volume((24, 24, 1)),
        units=None,
    )
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_status"] == "warning"
    assert result["qc_slice_thickness_status"] == "unknown"
    assert "spatial_units_unknown" in _codes(result)
    assert result["qc_blocking_required"] is False


def test_single_slice_abnormal_declared_thickness_remains_overrideable_failure(
    tmp_path,
):
    path = _write_nifti(
        tmp_path / "single-thick.nii.gz",
        data=_volume((24, 24, 1)),
        spacing=(1.0, 1.0, 6.0),
    )
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_input_mode"] == "single_slice"
    assert result["qc_slice_thickness_status"] == "abnormal"
    assert result["qc_status"] == "failed"
    assert has_non_overrideable_failure(result) is False


@pytest.mark.parametrize("slice_count", [2, 5, 9])
def test_truncated_multi_slice_inputs_remain_structural_failures(
    tmp_path, slice_count
):
    path = _write_nifti(
        tmp_path / f"truncated-{slice_count}.nii.gz",
        data=_volume((24, 24, slice_count)),
    )
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_input_mode"] == "invalid_mixed"
    assert result["qc_status"] == "failed"
    assert "invalid_slice_stack_configuration" in _codes(result)
    assert has_non_overrideable_failure(result) is True


def test_mixed_single_and_volume_inputs_are_structural_failures(tmp_path):
    paths = {
        "ncct": _write_nifti(
            tmp_path / "mixed-ncct.nii.gz", data=_volume((24, 24, 1))
        ),
        "mcta": _write_nifti(tmp_path / "mixed-mcta.nii.gz"),
        "vcta": _write_nifti(tmp_path / "mixed-vcta.nii.gz"),
        "dcta": _write_nifti(tmp_path / "mixed-dcta.nii.gz"),
    }
    result = run_image_quality_control(
        paths, paths.keys(), "ncct_mcta", config=_config()
    )
    assert result["qc_input_mode"] == "invalid_mixed"
    assert result["qc_status"] == "failed"
    assert "invalid_slice_stack_configuration" in _codes(result)
    assert has_non_overrideable_failure(result) is True


def test_ten_slice_boundary_is_volume_mode(tmp_path):
    path = _write_nifti(
        tmp_path / "ten-slices.nii.gz",
        data=_volume((24, 24, 10)),
        spacing=(1.0, 1.0, 1.0),
    )
    result = run_image_quality_control(
        {"ncct": path},
        ["ncct"],
        "ncct_only",
        config=_config(min_coverage_mm=10.0),
    )
    assert result["qc_input_mode"] == "volume"
    assert result["qc_status"] == "passed"


def test_single_slice_can_be_disabled_by_configuration(tmp_path):
    path = _write_nifti(
        tmp_path / "single-disabled.nii.gz", data=_volume((24, 24, 1))
    )
    result = run_image_quality_control(
        {"ncct": path},
        ["ncct"],
        "ncct_only",
        config=_config(allow_single_slice=False),
    )
    assert result["qc_input_mode"] == "invalid_mixed"
    assert result["qc_status"] == "failed"
    assert has_non_overrideable_failure(result) is True


def test_single_slice_in_plane_geometry_mismatch_remains_structural(tmp_path):
    paths = {
        "ncct": _write_nifti(
            tmp_path / "single-geometry-ncct.nii.gz", data=_volume((24, 24, 1))
        ),
        "mcta": _write_nifti(
            tmp_path / "single-geometry-mcta.nii.gz", data=_volume((23, 24, 1))
        ),
        "vcta": _write_nifti(
            tmp_path / "single-geometry-vcta.nii.gz", data=_volume((24, 24, 1))
        ),
        "dcta": _write_nifti(
            tmp_path / "single-geometry-dcta.nii.gz", data=_volume((24, 24, 1))
        ),
    }
    result = run_image_quality_control(
        paths, paths.keys(), "ncct_mcta", config=_config()
    )
    assert result["qc_input_mode"] == "single_slice"
    assert result["qc_geometry_status"] == "mismatched"
    assert "required_geometry_mismatch" in _codes(result)
    assert has_non_overrideable_failure(result) is True


def test_non_finite_and_constant_volumes_fail(tmp_path):
    data = _volume()
    data.flat[:100] = np.nan
    path = _write_nifti(tmp_path / "nan.nii.gz", data=data)
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert "non_finite_voxels" in _codes(result)
    assert result["qc_status"] == "failed"

    constant = _write_nifti(tmp_path / "constant.nii.gz", data=np.ones((20, 20, 30)))
    result = run_image_quality_control(
        {"ncct": constant}, ["ncct"], "ncct_only", config=_config()
    )
    assert "empty_or_constant_volume" in _codes(result)


def test_internal_blank_slices_warn_then_fail(tmp_path):
    one_blank = _volume()
    one_blank[:, :, 15] = 0
    path = _write_nifti(tmp_path / "one-blank.nii.gz", data=one_blank)
    warning = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert warning["qc_missing_slice_status"] == "suspected_single"
    assert warning["qc_status"] == "warning"

    two_blanks = _volume()
    two_blanks[:, :, 14:16] = 0
    path = _write_nifti(tmp_path / "two-blanks.nii.gz", data=two_blanks)
    failed = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert failed["qc_missing_slice_status"] == "suspected_multiple"
    assert failed["qc_status"] == "failed"
    assert has_non_overrideable_failure(failed) is False


@pytest.mark.parametrize(
    "shifted_indices,expected_status,expected_level",
    [([10, 18], "warning", "moderate"), ([8, 12, 16, 20], "failed", "severe")],
)
def test_motion_heuristic_warns_and_fails_at_configured_ratios(
    tmp_path, shifted_indices, expected_status, expected_level
):
    data = _volume()
    for index in shifted_indices:
        data[:, :, index] = np.roll(data[:, :, index], 5, axis=0)
    path = _write_nifti(tmp_path / f"motion-{len(shifted_indices)}.nii.gz", data=data)
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    assert result["qc_motion_artifact_level"] == expected_level
    assert result["qc_status"] == expected_status


def test_abrupt_internal_slice_jump_is_flagged_as_suspected_missing_data(tmp_path):
    data = _volume()
    rng = np.random.default_rng(20260731)
    data[:, :, 15] = rng.normal(50, 30, data.shape[:2])
    path = _write_nifti(tmp_path / "abrupt-jump.nii.gz", data=data)
    result = run_image_quality_control(
        {"ncct": path},
        ["ncct"],
        "ncct_only",
        config=_config(motion_max_shift_mm=1e6, motion_min_correlation=-1.0),
    )
    assert result["checks"]["coverage"]["abnormal_jump_pairs"]
    assert result["qc_missing_slice_status"] == "suspected_multiple"
    assert result["qc_status"] == "failed"


def test_path_specific_modalities_and_geometry(tmp_path):
    assert required_modalities("ncct_only", ["ncct"]) == ["ncct"]
    assert required_modalities(
        "ncct_mcta", ["ncct", "mcta", "vcta", "dcta"]
    ) == ["ncct", "mcta", "vcta", "dcta"]
    assert required_modalities(
        "ncct_mcta_ctp", ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]
    ) == ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]

    paths = {
        "ncct": _write_nifti(tmp_path / "ncct.nii.gz"),
        "mcta": _write_nifti(tmp_path / "mcta.nii.gz", data=_volume((31, 32, 30))),
        "vcta": _write_nifti(tmp_path / "vcta.nii.gz"),
        "dcta": _write_nifti(tmp_path / "dcta.nii.gz"),
    }
    result = run_image_quality_control(
        paths, paths.keys(), "ncct_mcta", config=_config()
    )
    assert result["qc_geometry_status"] == "mismatched"
    assert "required_geometry_mismatch" in _codes(result)
    assert has_non_overrideable_failure(result) is True


def test_real_ctp_requires_mutually_consistent_maps(tmp_path):
    paths = {
        "ncct": _write_nifti(tmp_path / "ncct.nii.gz"),
        "mcta": _write_nifti(tmp_path / "mcta.nii.gz"),
        "vcta": _write_nifti(tmp_path / "vcta.nii.gz"),
        "dcta": _write_nifti(tmp_path / "dcta.nii.gz"),
        "cbf": _write_nifti(tmp_path / "cbf.nii.gz", data=_volume((24, 24, 30))),
        "cbv": _write_nifti(tmp_path / "cbv.nii.gz", data=_volume((24, 24, 30))),
        "tmax": _write_nifti(tmp_path / "tmax.nii.gz", data=_volume((24, 25, 30))),
    }
    result = run_image_quality_control(
        paths, paths.keys(), "ncct_mcta_ctp", config=_config()
    )
    assert result["checks"]["geometry"]["ctp"]["status"] == "mismatched"
    assert result["qc_status"] == "failed"


def test_review_preserves_original_failure_and_fingerprint(tmp_path):
    data = _volume()
    data[:, :, 14:16] = 0
    path = _write_nifti(tmp_path / "review.nii.gz", data=data)
    result = run_image_quality_control(
        {"ncct": path}, ["ncct"], "ncct_only", config=_config()
    )
    reviewed = apply_quality_review(
        result,
        decision="accept_risk",
        reviewer="doctor-test",
        comment="synthetic test",
        reviewed_at="2026-07-31T00:00:00+00:00",
    )
    assert reviewed["qc_status"] == "failed"
    assert reviewed["qc_fingerprint"] == result["qc_fingerprint"]
    assert reviewed["review_override"]["original_qc_status"] == "failed"
    assert reviewed["review_override"]["decision"] == "accept_risk"
