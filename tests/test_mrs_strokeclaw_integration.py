from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from backend import app as app_module
from backend.clinical_dag import build_clinical_dag
from backend.icv import evaluate_icv
from backend import mrs_prognosis


def _run(record=None):
    return {
        "run_id": "run-mrs-test",
        "patient_id": 7,
        "file_id": "case-mrs-test",
        "planner_input": {
            "patient_id": 7,
            "file_id": "case-mrs-test",
            "mrs_clinical_record": dict(record or {}),
            "mrs_image_files": ["slice.npy"],
        },
    }


def _inference(mode: str):
    risk = 0.7 if mode == "update_24h" else 0.4
    return {
        "status": "success",
        "model": {
            "version": f"{mode}-v1",
            "bundle_version": "mrs-mvp-1",
            "release_status": "MVP_RESEARCH",
            "is_real_inference": True,
        },
        "prediction": {
            "good_prognosis_probability": 1.0 - risk,
            "poor_prognosis_risk": risk,
            "predicted_class": int(risk >= 0.55),
            "decision_threshold": 0.55,
            "probability_calibrated": True,
        },
        "confidence": {
            "level": "high",
            "ensemble_probability_std": 0.01,
            "threshold_margin": abs(risk - 0.55),
            "reasons": [],
        },
        "key_evidence": {"clinical": [], "imaging": []},
        "data_quality": {
            "missing_clinical_fields": [],
            "used_ncct_files": [],
            "image_quality_warnings": [],
        },
    }


class _FakeModel:
    def __init__(self, mode):
        self.mode = mode

    def predict(self, *_args, **_kwargs):
        return _inference(self.mode)


@pytest.fixture(autouse=True)
def _clear_runs():
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()
    yield
    with app_module.AGENT_RUNTIME_LOCK:
        app_module.AGENT_RUNS.clear()
        app_module.AGENT_EVENTS.clear()


def test_runtime_order_places_mrs_after_stroke_and_before_icv():
    for name in ("ncct_mcta", "ncct_mcta_ctp"):
        sequence = app_module.AGENT_TOOL_SEQUENCE_MAP[name]
        assert sequence.index("run_stroke_analysis") + 1 == sequence.index(
            "run_mrs_prognosis_prediction"
        )
        assert sequence.index("run_mrs_prognosis_prediction") + 1 == sequence.index("icv")
    dag = build_clinical_dag(["ncct", "mcta", "vcta", "dcta"])
    edges = {(item["from"], item["to"]) for item in dag["edges"]}
    assert ("stroke_analysis", "mrs_prognosis") in edges
    assert ("mrs_prognosis", "internal_check") in edges


def test_missing_24h_routes_to_baseline(monkeypatch):
    loaded = []

    def fake_load(path, **_kwargs):
        loaded.append(Path(path).name)
        return _FakeModel("baseline")

    monkeypatch.setattr(mrs_prognosis, "_load_model", fake_load)
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=_run({"Gender": "M", "Age": 70, "NIHSS Baseline": 10}),
        patient_data={},
    )
    assert result["status"] == "completed"
    assert result["result_mode"] == "baseline"
    assert result["display_mode"] == "首诊初步评估"
    assert loaded == ["mrs_baseline_mvp.pt"]


def test_observed_24h_routes_to_update(monkeypatch):
    loaded = []

    def fake_load(path, **_kwargs):
        loaded.append(Path(path).name)
        return _FakeModel("update_24h")

    monkeypatch.setattr(mrs_prognosis, "_load_model", fake_load)
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=_run(
            {
                "Gender": "F",
                "Age": 60,
                "NIHSS Baseline": 12,
                "NIHSS 24 HOURS": 8,
            }
        ),
        patient_data={},
    )
    assert result["status"] == "completed"
    assert result["result_mode"] == "update_24h"
    assert result["display_mode"] == "24小时更新评估"
    assert loaded == ["mrs_update24h_mvp.pt"]


