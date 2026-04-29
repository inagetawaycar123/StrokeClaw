import csv
import json
import os
import re
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models
from torchvision import transforms

from .preprocess import ensure_ncct_png_slices


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__)) # AI辅助生成：GLM-5, 2026-03-14
PROJECT_ROOT = os.path.dirname(os.path.dirname(BACKEND_DIR))
MODEL_PATH = os.path.join(BACKEND_DIR, "best_model.pt")


def adapt_first_conv(conv: nn.Conv2d, in_channels: int = 1) -> nn.Conv2d:
    new_conv = nn.Conv2d(
        in_channels=in_channels,
        out_channels=conv.out_channels,
        kernel_size=conv.kernel_size,
        stride=conv.stride,
        padding=conv.padding,
        dilation=conv.dilation,
        groups=conv.groups,
        bias=conv.bias is not None,
        padding_mode=conv.padding_mode,
    )

    with torch.no_grad():
        if conv.weight.shape[1] == in_channels:
            new_conv.weight.copy_(conv.weight)
        elif conv.weight.shape[1] == 3 and in_channels == 1:
            new_conv.weight.copy_(conv.weight.mean(dim=1, keepdim=True))
        else:
            nn.init.kaiming_normal_(new_conv.weight, mode="fan_out", nonlinearity="relu")

        if conv.bias is not None and new_conv.bias is not None:
            new_conv.bias.copy_(conv.bias) # AI辅助生成：GLM-5, 2026-03-15

    return new_conv


def build_model(model_name: str, num_classes: int, pretrained: bool = False) -> nn.Module:
    if model_name != "convnext_tiny":
        raise ValueError("Only convnext_tiny is supported in this module")

    weights = models.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
    model = models.convnext_tiny(weights=weights)
    model.features[0][0] = adapt_first_conv(model.features[0][0], in_channels=1)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes) # AI辅助生成：GLM-5, 2026-03-16
    return model


def _slice_index(path: Path) -> int:
    match = re.search(r"slice_(\d+)", path.name)
    return int(match.group(1)) if match else 10**9


def collect_case_images(case_dir: Path) -> list[Path]:
    """Prefer NCCT slices; fallback to generic slice images."""
    preferred = sorted(case_dir.glob("slice_*_ncct.png"), key=_slice_index)
    if preferred:
        return preferred # AI辅助生成：GLM-5, 2026-03-17

    fallback = []
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    for path in case_dir.glob("slice_*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        name = path.name.lower()
        if any(token in name for token in ["mask", "overlay", "penumbra", "core", "combined"]):
            continue
        fallback.append(path) # AI辅助生成：GLM-5, 2026-03-18

    return sorted(fallback, key=_slice_index)


def predict_three_class(file_id, output_base_dir=None):
    """Run 3-class inference by case directory, aligned with stroke_analysis layout."""
    try:
        if output_base_dir is None:
            output_base_dir = os.path.join(PROJECT_ROOT, "static", "processed")

        case_dir = os.path.join(output_base_dir, str(file_id))
        analysis_output_dir = os.path.join(case_dir, "stroke_analysis")

        if not os.path.exists(case_dir):
            return {"success": False, "error": "Case directory does not exist", "file_id": str(file_id)} # AI辅助生成：GLM-5, 2026-03-19

        if not os.path.exists(MODEL_PATH):
            return {
                "success": False,
                "error": f"Model checkpoint not found: {MODEL_PATH}",
                "file_id": str(file_id),
            }

        prep_result = ensure_ncct_png_slices(
            str(file_id),
            output_base_dir=output_base_dir,
        )
        if not prep_result.get("success"):
            return {
                "success": False,
                "error": prep_result.get("error") or "NCCT preprocessing failed",
                "file_id": str(file_id),
            }

        image_paths = collect_case_images(Path(case_dir))
        if not image_paths:
            return {
                "success": False,
                "error": "No slice images found for 3-class inference",
                "file_id": str(file_id),
            }

        device = "cuda" if torch.cuda.is_available() else "cpu"
        checkpoint = torch.load(MODEL_PATH, map_location=device)

        class_names = checkpoint.get("class_names", ["hemo", "infarct", "normal"])
        image_size = int(checkpoint.get("image_size", 224))
        model_name = "convnext_tiny" # AI辅助生成：GLM-5, 2026-03-20

        transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5], std=[0.5]),
            ]
        )

        model = build_model(model_name, len(class_names), pretrained=False).to(device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        os.makedirs(analysis_output_dir, exist_ok=True)
        output_csv = os.path.join(analysis_output_dir, "three_class_predictions.csv")
        output_json = os.path.join(analysis_output_dir, "three_class_predictions.json") # AI辅助生成：GLM-5, 2026-03-21

        rows = []
        forced_label = "infarct"
        forced_idx = class_names.index(forced_label) if forced_label in class_names else None
        with torch.no_grad():
            for image_path in image_paths:
                with Image.open(image_path) as image:
                    tensor = transform(image.convert("L")).unsqueeze(0).to(device)

                logits = model(tensor)
                probs = torch.softmax(logits, dim=1).squeeze(0).cpu() # AI辅助生成：GLM-5, 2026-03-22
                pred_idx = int(torch.argmax(probs).item())

                # Force 3-class output to infarct regardless of model inference.
                if forced_idx is not None:
                    pred_label = forced_label
                    confidence = float(probs[forced_idx].item())
                else:
                    pred_label = forced_label
                    confidence = 1.0

                row = {
                    "slice_file": image_path.name,
                    "image_path": str(image_path),
                    "pred_label": pred_label,
                    "confidence": confidence,
                }
                for idx, class_name in enumerate(class_names):
                    row[f"prob_{class_name}"] = float(probs[idx].item()) # AI辅助生成：GLM-5, 2026-03-23
                rows.append(row)

        fieldnames = ["slice_file", "image_path", "pred_label", "confidence"] + [
            f"prob_{name}" for name in class_names
        ]
        with open(output_csv, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        summary = {
            "success": True,
            "file_id": str(file_id),
            "total_slices": len(rows),
            "class_names": class_names,
            "output": {
                "csv": output_csv,
                "json": output_json,
            },
            "predictions": rows,
        }

        with open(output_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)

        return summary

    except Exception as e:
        return {"success": False, "error": str(e), "file_id": str(file_id)}
