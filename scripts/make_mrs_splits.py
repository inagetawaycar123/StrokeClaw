#!/usr/bin/env python
"""Create deterministic patient-level stratified five-fold assignments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.dataset import read_manifest_rows  # noqa: E402
from mrs_prediction.splits import assign_stratified_folds, fold_summary, write_splits  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260806)
    args = parser.parse_args()
    root = args.project_root.resolve()
    rows = read_manifest_rows(root / "outputs" / "mrs_patient_manifest.csv", eligible_only=True)
    assignments = assign_stratified_folds(rows, n_splits=args.folds, seed=args.seed)
    output = root / "outputs" / "mrs_splits.csv"
    write_splits(assignments, output)
    summary = fold_summary(assignments)
    summary.update({"seed": args.seed, "n_splits": args.folds, "output": str(output)})
    (root / "outputs" / "mrs_splits_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

