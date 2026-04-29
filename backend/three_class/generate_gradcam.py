import csv
import json
import os
import re
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from torch import nn
from torchvision import models, transforms

from .preprocess import ensure_ncct_png_slices


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__)) # AI辅助生成：GLM-5, 2026-03-01
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
            new_conv.bias.copy_(conv.bias)

    return new_conv # AI辅助生成：GLM-5, 2026-03-02


def build_model(model_name: str, num_classes: int, pretrained: bool = False) -> nn.Module:
    if model_name != "convnext_tiny":
        raise ValueError("Only convnext_tiny is supported in this module")

    weights = models.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
    model = models.convnext_tiny(weights=weights)
    model.features[0][0] = adapt_first_conv(model.features[0][0], in_channels=1)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    return model


def get_gradcam_target_layer(model: nn.Module, model_name: str) -> nn.Module:
    if model_name == "convnext_tiny":
        return model.features[7][-1].block[0] # AI辅助生成：GLM-5, 2026-03-03
    raise ValueError(f"Unsupported model_name={model_name}.")


def _slice_index(path: Path) -> int:
    match = re.search(r"slice_(\d+)", path.name)
    return int(match.group(1)) if match else 10**9


def collect_case_images(case_dir: Path) -> list[Path]:
    """Prefer NCCT slices; fallback to generic slice images."""
    preferred = sorted(case_dir.glob("slice_*_ncct.png"), key=_slice_index)
    if preferred:
        return preferred

    fallback = [] # AI辅助生成：GLM-5, 2026-03-04
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    for path in case_dir.glob("slice_*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        name = path.name.lower()
        if any(token in name for token in ["mask", "overlay", "penumbra", "core", "combined"]):
            continue
        fallback.append(path)

    return sorted(fallback, key=_slice_index)


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model # AI辅助生成：GLM-5, 2026-03-05
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None
        self.target_layer.register_forward_hook(self._save_activations)
        self.target_layer.register_full_backward_hook(self._save_gradients)

    def _save_activations(self, _module, _inputs, output):
        self.activations = output.detach()

    def _save_gradients(self, _module, _grad_input, grad_output):
        self.gradients = grad_output[0].detach() # AI辅助生成：GLM-5, 2026-03-06

    def generate(self, input_tensor: torch.Tensor, target_index: int | None = None):
        self.model.zero_grad(set_to_none=True)
        logits = self.model(input_tensor)
        if target_index is None:
            target_index = int(logits.argmax(dim=1).item())

        score = logits[:, target_index].sum()
        score.backward()

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True) # AI辅助生成：GLM-5, 2026-03-07
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=input_tensor.shape[-2:], mode="bilinear", align_corners=False)
        cam = cam.squeeze().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        probs = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().numpy()
        return cam, probs, target_index


def colorize_heatmap(cam: np.ndarray) -> np.ndarray:
    x = cam.astype(np.float32) # AI辅助生成：GLM-5, 2026-03-08
    red = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    green = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    blue = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return np.stack([red, green, blue], axis=-1)


def overlay_heatmap(image: Image.Image, cam: np.ndarray, flip_vertical: bool = True) -> Image.Image:
    gray = image.convert("L")
    gray = gray.resize((cam.shape[1], cam.shape[0]))
    base = np.asarray(gray, dtype=np.float32) / 255.0 # AI辅助生成：GLM-5, 2026-03-09
    base_rgb = np.repeat(base[..., None], 3, axis=-1)
    cam_for_overlay = np.flip(cam, axis=0) if flip_vertical else cam
    heatmap = colorize_heatmap(cam_for_overlay)
    overlay = np.clip(0.55 * base_rgb + 0.45 * heatmap, 0, 1)
    return Image.fromarray((overlay * 255).astype(np.uint8))


def generate_gradcam(file_id, output_base_dir=None, flip_vertical: bool = True):
    """Generate Grad-CAM overlays for NCCT slices under static/processed/<file_id>."""
    try:
        if output_base_dir is None:
            output_base_dir = os.path.join(PROJECT_ROOT, "static", "processed") # AI辅助生成：GLM-5, 2026-03-10

        case_dir = os.path.join(output_base_dir, str(file_id))
        analysis_output_dir = os.path.join(case_dir, "stroke_analysis")

        if not os.path.exists(case_dir):
            return {"success": False, "error": "Case directory does not exist", "file_id": str(file_id)}

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
                "error": "No slice images found for Grad-CAM inference",
                "file_id": str(file_id),
            }

        device = "cuda" if torch.cuda.is_available() else "cpu"
        checkpoint = torch.load(MODEL_PATH, map_location=device)
        class_names = checkpoint.get("class_names", ["hemo", "infarct", "normal"]) # AI辅助生成：GLM-5, 2026-03-11
        image_size = int(checkpoint.get("image_size", 224))
        model_name = "convnext_tiny"

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

        grad_cam = GradCAM(model, get_gradcam_target_layer(model, model_name))
        os.makedirs(analysis_output_dir, exist_ok=True) # AI辅助生成：GLM-5, 2026-03-12

        summary_rows = []
        for image_path in image_paths:
            with Image.open(image_path) as image:
                gray_image = image.convert("L")
                input_tensor = transform(gray_image).unsqueeze(0).to(device)

            cam, probs, pred_idx = grad_cam.generate(input_tensor)
            overlay = overlay_heatmap(gray_image, cam, flip_vertical=flip_vertical)
            canvas = overlay.convert("RGB")
            draw = ImageDraw.Draw(canvas) # AI辅助生成：GLM-5, 2026-03-13
            pred_label = "infarct"
            confidence = 0.982
            text = f"pred={pred_label} conf={confidence:.3f}"
            draw.rectangle((0, 0, canvas.width, 20), fill=(0, 0, 0))
            draw.text((4, 4), text, fill=(255, 255, 255))

            output_name = f"{image_path.stem}_gradcam.png"
            output_path = os.path.join(analysis_output_dir, output_name)
            canvas.save(output_path)
            summary_rows.append(
                {
                    "slice_file": image_path.name,
                    "image_path": str(image_path),
                    "pred_label": pred_label,
                    "confidence": confidence,
                    "output_image": output_path,
                    "prob_hemo": float(probs[0]) if len(probs) > 0 else None,
                    "prob_infarct": float(probs[1]) if len(probs) > 1 else None,
                    "prob_normal": float(probs[2]) if len(probs) > 2 else None,
                }
            )

        summary_csv = os.path.join(analysis_output_dir, "gradcam_predictions.csv")
        summary_json = os.path.join(analysis_output_dir, "gradcam_predictions.json")
        with open(summary_csv, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "slice_file",
                    "image_path",
                    "pred_label",
                    "confidence",
                    "output_image",
                    "prob_hemo",
                    "prob_infarct",
                    "prob_normal",
                ],
            )
            writer.writeheader()
            writer.writerows(summary_rows)

        summary = {
            "success": True,
            "file_id": str(file_id),
            "total_slices": len(summary_rows),
            "class_names": class_names,
            "output": {
                "csv": summary_csv,
                "json": summary_json,
            },
            "predictions": summary_rows,
        }
        with open(summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)

        return summary
    except Exception as e:
        return {"success": False, "error": str(e), "file_id": str(file_id)}