def test_update_bundle_load_failure_has_traceable_baseline_fallback(monkeypatch):
    def fake_load(path, **_kwargs):
        if "update24h" in Path(path).name:
            raise RuntimeError("update bundle checksum failed")
        return _FakeModel("baseline")

    monkeypatch.setattr(mrs_prognosis, "_load_model", fake_load)
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=_run({"NIHSS 24 HOURS": 9}), patient_data={}
    )
    assert result["status"] == "completed"
    assert result["result_mode"] == "baseline"
    assert result["fallback_used"] is True
    assert "checksum" in result["fallback_reason"]


def test_missing_bundle_never_outputs_fake_probability(monkeypatch):
    monkeypatch.setattr(
        mrs_prognosis,
        "_load_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=_run(), patient_data={}
    )
    assert result["status"] == "unavailable"
    assert result["prediction"] is None
    assert result["model"]["is_real_inference"] is False


def test_completed_probability_and_threshold_contract_passes_icv(monkeypatch):
    monkeypatch.setattr(
        mrs_prognosis, "_load_model", lambda *_args, **_kwargs: _FakeModel("baseline")
    )
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=_run(), patient_data={}
    )
    prediction = result["prediction"]
    assert prediction["good_prognosis_probability"] + prediction["poor_prognosis_risk"] == pytest.approx(1.0)
    assert prediction["predicted_class"] == int(
        prediction["poor_prognosis_risk"] >= prediction["decision_threshold"]
    )
    icv = evaluate_icv(
        planner_output={"tool_sequence": ["run_mrs_prognosis_prediction", "icv"]},
        tool_results=[
            {
                "tool_name": "run_mrs_prognosis_prediction",
                "status": "completed",
                "structured_output": result,
            },
            {"tool_name": "run_stroke_analysis", "status": "completed", "structured_output": {}},
        ],
        patient_context={
            "expected_identifiers": {
                "patient_id": 7,
                "file_id": "case-mrs-test",
                "run_id": "run-mrs-test",
            }
        },
    )["icv"]
    mrs_findings = [item for item in icv["findings"] if item["id"].startswith("MRS_")]
    assert mrs_findings
    assert not [item for item in mrs_findings if item["status"] in {"fail", "warn"}]


def test_cockpit_refresh_recovers_same_mrs_result():
    run_id = "run-refresh-mrs"
    result = _inference("baseline")
    result.update(
        {
            "status": "completed",
            "result_mode": "baseline",
            "display_mode": "首诊初步评估",
            "fallback_used": False,
        }
    )
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=7,
        file_id="case-refresh",
        available_modalities=["ncct"],
    )

    def prepare(run):
        run["planner_output"] = {
            "imaging_path": "ncct_only",
            "tool_sequence": ["run_mrs_prognosis_prediction", "icv"],
        }
        run["steps"] = [
            {"key": "run_mrs_prognosis_prediction", "status": "completed", "attempts": 1},
            {"key": "icv", "status": "pending", "attempts": 0},
        ]
        run["tool_results"] = [
            {
                "tool_name": "run_mrs_prognosis_prediction",
                "status": "completed",
                "structured_output": result,
                "attempt": 1,
                "retryable": False,
            }
        ]

    app_module._update_agent_run(run_id, prepare)
    client = app_module.app.test_client()
    first = client.get(f"/api/cockpit/overview?run_id={run_id}").get_json()
    second = client.get(f"/api/cockpit/overview?run_id={run_id}").get_json()
    first_node = next(item for item in first["dag"]["nodes"] if item["step_key"] == "run_mrs_prognosis_prediction")
    second_node = next(item for item in second["dag"]["nodes"] if item["step_key"] == "run_mrs_prognosis_prediction")
    assert first_node["output_payload"] == second_node["output_payload"] == result


