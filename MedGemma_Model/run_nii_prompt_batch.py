import argparse
import datetime as dt
import json
import os
from typing import List

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

from image_preprocessing import ImagePreprocessor


DEFAULT_PROMPT = (
    "你是一名神经影像科医生。请阅读这张头颅CT（NCCT）切片，"
    "重点关注是否存在出血或缺血/梗死征象、占位效应、"
    "中线移位、脑室受压或脑沟消失等表现，并给出影像学结论与建议。"
    "如果无法判断，请说明不确定的原因。"
    "用中文回答我的问题。"
)


def _resolve_model_dir(model_dir: str) -> str:
    if model_dir:
        return os.path.abspath(model_dir)
    return os.path.abspath(os.path.dirname(__file__))


def _resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def _resolve_dtype(dtype: str, device: str) -> torch.dtype:
    if dtype == "auto":
        if device == "cuda":
            if (
                hasattr(torch.cuda, "is_bf16_supported")
                and torch.cuda.is_bf16_supported()
            ):
                return torch.bfloat16
            return torch.float16
        return torch.float32
    if dtype == "bf16":
        return torch.bfloat16
    if dtype == "fp16":
        return torch.float16
    return torch.float32


def _parse_bool(value: str) -> bool:
    if value is None:
        return True
    value = value.strip().lower()
    if value in ("1", "true", "yes", "y"):
        return True
    if value in ("0", "false", "no", "n"):
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _load_prompt(prompt: str, prompt_file: str) -> str:
    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    if prompt:
        return prompt.strip()
    return DEFAULT_PROMPT


def _collect_nii_files(input_path: str) -> List[str]:
    if os.path.isfile(input_path) and input_path.endswith(".nii.gz"):
        return [input_path]
    if os.path.isdir(input_path):
        return [
            os.path.join(input_path, f)
            for f in sorted(os.listdir(input_path))
            if f.endswith(".nii.gz")
        ]
    return []


def _build_output_path(output_arg: str, input_path: str) -> str:
    if output_arg:
        return output_arg
    base = os.path.splitext(os.path.basename(input_path))[0]
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    return os.path.join(results_dir, f"medgemma_{base}_{timestamp}.json")


def _generate_response(
    model, processor, image, prompt, max_new_tokens, temperature, top_p
):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device, dtype=next(model.parameters()).dtype)

    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": temperature > 0,
        "temperature": temperature,
        "top_p": top_p,
    }

    with torch.inference_mode():
        generation = model.generate(**inputs, **gen_kwargs)

    input_len = inputs["input_ids"].shape[-1]
    generation = generation[0][input_len:]
    return processor.decode(generation, skip_special_tokens=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="MedGemma NIfTI batch inference")
    parser.add_argument(
        "--input", type=str, required=True, help="NIfTI file or directory"
    )
    parser.add_argument("--prompt", type=str, default="", help="Prompt text")
    parser.add_argument("--prompt-file", type=str, default="", help="Prompt file path")
    parser.add_argument("--axis", type=int, default=2, help="Slice axis (0/1/2)")
    parser.add_argument(
        "--slice-start", type=int, default=0, help="Start slice index (inclusive)"
    )
    parser.add_argument(
        "--slice-end",
        type=int,
        default=-1,
        help="End slice index (inclusive), -1 means last",
    )
    parser.add_argument("--slice-step", type=int, default=1, help="Slice step")
    parser.add_argument(
        "--max-slices", type=int, default=0, help="Max slices to process (0 = no limit)"
    )
    parser.add_argument("--output", type=str, default="", help="Output JSON path")
    parser.add_argument("--model-dir", type=str, default="", help="Local model dir")
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cuda", "cpu"],
        default="auto",
        help="Device to use (default: auto)",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        choices=["auto", "bf16", "fp16", "fp32"],
        default="auto",
        help="Torch dtype (default: auto)",
    )
    parser.add_argument(
        "--local-files-only",
        type=str,
        default="true",
        help="Force offline loading: true/false (default: true)",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=2000, help="Max new tokens"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.0, help="Sampling temperature"
    )
    parser.add_argument("--top-p", type=float, default=1.0, help="Top-p sampling")

    args = parser.parse_args()

    model_dir = _resolve_model_dir(args.model_dir)
    device = _resolve_device(args.device)
    dtype = _resolve_dtype(args.dtype, device)
    local_files_only = _parse_bool(args.local_files_only)
    prompt_text = _load_prompt(args.prompt, args.prompt_file)

    if device == "cuda" and not torch.cuda.is_available():
        print("Error: CUDA requested but not available.")
        return 1

    if device == "cpu" and dtype in (torch.float16, torch.bfloat16):
        print("Warning: fp16/bf16 on CPU may be unsupported; consider fp32.")

    nii_files = _collect_nii_files(args.input)
    if not nii_files:
        print(f"No .nii.gz files found at: {args.input}")
        return 1

    model_kwargs = {
        "torch_dtype": dtype,
        "device_map": "auto" if device == "cuda" else "cpu",
        "low_cpu_mem_usage": True,
        "local_files_only": local_files_only,
    }

    try:
        model = AutoModelForImageTextToText.from_pretrained(model_dir, **model_kwargs)
        processor = AutoProcessor.from_pretrained(
            model_dir, local_files_only=local_files_only
        )
    except Exception as exc:
        print(f"Model load failed: {exc}")
        return 1

    results = {
        "meta": {
            "model_dir": model_dir,
            "device": device,
            "dtype": str(dtype),
            "axis": args.axis,
            "prompt": prompt_text,
            "max_new_tokens": args.max_new_tokens,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "timestamp": dt.datetime.now().isoformat(),
        },
        "files": [],
    }

    total_processed = 0
    for file_path in nii_files:
        preprocessor = ImagePreprocessor(file_path)
        if not preprocessor.load_image():
            results["files"].append(
                {
                    "file_name": os.path.basename(file_path),
                    "file_path": file_path,
                    "slice_count": 0,
                    "error": "Failed to load NIfTI",
                    "slices": [],
                }
            )
            continue

        slice_count = preprocessor.image_data.shape[args.axis]
        slice_start = max(args.slice_start, 0)
        slice_end = (
            slice_count - 1
            if args.slice_end < 0
            else min(args.slice_end, slice_count - 1)
        )
        slice_step = max(args.slice_step, 1)

        file_entry = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "slice_count": slice_count,
            "slices": [],
        }

        for slice_idx in range(slice_start, slice_end + 1, slice_step):
            if args.max_slices and total_processed >= args.max_slices:
                break
            try:
                slice_data = preprocessor.get_slice(slice_idx, args.axis)
                if slice_data is None:
                    raise ValueError("Slice data is None")
                image = preprocessor.convert_to_pil(slice_data)
                if image is None:
                    raise ValueError("Failed to convert slice to PIL")
                answer = _generate_response(
                    model,
                    processor,
                    image,
                    prompt_text,
                    args.max_new_tokens,
                    args.temperature,
                    args.top_p,
                )
            except Exception as exc:
                answer = f"ERROR: {exc}"

            file_entry["slices"].append(
                {
                    "slice_index": slice_idx,
                    "prompt": prompt_text,
                    "answer": answer,
                }
            )
            total_processed += 1

        results["files"].append(file_entry)

    output_path = _build_output_path(args.output, args.input)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved results: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
