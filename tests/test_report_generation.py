import json
import queue
import threading

import pytest
import requests

from backend import report_generation
from backend.workers import report_worker


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _structured():
    return {
        "id": "patient-123",
        "patient_id": "patient-123",
        "patient_name": "测试患者甲",
        "patient_age": 68,
        "patient_sex": "女",
        "admission_nihss": 12,
        "onset_to_admission_hours": 3.5,
        "hemisphere": "left",
        "question": "请回答测试患者甲 patient-123 的取栓风险",
        "three_class_status": "completed",
        "three_class_label": "ischemic",
        "three_class_label_cn": "缺血性卒中",
        "three_class_confidence": 0.91,
        "vessel_occlusion_result": {
            "status": "completed",
            "vessel_occlusion_class_result": "large_vessel_occlusion",
            "predicted_class": "Class_1_LVO",
            "confidence": 0.82,
            "valid_predictions": 1,
            "class_counts": {"Class_0": 0, "Class_1_LVO": 1, "Class_2_MEVO": 0},
        },
    }


def _imaging():
    return {
        "available_modalities": ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"],
        "analysis_result": {
            "core_volume_ml": 6.14,
            "penumbra_volume_ml": 17.21,
            "mismatch_ratio": 2.8,
        },
    }


def test_baichuan_request_is_deidentified_and_contains_clinical_evidence(tmp_path):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "结构化报告正文"}}]})

    result = report_generation.generate_report(
        _structured(),
        _imaging(),
        "case-secret-456",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=fake_post,
    )

    assert result["success"] is True
    outbound = json.dumps(captured["json"], ensure_ascii=False)
    assert "测试患者甲" not in outbound
    assert "patient-123" not in outbound
    assert "case-secret-456" not in outbound
    assert "E:\\" not in outbound
    assert "6.14" in outbound
    assert "17.21" in outbound
    assert "2.8" in outbound
    assert "缺血性卒中" in outbound
    assert "large_vessel_occlusion" in outbound
    assert "[已去标识]" in outbound
    assert "测试患者甲" in result["report"]
    assert "patient-123" in result["report"]
    assert result["report_payload"]["provider"] == "baichuan_m3"
    assert result["report_payload"]["is_mock"] is False
    assert result["json_path"].startswith(str(tmp_path))


def test_quality_control_risks_and_override_reach_prompt_and_payload(tmp_path):
    captured = {}
    imaging = _imaging()
    imaging["analysis_result"]["quality_control"] = {
        "schema_version": "1.0",
        "qc_status": "failed",
        "qc_score": 0.72,
        "qc_method": "rule_based_nifti_qc",
        "qc_input_mode": "volume",
        "qc_not_applicable_checks": [],
        "qc_scan_coverage": "complete",
        "qc_slice_thickness_status": "normal",
        "qc_motion_artifact_level": "severe",
        "qc_missing_slice_status": "none_suspected",
        "qc_geometry_status": "matched",
        "findings": [
            {
                "code": "suspected_motion_artifact_severe",
                "severity": "high",
                "modality": "ncct",
                "metric": 0.3,
                "threshold": 0.25,
                "message": "疑似严重运动伪影",
                "overrideable": True,
            }
        ],
        "review_override": {
            "decision": "accept_risk",
            "reviewer": "doctor-local",
            "comment": "synthetic review",
        },
    }

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "质控风险报告"}}]})

    result = report_generation.generate_report(
        _structured(),
        imaging,
        "case-quality",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=fake_post,
    )
    outbound = json.dumps(captured["json"], ensure_ascii=False)
    assert "suspected_motion_artifact_severe" in outbound
    assert "accept_risk" in outbound
    assert '"qc_input_mode":"volume"' in captured["json"]["messages"][1]["content"]
    assert "doctor-local" not in outbound
    assert "synthetic review" not in outbound
    assert "case-quality" not in outbound
    assert result["report_payload"]["quality_control_result"]["qc_status"] == "failed"
    assert result["report_payload"]["quality_control_result"]["review_override"]["decision"] == "accept_risk"


def test_single_slice_quality_limit_is_preserved_in_prompt_and_payload(tmp_path):
    captured = {}
    imaging = _imaging()
    imaging["analysis_result"]["quality_control"] = {
        "schema_version": "1.0",
        "qc_status": "warning",
        "qc_score": 0.92,
        "qc_method": "rule_based_nifti_qc",
        "qc_input_mode": "single_slice",
        "qc_not_applicable_checks": [
            "axial_coverage",
            "internal_missing_slices",
            "inter_slice_motion",
        ],
        "qc_scan_coverage": "not_applicable",
        "qc_slice_thickness_status": "normal",
        "qc_motion_artifact_level": "not_applicable",
        "qc_missing_slice_status": "not_applicable",
        "qc_geometry_status": "matched",
        "findings": [
            {
                "code": "single_slice_limited_assessment",
                "severity": "medium",
                "message": "单层影像无法执行三维覆盖、疑似缺片及跨层运动评估",
            }
        ],
    }

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "单层质控报告"}}]})

    result = report_generation.generate_report(
        _structured(),
        imaging,
        "case-single-slice",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=fake_post,
    )
    prompt = captured["json"]["messages"][1]["content"]
    assert '"qc_input_mode":"single_slice"' in prompt
    assert "single_slice_limited_assessment" in prompt
    assert "inter_slice_motion" in prompt
    assert (
        result["report_payload"]["quality_control_result"]["qc_scan_coverage"]
        == "not_applicable"
    )