def test_current_run_mrs_result_and_tool_output_outrank_stale_report_payload():
    current = _inference("update_24h")
    current.update(
        {
            "status": "completed",
            "result_mode": "update_24h",
            "display_mode": "24小时更新评估",
        }
    )
    stale = _inference("baseline")
    stale.update(
        {
            "status": "completed",
            "result_mode": "baseline",
            "display_mode": "首诊初步评估",
        }
    )
    run = {
        "result": {
            "report_result": {
                "report_payload": {"mrs_prognosis_result": stale}
            }
        },
        "tool_results": [
            {
                "tool_name": "run_mrs_prognosis_prediction",
                "status": "completed",
                "structured_output": current,
            }
        ],
    }

    resolved = app_module._resolve_mrs_prognosis_result(run=run)

    assert resolved["result_mode"] == "update_24h"
    assert resolved["prediction"]["poor_prognosis_risk"] == 0.7


def test_report_context_uses_current_run_mrs_before_stale_report_payload(monkeypatch):
    run_id = "run-report-context-mrs"
    current = _inference("update_24h")
    current.update(
        {
            "status": "completed",
            "result_mode": "update_24h",
            "display_mode": "24小时更新评估",
        }
    )
    stale = _inference("baseline")
    stale.update(
        {
            "status": "completed",
            "result_mode": "baseline",
            "display_mode": "首诊初步评估",
        }
    )
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=7,
        file_id="case-report-context",
        available_modalities=["ncct"],
    )

    def prepare(run):
        run["result"] = {
            "mrs_prognosis_result": current,
            "report_result": {
                "report": "synthetic report",
                "report_payload": {"mrs_prognosis_result": stale},
            },
        }

    app_module._update_agent_run(run_id, prepare)
    monkeypatch.setattr(app_module, "get_patient_by_id", lambda _patient_id: {})
    monkeypatch.setattr(
        app_module,
        "get_imaging_by_case",
        lambda _patient_id, _file_id: {"analysis_result": {}},
    )

    payload = app_module.app.test_client().get(
        f"/api/report/context?run_id={run_id}"
    ).get_json()

    assert payload["success"] is True
    assert payload["report_payload"]["mrs_prognosis_result"]["result_mode"] == (
        "update_24h"
    )
    assert payload["structured_report"]["prognosis_assessment"]["prediction"][
        "poor_prognosis_risk"
    ] == 0.7


def test_historical_case_does_not_fabricate_mrs_completion(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_load_cockpit_case_report_payload",
        lambda **_kwargs: (
            {"final_report": {"summary": "legacy"}},
            {"source_chain": "test", "last_updated": "2026-08-06T00:00:00Z"},
            {"patient_id": 7, "available_modalities": ["ncct", "mcta", "vcta", "dcta"]},
            "legacy-case",
        ),
    )
    run, _events, _run_id, source = app_module._resolve_cockpit_run_and_events(
        file_id="legacy-case", patient_id=7
    )
    mrs_step = next(item for item in run["steps"] if item["key"] == "run_mrs_prognosis_prediction")
    assert source == "case"
    assert mrs_step["status"] == "unavailable"


def test_frontend_formats_null_as_dash_and_exposes_required_fields():
    processing = Path("static/js/processing.js").read_text(encoding="utf-8")
    cockpit = Path("static/js/cockpit.js").read_text(encoding="utf-8")
    processing_template = Path(
        "backend/templates/patient/upload/processing/index.html"
    ).read_text(encoding="utf-8")
    cockpit_template = Path(
        "backend/templates/patient/upload/cockpit/index.html"
    ).read_text(encoding="utf-8")
    assert 'value === null || value === undefined' in processing
    assert 'value === null || value === undefined' in cockpit
    assert "processing.js?v=20260807_mrs_display_v1" in processing_template
    assert "cockpit.js?v=20260806_mrs_compact" in cockpit_template
    for label in (
        "良好预后概率",
        "不良预后风险",
        "风险类别",
    ):
        assert label in processing
        assert label in cockpit
    for hidden_detail in (
        "前3项临床模型证据",
        "前3张NCCT模型高关注文件",
        "置信度原因：",
        "医生复核建议：",
        "研究型MVP，尚未完成外部验证。",
    ):
        assert hidden_detail not in processing
        assert hidden_detail not in cockpit


