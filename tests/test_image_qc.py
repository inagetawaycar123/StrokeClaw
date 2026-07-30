"""Unit tests for image quality control (image_qc.py)."""

import pytest
from backend.compat.image_qc import (
    check_modality_complete,
    check_scan_coverage,
    compute_aggregate_score,
    compute_qc_status,
    build_warning_messages,
    compute_affected_nodes,
    run_full_qc,
    check_contrast_phase,
    check_file_readable,
    MIN_NCCT_SLICES,
    MIN_COVERAGE_MM,
)


# ---------------------------------------------------------------------------
#  check_modality_complete
# ---------------------------------------------------------------------------

class TestCheckModalityComplete:
    def test_ncct_and_mcta_available(self):
        result = check_modality_complete(["ncct", "mcta", "vcta", "dcta"])
        assert result["qc_modality_complete"] is True
        assert result["qc_blocking_required"] is False

    def test_ncct_only(self):
        result = check_modality_complete(["ncct"])
        assert result["qc_modality_complete"] is False
        assert result["has_any_cta"] is False
        assert result["qc_blocking_required"] is False

    def test_missing_ncct(self):
        result = check_modality_complete(["mcta"])
        assert result["qc_modality_complete"] is False
        assert result["qc_blocking_required"] is True

    def test_missing_ctp(self):
        result = check_modality_complete(["ncct", "mcta"])
        assert result["has_ctp"] is False
        assert result["missing_perfusion"] == ["cbf", "cbv", "tmax"]

    def test_full_modalities(self):
        result = check_modality_complete(["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"])
        assert result["qc_modality_complete"] is True
        assert result["has_ctp"] is True
        assert result["missing_core"] == []
        assert result["missing_phase"] == []


# ---------------------------------------------------------------------------
#  check_scan_coverage  (tested through loaded_images dict mock)
# ---------------------------------------------------------------------------

class MockHeader:
    def get_zooms(self):
        return (0.5, 0.5, 1.5)


class MockImage3D:
    shape = (512, 512, 100)
    header = MockHeader()

    def get_fdata(self):
        import numpy as np
        data = np.zeros((512, 512, 100), dtype=np.float32)
        data[50:450, 50:450, :] = 50.0
        return data


class MockImageThinSlices:
    shape = (512, 512, 8)
    header = MockHeader()

    def get_fdata(self):
        import numpy as np
        data = np.zeros((512, 512, 8), dtype=np.float32)
        data[50:450, 50:450, :] = 50.0
        return data


class MockImageLowCoverage:
    shape = (512, 512, 30)
    header = MockHeader()

    def get_fdata(self):
        import numpy as np
        data = np.zeros((512, 512, 30), dtype=np.float32)
        data[50:450, 50:450, :] = 50.0
        return data


class TestCheckScanCoverage:
    def test_normal_coverage(self):
        result = check_scan_coverage({"ncct": MockImage3D()})
        assert result["qc_scan_coverage"] == "complete"
        assert result["coverage_mm"] >= MIN_COVERAGE_MM
        assert result["qc_brain_area_variation"] == "normal"

    def test_low_coverage(self):
        result = check_scan_coverage({"ncct": MockImageLowCoverage()})
        assert result["qc_scan_coverage"] == "incomplete"
        assert result["coverage_mm"] < MIN_COVERAGE_MM

    def test_missing_ncct(self):
        result = check_scan_coverage({})
        assert result["qc_scan_coverage"] == "unknown"

    def test_slice_thickness_normal(self):
        result = check_scan_coverage({"ncct": MockImage3D()})
        assert result["qc_slice_thickness_status"] == "normal"

    def test_slice_thickness_abnormal(self):
        class ThickSliceHeader:
            def get_zooms(self):
                return (0.5, 0.5, 6.0)

        class ThickSliceImage:
            shape = (512, 512, 30)
            header = ThickSliceHeader()
            def get_fdata(self):
                import numpy as np
                d = np.zeros((512, 512, 30), dtype=np.float32)
                d[50:450, 50:450, :] = 50.0
                return d

        result = check_scan_coverage({"ncct": ThickSliceImage()})
        assert result["qc_slice_thickness_status"] == "abnormal"