def test_hemorrhage_gate_removes_ctp_values_from_provider_prompt(tmp_path):
    captured = {}
    structured = _structured()
    structured.update(
        {
            "three_class_label": "hemo",
            "three_class_label_cn": "脑出血",
            "three_class_result": {
                "status": "completed",
                "three_class_label": "hemo",
                "three_class_label_cn": "脑出血",
                "three_class_confidence": 0.77,
                "safety_gate": {
                    "blocked": True,
                    "reason_code": "NCCT_SUSPECTED_HEMORRHAGE",
                    "reason": "NCCT 三分类提示疑似脑出血，已阻断后续 AIS/灌注分析",
                    "requires_clinician_review": True,
                },
            },
        }
    )

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "安全报告"}}]})

    result = report_generation.generate_report(
        structured,
        _imaging(),
        "case-gated",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=fake_post,
    )

    prompt = captured["json"]["messages"][-1]["content"]
    assert result["success"] is True
    assert result["report_payload"]["sections"]["ctp"]["enabled"] is False
    assert result["report_payload"]["sections"]["ctp"]["status"] == "skipped"
    assert result["report_payload"]["safety_gate"]["blocked"] is True
    assert '"core_infarct_volume_ml":null' in prompt
    assert '"penumbra_volume_ml":null' in prompt
    assert '"mismatch_ratio":null' in prompt


@pytest.mark.parametrize(
    "response_payload",
    [
        {"choices": [{"message": {"content": "choices content"}}]},
        {"content": "top-level content"},
        {"data": {"content": "data content"}},
    ],
)
def test_supported_baichuan_response_shapes(response_payload, tmp_path):
    result = report_generation.generate_report(
        _structured(),
        _imaging(),
        "case-a",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=lambda *_args, **_kwargs: FakeResponse(response_payload),
    )
    assert result["success"] is True
    assert result["is_mock"] is False
    assert result["report_payload"]["sections"]["ctp"]["enabled"] is True


def test_missing_key_uses_explicit_local_fallback_without_network(tmp_path):
    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    result = report_generation.generate_report(
        _structured(),
        _imaging(),
        "case-a",
        output_format="json",
        results_dir=str(tmp_path),
        api_key="",
        http_post=fail_if_called,
    )

    assert result["success"] is True
    assert called is False
    assert result["is_mock"] is True
    assert result["warning"]
    parsed = json.loads(result["report"])
    assert parsed["patient_id"] == "patient-123"
    assert parsed["patient_name"] == "测试患者甲"
    assert result["report_payload"]["provider"] == "local_fallback"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse({}, 503), "HTTP 503"),
        (FakeResponse({"choices": [{"message": {"content": ""}}]}), "空报告"),
    ],
)
def test_api_failures_do_not_fall_back(response, expected, tmp_path):
    result = report_generation.generate_report(
        _structured(),
        _imaging(),
        "case-a",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=lambda *_args, **_kwargs: response,
    )
    assert result["success"] is False
    assert expected in result["error"]
    assert list(tmp_path.glob("*.json")) == []


def test_timeout_does_not_fall_back(tmp_path):
    def timeout(*_args, **_kwargs):
        raise requests.exceptions.Timeout()

    result = report_generation.generate_report(
        _structured(),
        _imaging(),
        "case-a",
        results_dir=str(tmp_path),
        api_key="test-key",
        http_post=timeout,
    )
    assert result["success"] is False
    assert "超时" in result["error"]
    assert list(tmp_path.glob("*.json")) == []


def test_worker_keeps_queue_contract_and_uses_generic_generator(monkeypatch):
    request_queue = queue.Queue()
    response_queue = queue.Queue()
    monkeypatch.setattr(
        report_worker,
        "generate_report",
        lambda **kwargs: {
            "success": True,
            "format": kwargs["output_format"],
            "report": "ok",
            "report_payload": {},
            "json_path": "report.json",
            "is_mock": False,
            "warning": None,
        },
    )
    request_queue.put(
        {
            "type": "generate_report",
            "task_id": "task-1",
            "structured_data": {},
            "imaging_data": {},
            "file_id": "case-a",
            "output_format": "markdown",
        }
    )
    request_queue.put({"type": "shutdown"})

    worker = threading.Thread(
        target=report_worker.report_worker_entry,
        args=(request_queue, response_queue),
    )
    worker.start()
    worker.join(timeout=2)
    response = response_queue.get_nowait()
    assert response["task_id"] == "task-1"
    assert response["ok"] is True
    assert response["result"]["report"] == "ok"