def test_optional_mrs_clinical_fields_route_without_database_schema_change():
    record, observed = mrs_prognosis.build_mrs_record(
        run={"id": "clinical-db-route", "planner_input": {"patient_id": 7}},
        patient_data={
            "patient_sex": "男",
            "patient_age": 68,
            "admission_nihss": 11,
            "nihss_24h": 7,
            "onset_to_ct_hours": 2.5,
        },
    )
    assert observed is True
    assert record["NIHSS 24 HOURS"] == 7
    assert record["onset_to_ct_hours"] == 2.5

    patient_form = Path("backend/templates/patient/index.html").read_text(encoding="utf-8")
    patient_js = Path("static/js/patient.js").read_text(encoding="utf-8")
    upload_js = Path("static/js/upload.js").read_text(encoding="utf-8")
    app_source = Path("backend/app.py").read_text(encoding="utf-8")
    for field in ("nihss_24h", "onset_to_ct_hours"):
        assert f'id="{field}"' in patient_form
        assert field in patient_js
    assert "mrs_clinical_record_${patientId}" in patient_js
    assert "formData.append('mrs_clinical_record'" in upload_js
    assert 'request.form.get("mrs_clinical_record")' in app_source


def test_online_nifti_is_normalized_to_training_input_range(tmp_path):
    nib = pytest.importorskip("nibabel")
    volume = np.stack(
        [
            np.arange(64, dtype=np.float32).reshape(8, 8),
            np.full((8, 8), 12.0, dtype=np.float32),
        ],
        axis=2,
    )
    path = tmp_path / "online_ncct.nii.gz"
    nib.save(nib.Nifti1Image(volume, np.eye(4)), str(path))
    arrays, labels, warnings = mrs_prognosis.load_nifti_ncct_slices(path)
    assert len(arrays) == len(labels) == 2
    assert arrays[0].dtype == np.float32
    assert float(arrays[0].min()) == pytest.approx(0.0)
    assert float(arrays[0].max()) == pytest.approx(1.0)
    assert np.count_nonzero(arrays[1]) == 0
    assert any("2%-98%" in warning for warning in warnings)

    single_slice_path = tmp_path / "online_single_slice_ncct.nii.gz"
    nib.save(nib.Nifti1Image(volume[:, :, 0], np.eye(4)), str(single_slice_path))
    single_arrays, single_labels, single_warnings = (
        mrs_prognosis.load_nifti_ncct_slices(single_slice_path)
    )
    assert len(single_arrays) == len(single_labels) == 1
    assert single_arrays[0].shape == (8, 8)
    assert any("single-slice 2-D" in warning for warning in single_warnings)


