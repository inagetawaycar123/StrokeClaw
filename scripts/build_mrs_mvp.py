#!/usr/bin/env python
"""Build the two fixed 90-day mRS MVP research bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.mvp_training import build_mvp_bundles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "configs" / "mrs_cv_train.yaml"
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = build_mvp_bundles(
        args.project_root.resolve(), config_path=args.config.resolve(), force=args.force
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

