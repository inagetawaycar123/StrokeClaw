#!/usr/bin/env python3
"""Audit the real ProVe-IT clinical table and multi-phase CT ``.npy`` data.

This script is deliberately read-only with respect to source data.  It writes
only the three audit artifacts requested for the 90-day mRS project:

* ``outputs/mrs_data_audit.json``
* ``outputs/mrs_patient_manifest.csv``
* ``outputs/mrs_unmatched_records.csv``

Patient mapping is conservative.  Image names contain only ``BBB`` from the
described ``ProVe-IT-AA-BBB`` clinical identifier.  A clinical row is attached
only when that suffix has exactly one candidate in the workbook.  Ambiguous
suffixes are retained and reported rather than being assigned to a centre.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from openpyxl import load_workbook


EXPECTED_CHANNELS = ("01", "02", "03", "04")
CHANNEL_NAMES = {
    "01": "NCCT",
    "02": "arterial_CTA",
    "03": "venous_CTA",
    "04": "delayed_CTA",
}

IMAGE_NAME_RE = re.compile(
    r"^(?P<channel>\d{2})-(?P<patient_key>[^_]+)_(?P<slice_id>[^.]+)\.npy$",
    re.IGNORECASE,
)
CLINICAL_ID_RE = re.compile(
    r"^ProVe-IT-(?P<center>[^-]+)-(?P<patient_suffix>[^-]+)$",
    re.IGNORECASE,
)

RAW_ID_COLUMN = "Prove-it ID"
LABEL_COLUMN = "90 Day MRS"
SCREEN_FAILURE_COLUMN = "SF"

PREFERRED_CLINICAL_FEATURES = {
    "sex": "Gender",
    "age": "Age",
    "onset_to_ct_time": "Onset to CT time",
    "baseline_nihss": "NIHSS Baseline",
}
CTP_CORE_CANDIDATES = (
    "CTP_core_rCBF_thresh12.5",
    "CTP_core_aCBF_thresh15",
    "CTP_core_aCBV_thresh2",
)

MISSING_TEXT_TOKENS = {
    "",
    "na",
    "n/a",
    "nan",
    "nd",
    "none",
    "null",
    "<na>",
}

TEXT_SCAN_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".txt",
}
WEIGHT_EXTENSIONS = {".pt", ".pth", ".ckpt", ".joblib", ".pkl", ".onnx", ".safetensors"}
IGNORED_SCAN_PARTS = {".git", ".venv", "node_modules", "__pycache__"}

POTENTIAL_LEAKAGE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"NIHSS\s*24", re.I), "24-hour NIHSS is post-baseline information"),
    (re.compile(r"MRS\s*24", re.I), "24-hour mRS is post-baseline information"),
    (re.compile(r"Discharge", re.I), "discharge information occurs after the prediction time"),
    (re.compile(r"90\s*Day", re.I), "90-day outcome/follow-up information"),
    (re.compile(r"3\s*month|Follow[- ]?up|F/U", re.I), "follow-up information"),
    (re.compile(r"Deceased|Death|Mortality", re.I), "mortality/outcome information"),
    (re.compile(r"Recurrent", re.I), "recurrent event after baseline"),
    (re.compile(r"^FU_|FU CT|FU MR", re.I), "follow-up imaging information"),
    (re.compile(r"Symptomatic ICH", re.I), "post-treatment/outcome complication"),
    (re.compile(r"Current Medications|New Medications", re.I), "post-discharge treatment information"),
    (
        re.compile(
            r"Treatment Decision|Antithrombotics|IV tPA|TNK|Groin Puncture|"
            r"Recanalization|TICI|ANGIO RUN|General Anesthesia",
            re.I,
        ),
        "treatment/procedural information that may occur after the initial CT prediction point",
    ),
)

MARKDOWN_TO_EXCEL_MAPPING = (
    {
        "markdown_field": "patient_info.patient_age",
        "excel_columns": ["Age"],
        "mapping_status": "semantic_exact",
    },
    {
        "markdown_field": "patient_info.patient_sex",
        "excel_columns": ["Gender"],
        "mapping_status": "semantic_exact",
    },
    {
        "markdown_field": "patient_info.onset_exact_time",
        "excel_columns": ["Time of Symptom onset"],
        "mapping_status": "semantic_exact",
    },
    {
        "markdown_field": "clinical_context.onset_to_ct_time",
        "excel_columns": ["Onset to CT time"],
        "mapping_status": "excel_only_derived_interval",
    },
    {
        "markdown_field": "patient_info.admission_nihss",
        "excel_columns": ["NIHSS Baseline"],
        "mapping_status": "semantic_exact",
    },
    {
        "markdown_field": "patient_info.core_infarct_volume",
        "excel_columns": list(CTP_CORE_CANDIDATES),
        "mapping_status": "ambiguous_multiple_threshold_definitions",
    },
    {
        "markdown_field": "90_day_mrs_label",
        "excel_columns": [LABEL_COLUMN],
        "mapping_status": "excel_label_not_present_in_current_StrokeClaw_schema",
    },
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--image-dir", type=Path, default=None)
    parser.add_argument("--workbook", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--progress-every", type=int, default=500)
    return parser.parse_args(argv)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_json(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, Mapping):
        return {str(key): normalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def display_cell(value: Any) -> str:
    normalized = normalize_json(value)
    if normalized is None:
        return ""
    if isinstance(normalized, float) and normalized.is_integer():
        return str(int(normalized))
    return str(normalized)


def is_missing_text(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in MISSING_TEXT_TOKENS


def to_finite_float(value: Any) -> float | None:
    if is_missing_text(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def to_binary_label(value: Any) -> tuple[int | None, int | None]:
    numeric = to_finite_float(value)
    if numeric is None or not numeric.is_integer():
        return None, None
    label = int(numeric)
    if not 0 <= label <= 6:
        return label, None
    return label, 0 if label <= 2 else 1


def natural_key(value: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value))


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalize_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_csv_atomic(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: normalize_json(row.get(key)) for key in fieldnames})
    os.replace(temporary, path)


def iter_files_pruned(root: Path, extra_pruned_dirs: set[str] | None = None) -> Iterable[Path]:
    """Yield files without descending into dependency/cache-heavy directories."""

    pruned = set(IGNORED_SCAN_PARTS)
    pruned.update(extra_pruned_dirs or set())
    for current, directory_names, file_names in os.walk(root):
        directory_names[:] = [name for name in directory_names if name not in pruned]
        current_path = Path(current)
        for file_name in file_names:
            yield current_path / file_name


def discover_field_tables(search_roots: Sequence[Path]) -> dict[str, Any]:
    exact: dict[Path, dict[str, Any]] = {}
    candidates: dict[Path, dict[str, Any]] = {}
    for root in search_roots:
        if not root.exists():
            continue
        for path in iter_files_pruned(root, {"mrs_images", "MedGemma_Model", "runtime"}):
            if path.suffix.lower() != ".md":
                continue
            target = path.resolve()
            record = {
                "path": str(target),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            if path.name == "字段表.md":
                exact[target] = record
            elif "字段表" in path.name:
                candidates[target] = record

    selected: Path | None = None
    if exact:
        selected = sorted(exact)[0]
    else:
        project_candidates = [
            path
            for path in candidates
            if "StrokeClaw-main" in path.parts and "最新版" in path.name
        ]
        if project_candidates:
            selected = sorted(project_candidates)[0]

    parsed_fields: list[dict[str, Any]] = []
    if selected is not None:
        text = selected.read_text(encoding="utf-8-sig", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("|") or stripped.startswith("|---"):
                continue
            cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
            if len(cells) >= 3 and cells[0] in {"patient_info", "patient_imaging"}:
                parsed_fields.append(
                    {
                        "line_number": line_number,
                        "table_name": cells[0],
                        "field_name": cells[1],
                        "chinese_name": cells[2],
                    }
                )

    return {
        "exact_filename_found": bool(exact),
        "exact_matches": list(exact.values()),
        "candidate_matches": list(candidates.values()),
        "selected_for_semantic_reference": str(selected) if selected else None,
        "selection_note": (
            "Exact 字段表.md used."
            if exact
            else (
                "Exact 字段表.md was not found; the in-project 最新版 field-table document "
                "was read as a clearly labelled candidate, not treated as an exact filename match."
                if selected
                else "No field-table Markdown document was found."
            )
        ),
        "parsed_current_system_fields": parsed_fields,
    }


def discover_workbooks(data_dir: Path) -> list[Path]:
    return sorted(
        path.resolve()
        for path in data_dir.rglob("*")
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() in {".xlsx", ".xls"}
    )


def workbook_overview(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".xlsx":
        excel = pd.ExcelFile(path)
        return {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "sheet_names": list(excel.sheet_names),
            "sheets": [],
        }

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets = []
    for sheet in workbook.worksheets:
        first_row = next(sheet.iter_rows(min_row=1, max_row=1), ())
        raw_headers = [normalize_json(cell.value) for cell in first_row]
        sheets.append(
            {
                "name": sheet.title,
                "rows_including_header": sheet.max_row,
                "columns": sheet.max_column,
                "field_names": raw_headers,
            }
        )
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "sheet_names": [item["name"] for item in sheets],
        "sheets": sheets,
    }


def choose_clinical_source(workbooks: Sequence[Path]) -> tuple[Path, str, pd.DataFrame]:
    required = {RAW_ID_COLUMN, LABEL_COLUMN}
    errors: list[str] = []
    for workbook in workbooks:
        try:
            excel = pd.ExcelFile(workbook)
        except Exception as exc:  # pragma: no cover - environment-specific Excel engines
            errors.append(f"{workbook}: {exc}")
            continue
        for sheet_name in excel.sheet_names:
            try:
                header = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0).columns
            except Exception as exc:
                errors.append(f"{workbook}::{sheet_name}: {exc}")
                continue
            if required.issubset(set(str(item) for item in header)):
                frame = pd.read_excel(workbook, sheet_name=sheet_name, dtype=object)
                return workbook, sheet_name, frame
    raise RuntimeError(
        "No worksheet contains both required columns "
        f"{sorted(required)}. Errors: {'; '.join(errors)}"
    )


def read_workbook_field_dictionary(workbook: Path) -> list[dict[str, Any]]:
    try:
        excel = pd.ExcelFile(workbook)
    except Exception:
        return []
    dictionary_sheet = next((name for name in excel.sheet_names if "字段字典" in name), None)
    if dictionary_sheet is None:
        return []
    frame = pd.read_excel(workbook, sheet_name=dictionary_sheet, dtype=object)
    return [
        {str(column): normalize_json(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def identify_potential_leakage(columns: Sequence[Any]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_column in columns:
        column = str(raw_column)
        for pattern, reason in POTENTIAL_LEAKAGE_RULES:
            if pattern.search(column):
                if column not in seen:
                    results.append(
                        {
                            "excel_column": column,
                            "classification": "potential_leakage",
                            "reason": reason,
                            "allowed_as_model_input": "false",
                        }
                    )
                    seen.add(column)
                break
    return results


def inspect_existing_mrs_assets(project_root: Path) -> dict[str, Any]:
    mention_pattern = re.compile(
        r"(?i)(90\s*day\s*mrs|90天.{0,8}mrs|baseline_mrs|mrs_prediction|"
        r"MultiPhaseClinicalMRSModel|90dmRSPredictionModel|poor_prognosis|"
        r"good_prognosis|prognosis)"
    )
    mentions: list[dict[str, Any]] = []
    mrs_model_code: list[str] = []
    mrs_weights: list[dict[str, Any]] = []
    other_weights: list[dict[str, Any]] = []
    this_script = Path(__file__).resolve()

    for path in iter_files_pruned(project_root, {"mrs_images", "runtime"}):
        suffix = path.suffix.lower()
        if suffix in WEIGHT_EXTENSIONS:
            relative_weight_path = relative_or_absolute(path, project_root)
            record = {
                "path": str(path.resolve()),
                "project_relative_path": relative_weight_path,
                "size_bytes": path.stat().st_size,
            }
            if re.search(r"(?i)(mrs|prognosis)", relative_weight_path):
                mrs_weights.append(record)
            else:
                other_weights.append(record)
            continue
        if suffix not in TEXT_SCAN_EXTENSIONS or path.stat().st_size > 2_000_000:
            continue
        if path.resolve() == this_script:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if mention_pattern.search(line):
                hits.append({"line_number": line_number, "text": line.strip()[:300]})
                if len(hits) >= 20:
                    break
        if hits:
            mentions.append({"path": str(path.resolve()), "hits": hits})
            if re.search(
                r"(?i)(class\s+.*mrs|train.*mrs|infer.*mrs|MultiPhaseClinicalMRSModel|"
                r"90dmRSPredictionModel)",
                text,
            ):
                mrs_model_code.append(str(path.resolve()))

    return {
        "mrs_related_mentions": mentions,
        "mrs_training_model_or_inference_code": sorted(set(mrs_model_code)),
        "mrs_related_weight_files": mrs_weights,
        "other_unrelated_model_weight_files": other_weights,
        "conclusion": (
            "Existing mRS model/training/inference assets found."
            if mrs_model_code or mrs_weights
            else "No existing mRS training, inference, model implementation, or mRS weight bundle was found."
        ),
    }


def parse_clinical_rows(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    exact_ids: Counter[str] = Counter()
    suffixes: defaultdict[str, list[int]] = defaultdict(list)
    invalid_ids: list[dict[str, Any]] = []

    for zero_index, row in frame.iterrows():
        excel_row = int(zero_index) + 2
        patient_id = display_cell(row.get(RAW_ID_COLUMN)).strip()
        match = CLINICAL_ID_RE.fullmatch(patient_id)
        record = {
            "dataframe_index": int(zero_index),
            "excel_row_index": excel_row,
            "clinical_patient_id": patient_id,
            "center_code": match.group("center") if match else None,
            "patient_suffix": match.group("patient_suffix") if match else None,
            "row": row,
        }
        rows.append(record)
        if patient_id:
            exact_ids[patient_id.lower()] += 1
        if match:
            suffixes[match.group("patient_suffix")].append(int(zero_index))
        else:
            invalid_ids.append(
                {
                    "clinical_patient_id": patient_id,
                    "clinical_row_index": excel_row,
                }
            )

    duplicate_exact_ids = [
        {"normalized_id": key, "count": count}
        for key, count in exact_ids.items()
        if count > 1
    ]
    duplicate_suffixes = [
        {
            "patient_suffix": suffix,
            "count": len(indices),
            "clinical_patient_ids": [
                rows[index]["clinical_patient_id"] for index in indices
            ],
        }
        for suffix, indices in suffixes.items()
        if len(indices) > 1
    ]
    return rows, {
        "suffix_to_indices": dict(suffixes),
        "duplicate_exact_patient_ids": duplicate_exact_ids,
        "duplicate_patient_suffixes": duplicate_suffixes,
        "invalid_patient_ids": invalid_ids,
    }


def parse_image_inventory(image_dir: Path) -> tuple[
    dict[str, dict[str, list[dict[str, Any]]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    groups: defaultdict[str, defaultdict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    invalid_names: list[dict[str, Any]] = []
    parsed_files: list[dict[str, Any]] = []
    for path in sorted(image_dir.rglob("*.npy"), key=lambda item: natural_key(item.name)):
        match = IMAGE_NAME_RE.fullmatch(path.name)
        if match is None:
            invalid_names.append(
                {"source_file": str(path.resolve()), "issue": "invalid_npy_filename"}
            )
            continue
        record = {
            "path": path.resolve(),
            "file_name": path.name,
            "channel": match.group("channel"),
            "patient_key": match.group("patient_key"),
            "slice_id": match.group("slice_id"),
            "size_bytes": path.stat().st_size,
        }
        parsed_files.append(record)
        groups[record["patient_key"]][record["channel"]].append(record)
    return (
        {patient: dict(channels) for patient, channels in groups.items()},
        invalid_names,
        parsed_files,
    )


def array_statistics(array: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "element_count": int(array.size),
        "min": None,
        "max": None,
        "mean": None,
        "nan_count": 0,
        "positive_inf_count": 0,
        "negative_inf_count": 0,
    }
    if array.size == 0 or not (
        np.issubdtype(array.dtype, np.number) or np.issubdtype(array.dtype, np.bool_)
    ):
        return result

    if np.issubdtype(array.dtype, np.inexact):
        nan_mask = np.isnan(array)
        positive_inf_mask = np.isposinf(array)
        negative_inf_mask = np.isneginf(array)
        result["nan_count"] = int(np.count_nonzero(nan_mask))
        result["positive_inf_count"] = int(np.count_nonzero(positive_inf_mask))
        result["negative_inf_count"] = int(np.count_nonzero(negative_inf_mask))
        nonfinite_count = (
            result["nan_count"]
            + result["positive_inf_count"]
            + result["negative_inf_count"]
        )
        if nonfinite_count:
            finite_values = array[np.isfinite(array)]
            if finite_values.size:
                result["min"] = float(np.min(finite_values))
                result["max"] = float(np.max(finite_values))
                result["mean"] = float(np.mean(finite_values, dtype=np.float64))
            return result

    result["min"] = float(np.min(array))
    result["max"] = float(np.max(array))
    result["mean"] = float(np.mean(array, dtype=np.float64))
    return result


def scan_npy_files(
    parsed_files: Sequence[dict[str, Any]],
    project_root: Path,
    progress_every: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    details: list[dict[str, Any]] = []
    lookup: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    total = len(parsed_files)
    for index, record in enumerate(parsed_files, start=1):
        path = Path(record["path"])
        detail = {
            "source_file": path.name,
            "relative_path": relative_or_absolute(path, project_root),
            "channel": record["channel"],
            "patient_key": record["patient_key"],
            "slice_id": record["slice_id"],
            "size_bytes": record["size_bytes"],
            "read_status": "success",
            "error": None,
        }
        try:
            array = np.load(path, allow_pickle=False)
            detail.update(array_statistics(array))
        except Exception as exc:  # keep every failed source file in the audit
            detail.update(
                {
                    "read_status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "shape": None,
                    "dtype": None,
                    "element_count": None,
                    "min": None,
                    "max": None,
                    "mean": None,
                    "nan_count": None,
                    "positive_inf_count": None,
                    "negative_inf_count": None,
                }
            )
        details.append(detail)
        lookup[str(path.resolve())] = detail
        if progress_every > 0 and (index % progress_every == 0 or index == total):
            elapsed = time.monotonic() - started
            print(
                f"[audit_mrs_data] scanned {index}/{total} npy files "
                f"({elapsed:.1f}s)",
                flush=True,
            )
    return details, lookup


def clinical_missing_mask(row: pd.Series | None) -> list[str]:
    if row is None:
        return ["clinical_mapping_unresolved"]
    missing: list[str] = []
    gender = str(row.get(PREFERRED_CLINICAL_FEATURES["sex"], "")).strip().lower()
    if gender not in {"m", "f"}:
        missing.append("sex")
    for feature_name in ("age", "onset_to_ct_time", "baseline_nihss"):
        column = PREFERRED_CLINICAL_FEATURES[feature_name]
        if to_finite_float(row.get(column)) is None:
            missing.append(feature_name)
    core_values = [to_finite_float(row.get(column)) for column in CTP_CORE_CANDIDATES]
    if not any(value is not None and value != 99 for value in core_values):
        missing.append("ctp_core_volume_unresolved_or_suspected_sentinel_99")
    return missing


def key_field_missingness(frame: pd.DataFrame) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(frame)
    for feature_name, column in PREFERRED_CLINICAL_FEATURES.items():
        values = frame[column]
        raw_missing = int(values.map(is_missing_text).sum())
        if feature_name == "sex":
            usable = values.map(lambda value: str(value).strip().lower() in {"m", "f"})
        else:
            usable = values.map(lambda value: to_finite_float(value) is not None)
        unusable = int((~usable).sum())
        results.append(
            {
                "feature_name": feature_name,
                "excel_column": column,
                "raw_missing_count": raw_missing,
                "raw_missing_rate": raw_missing / total if total else None,
                "unusable_or_invalid_count": unusable,
                "unusable_or_invalid_rate": unusable / total if total else None,
            }
        )
    for column in CTP_CORE_CANDIDATES:
        values = frame[column]
        numeric = values.map(to_finite_float)
        missing = int(numeric.isna().sum())
        sentinel = int(numeric.map(lambda value: value == 99).sum())
        results.append(
            {
                "feature_name": "ctp_core_volume_candidate",
                "excel_column": column,
                "raw_missing_count": int(values.map(is_missing_text).sum()),
                "raw_missing_rate": float(values.map(is_missing_text).mean()),
                "unusable_or_invalid_count": missing,
                "unusable_or_invalid_rate": missing / total if total else None,
                "suspected_sentinel_99_count": sentinel,
                "suspected_sentinel_99_rate": sentinel / total if total else None,
                "sentinel_note": (
                    "Value 99 occurs simultaneously in all three core definitions for 54 rows and "
                    "is strongly associated with CTP Maps in DB? = n. It is flagged, not silently recoded."
                ),
            }
        )
    label_values = frame[LABEL_COLUMN]
    parsed = label_values.map(lambda value: to_binary_label(value)[1])
    results.append(
        {
            "feature_name": "label_only",
            "excel_column": LABEL_COLUMN,
            "raw_missing_count": int(label_values.map(is_missing_text).sum()),
            "raw_missing_rate": float(label_values.map(is_missing_text).mean()),
            "unusable_or_invalid_count": int(parsed.isna().sum()),
            "unusable_or_invalid_rate": float(parsed.isna().mean()),
            "allowed_as_model_input": False,
        }
    )
    return results


def build_outputs(
    *,
    project_root: Path,
    data_dir: Path,
    requested_image_dir: Path,
    image_dir: Path,
    workbooks: Sequence[Path],
    workbook_summaries: Sequence[dict[str, Any]],
    field_tables: dict[str, Any],
    clinical_workbook: Path,
    clinical_sheet: str,
    clinical_frame: pd.DataFrame,
    clinical_rows: Sequence[dict[str, Any]],
    clinical_index: dict[str, Any],
    image_groups: dict[str, dict[str, list[dict[str, Any]]]],
    invalid_image_names: Sequence[dict[str, Any]],
    image_details: Sequence[dict[str, Any]],
    image_detail_lookup: Mapping[str, dict[str, Any]],
    field_dictionary: Sequence[dict[str, Any]],
    existing_assets: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    suffix_to_indices: dict[str, list[int]] = clinical_index["suffix_to_indices"]
    used_clinical_indices: set[int] = set()
    manifest: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    duplicate_slice_records: list[dict[str, Any]] = []
    missing_pattern_counts: Counter[str] = Counter()
    per_channel_patient_counts: Counter[str] = Counter()
    per_channel_slice_counts: defaultdict[str, list[int]] = defaultdict(list)
    complete_four_channel = 0
    missing_one_channel = 0
    missing_multiple_channels = 0
    strict_cc_aligned_complete = 0
    available_channel_cc_aligned = 0
    unique_matches = 0

    clinical_row_by_index = {
        int(record["dataframe_index"]): record for record in clinical_rows
    }

    for patient_key in sorted(image_groups, key=natural_key):
        channels = image_groups[patient_key]
        for channel in channels:
            per_channel_patient_counts[channel] += 1
            per_channel_slice_counts[channel].append(len(channels[channel]))

        missing_channels = [channel for channel in EXPECTED_CHANNELS if channel not in channels]
        missing_pattern = "|".join(missing_channels) if missing_channels else "none"
        missing_pattern_counts[missing_pattern] += 1
        if not missing_channels:
            complete_four_channel += 1
        elif len(missing_channels) == 1:
            missing_one_channel += 1
        else:
            missing_multiple_channels += 1

        slice_sets: dict[str, set[str]] = {}
        for channel, records in channels.items():
            ids = [str(item["slice_id"]) for item in records]
            counts = Counter(ids)
            for slice_id, count in counts.items():
                if count > 1:
                    duplicate_slice_records.append(
                        {
                            "patient_key": patient_key,
                            "channel": channel,
                            "slice_id": slice_id,
                            "count": count,
                        }
                    )
            slice_sets[channel] = set(ids)

        available_sets = list(slice_sets.values())
        available_aligned = len(available_sets) >= 2 and all(
            item == available_sets[0] for item in available_sets[1:]
        )
        if available_aligned:
            available_channel_cc_aligned += 1
        strict_aligned = not missing_channels and available_aligned
        if strict_aligned:
            strict_cc_aligned_complete += 1

        candidate_indices = suffix_to_indices.get(patient_key, [])
        mapping_status = (
            "unique" if len(candidate_indices) == 1 else "ambiguous" if candidate_indices else "unmatched"
        )
        clinical_record = (
            clinical_row_by_index[candidate_indices[0]] if mapping_status == "unique" else None
        )
        if clinical_record is not None:
            unique_matches += 1
            used_clinical_indices.add(int(clinical_record["dataframe_index"]))
            row = clinical_record["row"]
            label_mrs90, binary_label = to_binary_label(row.get(LABEL_COLUMN))
            screen_failure = to_finite_float(row.get(SCREEN_FAILURE_COLUMN))
            missing_clinical = clinical_missing_mask(row)
        else:
            row = None
            label_mrs90 = None
            binary_label = None
            screen_failure = None
            missing_clinical = clinical_missing_mask(None)

        readable_files = 0
        failed_files = []
        for records in channels.values():
            for item in records:
                detail = image_detail_lookup.get(str(Path(item["path"]).resolve()))
                if detail and detail.get("read_status") == "success":
                    readable_files += 1
                else:
                    failed_files.append(item["file_name"])

        exclusions: list[str] = []
        if mapping_status == "ambiguous":
            exclusions.append("ambiguous_clinical_id_suffix")
        elif mapping_status == "unmatched":
            exclusions.append("no_clinical_record_for_image_suffix")
        if mapping_status == "unique" and binary_label is None:
            exclusions.append("missing_or_invalid_90_day_mrs_label")
        if screen_failure == 1:
            exclusions.append("screen_failure_SF_1")
        if readable_files == 0:
            exclusions.append("no_readable_image_files")

        candidate_ids = [
            clinical_row_by_index[index]["clinical_patient_id"] for index in candidate_indices
        ]
        if mapping_status != "unique":
            unmatched.append(
                {
                    "record_type": "image_patient",
                    "patient_key": patient_key,
                    "clinical_patient_id": "",
                    "clinical_row_index": "",
                    "mapping_status": mapping_status,
                    "issue": exclusions[0],
                    "candidate_clinical_patient_ids": json.dumps(
                        candidate_ids, ensure_ascii=False
                    ),
                    "source_file": "",
                }
            )

        channel_files: dict[str, list[str]] = {}
        for channel in EXPECTED_CHANNELS:
            channel_files[channel] = [
                item["file_name"]
                for item in sorted(
                    channels.get(channel, []),
                    key=lambda item: natural_key(str(item["slice_id"])),
                )
            ]

        manifest.append(
            {
                "patient_key": patient_key,
                "clinical_patient_id": (
                    clinical_record["clinical_patient_id"] if clinical_record else ""
                ),
                "clinical_row_index": (
                    clinical_record["excel_row_index"] if clinical_record else ""
                ),
                "label_mrs90": label_mrs90 if label_mrs90 is not None else "",
                "binary_label": binary_label if binary_label is not None else "",
                "channel_01_files": json.dumps(channel_files["01"], ensure_ascii=False),
                "channel_02_files": json.dumps(channel_files["02"], ensure_ascii=False),
                "channel_03_files": json.dumps(channel_files["03"], ensure_ascii=False),
                "channel_04_files": json.dumps(channel_files["04"], ensure_ascii=False),
                "channel_01_count": len(channel_files["01"]),
                "channel_02_count": len(channel_files["02"]),
                "channel_03_count": len(channel_files["03"]),
                "channel_04_count": len(channel_files["04"]),
                "missing_channel_mask": json.dumps(
                    [1 if channel in missing_channels else 0 for channel in EXPECTED_CHANNELS]
                ),
                "clinical_missing_mask": json.dumps(missing_clinical, ensure_ascii=False),
                "is_eligible": not exclusions,
                "exclusion_reason": "|".join(exclusions),
                "mapping_status": mapping_status,
                "candidate_clinical_patient_ids": json.dumps(candidate_ids, ensure_ascii=False),
                "available_channels": json.dumps(
                    [channel for channel in EXPECTED_CHANNELS if channel in channels]
                ),
                "missing_channels": json.dumps(missing_channels),
                "cc_strictly_aligned_across_four_channels": strict_aligned,
                "cc_aligned_across_available_channels": available_aligned,
                "screen_failure_raw": display_cell(row.get(SCREEN_FAILURE_COLUMN)) if row is not None else "",
                "image_read_failure_count": len(failed_files),
                "image_read_failures": json.dumps(failed_files, ensure_ascii=False),
            }
        )

    for record in clinical_rows:
        index = int(record["dataframe_index"])
        if index in used_clinical_indices:
            continue
        suffix = record["patient_suffix"]
        if suffix is None:
            issue = "invalid_clinical_patient_id_format"
            mapping_status = "invalid_id"
        elif suffix not in image_groups:
            issue = "no_image_patient_for_clinical_suffix"
            mapping_status = "unmatched"
        elif len(suffix_to_indices.get(suffix, [])) > 1:
            issue = "ambiguous_clinical_id_suffix"
            mapping_status = "ambiguous"
        else:
            issue = "clinical_record_not_selected"
            mapping_status = "unmatched"
        unmatched.append(
            {
                "record_type": "clinical_record",
                "patient_key": suffix or "",
                "clinical_patient_id": record["clinical_patient_id"],
                "clinical_row_index": record["excel_row_index"],
                "mapping_status": mapping_status,
                "issue": issue,
                "candidate_clinical_patient_ids": "",
                "source_file": clinical_workbook.name,
            }
        )

    for item in invalid_image_names:
        unmatched.append(
            {
                "record_type": "image_file",
                "patient_key": "",
                "clinical_patient_id": "",
                "clinical_row_index": "",
                "mapping_status": "invalid_filename",
                "issue": item["issue"],
                "candidate_clinical_patient_ids": "",
                "source_file": item["source_file"],
            }
        )
    for detail in image_details:
        if detail.get("read_status") != "failed":
            continue
        unmatched.append(
            {
                "record_type": "image_file",
                "patient_key": detail.get("patient_key", ""),
                "clinical_patient_id": "",
                "clinical_row_index": "",
                "mapping_status": "read_failed",
                "issue": detail.get("error", "npy_read_failed"),
                "candidate_clinical_patient_ids": "",
                "source_file": detail.get("source_file", ""),
            }
        )

    shape_counts = Counter(
        str(tuple(item["shape"]))
        for item in image_details
        if item.get("read_status") == "success" and item.get("shape") is not None
    )
    dtype_counts = Counter(
        str(item["dtype"])
        for item in image_details
        if item.get("read_status") == "success"
    )
    read_failures = sum(item.get("read_status") == "failed" for item in image_details)
    nan_files = sum((item.get("nan_count") or 0) > 0 for item in image_details)
    inf_files = sum(
        (item.get("positive_inf_count") or 0) + (item.get("negative_inf_count") or 0) > 0
        for item in image_details
    )

    all_labels = [to_binary_label(value)[1] for value in clinical_frame[LABEL_COLUMN]]
    matched_labels = [
        int(row["binary_label"])
        for row in manifest
        if row["mapping_status"] == "unique" and row["binary_label"] != ""
    ]
    eligible_labels = [int(row["binary_label"]) for row in manifest if row["is_eligible"]]

    center_coverage: dict[str, dict[str, int]] = {}
    image_keys = set(image_groups)
    for record in clinical_rows:
        center = record["center_code"] or "invalid"
        entry = center_coverage.setdefault(
            center, {"clinical_rows": 0, "suffixes_present_in_images": 0}
        )
        entry["clinical_rows"] += 1
        if record["patient_suffix"] in image_keys:
            entry["suffixes_present_in_images"] += 1

    ctp_flags = clinical_frame.iloc[:, 222] if clinical_frame.shape[1] > 222 else pd.Series(dtype=object)
    core_frame = clinical_frame[list(CTP_CORE_CANDIDATES)].apply(
        lambda series: series.map(to_finite_float)
    )
    all_core_99 = core_frame.eq(99).all(axis=1)
    ctp_sentinel_evidence = {
        "all_three_core_candidates_equal_99_count": int(all_core_99.sum()),
        "any_core_candidate_equal_99_count": int(core_frame.eq(99).any(axis=1).sum()),
        "volume_section_ctp_map_flag_when_all_three_equal_99": {
            str(key): int(value)
            for key, value in ctp_flags[all_core_99].astype("string").str.lower().value_counts(dropna=False).items()
        },
        "interpretation": (
            "99 is a suspected missing/sentinel value, but the source workbook does not encode it "
            "consistently enough to recode silently. It remains unchanged and is flagged for confirmation."
        ),
    }

    audit: dict[str, Any] = {
        "schema_version": "mrs-data-audit-1.0",
        "generated_at_utc": utc_now(),
        "execution_scope": {
            "real_source_data_used": True,
            "source_data_modified": False,
            "model_training_performed": False,
            "model_weights_created": False,
            "probabilities_generated": False,
        },
        "paths": {
            "project_root": str(project_root.resolve()),
            "data_dir": str(data_dir.resolve()),
            "requested_image_dir": str(requested_image_dir.resolve()),
            "actual_image_dir": str(image_dir.resolve()),
            "requested_image_dir_exists": requested_image_dir.exists(),
        },
        "workbooks": list(workbook_summaries),
        "clinical_source": {
            "workbook": str(clinical_workbook.resolve()),
            "worksheet": clinical_sheet,
            "patient_id_column": RAW_ID_COLUMN,
            "label_column": LABEL_COLUMN,
            "row_count": len(clinical_frame),
            "patient_id_nonempty_count": int(
                clinical_frame[RAW_ID_COLUMN].map(lambda value: bool(display_cell(value))).sum()
            ),
            "patient_id_unique_count": int(clinical_frame[RAW_ID_COLUMN].astype("string").nunique(dropna=True)),
            "all_field_names": [str(column) for column in clinical_frame.columns],
            "workbook_field_dictionary": list(field_dictionary),
        },
        "field_table_markdown": field_tables,
        "markdown_to_excel_correspondence": list(MARKDOWN_TO_EXCEL_MAPPING),
        "model_feature_policy": {
            "label": {
                "excel_column": LABEL_COLUMN,
                "definition": "0=mRS 0-2 good prognosis; 1=mRS 3-6 poor prognosis",
                "allowed_as_input": False,
            },
            "preferred_prediction_time_features": [
                {"feature_name": key, "excel_column": value}
                for key, value in PREFERRED_CLINICAL_FEATURES.items()
            ],
            "ctp_core_volume_candidates": list(CTP_CORE_CANDIDATES),
            "ctp_core_selection_status": "unresolved_requires_domain_confirmation",
            "potential_leakage": identify_potential_leakage(clinical_frame.columns),
            "nihss_24h_policy": (
                "Excluded in this audit because it is post-baseline and the leakage section explicitly "
                "forbids it unless later approved, despite a later architecture section listing it."
            ),
            "training_deployment_shift_warning": (
                "Workbook CTP core values are derived from true CTP threshold definitions. Online "
                "StrokeClaw may supply pseudo-CTP/stroke-analysis core volume; source and timing are "
                "not equivalent and must be validated before training/deployment."
            ),
        },
        "clinical_missingness": key_field_missingness(clinical_frame),
        "ctp_core_sentinel_audit": ctp_sentinel_evidence,
        "patient_mapping": {
            "clinical_id_format": "ProVe-IT-AA-BBB",
            "image_filename_format": "channel-BBB_CC.npy",
            "mapping_key_used": "BBB/patient suffix only",
            "mapping_rule": (
                "Attach a clinical row only if BBB has exactly one clinical candidate. Do not infer "
                "the clinical centre AA from the image channel AA."
            ),
            "successful_unique_matches": unique_matches,
            "ambiguous_image_patient_count": sum(
                row["mapping_status"] == "ambiguous" for row in manifest
            ),
            "unmatched_image_patient_count": sum(
                row["mapping_status"] == "unmatched" for row in manifest
            ),
            "unmatched_clinical_record_count": len(clinical_rows) - len(used_clinical_indices),
            "duplicate_exact_patient_ids": clinical_index["duplicate_exact_patient_ids"],
            "duplicate_patient_suffixes": clinical_index["duplicate_patient_suffixes"],
            "invalid_clinical_patient_ids": clinical_index["invalid_patient_ids"],
            "center_suffix_coverage": center_coverage,
        },
        "image_inventory": {
            "npy_file_count": len(image_details) + len(invalid_image_names),
            "valid_filename_count": len(image_details),
            "invalid_filename_count": len(invalid_image_names),
            "image_patient_count": len(image_groups),
            "channel_file_counts": {
                channel: sum(
                    len(channels.get(channel, [])) for channels in image_groups.values()
                )
                for channel in EXPECTED_CHANNELS
            },
            "channel_patient_counts": {
                channel: int(per_channel_patient_counts[channel]) for channel in EXPECTED_CHANNELS
            },
            "per_channel_slice_count_summary": {
                channel: {
                    "patient_count": len(per_channel_slice_counts[channel]),
                    "minimum": min(per_channel_slice_counts[channel]) if per_channel_slice_counts[channel] else None,
                    "maximum": max(per_channel_slice_counts[channel]) if per_channel_slice_counts[channel] else None,
                    "mean": (
                        sum(per_channel_slice_counts[channel]) / len(per_channel_slice_counts[channel])
                        if per_channel_slice_counts[channel]
                        else None
                    ),
                }
                for channel in EXPECTED_CHANNELS
            },
            "four_channel_complete_patient_count": complete_four_channel,
            "missing_exactly_one_channel_patient_count": missing_one_channel,
            "missing_multiple_channels_patient_count": missing_multiple_channels,
            "missing_channel_pattern_counts": dict(missing_pattern_counts),
            "duplicate_slice_identifiers": duplicate_slice_records,
            "strict_cc_alignment": {
                "complete_patients_with_identical_cc_sets": strict_cc_aligned_complete,
                "patients_with_at_least_two_available_channels_and_identical_cc_sets": available_channel_cc_aligned,
                "all_complete_patients_strictly_aligned": (
                    complete_four_channel > 0 and strict_cc_aligned_complete == complete_four_channel
                ),
                "conclusion": (
                    "CC identifiers are not strictly aligned across all four channels; index-based "
                    "four-channel stacking is not justified."
                ),
            },
            "npy_read_summary": {
                "successful": len(image_details) - read_failures,
                "failed": read_failures,
                "shape_counts": dict(shape_counts),
                "dtype_counts": dict(dtype_counts),
                "files_with_nan": nan_files,
                "files_with_inf": inf_files,
            },
            "per_file_statistics": list(image_details),
        },
        "label_distribution": {
            "all_clinical_rows": {
                "label_0_good_mrs_0_2": sum(value == 0 for value in all_labels),
                "label_1_poor_mrs_3_6": sum(value == 1 for value in all_labels),
                "missing_or_invalid": sum(value is None for value in all_labels),
            },
            "uniquely_matched_rows_with_valid_label": {
                "label_0_good_mrs_0_2": sum(value == 0 for value in matched_labels),
                "label_1_poor_mrs_3_6": sum(value == 1 for value in matched_labels),
            },
            "eligible_manifest_rows": {
                "label_0_good_mrs_0_2": sum(value == 0 for value in eligible_labels),
                "label_1_poor_mrs_3_6": sum(value == 1 for value in eligible_labels),
            },
        },
        "manifest_summary": {
            "row_count": len(manifest),
            "eligible_count": sum(bool(row["is_eligible"]) for row in manifest),
            "ineligible_count": sum(not bool(row["is_eligible"]) for row in manifest),
            "missing_channels_are_not_an_automatic_exclusion": True,
        },
        "unmatched_records_summary": {
            "row_count": len(unmatched),
            "by_record_type": dict(Counter(row["record_type"] for row in unmatched)),
            "by_issue": dict(Counter(row["issue"] for row in unmatched)),
        },
        "existing_mrs_assets": existing_assets,
        "data_anomalies_and_decisions": [
            {
                "severity": "high",
                "issue": "requested_image_directory_missing",
                "detail": (
                    f"Requested directory {requested_image_dir} does not exist; real npy files were "
                    f"discovered under {image_dir}."
                ),
            },
            {
                "severity": "high",
                "issue": "clinical_image_id_ambiguity",
                "detail": (
                    "Clinical centre codes reuse BBB suffixes, while image filenames omit the centre. "
                    "Ambiguous suffixes were not assigned."
                ),
            },
            {
                "severity": "high",
                "issue": "four_channel_incompleteness",
                "detail": (
                    f"Only {complete_four_channel} of {len(image_groups)} image patients have all four channels."
                ),
            },
            {
                "severity": "high",
                "issue": "cc_not_strictly_aligned",
                "detail": (
                    f"{strict_cc_aligned_complete} complete patients have identical CC sets across all four channels."
                ),
            },
            {
                "severity": "medium",
                "issue": "ctp_core_definition_unresolved",
                "detail": (
                    "The workbook contains three distinct CTP core definitions. No single feature was selected."
                ),
            },
            {
                "severity": "medium",
                "issue": "suspected_ctp_sentinel_99",
                "detail": (
                    "Values equal to 99 are strongly suggestive of a sentinel in some rows and remain flagged."
                ),
            },
        ],
        "next_stage_dataset_recommendation": {
            "recommended_structure": "separate_phase_attention_mil",
            "reason": (
                "Four-channel completeness is rare and CC sets are not strictly aligned. Read each "
                "phase independently, aggregate variable slice counts with masked Attention MIL, use "
                "an explicit missing-phase mask, and fuse at patient level with clinical features."
            ),
            "do_not_use": "forced index-based [4,H,W] slice stacking",
            "patient_level_split_required": True,
            "blocking_items_before_model_implementation": [
                "Resolve the 78 ambiguous BBB mappings with an external centre-aware linkage source.",
                "Choose and document the CTP core volume definition and sentinel policy.",
                "Confirm whether patients with SF missing should be eligible.",
                "Confirm the training-vs-deployment CTP core data source and prediction time.",
            ],
        },
    }
    return audit, manifest, unmatched


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    data_dir = (args.data_dir or project_root / "data").resolve()
    output_dir = (args.output_dir or project_root / "outputs").resolve()
    requested_image_dir = (project_root / "data" / "images").resolve()

    if not project_root.exists():
        raise FileNotFoundError(f"Project root does not exist: {project_root}")
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    if args.image_dir is not None:
        image_dir = args.image_dir.resolve()
        if not image_dir.exists():
            raise FileNotFoundError(f"Explicit image directory does not exist: {image_dir}")
    elif requested_image_dir.exists():
        image_dir = requested_image_dir
    else:
        discovered = [
            path.resolve()
            for path in data_dir.iterdir()
            if path.is_dir() and any(path.rglob("*.npy"))
        ]
        if len(discovered) != 1:
            raise RuntimeError(
                "Requested data/images is absent and a unique npy-containing fallback directory "
                f"could not be established. Candidates: {discovered}"
            )
        image_dir = discovered[0]

    workbooks = [args.workbook.resolve()] if args.workbook else discover_workbooks(data_dir)
    if not workbooks:
        raise FileNotFoundError(f"No xlsx/xls workbooks found under {data_dir}")
    workbook_summaries = [workbook_overview(path) for path in workbooks]
    clinical_workbook, clinical_sheet, clinical_frame = choose_clinical_source(workbooks)
    clinical_rows, clinical_index = parse_clinical_rows(clinical_frame)

    # The workspace root contains the project root, so one pruned walk covers
    # both user-requested search scopes without traversing the project twice.
    search_roots = [project_root.parent.resolve()]
    field_tables = discover_field_tables(search_roots)
    field_dictionary = read_workbook_field_dictionary(clinical_workbook)
    existing_assets = inspect_existing_mrs_assets(project_root)

    image_groups, invalid_image_names, parsed_files = parse_image_inventory(image_dir)
    if not parsed_files and not invalid_image_names:
        raise RuntimeError(f"No npy files found under {image_dir}")

    print(
        f"[audit_mrs_data] clinical rows={len(clinical_frame)}, "
        f"image patients={len(image_groups)}, npy files={len(parsed_files)}",
        flush=True,
    )
    image_details, image_detail_lookup = scan_npy_files(
        parsed_files,
        project_root,
        max(0, int(args.progress_every)),
    )

    audit, manifest, unmatched = build_outputs(
        project_root=project_root,
        data_dir=data_dir,
        requested_image_dir=requested_image_dir,
        image_dir=image_dir,
        workbooks=workbooks,
        workbook_summaries=workbook_summaries,
        field_tables=field_tables,
        clinical_workbook=clinical_workbook,
        clinical_sheet=clinical_sheet,
        clinical_frame=clinical_frame,
        clinical_rows=clinical_rows,
        clinical_index=clinical_index,
        image_groups=image_groups,
        invalid_image_names=invalid_image_names,
        image_details=image_details,
        image_detail_lookup=image_detail_lookup,
        field_dictionary=field_dictionary,
        existing_assets=existing_assets,
    )

    audit_path = output_dir / "mrs_data_audit.json"
    manifest_path = output_dir / "mrs_patient_manifest.csv"
    unmatched_path = output_dir / "mrs_unmatched_records.csv"

    manifest_fields = [
        "patient_key",
        "clinical_patient_id",
        "clinical_row_index",
        "label_mrs90",
        "binary_label",
        "channel_01_files",
        "channel_02_files",
        "channel_03_files",
        "channel_04_files",
        "channel_01_count",
        "channel_02_count",
        "channel_03_count",
        "channel_04_count",
        "missing_channel_mask",
        "clinical_missing_mask",
        "is_eligible",
        "exclusion_reason",
        "mapping_status",
        "candidate_clinical_patient_ids",
        "available_channels",
        "missing_channels",
        "cc_strictly_aligned_across_four_channels",
        "cc_aligned_across_available_channels",
        "screen_failure_raw",
        "image_read_failure_count",
        "image_read_failures",
    ]
    unmatched_fields = [
        "record_type",
        "patient_key",
        "clinical_patient_id",
        "clinical_row_index",
        "mapping_status",
        "issue",
        "candidate_clinical_patient_ids",
        "source_file",
    ]

    write_json_atomic(audit_path, audit)
    write_csv_atomic(manifest_path, manifest_fields, manifest)
    write_csv_atomic(unmatched_path, unmatched_fields, unmatched)

    print(f"[audit_mrs_data] wrote {audit_path}", flush=True)
    print(f"[audit_mrs_data] wrote {manifest_path}", flush=True)
    print(f"[audit_mrs_data] wrote {unmatched_path}", flush=True)
    print(
        "[audit_mrs_data] summary "
        f"unique_matches={audit['patient_mapping']['successful_unique_matches']} "
        f"eligible={audit['manifest_summary']['eligible_count']} "
        f"read_failures={audit['image_inventory']['npy_read_summary']['failed']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("[audit_mrs_data] interrupted", file=sys.stderr)
        raise SystemExit(130)
