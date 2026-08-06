#!/usr/bin/env python
"""Run independent real-patient inference checks for both MVP bundles."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.dataset import read_manifest_rows  # noqa: E402
from mrs_prediction.inference import (  # noqa: E402
    REQUIRED_MVP_BUNDLE_FIELDS,
    MRSInferenceRouter,
)
from mrs_prediction.preprocessing import extract_feature_values  # noqa: E402


def _observed_24h(record: dict[str, str]) -> bool:
    return math.isfinite(extract_feature_values(record, "update_24h")["nihss_24h"])


def _select_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    missing = next(record for record in records if not _observed_24h(record))
    selected: list[dict[str, str]] = []
    for label in (0, 1):
        selected.extend(
            record
            for record in records
            if int(float(record["binary_label"])) == label
            and _observed_24h(record)
            and record["patient_key"] != missing["patient_key"]
        )
        selected = selected[: 2 if label == 0 else 4]
    selected.append(missing)
    if len(selected) != 5 or len({record["patient_key"] for record in selected}) != 5:
        raise RuntimeError("Could not select five distinct real validation patients")
    labels = [int(float(record["binary_label"])) for record in selected]
    if labels.count(0) < 2 or labels.count(1) < 2:
        raise RuntimeError(f"Validation sample lacks required label representation: {labels}")
    return selected


def _assert_success(result: dict[str, Any], expected_mode: str) -> None:
    if result.get("status") != "success":
        raise AssertionError(result)
    if result["model"]["mode"] != expected_mode or not result["model_forward_executed"]:
        raise AssertionError("Inference routing or forward status is incorrect")
    prediction = result["prediction"]
    risk = float(prediction["poor_prognosis_risk"])
    good = float(prediction["good_prognosis_probability"])
    if not (0.0 <= risk <= 1.0 and 0.0 <= good <= 1.0):
        raise AssertionError("Prediction probability is outside [0, 1]")
    if abs(risk + good - 1.0) > 1e-8:
        raise AssertionError("Good and poor prognosis probabilities do not sum to one")
    if result["confidence"]["level"] not in {"high", "medium", "low"}:
        raise AssertionError("Confidence level is invalid")


def _bundle_fields(path: Path) -> dict[str, Any]:
    bundle = torch.load(path, map_location="cpu", weights_only=False)
    missing = sorted(REQUIRED_MVP_BUNDLE_FIELDS - set(bundle))
    if missing:
        raise AssertionError(f"Bundle {path} is missing {missing}")
    return {
        "path": str(path),
        "field_count": len(bundle),
        "required_fields_present": True,
        "ensemble_members": len(bundle["ensemble_state_dicts"]),
        "ensemble_seeds": list(bundle["ensemble_seeds"]),
        "model_mode": bundle["model_mode"],
        "external_validation_completed": bundle["external_validation_completed"],
        "release_status": bundle["release_status"],
        "online_loading_permitted": bundle["online_loading_permitted"],
        "is_real_inference": bundle["is_real_inference"],
        "production_approved": bundle["production_approved"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    root = args.project_root.resolve()
    baseline_path = root / "outputs" / "mrs_model" / "mrs_baseline_mvp.pt"
    update_path = root / "outputs" / "mrs_model" / "mrs_update24h_mvp.pt"
    records = read_manifest_rows(root / "outputs" / "mrs_patient_manifest.csv", eligible_only=True)
    selected = _select_records(records)
    router = MRSInferenceRouter(baseline_path, update_path, device=args.device)
    image_root = root / "data" / "mrs_images"
    patient_results: list[dict[str, Any]] = []
    reference_predictions: dict[tuple[str, str], float] = {}

    for record in selected:
        patient_key = str(record["patient_key"])
        true_label = int(float(record["binary_label"]))
        baseline = router.predict("baseline", record, image_root=image_root)
        _assert_success(baseline, "baseline")
        reference_predictions[(patient_key, "baseline")] = float(
            baseline["prediction"]["poor_prognosis_risk"]
        )
        entry: dict[str, Any] = {
            "patient_key": patient_key,
            "true_label_for_validation_only": true_label,
            "nihss_24h_missing": not _observed_24h(record),
            "baseline": baseline,
        }
        before = router.models["update_24h"].forward_call_count
        update = router.predict("update_24h", record, image_root=image_root)
        after = router.models["update_24h"].forward_call_count
        if _observed_24h(record):
            _assert_success(update, "update_24h")
            if after - before != 3:
                raise AssertionError("Observed update_24h inference did not call all three members")
            reference_predictions[(patient_key, "update_24h")] = float(
                update["prediction"]["poor_prognosis_risk"]
            )
        else:
            if not (
                update.get("status") == "unavailable"
                and update.get("error_code") == "MISSING_NIHSS_24H"
                and update.get("model_forward_executed") is False
                and after == before
            ):
                raise AssertionError("Missing 24-hour NIHSS did not block model forward")
        entry["update_24h"] = update
        patient_results.append(entry)

    reloaded = MRSInferenceRouter(baseline_path, update_path, device=args.device)
    maximum_reload_difference = 0.0
    for record in selected:
        patient_key = str(record["patient_key"])
        for mode in ("baseline", "update_24h"):
            if mode == "update_24h" and not _observed_24h(record):
                continue
            result = reloaded.predict(mode, record, image_root=image_root)
            _assert_success(result, mode)
            difference = abs(
                float(result["prediction"]["poor_prognosis_risk"])
                - reference_predictions[(patient_key, mode)]
            )
            maximum_reload_difference = max(maximum_reload_difference, difference)
    if maximum_reload_difference > 1e-8:
        raise AssertionError(
            f"Bundle reload changed risk probability by {maximum_reload_difference}"
        )

    summary = {
        "status": "passed",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "real_patient_count": len(selected),
        "label_distribution": {
            "0": sum(int(float(record["binary_label"])) == 0 for record in selected),
            "1": sum(int(float(record["binary_label"])) == 1 for record in selected),
        },
        "missing_nihss_24h_patient_count": sum(not _observed_24h(record) for record in selected),
        "checks": {
            "probabilities_in_unit_interval": True,
            "probability_pairs_sum_to_one": True,
            "bundle_reload_predictions_consistent": True,
            "maximum_reload_probability_difference": maximum_reload_difference,
            "baseline_update_routing_correct": True,
            "missing_nihss_24h_blocked_before_model_forward": True,
            "confidence_levels_valid": True,
        },
        "bundle_fields": {
            "baseline": _bundle_fields(baseline_path),
            "update_24h": _bundle_fields(update_path),
        },
        "patients": patient_results,
    }
    output = root / "outputs" / "mrs_model" / "mvp_inference_validation.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

