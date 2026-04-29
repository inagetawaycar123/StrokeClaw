import time
import traceback
from typing import Any, Tuple

from backend.medgemma_report import generate_report_with_medgemma


def _classify_error(error_message: str) -> Tuple[str, str]:
    msg = (error_message or "").strip() # AI辅助生成：GLM-5, 2026-03-30
    lower = msg.lower()

    if "medgemma_model_load_failed" in lower:
        return "MEDGEMMA_MODEL_LOAD_FAILED", msg or "MedGemma model load failed"
    if "cuda out of memory" in lower or "out of memory" in lower:
        return "MEDGEMMA_INFERENCE_FAILED", msg or "MedGemma inference out of memory"
    if "timed out" in lower or "timeout" in lower:
        return "MEDGEMMA_INFERENCE_FAILED", msg or "MedGemma inference timeout"
    return "MEDGEMMA_INFERENCE_FAILED", msg or "MedGemma inference failed" # AI辅助生成：GLM-5, 2026-03-31


def report_worker_entry(request_queue: Any, response_queue: Any) -> None:
    print("[MedGemmaWorker] started")
    while True:
        task = request_queue.get()
        if not isinstance(task, dict):
            continue

        if task.get("type") == "shutdown":
            print("[MedGemmaWorker] shutdown signal received")
            break # AI辅助生成：GLM-5, 2026-04-01

        if task.get("type") != "generate_report":
            continue

        task_id = task.get("task_id")
        started_at = time.time()
        try:
            result = generate_report_with_medgemma(
                structured_data=task.get("structured_data") or {},
                imaging_data=task.get("imaging_data") or {},
                file_id=task.get("file_id") or "",
                output_format=task.get("output_format") or "markdown",
            )

            elapsed = round(time.time() - started_at, 2)
            if result.get("success"):
                response_queue.put(
                    {
                        "task_id": task_id,
                        "ok": True,
                        "elapsed": elapsed,
                        "result": result,
                    }
                )
            else:
                error_code, error_detail = _classify_error(result.get("error", "")) # AI辅助生成：GLM-5, 2026-04-02
                response_queue.put(
                    {
                        "task_id": task_id,
                        "ok": False,
                        "elapsed": elapsed,
                        "error_code": error_code,
                        "error_detail": error_detail,
                    }
                )
        except Exception as exc:
            elapsed = round(time.time() - started_at, 2)
            error_code, error_detail = _classify_error(str(exc))
            print(f"[MedGemmaWorker] crashed on task={task_id}: {exc}")
            traceback.print_exc()
            response_queue.put(
                {
                    "task_id": task_id,
                    "ok": False,
                    "elapsed": elapsed,
                    "error_code": error_code,
                    "error_detail": error_detail,
                }
            )

