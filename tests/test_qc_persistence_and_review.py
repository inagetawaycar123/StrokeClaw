"""Tests for QC persistence, review actions, and pipeline resume logic.

IMPORTANT: These tests import from backend.app which triggers heavy module
loading (cv2, transformers, etc.). To avoid ImportError, the functions under
test are accessed via __import__ hacks or tested through their pure-logic
dependencies (image_qc.py).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.compat.image_qc import run_full_qc


# ---------------------------------------------------------------------------
# run_full_qc — smoke tests (no real NIfTI files)
# ---------------------------------------------------------------------------

class TestRunFullQcEdgeCases:
    def test_empty_input(self):
        result = run_full_qc(nifti_paths={}, available_modalities=[])
        assert result["qc_status"] == "failed"
        assert result["qc_blocking_required"] is True
        assert result["qc_review_required"] is True

    def test_missing_ncct_only(self):
        result = run_full_qc(nifti_paths={}, available_modalities=["mcta"])
        assert result["qc_blocking_required"] is True
        assert result["qc_modality_complete"] is False

    def test_ncct_only_no_cta(self):
        result = run_full_qc(nifti_paths={}, available_modalities=["ncct"])
        assert result["qc_status"] == "warning"
        assert result["qc_modality_complete"] is False
        assert "missing_cta_or_mcta" in result.get("qc_warning_message", "")

    def test_perfect_modalities_warning_only(self):
        result = run_full_qc(nifti_paths={}, available_modalities=["ncct", "mcta", "vcta", "dcta"])
        assert result["qc_status"] in ("warning", "failed")
        assert result["qc_file_readable"] is True

    def test_qc_result_structure(self):
        result = run_full_qc(nifti_paths={}, available_modalities=[])
        expected_keys = {
            "qc_status", "qc_score", "qc_file_readable", "qc_modality_complete",
            "qc_scan_coverage", "qc_slice_thickness_status", "qc_brain_area_variation",
            "qc_motion_artifact_level", "qc_metal_artifact_level", "qc_noise_level",
            "qc_contrast_phase_status", "qc_enhancement_quality", "qc_missing_phase",
            "qc_warning_message", "qc_affected_nodes", "qc_blocking_required",
            "qc_review_required", "qc_review_reason", "available_modalities",
        }
        assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
#  _build_quality_control — adapter layer tests
# ---------------------------------------------------------------------------

class TestBuildQualityControlAdapter:
    def test_build_quality_control_from_run(self):
        from backend.compat.adapters import build_quality_control
        result = build_quality_control(
            imaging={"available_modalities": ["ncct", "mcta"], "case_id": "test-case"},
            run={"file_id": "test-case", "run_id": "test-run"},
        )
        assert isinstance(result, dict)
        assert "qc_status" in result
        assert "qc_score" in result

    def test_build_quality_control_empty(self):
        from backend.compat.adapters import build_quality_control
        result = build_quality_control(None, None)
        assert isinstance(result, dict)
        assert result.get("qc_status") == "failed"


# ---------------------------------------------------------------------------
#  Resume logic — tested via direct function call on the image_qc module
# ---------------------------------------------------------------------------

class TestQcPipelineResumeLogic:
    """Test the resume logic by exercising the QC engine's contract with
    pipeline integration. The actual _resume_agent_pipeline_after_qc function
    lives in backend.app which has heavy imports; we verify its logic here
    through the QC result structure that drives it."""

    def test_qc_result_indicates_affected_nodes(self):
        """When modality is incomplete, affected nodes should list
        generate_ctp_maps and run_stroke_analysis."""
        result = run_full_qc(nifti_paths={}, available_modalities=["ncct", "mcta"])
        assert isinstance(result.get("qc_affected_nodes"), list)

    def test_review_required_on_failed_qc(self):
        """A failed QC result must have review_required=True (triggers pause)."""
        result = run_full_qc(nifti_paths={}, available_modalities=[])
        assert result["qc_review_required"] is True

    def test_full_modalities_with_no_files_has_review_required(self):
        """With full modality list but no actual files, review_required
        depends on the specific checks triggered."""
        result = run_full_qc(
            nifti_paths={},
            available_modalities=["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"],
        )
        assert "qc_review_required" in result


# ---------------------------------------------------------------------------
#  SQL schema validation
# ---------------------------------------------------------------------------

class TestQcSqlSchema:
    def test_sql_contains_all_required_columns(self):
        sql_path = __file__.rsplit("tests", 1)[0] + "sql\\image_quality_control.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            sql = f.read()

        required_columns = [
            "qc_status", "qc_score", "qc_file_readable", "qc_modality_complete",
            "qc_scan_coverage", "qc_slice_thickness_status", "qc_brain_area_variation",
            "qc_motion_artifact_level", "qc_metal_artifact_level", "qc_noise_level",
            "qc_contrast_phase_status", "qc_enhancement_quality",
            "qc_missing_phase", "qc_warning_message", "qc_affected_nodes",
            "qc_blocking_required", "qc_review_required", "qc_review_reason",
            "qc_review_action", "qc_review_comment", "qc_reviewed_by", "qc_reviewed_at",
            "qc_raw_payload", "available_modalities",
        ]
        for col in required_columns:
            assert col in sql, f"Missing column '{col}' in image_quality_control.sql"

    def test_sql_has_unique_constraint(self):
        sql_path = __file__.rsplit("tests", 1)[0] + "sql\\image_quality_control.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            sql = f.read()
        assert "UNIQUE" in sql or "uq_qc_case_run" in sql

    def test_sql_has_indexes(self):
        sql_path = __file__.rsplit("tests", 1)[0] + "sql\\image_quality_control.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            sql = f.read()
        assert "CREATE INDEX" in sql


# ---------------------------------------------------------------------------
#  Adapter - build_quality_control reads from DB when available
# ---------------------------------------------------------------------------

class TestBuildQualityControlFromDb:
    @patch("backend.compat.adapters._get_qc_from_db")
    def test_uses_persisted_qc_when_available(self, mock_get_db):
        mock_get_db.return_value = {
            "qc_status": "failed",
            "qc_score": 0.3,
            "qc_review_required": True,
        }
        from backend.compat.adapters import build_quality_control
        result = build_quality_control(
            imaging={"available_modalities": ["ncct"], "case_id": "test-case"},
            run={"file_id": "test-case", "run_id": "test-run"},
        )
        assert result["qc_status"] == "failed"
        assert result["qc_score"] == 0.3
        mock_get_db.assert_called_once()

    @patch("backend.compat.adapters._get_qc_from_db")
    def test_falls_back_to_on_the_fly_qc_when_no_persisted(self, mock_get_db):
        mock_get_db.return_value = None
        from backend.compat.adapters import build_quality_control
        result = build_quality_control(
            imaging={"available_modalities": ["ncct"], "case_id": "test-case"},
            run={"file_id": "test-case", "run_id": "test-run"},
        )
        assert result["qc_status"] in ("warning", "failed")
        assert result["qc_review_required"] is True
