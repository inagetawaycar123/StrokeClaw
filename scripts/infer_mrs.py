#!/usr/bin/env python
"""Standalone CLI for baseline or 24-hour MVP ensemble inference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.dataset import read_manifest_rows  # noqa: E402
from mrs_prediction.inference import MRSInferenceRouter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-mode", choices=("baseline", "update_24h"), required=True)
    parser.add_argument("--patient-key")
    parser.add_argument("--clinical-json", type=Path)
    parser.add_argument("--image-file", action="append", default=[])
    parser.add_argument(
        "--manifest", type=Path, default=PROJECT_ROOT / "outputs" / "mrs_patient_manifest.csv"
    )
    parser.add_argument("--image-root", type=Path, default=PROJECT_ROOT / "data" / "mrs_images")
    parser.add_argument(
        "--baseline-bundle",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "mrs_model" / "mrs_baseline_mvp.pt",
    )
    parser.add_argument(
        "--update24h-bundle",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "mrs_model" / "mrs_update24h_mvp.pt",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()

    if bool(args.patient_key) == bool(args.clinical_json):
        parser.error("Provide exactly one of --patient-key or --clinical-json")
    if args.patient_key:
        records = read_manifest_rows(args.manifest, eligible_only=True)
        matches = [record for record in records if record.get("patient_key") == args.patient_key]
        if len(matches) != 1:
            parser.error(f"patient_key must match exactly one frozen V0 record; got {len(matches)}")
        record = matches[0]
    else:
        record = json.loads(args.clinical_json.read_text(encoding="utf-8"))

    router = MRSInferenceRouter(
        args.baseline_bundle, args.update24h_bundle, device=args.device
    )
    result = router.predict(
        args.model_mode,
        record,
        image_root=args.image_root,
        image_files=args.image_file or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())

