import hashlib
import json
from pathlib import Path

from scripts import repair_ncct_perfusion_reports as repair


def _source_document():
    return {
        "meta": {"file_id": "case-a"},
        "report_payload": {
            "patient_id": 1,
            "patient_age": 60,
            "patient_sex": "female",
            "modalities": ["ncct", "mcta", "vcta", "dcta"],
            "core_infarct_volume": 6.14,
            "penumbra_volume": 17.21,
            "mismatch_ratio": 2.8,
            "review_state": {
                "all_confirmed": True,
                "confirmed_count": 1,
                "sections": [
                    {
                        "section_id": "imaging_summary",
                        "review_status": "confirmed",
                        "doctor_note": "保留备注",
                    }
                ],
            },
            "structured_report_v2": {
                "imaging_findings": [
                    {
                        "finding_id": "ncct_classification",
                        "status": "missing",
                        "value": None,
                    },
                    {
                        "finding_id": "perfusion_analysis",
                        "status": "completed",
                        "value": None,
                    },
                ],
                "quantitative_metrics": [
                    {
                        "metric_id": "core_infarct_volume",
                        "value": 6.14,
                    }
                ],
            },
        },
    }


def _three_class_result():
    return {
        "status": "completed",
        "three_class_label": "normal",
        "three_class_label_cn": "正常",
        "three_class_confidence": 0.8,
        "class_counts": {"normal": 1, "hemo": 0, "infarct": 0},
        "total_slices": 1,
        "safety_gate": {
            "blocked": False,
            "reason_code": None,
            "reason": None,
            "requires_clinician_review": False,
        },
    }


def test_repair_is_dry_run_by_default_and_apply_is_idempotent(
    tmp_path, monkeypatch
):
    source = tmp_path / "baichuan_report_case-a_20260728_120000_000001.json"
    source.write_text(
        json.dumps(_source_document(), ensure_ascii=False), encoding="utf-8"
    )
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = {"generate": 0}

    monkeypatch.setattr(
        repair, "_prediction_result", lambda _file_id: _three_class_result()
    )
    monkeypatch.setenv("BAICHUAN_API_KEY", "test-key")

    def fake_generate_report(**kwargs):
        calls["generate"] += 1
        result_path = (
            Path(kwargs["results_dir"])
            / "baichuan_report_case-a_20260728_130000_000001.json"
        )
        payload = dict(kwargs["structured_data"])
        result_path.write_text(
            json.dumps(
                {
                    "meta": {"file_id": "case-a"},
                    "report": "repaired",
                    "report_payload": payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {
            "success": True,
            "is_mock": False,
            "report": "repaired",
            "report_payload": payload,
            "json_path": str(result_path),
        }

    monkeypatch.setattr(repair, "generate_report", fake_generate_report)
    monkeypatch.setattr(
        repair, "_sync_supabase", lambda *_args: (True, "updated")
    )

    dry_run = repair.run(apply=False, skip_db_sync=False, report_dir=tmp_path)
    assert dry_run["affected"] == 1
    assert dry_run["eligible"] == 1
    assert dry_run["created"] == 0
    assert calls["generate"] == 0

    applied = repair.run(apply=True, skip_db_sync=False, report_dir=tmp_path)
    assert applied["created"] == 1
    assert applied["db_synced"] == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha

    repaired_files = [
        path
        for path in tmp_path.glob("*.json")
        if path != source
    ]
    assert len(repaired_files) == 1
    repaired = json.loads(repaired_files[0].read_text(encoding="utf-8"))
    payload = repaired["report_payload"]
    assert payload["repair_meta"]["source_sha256"] == source_sha
    assert payload["review_state"]["all_confirmed"] is False
    assert payload["review_state"]["sections"][0]["review_status"] == "pending"
    assert payload["review_state"]["sections"][0]["doctor_note"] == "保留备注"

    rerun = repair.run(apply=True, skip_db_sync=False, report_dir=tmp_path)
    assert rerun["already_repaired"] == 1
    assert rerun["created"] == 0
    assert calls["generate"] == 1
