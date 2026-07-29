"""Rebuild reports affected by the NCCT propagation and perfusion-card bugs.

The command is dry-run by default.  Use ``--apply`` to create new report
versions.  Existing report files are never modified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.report_generation import generate_report  # noqa: E402
from backend.summary_assembler import build_summary_artifacts  # noqa: E402
from backend.three_class.result import (  # noqa: E402
    aggregate_three_class_predictions,
)


REPAIR_VERSION = "ncct-perfusion-v1"
REPORT_NAME_RE = re.compile(
    r"(?:baichuan|medgemma)_report_(.+?)_\d{8}_\d{6}(?:_\d+)?\.json$"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("report JSON root must be an object")
    return value


def _payload(document: Dict[str, Any]) -> Dict[str, Any]:
    nested = document.get("report_payload")
    return nested if isinstance(nested, dict) else document


def _affected_flags(payload: Dict[str, Any]) -> Tuple[bool, bool]:
    structured = payload.get("structured_report_v2")
    if not isinstance(structured, dict):
        return False, False
    findings = structured.get("imaging_findings") or []
    metrics = structured.get("quantitative_metrics") or []
    ncct = next(
        (
            item
            for item in findings
            if isinstance(item, dict)
            and item.get("finding_id") == "ncct_classification"
        ),
        None,
    )
    perfusion = next(
        (
            item
            for item in findings
            if isinstance(item, dict)
            and item.get("finding_id") == "perfusion_analysis"
        ),
        None,
    )
    ncct_missing = bool(
        ncct
        and (
            str(ncct.get("status") or "").lower() in {"missing", "unavailable"}
            or not ncct.get("value")
        )
    )
    has_metrics = any(
        isinstance(item, dict)
        and item.get("metric_id")
        in {"core_infarct_volume", "penumbra_volume", "mismatch_ratio"}
        and item.get("value") is not None
        for item in metrics
    )
    perfusion_empty = bool(
        perfusion
        and str(perfusion.get("status") or "").lower() == "completed"
        and not perfusion.get("value")
        and has_metrics
    )
    return ncct_missing, perfusion_empty


def _file_id(path: Path, document: Dict[str, Any]) -> Optional[str]:
    meta = document.get("meta") if isinstance(document.get("meta"), dict) else {}
    candidate = str(meta.get("file_id") or "").strip()
    if not candidate:
        match = REPORT_NAME_RE.match(path.name)
        candidate = match.group(1) if match else ""
    if not candidate or not re.fullmatch(r"[A-Za-z0-9_.-]+", candidate):
        return None
    return candidate


def _prediction_result(file_id: str) -> Dict[str, Any]:
    path = (
        PROJECT_ROOT
        / "static"
        / "processed"
        / file_id
        / "stroke_analysis"
        / "three_class_predictions.json"
    )
    document = _load_json(path)
    return aggregate_three_class_predictions(
        document.get("predictions") or [],
        document.get("class_names"),
    )


def _reset_review_state(payload: Dict[str, Any]) -> None:
    state = payload.get("review_state")
    if not isinstance(state, dict):
        return
    state = copy.deepcopy(state)
    sections = [
        item for item in (state.get("sections") or []) if isinstance(item, dict)
    ]
    for item in sections:
        item["review_status"] = "pending"
        item["clinician_confirmed"] = False
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["sections"] = sections
    state["all_confirmed"] = False
    state["confirmed_count"] = 0
    state["pending_count"] = len(sections)
    state["current_section_id"] = (
        str(sections[0].get("section_id") or "") if sections else None
    )
    payload["review_state"] = state
    payload.pop("final_confirmed_report", None)
    payload.pop("review_finalized_at", None)


def _structured_inputs(
    old_payload: Dict[str, Any],
    three_class_result: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    structured = copy.deepcopy(old_payload)
    if three_class_result:
        structured["three_class_result"] = copy.deepcopy(three_class_result)
        structured["three_class_status"] = three_class_result.get("status")
        for key in (
            "three_class_label",
            "three_class_label_cn",
            "three_class_confidence",
            "safety_gate",
        ):
            structured[key] = copy.deepcopy(three_class_result.get(key))
    analysis = {
        "core_volume_ml": old_payload.get("core_infarct_volume"),
        "penumbra_volume_ml": old_payload.get("penumbra_volume"),
        "mismatch_ratio": old_payload.get("mismatch_ratio"),
    }
    if three_class_result:
        analysis["three_class_result"] = copy.deepcopy(three_class_result)
    imaging = {
        "available_modalities": old_payload.get("modalities") or [],
        "hemisphere": old_payload.get("hemisphere"),
        "analysis_result": analysis,
    }
    return structured, imaging


def _write_repaired_document(
    result_path: Path,
    report_payload: Dict[str, Any],
    source_path: Path,
    source_sha256: str,
) -> str:
    document = _load_json(result_path)
    repair_meta = {
        "version": REPAIR_VERSION,
        "source_sha256": source_sha256,
        "source_name_sha256": hashlib.sha256(
            source_path.name.encode("utf-8")
        ).hexdigest(),
        "repaired_at": datetime.now(timezone.utc).isoformat(),
        "review_reset": True,
    }
    report_payload["repair_meta"] = repair_meta
    document["report_payload"] = report_payload
    document["structured_report_v2"] = report_payload.get("structured_report_v2")
    document["repair_meta"] = repair_meta
    temp_path = result_path.with_suffix(result_path.suffix + ".repair.tmp")
    temp_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(str(temp_path), str(result_path))
    _load_json(result_path)
    return _sha256(result_path)


def _sync_supabase(
    file_id: str, patient_id: Any, report_payload: Dict[str, Any]
) -> Tuple[bool, str]:
    url = str(os.environ.get("SUPABASE_URL") or "").strip()
    key = str(os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not url or not key:
        return False, "credentials_missing"
    try:
        from supabase import create_client

        query = create_client(url, key).table("patient_imaging").update(
            {"report_payload": report_payload}
        ).eq("case_id", file_id)
        if patient_id not in (None, ""):
            query = query.eq("patient_id", patient_id)
        response = query.execute()
        if response.data:
            return True, "updated"
        return False, "row_not_found"
    except Exception as exc:
        return False, type(exc).__name__


def _existing_repair_sources(report_dir: Path) -> set[str]:
    repaired: set[str] = set()
    for path in report_dir.rglob("*.json"):
        try:
            document = _load_json(path)
        except Exception:
            continue
        meta = document.get("repair_meta")
        if not isinstance(meta, dict):
            meta = _payload(document).get("repair_meta")
        if (
            isinstance(meta, dict)
            and meta.get("version") == REPAIR_VERSION
            and meta.get("source_sha256")
        ):
            repaired.add(str(meta["source_sha256"]))
    return repaired


def run(*, apply: bool, skip_db_sync: bool, report_dir: Path) -> Dict[str, int]:
    stats = {
        "json_files": 0,
        "invalid_json": 0,
        "affected": 0,
        "already_repaired": 0,
        "eligible": 0,
        "created": 0,
        "failed": 0,
        "db_synced": 0,
        "db_sync_failed": 0,
    }
    repaired_sources = _existing_repair_sources(report_dir)
    candidates = list(report_dir.rglob("*.json"))
    stats["json_files"] = len(candidates)
    for source_path in candidates:
        try:
            source_document = _load_json(source_path)
        except Exception:
            stats["invalid_json"] += 1
            continue
        old_payload = _payload(source_document)
        ncct_missing, perfusion_empty = _affected_flags(old_payload)
        if not (ncct_missing or perfusion_empty):
            continue
        stats["affected"] += 1
        source_sha256 = _sha256(source_path)
        if source_sha256 in repaired_sources:
            stats["already_repaired"] += 1
            continue
        file_id = _file_id(source_path, source_document)
        if not file_id:
            stats["failed"] += 1
            continue
        try:
            three_class_result = (
                _prediction_result(file_id)
                if ncct_missing
                else copy.deepcopy(old_payload.get("three_class_result"))
            )
        except Exception:
            stats["failed"] += 1
            continue
        stats["eligible"] += 1
        if not apply:
            continue
        api_key = str(os.environ.get("BAICHUAN_API_KEY") or "").strip()
        if not api_key:
            stats["failed"] += 1
            continue
        structured, imaging = _structured_inputs(old_payload, three_class_result)
        generated = generate_report(
            structured_data=structured,
            imaging_data=imaging,
            file_id=file_id,
            output_format="markdown",
            results_dir=str(report_dir),
            api_key=api_key,
        )
        if not generated.get("success") or generated.get("is_mock"):
            stats["failed"] += 1
            continue
        result_path = Path(str(generated.get("json_path") or ""))
        try:
            if not result_path.is_file():
                raise FileNotFoundError("generated report JSON missing")
            new_payload = copy.deepcopy(generated.get("report_payload") or {})
            for key in ("notes", "report_notes", "doctor_notes", "review_state"):
                if key in old_payload:
                    new_payload[key] = copy.deepcopy(old_payload[key])
            _reset_review_state(new_payload)
            new_payload = build_summary_artifacts(
                run_id=f"repair:{REPAIR_VERSION}",
                file_id=file_id,
                report_payload=new_payload,
                icv=old_payload.get("icv"),
                ekv=old_payload.get("ekv"),
                consensus=old_payload.get("consensus"),
                goal_question="",
                patient_context=structured,
            )
            _write_repaired_document(
                result_path, new_payload, source_path, source_sha256
            )
        except Exception:
            try:
                if (
                    result_path.is_file()
                    and report_dir in result_path.resolve().parents
                ):
                    result_path.unlink()
            except Exception:
                pass
            stats["failed"] += 1
            continue
        stats["created"] += 1
        repaired_sources.add(source_sha256)
        if skip_db_sync:
            continue
        db_ok, _ = _sync_supabase(
            file_id, old_payload.get("patient_id"), new_payload
        )
        if db_ok:
            stats["db_synced"] += 1
        else:
            stats["db_sync_failed"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create repaired report versions; default is dry-run",
    )
    parser.add_argument(
        "--skip-db-sync",
        action="store_true",
        help="create local versions without updating Supabase",
    )
    parser.add_argument(
        "--report-dir",
        default=str(PROJECT_ROOT / "runtime" / "reports"),
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except Exception:
        pass

    stats = run(
        apply=bool(args.apply),
        skip_db_sync=bool(args.skip_db_sync),
        report_dir=Path(args.report_dir).resolve(),
    )
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 1 if args.apply and stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
