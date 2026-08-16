#!/usr/bin/env python
"""Append conservative V0 eligibility and exact clinical fields to the audit manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.manifest import build_v0_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    summary = build_v0_manifest(
        root / "outputs" / "mrs_patient_manifest.csv",
        root / "data" / "ProveIt_中文翻译_编码保留版.xlsx",
        summary_path=root / "outputs" / "mrs_v0_cohort_summary.json",
        onset_audit_path=root / "outputs" / "mrs_onset_to_ct_correction_audit.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
