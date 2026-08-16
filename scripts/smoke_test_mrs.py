#!/usr/bin/env python
"""Run a deliberately small one-epoch smoke test for all three V0 models."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402
from torch import nn  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from mrs_prediction.dataset import MRSPatientDataset, mrs_patient_collate, read_manifest_rows  # noqa: E402
from mrs_prediction.model import ClinicalOnlyMRSModel, NCCTClinicalMRSModel, NCCTOnlyMRSModel  # noqa: E402
from mrs_prediction.preprocessing import ClinicalPreprocessor  # noqa: E402


def _fold_map(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["patient_key"]: int(row["fold"]) for row in csv.DictReader(handle)}


def _small_stratified_sample(records: list[dict[str, str]], maximum: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    by_label = {
        label: [record for record in records if int(float(record["binary_label"])) == label]
        for label in (0, 1)
    }
    for values in by_label.values():
        rng.shuffle(values)
    target_one = min(len(by_label[1]), max(1, maximum // 2))
    target_zero = min(len(by_label[0]), maximum - target_one)
    selected = by_label[0][:target_zero] + by_label[1][:target_one]
    rng.shuffle(selected)
    return selected


def _model_factories(clinical_dim: int) -> dict[str, Callable[[], nn.Module]]:
    common = {"embedding_dim": 16, "dropout": 0.1}
    return {
        "clinical_only": lambda: ClinicalOnlyMRSModel(clinical_dim, **common),
        "ncct_only": lambda: NCCTOnlyMRSModel(
            embedding_dim=16, attention_dim=8, base_channels=4, dropout=0.1
        ),
        "ncct_clinical": lambda: NCCTClinicalMRSModel(
            clinical_dim,
            embedding_dim=16,
            attention_dim=8,
            base_channels=4,
            fusion_dim=16,
            dropout=0.1,
        ),
    }


def _move(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {
        **batch,
        "ncct_images": batch["ncct_images"].to(device),
        "ncct_mask": batch["ncct_mask"].to(device),
        "clinical": batch["clinical"].to(device),
        "label": batch["label"].to(device),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--model-mode", choices=("baseline", "update_24h"), default="baseline")
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--patients", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-ncct-files", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--seed", type=int, default=20260806)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device("cuda" if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()) else "cpu")

    root = args.project_root.resolve()
    all_records = read_manifest_rows(root / "outputs" / "mrs_patient_manifest.csv", eligible_only=True)
    fold_by_patient = _fold_map(root / "outputs" / "mrs_splits.csv")
    train_records = [record for record in all_records if fold_by_patient[record["patient_key"]] != args.fold]
    if not train_records:
        raise RuntimeError("No training records remain after holding out the requested fold")

    # Fit on all training patients in the fold, never on the held-out fold.
    clinical_preprocessor = ClinicalPreprocessor(args.model_mode).fit(train_records)
    smoke_records = _small_stratified_sample(train_records, args.patients, args.seed)
    dataset = MRSPatientDataset(
        smoke_records,
        root / "data" / "mrs_images",
        clinical_preprocessor,
        image_size=(args.image_size, args.image_size),
        max_ncct_files=args.max_ncct_files,
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=mrs_patient_collate,
    )
    first_batch_cpu = next(iter(loader))
    output_dir = root / "outputs" / "mrs_smoke_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    criterion = nn.BCEWithLogitsLoss()
    results: dict[str, Any] = {}

    for model_name, factory in _model_factories(clinical_preprocessor.output_dim).items():
        model = factory().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        model.train()
        losses: list[float] = []
        backward_steps = 0
        for batch_cpu in loader:
            batch = _move(batch_cpu, device)
            optimizer.zero_grad(set_to_none=True)
            output = model(
                ncct_images=batch["ncct_images"],
                ncct_mask=batch["ncct_mask"],
                clinical=batch["clinical"],
            )
            loss = criterion(output["logit"], batch["label"])
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite smoke loss for {model_name}")
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            backward_steps += 1

        checkpoint_path = output_dir / f"{model_name}_TEST_ONLY_SMOKE.pt"
        checkpoint = {
            "artifact_type": "TEST_ONLY_SMOKE_CHECKPOINT",
            "status": "TEST_ONLY_NOT_FOR_CLINICAL_OR_REAL_INFERENCE",
            "is_real_inference": False,
            "production_approved": False,
            "contains_unvalidated_smoke_weights": True,
            "model_name": model.__class__.__name__,
            "model_mode": args.model_mode,
            "feature_schema_version": "mrs-v0.2",
            "model_state_dict": model.state_dict(),
            "clinical_preprocessor": clinical_preprocessor.to_dict(),
            "smoke_scope": {
                "epoch_count": 1,
                "patient_count": len(smoke_records),
                "held_out_fold": args.fold,
                "max_ncct_files": args.max_ncct_files,
                "image_size": args.image_size,
            },
        }
        torch.save(checkpoint, checkpoint_path)

        reloaded = factory().to(device)
        loaded = torch.load(checkpoint_path, map_location=device, weights_only=False)
        if loaded.get("production_approved") is not False or loaded.get("is_real_inference") is not False:
            raise RuntimeError("Smoke checkpoint safety flags are invalid")
        reloaded.load_state_dict(loaded["model_state_dict"])
        model.eval()
        reloaded.eval()
        verification_batch = _move(first_batch_cpu, device)
        with torch.no_grad():
            arguments = {
                "ncct_images": verification_batch["ncct_images"],
                "ncct_mask": verification_batch["ncct_mask"],
                "clinical": verification_batch["clinical"],
            }
            original_logits = model(**arguments)["logit"]
            reloaded_logits = reloaded(**arguments)["logit"]
        maximum_difference = float((original_logits - reloaded_logits).abs().max().cpu())
        if maximum_difference > 1e-6:
            raise RuntimeError(f"Reload mismatch for {model_name}: {maximum_difference}")
        results[model_name] = {
            "epoch_count": 1,
            "optimization_steps": backward_steps,
            "mean_training_loss": sum(losses) / len(losses),
            "checkpoint": str(checkpoint_path),
            "checkpoint_reload_max_abs_logit_difference": maximum_difference,
            "forward_backward_success": True,
        }

    label_counts = {
        str(label): sum(int(float(record["binary_label"])) == label for record in smoke_records)
        for label in (0, 1)
    }
    summary = {
        "artifact_type": "TEST_ONLY_SMOKE_RUN",
        "status": "success",
        "production_approved": False,
        "is_real_inference": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "torch_version": torch.__version__,
        "model_mode": args.model_mode,
        "held_out_fold": args.fold,
        "fold_preprocessor_fit_patient_count": len(train_records),
        "smoke_patient_count": len(smoke_records),
        "smoke_label_distribution": label_counts,
        "first_batch_shapes": {
            "ncct_images": list(first_batch_cpu["ncct_images"].shape),
            "ncct_mask": list(first_batch_cpu["ncct_mask"].shape),
            "clinical": list(first_batch_cpu["clinical"].shape),
            "label": list(first_batch_cpu["label"].shape),
        },
        "models": results,
        "clinical_preprocessor": clinical_preprocessor.to_dict(),
    }
    summary_path = output_dir / "smoke_test_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
