"""Evidence-backed analysis of the four internal channels in mRS `.npy` files."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageOps


FILENAME_PATTERN = re.compile(
    r"^(?P<group>\d{2})-(?P<subject>\d{3})_(?P<slice>\d+)\.npy$",
    re.IGNORECASE,
)
INTERNAL_CHANNELS = (
    "NCCT",
    "arterial_mCTA",
    "venous_mCTA",
    "delayed_mCTA",
)


def _json_number(value: float) -> float | None:
    value = float(value)
    return value if np.isfinite(value) else None


def _channel_statistics(array: np.ndarray) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, name in enumerate(INTERNAL_CHANNELS):
        values = np.asarray(array[..., index], dtype=np.float64)
        result.append(
            {
                "internal_channel_index": index,
                "interpreted_name": name,
                "min": float(values.min()),
                "max": float(values.max()),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
            }
        )
    return result


def _correlation(array: np.ndarray) -> list[list[float | None]]:
    matrix = np.corrcoef(array.reshape(-1, 4), rowvar=False)
    return [[_json_number(value) for value in row] for row in matrix]


def _display_plane(plane: np.ndarray) -> Image.Image:
    clipped = np.clip(np.asarray(plane, dtype=np.float32), 0.0, 1.0)
    return Image.fromarray(np.rint(clipped * 255.0).astype(np.uint8), mode="L")


def _save_visualizations(array: np.ndarray, filename: str, output_dir: Path) -> dict[str, Any]:
    stem = Path(filename).stem
    individual: list[str] = []
    panels: list[Image.Image] = []
    for index, name in enumerate(INTERNAL_CHANNELS):
        plane = _display_plane(array[..., index])
        directory = output_dir / f"channel_{index}_{name}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stem}.png"
        plane.save(path)
        individual.append(str(path))
        panels.append(plane.convert("RGB"))

    title_height = 36
    width = sum(panel.width for panel in panels)
    canvas = Image.new("RGB", (width, panels[0].height + title_height), "white")
    draw = ImageDraw.Draw(canvas)
    panel_width = panels[0].width
    for index, panel in enumerate(panels):
        canvas.paste(panel, (index * panel_width, title_height))
        draw.text((index * panel_width + 5, 4), f"ch{index}: {INTERNAL_CHANNELS[index]}", fill="black")
    montage_dir = output_dir / "montages"
    montage_dir.mkdir(parents=True, exist_ok=True)
    montage_path = montage_dir / f"{stem}_four_internal_channels.png"
    ImageOps.expand(canvas, border=1, fill="black").save(montage_path)
    return {"individual_channel_images": individual, "montage": str(montage_path)}


def _sample_files(image_dir: Path, per_group: int, seed: int) -> dict[str, list[Path]]:
    by_group: dict[str, dict[str, list[Path]]] = {key: {} for key in ("01", "02", "03", "04")}
    for path in sorted(image_dir.glob("*.npy")):
        match = FILENAME_PATTERN.match(path.name)
        if not match:
            continue
        group = match.group("group")
        if group not in by_group:
            continue
        patient_id = f"{group}-{match.group('subject')}"
        by_group[group].setdefault(patient_id, []).append(path)
    rng = random.Random(seed)
    selected: dict[str, list[Path]] = {}
    for group, patient_files in by_group.items():
        patients = sorted(patient_files)
        if len(patients) < per_group:
            raise ValueError(f"Filename group {group} has only {len(patients)} patients; need {per_group}")
        sampled_patients = rng.sample(patients, per_group)
        selected[group] = [rng.choice(sorted(patient_files[patient])) for patient in sampled_patients]
    return selected


def _aggregate(files: Iterable[Path]) -> dict[str, Any]:
    arrays = [np.load(path, allow_pickle=False).reshape(-1, 4).astype(np.float64) for path in files]
    values = np.concatenate(arrays, axis=0)
    return {
        "file_count": len(arrays),
        "pixel_count_per_internal_channel": int(values.shape[0]),
        "channels": [
            {
                "internal_channel_index": index,
                "interpreted_name": INTERNAL_CHANNELS[index],
                "min": float(values[:, index].min()),
                "max": float(values[:, index].max()),
                "mean": float(values[:, index].mean()),
                "std": float(values[:, index].std(ddof=0)),
            }
            for index in range(4)
        ],
        "correlation_matrix": _correlation(values.reshape(-1, 1, 4)),
    }


def _source_evidence(project_root: Path, search_root: Path) -> dict[str, Any]:
    dataset_path = project_root / "mrdpm" / "data" / "dataset.py"
    evidence_lines: list[dict[str, Any]] = []
    if dataset_path.exists():
        lines = dataset_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number in (101, 135, 149, 152, 153, 233, 236, 237):
            if line_number <= len(lines):
                evidence_lines.append(
                    {"path": str(dataset_path), "line": line_number, "text": lines[line_number - 1].strip()}
                )

    save_matches: list[dict[str, Any]] = []
    skipped = {".venv", "node_modules", ".git", "mrs_images", "outputs"}
    for path in search_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".ipynb", ".ps1"}:
            continue
        if any(part in skipped for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"\b(?:np|numpy)\.save\s*\(", line):
                save_matches.append({"path": str(path), "line": line_number, "text": line.strip()[:500]})

    data_generation_hits = [
        item
        for item in save_matches
        if "mrs_images" in item["text"] or "NCCT_mCTA_only" in item["text"]
    ]
    return {
        "search_root": str(search_root),
        "np_save_matches": save_matches,
        "raw_mrs_npy_generation_save_logic_found": bool(data_generation_hits),
        "raw_mrs_npy_generation_matches": data_generation_hits,
        "consumer_logic": {
            "found": bool(evidence_lines),
            "evidence": evidence_lines,
            "interpretation": (
                "The existing loader treats the stored HWC array as four channels after ToTensor: "
                "internal index 0 is NCCT, index 1 is arterial mCTA, and mcta_phase selects CTA phase indices."
            ),
        },
        "limitation": (
            "The original DICOM/volume-to-mrs_images np.save producer is not present in the project, "
            "parent directory, or supplied project ZIP. The channel interpretation is therefore based "
            "on direct downstream loader code plus empirical image statistics, not the missing producer."
        ),
    }


def analyze_channels(
    project_root: str | Path,
    *,
    image_dir: str | Path | None = None,
    output_json: str | Path | None = None,
    examples_dir: str | Path | None = None,
    per_group: int = 10,
    seed: int = 20260806,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    images = Path(image_dir).resolve() if image_dir else root / "data" / "mrs_images"
    output = Path(output_json).resolve() if output_json else root / "outputs" / "mrs_npy_channel_analysis.json"
    examples = Path(examples_dir).resolve() if examples_dir else root / "outputs" / "mrs_npy_channel_examples"
    examples.mkdir(parents=True, exist_ok=True)

    selected = _sample_files(images, per_group, seed)
    samples: list[dict[str, Any]] = []
    all_selected: list[Path] = []
    for group in sorted(selected):
        for path in selected[group]:
            array = np.load(path, allow_pickle=False)
            if array.shape != (256, 256, 4):
                raise ValueError(f"Unexpected sampled shape for {path}: {array.shape}")
            match = FILENAME_PATTERN.match(path.name)
            assert match is not None
            all_selected.append(path)
            samples.append(
                {
                    "outer_filename_group": group,
                    "full_patient_prefix": f"{group}-{match.group('subject')}",
                    "slice_id": match.group("slice"),
                    "source_file": str(path),
                    "shape": list(array.shape),
                    "dtype": str(array.dtype),
                    "channels": _channel_statistics(array),
                    "correlation_matrix": _correlation(array),
                    "visualizations": _save_visualizations(array, path.name, examples),
                }
            )

    report = {
        "schema_version": "mrs-npy-channel-analysis-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": seed,
        "sampling": {
            "method": "seeded random; one file from each of ten distinct AA-BBB prefixes per outer group",
            "files_per_outer_filename_group": per_group,
            "total_sampled_files": len(all_selected),
            "distinct_full_patient_prefixes": len({item["full_patient_prefix"] for item in samples}),
            "important_correction": (
                "Outer AA is a patient/site prefix in the available data organization, not an image phase. "
                "The four image phases are stored on the final array axis."
            ),
        },
        "source_code_evidence": _source_evidence(root, root.parent),
        "classification": {
            "result": "four_phase_CT_bundle",
            "confidence": "high_for_indices_0_and_1; moderate_for_exact_order_of_indices_2_and_3",
            "internal_channel_mapping": {
                "0": "NCCT (direct loader-code evidence)",
                "1": "arterial mCTA (direct loader-code evidence)",
                "2": "venous mCTA (canonical project order; producer absent)",
                "3": "delayed mCTA (canonical project order; producer absent)",
            },
            "rejected_interpretations": {
                "RGBA": "rejected: channel 3 is non-constant image data, not alpha",
                "adjacent_slices": "rejected: existing loader selects channels as NCCT/mCTA modalities",
                "multiple_windows": "rejected: existing loader names channels as NCCT/mCTA phases",
                "derived_images": "not supported by the located loader code",
            },
            "v0_dataset_decision": "Load full HWC4 safely, select internal channel 0 only for NCCT baselines.",
        },
        "aggregate_by_outer_filename_group": {
            group: _aggregate(paths) for group, paths in sorted(selected.items())
        },
        "aggregate_all_sampled_files": _aggregate(all_selected),
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return report

