from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.app as app_module


def _configure_fake_model(monkeypatch, processed_dir: Path, predictor):
    project_root = processed_dir / "project-root"
    dinov3_dir = project_root / "dinov3"
    (dinov3_dir / "ckpt").mkdir(parents=True, exist_ok=True)
    (dinov3_dir / "dinov3").mkdir(exist_ok=True)
    (dinov3_dir / "dinov3权重.pth").write_bytes(b"classifier")
    (dinov3_dir / "ckpt" / "dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth").write_bytes(
        b"backbone"
    )
    monkeypatch.setitem(app_module.app.config, "PROCESSED_FOLDER", str(processed_dir))
    monkeypatch.setattr(app_module, "PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(app_module, "_DINOV3_AVAILABLE", True)
    monkeypatch.setattr(app_module, "_dinov3_predict_single", predictor)


def test_vessel_classification_requires_cta_input(monkeypatch, tmp_path):
    case_dir = tmp_path / "case-no-cta"
    case_dir.mkdir()
    (case_dir / "slice_000_ncct.png").write_bytes(b"not-an-image")
    _configure_fake_model(
        monkeypatch,
        tmp_path,
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    ok, result, message = app_module._run_vessel_occlusion_on_file("case-no-cta")

    assert ok is False
    assert result["status"] == "unavailable"
    assert result["error_code"] == "CTA_INPUT_MISSING"
    assert result["vessel_occlusion_class_result"] is None
    assert "CTA" in message


def test_vessel_classification_keeps_partial_failures(monkeypatch, tmp_path):
    case_dir = tmp_path / "case-partial"
    case_dir.mkdir()
    (case_dir / "slice_000_mcta.png").write_bytes(b"first")
    (case_dir / "slice_001_mcta.png").write_bytes(b"second")

    def predictor(*, image_path, **_kwargs):
        if image_path.endswith("slice_001_mcta.png"):
            raise RuntimeError("synthetic inference failure")
        return {"predicted_label": "Class_0", "confidence": 0.75}

    _configure_fake_model(monkeypatch, tmp_path, predictor)

    ok, result, message = app_module._run_vessel_occlusion_on_file("case-partial")

    assert ok is True
    assert message is None
    assert result["status"] == "completed"
    assert result["vessel_occlusion_class_result"] == "无明显狭窄"
    assert result["confidence"] == 0.75
    assert result["total_slices"] == 2
    assert result["valid_predictions"] == 1
    assert result["class_counts"]["Class_0"] == 1
    assert result["failures"][0]["slice_file"] == "slice_001_mcta.png"


def test_vessel_classification_all_failures_are_structured(monkeypatch, tmp_path):
    case_dir = tmp_path / "case-failed"
    case_dir.mkdir()
    (case_dir / "slice_000_mcta.png").write_bytes(b"input")
    _configure_fake_model(
        monkeypatch,
        tmp_path,
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    ok, result, message = app_module._run_vessel_occlusion_on_file("case-failed")

    assert ok is False
    assert result["status"] == "failed"
    assert result["error_code"] == "ALL_PREDICTIONS_FAILED"
    assert result["vessel_occlusion_class_result"] is None
    assert result["valid_predictions"] == 0
    assert result["failures"][0]["error_message"] == "boom"
    assert message == "All 1 predictions failed"


def test_vessel_classification_falls_back_after_preferred_phase_fully_fails(
    monkeypatch, tmp_path
):
    case_dir = tmp_path / "case-phase-fallback"
    case_dir.mkdir()
    (case_dir / "slice_000_mcta.png").write_bytes(b"broken preferred phase")
    (case_dir / "slice_000_vcta.png").write_bytes(b"valid fallback phase")
    (case_dir / "slice_000_dcta.png").write_bytes(b"must not be reached")
    attempted = []

    def predictor(*, image_path, **_kwargs):
        filename = Path(image_path).name
        attempted.append(filename)
        if filename.endswith("_mcta.png"):
            raise RuntimeError("mCTA decode failure")
        return {"predicted_label": "Class_2_MEVO", "confidence": 0.82}

    _configure_fake_model(monkeypatch, tmp_path, predictor)

    ok, result, message = app_module._run_vessel_occlusion_on_file(
        "case-phase-fallback"
    )

    assert ok is True
    assert message is None
    assert attempted == ["slice_000_mcta.png", "slice_000_vcta.png"]
    assert result["status"] == "completed"
    assert result["predicted_class"] == "Class_2_MEVO"
    assert result["confidence"] == pytest.approx(0.82)
    assert result["total_slices"] == 2
    assert result["valid_predictions"] == 1
    assert result["class_counts"]["Class_2_MEVO"] == 1
    assert result["failures"][0]["cta_phase"] == "mcta"


@pytest.mark.parametrize(
    "invalid_confidence",
    ["not-a-number", float("nan")],
    ids=["non-numeric", "nan"],
)
def test_vessel_classification_rejects_invalid_confidence_atomically(
    monkeypatch, tmp_path, invalid_confidence
):
    case_dir = tmp_path / "case-invalid-confidence"
    case_dir.mkdir()
    (case_dir / "slice_000_mcta.png").write_bytes(b"input")
    _configure_fake_model(
        monkeypatch,
        tmp_path,
        lambda **_kwargs: {
            "predicted_label": "Class_1_LVO",
            "confidence": invalid_confidence,
        },
    )

    ok, result, message = app_module._run_vessel_occlusion_on_file(
        "case-invalid-confidence"
    )

    assert ok is False
    assert result["status"] == "failed"
    assert result["error_code"] == "ALL_PREDICTIONS_FAILED"
    assert result["valid_predictions"] == 0
    assert result["class_counts"] == {
        "Class_0": 0,
        "Class_1_LVO": 0,
        "Class_2_MEVO": 0,
    }
    assert len(result["failures"]) == 1
    assert message == "All 1 predictions failed"


def test_vessel_dominant_confidence_only_uses_dominant_class(
    monkeypatch, tmp_path
):
    case_dir = tmp_path / "case-dominant-confidence"
    case_dir.mkdir()
    for index in range(3):
        (case_dir / f"slice_{index:03d}_mcta.png").write_bytes(b"input")
    predictions = {
        "slice_000_mcta.png": ("Class_0", 0.6),
        "slice_001_mcta.png": ("Class_0", 0.8),
        "slice_002_mcta.png": ("Class_1_LVO", 1.0),
    }

    def predictor(*, image_path, **_kwargs):
        label, confidence = predictions[Path(image_path).name]
        return {"predicted_label": label, "confidence": confidence}

    _configure_fake_model(monkeypatch, tmp_path, predictor)

    ok, result, message = app_module._run_vessel_occlusion_on_file(
        "case-dominant-confidence"
    )

    assert ok is True
    assert message is None
    assert result["predicted_class"] == "Class_0"
    assert result["confidence"] == pytest.approx(0.7)


def test_vessel_exact_evidence_tie_favors_higher_acuity_class(
    monkeypatch, tmp_path
):
    case_dir = tmp_path / "case-acuity-tie"
    case_dir.mkdir()
    (case_dir / "slice_000_mcta.png").write_bytes(b"input")
    (case_dir / "slice_001_mcta.png").write_bytes(b"input")

    def predictor(*, image_path, **_kwargs):
        label = (
            "Class_0"
            if Path(image_path).name == "slice_000_mcta.png"
            else "Class_1_LVO"
        )
        return {"predicted_label": label, "confidence": 0.8}

    _configure_fake_model(monkeypatch, tmp_path, predictor)

    ok, result, message = app_module._run_vessel_occlusion_on_file(
        "case-acuity-tie"
    )

    assert ok is True
    assert message is None
    assert result["predicted_class"] == "Class_1_LVO"
    assert result["confidence"] == pytest.approx(0.8)


def test_vessel_result_is_attached_to_deferred_agent(monkeypatch):
    run_id = "test-vessel-run"
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=1,
        file_id="case-1",
        available_modalities=["ncct", "mcta"],
    )
    result = {
        "status": "completed",
        "vessel_occlusion_class_result": "中血管闭塞",
        "predicted_class": "Class_2_MEVO",
        "confidence": 0.8,
        "class_counts": {"Class_2_MEVO": 1},
        "total_slices": 1,
        "valid_predictions": 1,
    }

    try:
        assert app_module._attach_vessel_result_to_agent_run(run_id, result) is True
        run = app_module._get_agent_run(run_id)
        attached = run["planner_input"]["vessel_occlusion_result"]
        assert attached["status"] == "completed"
        assert attached["predicted_class"] == "Class_2_MEVO"
        context = app_module._build_context_from_completed_tools(run)
        assert context["vessel_occlusion_result"] == attached
    finally:
        with app_module.AGENT_RUNTIME_LOCK:
            app_module.AGENT_RUNS.pop(run_id, None)
            app_module.AGENT_EVENTS.pop(run_id, None)


def test_vessel_result_merges_into_existing_imaging_json(monkeypatch):
    captured = {}

    class Query:
        def update(self, payload):
            captured.update(payload)
            return self

        def eq(self, *_args):
            return self

        def execute(self):
            return SimpleNamespace(data=[captured])

    class Supabase:
        def table(self, name):
            assert name == "patient_imaging"
            return Query()

    monkeypatch.setattr(app_module, "SUPABASE_AVAILABLE", True)
    monkeypatch.setattr(app_module, "supabase", Supabase())
    monkeypatch.setattr(
        app_module,
        "get_imaging_by_case",
        lambda _patient_id, _file_id: {"analysis_result": {"stroke": "kept"}},
    )
    result = {
        "status": "failed",
        "error_code": "ALL_PREDICTIONS_FAILED",
        "error_message": "All 1 predictions failed",
    }

    assert app_module._persist_vessel_result_to_imaging(1, "case-1", result) is True
    merged = captured["analysis_result"]
    assert merged["stroke"] == "kept"
    assert merged["vessel_occlusion_result"]["status"] == "failed"
    assert merged["vessel_occlusion_result"]["vessel_occlusion_class_result"] is None
