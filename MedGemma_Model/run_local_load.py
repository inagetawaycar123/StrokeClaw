import argparse
import os
import time

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor


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


def main() -> int:
    parser = argparse.ArgumentParser(description="MedGemma local model load verifier")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="",
        help="Path to local MedGemma_Model directory (default: script directory)",
    )
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
        "--offload-dir",
        type=str,
        default="",
        help="Optional offload folder for low VRAM",
    )

    args = parser.parse_args()

    model_dir = _resolve_model_dir(args.model_dir)
    device = _resolve_device(args.device)
    dtype = _resolve_dtype(args.dtype, device)
    local_files_only = _parse_bool(args.local_files_only)

    print("=" * 60)
    print("MedGemma local load check")
    print(f"Model dir: {model_dir}")
    print(f"Device: {device}")
    print(f"Dtype: {dtype}")
    print(f"Local files only: {local_files_only}")
    if args.offload_dir:
        print(f"Offload dir: {args.offload_dir}")
    print("=" * 60)

    if device == "cuda" and not torch.cuda.is_available():
        print("Error: CUDA requested but not available.")
        return 1

    if device == "cpu" and dtype in (torch.float16, torch.bfloat16):
        print("Warning: fp16/bf16 on CPU may be unsupported; consider fp32.")

    start_time = time.time()
    model_kwargs = {
        "torch_dtype": dtype,
        "device_map": "auto" if device == "cuda" else "cpu",
        "low_cpu_mem_usage": True,
        "local_files_only": local_files_only,
    }
    if args.offload_dir:
        model_kwargs["offload_folder"] = args.offload_dir

    try:
        model = AutoModelForImageTextToText.from_pretrained(model_dir, **model_kwargs)
        processor = AutoProcessor.from_pretrained(
            model_dir, local_files_only=local_files_only
        )
    except Exception as exc:
        print(f"Load failed: {exc}")
        return 1

    elapsed = time.time() - start_time
    print(f"Load success. Time: {elapsed:.2f}s")
    print(f"Model device: {model.device}")
    print(f"Processor type: {type(processor)}")

    if device == "cuda":
        print(f"CUDA devices: {torch.cuda.device_count()}")
        print(f"CUDA current: {torch.cuda.current_device()}")
        print(f"CUDA name: {torch.cuda.get_device_name(0)}")
        print(
            f"CUDA total memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