def test_real_baseline_bundle_result_survives_cockpit_refresh():
    manifest_path = Path("outputs/mrs_patient_manifest.csv")
    bundle_path = Path("outputs/mrs_model/mrs_baseline_mvp.pt")
    if not manifest_path.exists() or not bundle_path.exists():
        pytest.skip("real audited cohort or baseline MVP bundle is unavailable")
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        row = next(item for item in csv.DictReader(handle) if item["patient_key"] == "146")
    clinical = {
        name: row.get(name)
        for name in (
            "Gender",
            "Age",
            "Onset to CT time",
            "onset_to_ct_hours",
            "NIHSS Baseline",
            "NIHSS 24 HOURS",
        )
    }
    run_id = "real-baseline-refresh-146"
    run = {
        "id": run_id,
        "patient_id": 146,
        "file_id": "real-audit-146",
        "planner_input": {
            "patient_id": 146,
            "file_id": "real-audit-146",
            "mrs_clinical_record": clinical,
        },
    }
    result = mrs_prognosis.run_mrs_prognosis_prediction(
        run=run, patient_data={}
    )
    assert result["status"] == "completed"
    assert result["result_mode"] == "baseline"
    assert result["model"]["is_real_inference"] is True
    assert result["model"]["production_approved"] is False

    app_module._create_agent_run(
        run_id=run_id,
        patient_id=146,
        file_id="real-audit-146",
        available_modalities=["ncct"],
    )

    def prepare(stored):
        stored["planner_output"] = {
            "imaging_path": "ncct_only",
            "tool_sequence": ["run_mrs_prognosis_prediction", "icv"],
        }
        stored["steps"] = [
            {"key": "run_mrs_prognosis_prediction", "status": "completed", "attempts": 1},
            {"key": "icv", "status": "pending", "attempts": 0},
        ]
        stored["tool_results"] = [
            {
                "tool_name": "run_mrs_prognosis_prediction",
                "status": "completed",
                "structured_output": result,
                "attempt": 1,
                "retryable": False,
            }
        ]

    app_module._update_agent_run(run_id, prepare)
    client = app_module.app.test_client()
    first = client.get(f"/api/cockpit/overview?run_id={run_id}").get_json()
    second = client.get(f"/api/cockpit/overview?run_id={run_id}").get_json()
    first_node = next(
        node for node in first["dag"]["nodes"]
        if node["step_key"] == "run_mrs_prognosis_prediction"
    )
    second_node = next(
        node for node in second["dag"]["nodes"]
        if node["step_key"] == "run_mrs_prognosis_prediction"
    )
    assert first_node["output_payload"] == second_node["output_payload"] == result


def test_patient_insert_retries_legacy_schema_without_losing_current_flow(monkeypatch):
    submitted = []

    class FakeResponse:
        def __init__(self, data):
            self.data = data

    class FakeTable:
        def __init__(self):
            self.payload = None

        def insert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            row = dict(self.payload[0])
            submitted.append(row)
            if "nihss_24h" in row:
                raise RuntimeError(
                    "PGRST204 Could not find the 'nihss_24h' column of "
                    "'patient_info' in the schema cache"
                )
            return FakeResponse([{"id": 901, **row}])

    class FakeSupabase:
        def table(self, name):
            assert name == "patient_info"
            return FakeTable()

    monkeypatch.setattr(app_module, "SUPABASE_AVAILABLE", True)
    monkeypatch.setattr(app_module, "supabase", FakeSupabase())
    success, result = app_module.insert_patient_info(
        {
            "patient_name": "schema-fallback",
            "admission_nihss": 10,
            "nihss_24h": 4,
            "onset_to_ct_hours": 2.0,
            "create_time": "ignored",
        }
    )
    assert success is True
    assert result["id"] == 901
    assert result["nihss_24h"] == 4
    assert result["onset_to_ct_hours"] == 2.0
    assert result["_clinical_schema_fallback"] is True
    assert len(submitted) == 2
    assert "nihss_24h" not in submitted[1]
    assert "onset_to_ct_hours" not in submitted[1]


def test_schema_fallback_clinical_values_are_carried_into_agent_run():
    record = {
        "patient_sex": "女",
        "patient_age": 21,
        "admission_nihss": 10,
        "nihss_24h": 4,
        "onset_to_ct_hours": 10.0,
    }
    run = app_module._create_agent_run(
        run_id="schema-fallback-agent",
        patient_id=901,
        file_id="schema-fallback-case",
        available_modalities=["ncct"],
        mrs_clinical_record=record,
    )
    assert run["planner_input"]["mrs_clinical_record"] == record
    patient_js = Path("static/js/patient.js").read_text(encoding="utf-8")
    upload_js = Path("static/js/upload.js").read_text(encoding="utf-8")
    assert "mrs_clinical_record_${patientId}" in patient_js
    assert "mrs_clinical_record_${patientId}" in upload_js
    assert "formData.append('mrs_clinical_record'" in upload_js
