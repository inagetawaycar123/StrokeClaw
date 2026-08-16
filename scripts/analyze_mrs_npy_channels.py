#!/usr/bin/env python
"""Analyze and visualize the four internal channels in the real mRS arrays."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.channel_analysis import analyze_channels  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--per-group", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260806)
    args = parser.parse_args()
    report = analyze_channels(args.project_root, per_group=args.per_group, seed=args.seed)
    print(
        json.dumps(
            {
                "result": report["classification"]["result"],
                "sampled_files": report["sampling"]["total_sampled_files"],
                "output": str(args.project_root / "outputs" / "mrs_npy_channel_analysis.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