# ---------------------------------------------------------------------------
#  compute_qc_status
# ---------------------------------------------------------------------------

class TestComputeQcStatus:
    def test_passed(self):
        assert compute_qc_status(1.0, False) == "passed"

    def test_warning(self):
        assert compute_qc_status(0.8, False) == "warning"

    def test_failed_low_score(self):
        assert compute_qc_status(0.5, False) == "failed"

    def test_failed_blocking(self):
        assert compute_qc_status(1.0, True) == "failed"


# ---------------------------------------------------------------------------
#  compute_aggregate_score
# ---------------------------------------------------------------------------

class TestComputeAggregateScore:
    def test_perfect_score(self):
        score = compute_aggregate_score(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert score == 1.0

    def test_ncct_unreadable_penalty(self):
        score = compute_aggregate_score(
            file_check={"unreadable_modalities": {"ncct": "error"}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert score <= 0.6

    def test_severe_motion_penalty(self):
        score = compute_aggregate_score(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal"},
            artifact_check={"qc_motion_artifact_level": "severe",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert score == 0.85

    def test_enhancement_failed_penalty(self):
        score = compute_aggregate_score(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "failed"},
        )
        assert score == 0.8


# ---------------------------------------------------------------------------
#  build_warning_messages
# ---------------------------------------------------------------------------

class TestBuildWarningMessages:
    def test_no_warnings(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert warnings == []

    def test_missing_ncct_warning(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": ["ncct"], "missing_phase": [],
                            "has_any_cta": False, "has_ctp": False},
            coverage_check={"qc_scan_coverage": "unknown", "qc_brain_area_variation": "unknown",
                            "qc_slice_thickness_status": "unknown"},
            artifact_check={"qc_motion_artifact_level": "unknown",
                            "qc_metal_artifact_level": "unknown",
                            "qc_noise_level": "unknown"},
            contrast_check={"qc_enhancement_quality": "unknown"},
        )
        assert "missing_ncct" in warnings
        assert "missing_cta_or_mcta" in warnings

    def test_scan_coverage_incomplete(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "incomplete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert "scan_coverage_incomplete" in warnings

    def test_motion_and_metal_warnings(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "severe",
                            "qc_metal_artifact_level": "moderate",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert "motion_artifact_severe" in warnings
        assert "metal_artifact_moderate" in warnings

    def test_noise_warning(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "severe"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert "excessive_noise_severe" in warnings

    def test_enhancement_warnings(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "failed"},
        )
        assert "cta_enhancement_failed" in warnings

    def test_too_few_slices_warning(self):
        warnings = build_warning_messages(
            file_check={"unreadable_modalities": {}, "too_few_slices": {"ncct": 5}},
            modality_check={"missing_core": [], "missing_phase": [],
                            "has_any_cta": True, "has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete", "qc_brain_area_variation": "normal",
                            "qc_slice_thickness_status": "normal"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert any("too_few_slices" in w for w in warnings)
        assert any("ncct" in w for w in warnings)


# ---------------------------------------------------------------------------
#  compute_affected_nodes
# ---------------------------------------------------------------------------

class TestComputeAffectedNodes:
    def test_no_affected(self):
        affected = compute_affected_nodes(
            modality_check={"has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert affected == []

    def test_ctp_missing_affects_ctp_and_stroke(self):
        affected = compute_affected_nodes(
            modality_check={"has_ctp": False},
            coverage_check={"qc_scan_coverage": "complete"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert "generate_ctp_maps" in affected
        assert "run_stroke_analysis" in affected

    def test_severe_artifact_affects_vessel(self):
        affected = compute_affected_nodes(
            modality_check={"has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete"},
            artifact_check={"qc_motion_artifact_level": "severe",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "good"},
        )
        assert "vessel_occlusion" in affected
        assert "run_stroke_analysis" in affected

    def test_weak_enhancement_affects_vessel_and_ctp(self):
        affected = compute_affected_nodes(
            modality_check={"has_ctp": True},
            coverage_check={"qc_scan_coverage": "complete"},
            artifact_check={"qc_motion_artifact_level": "none",
                            "qc_metal_artifact_level": "none",
                            "qc_noise_level": "normal"},
            contrast_check={"qc_enhancement_quality": "weak"},
        )
        assert "vessel_occlusion" in affected
        assert "generate_ctp_maps" in affected
        assert "run_stroke_analysis" in affected


# ---------------------------------------------------------------------------
#  check_contrast_phase
# ---------------------------------------------------------------------------

class TestCheckContrastPhase:
    def test_missing_phase_without_images(self):
        result = check_contrast_phase(["vcta", "dcta"], True)
        assert result["qc_contrast_phase_status"] == "incomplete"
        assert result["qc_missing_phase"] == ["Š¹    ö	ï\÷	ï\÷	ï\y           @ &v!  0          Ÿ 0      A _ _ i n i t _ _ . c p y t h o A n - 3 1 1 . p y c . 2 1 5 6 6 A 8 3 4 0 8 1 7 6               …    ö	ï\÷	ï\÷	ï\y           À þc  0          Ÿ 0      Á _ _ i n i t _ _ . c p y t h o Á n - 3 1 1 . p y c             0Ö    ö	ï\÷	ï\÷	ï\|           @ 'ŽÎ  @            @      A c o n t r a c t s . c p y t h A o n - 3 1 1 . p y c . 2 1 5 6 A 6 8 3 4 0 8 1 7 6             …K´    ö	ï\÷	ï\÷	ï\|           À Ïî  @            @      Á c o n t r a c t s . c p y t h Á o n - 3 1 1 . p y c           8~    ö	ï\÷	ï\÷	ï\~           @ % A  b          ¡ b      A p l a n n e r . c p y t h o n A - 3 1 1 . p y c . 2 1 5 6 6 8 A 4 0 0 3 5 6 8                 …¬´    ö	ï\÷	ï\÷	ï\~           À žv  b          ¡ b      Á p l a n n e r . c p y t h o n Á - 3 1 1 . p y c               …©    ö	ï\÷	ï\÷	ï\€           À ”-  C#          ¥ C#      Á c o n t e x t _ m a n a g e r Á . c p y t h o n - 3 1 1 . p y Á c                             a¬    ö	ï\÷	ï\÷	ï\ƒ           @ +në  o          ¦ o      A t o o l _ r e g i s t r y . c A p y t h o n - 3 1 1 . p y c . A 2 1 5 6 6 8 3 5 6 7 1 5 2     …	ž    ö	ï\÷	ï\÷	ï\ƒ           À Œ  o          ¦ o      Á t o o l _ r e g i s t r y . c Á p y t h o n - 3 1 1 . p y c   +*    ö	ï\÷	ï\÷	ï\…           @ &a  ‰	          § ‰	      A e x e c u t o r . c p y t h o A n - 3 1 1 . p y c . 2 1 5 6 6 A 8 3 7 5 6 2 0 8               …äô    ö	ï\÷	ï\÷	ï\…           À ‰õ  ‰	          § ‰	      Á e x e c u t o r . c p y t h o Á n - 3 1 1 . p y c             l—    ö	ï\÷	ï\÷	ï\‡           @ &±  Ö          ¨ Ö      A r e p o r t e r . c p y t h o A n - 3 1 1 . p y c . 2 1 5 6 6 A 8 3 7 5 7 6 1 6               …)1    ö	ï\÷	ï\÷	ï\‡           À j¶  Ö          ¨ Ö      Á r e p o r t e r . c p y t h o Á n - 3 1 1 . p y c             …Oþ    ö	ï\÷	ï\÷	ï\Š           À   ÙH          © ÙH      Á l o o p _ c o n t r o l l e r Á . c p y t h o n - 3 1 1 . p y Á c                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              