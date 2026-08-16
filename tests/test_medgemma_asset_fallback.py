import json

import pytest

from backend import medgemma_report


def _write_incomplete_model(model_dir):
    index = {
        "metadata": {"total_size": 8600158944},
        "weight_map": {
            "model.a": "model-00001-of-00002.safetensors",
            "model.b": "model-00002-of-00002.safetensors",
        },
    }
    (model_dir / "model.safetensors.index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )
    (model_dir / "tokenizer.json").write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:placeholder\nsize 100\n",
        encoding="utf-8",
    )


def test_asset_validation_reports_missing_shards_and_lfs_pointers(tmp_path):
    _write_incomplete_model(tmp_path)

    with pytest.raises(medgemma_report.MedGemmaModelAssetsError) as exc_info:
        medgemma_report.validate_medgemma_assets(str(tmp_path))

    message = str(exc_info.value)
    assert "model-00001-of-00002.safetensors" in message
    assert "model-00002-of-00002.safetensors" in message
    assert "tokenizer.json" in message
    assert "Git LFS" in message


def test_missing_model_assets_return_transparent_structured_fallback(
    tmp_path, monkeypatch
):
    _write_incomplete_model(tmp_path)
    monkeypatch.setattr(medgemma_report, "_medgemma_dir", lambda: str(tmp_path))

    result = medgemma_report.generate_report_with_medgemma(
        structured_data={
            "core_infarct_volume": 12.5,
            "penumbra_volume": 30.0,
            "mismatch_ratio": 2.4,
            "vessel_occlusion_result": {
                "status": "completed",
                "vessel_occlusion_class_result": "无明显狭窄",
                "predicted_class": "Class_0",
                "confidence": 0.82,
                "class_counts": {"Class_0": 3},
                "total_slices": 3,
                "valid_predictions": 3,
            },
        },
        imaging_data={"available_modalities": ["ncct", "mcta"]},
        file_id="case-incomplete-model",
        output_format="markdown",
    )

    assert result["success"] is True
    assert result["is_mock"] is True
    assert result["degraded_mode"] is True
    assert result["error_code"] == "MEDGEMMA_MODEL_ASSETS_MISSING"
    assert "降级模式" in result["report"]
    assert "无明显狭窄" in result["report"]
    assert result["report_payload"]["model_status"]["available"] is False
