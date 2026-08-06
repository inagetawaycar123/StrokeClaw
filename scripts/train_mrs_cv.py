#!/usr/bin/env python
"""Run gated or complete V0.2 patient-level nested cross-validation training."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mrs_prediction.cv_training import (  # noqa: E402
    aggregate_training_outputs,
    load_training_config,
    prepare_training_context,
    run_fold,
)
from mrs_prediction.image_preprocessing import NCCTResizeCache  # noqa: E402


def _parse_ints(value: str | None, default: list[int]) -> list[int]:
    if not value:
        return default
    return [int(token.strip()) for token in value.split(",") if token.strip()]


def _parse_strings(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [token.strip() for token in value.split(",") if token.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "mrs_cv_train.yaml")
    parser.add_argument(
        "--stage",
        choices=("prepare", "fold0_clinical", "fold0_imaging", "main", "sensitivity", "report", "all"),
        default="prepare",
    )
    parser.add_argument("--folds", help="Comma-separated outer folds")
    parser.add_argument("--seeds", help="Comma-separated training seeds")
    parser.add_argument("--model-modes", help="Comma-separated baseline/update_24h")
    parser.add_argument("--models", help="Comma-separated model names")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    config = load_training_config(args.config.resolve())
    context = prepare_training_context(root, config)
    if args.stage == "prepare":
        print(json.dumps(context["training_manifest"], ensure_ascii=False, indent=2))
        return 0
    if args.stage == "report":
        comparison = aggregate_training_outputs(context, config)
        print(json.dumps(comparison, ensure_ascii=False, indent=2))
        return 0

    default_folds = list(range(int(config["cross_validation"]["outer_folds"])))
    default_seeds = [int(value) for value in config["cross_validation"]["seeds"]]
    folds = _parse_ints(args.folds, default_folds)
    seeds = _parse_ints(args.seeds, default_seeds)
    modes = _parse_strings(args.model_modes, ["baseline", "update_24h"])
    models = _parse_strings(args.models, ["clinical_only", "ncct_only", "ncct_clinical"])
    analysis = "main"

    if args.stage == "fold0_clinical":
        folds, seeds, modes, models = [0], [default_seeds[0]], ["baseline"], ["clinical_only"]
    elif args.stage == "fold0_imaging":
        folds, seeds, modes, models = [0], [default_seeds[0]], ["baseline"], ["ncct_only", "ncct_clinical"]
    elif args.stage == "sensitivity":
        analysis = "sensitivity_witnessed_only"
        seeds = _parse_ints(
            args.seeds, [int(value) for value in config["cross_validation"]["sensitivity_seeds"]]
        )
        modes = _parse_strings(args.model_modes, list(config["sensitivity_analysis"]["model_modes"]))
        models = _parse_strings(args.models, list(config["sensitivity_analysis"]["models"]))
    elif args.stage == "all":
        # Main runs are handled first. Sensitivity is deliberately a separate
        # invocation so a failure cannot overwrite or obscure the main results.
        analysis = "main"

    need_images = any(model != "clinical_only" for model in models)
    image_cache = None
    if need_images:
        image_cache = NCCTResizeCache.build_or_load(
            context["records"],
            root / str(config["data"]["image_root"]),
            context["output_root"] / "cache",
            tuple(int(value) for value in config["image"]["image_size"]),
        )

    failures = []
    completed = []
    for seed in seeds:
        for mode in modes:
            for model in models:
                for fold in folds:
                    run_id = f"{analysis}/{mode}/{model}/seed_{seed}/fold_{fold}"
                    print(f"[MRS_CV] START {run_id}", flush=True)
                    try:
                        result = run_fold(
                            context,
                            config,
                            model_mode=mode,
                            model_name=model,
                            fold=fold,
                            seed=seed,
                            analysis=analysis,
                            image_cache=image_cache,
                            force=args.force,
                        )
                        completed.append(run_id)
                        runtime = result.get("runtime", {})
                        print(
                            f"[MRS_CV] DONE {run_id} epochs={result.get('epochs_completed')} "
                            f"best_auc={result.get('best_validation_roc_auc')} "
                            f"elapsed_s={runtime.get('elapsed_seconds')}",
                            flush=True,
                        )
                    except Exception as exc:
                        failure = {
                            "run_id": run_id,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                            "traceback": traceback.format_exc(),
                        }
                        failures.append(failure)
                        failure_path = context["output_root"] / "training_failures.json"
                        failure_path.write_text(
                            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        print(f"[MRS_CV] FAILED {run_id}: {exc}", flush=True)
                        raise

    comparison = aggregate_training_outputs(context, config)
    print(
        json.dumps(
            {
                "status": "completed",
                "analysis": analysis,
                "completed_runs": len(completed),
                "failures": failures,
                "model_comparison": str(context["output_root"] / "model_comparison.json"),
                "recommended_cv_candidates": comparison.get("recommended_cv_candidates", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
