"""Build the conservative Stage-2 V0 patient cohort from audited records."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CLINICAL_COLUMNS = (
    "Gender",
    "Age",
    "Onset to CT time",
    "NIHSS Baseline",
    "NIHSS 24 HOURS",
)

ONSET_SOURCE_COLUMNS = (
    "Stroke on awakening/Unwitnessed",
    "Stroke witnessed",
    "Time of Symptom onset",
    "Time of Initial CT_Osirix",
)


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    token = str(value or "").strip()
    if not token or token.lower() == "nan":
        return []
    parsed = json.loads(token)
    return [str(item) for item in parsed]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def derive_onset_to_ct(record: dict[str, Any]) -> dict[str, Any]:
    """Derive an auditable onset-to-CT interval in hours from source time cells.

    The workbook stores time-of-day as Excel day fractions and lacks a separate
    CT date. Acute imaging is therefore assumed to occur within 24 hours, and a
    modulo-one-day difference handles midnight crossing. The original workbook
    value is always retained separately.
    """

    onset = _number(record.get("Time of Symptom onset"))
    ct_time = _number(record.get("Time of Initial CT_Osirix"))
    raw_days = _number(record.get("Onset to CT time"))
    wakeup = _number(record.get("Stroke on awakening/Unwitnessed"))
    witnessed = _number(record.get("Stroke witnessed"))
    if onset is None or ct_time is None:
        return {
            "onset_to_ct_hours": "",
            "onset_to_ct_days_derived": "",
            "onset_to_ct_derivation_status": "unavailable_missing_source_time",
            "onset_to_ct_raw_difference_days": "",
            "onset_to_ct_correction_applied": False,
            "onset_to_ct_witness_status": (
                "unwitnessed_or_wakeup" if wakeup == 1.0 and witnessed == 0.0 else "unknown"
            ),
        }
    derived_days = (ct_time - onset) % 1.0
    difference = raw_days - derived_days if raw_days is not None else None
    correction = difference is None or abs(difference) > 1e-9
    if witnessed == 1.0:
        witness_status = "witnessed"
    elif wakeup == 1.0:
        witness_status = "unwitnessed_or_wakeup"
    else:
        witness_status = "unknown"
    return {
        "onset_to_ct_hours": derived_days * 24.0,
        "onset_to_ct_days_derived": derived_days,
        "onset_to_ct_derivation_status": "success_modulo_24h",
        "onset_to_ct_raw_difference_days": "" if difference is None else difference,
        "onset_to_ct_correction_applied": correction,
        "onset_to_ct_witness_status": witness_status,
    }


def build_v0_manifest(
    manifest_path: str | Path,
    workbook_path: str | Path,
    *,
    sheet_name: str = "1_原始Master",
    summary_path: str | Path | None = None,
    onset_audit_path: str | Path | None = None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    workbook_file = Path(workbook_path).resolve()
    manifest = pd.read_csv(manifest_file, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    clinical = pd.read_excel(workbook_file, sheet_name=sheet_name, dtype=object)
    required = {"Prove-it ID", "90 Day MRS", *CLINICAL_COLUMNS, *ONSET_SOURCE_COLUMNS}
    missing = sorted(required - set(clinical.columns))
    if missing:
        raise KeyError(f"Clinical workbook is missing required columns: {missing}")
    clinical_ids = clinical["Prove-it ID"].astype(str).str.strip()
    duplicate_ids = sorted(clinical_ids[clinical_ids.duplicated(keep=False)].unique().tolist())
    if duplicate_ids:
        raise ValueError(f"Clinical workbook has duplicate exact Prove-it IDs: {duplicate_ids[:10]}")
    clinical_by_id = {patient_id: index for index, patient_id in clinical_ids.items()}

    appended_columns = [
        "npy_bundle_files",
        "npy_bundle_file_count",
        "has_internal_ncct",
        "internal_ncct_channel_index",
        "is_v0_eligible",
        "v0_exclusion_reason",
        "v0_clinical_missing_mask",
        "v0_clinical_data_warnings",
        *CLINICAL_COLUMNS,
        *ONSET_SOURCE_COLUMNS,
        "onset_to_ct_hours",
        "onset_to_ct_days_derived",
        "onset_to_ct_derivation_status",
        "onset_to_ct_raw_difference_days",
        "onset_to_ct_correction_applied",
        "onset_to_ct_witness_status",
        "nihss_change_24h",
        "ctp_core_volume",
        "ctp_core_volume_use_status",
        "model_modes_available",
    ]
    for column in appended_columns:
        if column in manifest.columns:
            manifest = manifest.drop(columns=[column])

    output_rows: list[dict[str, Any]] = []
    for _, source in manifest.iterrows():
        row = source.to_dict()
        files: list[str] = []
        for column in ("channel_01_files", "channel_02_files", "channel_03_files", "channel_04_files"):
            files.extend(_parse_list(row.get(column)))
        files = sorted(set(files))
        reasons: list[str] = []
        mapping_status = str(row.get("mapping_status", "")).strip().lower()
        if mapping_status == "ambiguous":
            reasons.append("ambiguous_clinical_id_suffix")
        elif mapping_status != "unique":
            reasons.append("clinical_image_mapping_not_unique")
        try:
            binary_label = int(float(str(row.get("binary_label", ""))))
        except ValueError:
            binary_label = -1
        # An ambiguous row has no attached label because the clinical record was
        # intentionally not chosen; do not misreport that as a genuinely missing
        # outcome. Label validity is assessed only after a unique mapping exists.
        if mapping_status == "unique" and binary_label not in (0, 1):
            reasons.append("invalid_or_missing_90_day_mrs")
        if not files:
            reasons.append("no_ncct")
        try:
            failures = int(float(str(row.get("image_read_failure_count", "0") or "0")))
        except ValueError:
            failures = 1
        if failures > 0:
            reasons.append("image_read_failure")

        clinical_values: dict[str, Any] = {column: "" for column in (*CLINICAL_COLUMNS, *ONSET_SOURCE_COLUMNS)}
        clinical_row_index = str(row.get("clinical_row_index", "")).strip()
        if mapping_status == "unique" and clinical_row_index:
            expected_id = str(row.get("clinical_patient_id", "")).strip()
            if expected_id not in clinical_by_id:
                raise ValueError(f"Clinical ID from manifest is absent from workbook: {expected_id!r}")
            index = int(clinical_by_id[expected_id])
            clinical_row = clinical.iloc[index]
            actual_id = str(clinical_row["Prove-it ID"]).strip()
            if expected_id != actual_id:
                raise ValueError(
                    f"Clinical row index mismatch for {row.get('patient_key')}: {expected_id!r} != {actual_id!r}"
                )
            # The audit stores the 1-based Excel worksheet row, including the header.
            if int(float(clinical_row_index)) != index + 2:
                raise ValueError(
                    f"Audit Excel-row reference mismatch for {expected_id}: "
                    f"manifest={clinical_row_index}, workbook={index + 2}"
                )
            clinical_values = {
                column: "" if pd.isna(clinical_row[column]) else clinical_row[column]
                for column in (*CLINICAL_COLUMNS, *ONSET_SOURCE_COLUMNS)
            }

        baseline = _number(clinical_values["NIHSS Baseline"])
        followup = _number(clinical_values["NIHSS 24 HOURS"])
        nihss_change = followup - baseline if baseline is not None and followup is not None else ""
        onset_derivation = derive_onset_to_ct(clinical_values)
        missing_clinical: list[str] = []
        warnings: list[str] = []
        gender = str(clinical_values["Gender"] or "").strip().upper()
        if gender not in {"F", "M"}:
            missing_clinical.append("Gender")
        for column in ("Age", "NIHSS Baseline", "NIHSS 24 HOURS"):
            if _number(clinical_values[column]) is None:
                missing_clinical.append(column)
        if onset_derivation["onset_to_ct_derivation_status"] != "success_modulo_24h":
            missing_clinical.append("onset_to_ct_hours")
        if onset_derivation["onset_to_ct_correction_applied"]:
            warnings.append("onset_to_ct_raw_value_corrected")
        if onset_derivation["onset_to_ct_witness_status"] == "unwitnessed_or_wakeup":
            warnings.append("onset_time_unwitnessed_or_wakeup")
        row.update(
            {
                "npy_bundle_files": json.dumps(files, ensure_ascii=False),
                "npy_bundle_file_count": len(files),
                "has_internal_ncct": bool(files),
                "internal_ncct_channel_index": 0 if files else "",
                "is_v0_eligible": not reasons,
                "v0_exclusion_reason": ";".join(reasons),
                "v0_clinical_missing_mask": json.dumps(missing_clinical, ensure_ascii=False),
                "v0_clinical_data_warnings": json.dumps(warnings, ensure_ascii=False),
                **clinical_values,
                **onset_derivation,
                "nihss_change_24h": nihss_change,
                "ctp_core_volume": "",
                "ctp_core_volume_use_status": "reserved_not_used_v0",
                "model_modes_available": json.dumps(["baseline", "update_24h"]),
            }
        )
        output_rows.append(row)

    updated = pd.DataFrame(output_rows)
    temporary = manifest_file.with_suffix(manifest_file.suffix + ".tmp")
    updated.to_csv(temporary, index=False, encoding="utf-8-sig")
    temporary.replace(manifest_file)

    eligible = updated[updated["is_v0_eligible"] == True]  # noqa: E712
    exclusion_counts = Counter(
        reason
        for value in updated.loc[updated["is_v0_eligible"] == False, "v0_exclusion_reason"]  # noqa: E712
        for reason in str(value).split(";")
        if reason
    )
    label_counts = Counter(int(float(value)) for value in eligible["binary_label"])
    missing_counts = Counter(
        field
        for value in eligible["v0_clinical_missing_mask"]
        for field in _parse_list(value)
    )
    warning_counts = Counter(
        warning
        for value in eligible["v0_clinical_data_warnings"]
        for warning in _parse_list(value)
    )
    successful_onset = eligible[eligible["onset_to_ct_derivation_status"] == "success_modulo_24h"]
    correction_count = int(
        successful_onset["onset_to_ct_correction_applied"].astype(str).str.lower().eq("true").sum()
    )
    onset_hours = pd.to_numeric(successful_onset["onset_to_ct_hours"], errors="coerce")
    summary = {
        "schema_version": "mrs-v0-cohort-1.0",
        "source_manifest": str(manifest_file),
        "source_workbook": str(workbook_file),
        "source_sheet": sheet_name,
        "rows_total": int(len(updated)),
        "v0_eligible_patients": int(len(eligible)),
        "label_distribution": {"0": label_counts[0], "1": label_counts[1]},
        "excluded_patients": int(len(updated) - len(eligible)),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "eligible_clinical_missing_counts": dict(sorted(missing_counts.items())),
        "eligible_clinical_warning_counts": dict(sorted(warning_counts.items())),
        "onset_to_ct_correction": {
            "eligible_patients": int(len(eligible)),
            "successfully_derived": int(len(successful_onset)),
            "raw_values_already_correct": int(len(successful_onset) - correction_count),
            "raw_values_corrected": correction_count,
            "unavailable_missing_source_time": int(len(eligible) - len(successful_onset)),
            "unwitnessed_or_wakeup": int(
                eligible["onset_to_ct_witness_status"].eq("unwitnessed_or_wakeup").sum()
            ),
            "derived_hours_min": float(onset_hours.min()) if not onset_hours.empty else None,
            "derived_hours_max": float(onset_hours.max()) if not onset_hours.empty else None,
            "assumption": "source times are Excel day fractions and imaging interval is less than 24 hours",
        },
        "ncct_definition": "internal channel index 0 in every HWC4 .npy bundle",
        "raw_source_data_modified": False,
    }
    if summary_path:
        summary_file = Path(summary_path).resolve()
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if onset_audit_path:
        audit_file = Path(onset_audit_path).resolve()
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        audit = eligible[
            [
                "patient_key",
                "clinical_patient_id",
                "Stroke on awakening/Unwitnessed",
                "Stroke witnessed",
                "Time of Symptom onset",
                "Time of Initial CT_Osirix",
                "Onset to CT time",
                "onset_to_ct_days_derived",
                "onset_to_ct_hours",
                "onset_to_ct_raw_difference_days",
                "onset_to_ct_correction_applied",
                "onset_to_ct_derivation_status",
                "onset_to_ct_witness_status",
            ]
        ].rename(columns={"Onset to CT time": "onset_to_ct_time_raw_excel_days"})
        audit["derivation_assumption"] = "modulo_1_day; acute interval_less_than_24h"
        audit_temporary = audit_file.with_suffix(audit_file.suffix + ".tmp")
        audit.to_csv(audit_temporary, index=False, encoding="utf-8-sig")
        audit_temporary.replace(audit_file)
        summary["onset_to_ct_correction"]["audit_output"] = str(audit_file)
        if summary_path:
            summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
