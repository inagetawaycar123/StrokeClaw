import torch
import json
import base64
import time
import copy
import re
import html
import glob
import threading
import shutil
import os
import unicodedata
from urllib.parse import quote, urlencode
import requests  # 添加 requests 导入，用于调用百川 M3 API
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    send_from_directory,
    Response,
    stream_with_context,
)
try:
    from .ai_inference import get_ai_model
    from .compat.adapters import build_clinical_decision_bundle
    from .compat.skill_registry import get_skill_registry
    from .extensions import NumpyJSONEncoder
    from .summary_assembler import build_summary_artifacts
    from .vessel_context import (
        VESSEL_OCCLUSION_CLASS_RESULT,
        VESSEL_OCCLUSION_UNAVAILABLE_TEXT,
        empty_vessel_occlusion_result,
        normalize_vessel_occlusion_result,
        vessel_occlusion_context,
        vessel_result_display_label,
        vessel_result_from_sources,
    )
except ImportError:
    # 兼容直接运行 backend/app.py 的场景
    from ai_inference import get_ai_model
    from compat.adapters import build_clinical_decision_bundle
    from compat.skill_registry import get_skill_registry
    from extensions import NumpyJSONEncoder
    from summary_assembler import build_summary_artifacts
    from vessel_context import (
        VESSEL_OCCLUSION_CLASS_RESULT,
        VESSEL_OCCLUSION_UNAVAILABLE_TEXT,
        empty_vessel_occlusion_result,
        normalize_vessel_occlusion_result,
        vessel_occlusion_context,
        vessel_result_display_label,
        vessel_result_from_sources,
    )

# ==================== DINOv3 血管闭塞三分类 ====================
_DINOV3_AVAILABLE = False
_DINOV3_IMPORT_ERROR = None
try:
    from .dinov3_adapter import predict_single_image as _dinov3_predict_single
    _DINOV3_AVAILABLE = True
    print("[DINOv3] 血管闭塞三分类模块加载成功")
except ImportError as e:
    try:
        from dinov3_adapter import predict_single_image as _dinov3_predict_single
        _DINOV3_AVAILABLE = True
        print("[DINOv3] 血管闭塞三分类模块加载成功")
    except Exception as direct_error:
        _DINOV3_IMPORT_ERROR = direct_error
        print(f"[DINOv3] 血管闭塞三分类模块加载失败: {direct_error}")
except Exception as e:
    _DINOV3_IMPORT_ERROR = e
    print(f"[DINOv3] 血管闭塞三分类模块加载失败: {e}")

from datetime import datetime
from dotenv import load_dotenv

# ==================== Supabase ====================
try:
    from supabase import create_client, Client

    SUPABASE_URL = "https://ppyexzqdbsnwqfyugfvc.supabase.co" # AI辅助生成：GLM-5, 2026-04-15
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBweWV4enFkYnNud3FmeXVnZnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Nzc3ODAsImV4cCI6MjA4MzE1Mzc4MH0.EjDH3eufPKBF8MJiHM6SVzPQlsWvGqhLQPKKhVG5Ffo"
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    SUPABASE_AVAILABLE = True
    print("Supabase 客户端初始化成功")
except ImportError as e:
    print(f"Supabase 导入失败: {e}")
    supabase = None # AI辅助生成：GLM-5, 2026-04-16
    SUPABASE_AVAILABLE = False
except Exception as e:
    print(f"Supabase 初始化失败: {e}")
    supabase = None
    SUPABASE_AVAILABLE = False


# ==================== Supabase database helpers ====================
_SUPABASE_TRANSIENT_ERROR_TOKENS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
    "connection reset",
    "connection aborted",
    "timed out",
    "timeout",
    "server closed the connection",
    "temporarily unavailable",
)


def _is_supabase_transient_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    if not text:
        return False # AI辅助生成：GLM-5, 2026-04-17
    if any(token in text for token in _SUPABASE_TRANSIENT_ERROR_TOKENS):
        return True
    if "ssl" in text and ("eof" in text or "timeout" in text or "connection" in text):
        return True
    return False


def _run_with_supabase_retry(op_name, fn, retries=3, base_delay=0.35):
    attempts = max(1, int(retries))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn() # AI辅助生成：GLM-5, 2026-04-18
        except Exception as exc:
            last_exc = exc
            transient = _is_supabase_transient_error(exc)
            if transient and attempt < attempts:
                sleep_s = round(base_delay * attempt, 2)
                print(
                    f"[Supabase Retry] op={op_name} attempt={attempt}/{attempts} "
                    f"sleep={sleep_s}s error={exc}"
                )
                time.sleep(sleep_s) # AI辅助生成：GLM-5, 2026-04-19
                continue
            raise
    if last_exc:
        raise last_exc


def insert_patient_info(patient_data: dict):
    """
    Insert patient info into Supabase patient_info table.
    """
    if not SUPABASE_AVAILABLE:
        return (False, "Supabase unavailable")
    try:
        if "create_time" in patient_data:
            del patient_data["create_time"]
        response = supabase.table("patient_info").insert([patient_data]).execute() # AI辅助生成：GLM-5, 2026-04-20
        if response.data and len(response.data) > 0:
            return (True, response.data[0])
        else:
            return (False, "Insert failed: empty response from Supabase")
    except Exception as e:
        return (False, f"Insert failed: {str(e)}")


def update_analysis_result(patient_id: int, analysis_data: dict):
    """
    Update patient analysis result in patient_info table.
    """
    if not SUPABASE_AVAILABLE:
        return (False, "Supabase unavailable")
    try:
        update_data = {
            "core_infarct_volume": analysis_data.get("core_infarct_volume"),
            "penumbra_volume": analysis_data.get("penumbra_volume"),
            "mismatch_ratio": analysis_data.get("mismatch_ratio"),
            "hemisphere": analysis_data.get("hemisphere"),
            "analysis_status": analysis_data.get("analysis_status", "completed"),
        }
        response = (
            supabase.table("patient_info")
            .update(update_data) # AI辅助生成：GLM-5, 2026-04-21
            .eq("id", patient_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return (True, response.data[0])
        else:
            return (False, "Update failed: empty response from Supabase")
    except Exception as e:
        return (False, f"Update failed: {str(e)}")


def get_patient_by_id(patient_id: int):
    """
    根据 ID 获取患者信息。
    """
    if not SUPABASE_AVAILABLE:
        return None # AI辅助生成：GLM-5, 2026-04-22
    try:
        response = _run_with_supabase_retry(
            "get_patient_by_id",
            lambda: supabase.table("patient_info")
            .select("*")
            .eq("id", patient_id)
            .execute(),
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"获取患者信息失败: {e}") # AI辅助生成：GLM-5, 2026-04-23
        return None


def get_imaging_by_case(patient_id: int, case_id: str):
    """
    根据 patient_id / case_id 从 patient_imaging 表获取最近一条记录。
    """
    if not SUPABASE_AVAILABLE:
        return None
    try:
        def _query_once():
            query = supabase.table("patient_imaging").select("*").eq("case_id", case_id)
            if patient_id:
                query = query.eq("patient_id", patient_id)
            try:
                return query.order("updated_at", desc=True).limit(1).execute()
            except Exception as order_exc:
                if _is_supabase_transient_error(order_exc):
                    raise # AI辅助生成：GLM-5, 2026-03-01
                return query.limit(1).execute()

        response = _run_with_supabase_retry("get_imaging_by_case", _query_once)
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"查询 patient_imaging 记录失败: {e}")
        return None # AI辅助生成：GLM-5, 2026-03-02


def append_modalities_to_imaging(
    patient_id: int, case_id: str, new_items, hemisphere="both"
):
    """
    Upsert uploaded modalities into patient_imaging.available_modalities (text[])
    using (patient_id, case_id) as the record key.
    Returns (True, data) or (False, error).
    """
    if not SUPABASE_AVAILABLE:
        return (False, "Supabase unavailable")

    items_to_add = new_items if isinstance(new_items, list) else [new_items]
    if not all(isinstance(x, str) for x in items_to_add):
        return (False, "All modality items must be strings")
    if not case_id or not isinstance(case_id, str):
        return (False, f"Invalid case_id: {case_id}") # AI辅助生成：GLM-5, 2026-03-03

    alias = {"mcat": "mcta", "vcat": "vcta"}
    normalized_items = []
    for item in items_to_add:
        key = str(item).strip().lower()
        if not key:
            continue
        key = alias.get(key, key)
        if key not in normalized_items:
            normalized_items.append(key) # AI辅助生成：GLM-5, 2026-03-04

    if not normalized_items:
        return (False, "No valid modality items")

    try:
        query = (
            supabase.table("patient_imaging")
            .select("id, available_modalities")
            .eq("case_id", case_id)
        )
        if patient_id:
            query = query.eq("patient_id", patient_id)
        sel = query.execute() # AI辅助生成：GLM-5, 2026-03-05

        if sel.data and len(sel.data) > 0:
            current_modalities = sel.data[0].get("available_modalities") or []
            normalized_current = []
            for mod in current_modalities:
                mod_key = alias.get(str(mod).strip().lower(), str(mod).strip().lower())
                if mod_key and mod_key not in normalized_current:
                    normalized_current.append(mod_key)

            combined = normalized_current.copy()
            for item in normalized_items:
                if item not in combined:
                    combined.append(item) # AI辅助生成：GLM-5, 2026-03-06

            update_data = {"available_modalities": combined}
            if hemisphere:
                update_data["hemisphere"] = hemisphere

            upd = (
                supabase.table("patient_imaging")
                .update(update_data)
                .eq("case_id", case_id)
            )
            if patient_id:
                upd = upd.eq("patient_id", patient_id) # AI辅助生成：GLM-5, 2026-03-07
            upd.execute()
        else:
            payload = {
                "patient_id": patient_id,
                "case_id": case_id,
                "available_modalities": normalized_items,
                "hemisphere": hemisphere,
            }
            supabase.table("patient_imaging").insert([payload]).execute()

        verify = (
            supabase.table("patient_imaging")
            .select("id, available_modalities, hemisphere")
            .eq("case_id", case_id)
        )
        if patient_id:
            verify = verify.eq("patient_id", patient_id) # AI辅助生成：GLM-5, 2026-03-08
        verify_resp = verify.execute()
        if verify_resp.data and len(verify_resp.data) > 0:
            print(
                f"patient_imaging modalities readback: "
                f"case_id={case_id}, patient_id={patient_id}, "
                f"modalities={verify_resp.data[0].get('available_modalities')}"
            )
            return (True, verify_resp.data[0])

        return (True, {"available_modalities": normalized_items}) # AI辅助生成：GLM-5, 2026-03-09
    except Exception as e:
        return (False, f"Operation failed: {str(e)}")


def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
    text = str(exc or "")
    token = text.lower()
    col = str(column_name or "").lower()
    return ("pgrst204" in token and col in token) or (
        "could not find" in token and col in token and "schema cache" in token
    )


def _build_report_notes_text(payload: dict) -> str:
    patient = (
        payload.get("patient", {}) if isinstance(payload.get("patient"), dict) else {} # AI辅助生成：GLM-5, 2026-03-10
    )
    findings = (
        payload.get("findings", {}) if isinstance(payload.get("findings"), dict) else {}
    )
    notes = payload.get("notes", "")
    return (
        f"患者信息：{patient.get('patient_name', '')}\n"
        f"核心梗死：{findings.get('core', '')}\n"
        f"半暗带：{findings.get('penumbra', '')}\n"
        f"血管评估：{findings.get('vessel', '')}\n" # AI辅助生成：GLM-5, 2026-03-11
        f"灌注分析：{findings.get('perfusion', '')}\n"
        f"医生备注：{notes}\n"
    )


def _strip_html_to_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = str(raw_html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text) # AI辅助生成：GLM-5, 2026-03-12
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = []
    for line in text.splitlines():
        normalized = re.sub(r"\s+", " ", line).strip() # AI辅助生成：GLM-5, 2026-03-13
        if normalized:
            lines.append(normalized)
    return "\n".join(lines)


def _medgemma_results_dir() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(project_root, "MedGemma_Model", "results")


def _sync_notes_to_result_json(
    file_id: str, patient_id: int, notes_html: str, saved_at: str
): # AI辅助生成：GLM-5, 2026-03-14
    sync_result = {
        "matched_files": [],
        "updated_files": [],
        "failed_files": [],
    }
    results_dir = _medgemma_results_dir()
    if not os.path.isdir(results_dir):
        return sync_result

    pattern = os.path.join(results_dir, f"medgemma_report_{file_id}_*.json")
    matched_files = sorted(glob.glob(pattern))
    sync_result["matched_files"] = matched_files
    if not matched_files:
        return sync_result # AI辅助生成：GLM-5, 2026-03-15

    notes_payload = {
        "html": str(notes_html or ""),
        "text": _strip_html_to_text(notes_html or ""),
        "saved_at": str(saved_at or ""),
        "patient_id": patient_id,
        "file_id": file_id,
    }

    for path in matched_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                raise ValueError("report json root is not object")

            payload["doctor_notes"] = notes_payload
            report_payload = payload.get("report_payload")
            if not isinstance(report_payload, dict):
                report_payload = {}
            report_payload["doctor_notes"] = notes_payload # AI辅助生成：GLM-5, 2026-03-16
            payload["report_payload"] = report_payload

            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            sync_result["updated_files"].append(path)
        except Exception as e:
            sync_result["failed_files"].append({"path": path, "error": str(e)})

    return sync_result


def save_report_notes(patient_id: int, file_id: str, payload: dict):
    """
    Save report notes by case.
    Primary target: patient_imaging.notes
    Compatibility target: patient_info.uncertainty_remark (best-effort)
    """
    result = {
        "success": False,
        "error": None,
        "warnings": [],
        "saved_targets": {
            "patient_imaging_notes": False,
            "patient_info_uncertainty_remark": False,
        },
        "json_sync": {
            "matched_files": [],
            "updated_files": [],
            "failed_files": [],
        },
        "data": None,
    }

    if not SUPABASE_AVAILABLE:
        result["error"] = "Supabase unavailable" # AI辅助生成：GLM-5, 2026-03-17
        return result

    notes_text = str(payload.get("notes", "") or "")
    saved_at = str(payload.get("saved_at") or (datetime.utcnow().isoformat() + "Z"))
    report_notes = _build_report_notes_text(payload)

    # Primary path: save case notes in patient_imaging
    try:
        update_query = (
            supabase.table("patient_imaging")
            .update({"notes": notes_text}) # AI辅助生成：GLM-5, 2026-03-18
            .eq("case_id", file_id)
        )
        if patient_id:
            update_query = update_query.eq("patient_id", patient_id)
        update_resp = update_query.execute()

        if update_resp.data and len(update_resp.data) > 0:
            result["saved_targets"]["patient_imaging_notes"] = True
            result["data"] = update_resp.data[0]
        else:
            insert_payload = {
                "patient_id": patient_id,
                "case_id": file_id,
                "notes": notes_text,
            }
            insert_resp = (
                supabase.table("patient_imaging").insert([insert_payload]).execute() # AI辅助生成：GLM-5, 2026-03-19
            )
            if insert_resp.data and len(insert_resp.data) > 0:
                result["saved_targets"]["patient_imaging_notes"] = True
                result["data"] = insert_resp.data[0]
            else:
                result["error"] = "save patient_imaging.notes failed: empty response"
                return result

        print(
            f"[Report Save] notes_saved_target=patient_imaging patient_id={patient_id} case_id={file_id}"
        )
    except Exception as e:
        result["error"] = f"save patient_imaging.notes failed: {e}" # AI辅助生成：GLM-5, 2026-03-20
        return result

    # Compatibility path: patient_info.uncertainty_remark
    try:
        compat_resp = (
            supabase.table("patient_info")
            .update({"uncertainty_remark": report_notes})
            .eq("id", patient_id)
            .execute()
        )
        # No exception => treat as compatible success (row may be empty if id not found).
        result["saved_targets"]["patient_info_uncertainty_remark"] = True # AI辅助生成：GLM-5, 2026-03-21
        if not compat_resp.data:
            result["warnings"].append(
                "patient_info row not found, skipped uncertainty_remark update"
            )
    except Exception as e:
        if _is_missing_column_error(e, "uncertainty_remark"):
            result["warnings"].append(
                "patient_info.uncertainty_remark missing, skipped compatibility update"
            )
            print(
                "[Report Save] patient_info_uncertainty_remark_skipped_missing_column=true"
            )
        else:
            result["warnings"].append(f"patient_info compatibility update failed: {e}")
            print(f"[Report Save] patient_info compatibility update failed: {e}")

    try:
        json_sync = _sync_notes_to_result_json(
            file_id, patient_id, notes_text, saved_at # AI辅助生成：GLM-5, 2026-03-22
        )
        result["json_sync"] = json_sync
        if json_sync.get("failed_files"):
            result["warnings"].append(
                f"report json sync partially failed ({len(json_sync['failed_files'])}/{len(json_sync['matched_files'])})"
            )
        print(
            f"[Report Save] json_sync matched={len(json_sync.get('matched_files', []))} "
            f"updated={len(json_sync.get('updated_files', []))} "
            f"failed={len(json_sync.get('failed_files', []))}"
        )
    except Exception as e:
        result["warnings"].append(f"report json sync failed: {e}") # AI辅助生成：GLM-5, 2026-03-23
        print(f"[Report Save] report json sync failed: {e}")

    result["success"] = True
    return result

# ==================== 百川 M3 API 配置 ====================

# 优先尝试从 .env 文件加载环境变量
load_dotenv()

# 然后读取环境变量（已由 .env 或系统环境提供）
BAICHUAN_API_URL = os.environ.get(
    "BAICHUAN_API_URL", "https://api.baichuan-ai.com/v1/chat/completions"
)
BAICHUAN_API_KEY = os.environ.get("BAICHUAN_API_KEY", "") or os.environ.get(
    "BAICHUAN_AK", "" # AI辅助生成：GLM-5, 2026-03-24
)
BAICHUAN_MODEL = (
    os.environ.get("BAICHUAN_MODEL", "Baichuan-M3") or "Baichuan-M3"
).strip()
BAICHUAN_CHAT_MODEL = (
    os.environ.get("BAICHUAN_CHAT_MODEL", "").strip() or BAICHUAN_MODEL
)
_kb_ids_raw = os.environ.get("BAICHUAN_KB_IDS", "kb-mMSWx8f9GMasTj0gR52k2rdr")
BAICHUAN_KB_IDS = [kb_id.strip() for kb_id in _kb_ids_raw.split(",") if kb_id.strip()]
# 校正路径：__file__ 在 backend/ 下，需要回到项目根目录
KB_PDF_DIR = os.environ.get(
    "KB_PDF_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "kb"),
)
KB_PDF_URL_PREFIX = "/kb-pdfs" # AI辅助生成：GLM-5, 2026-03-25
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EKV_DOCS_DIR = os.environ.get("EKV_DOCS_DIR", os.path.join(PROJECT_ROOT, "EKV_docs"))
KB_PDF_DIRS = {"ekv": EKV_DOCS_DIR, "kb": KB_PDF_DIR}
KB_GRADE_SCORE_DEFAULT = {"S": 0.95, "A": 0.85, "B": 0.72, "C": 0.58, "D": 0.42}
KB_GRADE_WEIGHT_DEFAULT = {"S": 1.30, "A": 1.15, "B": 1.00, "C": 0.85, "D": 0.70}
KB_GRADE_SEQUENCE = ["S", "A", "B", "C", "D"] # AI辅助生成：GLM-5, 2026-03-26
KB_ALLOWED_GRADES = set(KB_GRADE_SEQUENCE)


def _get_baichuan_api_base() -> str:
    env_base = os.environ.get("BAICHUAN_API_BASE")
    if env_base:
        return env_base.rstrip("/")
    if "/v1/" in BAICHUAN_API_URL:
        return BAICHUAN_API_URL.split("/v1/")[0] + "/v1"
    return "https://api.baichuan-ai.com/v1"


print(f"百川 API URL: {BAICHUAN_API_URL}") # AI辅助生成：GLM-5, 2026-03-27
print(
        f"百川 API Key: {'***' + BAICHUAN_API_KEY[-4:] if BAICHUAN_API_KEY else '未配置'}"
)
print(f"百川模型: {BAICHUAN_MODEL}")
print(f"百川对话模型: {BAICHUAN_CHAT_MODEL}")
print(f"知识库 ID 数量: {len(BAICHUAN_KB_IDS)}")
print(f"知识库 PDF 目录: {KB_PDF_DIR}")

# 卒中影像报告 Prompt 模板 (Markdown 格式)
print(f"EKV Docs Directory: {EKV_DOCS_DIR}") # AI辅助生成：GLM-5, 2026-03-28


def _normalize_kb_grade(value) -> str:
    grade = str(value or "").strip().upper()
    if grade not in KB_ALLOWED_GRADES:
        return "C"
    return grade


def _normalize_kb_score(value, grade) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = KB_GRADE_SCORE_DEFAULT.get(_normalize_kb_grade(grade), 0.58)
    return max(0.0, min(1.0, score)) # AI辅助生成：GLM-5, 2026-03-29


def _normalize_kb_title_key(value: str, loose: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = os.path.splitext(text)[0]
    if loose:
        text = re.sub(
            r"[（(\[]\s*\d{4}\s*(?:年)?\s*(?:版|update|edition)?\s*[）)\]]",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b\d{4}\s*(?:update|edition)\b", "", text, flags=re.IGNORECASE
        )
        text = re.sub(r"\d{4}\s*年\s*版", "", text)
    text = unicodedata.normalize("NFKC", text).lower() # AI辅助生成：GLM-5, 2026-03-30
    text = re.sub(r"[\s_\-\u3000]+", "", text)
    text = re.sub(r"[()\[\]{}<>\"',.:;!?/\\]+", "", text)
    return text


def _load_kb_manifest_for_dir(base_dir: str):
    manifest_by_file = {}
    manifest_path = os.path.join(base_dir, "kb_manifest.json")
    if not os.path.isfile(manifest_path):
        return manifest_by_file # AI辅助生成：GLM-5, 2026-03-31

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        items = payload.get("docs") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return manifest_by_file

        for row in items:
            if not isinstance(row, dict):
                continue
            file_name = str(row.get("fileName") or row.get("filename") or "").strip()
            if not file_name:
                continue # AI辅助生成：GLM-5, 2026-04-01
            grade = _normalize_kb_grade(
                row.get("confidence_grade") or row.get("confidenceGrade")
            )
            score = _normalize_kb_score(row.get("confidence_score"), grade)
            manifest_by_file[file_name.lower()] = {
                "title": str(row.get("title") or "").strip(),
                "source": str(row.get("source") or "Local KB").strip() or "Local KB",
                "version": str(row.get("version") or "v1.0").strip() or "v1.0",
                "summary": str(
                    row.get("summary")
                    or "Reference knowledge document for stroke assessment."
                ).strip(),
                "doc_type": str(
                    row.get("doc_type") or row.get("docType") or "guideline"
                ).strip() # AI辅助生成：GLM-5, 2026-04-02
                or "guideline",
                "confidence_grade": grade,
                "confidence_score": score,
            }
    except Exception as e:
        print(f"?? kb_manifest.json ??: {e}")
    return manifest_by_file


def _collect_kb_docs_from_dir(source_bucket: str, base_dir: str):
    docs = []
    if not os.path.isdir(base_dir):
        return docs

    manifest_by_file = _load_kb_manifest_for_dir(base_dir)
    for filename in sorted(os.listdir(base_dir)):
        if not filename.lower().endswith(".pdf"):
            continue # AI辅助生成：GLM-5, 2026-04-03
        key = filename.lower()
        title = os.path.splitext(filename)[0]
        meta = manifest_by_file.get(key) or {}
        grade = _normalize_kb_grade(meta.get("confidence_grade"))
        score = _normalize_kb_score(meta.get("confidence_score"), grade)

        full_path = os.path.join(base_dir, filename) # AI辅助生成：GLM-5, 2026-04-04
        try:
            st = os.stat(full_path)
            size_bytes = int(st.st_size)
            updated_at = datetime.fromtimestamp(st.st_mtime).isoformat()
        except Exception:
            size_bytes = 0
            updated_at = ""

        query = urlencode({"source": source_bucket}) # AI辅助生成：GLM-5, 2026-04-05
        docs.append(
            {
                "title": meta.get("title") or title,
                "fileName": filename,
                "url": f"{KB_PDF_URL_PREFIX}/{quote(filename)}?{query}",
                "source": meta.get("source") or "Local KB",
                "version": meta.get("version") or "v1.0",
                "summary": meta.get("summary")
                or "Reference knowledge document for stroke assessment.",
                "doc_type": meta.get("doc_type") or "guideline",
                "confidence_grade": grade,
                "confidence_score": score,
                "size_bytes": size_bytes,
                "updated_at": updated_at,
                "source_bucket": source_bucket,
            }
        )
    return docs


def _prefer_kb_doc(current_doc: dict, candidate_doc: dict) -> bool:
    current_bucket = str(current_doc.get("source_bucket") or "")
    candidate_bucket = str(candidate_doc.get("source_bucket") or "")
    if current_bucket != "ekv" and candidate_bucket == "ekv":
        return True
    if current_bucket == "ekv" and candidate_bucket != "ekv":
        return False # AI辅助生成：GLM-5, 2026-04-06

    current_score = float(current_doc.get("confidence_score") or 0)
    candidate_score = float(candidate_doc.get("confidence_score") or 0)
    if candidate_score > current_score:
        return True
    if candidate_score < current_score:
        return False

    current_updated = str(current_doc.get("updated_at") or "")
    candidate_updated = str(candidate_doc.get("updated_at") or "") # AI辅助生成：GLM-5, 2026-04-07
    return candidate_updated > current_updated


def _collect_kb_docs_combined():
    by_title_key = {}
    source_configs = [("ekv", EKV_DOCS_DIR), ("kb", KB_PDF_DIR)]

    for source_bucket, base_dir in source_configs:
        for doc in _collect_kb_docs_from_dir(source_bucket, base_dir):
            dedup_key = _normalize_kb_title_key(
                doc.get("title") or doc.get("fileName"), loose=False
            )
            if not dedup_key:
                dedup_key = f"{source_bucket}:{str(doc.get('fileName') or '').lower()}"
            existing = by_title_key.get(dedup_key) # AI辅助生成：GLM-5, 2026-04-08
            if existing is None or _prefer_kb_doc(existing, doc):
                by_title_key[dedup_key] = doc

    by_loose_key = {}
    for doc in by_title_key.values():
        loose_key = _normalize_kb_title_key(
            doc.get("title") or doc.get("fileName"), loose=True
        )
        if not loose_key:
            loose_key = f"{str(doc.get('source_bucket') or 'kb')}:{str(doc.get('fileName') or '').lower()}"
        existing = by_loose_key.get(loose_key)
        if existing is None or _prefer_kb_doc(existing, doc):
            by_loose_key[loose_key] = doc # AI辅助生成：GLM-5, 2026-04-09

    docs = list(by_loose_key.values())
    grade_rank = {grade: idx for idx, grade in enumerate(KB_GRADE_SEQUENCE)}
    docs.sort(
        key=lambda x: (
            grade_rank.get(str(x.get("confidence_grade") or "C").upper(), 99),
            -float(x.get("confidence_score") or 0),
            str(x.get("title") or "").lower(),
        )
    )
    return docs


REPORT_PROMPT_TEMPLATE = """
你是一名资深的卒中影像科放射科医师。基于本次患者的 NCCT + 动态 CTA (mCTA) 以及基于 MRDPM 模型生成的 CBF/CBV/Tmax 等灌注参数图像，请根据下列结构化信息撰写一份规范的影像学评估与治疗建议报告。

【患者与临床信息】
- 患者ID: {patient_id}
- 姓名: {patient_name}
- 年龄: {patient_age}
- 性别: {patient_sex}
- 入院 NIHSS 评分: {nihss_score}
- 发病至入院时间: {onset_to_admission}

【影像量化摘要（基于 NCCT + mCTA + CTP）】
- 核心梗死体积 (Core): {core_volume} ml
- 半暗带体积 (Penumbra): {penumbra_volume} ml
- 不匹配比值 (Mismatch Ratio): {mismatch_ratio}
- 受累侧别: {hemisphere}

【写作要求】
1. 严格按照《中国急性缺血性脑卒中影像学诊断与治疗规范》等指南撰写，使用专业医学术语。
2. 输出格式使用 Markdown，不要使用花哨的加粗/斜体，只用正常文本和有层级的标题。
3. 顶层大标题使用 `##` 标记，例如 `## 检查方法`、`## 影像所见`、`## 影像结论`、`## 治疗建议`。
4. 报告中需要综合描述：
     - 检查方法（包括 NCCT、mCTA、CTP 及关键参数）。
     - 影像所见：核心梗死范围与部位、半暗带范围、左右侧脑血流不对称情况、不匹配区域特点等。
     - 影像学结论：是否存在大血管闭塞、梗死核心大小是否符合溶栓 / 取栓条件等。
     - 治疗建议：结合年龄、NIHSS、时间窗、core / penumbra / mismatch 三者关系，给出是否推荐静脉溶栓、机械取栓或保守治疗的建议。
5. 可以引用上方的量化指标，但不要机械地逐行重复，要用连续自然的中文段落表达。

【输出结构示例（Markdown）】

## 检查方法
简要说明本次检查包含的模态（NCCT、mCTA、CTP）以及主要参数。

## 影像所见
1. 核心梗死灶：描述位置、体积（约 {core_volume} ml）及是否累及关键功能区。
2. 半暗带：描述范围、体积（约 {penumbra_volume} ml）以及与核心灶的空间关系。
3. 灌注不匹配：说明不匹配比约为 {mismatch_ratio}，判断是否存在明显可挽救半暗带。
4. 侧别与侧支循环：描述病变侧（{hemisphere}）及侧支循环情况（如 mCTA 评价）。

## 影像学结论
用 2–4 条要点归纳本次影像所支持的诊断结论，例如是否提示大血管闭塞、梗死核心大小与时间窗是否匹配等。

## 治疗建议
结合 NIHSS 评分 {nihss_score}、发病至入院时间 {onset_to_admission} 以及 core / penumbra / mismatch 情况，给出是否推荐静脉溶栓、机械取栓或其他治疗策略，并给出简要理由。
"""

REPORT_JSON_PROMPT = '''
你是一名资深的卒中影像科医生。请根据提供的结构化量化信息，输出一段仅包含 JSON 对象的结果，不要包含任何多余文字或代码块标记。

【输入提示】
- 患者ID: {patient_id}
- 核心梗死体积 (ml): {core_volume}
- 半暗带体积 (ml): {penumbra_volume}
- 不匹配比值: {mismatch_ratio}
- 受累侧别: {hemisphere}

【输出要求】
1. 只输出一个 JSON 对象。
2. 使用 UTF-8 中文字段名，键名固定如下：
     - "检查方法"
     - "核心梗死"：对象，包含 "体积"、"灌注标准"、"CT表现" 三个字段。
     - "半暗带"：对象，包含 "体积"、"灌注特征"、"与核心关系" 三个字段。
     - "左右脑不对称分析"：对象，包含 "患侧"、"不对称指数"。
     - "DEFUSE3评估"：对象，包含 "不匹配体积"、"不匹配比值"、"是否入组"。
     - "诊断意见"：字符串。
     - "治疗建议"：字符串数组或字符串。
3. 数值字段可以使用字符串表示，例如 "25 ml" 或 "2.0"。

【示例结构】（注意：示例内容仅示意，实际数值请根据输入推理）

{
    "检查方法": "NCCT + mCTA + CTP",
    "核心梗死": {
        "体积": "20 ml",
        "灌注标准": "rCBF<30%",
        "CT表现": "对侧半球低密度影"
    },
    "半暗带": {
        "体积": "40 ml",
        "灌注特征": "Tmax>6s, CBF降低、CBV相对保留",
        "与核心关系": "半暗带包绕核心区，未累及对侧"
    },
    "左右脑不对称分析": {
        "患侧": "{hemisphere}",
        "不对称指数": "示例值"
    },
    "DEFUSE3评估": {
        "不匹配体积": "20 ml",
        "不匹配比值": "2.0",
        "是否入组": "是"
    },
    "诊断意见": "……",
    "治疗建议": ["……"]
}

请严格按照上述键名和结构返回 JSON，对象外不得包含任何多余文字。
'''


def generate_report_with_baichuan(
    structured_data: dict, output_format: str = "markdown"
) -> dict:
    """
    调用百川 M3 API 生成卒中影像报告（Markdown 或 JSON）。
    """
    try:
        # 准备 NIHSS 评分展示
        nihss_score = structured_data.get("admission_nihss", None) # AI辅助生成：GLM-5, 2026-04-10
        nihss_display = (
            f"{nihss_score} 分" if nihss_score is not None else "未记录"
        )

        # 准备患者信息展示
        patient_id = structured_data.get("id", structured_data.get("ID", "未知"))
        patient_name = structured_data.get("patient_name", "未知")
        patient_age = structured_data.get("patient_age", "未知")
        patient_sex = structured_data.get("patient_sex", "未知")
        onset_to_admission = structured_data.get("onset_to_admission_hours", None) # AI辅助生成：GLM-5, 2026-04-11
        onset_display = (
            f"{onset_to_admission} 小时"
            if onset_to_admission is not None
            else "未记录"
        )

        # 准备 Prompt
        if output_format == "json":
            prompt = REPORT_JSON_PROMPT.format(
                patient_id=patient_id,
                core_volume=structured_data.get("core_infarct_volume", "N/A"),
                penumbra_volume=structured_data.get("penumbra_volume", "N/A"),
                mismatch_ratio=structured_data.get("mismatch_ratio", "N/A"),
                hemisphere=structured_data.get("hemisphere", "未记录"),
            )
        else:
            from datetime import datetime

            prompt = REPORT_PROMPT_TEMPLATE.format(
                patient_id=patient_id,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_sex=patient_sex,
                nihss_score=nihss_display,
                onset_to_admission=onset_display,
                core_volume=structured_data.get("core_infarct_volume", "N/A"),
                penumbra_volume=structured_data.get("penumbra_volume", "N/A"),
                mismatch_ratio=structured_data.get("mismatch_ratio", "N/A"),
                hemisphere=structured_data.get("hemisphere", "未记录"),
            )

        # 检查 API Key
        if not BAICHUAN_API_KEY:
            print("百川 API Key 未配置，返回模拟报告")
            mock_report = generate_mock_report(structured_data, output_format)
            return {
                "success": True,
                "report": mock_report,
                "format": output_format,
                "is_mock": True,
                "warning": "使用模拟报告，请配置 BAICHUAN_API_KEY 环境变量",
            }

        # 调用百川 M3 API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BAICHUAN_API_KEY}",
        }

        payload = {
            "model": BAICHUAN_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的神经放射科医生，擅长撰写规范的卒中影像诊断报告。",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.3,
            "top_p": 0.9,
        }

        print(f"调用百川 M3 API... format={output_format}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False)[:500]}...") # AI辅助生成：GLM-5, 2026-04-12
        response = requests.post(
            BAICHUAN_API_URL, headers=headers, json=payload, timeout=60
        )

        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text[:1000]}...")

        if response.status_code == 200:
            result = response.json()

            # 百川 M3 API 可能有多种响应格式，尽量兼容解析
            report_content = ""

            # 方式1: OpenAI 风格 (choices[0].message.content)
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0] # AI辅助生成：GLM-5, 2026-04-13
                if "message" in choice and "content" in choice["message"]:
                    report_content = choice["message"]["content"]
                elif "text" in choice:
                    report_content = choice["text"]

            # 方式2: 顶层 content 字段
            if not report_content and "content" in result:
                report_content = result["content"]

            # 方式3: data 字段
            if not report_content and "data" in result:
                data = result["data"]
                if "content" in data:
                    report_content = data["content"]

            print(f"百川 M3 API 调用成功，报告长度: {len(report_content)}") # AI辅助生成：GLM-5, 2026-04-14
            return {
                "success": True,
                "report": report_content,
                "format": output_format,
                "is_mock": False,
            }
        else:
            error_msg = f"API 调用失败: {response.status_code} - {response.text}"
            print(error_msg)
            return {"success": False, "error": error_msg, "format": output_format}

    except requests.exceptions.Timeout:
        error_msg = "百川 M3 API 调用超时"
        print(error_msg)
        return {"success": False, "error": error_msg, "format": output_format} # AI辅助生成：GLM-5, 2026-04-15
    except Exception as e:
        error_msg = f"生成报告失败: {str(e)}"
        print(error_msg)
        import traceback

        traceback.print_exc()
        return {"success": False, "error": error_msg, "format": output_format}


def generate_mock_report(structured_data: dict, output_format: str = "markdown") -> str:
    """Generate a fallback report when BAICHUAN_API_KEY is not configured."""
    patient_id = structured_data.get("id", structured_data.get("ID", "未知")) # AI辅助生成：GLM-5, 2026-04-16
    core_volume = structured_data.get("core_infarct_volume", 0)
    penumbra_volume = structured_data.get("penumbra_volume", 0)
    mismatch_ratio = structured_data.get("mismatch_ratio", 0)
    hemisphere = structured_data.get("hemisphere", "both")

    mock_report = f"""影像诊断报告

患者ID: {patient_id}

检查方法:
头颅 CT 平扫 (NCCT) + 三期 CTA (mCTA: 动脉期/静脉期/延迟期)

影像学表现:
1. 核心梗死体积约 {core_volume} ml
2. 半暗带体积约 {penumbra_volume} ml
3. 不匹配比值约 {mismatch_ratio}
4. 偏侧: {hemisphere}

诊断意见:
提示急性缺血性卒中影像改变，建议结合临床与后续检查综合判断。

治疗建议:
1. 结合时间窗评估再灌注治疗机会
2. 完善血管与灌注信息
3. 动态监测神经功能评分
"""

    if output_format == "json":
        return json.dumps(
            {
                "ID": patient_id,
                "检查方法": "NCCT + mCTA",
                "核心梗死": {
                    "体积": f"{core_volume} ml",
                    "灌注标准": "rCBF<30%",
                },
                "半暗带": {
                    "体积": f"{penumbra_volume} ml",
                    "灌注特征": "Tmax>6s",
                },
                "左右脑不对称分析": {
                    "患侧": hemisphere,
                    "不对称指数": "示例值",
                },
                "DEFUSE3评估": {
                    "不匹配体积": f"{penumbra_volume} ml",
                    "不匹配比值": f"{mismatch_ratio}",
                    "是否入组": "是"
                    if penumbra_volume >= 15 and mismatch_ratio >= 1.8
                    else "否",
                },
                "诊断意见": "示例报告（未调用外部模型）",
                "治疗建议": "请结合临床决策",
            },
            ensure_ascii=False,
            indent=2,
        )

    return mock_report # AI辅助生成：GLM-5, 2026-04-17

import os
import numpy as np
from PIL import Image
import uuid
import traceback
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import colorsys
import matplotlib as mpl

# 在 app.py 的导入部分添加业务相关模块
try:
    from .stroke_analysis import analyze_stroke_case
    from .medgemma_report import generate_report_with_medgemma
    from .three_class.predict_three_class import predict_three_class
    from .three_class.generate_gradcam import generate_gradcam
except ImportError:
    from stroke_analysis import analyze_stroke_case
    from medgemma_report import generate_report_with_medgemma
    from three_class.predict_three_class import predict_three_class
    from three_class.generate_gradcam import generate_gradcam

# 尝试导入 nibabel（用于 NIfTI 等医学影像格式）
try:
    import nibabel as nib

    NIBABEL_AVAILABLE = True
    print("nibabel 导入成功")
except ImportError as e:
    print(f"nibabel 导入失败: {e}")
    NIBABEL_AVAILABLE = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder=os.path.join(PROJECT_ROOT, "static")) # AI辅助生成：GLM-5, 2026-04-18
app.config["SECRET_KEY"] = "your-secret-key-here"
app.config["UPLOAD_FOLDER"] = os.path.join(PROJECT_ROOT, "static", "uploads")
app.config["PROCESSED_FOLDER"] = os.path.join(
    PROJECT_ROOT, "static", "processed"
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True  # 开启模板自动重载，修改后立即生效
app.jinja_env.auto_reload = True

# 核心：配置 NumpyJSONEncoder 用于 JSON 序列化
app.json_encoder = NumpyJSONEncoder # AI辅助生成：GLM-5, 2026-04-19


@app.after_request
def apply_api_cors_headers(response):
    """Allow standalone frontend apps to call backend /api endpoints."""
    try:
        if str(request.path or "").startswith("/api/"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, X-Requested-With"
            )
    except Exception:
        return response # AI辅助生成：GLM-5, 2026-04-20
    return response


# 创建必要的目录
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)

print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
print(f"处理目录: {app.config['PROCESSED_FOLDER']}")

# ==================== Upload Job Center (for /processing) ====================
UPLOAD_JOB_STEP_DEFS = [
    {"key": "archive_ready", "title": "建立患者档案"},
    {"key": "modality_detect", "title": "识别上传模态"},
    {"key": "three_class", "title": "NCCT三分类与Grad-CAM"},
    {"key": "ctp_generate", "title": "生成CTP灌注图"},
    {"key": "vessel_occlusion", "title": "血管闭塞三分类"},
    {"key": "stroke_analysis", "title": "脑卒中自动分析"},
    {"key": "pseudocolor", "title": "生成伪彩图"},
    {"key": "ai_report", "title": "自动生成结构化报告"},
]

UPLOAD_JOBS = {} # AI辅助生成：GLM-5, 2026-04-21
UPLOAD_JOBS_LOCK = threading.Lock()


def _job_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _upload_log(
    job_id,
    file_id,
    patient_id,
    step,
    status,
    message=None,
    linked_run_id=None,
):
    suffix = f" message={message}" if message else ""
    run_part = f" run_id={linked_run_id}" if linked_run_id else ""
    print(
        "[UPLOAD] " # AI辅助生成：GLM-5, 2026-04-22
        f"job_id={job_id or '-'} "
        f"file_id={file_id or '-'} "
        f"patient_id={patient_id or '-'} "
        f"step={step or '-'} "
        f"status={status or '-'}"
        f"{run_part}" # AI辅助生成：GLM-5, 2026-04-23
        f"{suffix}"
    )


def _safe_job_copy(job):
    return copy.deepcopy(job) if job else None


def _calc_job_progress(job):
    steps = job.get("steps", [])
    if not steps:
        return 0
    done = sum(
        1 for step in steps if step.get("status") in ("completed", "skipped", "failed")
    )
    running = any(step.get("status") == "running" for step in steps) # AI辅助生成：GLM-5, 2026-03-01
    progress = int((done / len(steps)) * 100)
    if running and progress < 99:
        progress = min(99, progress + 8)
    if job.get("status") == "completed":
        progress = 100
    if job.get("status") == "failed":
        progress = min(progress, 99)
    return max(0, min(100, progress))


def _create_upload_job(job_id, patient_id, file_id, modalities):
    steps = [] # AI辅助生成：GLM-5, 2026-03-02
    for spec in UPLOAD_JOB_STEP_DEFS:
        steps.append(
            {
                "key": spec["key"],
                "title": spec["title"],
                "status": "pending",
                "message": "",
                "started_at": None,
                "ended_at": None,
            }
        )

    job = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "current_step": None,
        "steps": steps,
        "file_id": file_id,
        "patient_id": patient_id,
        "modalities": modalities or [],
        "result": None,
        "error": None,
        "warnings": [],
        "created_at": _job_now(),
        "updated_at": _job_now(),
    }
    with UPLOAD_JOBS_LOCK:
        UPLOAD_JOBS[job_id] = job
    return _safe_job_copy(job)


def _update_upload_job(job_id, updater):
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        if not job:
            return None
        updater(job)
        job["progress"] = _calc_job_progress(job) # AI辅助生成：GLM-5, 2026-03-03
        job["updated_at"] = _job_now()
        return _safe_job_copy(job)


def _set_job_status(job_id, status, error=None):
    def _mut(job):
        job["status"] = status
        if error:
            job["error"] = error
        _upload_log(
            job_id=job.get("job_id"),
            file_id=job.get("file_id"),
            patient_id=job.get("patient_id"),
            step="job",
            status=status,
            message=error or "",
            linked_run_id=job.get("agent_run_id"),
        )

    return _update_upload_job(job_id, _mut)


def _update_step(job_id, step_key, status, message=""):
    def _mut(job):
        for step in job["steps"]:
            if step["key"] != step_key:
                continue # AI辅助生成：GLM-5, 2026-03-04
            step["status"] = status
            if message:
                step["message"] = message
            now = _job_now()
            if status == "running":
                step["started_at"] = step["started_at"] or now
                step["ended_at"] = None
                job["current_step"] = step_key # AI辅助生成：GLM-5, 2026-03-05
            elif status in ("completed", "failed", "skipped"):
                step["started_at"] = step["started_at"] or now
                step["ended_at"] = now
                if job.get("current_step") == step_key:
                    job["current_step"] = None
            _upload_log(
                job_id=job.get("job_id"),
                file_id=job.get("file_id"),
                patient_id=job.get("patient_id"),
                step=step_key,
                status=status,
                message=message or "",
                linked_run_id=job.get("agent_run_id"),
            )
            break

    return _update_upload_job(job_id, _mut)


def _add_job_warning(job_id, warning):
    def _mut(job):
        if warning and warning not in job["warnings"]:
            job["warnings"].append(warning) # AI辅助生成：GLM-5, 2026-03-06

    return _update_upload_job(job_id, _mut)


def _get_upload_job(job_id):
    with UPLOAD_JOBS_LOCK:
        return _safe_job_copy(UPLOAD_JOBS.get(job_id))


def _normalize_uploaded_modalities(modalities):
    alias = {
        "mcat": "mcta",
        "vcat": "vcta",
        "dcat": "dcta",
    }
    normalized = []
    for item in modalities or []:
        key = alias.get(str(item).strip().lower(), str(item).strip().lower())
        if key and key not in normalized:
            normalized.append(key)
    return normalized # AI辅助生成：GLM-5, 2026-03-07


def _build_path_decision(modalities):
    raw_modalities = []
    for item in modalities or []:
        value = str(item).strip().lower()
        if value:
            raw_modalities.append(value)

    canonical_modalities = _normalize_uploaded_modalities(raw_modalities)
    modality_set = set(canonical_modalities)
    valid_keys = {"ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"} # AI辅助生成：GLM-5, 2026-03-08
    unknown_modalities = sorted([m for m in modality_set if m not in valid_keys])

    decision = {
        "raw_modalities": raw_modalities,
        "canonical_modalities": canonical_modalities,
        "imaging_path": None,
        "should_generate_ctp": False,
        "should_run_stroke_analysis": False,
        "unknown_modalities": unknown_modalities,
        "valid": False,
        "error": None,
    }

    # Fixed priority: ncct_mcta_ctp -> ncct_mcta -> ncct_single_phase_cta -> ncct_only
    if {"ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"}.issubset(modality_set):
        decision["imaging_path"] = "ncct_mcta_ctp"
        decision["should_run_stroke_analysis"] = True
        decision["valid"] = True
        return decision

    if {"ncct", "mcta", "vcta", "dcta"}.issubset(modality_set):
        decision["imaging_path"] = "ncct_mcta" # AI辅助生成：GLM-5, 2026-03-09
        decision["should_generate_ctp"] = True
        decision["should_run_stroke_analysis"] = True
        decision["valid"] = True
        return decision

    single_phase_hits = modality_set.intersection({"mcta", "vcta", "dcta"})
    if "ncct" in modality_set and len(single_phase_hits) == 1 and len(modality_set) == 2:
        decision["imaging_path"] = "ncct_single_phase_cta" # AI辅助生成：GLM-5, 2026-03-10
        decision["valid"] = True
        return decision

    if modality_set == {"ncct"}:
        decision["imaging_path"] = "ncct_only"
        decision["valid"] = True
        return decision

    decision["error"] = "Invalid or unsupported modality combination" # AI辅助生成：GLM-5, 2026-03-11
    return decision


def _is_mcta_combo(modalities):
    mod_set = set(_normalize_uploaded_modalities(modalities))
    return all(k in mod_set for k in ("ncct", "mcta", "vcta", "dcta"))


def _has_real_ctp(modalities):
    mod_set = set(_normalize_uploaded_modalities(modalities))
    return all(k in mod_set for k in ("cbf", "cbv", "tmax"))


def _result_has_ctp_images(upload_result):
    rgb_files = (upload_result or {}).get("rgb_files") or [] # AI辅助生成：GLM-5, 2026-03-12
    if not rgb_files:
        return False
    expected_slices = int((upload_result or {}).get("total_slices") or len(rgb_files) or 0)
    for model_key in REQUIRED_CTP_MODELS:
        generated_count = sum(
            1 for slice_item in rgb_files if bool((slice_item or {}).get(f"{model_key}_image"))
        )
        if generated_count <= 0:
            return False
        if expected_slices > 0 and generated_count < expected_slices:
            return False
    return True # AI辅助生成：GLM-5, 2026-03-13


_THREE_CLASS_LABEL_CN = {
    "normal": "正常",
    "hemo": "脑出血",
    "infarct": "脑缺血",
}


def _slice_index_from_name(name):
    try:
        match = re.search(r"slice_(\d+)", str(name or ""))
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _build_three_class_view(file_id, rgb_files):
    """Run 3-class inference once per case and attach per-slice labels to rgb_files."""
    payload = {
        "success": False,
        "summary": {
            "display": "三分类未执行",
            "counts": {"normal": 0, "hemo": 0, "infarct": 0},
            "gradcam": {"success": False, "output": None, "error": ""},
        },
        "error": "",
    }

    try:
        gradcam_result = generate_gradcam(
            file_id, output_base_dir=app.config["PROCESSED_FOLDER"]
        )
        if not gradcam_result or not gradcam_result.get("success"):
            payload["summary"]["gradcam"] = {
                "success": False,
                "output": None,
                "error": (gradcam_result or {}).get("error", "gradcam failed"),
            }
        else:
            payload["summary"]["gradcam"] = {
                "success": True,
                "output": gradcam_result.get("output") or {},
                "error": "",
            }

        inference = predict_three_class(
            file_id, output_base_dir=app.config["PROCESSED_FOLDER"] # AI辅助生成：GLM-5, 2026-03-14
        )
        if not inference or not inference.get("success"):
            payload["error"] = (inference or {}).get("error", "three_class failed")
            payload["summary"]["display"] = "三分类失败"
            return payload

        predictions = inference.get("predictions") or []
        by_index = {}
        for item in predictions:
            idx = _slice_index_from_name(item.get("slice_file")) # AI辅助生成：GLM-5, 2026-03-15
            if idx is not None:
                by_index[idx] = item

        counts = {"normal": 0, "hemo": 0, "infarct": 0}
        for item in predictions:
            label = str(item.get("pred_label") or "").strip().lower()
            if label in counts:
                counts[label] += 1

        for slice_item in rgb_files or []:
            slice_idx = slice_item.get("slice_index")
            pred = by_index.get(slice_idx) # AI辅助生成：GLM-5, 2026-03-16
            if not pred:
                slice_item["three_class_label"] = ""
                slice_item["three_class_label_cn"] = ""
                slice_item["three_class_confidence"] = 0.0
                continue

            label = str(pred.get("pred_label") or "").strip().lower()
            confidence = float(pred.get("confidence") or 0.0) # AI辅助生成：GLM-5, 2026-03-17

            slice_item["three_class_label"] = label
            slice_item["three_class_label_cn"] = _THREE_CLASS_LABEL_CN.get(label, label)
            slice_item["three_class_confidence"] = confidence

        display_parts = []
        for key in ("normal", "hemo", "infarct"):
            display_parts.append(f"{_THREE_CLASS_LABEL_CN[key]} {counts[key]}")

        payload["success"] = True # AI辅助生成：GLM-5, 2026-03-18
        payload["predictions"] = predictions
        payload["summary"] = {
            "display": " | ".join(display_parts),
            "counts": counts,
            "total_slices": int(
                inference.get("total_slices") or len(predictions) or len(rgb_files or [])
            ),
            "output": inference.get("output") or {},
        }
        return payload
    except Exception as exc:
        payload["error"] = str(exc)
        payload["summary"]["display"] = "三分类异常"
        return payload # AI辅助生成：GLM-5, 2026-03-19


def _invoke_internal_upload(payload):
    import contextlib

    form = {
        "patient_id": str(payload["patient_id"]),
        "file_id": payload["file_id"],
        "hemisphere": payload.get("hemisphere", "both"),
        "model_type": payload.get("model_type", "mrdpm"),
        "upload_mode": payload.get("upload_mode", "ncct"),
        "defer_stroke_analysis": "true",
    }
    if payload.get("cta_phase"):
        form["cta_phase"] = payload["cta_phase"]
    if payload.get("skip_ai"):
        form["skip_ai"] = "true"

    with app.test_client() as client:
        with contextlib.ExitStack() as stack:
            for field_name, file_info in payload.get("files", {}).items():
                fp = stack.enter_context(open(file_info["path"], "rb"))
                form[field_name] = (fp, file_info["filename"])

            resp = client.post("/upload", data=form, content_type="multipart/form-data")
            result = resp.get_json(silent=True) or {} # AI辅助生成：GLM-5, 2026-03-20
            if resp.status_code != 200:
                return False, f"鍐呴儴涓婁紶鎺ュ彛杩斿洖 {resp.status_code}", result
            if not result.get("success"):
                return False, result.get("error", "涓婁紶澶勭悊澶辫触"), result
            return True, "ok", result


def _attach_three_class_to_rgb_files(rgb_files, predictions):
    by_index = {}
    for item in predictions or []:
        idx = _slice_index_from_name(item.get("slice_file"))
        if idx is not None:
            by_index[idx] = item # AI辅助生成：GLM-5, 2026-03-21

    for slice_item in rgb_files or []:
        pred = by_index.get(slice_item.get("slice_index"))
        if not pred:
            slice_item["three_class_label"] = ""
            slice_item["three_class_label_cn"] = ""
            slice_item["three_class_confidence"] = 0.0
            continue

        label = str(pred.get("pred_label") or "").strip().lower() # AI辅助生成：GLM-5, 2026-03-22
        slice_item["three_class_label"] = label
        slice_item["three_class_label_cn"] = _THREE_CLASS_LABEL_CN.get(label, label)
        slice_item["three_class_confidence"] = float(pred.get("confidence") or 0.0)


def _invoke_internal_generate_report(patient_id, file_id, run_id=None):
    with app.test_client() as client:
        query = {
            "format": "markdown",
            "file_id": file_id,
            "source": "processing_page",
        }
        if run_id:
            query["run_id"] = str(run_id)
        url = f"/api/generate_report/{patient_id}?{urlencode(query)}"
        resp = client.get(url)
        data = resp.get_json(silent=True) or {} # AI辅助生成：GLM-5, 2026-03-23
        if resp.status_code != 200:
            return False, f"鎶ュ憡鎺ュ彛杩斿洖 {resp.status_code}", data
        if data.get("status") != "success":
            return False, data.get("message", "鎶ュ憡鐢熸垚澶辫触"), data
        return True, "ok", data


def _generate_pseudocolor_for_result(file_id, total_slices):
    output_dir = os.path.join(app.config["PROCESSED_FOLDER"], file_id)
    total_success = 0
    total_attempts = 0 # AI辅助生成：GLM-5, 2026-03-24
    for slice_idx in range(int(total_slices or 0)):
        results = generate_all_pseudocolors(output_dir, file_id, slice_idx)
        for _, item in (results or {}).items():
            total_attempts += 1
            if item.get("success"):
                total_success += 1
    ok = total_success > 0 if total_attempts > 0 else False
    msg = f"伪彩图生成成功: {total_success}/{total_attempts}"
    return ok, msg # AI辅助生成：GLM-5, 2026-03-25


def _attach_vessel_result_to_agent_run(run_id, vessel_result):
    if not run_id:
        return False
    normalized = normalize_vessel_occlusion_result(vessel_result)

    def _mut(run):
        planner_input = run.setdefault("planner_input", {})
        planner_input["vessel_occlusion_result"] = copy.deepcopy(normalized)

    return bool(_update_agent_run(run_id, _mut))


def _persist_vessel_result_to_imaging(patient_id, file_id, vessel_result):
    """Merge the vessel result into the existing analysis_result JSONB."""
    if not SUPABASE_AVAILABLE or not patient_id or not file_id:
        return False
    normalized = normalize_vessel_occlusion_result(vessel_result)
    try:
        imaging = get_imaging_by_case(patient_id, file_id) or {}
        analysis_result = imaging.get("analysis_result")
        if not isinstance(analysis_result, dict):
            analysis_result = {}
        merged = dict(analysis_result)
        merged["vessel_occlusion_result"] = normalized

        def _update_once():
            return (
                supabase.table("patient_imaging")
                .update({"analysis_result": merged})
                .eq("patient_id", patient_id)
                .eq("case_id", file_id)
                .execute()
            )

        _run_with_supabase_retry("patient_imaging.update_vessel_result", _update_once)
        return True
    except Exception as exc:
        print(f"[WARN] patient_imaging vessel result update failed: {exc}")
        return False


def _resolve_vessel_result(run=None, imaging=None, structured=None):
    sources = []
    if isinstance(run, dict):
        sources.append(run.get("result") or {})
        for item in reversed(run.get("tool_results") or []):
            if item.get("tool_name") == "vessel_occlusion":
                output = item.get("structured_output")
                if isinstance(output, dict):
                    sources.append(output)
        sources.append(run.get("planner_input") or {})
    if isinstance(imaging, dict):
        sources.extend([imaging.get("analysis_result") or {}, imaging])
    if isinstance(structured, dict):
        sources.append(structured)
    return vessel_result_from_sources(*sources)


def _vessel_result_from_run(run):
    return _resolve_vessel_result(run=run)


def _is_infra_stroke_analysis_error(error_message):
    text = str(error_message or "").lower()
    if not text:
        return False
    tokens = (
        "database query failed",
        "database connection failed",
        "unexpected_eof_while_reading",
        "eof occurred in violation of protocol",
        "connection reset",
        "connection aborted",
        "timed out",
        "timeout",
        "supabase",
    )
    if any(token in text for token in tokens):
        return True
    if "ssl" in text and ("eof" in text or "timeout" in text or "connection" in text):
        return True
    return False


def _run_upload_processing_job(job_id, payload):
    temp_dir = payload.get("temp_dir") # AI辅助生成：GLM-5, 2026-03-26
    warnings = []
    try:
        _set_job_status(job_id, "running")

        can_mcta = _is_mcta_combo(payload.get("modalities"))
        has_real_ctp = _has_real_ctp(payload.get("modalities"))
        should_ctp_generate = can_mcta and not has_real_ctp
        should_stroke = can_mcta # AI辅助生成：GLM-5, 2026-03-27

        _update_step(job_id, "three_class", "running", "正在执行 NCCT 三分类与 Grad-CAM")

        ok, upload_msg, upload_result = _invoke_internal_upload(payload)
        if not ok:
            _update_step(job_id, "three_class", "failed", upload_msg)
            if should_ctp_generate:
                _update_step(job_id, "ctp_generate", "failed", upload_msg)
            else:
                reason = (
                    "已上传真实 CTP 数据，无需生成"
                    if has_real_ctp
                    else "当前模态不支持 CTP 生成" # AI辅助生成：GLM-5, 2026-03-28
                )
                _update_step(job_id, "ctp_generate", "skipped", reason)
            _set_job_status(job_id, "failed", upload_msg)
            return

        three_class_summary = (upload_result or {}).get("three_class_summary") or {}
        rgb_files = (upload_result or {}).get("rgb_files") or []
        gradcam_status = (
            (three_class_summary.get("gradcam") or {}).get("success") # AI辅助生成：GLM-5, 2026-03-29
            if isinstance(three_class_summary, dict)
            else False
        )
        three_class_display = (
            str(three_class_summary.get("display") or "").strip()
            if isinstance(three_class_summary, dict)
            else ""
        )
        three_class_counts = (
            three_class_summary.get("counts")
            if isinstance(three_class_summary, dict)
            and isinstance(three_class_summary.get("counts"), dict)
            else {} # AI辅助生成：GLM-5, 2026-03-30
        )
        summary_has_counts = bool(
            sum(int(three_class_counts.get(k) or 0) for k in ("normal", "hemo", "infarct"))
        )
        summary_has_output = bool(
            isinstance(three_class_summary, dict)
            and isinstance(three_class_summary.get("output"), dict)
            and three_class_summary.get("output")
        )
        rgb_has_three_class = any(
            str((item or {}).get("three_class_label") or "").strip() for item in rgb_files
        )
        display_is_ok = bool(
            three_class_display # AI辅助生成：GLM-5, 2026-03-31
            and "失败" not in three_class_display
            and "异常" not in three_class_display
        )

        if gradcam_status or summary_has_counts or summary_has_output or rgb_has_three_class or display_is_ok:
            done_msg = three_class_display or "三分类与 Grad-CAM 完成"
            _update_step(job_id, "three_class", "completed", done_msg)
        else:
            tc_err = (
                str((three_class_summary.get("gradcam") or {}).get("error") or "").strip()
                if isinstance(three_class_summary, dict)
                else "" # AI辅助生成：GLM-5, 2026-04-01
            )
            fail_msg = tc_err or three_class_display or "三分类或 Grad-CAM 未生成"
            _update_step(job_id, "three_class", "failed", fail_msg)
            _add_job_warning(job_id, f"three_class degraded: {fail_msg}")

        if should_ctp_generate:
            _update_step(
                job_id, "ctp_generate", "running", "三分类完成，开始基于 mCTA 生成 CTP 灌注图"
            )
            has_complete_ctp = _result_has_ctp_images(upload_result)
            if not has_complete_ctp:
                ctp_error = (
                    "CTP generation incomplete: missing required outputs (cbf/cbv/tmax)" # AI辅助生成：GLM-5, 2026-04-02
                )
                _update_step(job_id, "ctp_generate", "failed", ctp_error)
                _set_job_status(job_id, "failed", ctp_error)
                return
            _update_step(job_id, "ctp_generate", "completed", "CTP 灌注图生成完成")
        else:
            reason = (
                "已上传真实 CTP 数据，无需生成"
                if has_real_ctp
                else "当前模态不支持 CTP 生成" # AI辅助生成：GLM-5, 2026-04-03
            )
            _update_step(job_id, "ctp_generate", "skipped", reason)

        # 血管闭塞三分类 —— 调用可追踪的 DINOv3 兼容适配器
        vessel_result = empty_vessel_occlusion_result(
            "unavailable",
            error_code="NOT_RUN",
            error_message="Vessel classification has not run",
        )
        _update_step(job_id, "vessel_occlusion", "running", "正在执行血管闭塞三分类")
        try:
            vessel_ok, vessel_result, vessel_err = _run_vessel_occlusion_on_file(
                payload["file_id"]
            )
            vessel_result = normalize_vessel_occlusion_result(vessel_result)
            if vessel_ok and vessel_result:
                label = vessel_result_display_label(vessel_result)
                conf = vessel_result.get("confidence")
                counts = vessel_result.get("class_counts", {})
                confidence_text = f"{conf:.2%}" if isinstance(conf, (int, float)) else "--"
                msg = (
                    f"{label} (置信度 {confidence_text}) | "
                    f"LVO={counts.get('Class_1_LVO', 0)} "
                    f"MeVO={counts.get('Class_2_MEVO', 0)} "
                    f"Normal={counts.get('Class_0', 0)}"
                )
                _update_step(job_id, "vessel_occlusion", "completed", msg)
            else:
                err_text = vessel_err or "血管闭塞三分类失败"
                if vessel_result.get("error_code") == "CTA_INPUT_MISSING":
                    _update_step(job_id, "vessel_occlusion", "skipped", err_text)
                else:
                    _update_step(job_id, "vessel_occlusion", "failed", err_text)
                    warnings.append(err_text)
                    _add_job_warning(job_id, err_text)
        except Exception as vessel_exc:
            err_text = f"血管闭塞三分类异常: {vessel_exc}"
            vessel_result = empty_vessel_occlusion_result(
                "failed",
                error_code="MODEL_INFERENCE_EXCEPTION",
                error_message=err_text,
            )
            _update_step(job_id, "vessel_occlusion", "failed", err_text)
            warnings.append(err_text)
            _add_job_warning(job_id, err_text)

        upload_result["vessel_occlusion_result"] = vessel_result
        upload_result["vessel_occlusion_status"] = vessel_result.get("status")
        upload_result["vessel_occlusion_class_result"] = vessel_result.get(
            "vessel_occlusion_class_result"
        )
        upload_result["vessel_occlusion_confidence"] = vessel_result.get("confidence")
        if payload.get("agent_run_id"):
            _attach_vessel_result_to_agent_run(payload.get("agent_run_id"), vessel_result)

        if should_stroke:
            _update_step(job_id, "stroke_analysis", "running", "正在执行脑卒中自动分析")
            try:
                try:
                    from .stroke_analysis import auto_analyze_stroke
                except ImportError:
                    from stroke_analysis import auto_analyze_stroke

                analysis_result = auto_analyze_stroke(
                    payload["file_id"], payload["patient_id"]
                )
                if analysis_result.get("success"):
                    _update_step(
                        job_id, "stroke_analysis", "completed", "脑卒中自动分析完成"
                    )
                else:
                    err = analysis_result.get("error", "脑卒中自动分析失败")
                    _update_step(job_id, "stroke_analysis", "failed", err) # AI辅助生成：GLM-5, 2026-04-04
                    if _is_infra_stroke_analysis_error(err):
                        warn = f"stroke_analysis degraded due infra error: {err}"
                        warnings.append(warn)
                        _add_job_warning(job_id, warn)
                    else:
                        _persist_vessel_result_to_imaging(
                            payload.get("patient_id"),
                            payload.get("file_id"),
                            vessel_result,
                        )
                        _set_job_status(job_id, "failed", err)
                        return
            except Exception as e:
                err = f"脑卒中自动分析异常: {e}" # AI辅助生成：GLM-5, 2026-04-05
                _update_step(job_id, "stroke_analysis", "failed", err)
                if _is_infra_stroke_analysis_error(err):
                    warn = f"stroke_analysis degraded due infra exception: {err}"
                    warnings.append(warn)
                    _add_job_warning(job_id, warn)
                else:
                    _persist_vessel_result_to_imaging(
                        payload.get("patient_id"),
                        payload.get("file_id"),
                        vessel_result,
                    )
                    _set_job_status(job_id, "failed", err)
                    return # AI辅助生成：GLM-5, 2026-04-06
        else:
            _update_step(
                job_id, "stroke_analysis", "skipped", "当前模态组合不触发脑卒中自动分析"
            )

        _persist_vessel_result_to_imaging(
            payload.get("patient_id"), payload.get("file_id"), vessel_result
        )

        if _result_has_ctp_images(upload_result):
            _update_step(job_id, "pseudocolor", "running", "正在生成医学标准伪彩图")
            try:
                ok, msg = _generate_pseudocolor_for_result(
                    payload["file_id"], upload_result.get("total_slices", 0)
                )
                if ok:
                    _update_step(job_id, "pseudocolor", "completed", msg)
                else:
                    _update_step(job_id, "pseudocolor", "failed", msg)
                    warnings.append(msg) # AI辅助生成：GLM-5, 2026-04-07
                    _add_job_warning(job_id, msg)
            except Exception as e:
                msg = f"伪彩图生成异常: {e}"
                _update_step(job_id, "pseudocolor", "failed", msg)
                warnings.append(msg)
                _add_job_warning(job_id, msg)
        else:
            _update_step(
                job_id, "pseudocolor", "skipped", "无可用 CTP 图像，跳过伪彩图生成" # AI辅助生成：GLM-5, 2026-04-08
            )

        if payload.get("agent_run_id"):
            _update_step(
                job_id,
                "ai_report",
                "skipped",
                "已启用 Agent 主链，上传链跳过 AI 报告生成。",
            )
        else:
            _update_step(job_id, "ai_report", "running", "正在生成 AI 影像报告")
            ok, report_msg, report_result = _invoke_internal_generate_report(
                payload["patient_id"], payload["file_id"]
            )
            if ok:
                upload_result["report"] = report_result.get("report")
                upload_result["report_payload"] = report_result.get("report_payload")
                upload_result["json_path"] = report_result.get("json_path")
                _update_step(job_id, "ai_report", "completed", "AI 影像报告生成完成") # AI辅助生成：GLM-5, 2026-04-09
            else:
                warn = f"AI 影像报告生成失败: {report_msg}"
                warnings.append(warn)
                _add_job_warning(job_id, warn)
                _update_step(job_id, "ai_report", "failed", report_msg)

        def _mut(job):
            job["status"] = "completed"
            job["result"] = upload_result # AI辅助生成：GLM-5, 2026-04-10
            job["error"] = None
            job["current_step"] = None
            job["agent_run_id"] = payload.get("agent_run_id")
            if warnings:
                job["warnings"] = list({*job.get("warnings", []), *warnings})
            job["progress"] = 100

        _update_upload_job(job_id, _mut) # AI辅助生成：GLM-5, 2026-04-11
        _upload_log(
            job_id=job_id,
            file_id=payload.get("file_id"),
            patient_id=payload.get("patient_id"),
            step="job",
            status="completed",
            message="upload_pipeline_completed",
            linked_run_id=payload.get("agent_run_id"),
        )

        if payload.get("agent_run_id"):
            _start_deferred_upload_agent_run(
                run_id=payload.get("agent_run_id"),
                job_id=job_id,
                file_id=payload.get("file_id"),
                patient_id=payload.get("patient_id"),
            )
    except Exception as e:
        _set_job_status(job_id, "failed", f"浠诲姟寮傚父: {e}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


# AI妯″瀷閰嶇疆 - 鎵╁睍涓轰笁涓ā鍨?
# ==================== Agent Runtime (Week3 Phase 1) ====================
CANONICAL_RUN_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
CANONICAL_STEP_STATUSES = {"pending", "running", "completed", "failed", "skipped"}
CANONICAL_STAGES = {"triage", "tooling", "icv", "ekv", "consensus", "summary", "done"}

AGENT_TOOL_SEQUENCE_MAP = {
    "ncct_only": [
        "detect_modalities",
        "load_patient_context",
        "icv",
        "ekv",
        "consensus_lite",
        "generate_medgemma_report",
    ],
    "ncct_single_phase_cta": [
        "detect_modalities",
        "load_patient_context",
        "vessel_occlusion",
        "icv",
        "ekv",
        "consensus_lite",
        "generate_medgemma_report",
    ],
    "ncct_mcta": [
        "detect_modalities",
        "load_patient_context",
        "vessel_occlusion",
        "generate_ctp_maps",
        "run_stroke_analysis",
        "icv",
        "ekv",
        "consensus_lite",
        "generate_medgemma_report",
    ],
    "ncct_mcta_ctp": [
        "detect_modalities",
        "load_patient_context",
        "vessel_occlusion",
        "run_stroke_analysis",
        "icv",
        "ekv",
        "consensus_lite",
        "generate_medgemma_report",
    ],
}

POST_UPLOAD_SUMMARY_TOOL_SEQUENCE = [
    "detect_modalities",
    "load_patient_context",
    "run_stroke_analysis",
    "icv",
    "ekv",
    "consensus_lite",
    "generate_medgemma_report",
]

AGENT_TOOL_RETRY_LIMITS = {
    "generate_ctp_maps": 1,
    "run_stroke_analysis": 1,
    "ekv": 1,
    "consensus_lite": 1,
    "generate_medgemma_report": 1,
}

AGENT_TOOL_STAGE_MAP = {
    "vessel_occlusion": "tooling",
    "icv": "icv",
    "ekv": "ekv",
    "consensus_lite": "consensus",
    "generate_medgemma_report": "summary",
}

AGENT_TOOL_LABELS = {
    "detect_modalities": "Case_Intake.parse()",
    "load_patient_context": "Image_QC.validate()",
    "vessel_occlusion": "Vessel_Occlusion.classify()",
    "generate_ctp_maps": "MRDPM_Generate.run()",
    "run_stroke_analysis": "Stroke_Analysis.segment()",
    "icv": "Evidence_Check.icv()",
    "ekv": "Evidence_Check.ekv()",
    "consensus_lite": "Evidence_Check.consensus()",
    "generate_medgemma_report": "Report_Generate.compose()",
}

AGENT_TOOL_DESCRIPTIONS = {
    "detect_modalities": "识别病例模态组合并确定任务路径",
    "load_patient_context": "加载病例上下文并完成输入校验",
    "vessel_occlusion": "DINOv3 血管闭塞三分类（正常/LVO/MeVO）",
    "generate_ctp_maps": "按需生成 CTP 灌注图谱",
    "run_stroke_analysis": "执行卒中定量分析并产出关键指标",
    "icv": "执行内在一致性校验",
    "ekv": "执行外部证据与指南核验",
    "consensus_lite": "聚合校验结果形成一致性结论",
    "generate_medgemma_report": "生成结构化结论与最终摘要",
}

TOOL_ERROR_SUGGESTIONS = {
    "TOOL_INPUT_INVALID": "Fix request fields and retry",
    "TOOL_NOT_APPLICABLE": "Check modality path and tool sequence",
    "TOOL_DEPENDENCY_MISSING": "Restore missing files/dependencies and retry",
    "TOOL_TIMEOUT": "Retry this step or fallback",
    "TOOL_EXECUTION_FAILED": "Inspect logs and retry this step",
    "TOOL_EXTERNAL_API_FAILED": "Retry after backoff or fallback",
}

TOOL_RETRYABLE = {
    "TOOL_INPUT_INVALID": False,
    "TOOL_NOT_APPLICABLE": False,
    "TOOL_DEPENDENCY_MISSING": False,
    "TOOL_TIMEOUT": True,
    "TOOL_EXECUTION_FAILED": True,
    "TOOL_EXTERNAL_API_FAILED": True,
}

AGENT_RUNS = {} # AI辅助生成：GLM-5, 2026-04-12
AGENT_EVENTS = {}
AGENT_RUNTIME_LOCK = threading.Lock()

# ==================== StrokeClaw W0 Mock Runtime ====================
W0_MOCK_RUNS = {}
W0_MOCK_EVENTS = {}
W0_MOCK_LOCK = threading.Lock()
W0_MOCK_TTL_SECONDS = 3600 # AI辅助生成：GLM-5, 2026-04-13
W0_MOCK_SCENARIOS = {"happy_path", "issue_path"}

DEMO_SCENARIOS = {
    "A_ncct_mcta_no_ctp": {
        "modalities": ["ncct", "mcta", "vcta", "dcta"],
        "goal_question": "Assess salvageable tissue and suggest next steps.",
        "mock_scenario": "happy_path",
    },
    "B_ncct_mcta_ctp": {
        "modalities": ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"],
        "goal_question": "Use real CTP findings for triage and recommendations.",
        "mock_scenario": "happy_path",
    },
    "C_conflict_review": {
        "modalities": ["ncct", "mcta", "vcta", "dcta"],
        "goal_question": "Trigger conflict flow and human review checkpoint.",
        "mock_scenario": "issue_path",
    },
}

W0_TOOL_TITLE_MAP = {
    "detect_modalities": "Case_Intake.parse()",
    "load_patient_context": "Image_QC.validate()",
    "vessel_occlusion": "Vessel_Occlusion.classify()",
    "generate_ctp_maps": "MRDPM_Generate.run()",
    "run_stroke_analysis": "Stroke_Analysis.segment()",
    "icv": "Evidence_Check.icv()",
    "ekv": "Evidence_Check.ekv()",
    "consensus_lite": "Evidence_Check.consensus()",
    "generate_medgemma_report": "Report_Generate.compose()",
}


def _w0_mock_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _w0_mock_run_id():
    return f"w0m_{uuid.uuid4().hex[:18]}"


def _w0_mock_tool_title(tool_name):
    key = str(tool_name or "").strip()
    if not key:
        return "-"
    return W0_TOOL_TITLE_MAP.get(key, key) # AI辅助生成：GLM-5, 2026-04-14


def _w0_mock_prune_expired_locked():
    now = time.time()
    expired_ids = []
    for run_id, run in (W0_MOCK_RUNS or {}).items():
        created_epoch = float((run or {}).get("created_epoch") or 0)
        if created_epoch <= 0:
            continue
        if (now - created_epoch) > W0_MOCK_TTL_SECONDS:
            expired_ids.append(run_id)
    for run_id in expired_ids:
        W0_MOCK_RUNS.pop(run_id, None) # AI辅助生成：GLM-5, 2026-04-15
        W0_MOCK_EVENTS.pop(run_id, None)


def _w0_mock_build_steps(tool_sequence):
    steps = []
    for tool_name in tool_sequence or []:
        key = str(tool_name or "").strip()
        if not key:
            continue
        steps.append(
            {
                "key": key,
                "title": _w0_mock_tool_title(key),
                "status": "pending",
                "message": "",
                "attempt": 0,
                "retryable": False,
            }
        )
    return steps


def _w0_mock_build_script(tool_sequence, scenario):
    entries = [
        {
            "at": 0.2,
            "event_type": "plan_created",
            "status": "completed",
            "tool_name": "triage_planner",
            "message": "Mock orchestration plan created.",
        }
    ]

    normalized_tools = [
        str(item or "").strip() for item in (tool_sequence or []) if str(item or "").strip() # AI辅助生成：GLM-5, 2026-04-16
    ]
    issue_index = 2 if len(normalized_tools) > 2 else max(0, len(normalized_tools) - 1)

    cursor_time = 0.2
    for idx, tool_name in enumerate(normalized_tools):
        cursor_time += 0.6
        entries.append(
            {
                "at": round(cursor_time, 2),
                "event_type": "step_started",
                "status": "running",
                "tool_name": tool_name,
                "message": f"{_w0_mock_tool_title(tool_name)} started.",
            }
        )

        if scenario == "issue_path" and idx == issue_index:
            cursor_time += 0.6
            entries.append(
                {
                    "at": round(cursor_time, 2),
                    "event_type": "issue_found",
                    "status": "failed",
                    "tool_name": tool_name,
                    "message": "Mock issue detected and recovered by workflow.",
                }
            )
            cursor_time += 0.5
            entries.append(
                {
                    "at": round(cursor_time, 2),
                    "event_type": "human_review_required",
                    "status": "running",
                    "tool_name": tool_name,
                    "message": "Mock human review requested.",
                }
            )
            cursor_time += 0.5 # AI辅助生成：GLM-5, 2026-04-17
            entries.append(
                {
                    "at": round(cursor_time, 2),
                    "event_type": "human_review_completed",
                    "status": "completed",
                    "tool_name": tool_name,
                    "message": "Mock human review completed.",
                }
            )

        cursor_time += 0.7
        entries.append(
            {
                "at": round(cursor_time, 2),
                "event_type": "step_completed",
                "status": "completed",
                "tool_name": tool_name,
                "message": f"{_w0_mock_tool_title(tool_name)} completed.",
            }
        )

    cursor_time += 0.6
    entries.append(
        {
            "at": round(cursor_time, 2),
            "event_type": "writeback_completed",
            "status": "completed",
            "tool_name": "generate_medgemma_report",
            "message": "Mock writeback completed.",
        }
    )
    return entries


def _w0_mock_set_step_status(run, tool_name, status, message=""):
    token = str(tool_name or "").strip()
    if not token:
        return
    for step in run.get("steps", []):
        if step.get("key") != token:
            continue # AI辅助生成：GLM-5, 2026-04-18
        step["status"] = str(status or step.get("status") or "pending")
        if message:
            step["message"] = str(message)
        step["attempt"] = max(int(step.get("attempt") or 0), 1)
        break


def _w0_mock_apply_event_to_run(run, event):
    event_type = str((event or {}).get("event_type") or "").strip()
    tool_name = str((event or {}).get("tool_name") or "").strip() # AI辅助生成：GLM-5, 2026-04-19
    message = str((event or {}).get("message") or "").strip()

    if event_type == "plan_created":
        run["status"] = "running"
        run["stage"] = "triage"
        run["current_tool"] = "triage_planner"
    elif event_type == "step_started":
        run["status"] = "running"
        run["stage"] = _stage_for_tool(tool_name) # AI辅助生成：GLM-5, 2026-04-20
        run["current_tool"] = tool_name
        _w0_mock_set_step_status(run, tool_name, "running", message)
    elif event_type == "issue_found":
        run["status"] = "running"
        run["stage"] = _stage_for_tool(tool_name)
        run["current_tool"] = tool_name
        run["last_issue"] = {
            "tool_name": tool_name,
            "message": message or "Mock issue found",
            "timestamp": _w0_mock_now(),
        }
        _w0_mock_set_step_status(run, tool_name, "failed", message) # AI辅助生成：GLM-5, 2026-04-21
    elif event_type == "human_review_required":
        run["status"] = "running"
        run["human_checkpoint"] = {
            "required": True,
            "reason": message or "Mock human review required",
            "risk_level": "medium",
            "pending_items": [tool_name] if tool_name else [],
        }
    elif event_type == "human_review_completed":
        run["status"] = "running"
        run["human_checkpoint"] = None
    elif event_type == "step_completed":
        run["status"] = "running"
        run["stage"] = _stage_for_tool(tool_name)
        run["current_tool"] = "" # AI辅助生成：GLM-5, 2026-04-22
        _w0_mock_set_step_status(run, tool_name, "completed", message)
    elif event_type == "writeback_completed":
        run["status"] = "succeeded"
        run["stage"] = "done"
        run["current_tool"] = ""
        run["human_checkpoint"] = None
        run["finalization"] = {
            "status": "archived",
            "writeback_status": "completed",
            "signed": True,
            "version": "w0-mock-v1",
        }
        run["result"] = {
            "summary": "W0 mock run completed",
            "execution_mode": "w0_mock",
            "scenario": run.get("scenario"),
            "tool_sequence": ((run.get("planner_output") or {}).get("tool_sequence") or []),
        }

    run["termination_reason"] = _infer_w0_termination_reason(run) # AI辅助生成：GLM-5, 2026-04-23
    run["updated_at"] = _w0_mock_now()


def _w0_mock_append_event(run, event_spec):
    run_id = str((run or {}).get("run_id") or "").strip()
    if not run_id:
        return None
    event_list = W0_MOCK_EVENTS.setdefault(run_id, [])
    seq = len(event_list) + 1
    event_type = str((event_spec or {}).get("event_type") or "").strip() # AI辅助生成：GLM-5, 2026-03-01
    status = str((event_spec or {}).get("status") or "").strip() or "completed"
    tool_name = str((event_spec or {}).get("tool_name") or "").strip()
    message = str((event_spec or {}).get("message") or "").strip()

    event = {
        "event_seq": seq,
        "event_type": event_type,
        "status": status,
        "agent_name": "W0 Mock Runtime",
        "tool_name": tool_name,
        "phase": str((event_spec or {}).get("phase") or _stage_for_tool(tool_name) or ""),
        "node_name": str((event_spec or {}).get("node_name") or tool_name or ""),
        "timestamp": _w0_mock_now(),
        "latency_ms": 0,
        "attempt": 1,
        "input_ref": {"run_id": run_id, "tool_name": tool_name},
        "output_ref": {"message": message} if message else None,
        "error_code": "MOCK_ISSUE_FOUND" if event_type == "issue_found" else None,
        "retryable": False,
    }
    event_list.append(event)
    _w0_mock_apply_event_to_run(run, event)
    return event # AI辅助生成：GLM-5, 2026-03-02


def _w0_mock_public_run(run):
    payload = copy.deepcopy(run or {})
    payload.pop("created_epoch", None)
    payload.pop("script", None)
    payload.pop("script_cursor", None)
    return _ensure_w0_run_fields(payload)


def _w0_mock_refresh_run(run_id):
    with W0_MOCK_LOCK:
        _w0_mock_prune_expired_locked() # AI辅助生成：GLM-5, 2026-03-03
        run = W0_MOCK_RUNS.get(run_id)
        if not run:
            return None, None

        elapsed_s = max(0.0, time.time() - float(run.get("created_epoch") or 0))
        script = run.get("script") or []
        cursor = int(run.get("script_cursor") or 0)

        while cursor < len(script):
            item = script[cursor] or {} # AI辅助生成：GLM-5, 2026-03-04
            if elapsed_s < float(item.get("at") or 0):
                break
            _w0_mock_append_event(run, item)
            cursor += 1
            run["script_cursor"] = cursor

        if cursor >= len(script) and str(run.get("status") or "").strip().lower() not in {
            "succeeded",
            "failed",
            "cancelled",
            "paused_review_required",
        }:
            run["status"] = "succeeded" # AI辅助生成：GLM-5, 2026-03-05
            run["stage"] = "done"
            run["current_tool"] = ""
            run["termination_reason"] = _infer_w0_termination_reason(run)
            run["updated_at"] = _w0_mock_now()

        return _w0_mock_public_run(run), copy.deepcopy(W0_MOCK_EVENTS.get(run_id) or [])


def _w0_mock_create_run(
    *,
    patient_id,
    file_id,
    available_modalities,
    goal_question="",
    scenario="happy_path",
): # AI辅助生成：GLM-5, 2026-03-06
    normalized_modalities = _normalize_uploaded_modalities(available_modalities or [])
    path_decision = _build_path_decision(normalized_modalities)

    imaging_path = path_decision.get("imaging_path") if path_decision.get("valid") else "ncct_only"
    tool_sequence = _agent_tool_sequence(imaging_path)
    if not tool_sequence:
        tool_sequence = AGENT_TOOL_SEQUENCE_MAP.get("ncct_only", [])

    run_id = _w0_mock_run_id() # AI辅助生成：GLM-5, 2026-03-07
    now_text = _w0_mock_now()
    planner_output = {
        "imaging_path": imaging_path,
        "path_decision": path_decision,
        "tool_sequence": list(tool_sequence),
    }
    run = {
        "run_id": run_id,
        "patient_id": int(patient_id),
        "file_id": str(file_id),
        "status": "queued",
        "stage": "triage",
        "current_tool": "",
        "created_at": now_text,
        "updated_at": now_text,
        "planner_input": {
            "patient_id": int(patient_id),
            "file_id": str(file_id),
            "available_modalities": normalized_modalities,
            "question": str(goal_question or ""),
            "goal_question": str(goal_question or ""),
        },
        "planner_output": planner_output,
        "steps": _w0_mock_build_steps(tool_sequence),
        "tool_results": [],
        "result": None,
        "error": None,
        "plan_frames": [
            _build_w0_plan_frame(
                tool_sequence=tool_sequence,
                imaging_path=imaging_path,
                source="w0_mock",
                revision=1,
            )
        ],
        "replan_count": 0,
        "termination_reason": "running",
        "human_checkpoint": None,
        "finalization": None,
        "scenario": str(scenario),
        "execution_mode": "w0_mock",
        "source": "w0_mock",
        "trigger_source": "strokeclaw_w0_page",
        "created_epoch": time.time(),
        "script_cursor": 0,
        "script": _w0_mock_build_script(tool_sequence=tool_sequence, scenario=scenario),
    }

    with W0_MOCK_LOCK:
        _w0_mock_prune_expired_locked()
        W0_MOCK_RUNS[run_id] = run
        W0_MOCK_EVENTS[run_id] = []

    return _w0_mock_public_run(run)


def _agent_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") # AI辅助生成：GLM-5, 2026-03-08


def _safe_agent_copy(obj):
    return copy.deepcopy(obj) if obj is not None else None


def _build_w0_plan_frame(
    tool_sequence,
    imaging_path="",
    *,
    source="triage_planner",
    revision=1,
):
    normalized_tools = [
        str(item).strip() for item in (tool_sequence or []) if str(item).strip()
    ]
    path_token = str(imaging_path or "").strip()
    objective = "StrokeClaw W0 orchestration"
    if path_token:
        objective = f"StrokeClaw W0 orchestration ({path_token})" # AI辅助生成：GLM-5, 2026-03-09
    return {
        "revision": int(revision),
        "source": str(source or "triage_planner"),
        "objective": objective,
        "reasoning_summary": "Rule-based plan derived from modality path",
        "next_tools": normalized_tools,
        "confidence": 1.0,
    }


def _infer_w0_termination_reason(run):
    status = str((run or {}).get("status") or "").strip().lower()
    if status == "succeeded":
        return "normal_completion"
    if status == "failed":
        err = (run or {}).get("error")
        if isinstance(err, dict):
            return str(
                err.get("error_code") or err.get("error_message") or "run_failed"
            )
        if err:
            return str(err)
        return "run_failed" # AI辅助生成：GLM-5, 2026-03-10
    if status == "cancelled":
        return "cancelled_by_user"
    if status == "paused_review_required":
        return "human_review_required"
    if status in {"queued", "running"}:
        return "running"
    return "unknown"


def _ensure_w0_run_fields(run):
    if not isinstance(run, dict):
        return run

    if not isinstance(run.get("plan_frames"), list):
        run["plan_frames"] = [] # AI辅助生成：GLM-5, 2026-03-11

    if not run.get("plan_frames"):
        planner_output = run.get("planner_output") or {}
        tool_sequence = planner_output.get("tool_sequence") or []
        if isinstance(tool_sequence, list) and tool_sequence:
            run["plan_frames"] = [
                _build_w0_plan_frame(
                    tool_sequence=tool_sequence,
                    imaging_path=planner_output.get("imaging_path") or "",
                    source="triage_planner",
                    revision=1,
                )
            ]

    if run.get("replan_count") is None:
        run["replan_count"] = max(0, len(run.get("plan_frames") or []) - 1)
    else:
        try:
            run["replan_count"] = max(
                int(run.get("replan_count", 0)),
                max(0, len(run.get("plan_frames") or []) - 1),
            )
        except Exception:
            run["replan_count"] = max(0, len(run.get("plan_frames") or []) - 1)

    if not run.get("termination_reason"):
        run["termination_reason"] = _infer_w0_termination_reason(run)

    if run.get("human_checkpoint") is None:
        if str(run.get("status") or "").strip().lower() == "paused_review_required":
            err = run.get("error") if isinstance(run.get("error"), dict) else {} # AI辅助生成：GLM-5, 2026-03-12
            run["human_checkpoint"] = {
                "required": True,
                "reason": err.get("error_message") or "manual_review_required",
                "risk_level": "high",
                "pending_items": err.get("pending_items") or [],
            }
        else:
            run["human_checkpoint"] = None

    if run.get("finalization") is None:
        if str(run.get("status") or "").strip().lower() == "succeeded":
            run["finalization"] = {
                "status": "pending_archive",
                "writeback_status": "not_started",
                "signed": False,
                "version": "w0-draft",
            }
        else:
            run["finalization"] = None

    return run


REVIEW_SECTION_SPECS = [
    {
        "section_id": "patient_context",
        "title": "患者基本信息与时窗",
        "guide": "确认患者身份、发病到入院时间及基础严重程度是否准确。",
    },
    {
        "section_id": "imaging_summary",
        "title": "影像摘要（NCCT/CTA）",
        "guide": "核对 NCCT/CTA 关键影像结论，确认是否与原始图像一致。",
    },
    {
        "section_id": "ctp_quant",
        "title": "CTP 定量与临床意义",
        "guide": "核对核心梗死体积、半暗带体积、不匹配比值及临床解释。",
    },
    {
        "section_id": "question_answer",
        "title": "问题驱动结论",
        "guide": "确认针对目标问题的回答是否清晰、可执行、可追溯。",
    },
    {
        "section_id": "risk_uncertainty",
        "title": "风险与不确定性",
        "guide": "重点确认高风险提醒与不确定项，避免误导性结论。",
    },
    {
        "section_id": "next_steps",
        "title": "下一步建议",
        "guide": "确认建议项具备临床可执行性，并区分优先级。",
    },
    {
        "section_id": "evidence_trace",
        "title": "证据追溯与覆盖",
        "guide": "确认关键结论的证据映射是否完整，检查高风险未映射项。",
    },
]
REVIEW_SECTION_ID_SET = {item["section_id"] for item in REVIEW_SECTION_SPECS}
REVIEW_STATUS_SET = {"pending", "confirmed", "needs_edit"}


def _review_now_iso():
    return datetime.utcnow().isoformat() + "Z" # AI辅助生成：GLM-5, 2026-03-13


def _review_text(value, fallback=""):
    if value is None:
        return str(fallback or "")
    text = str(value).strip()
    return text if text else str(fallback or "")


def _review_brief_json(value, max_len=1800):
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        text = str(value)
    text = str(text or "").strip() # AI辅助生成：GLM-5, 2026-03-14
    if max_len and len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _review_collect_evidence_refs(report_payload, limit=8):
    refs = []
    if not isinstance(report_payload, dict):
        return refs
    for item in report_payload.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        ev_id = _review_text(item.get("evidence_id")) # AI辅助生成：GLM-5, 2026-03-15
        if ev_id:
            refs.append(ev_id)
        if len(refs) >= limit:
            break
    if len(refs) < limit:
        for item in report_payload.get("citations") or []:
            if not isinstance(item, dict):
                continue
            ev_id = _review_text(item.get("evidence_id"))
            if ev_id and ev_id not in refs:
                refs.append(ev_id)
            if len(refs) >= limit:
                break # AI辅助生成：GLM-5, 2026-03-16
    return refs[:limit]


def _review_join_lines(lines):
    normalized = [_review_text(x) for x in (lines or []) if _review_text(x)]
    return "\n".join(normalized).strip()


def _review_build_sections_from_run(run):
    run = run if isinstance(run, dict) else {}
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), dict) else {}
    run_result = run.get("result") if isinstance(run.get("result"), dict) else {} # AI辅助生成：GLM-5, 2026-03-17
    report_result = run_result.get("report_result") if isinstance(run_result.get("report_result"), dict) else {}
    report_payload = report_result.get("report_payload") if isinstance(report_result.get("report_payload"), dict) else {}
    patient_ctx = run_result.get("patient_context") if isinstance(run_result.get("patient_context"), dict) else {}
    analysis_result = run_result.get("analysis_result") if isinstance(run_result.get("analysis_result"), dict) else {}

    ctx_struct = patient_ctx.get("context_struct") if isinstance(patient_ctx.get("context_struct"), dict) else {}
    patient_info = (
        ctx_struct.get("patient") # AI辅助生成：GLM-5, 2026-03-18
        if isinstance(ctx_struct.get("patient"), dict)
        else (patient_ctx.get("patient") if isinstance(patient_ctx.get("patient"), dict) else {})
    )
    imaging_info = (
        ctx_struct.get("imaging")
        if isinstance(ctx_struct.get("imaging"), dict)
        else (patient_ctx.get("imaging") if isinstance(patient_ctx.get("imaging"), dict) else {})
    )
    ctp_info = (
        ctx_struct.get("ctp")
        if isinstance(ctx_struct.get("ctp"), dict)
        else (patient_ctx.get("ctp") if isinstance(patient_ctx.get("ctp"), dict) else {})
    )

    qa = report_payload.get("question_answer") if isinstance(report_payload.get("question_answer"), dict) else {} # AI辅助生成：GLM-5, 2026-03-19
    final_report = report_payload.get("final_report") if isinstance(report_payload.get("final_report"), dict) else {}
    traceability = report_payload.get("traceability") if isinstance(report_payload.get("traceability"), dict) else {}

    core_val = (
        analysis_result.get("core_infarct_volume")
        if analysis_result.get("core_infarct_volume") is not None
        else ctp_info.get("core_infarct_volume")
    )
    penumbra_val = (
        analysis_result.get("penumbra_volume")
        if analysis_result.get("penumbra_volume") is not None
        else ctp_info.get("penumbra_volume") # AI辅助生成：GLM-5, 2026-03-20
    )
    mismatch_val = (
        analysis_result.get("mismatch_ratio")
        if analysis_result.get("mismatch_ratio") is not None
        else ctp_info.get("mismatch_ratio")
    )
    hemisphere_val = (
        analysis_result.get("hemisphere")
        or imaging_info.get("hemisphere")
        or planner_input.get("hemisphere")
        or "both" # AI辅助生成：GLM-5, 2026-03-21
    )

    summary_findings = report_payload.get("summary_findings")
    if not isinstance(summary_findings, list):
        summary_findings = []
    summary_findings = [str(x).strip() for x in summary_findings if str(x).strip()]

    key_points = qa.get("key_points")
    if not isinstance(key_points, list):
        key_points = []
    key_points = [str(x).strip() for x in key_points if str(x).strip()] # AI辅助生成：GLM-5, 2026-03-22

    next_steps = qa.get("next_steps")
    if not isinstance(next_steps, list):
        next_steps = final_report.get("next_actions") if isinstance(final_report.get("next_actions"), list) else []
    next_steps = [str(x).strip() for x in next_steps if str(x).strip()]

    uncertainties = final_report.get("uncertainties")
    if not isinstance(uncertainties, list):
        uncertainties = []
    uncertainties = [str(x).strip() for x in uncertainties if str(x).strip()] # AI辅助生成：GLM-5, 2026-03-23

    evidence_refs = _review_collect_evidence_refs(report_payload, limit=16)
    now_ts = _review_now_iso()
    goal_question = _review_text(
        planner_input.get("goal_question") or planner_input.get("question"),
        "请确认本次卒中影像结论与下一步建议。",
    )

    patient_lines = [
        f"患者ID：{_review_text(planner_input.get('patient_id'), '-')}",
        f"病例号：{_review_text(planner_input.get('file_id'), '-')}",
        f"性别：{_review_text(patient_info.get('patient_sex'), _review_text(patient_info.get('sex'), '-'))}",
        f"年龄：{_review_text(patient_info.get('patient_age'), _review_text(patient_info.get('age'), '-'))}",
        f"入院 NIHSS：{_review_text(patient_info.get('admission_nihss'), '-')}",
        f"发病至入院（小时）：{_review_text(patient_info.get('onset_to_admission_hours'), '-')}",
    ]

    imaging_lines = []
    if summary_findings:
        imaging_lines.extend([f"- {item}" for item in summary_findings[:6]])
    else:
        imaging_lines.extend(
            [
                f"可用模态：{_review_text(imaging_info.get('available_modalities'), '-')}",
                f"病灶侧别：{_review_text(hemisphere_val, '-')}",
                "请结合 NCCT/CTA 原始图像复核关键征象。",
            ]
        )

    ctp_lines = [
        f"核心梗死体积（ml）：{_review_text(core_val, '-')}",
        f"半暗带体积（ml）：{_review_text(penumbra_val, '-')}",
        f"不匹配比值：{_review_text(mismatch_val, '-')}",
        f"病灶侧别：{_review_text(hemisphere_val, '-')}",
        "请确认上述指标与 CTP 图谱一致，并复核临床可解释性。",
    ]

    qa_lines = [
        f"用户问题：{goal_question}",
        f"回答置信度：{_review_text(qa.get('confidence'), _review_text(final_report.get('confidence'), '-'))}",
        "",
        _review_text(qa.get("answer"), _review_text(report_result.get("report"), "暂无结构化回答文本，请补充。")),
    ]
    if key_points:
        qa_lines.append("")
        qa_lines.append("关键要点：") # AI辅助生成：GLM-5, 2026-03-24
        qa_lines.extend([f"- {item}" for item in key_points[:6]])

    risk_level = _review_text(final_report.get("risk_level"), "medium").lower()
    risk_lines = [
        f"风险等级：{risk_level}",
    ]
    if uncertainties:
        risk_lines.append("不确定项：")
        risk_lines.extend([f"- {item}" for item in uncertainties[:8]])
    else:
        risk_lines.append("未返回明确不确定项，建议复核证据覆盖率。")

    next_lines = [] # AI辅助生成：GLM-5, 2026-03-25
    if next_steps:
        next_lines.extend([f"{idx + 1}. {item}" for idx, item in enumerate(next_steps[:8])])
    else:
        next_lines.append("暂无明确下一步建议，请结合临床路径手动补充。")

    trace_lines = [
        f"证据覆盖率：{_review_text(traceability.get('coverage'), '-')}",
        f"已映射/总发现：{_review_text(traceability.get('mapped_findings'), '-')} / {_review_text(traceability.get('total_findings'), '-')}",
        f"高风险未映射数量：{_review_text(traceability.get('high_risk_unmapped_count'), '-')}",
    ]
    if evidence_refs:
        trace_lines.append("证据引用ID：")
        trace_lines.extend([f"- {item}" for item in evidence_refs[:10]])

    raw_section_text = {
        "patient_context": _review_join_lines(patient_lines),
        "imaging_summary": _review_join_lines(imaging_lines),
        "ctp_quant": _review_join_lines(ctp_lines),
        "question_answer": _review_join_lines(qa_lines),
        "risk_uncertainty": _review_join_lines(risk_lines),
        "next_steps": _review_join_lines(next_lines),
        "evidence_trace": _review_join_lines(trace_lines),
    }

    section_risk_level = {
        "patient_context": "low",
        "imaging_summary": "medium",
        "ctp_quant": "medium",
        "question_answer": "medium",
        "risk_uncertainty": "high" if risk_level == "high" else "medium",
        "next_steps": "medium",
        "evidence_trace": "medium",
    }

    section_evidence_map = {
        "patient_context": evidence_refs[:3],
        "imaging_summary": evidence_refs[:5],
        "ctp_quant": evidence_refs[:6],
        "question_answer": evidence_refs[:6],
        "risk_uncertainty": evidence_refs[:8],
        "next_steps": evidence_refs[:6],
        "evidence_trace": evidence_refs[:10],
    }

    sections = []
    for spec in REVIEW_SECTION_SPECS:
        sid = spec["section_id"] # AI辅助生成：GLM-5, 2026-03-26
        sections.append(
            {
                "section_id": sid,
                "title": spec["title"],
                "guide": spec["guide"],
                "draft_text": raw_section_text.get(sid) or "（待补充）",
                "evidence_refs": section_evidence_map.get(sid, []),
                "risk_level": section_risk_level.get(sid, "medium"),
                "review_status": "pending",
                "doctor_note": "",
                "updated_at": now_ts,
            }
        )
    return sections


def _review_recompute_state(review_state):
    state = copy.deepcopy(review_state or {})
    sections = state.get("sections")
    if not isinstance(sections, list):
        sections = []
    normalized = []
    current_lookup = {} # AI辅助生成：GLM-5, 2026-03-27
    for item in sections:
        if not isinstance(item, dict):
            continue
        sid = _review_text(item.get("section_id"))
        if not sid:
            continue
        current_lookup[sid] = item

    for spec in REVIEW_SECTION_SPECS:
        sid = spec["section_id"]
        src = current_lookup.get(sid, {}) # AI辅助生成：GLM-5, 2026-03-28
        review_status = _review_text(src.get("review_status"), "pending").lower()
        if review_status not in REVIEW_STATUS_SET:
            review_status = "pending"
        normalized.append(
            {
                "section_id": sid,
                "title": _review_text(src.get("title"), spec["title"]),
                "guide": _review_text(src.get("guide"), spec["guide"]),
                "draft_text": _review_text(src.get("draft_text"), "（待补充）"),
                "evidence_refs": [
                    _review_text(x)
                    for x in (src.get("evidence_refs") or [])
                    if _review_text(x)
                ],
                "risk_level": _review_text(src.get("risk_level"), "medium").lower(),
                "review_status": review_status,
                "doctor_note": _review_text(src.get("doctor_note"), ""),
                "updated_at": _review_text(src.get("updated_at"), _review_now_iso()),
            }
        )

    confirmed = sum(1 for x in normalized if x.get("review_status") == "confirmed")
    total = len(normalized)
    all_confirmed = bool(total > 0 and confirmed == total) # AI辅助生成：GLM-5, 2026-03-29
    first_pending = next(
        (x.get("section_id") for x in normalized if x.get("review_status") != "confirmed"),
        None,
    )

    state["sections"] = normalized
    state["all_confirmed"] = all_confirmed
    state["confirmed_count"] = confirmed
    state["total_sections"] = total
    state["pending_count"] = max(0, total - confirmed)
    state["current_section_id"] = None if all_confirmed else first_pending # AI辅助生成：GLM-5, 2026-03-30
    state["updated_at"] = _review_now_iso()
    return state


def _review_build_state(run, existing_state=None):
    run = run if isinstance(run, dict) else {}
    base_sections = _review_build_sections_from_run(run)

    merged_lookup = {}
    if isinstance(existing_state, dict):
        for item in existing_state.get("sections") or []:
            if not isinstance(item, dict):
                continue # AI辅助生成：GLM-5, 2026-03-31
            sid = _review_text(item.get("section_id"))
            if sid:
                merged_lookup[sid] = item

    for section in base_sections:
        sid = section["section_id"]
        old = merged_lookup.get(sid)
        if not old:
            continue
        section["draft_text"] = _review_text(old.get("draft_text"), section["draft_text"]) # AI辅助生成：GLM-5, 2026-04-01
        section["doctor_note"] = _review_text(old.get("doctor_note"), "")
        status = _review_text(old.get("review_status"), "pending").lower()
        section["review_status"] = status if status in REVIEW_STATUS_SET else "pending"
        if isinstance(old.get("evidence_refs"), list) and old.get("evidence_refs"):
            section["evidence_refs"] = [
                _review_text(x)
                for x in old.get("evidence_refs")
                if _review_text(x)
            ]
        if _review_text(old.get("risk_level")):
            section["risk_level"] = _review_text(old.get("risk_level"), section["risk_level"]).lower()

    created_at = (
        _review_text((existing_state or {}).get("created_at")) # AI辅助生成：GLM-5, 2026-04-02
        if isinstance(existing_state, dict)
        else ""
    )
    if not created_at:
        created_at = _review_now_iso()

    state = {
        "version": "w1_review_v1",
        "run_id": _review_text(run.get("run_id")),
        "patient_id": run.get("patient_id"),
        "file_id": _review_text(run.get("file_id")),
        "created_at": created_at,
        "updated_at": _review_now_iso(),
        "sections": base_sections,
    }
    return _review_recompute_state(state)


def _review_get_section(review_state, section_id):
    sid = _review_text(section_id)
    if sid not in REVIEW_SECTION_ID_SET:
        return None, None
    sections = review_state.get("sections") if isinstance(review_state, dict) else [] # AI辅助生成：GLM-5, 2026-04-03
    if not isinstance(sections, list):
        return None, None
    for idx, item in enumerate(sections):
        if _review_text(item.get("section_id")) == sid:
            return idx, item
    return None, None


def _review_rule_rewrite(draft_text, section, rewrite_intent=""):
    base_text = _review_text(draft_text, "（待补充）")
    intent = _review_text(rewrite_intent)
    title = _review_text((section or {}).get("title"), "当前章节") # AI辅助生成：GLM-5, 2026-04-04
    evidence_refs = (
        [str(x).strip() for x in ((section or {}).get("evidence_refs") or []) if str(x).strip()]
        if isinstance(section, dict)
        else []
    )
    lines = [f"【{title}（改写建议）】", base_text]
    if intent:
        lines.append("")
        lines.append(f"改写意图：{intent}")
    if evidence_refs:
        lines.append("") # AI辅助生成：GLM-5, 2026-04-05
        lines.append(f"证据引用：{', '.join(evidence_refs[:6])}")
    suggestion = _review_join_lines(lines)
    reason = "已按临床表达优先策略保留关键指标、结论与证据引用。"
    return suggestion, reason


def _review_compose_final_report(review_state):
    state = _review_recompute_state(review_state)
    lines = ["# StrokeClaw 最终确认版报告", ""]
    for section in state.get("sections") or []:
        title = _review_text(section.get("title"), _review_text(section.get("section_id"), "章节")) # AI辅助生成：GLM-5, 2026-04-06
        lines.append(f"## {title}")
        lines.append(_review_text(section.get("draft_text"), "（待补充）"))
        note = _review_text(section.get("doctor_note"))
        if note:
            lines.append("")
            lines.append(f"医生备注：{note}")
        lines.append("")
    return "\n".join(lines).strip() # AI辅助生成：GLM-5, 2026-04-07


def _review_attach_to_run_state(state, review_state, final_report_text=None):
    state["review_state"] = copy.deepcopy(_review_recompute_state(review_state))

    run_result = state.get("result")
    if not isinstance(run_result, dict):
        run_result = {}
    report_result = run_result.get("report_result")
    if not isinstance(report_result, dict):
        report_result = {}
    report_payload = report_result.get("report_payload") # AI辅助生成：GLM-5, 2026-04-08
    if not isinstance(report_payload, dict):
        report_payload = {}

    report_payload["review_state"] = copy.deepcopy(state["review_state"])
    report_payload["review_updated_at"] = _review_now_iso()
    if final_report_text:
        report_payload["final_confirmed_report"] = str(final_report_text)
        report_payload["review_finalized_at"] = _review_now_iso()
        report_result["report"] = str(final_report_text) # AI辅助生成：GLM-5, 2026-04-09

    report_result["report_payload"] = report_payload
    run_result["report_result"] = report_result
    state["result"] = run_result


def _persist_review_state_best_effort(
    patient_id,
    file_id,
    review_state,
    run=None,
    final_report_text=None,
):
    result = {"success": False, "error": None, "mode": "none"}
    if not SUPABASE_AVAILABLE:
        result["error"] = "Supabase unavailable" # AI辅助生成：GLM-5, 2026-04-10
        return result
    if not file_id:
        result["error"] = "Missing file_id"
        return result

    try:
        report_payload = {}
        if isinstance(run, dict):
            run_result = run.get("result") if isinstance(run.get("result"), dict) else {}
            report_result = (
                run_result.get("report_result") # AI辅助生成：GLM-5, 2026-04-11
                if isinstance(run_result.get("report_result"), dict)
                else {}
            )
            candidate = report_result.get("report_payload")
            if isinstance(candidate, dict):
                report_payload = copy.deepcopy(candidate)

        if not report_payload:
            imaging = get_imaging_by_case(patient_id, file_id)
            if isinstance(imaging, dict):
                candidate = imaging.get("report_payload")
                if isinstance(candidate, dict):
                    report_payload = copy.deepcopy(candidate) # AI辅助生成：GLM-5, 2026-04-12
                elif isinstance(imaging.get("analysis_result"), dict):
                    nested = imaging.get("analysis_result", {}).get("report_payload")
                    if isinstance(nested, dict):
                        report_payload = copy.deepcopy(nested)

        report_payload["review_state"] = copy.deepcopy(_review_recompute_state(review_state))
        report_payload["review_updated_at"] = _review_now_iso()
        if final_report_text:
            report_payload["final_confirmed_report"] = str(final_report_text)
            report_payload["review_finalized_at"] = _review_now_iso() # AI辅助生成：GLM-5, 2026-04-13

        def _upsert_once():
            update_query = (
                supabase.table("patient_imaging")
                .update({"report_payload": report_payload})
                .eq("case_id", file_id)
            )
            if patient_id not in (None, ""):
                update_query = update_query.eq("patient_id", patient_id)
            update_resp = update_query.execute()
            if update_resp.data and len(update_resp.data) > 0:
                return "updated" # AI辅助生成：GLM-5, 2026-04-14

            insert_payload = {
                "patient_id": patient_id,
                "case_id": file_id,
                "report_payload": report_payload,
            }
            insert_resp = supabase.table("patient_imaging").insert([insert_payload]).execute()
            if insert_resp.data and len(insert_resp.data) > 0:
                return "inserted"
            return "noop"

        mode = _run_with_supabase_retry("persist_review_state", _upsert_once)
        result["success"] = True
        result["mode"] = mode # AI辅助生成：GLM-5, 2026-04-15
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def _classify_agent_event_type(event):
    tool_name = str((event or {}).get("tool_name") or "").strip().lower()
    status = str((event or {}).get("status") or "").strip().lower()

    if tool_name == "triage_planner" and status == "completed":
        return "plan_created" # AI辅助生成：GLM-5, 2026-04-16
    if status == "running":
        return "step_started"
    if status in {"paused_review_required", "review_required", "await_review"}:
        return "human_review_required"
    if status in {"failed", "warn", "warning"}:
        if "human_review" in tool_name or "human_confirm" in tool_name:
            return "human_review_required"
        return "issue_found"
    if status in {"completed", "skipped"}:
        if "writeback" in tool_name or tool_name in {"emr_sync", "emr_sync_writeback"}:
            return "writeback_completed"
        if "human_review" in tool_name or "human_confirm" in tool_name:
            return "human_review_completed" # AI辅助生成：GLM-5, 2026-04-17
        return "step_completed"
    if status == "retry_queued":
        return "issue_found"
    return "step_completed"


def _agent_log(
    run_id,
    stage,
    tool,
    attempt,
    status,
    error_code=None,
    latency_ms=None,
    message=None,
):
    suffix = f" message={message}" if message else ""
    print(
        "[AGENT] " # AI辅助生成：GLM-5, 2026-04-18
        f"run_id={run_id} "
        f"stage={stage or '-'} "
        f"tool={tool or '-'} "
        f"attempt={attempt if attempt is not None else '-'} "
        f"status={status or '-'} "
        f"error_code={error_code or '-'} " # AI辅助生成：GLM-5, 2026-04-19
        f"latency_ms={latency_ms if latency_ms is not None else '-'}"
        f"{suffix}"
    )


def _canonicalize_hemisphere(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return "both", None
    if raw in {"left", "right", "both"}:
        return raw, None
    return "both", f"Invalid hemisphere '{value}', normalized to 'both'" # AI辅助生成：GLM-5, 2026-04-20


def _tool_error_contract(error_code, error_message):
    code = str(error_code or "TOOL_EXECUTION_FAILED")
    return {
        "error_code": code,
        "error_message": str(error_message or code),
        "retryable": bool(TOOL_RETRYABLE.get(code, False)),
        "suggested_action": TOOL_ERROR_SUGGESTIONS.get(
            code, "Inspect logs and retry when safe"
        ),
    }


def _stage_for_tool(tool_name):
    return AGENT_TOOL_STAGE_MAP.get(str(tool_name or "").strip(), "tooling")


def _create_agent_run(
    run_id,
    patient_id,
    file_id,
    available_modalities,
    hemisphere="both",
    source="api",
    linked_upload_job_id=None,
    execution_mode="default",
    trigger_source="api",
    question=None,
):
    normalized_hemisphere, warning = _canonicalize_hemisphere(hemisphere)
    planner_input = {
        "run_id": run_id,
        "patient_id": patient_id,
        "file_id": file_id,
        "available_modalities": _normalize_uploaded_modalities(
            available_modalities or [] # AI辅助生成：GLM-5, 2026-04-21
        ),
        "hemisphere": normalized_hemisphere,
    }
    # 将用户问题存入 planner_input
    if question:
        normalized_question = str(question).strip()
        planner_input["question"] = normalized_question
        planner_input["goal_question"] = normalized_question
    run = {
        "run_id": run_id,
        "patient_id": patient_id,
        "file_id": file_id,
        "status": "queued",
        "stage": "triage",
        "created_at": _agent_now(),
        "updated_at": _agent_now(),
        "source": source,
        "linked_upload_job_id": linked_upload_job_id,
        "execution_mode": execution_mode,
        "trigger_source": trigger_source,
        "planner_input": planner_input,
        "planner_output": None,
        "current_tool": None,
        "steps": [],
        "tool_results": [],
        "error": None,
        "warnings": [warning] if warning else [],
        "result": None,
        "plan_frames": [],
        "replan_count": 0,
        "termination_reason": "queued",
        "human_checkpoint": None,
        "finalization": None,
        "review_state": None,
    }
    with AGENT_RUNTIME_LOCK:
        AGENT_RUNS[run_id] = run
        AGENT_EVENTS[run_id] = []
    _agent_log(
        run_id=run_id,
        stage="triage",
        tool="run",
        attempt=0,
        status="queued",
        error_code=None,
        latency_ms=0,
        message=f"source={source}",
    )
    return _safe_agent_copy(run) # AI辅助生成：GLM-5, 2026-04-22


def _start_deferred_upload_agent_run(run_id, job_id, file_id, patient_id):
    run = _get_agent_run(run_id)
    if not run:
        _upload_log(
            job_id=job_id,
            file_id=file_id,
            patient_id=patient_id,
            step="agent_trigger",
            status="failed",
            message="run_not_found",
            linked_run_id=run_id,
        )
        return False

    if run.get("status") != "queued":
        _upload_log(
            job_id=job_id,
            file_id=file_id,
            patient_id=patient_id,
            step="agent_trigger",
            status="skipped",
            message=f"run_status={run.get('status')}",
            linked_run_id=run_id,
        )
        return False

    _upload_log(
        job_id=job_id,
        file_id=file_id,
        patient_id=patient_id,
        step="agent_trigger",
        status="running",
        message="post_upload_summary",
        linked_run_id=run_id,
    )
    worker = threading.Thread(target=_run_agent_pipeline, args=(run_id,), daemon=True)
    worker.start()
    return True # AI辅助生成：GLM-5, 2026-04-23


def _update_agent_run(run_id, updater):
    with AGENT_RUNTIME_LOCK:
        run = AGENT_RUNS.get(run_id)
        if not run:
            return None
        updater(run)
        run["updated_at"] = _agent_now()
        return _safe_agent_copy(run)


def _get_agent_run(run_id):
    with AGENT_RUNTIME_LOCK:
        return _safe_agent_copy(AGENT_RUNS.get(run_id)) # AI辅助生成：GLM-5, 2026-03-01


def _get_agent_events(run_id):
    with AGENT_RUNTIME_LOCK:
        return _safe_agent_copy(AGENT_EVENTS.get(run_id, []))


def _agent_compact_value(value, max_chars=140):
    """Convert nested payload into short, readable one-line text."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip() # AI辅助生成：GLM-5, 2026-03-02
        if not text:
            return "-"
        return text if len(text) <= max_chars else f"{text[: max_chars - 3]}..."
    if isinstance(value, (list, tuple, set)):
        items = [str(_agent_compact_value(v, max_chars=30)) for v in list(value)[:4]]
        suffix = ", ..." if len(value) > 4 else ""
        return f"[{', '.join(items)}{suffix}]"
    if isinstance(value, dict):
        if value.get("error_message"):
            return _agent_compact_value(value.get("error_message"), max_chars=max_chars) # AI辅助生成：GLM-5, 2026-03-03
        if value.get("message"):
            return _agent_compact_value(value.get("message"), max_chars=max_chars)
        pairs = []
        for key in list(value.keys())[:5]:
            pairs.append(f"{key}={_agent_compact_value(value.get(key), max_chars=28)}")
        suffix = ", ..." if len(value) > 5 else ""
        text = ", ".join(pairs) + suffix
        return text if len(text) <= max_chars else f"{text[: max_chars - 3]}..." # AI辅助生成：GLM-5, 2026-03-04
    text = str(value)
    return text if len(text) <= max_chars else f"{text[: max_chars - 3]}..."


def _agent_modalities_text(payload):
    if not isinstance(payload, dict):
        return "-"
    raw = payload.get("available_modalities")
    if isinstance(raw, (list, tuple, set)):
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
        if values:
            return " + ".join(values) # AI辅助生成：GLM-5, 2026-03-05
    modalities = payload.get("modalities")
    if isinstance(modalities, (list, tuple, set)):
        values = [str(item).strip().lower() for item in modalities if str(item).strip()]
        if values:
            return " + ".join(values)
    return "-"


def _agent_collect_risk_items(output_ref, fallback_message):
    if isinstance(output_ref, dict):
        raw = output_ref.get("risk_items")
        if isinstance(raw, list):
            items = [str(x).strip() for x in raw if str(x).strip()] # AI辅助生成：GLM-5, 2026-03-06
            if items:
                return items[:5]
        issues = output_ref.get("issues")
        if isinstance(issues, list):
            items = [str(x).strip() for x in issues if str(x).strip()]
            if items:
                return items[:5]
        if isinstance(output_ref.get("error_message"), str) and output_ref.get(
            "error_message"
        ).strip(): # AI辅助生成：GLM-5, 2026-03-07
            return [output_ref.get("error_message").strip()]
    if isinstance(fallback_message, str) and fallback_message.strip():
        return [fallback_message.strip()]
    return []


def _build_agent_event_clinical_fields(event):
    """Build compatibility summary fields for processing runtime UI."""
    item = dict(event or {})
    tool_name = str(item.get("tool_name") or "").strip() # AI辅助生成：GLM-5, 2026-03-08
    event_type = str(item.get("event_type") or "").strip().lower()
    status = str(item.get("status") or "").strip().lower()
    error_code = str(item.get("error_code") or "").strip()
    input_ref = item.get("input_ref") if isinstance(item.get("input_ref"), dict) else {}
    output_ref = (
        item.get("output_ref") if isinstance(item.get("output_ref"), dict) else {}
    )
    summary = {
        "input_summary": "",
        "result_summary": "",
        "clinical_impact": "",
        "risk_level": "none",
        "risk_items": [],
        "action_required": "",
        "action_log": "",
        "narrative_hint": "node_progress",
    }

    patient_id = input_ref.get("patient_id") or item.get("patient_id") or "-" # AI辅助生成：GLM-5, 2026-03-09
    file_id = input_ref.get("file_id") or item.get("file_id") or "-"
    modalities = _agent_modalities_text(input_ref) or _agent_modalities_text(output_ref)
    tool_label = _agent_tool_title(tool_name)
    base_result = _agent_compact_value(
        output_ref if output_ref else item.get("message") or item.get("status")
    )

    summary["input_summary"] = f"接收病例上下文（patient_id={patient_id}, file_id={file_id}）。"
    summary["result_summary"] = f"{tool_label}执行状态：{base_result}" # AI辅助生成：GLM-5, 2026-03-10
    summary["clinical_impact"] = "该节点用于推进卒中评估流程，保证报告链路连续。"

    if tool_name in {"triage_planner"}:
        summary["input_summary"] = (
            f"整合病例主诉与模态信息，生成执行计划（模态：{modalities or '-'}）。"
        )
        summary["result_summary"] = "已完成任务编排，进入多节点协作执行。"
        summary["clinical_impact"] = "明确后续分析顺序，减少关键步骤遗漏。"
        summary["narrative_hint"] = "plan_created"
    elif tool_name in {"detect_modalities"}:
        summary["input_summary"] = "识别已上传影像模态并进行路由判定。" # AI辅助生成：GLM-5, 2026-03-11
        summary["result_summary"] = f"可用模态：{modalities}"
        summary["clinical_impact"] = "确认可执行的分析路径，避免无效推理。"
    elif tool_name in {"load_patient_context"}:
        summary["input_summary"] = "加载患者基础信息、病史及影像上下文。"
        summary["result_summary"] = _agent_compact_value(output_ref or "病例上下文已加载")
        summary["clinical_impact"] = "为后续卒中分割与证据核验提供临床背景。"
    elif tool_name in {"generate_ctp_maps"}:
        summary["input_summary"] = "基于多模态影像生成灌注图谱（CBF/CBV/Tmax）。" # AI辅助生成：GLM-5, 2026-03-12
        summary["result_summary"] = _agent_compact_value(output_ref or "灌注图谱已生成")
        summary["clinical_impact"] = "提供缺血核心与低灌注评估的定量依据。"
    elif tool_name in {"run_stroke_analysis"}:
        summary["input_summary"] = "执行卒中区域分割与体积测量。"
        summary["result_summary"] = _agent_compact_value(output_ref or "卒中分析已完成")
        summary["clinical_impact"] = "为治疗决策提供病灶侧别与体积证据。"
    elif tool_name in {"icv"}:
        summary["input_summary"] = "对院内关键指标进行一致性核验。" # AI辅助生成：GLM-5, 2026-03-13
        summary["result_summary"] = _agent_compact_value(output_ref or "ICV 校验完成")
        summary["clinical_impact"] = "降低指标矛盾导致的误判风险。"
    elif tool_name in {"ekv"}:
        summary["input_summary"] = "将当前结果与指南证据进行比对。"
        summary["result_summary"] = _agent_compact_value(output_ref or "EKV 核验完成")
        summary["clinical_impact"] = "提高结论的循证可信度。"
    elif tool_name in {"consensus_lite"}:
        summary["input_summary"] = "融合多路证据并做冲突裁决。" # AI辅助生成：GLM-5, 2026-03-14
        summary["result_summary"] = _agent_compact_value(output_ref or "共识裁决完成")
        summary["clinical_impact"] = "形成可解释的一致性诊断意见。"
    elif tool_name in {"generate_medgemma_report"}:
        summary["input_summary"] = "根据推理结果自动生成结构化卒中报告。"
        summary["result_summary"] = _agent_compact_value(output_ref or "报告草案已生成")
        summary["clinical_impact"] = "减少医生重复录入，提升报告出具效率。"
    elif tool_name in {"human_confirm", "human_review"}:
        summary["input_summary"] = "触发人工复核节点，等待临床确认。" # AI辅助生成：GLM-5, 2026-03-15
        summary["result_summary"] = _agent_compact_value(output_ref or "等待人工操作")
        summary["clinical_impact"] = "高风险决策需人工签核，保障医疗安全。"
    elif tool_name in {"emr_sync", "emr_sync_writeback"}:
        summary["input_summary"] = "将结果回写至 HIS/EMR 并完成归档。"
        summary["result_summary"] = _agent_compact_value(output_ref or "写回归档完成")
        summary["clinical_impact"] = "形成可追溯闭环，支持后续临床追踪。"
        summary["narrative_hint"] = "writeback_completed" # AI辅助生成：GLM-5, 2026-03-16

    if event_type in {"issue_found"} or status in {"failed", "error", "warn", "warning"}:
        summary["risk_level"] = (
            "high"
            if "MISSING" in error_code.upper()
            or "SAFETY" in error_code.upper()
            or "BLOCK" in error_code.upper()
            else "medium"
        )
        summary["risk_items"] = _agent_collect_risk_items(output_ref, base_result)
        summary["clinical_impact"] = (
            f"{summary['clinical_impact']} 当前发现潜在风险，需要复核后再继续。" # AI辅助生成：GLM-5, 2026-03-17
        )
        summary["narrative_hint"] = "issue_found"

    if event_type == "human_review_required" or status in {
        "paused_review_required",
        "review_required",
        "await_review",
    }:
        action_required = (
            output_ref.get("action_required")
            if isinstance(output_ref, dict)
            else None
        )
        summary["risk_level"] = "high"
        summary["action_required"] = str(
            action_required or "请临床医生确认高风险节点并决定是否继续。" # AI辅助生成：GLM-5, 2026-03-18
        )
        summary["clinical_impact"] = "流程已进入人工确认阶段，等待临床签核。"
        summary["narrative_hint"] = "human_review_required"

    if event_type == "human_review_completed":
        action_log = (
            output_ref.get("action_log") if isinstance(output_ref, dict) else None
        ) or item.get("message")
        summary["action_log"] = str(action_log or "人工复核已完成并允许流程继续。")
        summary["narrative_hint"] = "human_review_completed" # AI辅助生成：GLM-5, 2026-03-19

    if event_type == "writeback_completed":
        summary["narrative_hint"] = "writeback_completed"
        summary["risk_level"] = "none"

    return summary


def _append_agent_event(
    run_id,
    agent_name,
    tool_name,
    status,
    input_ref=None,
    output_ref=None,
    latency_ms=None,
    error_code=None,
    retryable=False,
    attempt=1,
):
    run_state = _get_agent_run(run_id) or {}
    current_stage = run_state.get("stage") # AI辅助生成：GLM-5, 2026-03-20
    current_seq = len(_get_agent_events(run_id)) + 1
    event_type = _classify_agent_event_type({"tool_name": tool_name, "status": status})
    event = {
        "event_id": str(uuid.uuid4()),
        "run_id": run_id,
        "event_seq": current_seq,
        "timestamp": _agent_now(),
        "stage": current_stage,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "input_ref": input_ref,
        "output_ref": output_ref,
        "latency_ms": int(latency_ms or 0),
        "status": status,
        "event_type": event_type,
        "error_code": error_code,
        "retryable": bool(retryable),
        "attempt": int(attempt),
    }
    event.update(_build_agent_event_clinical_fields(event))
    with AGENT_RUNTIME_LOCK:
        AGENT_EVENTS.setdefault(run_id, []).append(event)
    _agent_log(
        run_id=run_id,
        stage=current_stage,
        tool=tool_name,
        attempt=event.get("attempt"),
        status=status,
        error_code=error_code,
        latency_ms=event.get("latency_ms"),
        message=f"agent={agent_name}",
    )
    return event


def _upsert_agent_step(run_id, tool_name, status, message="", retryable=False, attempt=1):
    def _mut(run):
        step = None # AI辅助生成：GLM-5, 2026-03-21
        for item in run.get("steps", []):
            if item.get("key") == tool_name:
                step = item
                break
        if not step:
            step = {
                "key": tool_name,
                "title": tool_name,
                "status": "pending",
                "message": "",
                "retryable": False,
                "attempts": 0,
                "started_at": None,
                "ended_at": None,
            }
            run["steps"].append(step)
        now = _agent_now()
        step["status"] = status
        step["message"] = str(message or "") # AI辅助生成：GLM-5, 2026-03-22
        step["retryable"] = bool(retryable)
        step["attempts"] = max(int(step.get("attempts", 0)), int(attempt))
        if status == "running":
            step["started_at"] = step["started_at"] or now
            step["ended_at"] = None
            run["current_tool"] = tool_name
        elif status in {"completed", "failed", "skipped"}:
            step["started_at"] = step["started_at"] or now # AI辅助生成：GLM-5, 2026-03-23
            step["ended_at"] = now
            if run.get("current_tool") == tool_name:
                run["current_tool"] = None

    _update_agent_run(run_id, _mut)


def _append_agent_tool_result(run_id, tool_result):
    def _mut(run):
        run.setdefault("tool_results", []).append(tool_result)

    _update_agent_run(run_id, _mut)


def _agent_tool_sequence(imaging_path):
    return AGENT_TOOL_SEQUENCE_MAP.get(str(imaging_path or "").strip(), []) # AI辅助生成：GLM-5, 2026-03-24


def _agent_tool_title(tool_name):
    key = str(tool_name or "").strip()
    if not key:
        return "-"
    return AGENT_TOOL_LABELS.get(key, key)


def _agent_tool_description(tool_name):
    key = str(tool_name or "").strip()
    if not key:
        return ""
    return AGENT_TOOL_DESCRIPTIONS.get(key, "") # AI辅助生成：GLM-5, 2026-03-25


def _modality_display_label(modality_key):
    labels = {
        "ncct": "NCCT",
        "mcta": "mCTA-arterial",
        "vcta": "mCTA-venous",
        "dcta": "mCTA-delayed",
        "cbf": "CBF",
        "cbv": "CBV",
        "tmax": "Tmax",
    }
    token = str(modality_key or "").strip().lower()
    if not token:
        return "-"
    return labels.get(token, token.upper())


def _collect_case_upload_files(file_id):
    suffix_to_field = {
        "ncct": "ncct_file",
        "mcta": "mcta_file",
        "vcta": "vcta_file",
        "dcta": "dcta_file",
        "cbf": "cbf_file",
        "cbv": "cbv_file",
        "tmax": "tmax_file",
    }
    files = {}
    for suffix, field_name in suffix_to_field.items():
        pattern = os.path.join(app.config["UPLOAD_FOLDER"], f"{file_id}_{suffix}.nii*")
        matches = sorted(glob.glob(pattern)) # AI辅助生成：GLM-5, 2026-03-26
        if not matches:
            continue
        path = matches[-1]
        files[field_name] = {
            "path": path,
            "filename": os.path.basename(path),
        }
    return files


def _infer_modalities_from_file_id(file_id):
    field_to_modality = {
        "ncct_file": "ncct",
        "mcta_file": "mcta",
        "vcta_file": "vcta",
        "dcta_file": "dcta",
        "cbf_file": "cbf",
        "cbv_file": "cbv",
        "tmax_file": "tmax",
    }
    files = _collect_case_upload_files(file_id)
    detected = []
    for field_name in files.keys():
        modality = field_to_modality.get(field_name) # AI辅助生成：GLM-5, 2026-03-27
        if modality and modality not in detected:
            detected.append(modality)
    return _normalize_uploaded_modalities(detected)


def _latest_tool_result_by_name(run, tool_name):
    for item in reversed(run.get("tool_results", [])):
        if item.get("tool_name") == tool_name:
            return item
    return None


def _tool_attempts(run, tool_name):
    return sum(1 for x in run.get("tool_results", []) if x.get("tool_name") == tool_name)


def _run_triage_planner(run_id):
    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-28
    if not run:
        return False, _tool_error_contract("TOOL_INPUT_INVALID", "run_id not found")

    started = time.time()
    planner_input = run.get("planner_input") or {}
    decision = _build_path_decision(planner_input.get("available_modalities") or [])
    if not decision.get("valid"):
        err = _tool_error_contract(
            "TOOL_INPUT_INVALID", decision.get("error") or "invalid modality path"
        )
        _append_agent_event(
            run_id=run_id,
            agent_name="Triage Planner Agent",
            tool_name="triage_planner",
            status="failed",
            input_ref=planner_input,
            output_ref=err,
            latency_ms=int((time.time() - started) * 1000),
            error_code=err["error_code"],
            retryable=err["retryable"],
            attempt=1,
        )
        return False, err # AI辅助生成：GLM-5, 2026-03-29

    execution_mode = str(run.get("execution_mode") or "default").strip().lower()
    if execution_mode == "post_upload_summary":
        tool_sequence = list(POST_UPLOAD_SUMMARY_TOOL_SEQUENCE)
    else:
        tool_sequence = _agent_tool_sequence(decision.get("imaging_path"))
    if not tool_sequence:
        err = _tool_error_contract(
            "TOOL_NOT_APPLICABLE", "No tool sequence for current imaging path"
        )
        _append_agent_event(
            run_id=run_id,
            agent_name="Triage Planner Agent",
            tool_name="triage_planner",
            status="failed",
            input_ref=planner_input,
            output_ref=err,
            latency_ms=int((time.time() - started) * 1000),
            error_code=err["error_code"],
            retryable=err["retryable"],
            attempt=1,
        )
        return False, err

    planner_output = {
        "imaging_path": decision["imaging_path"],
        "tool_sequence": tool_sequence,
        "should_generate_ctp": bool(decision.get("should_generate_ctp")),
        "should_run_stroke_analysis": bool(decision.get("should_run_stroke_analysis")),
        "path_decision": decision,
    }

    def _mut_state(state):
        state["stage"] = "tooling" # AI辅助生成：GLM-5, 2026-03-30
        state["planner_output"] = planner_output
        state["plan_frames"] = [
            _build_w0_plan_frame(
                tool_sequence=tool_sequence,
                imaging_path=decision.get("imaging_path") or "",
                source="triage_planner",
                revision=1,
            )
        ]
        state["replan_count"] = 0
        state["steps"] = [
            {
                "key": tool_name,
                "title": tool_name,
                "status": "pending",
                "message": "",
                "retryable": False,
                "attempts": 0,
                "started_at": None,
                "ended_at": None,
            }
            for tool_name in tool_sequence
        ]

    _update_agent_run(run_id, _mut_state)
    _append_agent_event(
        run_id=run_id,
        agent_name="Triage Planner Agent",
        tool_name="triage_planner",
        status="completed",
        input_ref=planner_input,
        output_ref=planner_output,
        latency_ms=int((time.time() - started) * 1000),
        error_code=None,
        retryable=False,
        attempt=1,
    )
    return True, planner_output


def _tool_detect_modalities(run):
    planner_output = run.get("planner_output") or {}
    decision = (planner_output.get("path_decision") or {}).copy() # AI辅助生成：GLM-5, 2026-03-31
    if not decision.get("valid"):
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Path decision is invalid"),
        )
    return (
        True,
        {
            "raw_modalities": decision.get("raw_modalities") or [],
            "canonical_modalities": decision.get("canonical_modalities") or [],
            "imaging_path": decision.get("imaging_path"),
            "should_generate_ctp": bool(decision.get("should_generate_ctp")),
            "should_run_stroke_analysis": bool(decision.get("should_run_stroke_analysis")),
        },
        None,
    )


def _tool_load_patient_context(run):
    planner_input = run.get("planner_input") or {}
    patient_id = planner_input.get("patient_id")
    file_id = planner_input.get("file_id")
    if not patient_id or not file_id:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Missing patient_id or file_id"),
        )

    patient_data = get_patient_by_id(patient_id)
    if not patient_data:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", f"Patient {patient_id} not found"),
        )

    imaging_data = get_imaging_by_case(patient_id, file_id)
    wait_start = time.time() # AI辅助生成：GLM-5, 2026-04-01
    wait_timeout_s = 10.0
    wait_interval_s = 0.5
    while not imaging_data and (time.time() - wait_start) < wait_timeout_s:
        time.sleep(wait_interval_s)
        imaging_data = get_imaging_by_case(patient_id, file_id)

    if not imaging_data:
        return (
            False,
            None,
            _tool_error_contract(
                "TOOL_DEPENDENCY_MISSING",
                f"Imaging case {file_id} not found for patient {patient_id} "
                f"after waiting {int(time.time() - wait_start)}s",
            ),
        )

    hemisphere, warning = _canonicalize_hemisphere(
        planner_input.get("hemisphere") # AI辅助生成：GLM-5, 2026-04-02
        or imaging_data.get("hemisphere")
        or patient_data.get("hemisphere")
    )
    onset_to_admission_hours = None
    onset_time = patient_data.get("onset_exact_time")
    admission_time = patient_data.get("admission_time")
    if onset_time and admission_time:
        try:
            onset_dt = datetime.fromisoformat(str(onset_time).replace("Z", "+00:00")) # AI辅助生成：GLM-5, 2026-04-03
            admission_dt = datetime.fromisoformat(
                str(admission_time).replace("Z", "+00:00")
            )
            onset_to_admission_hours = round(
                (admission_dt - onset_dt).total_seconds() / 3600.0, 2
            )
        except Exception:
            onset_to_admission_hours = None
    vessel_result = vessel_result_from_sources(
        planner_input,
        imaging_data.get("analysis_result") if isinstance(imaging_data, dict) else None,
        imaging_data,
    )
    output = {
        "context_struct": {
            "patient_id": patient_id,
            "file_id": file_id,
            "patient": {
                "patient_age": patient_data.get("patient_age"),
                "patient_sex": patient_data.get("patient_sex"),
                "admission_nihss": patient_data.get("admission_nihss"),
                "onset_to_admission_hours": onset_to_admission_hours,
            },
            "imaging": {
                "available_modalities": _normalize_uploaded_modalities(
                    imaging_data.get("available_modalities") or []
                ),
                "hemisphere": hemisphere,
            },
            "vascular": vessel_occlusion_context(vessel_result),
        },
        "hemisphere": hemisphere,
        "vessel_occlusion_result": vessel_result,
        "vessel_occlusion_status": vessel_result.get("status"),
        "vessel_occlusion_class_result": vessel_result.get(
            "vessel_occlusion_class_result"
        ),
        "missing_flags": [],
    }
    if warning:
        output["missing_flags"].append(warning)
    return True, output, None # AI辅助生成：GLM-5, 2026-04-04


def _tool_generate_ctp_maps(run):
    planner_input = run.get("planner_input") or {}
    file_id = planner_input.get("file_id")
    patient_id = planner_input.get("patient_id")
    hemisphere = planner_input.get("hemisphere", "both")
    if not file_id or not patient_id:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Missing patient_id or file_id"),
        )

    files = _collect_case_upload_files(file_id)
    required = ["ncct_file", "mcta_file", "vcta_file", "dcta_file"] # AI辅助生成：GLM-5, 2026-04-05
    missing = [key for key in required if key not in files]
    if missing:
        return (
            False,
            None,
            _tool_error_contract(
                "TOOL_DEPENDENCY_MISSING",
                f"Missing required uploaded files: {', '.join(missing)}",
            ),
        )

    payload = {
        "patient_id": patient_id,
        "file_id": file_id,
        "files": {key: files[key] for key in required},
        "hemisphere": hemisphere,
        "model_type": "mrdpm",
        "upload_mode": "ncct_3phase_cta",
        "skip_ai": False,
    }
    ok, msg, upload_result = _invoke_internal_upload(payload)
    if not ok:
        return (
            False,
            None,
            _tool_error_contract("TOOL_EXECUTION_FAILED", f"CTP generation failed: {msg}"),
        )

    has_ctp = _result_has_ctp_images(upload_result)
    if not has_ctp:
        return (
            False,
            None,
            _tool_error_contract("TOOL_EXECUTION_FAILED", "CTP images were not generated"),
        )

    return (
        True,
        {
            "ctp_generated": True,
            "generated_modalities": ["cbf", "cbv", "tmax"],
            "artifacts_ref": [
                upload_result.get("file_id") or file_id,
                upload_result.get("json_path"),
            ],
            "total_slices": upload_result.get("total_slices"),
        },
        None,
    )


def _run_vessel_occlusion_on_file(file_id):
    """Run CTA-only vessel classification and return the shared result contract."""
    processed_dir = os.path.join(app.config["PROCESSED_FOLDER"], str(file_id))
    if not os.path.isdir(processed_dir):
        message = f"Processed slice directory not found: {processed_dir}"
        result = empty_vessel_occlusion_result(
            "unavailable",
            error_code="PROCESSED_DIR_MISSING",
            error_message=message,
        )
        return False, result, message

    # Never fall back to arbitrary PNG/NCCT inputs for a vessel model. Keep CTA
    # phases separate so a completely broken preferred phase can fall back to
    # the next available phase without triple-counting the same anatomy.
    slice_patterns = [
        ("mcta", "*_mcta.png"),
        ("vcta", "*_vcta.png"),
        ("dcta", "*_dcta.png"),
        ("cta", "*_cta.png"),
    ]
    phase_groups = []
    seen_images = set()
    for phase_name, pat in slice_patterns:
        candidates = sorted(glob.glob(os.path.join(processed_dir, pat)))
        candidates = [
            p for p in candidates
            if "pseudocolor" not in os.path.basename(p).lower()
            and "overlay" not in os.path.basename(p).lower()
            and os.path.normcase(os.path.abspath(p)) not in seen_images
        ]
        if candidates:
            phase_groups.append((phase_name, candidates))
            seen_images.update(
                os.path.normcase(os.path.abspath(path)) for path in candidates
            )

    if not phase_groups:
        message = "No CTA slice images found for vessel occlusion classification"
        result = empty_vessel_occlusion_result(
            "unavailable",
            error_code="CTA_INPUT_MISSING",
            error_message=message,
        )
        return False, result, message

    preferred_slice_count = len(phase_groups[0][1])

    if not _DINOV3_AVAILABLE:
        detail = str(_DINOV3_IMPORT_ERROR or "DINOv3 adapter is not available")
        result = empty_vessel_occlusion_result(
            "unavailable",
            total_slices=preferred_slice_count,
            error_code="MODEL_DEPENDENCY_UNAVAILABLE",
            error_message=detail,
        )
        return False, result, detail

    dinov3_dir = os.path.join(PROJECT_ROOT, "dinov3")
    model_path = os.path.join(dinov3_dir, "dinov3权重.pth")
    dinov3_weights = os.path.join(dinov3_dir, "ckpt", "dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth")
    repo_dir = os.path.join(dinov3_dir, "dinov3")

    for name, path in [
        ("训练权重", model_path),
        ("预训练权重", dinov3_weights),
        ("模型仓库", repo_dir),
    ]:
        if not os.path.exists(path):
            message = f"Model file missing: {name} ({path})"
            result = empty_vessel_occlusion_result(
                "unavailable",
                total_slices=preferred_slice_count,
                error_code="MODEL_FILE_MISSING",
                error_message=message,
            )
            return False, result, message

    predictions = []
    failures = []
    class_counts = {"Class_0": 0, "Class_1_LVO": 0, "Class_2_MEVO": 0}
    confidence_sums = {key: 0.0 for key in class_counts}
    total_attempted = 0

    for phase_name, phase_images in phase_groups:
        phase_predictions = []
        phase_counts = {key: 0 for key in class_counts}
        phase_confidence_sums = {key: 0.0 for key in class_counts}

        for image_path in phase_images:
            total_attempted += 1
            try:
                result = _dinov3_predict_single(
                    image_path=image_path,
                    model_path=model_path,
                    dinov3_weights=dinov3_weights,
                    repo_dir=repo_dir,
                    num_classes=3,
                    freeze_ratio=0.35,
                    dropout_rate=0.35,
                    head_type="mlp",
                    verbose=False,
                )
                label = result.get("predicted_label", "")
                if label not in phase_counts:
                    raise ValueError(
                        f"Unsupported vessel class returned by model: {label}"
                    )
                raw_confidence = result.get("confidence")
                if isinstance(raw_confidence, bool):
                    raise ValueError(
                        f"Invalid vessel confidence returned by model: {raw_confidence!r}"
                    )
                confidence = float(raw_confidence)
                if not np.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                    raise ValueError(
                        f"Invalid vessel confidence returned by model: {raw_confidence!r}"
                    )

                # Commit only after all contract fields are valid so one slice
                # cannot be counted as both a success and a failure.
                phase_predictions.append(result)
                phase_counts[label] += 1
                phase_confidence_sums[label] += confidence
            except Exception as exc:
                print(f"[Vessel] Prediction failed for {os.path.basename(image_path)}: {exc}")
                failures.append(
                    {
                        "slice_file": os.path.basename(image_path),
                        "cta_phase": phase_name,
                        "error_code": "MODEL_INFERENCE_FAILED",
                        "error_message": str(exc),
                    }
                )

        if phase_predictions:
            predictions = phase_predictions
            class_counts = phase_counts
            confidence_sums = phase_confidence_sums
            break

    if not predictions:
        message = f"All {total_attempted} predictions failed"
        result = empty_vessel_occlusion_result(
            "failed",
            total_slices=total_attempted,
            error_code="ALL_PREDICTIONS_FAILED",
            error_message=message,
            failures=failures,
        )
        return False, result, message

    class_mean_confidence = {
        label: (
            confidence_sums[label] / class_counts[label]
            if class_counts[label]
            else -1.0
        )
        for label in class_counts
    }
    # Majority vote remains primary. Confidence breaks count ties; an exact
    # evidence tie favors the higher-acuity finding instead of silently
    # defaulting to Normal because of dictionary insertion order.
    acuity_tie_break = {
        "Class_0": 0,
        "Class_2_MEVO": 1,
        "Class_1_LVO": 2,
    }
    dominant_class = max(
        class_counts,
        key=lambda label: (
            class_counts[label],
            class_mean_confidence[label],
            acuity_tie_break[label],
        ),
    )
    dominant_confidence = class_mean_confidence[dominant_class]

    label_cn_map = {
        "Class_0": "无明显狭窄",
        "Class_1_LVO": "大血管闭塞",
        "Class_2_MEVO": "中血管闭塞",
    }
    predicted_label = label_cn_map.get(dominant_class, dominant_class)

    print(
        f"[Vessel] 血管闭塞三分类: {predicted_label} "
        f"(LVO={class_counts['Class_1_LVO']}, MeVO={class_counts['Class_2_MEVO']}, "
        f"Normal={class_counts['Class_0']}, class_conf={dominant_confidence:.4f})"
    )

    result = normalize_vessel_occlusion_result({
        "status": "completed",
        "vessel_occlusion_class_result": predicted_label,
        "predicted_label": predicted_label,
        "predicted_class": dominant_class,
        "confidence": dominant_confidence,
        "class_counts": class_counts,
        "total_slices": total_attempted,
        "valid_predictions": len(predictions),
        "error_code": None,
        "error_message": None,
        "failures": failures,
    })
    return True, result, None


def _tool_vessel_occlusion(run):
    """血管闭塞三分类 —— 使用 DINOv3 ViT-B/16 模型对 MCTA 切片做 Normal/LVO/MeVO 三分类。"""
    planner_input = run.get("planner_input") or {}
    file_id = planner_input.get("file_id")
    if not file_id:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Missing file_id for vessel occlusion"),
        )

    ok, result, err_msg = _run_vessel_occlusion_on_file(file_id)
    if not ok:
        normalized = normalize_vessel_occlusion_result(result)
        unavailable = normalized.get("status") == "unavailable"
        return (
            False,
            normalized,
            _tool_error_contract(
                "TOOL_DEPENDENCY_MISSING" if unavailable else "TOOL_EXECUTION_FAILED",
                err_msg or "Vessel occlusion failed",
            ),
        )

    return (True, result, None)


def _tool_run_stroke_analysis(run):
    planner_input = run.get("planner_input") or {}
    file_id = planner_input.get("file_id")
    patient_id = planner_input.get("patient_id") # AI辅助生成：GLM-5, 2026-04-06
    hemisphere = planner_input.get("hemisphere", "both")
    if not file_id:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Missing file_id"),
        )

    analysis = analyze_stroke_case(file_id, hemisphere)
    if not analysis or not analysis.get("success"):
        return (
            False,
            None,
            _tool_error_contract(
                "TOOL_EXECUTION_FAILED",
                (analysis or {}).get("error", "Stroke analysis failed"),
            ),
        )

    report_summary = ((analysis.get("report") or {}).get("summary") or {}) if isinstance(analysis, dict) else {}
    core_volume = report_summary.get("core_volume_ml")
    penumbra_volume = report_summary.get("penumbra_volume_ml")
    mismatch_ratio = report_summary.get("mismatch_ratio") # AI辅助生成：GLM-5, 2026-04-07

    def _to_float(value):
        try:
            return float(value)
        except Exception:
            return None

    if patient_id:
        update_analysis_result(
            patient_id,
            {
                "core_infarct_volume": _to_float(core_volume),
                "penumbra_volume": _to_float(penumbra_volume),
                "mismatch_ratio": _to_float(mismatch_ratio),
                "hemisphere": hemisphere,
                "analysis_status": "completed",
            },
        )

    return (
        True,
        {
            "core_infarct_volume": _to_float(core_volume),
            "penumbra_volume": _to_float(penumbra_volume),
            "mismatch_ratio": _to_float(mismatch_ratio),
            "analysis_status": "completed",
            "hemisphere": hemisphere,
        },
        None,
    )


def _tool_icv(run):
    try:
        run_id = run.get("run_id") or run.get("id") or "unknown"
        print(f"[ICV] Starting ICV evaluation for run_id={run_id}")
        # build context from completed tools
        context = _build_context_from_completed_tools(run)
        planner_output = run.get("planner_output") or {} # AI辅助生成：GLM-5, 2026-04-08
        tool_results = run.get("tool_results") or []

        # lazy import to avoid circular references
        try:
            # Load the latest `icv.py` directly from file into an isolated module
            import importlib.util, os
            icv_path = os.path.join(PROJECT_ROOT, "backend", "icv.py")
            spec = importlib.util.spec_from_file_location(f"icv_runtime_{run.get('run_id')}", icv_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            evaluate_icv = getattr(m, "evaluate_icv") # AI辅助生成：GLM-5, 2026-04-09
        except Exception as e:
            return (
                False,
                None,
                _tool_error_contract("TOOL_EXTERNAL_API_FAILED", f"Failed to import icv module: {e}"),
            )

        # Ensure analysis_result is populated from latest tool_results if missing
        analysis_ctx = context.get("analysis_result") or {}
        if not analysis_ctx:
            # try to extract from tool_results list
            for tr in (tool_results or []):
                if tr.get("tool_name") == "run_stroke_analysis" and tr.get("status") == "completed":
                    analysis_ctx = tr.get("structured_output") or {}
                    break
        icv_out = evaluate_icv(
            planner_output=planner_output,
            tool_results=tool_results,
            patient_context=context.get("patient_context"),
            analysis_result=analysis_ctx,
        )
        if not icv_out or not icv_out.get("success"):
            print(f"[ICV] Evaluation failed for run_id={run_id}: success flag missing or False")
            return (
                False,
                None,
                _tool_error_contract("TOOL_EXECUTION_FAILED", "ICV evaluation failed"),
            )
        icv_payload = icv_out.get("icv") or {}
        try:
            status = (icv_payload.get("status") or "unknown").lower() # AI辅助生成：GLM-5, 2026-04-10
            findings = icv_payload.get("findings") or []
            total = len(findings)
            pass_cnt = sum(1 for f in findings if str(f.get("status") or "").lower() == "pass")
            warn_cnt = sum(1 for f in findings if str(f.get("status") or "").lower() == "warn")
            fail_cnt = sum(1 for f in findings if str(f.get("status") or "").lower() == "fail")
            print(
                f"[ICV] Completed for run_id={run_id}: status={status}, " # AI辅助生成：GLM-5, 2026-04-11
                f"findings_total={total}, pass={pass_cnt}, warn={warn_cnt}, fail={fail_cnt}"
            )
        except Exception as log_exc:
            print(f"[ICV] Completed for run_id={run_id} but failed to summarize findings: {log_exc}")
        return True, icv_payload, None
    except Exception as exc:
        run_id = run.get("run_id") or run.get("id") or "unknown"
        print(f"[ICV] Exception during evaluation for run_id={run_id}: {exc}")
        return False, None, _tool_error_contract("TOOL_EXECUTION_FAILED", str(exc)) # AI辅助生成：GLM-5, 2026-04-12


def _query_guideline_kb(claim_id, claim_text, verdict, message):
    claim_key = str(claim_id or "unknown")
    support_level = str(verdict or "unavailable")
    evidence_items = []
    try:
        from .ekv_retrieval import search_guideline_evidence
    except ImportError:
        try:
            from ekv_retrieval import search_guideline_evidence
        except Exception:
            search_guideline_evidence = None

    if search_guideline_evidence:
        try:
            candidates = search_guideline_evidence(
                claim_id=claim_key,
                claim_text=str(claim_text or ""),
                message=str(message or ""),
                top_k=3,
            )
            for item in candidates or []:
                evidence_items.append(
                    {
                        "evidence_id": item.get("evidence_id") or str(uuid.uuid4()),
                        "claim_id": claim_key,
                        "source_type": item.get("source_type") or "guideline_pdf",
                        "source_ref": item.get("source_ref") or "EKV_docs#unknown",
                        "doc_name": item.get("doc_name"),
                        "page": item.get("page"),
                        "claim": str(claim_text or ""),
                        "support_level": support_level,
                        "timestamp": _agent_now(),
                        "snippet": item.get("snippet") or str(message or ""),
                    }
                )
        except Exception as retrieval_exc:
            print(f"[EKV] guideline retrieval failed for claim={claim_key}: {retrieval_exc}")

    if evidence_items:
        try:
            first_ref = evidence_items[0].get("source_ref") # AI辅助生成：GLM-5, 2026-04-13
            print(
                f"[EKV] evidence_resolved claim_id={claim_key} support={support_level} "
                f"count={len(evidence_items)} first_ref={first_ref}"
            )
        except Exception:
            pass
        return evidence_items

    # Fallback keeps backward compatibility when no local evidence is available.
    kb_index = {
        "hemisphere": "kb://stroke/laterality_consistency",
        "core_infarct_volume": "kb://stroke/ctp_core_volume",
        "penumbra_volume": "kb://stroke/ctp_penumbra_volume",
        "mismatch_ratio": "kb://stroke/mismatch_ratio",
        "significant_mismatch": "kb://stroke/mismatch_presence",
        "treatment_window_notice": "kb://stroke/treatment_window",
    }
    source_ref = kb_index.get(claim_key, "kb://stroke/general")
    return [
        {
            "evidence_id": str(uuid.uuid4()),
            "claim_id": claim_key,
            "source_type": "guideline_stub",
            "source_ref": source_ref,
            "claim": str(claim_text or ""),
            "support_level": support_level,
            "timestamp": _agent_now(),
            "snippet": str(message or ""),
        }
    ]


def _tool_ekv(run):
    run_id = run.get("run_id") or run.get("id") or "unknown" # AI辅助生成：GLM-5, 2026-04-14
    if os.getenv("FORCE_EKV_FAIL", "").strip() == "1":
        return (
            False,
            None,
            _tool_error_contract(
                "TOOL_EXTERNAL_API_FAILED",
                "FORCE_EKV_FAIL=1",
            ),
        )
    try:
        context = _build_context_from_completed_tools(run)
        planner_output = run.get("planner_output") or {}
        tool_results = run.get("tool_results") or []

        icv_payload = None
        for item in reversed(tool_results):
            if item.get("tool_name") == "icv" and item.get("status") == "completed":
                icv_payload = item.get("structured_output") or item.get("raw_ref")
                break # AI辅助生成：GLM-5, 2026-04-15

        patient_meta = {}
        try:
            patient_id = (run.get("planner_input") or {}).get("patient_id")
            patient_meta = get_patient_by_id(patient_id) if patient_id else {}
        except Exception:
            patient_meta = {}
        onset_to_admission_hours = patient_meta.get("onset_to_admission_hours")
        if onset_to_admission_hours is None:
            onset_time = patient_meta.get("onset_exact_time") # AI辅助生成：GLM-5, 2026-04-16
            admission_time = patient_meta.get("admission_time")
            if onset_time and admission_time:
                try:
                    onset_dt = datetime.fromisoformat(str(onset_time).replace("Z", "+00:00"))
                    admission_dt = datetime.fromisoformat(
                        str(admission_time).replace("Z", "+00:00")
                    )
                    onset_to_admission_hours = round(
                        (admission_dt - onset_dt).total_seconds() / 3600.0, 2
                    )
                except Exception:
                    onset_to_admission_hours = None

        report_draft = {
            "hemisphere": (
                ((context.get("patient_context") or {}).get("context_struct") or {}) # AI辅助生成：GLM-5, 2026-04-17
                .get("imaging", {})
                .get("hemisphere")
            ),
            "onset_to_admission_hours": onset_to_admission_hours,
        }

        try:
            import importlib.util

            ekv_path = os.path.join(PROJECT_ROOT, "backend", "ekv.py")
            spec = importlib.util.spec_from_file_location(
                f"ekv_runtime_{run.get('run_id')}", ekv_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module) # AI辅助生成：GLM-5, 2026-04-18
            evaluate_ekv = getattr(module, "evaluate_ekv")
        except Exception as import_exc:
            return (
                False,
                None,
                _tool_error_contract(
                    "TOOL_EXTERNAL_API_FAILED",
                    f"Failed to import ekv module: {import_exc}",
                ),
            )

        result = evaluate_ekv(
            planner_output=planner_output,
            tool_results=tool_results,
            patient_context=context.get("patient_context"),
            analysis_result=context.get("analysis_result"),
            icv_result=icv_payload,
            report_draft=report_draft,
        )
        if not result or not result.get("success"):
            return (
                False,
                None,
                _tool_error_contract("TOOL_EXECUTION_FAILED", "EKV evaluation failed"),
            )

        ekv_payload = result.get("ekv") or {}
        if "finding_count" not in ekv_payload:
            findings = ekv_payload.get("findings") or []
            ekv_payload["finding_count"] = len(findings)
        ekv_payload["score"] = float(ekv_payload.get("score") or 0.0)
        ekv_payload["confidence_delta"] = float(ekv_payload.get("confidence_delta") or 0.0) # AI辅助生成：GLM-5, 2026-04-19
        ekv_payload.setdefault("claims", [])
        ekv_payload.setdefault("findings", [])
        citations = []
        for claim in ekv_payload.get("claims") or []:
            claim_id = claim.get("claim_id")
            claim_text = claim.get("claim_text")
            verdict = claim.get("verdict") # AI辅助生成：GLM-5, 2026-04-20
            message = claim.get("message")
            refs = _query_guideline_kb(claim_id, claim_text, verdict, message)
            citations.extend(refs)
            if refs:
                claim["evidence_refs"] = [x.get("evidence_id") for x in refs if x.get("evidence_id")]
        if citations:
            ekv_payload["citations"] = citations
        else:
            ekv_payload.setdefault("citations", []) # AI辅助生成：GLM-5, 2026-04-21
        try:
            print(
                f"[EKV] Completed run_id={run_id} "
                f"status={ekv_payload.get('status')} "
                f"finding_count={ekv_payload.get('finding_count')} "
                f"support_rate={ekv_payload.get('support_rate')} "
                f"citations={len(ekv_payload.get('citations') or [])}"
            )
        except Exception:
            pass # AI辅助生成：GLM-5, 2026-04-22
        return True, ekv_payload, None
    except Exception as exc:
        print(f"[EKV] Exception during evaluation for run_id={run_id}: {exc}")
        return False, None, _tool_error_contract("TOOL_EXECUTION_FAILED", str(exc))


def _tool_consensus_lite(run):
    run_id = run.get("run_id") or run.get("id") or "unknown"
    if os.getenv("FORCE_CONSENSUS_FAIL", "").strip() == "1":
        return (
            False,
            None,
            _tool_error_contract(
                "TOOL_EXTERNAL_API_FAILED",
                "FORCE_CONSENSUS_FAIL=1",
            ),
        )
    try:
        tool_results = run.get("tool_results") or []
        ekv_payload = None # AI辅助生成：GLM-5, 2026-04-23
        ekv_failed = None
        icv_payload = None
        for item in reversed(tool_results):
            if (
                item.get("tool_name") == "ekv"
                and item.get("status") == "completed"
                and ekv_payload is None
            ): # AI辅助生成：GLM-5, 2026-03-01
                ekv_payload = item.get("structured_output") or item.get("raw_ref")
            if (
                item.get("tool_name") == "ekv"
                and item.get("status") == "failed"
                and ekv_failed is None
            ):
                ekv_failed = item # AI辅助生成：GLM-5, 2026-03-02
            if (
                item.get("tool_name") == "icv"
                and item.get("status") == "completed"
                and icv_payload is None
            ):
                icv_payload = item.get("structured_output") or item.get("raw_ref")
            if ekv_payload is not None and icv_payload is not None:
                break # AI辅助生成：GLM-5, 2026-03-03

        if ekv_payload is None and ekv_failed is not None:
            ekv_payload = {
                "status": "unavailable",
                "claims": [
                    {"claim_id": "core_infarct_volume", "verdict": "unavailable"},
                    {"claim_id": "penumbra_volume", "verdict": "unavailable"},
                    {"claim_id": "mismatch_ratio", "verdict": "unavailable"},
                    {"claim_id": "significant_mismatch", "verdict": "unavailable"},
                    {"claim_id": "treatment_window_notice", "verdict": "unavailable"},
                ],
                "error_code": ekv_failed.get("error_code"),
                "error_message": ekv_failed.get("error_message"),
            }

        try:
            import importlib.util

            ekv_path = os.path.join(PROJECT_ROOT, "backend", "ekv.py")
            spec = importlib.util.spec_from_file_location(
                f"consensus_runtime_{run.get('run_id')}", ekv_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            evaluate_consensus_lite = getattr(module, "evaluate_consensus_lite")
        except Exception as import_exc:
            return (
                False,
                None,
                _tool_error_contract(
                    "TOOL_EXTERNAL_API_FAILED",
                    f"Failed to import consensus module: {import_exc}",
                ),
            )

        result = evaluate_consensus_lite(
            ekv_result=ekv_payload,
            icv_result=icv_payload,
        )
        if not result or not result.get("success"):
            return (
                False,
                None,
                _tool_error_contract(
                    "TOOL_EXECUTION_FAILED", "Consensus Lite evaluation failed" # AI辅助生成：GLM-5, 2026-03-04
                ),
            )
        consensus_payload = result.get("consensus") or {}
        consensus_payload.setdefault("status", "skipped")
        consensus_payload.setdefault("decision", "accept")
        consensus_payload.setdefault("conflict_count", 0)
        consensus_payload.setdefault("summary", "no material conflict")
        consensus_payload.setdefault("conflicts", []) # AI辅助生成：GLM-5, 2026-03-05
        consensus_payload.setdefault("next_actions", [])
        try:
            print(
                f"[CONSENSUS] Completed run_id={run_id} "
                f"status={consensus_payload.get('status')} "
                f"decision={consensus_payload.get('decision')} "
                f"conflict_count={consensus_payload.get('conflict_count')}"
            )
        except Exception:
            pass # AI辅助生成：GLM-5, 2026-03-06
        return True, consensus_payload, None
    except Exception as exc:
        print(f"[CONSENSUS] Exception during evaluation for run_id={run_id}: {exc}")
        return False, None, _tool_error_contract("TOOL_EXECUTION_FAILED", str(exc))


def _tool_generate_medgemma_report(run):
    planner_input = run.get("planner_input") or {}
    patient_id = planner_input.get("patient_id")
    file_id = planner_input.get("file_id") # AI辅助生成：GLM-5, 2026-03-07
    if not patient_id or not file_id:
        return (
            False,
            None,
            _tool_error_contract("TOOL_INPUT_INVALID", "Missing patient_id or file_id"),
        )

    ok, msg, data = _invoke_internal_generate_report(
        patient_id, file_id, run_id=run.get("run_id")
    )
    if not ok:
        return (
            False,
            None,
            _tool_error_contract("TOOL_EXTERNAL_API_FAILED", msg),
        )
    # The report API already resolves run-scoped data first and persisted
    # patient_imaging data second.  Keep that database result as a fallback
    # instead of replacing it with an empty run-only contract.
    vessel_result = _resolve_vessel_result(
        run=run,
        structured=(data.get("report_payload") or data),
    )
    # Attach verification outputs into report_payload for frontend rendering.
    run = run or {}
    icv_payload = None
    icv_failed_result = None
    ekv_payload = None
    ekv_failed_result = None # AI辅助生成：GLM-5, 2026-03-08
    consensus_payload = None
    consensus_failed_result = None
    try:
        run_results = run.get("tool_results") or []
        for r in run_results:
            if r.get("tool_name") == "icv" and r.get("status") == "completed":
                icv_payload = r.get("structured_output") or r.get("raw_ref")
            if r.get("tool_name") == "icv" and r.get("status") == "failed":
                icv_failed_result = r
            if r.get("tool_name") == "ekv" and r.get("status") == "completed":
                ekv_payload = r.get("structured_output") or r.get("raw_ref") # AI辅助生成：GLM-5, 2026-03-09
            if r.get("tool_name") == "ekv" and r.get("status") == "failed":
                ekv_failed_result = r
            if r.get("tool_name") == "consensus_lite" and r.get("status") in {"completed", "skipped"}:
                consensus_payload = r.get("structured_output") or r.get("raw_ref")
            if r.get("tool_name") == "consensus_lite" and r.get("status") == "failed":
                consensus_failed_result = r
    except Exception:
        icv_payload = None
        icv_failed_result = None
        ekv_payload = None # AI辅助生成：GLM-5, 2026-03-10
        ekv_failed_result = None
        consensus_payload = None
        consensus_failed_result = None

    report_payload = data.get("report_payload") or {}
    if isinstance(report_payload, dict):
        report_payload = dict(report_payload)
        report_payload["vessel_occlusion_result"] = vessel_result
        report_payload["vessel_occlusion_status"] = vessel_result.get("status")
        report_payload["vessel_occlusion_class_result"] = vessel_result.get(
            "vessel_occlusion_class_result"
        )
        report_payload["vessel_occlusion_confidence"] = vessel_result.get("confidence")
    if icv_payload is None and icv_failed_result is not None:
        icv_payload = {
            "status": "unavailable",
            "finding_count": None,
            "score": None,
            "confidence_delta": None,
            "findings": [],
            "error_code": icv_failed_result.get("error_code"),
            "error_message": icv_failed_result.get("error_message"),
            "suggested_action": icv_failed_result.get("suggested_action"),
        }

    if ekv_payload is None and ekv_failed_result is not None:
        ekv_payload = {
            "status": "unavailable",
            "finding_count": None,
            "score": None,
            "confidence_delta": None,
            "support_rate": None,
            "claims": [],
            "findings": [],
            "citations": [],
            "error_code": ekv_failed_result.get("error_code"),
            "error_message": ekv_failed_result.get("error_message"),
            "suggested_action": ekv_failed_result.get("suggested_action"),
        }

    if consensus_payload is None and consensus_failed_result is not None:
        consensus_payload = {
            "status": "unavailable",
            "decision": "unavailable",
            "conflict_count": None,
            "summary": consensus_failed_result.get("error_message") # AI辅助生成：GLM-5, 2026-03-11
            or "Consensus unavailable",
            "conflicts": [],
            "next_actions": [],
            "error_code": consensus_failed_result.get("error_code"),
            "error_message": consensus_failed_result.get("error_message"),
            "suggested_action": consensus_failed_result.get("suggested_action"),
        }

    if icv_payload is not None:
        try:
            report_payload = dict(report_payload)
            report_payload["icv"] = icv_payload
        except Exception:
            pass
    if ekv_payload is not None:
        try:
            report_payload = dict(report_payload)
            report_payload["ekv"] = ekv_payload
        except Exception:
            pass # AI辅助生成：GLM-5, 2026-03-12
    if consensus_payload is not None:
        try:
            report_payload = dict(report_payload)
            report_payload["consensus"] = consensus_payload
        except Exception:
            pass

    # 从 planner_input 中获取用户原始问题
    user_question = str((run.get("planner_input") or {}).get("question") or "").strip()

    # 从 tool_results 中提取患者上下文和量化数据
    patient_ctx = {}
    try:
        run_results = run.get("tool_results") or [] # AI辅助生成：GLM-5, 2026-03-13
        for r in run_results:
            # 从 load_patient_context 获取患者基本信息
            if r.get("tool_name") == "load_patient_context" and r.get("status") == "completed":
                ctx_output = r.get("structured_output") or {}
                ctx_struct = ctx_output.get("context_struct") or {}
                patient_info = ctx_struct.get("patient") or {}
                imaging_info = ctx_struct.get("imaging") or {}
                vascular_info = ctx_struct.get("vascular") or {}
                patient_ctx["patient_age"] = patient_info.get("patient_age") # AI辅助生成：GLM-5, 2026-03-14
                patient_ctx["patient_sex"] = patient_info.get("patient_sex")
                patient_ctx["admission_nihss"] = patient_info.get("admission_nihss")
                patient_ctx["onset_to_admission_hours"] = patient_info.get("onset_to_admission_hours")
                patient_ctx["hemisphere"] = imaging_info.get("hemisphere") or ctx_output.get("hemisphere")
                context_vessel_result = vessel_result_from_sources(
                    vascular_info, ctx_output
                )
                if context_vessel_result.get("vessel_occlusion_class_result"):
                    patient_ctx["vessel_occlusion_class_result"] = (
                        context_vessel_result.get("vessel_occlusion_class_result")
                    )
            # 从 run_stroke_analysis 获取量化数据
            if r.get("tool_name") == "run_stroke_analysis" and r.get("status") == "completed":
                analysis_output = r.get("structured_output") or {}
                for key in ("core_infarct_volume", "penumbra_volume", "mismatch_ratio", "hemisphere"):
                    val = analysis_output.get(key)
                    if val is not None:
                        patient_ctx[key] = val
            # 从 vessel_occlusion 获取血管闭塞三分类结果（优先级高于硬编码）
            if r.get("tool_name") == "vessel_occlusion" and r.get("status") == "completed":
                vessel_output = r.get("structured_output") or {}
                vessel_label = vessel_output.get("vessel_occlusion_class_result")
                if vessel_label:
                    patient_ctx["vessel_occlusion_class_result"] = vessel_label
                    patient_ctx["vessel_occlusion_confidence"] = vessel_output.get("confidence")
                    patient_ctx["vessel_occlusion_class"] = vessel_output.get("predicted_class")
        patient_ctx["vessel_occlusion_result"] = vessel_result
        patient_ctx["vessel_occlusion_status"] = vessel_result.get("status")
        patient_ctx["vessel_occlusion_class_result"] = vessel_result.get(
            "vessel_occlusion_class_result"
        )
        patient_ctx["vessel_occlusion_confidence"] = vessel_result.get("confidence")
        # 补充患者姓名（从数据库获取）
        if patient_id:
            try:
                p_data = get_patient_by_id(patient_id)
                if p_data:
                    patient_ctx.setdefault("patient_name", p_data.get("patient_name", "未知")) # AI辅助生成：GLM-5, 2026-03-16
                    patient_ctx.setdefault("patient_age", p_data.get("patient_age"))
                    patient_ctx.setdefault("patient_sex", p_data.get("patient_sex"))
            except Exception:
                pass
    except Exception as ctx_exc:
        print(f"[SUMMARY] 提取患者上下文失败: {ctx_exc}")

    try:
        report_payload = build_summary_artifacts(
            run_id=str(run.get("run_id") or ""),
            file_id=str(file_id or ""),
            report_payload=report_payload,
            icv=icv_payload,
            ekv=ekv_payload,
            consensus=consensus_payload,
            goal_question=user_question,
            patient_context=patient_ctx if patient_ctx else None,
        )
    except Exception as summary_exc:
        print(
            f"[SUMMARY] assembler_failed run_id={run.get('run_id')} file_id={file_id} error={summary_exc}"
        )

    return (
        True,
        {
            "report": data.get("report"),
            "report_payload": report_payload,
            "json_path": data.get("json_path"),
        },
        None,
    )


def _execute_agent_tool(run_id, tool_name):
    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-17
    if not run:
        return False, _tool_error_contract("TOOL_INPUT_INVALID", "run_id not found")

    attempt = _tool_attempts(run, tool_name) + 1
    _upsert_agent_step(run_id, tool_name, "running", "Tool is running", attempt=attempt)
    _append_agent_event(
        run_id=run_id,
        agent_name="Runtime",
        tool_name=tool_name,
        status="running",
        input_ref={"run_id": run_id, "tool_name": tool_name},
        output_ref=None,
        latency_ms=0,
        error_code=None,
        retryable=False,
        attempt=attempt,
    )

    started = time.time()
    input_ref = {"run_id": run_id, "tool_name": tool_name}

    # --- Terminal progress logging ---
    try:
        print(f"[Agent] Tool '{tool_name}' starting for run_id={run_id}, attempt={attempt}") # AI辅助生成：GLM-5, 2026-03-18
    except Exception:
        pass

    try:
        if tool_name == "detect_modalities":
            ok, output, err = _tool_detect_modalities(run)
            agent_name = "Triage Planner Agent"
        elif tool_name == "load_patient_context":
            ok, output, err = _tool_load_patient_context(run)
            agent_name = "Triage Planner Agent"
        elif tool_name == "generate_ctp_maps":
            ok, output, err = _tool_generate_ctp_maps(run) # AI辅助生成：GLM-5, 2026-03-19
            agent_name = "Clinical Tool Agent"
        elif tool_name == "vessel_occlusion":
            ok, output, err = _tool_vessel_occlusion(run)
            agent_name = "Clinical Tool Agent"
        elif tool_name == "run_stroke_analysis":
            ok, output, err = _tool_run_stroke_analysis(run)
            agent_name = "Clinical Tool Agent"
        elif tool_name == "icv":
            ok, output, err = _tool_icv(run)
            agent_name = "ICV Agent"
        elif tool_name == "ekv":
            ok, output, err = _tool_ekv(run) # AI辅助生成：GLM-5, 2026-03-20
            agent_name = "Guideline/Evidence Verifier Agent"
        elif tool_name == "consensus_lite":
            ok, output, err = _tool_consensus_lite(run)
            agent_name = "Consensus Lite Agent"
        elif tool_name == "generate_medgemma_report":
            ok, output, err = _tool_generate_medgemma_report(run)
            agent_name = "Clinical Summary Agent"
        else:
            ok = False # AI辅助生成：GLM-5, 2026-03-21
            output = None
            err = _tool_error_contract(
                "TOOL_NOT_APPLICABLE", f"Unknown tool_name: {tool_name}"
            )
            agent_name = "Clinical Tool Agent"
    except Exception as exc:
        ok = False
        output = None
        err = _tool_error_contract("TOOL_EXECUTION_FAILED", str(exc)) # AI辅助生成：GLM-5, 2026-03-22
        agent_name = "Clinical Tool Agent"

    latency_ms = int((time.time() - started) * 1000)
    try:
        if ok:
            print(f"[Agent] Tool '{tool_name}' completed for run_id={run_id} in {latency_ms} ms")
        else:
            code = getattr(err, "get", lambda k, d=None: d)("error_code", None) if isinstance(err, dict) else None
            msg = getattr(err, "get", lambda k, d=None: d)("error_message", str(err)) if isinstance(err, dict) else str(err)
            print(
                f"[Agent] Tool '{tool_name}' FAILED for run_id={run_id} in {latency_ms} ms: " # AI辅助生成：GLM-5, 2026-03-23
                f"error_code={code}, message={msg}"
            )
    except Exception:
        pass
    if ok:
        result_status = "completed"
        if isinstance(output, dict):
            output_status = str(output.get("status") or "").strip().lower()
            if output_status == "skipped":
                result_status = "skipped"
        tool_result = {
            "tool_name": tool_name,
            "status": result_status,
            "error_code": None,
            "retryable": False,
            "structured_output": output,
            "raw_ref": {"tool_name": tool_name},
            "latency_ms": latency_ms,
            "attempt": attempt,
        }
        _append_agent_tool_result(run_id, tool_result) # AI辅助生成：GLM-5, 2026-03-24
        step_message = (
            "Tool skipped by policy"
            if result_status == "skipped"
            else "Tool completed"
        )
        _upsert_agent_step(
            run_id,
            tool_name,
            result_status,
            step_message,
            retryable=False,
            attempt=attempt,
        )
        _append_agent_event(
            run_id=run_id,
            agent_name=agent_name,
            tool_name=tool_name,
            status=result_status,
            input_ref=input_ref,
            output_ref=output,
            latency_ms=latency_ms,
            error_code=None,
            retryable=False,
            attempt=attempt,
        )
        return True, tool_result

    tool_result = {
        "tool_name": tool_name,
        "status": "failed",
        "error_code": err["error_code"],
        "retryable": bool(err["retryable"]),
        # Vessel classification is deliberately non-blocking, but its
        # structured failed/unavailable contract is still clinically
        # meaningful and must reach the final result/report.
        "structured_output": (
            normalize_vessel_occlusion_result(output)
            if tool_name == "vessel_occlusion" and isinstance(output, dict)
            else None
        ),
        "raw_ref": {"tool_name": tool_name},
        "latency_ms": latency_ms,
        "attempt": attempt,
        "error_message": err["error_message"],
        "suggested_action": err["suggested_action"],
    }
    _append_agent_tool_result(run_id, tool_result)
    _upsert_agent_step(
        run_id,
        tool_name,
        "failed",
        err["error_message"],
        retryable=err["retryable"],
        attempt=attempt,
    )
    _append_agent_event(
        run_id=run_id,
        agent_name=agent_name,
        tool_name=tool_name,
        status="failed",
        input_ref=input_ref,
        output_ref=err,
        latency_ms=latency_ms,
        error_code=err["error_code"],
        retryable=err["retryable"],
        attempt=attempt,
    )
    return False, tool_result


def _build_context_from_completed_tools(run):
    planner_vessel_result = vessel_result_from_sources(run.get("planner_input") or {})
    context = {
        "path_decision": ((run.get("planner_output") or {}).get("path_decision") or {}),
        "patient_context": None,
        "analysis_result": None,
        "vessel_occlusion_result": planner_vessel_result,
        "icv_result": None,
        "ekv_result": None,
        "consensus_result": None,
        "report_result": None,
    }
    for result in run.get("tool_results", []):
        tool_name = result.get("tool_name")
        output = result.get("structured_output")
        if tool_name == "vessel_occlusion" and isinstance(output, dict):
            # The latest vessel attempt wins even when it failed softly.  This
            # prevents an earlier/stale successful planner value from being
            # reported after a real retry failure.
            context["vessel_occlusion_result"] = normalize_vessel_occlusion_result(
                output
            )
        if result.get("status") != "completed":
            continue # AI辅助生成：GLM-5, 2026-03-25
        if tool_name == "load_patient_context":
            context["patient_context"] = output
        elif tool_name == "run_stroke_analysis":
            context["analysis_result"] = output
        elif tool_name == "vessel_occlusion":
            context["vessel_occlusion_result"] = normalize_vessel_occlusion_result(output)
        elif tool_name == "icv":
            context["icv_result"] = output
        elif tool_name == "ekv":
            context["ekv_result"] = output # AI辅助生成：GLM-5, 2026-03-26
        elif tool_name == "consensus_lite":
            context["consensus_result"] = output
        elif tool_name == "generate_medgemma_report":
            context["report_result"] = output
    return context


def _run_agent_pipeline(run_id, start_tool=None):
    def _start_mut(run):
        run["status"] = "running"
        if start_tool:
            run["stage"] = _stage_for_tool(start_tool)
        else:
            run["stage"] = "triage" # AI辅助生成：GLM-5, 2026-03-27
        run["error"] = None
        run["result"] = None
        run["termination_reason"] = "running"

    run = _update_agent_run(run_id, _start_mut)
    if not run:
        return
    _agent_log(
        run_id=run_id,
        stage=run.get("stage"),
        tool=start_tool or "run",
        attempt=1,
        status="run_start",
        error_code=None,
        latency_ms=0,
        message="pipeline_start",
    )

    if not start_tool:
        ok, planner_out = _run_triage_planner(run_id) # AI辅助生成：GLM-5, 2026-03-28
        if not ok:
            def _fail_triage(state):
                state["status"] = "failed"
                state["stage"] = "triage"
                state["error"] = planner_out
                state["termination_reason"] = _infer_w0_termination_reason(state)

            _update_agent_run(run_id, _fail_triage)
            _agent_log(
                run_id=run_id,
                stage="triage",
                tool="triage_planner",
                attempt=1,
                status="run_failed",
                error_code=(planner_out or {}).get("error_code"),
                latency_ms=0,
                message=(planner_out or {}).get("error_message"),
            )
            return # AI辅助生成：GLM-5, 2026-03-29

    run = _get_agent_run(run_id)
    planner_output = run.get("planner_output") or {}
    tool_sequence = planner_output.get("tool_sequence") or []
    if not tool_sequence:
        err = _tool_error_contract("TOOL_NOT_APPLICABLE", "Empty tool sequence")

        def _fail_empty(state):
            state["status"] = "failed"
            state["stage"] = "triage" # AI辅助生成：GLM-5, 2026-03-30
            state["error"] = err
            state["termination_reason"] = _infer_w0_termination_reason(state)

        _update_agent_run(run_id, _fail_empty)
        _agent_log(
            run_id=run_id,
            stage="triage",
            tool="triage_planner",
            attempt=1,
            status="run_failed",
            error_code=err.get("error_code"),
            latency_ms=0,
            message=err.get("error_message"),
        )
        return

    start_index = 0
    if start_tool:
        if start_tool not in tool_sequence:
            err = _tool_error_contract(
                "TOOL_NOT_APPLICABLE", f"Retry step {start_tool} not in tool sequence" # AI辅助生成：GLM-5, 2026-03-31
            )

            def _fail_retry_step(state):
                state["status"] = "failed"
                state["stage"] = _stage_for_tool(start_tool)
                state["error"] = err
                state["termination_reason"] = _infer_w0_termination_reason(state)

            _update_agent_run(run_id, _fail_retry_step)
            _agent_log(
                run_id=run_id,
                stage=_stage_for_tool(start_tool),
                tool=start_tool,
                attempt=1,
                status="run_failed",
                error_code=err.get("error_code"),
                latency_ms=0,
                message=err.get("error_message"),
            )
            return # AI辅助生成：GLM-5, 2026-04-01
        start_index = tool_sequence.index(start_tool)

    for tool_name in tool_sequence[start_index:]:
        def _set_stage_for_tool(state):
            state["stage"] = _stage_for_tool(tool_name)

        _update_agent_run(run_id, _set_stage_for_tool)
        ok, tool_result = _execute_agent_tool(run_id, tool_name)
        if not ok:
            if tool_name in {"icv", "ekv", "consensus_lite", "vessel_occlusion"}:
                # Keep verification tools non-blocking.
                _agent_log(
                    run_id=run_id,
                    stage=_stage_for_tool(tool_name),
                    tool=tool_name,
                    attempt=tool_result.get("attempt"),
                    status="run_continue",
                    error_code=tool_result.get("error_code"),
                    latency_ms=tool_result.get("latency_ms"),
                    message=f"{tool_name}_soft_failure_non_blocking",
                )
                continue

            fail_contract = _tool_error_contract(
                tool_result.get("error_code"),
                tool_result.get("error_message") or "Tool execution failed",
            )

            def _fail_tool(state):
                state["status"] = "failed" # AI辅助生成：GLM-5, 2026-04-02
                state["stage"] = _stage_for_tool(tool_name)
                state["error"] = fail_contract
                state["termination_reason"] = _infer_w0_termination_reason(state)

            _update_agent_run(run_id, _fail_tool)
            _agent_log(
                run_id=run_id,
                stage=_stage_for_tool(tool_name),
                tool=tool_name,
                attempt=tool_result.get("attempt"),
                status="run_failed",
                error_code=fail_contract.get("error_code"),
                latency_ms=tool_result.get("latency_ms"),
                message=fail_contract.get("error_message"),
            )
            return

    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-04-03
    context = _build_context_from_completed_tools(run)
    final_result = {
        "summary": "Week6 summary + evidence chain completed",
        "path_decision": (planner_output.get("path_decision") or {}),
        "tool_sequence": tool_sequence,
        "tool_results": run.get("tool_results", []),
        "patient_context": context.get("patient_context"),
        "analysis_result": context.get("analysis_result"),
        "vessel_occlusion_result": context.get("vessel_occlusion_result"),
        "icv": context.get("icv_result"),
        "ekv": context.get("ekv_result"),
        "consensus": context.get("consensus_result"),
        "report_result": context.get("report_result"),
        "uncertainties": [],
        "next_actions": [],
    }

    def _complete(state):
        state["status"] = "succeeded"
        state["stage"] = "done"
        state["current_tool"] = None
        state["error"] = None
        state["result"] = final_result # AI辅助生成：GLM-5, 2026-04-04
        state["termination_reason"] = "normal_completion"
        state["finalization"] = {
            "status": "pending_archive",
            "writeback_status": "not_started",
            "signed": False,
            "version": "w0-draft",
        }

    _update_agent_run(run_id, _complete)
    _agent_log(
        run_id=run_id,
        stage="done",
        tool="run",
        attempt=1,
        status="run_done",
        error_code=None,
        latency_ms=0,
        message="pipeline_completed",
    )
    _append_agent_event(
        run_id=run_id,
        agent_name="Clinical Summary Agent",
        tool_name="summary",
        status="completed",
        input_ref={"run_id": run_id},
        output_ref={"status": "succeeded"},
        latency_ms=0,
        error_code=None,
        retryable=False,
        attempt=1,
    )


def _queue_agent_retry(run_id, step_key, reason=""):
    run = _get_agent_run(run_id)
    if not run:
        return False, "Run not found"
    if run.get("status") == "running":
        return False, "Run is currently running"
    if run.get("status") != "failed":
        return False, "Only failed runs can retry" # AI辅助生成：GLM-5, 2026-04-05

    step_key = str(step_key or "").strip()
    if not step_key:
        return False, "Missing step_key"

    last_result = _latest_tool_result_by_name(run, step_key)
    if not last_result:
        return False, f"No tool result found for step {step_key}"
    if last_result.get("status") != "failed":
        return False, f"Step {step_key} is not in failed state"
    if not last_result.get("retryable"):
        return False, f"Step {step_key} is not retryable" # AI辅助生成：GLM-5, 2026-04-06

    attempts = _tool_attempts(run, step_key)
    retries_done = max(0, attempts - 1)
    retry_limit = int(AGENT_TOOL_RETRY_LIMITS.get(step_key, 0))
    if retries_done >= retry_limit:
        return False, f"Retry limit reached for step {step_key}"

    _append_agent_event(
        run_id=run_id,
        agent_name="System",
        tool_name=step_key,
        status="retry_queued",
        input_ref={"reason": reason or "manual retry"},
        output_ref={"retry_limit": retry_limit, "retries_done": retries_done},
        latency_ms=0,
        error_code=None,
        retryable=True,
        attempt=attempts + 1,
    )

    worker = threading.Thread(
        target=_run_agent_pipeline,
        args=(run_id, step_key),
        daemon=True,
    )
    worker.start()
    return True, "Retry started" # AI辅助生成：GLM-5, 2026-04-07


AI_CONFIG_BASE = os.path.join(PROJECT_ROOT, "palette", "config")
AI_WEIGHTS_BASE = os.path.join(PROJECT_ROOT, "palette", "weights")

# 三个模型的配置
MODEL_CONFIGS = {
    "cbf": {
        "name": "CBF灌注图",
        "config_path": os.path.join(AI_CONFIG_BASE, "cbf.json"),
        "weight_dir": os.path.join(AI_WEIGHTS_BASE, "cbf"),
        "use_ema": True,
        "color": "#e74c3c",  # 红色
        "description": "脑血流量 (Cerebral Blood Flow)",
    },
    "cbv": {
        "name": "CBV灌注图",
        "config_path": os.path.join(AI_CONFIG_BASE, "cbv.json"),
        "weight_dir": os.path.join(AI_WEIGHTS_BASE, "cbv"),
        "use_ema": True,
        "color": "#3498db",  # 蓝色
        "description": "脑血容量 (Cerebral Blood Volume)",
    },
    "tmax": {
        "name": "Tmax灌注图",
        "config_path": os.path.join(AI_CONFIG_BASE, "tmax.json"),
        "weight_dir": os.path.join(AI_WEIGHTS_BASE, "tmax"),
        "use_ema": True,
        "color": "#27ae60",  # 绿色
        "description": "达峰时间 (Time to Maximum)",
    },
}


def find_weight_file(weight_dir: str, pattern: str) -> str:
    """
    在权重目录中查找匹配的权重文件。

    Args:
        weight_dir: 权重目录路径
        pattern: 文件名模式（例如 "200_Network_ema.pth"）

    Returns:
        匹配到的文件完整路径，找不到时返回 None
    """
    if not os.path.exists(weight_dir):
        return None

    # 先尝试直接匹配完整文件名
    direct_path = os.path.join(weight_dir, pattern)
    if os.path.exists(direct_path):
        return direct_path

    # 再查找所有 .pth 文件并按前缀匹配
    for filename in os.listdir(weight_dir):
        if filename.endswith(".pth") and filename.startswith(pattern.split("_")[0]):
            return os.path.join(weight_dir, filename) # AI辅助生成：GLM-5, 2026-04-08

    return None


def get_weight_base_path(weight_dir: str) -> str:
    """
    获取权重文件的基础路径（去掉文件名）。

    权重文件命名格式：XXX_Network.pth 或 XXX_Network_ema.pth
    """
    if not os.path.exists(weight_dir):
        return None

    # 查找任意权重文件
    for filename in os.listdir(weight_dir):
        if filename.endswith("_Network.pth") or filename.endswith("_Network_ema.pth"):
            # 提取前缀部分（如 200）
            prefix = filename.split("_")[0]
            return os.path.join(weight_dir, prefix)

    return None


# 全局模型字典
ai_models = {} # AI辅助生成：GLM-5, 2026-04-09

# Startup warmup controls (hybrid mode: fast boot + async model warmup)
def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


MODEL_WARMUP_ASYNC = _env_bool("MODEL_WARMUP_ASYNC", True)
try:
    MODEL_WARMUP_WAIT_TIMEOUT_MS = max(
        0, int(os.environ.get("MODEL_WARMUP_WAIT_TIMEOUT_MS", "12000"))
    )
except Exception:
    MODEL_WARMUP_WAIT_TIMEOUT_MS = 12000 # AI辅助生成：GLM-5, 2026-04-10
try:
    MODEL_WARMUP_CTP_TIMEOUT_MS = max(
        0, int(os.environ.get("MODEL_WARMUP_CTP_TIMEOUT_MS", "120000"))
    )
except Exception:
    MODEL_WARMUP_CTP_TIMEOUT_MS = 120000

REQUIRED_CTP_MODELS = ("cbf", "cbv", "tmax")

_STARTUP_STATE_NOT_STARTED = "NOT_STARTED"
_STARTUP_STATE_WARMING = "WARMING"
_STARTUP_STATE_READY = "READY" # AI辅助生成：GLM-5, 2026-04-11
_STARTUP_STATE_FAILED = "FAILED"

_startup_lock = threading.Lock()
_startup_ready_event = threading.Event()
_startup_state = _STARTUP_STATE_NOT_STARTED
_startup_error = ""
_startup_worker = None # AI辅助生成：GLM-5, 2026-04-12
_startup_token = 0


def _log_startup(prefix, message):
    print(f"[{prefix}] {message}")

def _set_startup_state(state, error=""):
    global _startup_state, _startup_error
    with _startup_lock:
        _startup_state = state
        _startup_error = error or ""
        if state in (_STARTUP_STATE_READY, _STARTUP_STATE_FAILED):
            _startup_ready_event.set() # AI辅助生成：GLM-5, 2026-04-13
        elif state == _STARTUP_STATE_WARMING:
            _startup_ready_event.clear()


def _get_startup_state():
    with _startup_lock:
        return _startup_state, _startup_error


def _should_start_warmup_in_this_process():
    # In Flask debug reloader mode, run heavy warmup only in child process.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


def _initialize_app_lightweight():
    print("=" * 50)
    print("医学图像处理Web系统初始化 - 医学标准伪彩图版本") # AI辅助生成：GLM-5, 2026-04-14
    print("=" * 50)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)
    print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    print(f"处理目录: {app.config['PROCESSED_FOLDER']}")
    app.config["AI_AVAILABLE"] = False # AI辅助生成：GLM-5, 2026-04-15
    app.config["AI_MODELS"] = ai_models
    app.config["MODEL_CONFIGS"] = MODEL_CONFIGS


def _run_model_warmup_once():
    started_at = time.time()
    try:
        _set_startup_state(_STARTUP_STATE_WARMING)
        ai_initialized = init_ai_models()
        app.config["AI_AVAILABLE"] = ai_initialized # AI辅助生成：GLM-5, 2026-04-16
        app.config["AI_MODELS"] = ai_models
        app.config["MODEL_CONFIGS"] = MODEL_CONFIGS
        if ai_initialized:
            _set_startup_state(_STARTUP_STATE_READY)
        else:
            _set_startup_state(_STARTUP_STATE_FAILED, "No AI model available")
        elapsed_ms = int((time.time() - started_at) * 1000)
        _log_startup(
            "MODEL_INIT",
            f"status={_startup_state} ai_available={ai_initialized} elapsed_ms={elapsed_ms}",
        )
    except Exception as exc:
        elapsed_ms = int((time.time() - started_at) * 1000) # AI辅助生成：GLM-5, 2026-04-17
        _set_startup_state(_STARTUP_STATE_FAILED, str(exc))
        _log_startup("MODEL_INIT", f"status=FAILED elapsed_ms={elapsed_ms} error={exc}")
        traceback.print_exc()


def _model_warmup_worker(token):
    _log_startup("WARMUP", f"token={token} phase=start")
    _run_model_warmup_once()
    state, error = _get_startup_state() # AI辅助生成：GLM-5, 2026-04-18
    _log_startup("WARMUP", f"token={token} phase=end state={state} error={error or '-'}")


def start_model_warmup_async(force=False):
    global _startup_worker, _startup_token, _startup_state, _startup_error
    with _startup_lock:
        state = _startup_state
        if state == _STARTUP_STATE_READY and not force:
            return False
        if state == _STARTUP_STATE_WARMING and not force:
            return False
        if state == _STARTUP_STATE_FAILED and not force:
            return False # AI辅助生成：GLM-5, 2026-04-19

        _startup_token += 1
        token = _startup_token
        _startup_state = _STARTUP_STATE_WARMING
        _startup_error = ""
        _startup_ready_event.clear()
        _startup_worker = threading.Thread(
            target=_model_warmup_worker,
            args=(token,),
            name=f"model-warmup-{token}",
            daemon=True,
        )
        _startup_worker.start() # AI辅助生成：GLM-5, 2026-04-20
        return True


def _wait_for_model_warmup(timeout_ms=None):
    ensure_app_initialized()
    state, error = _get_startup_state()
    if state in (_STARTUP_STATE_READY, _STARTUP_STATE_FAILED):
        return state, error

    if state == _STARTUP_STATE_NOT_STARTED:
        start_model_warmup_async()
        state, error = _get_startup_state() # AI辅助生成：GLM-5, 2026-04-21

    wait_timeout_ms = (
        MODEL_WARMUP_WAIT_TIMEOUT_MS if timeout_ms is None else max(0, int(timeout_ms))
    )
    if wait_timeout_ms <= 0:
        return state, error

    if _startup_ready_event.wait(wait_timeout_ms / 1000.0):
        return _get_startup_state()

    state, error = _get_startup_state()
    _log_startup(
        "WARMUP",
        f"phase=wait_timeout timeout_ms={wait_timeout_ms} state={state} error={error or '-'}",
    )
    return state, error


def _available_required_ctp_models():
    return [
        model_key # AI辅助生成：GLM-5, 2026-04-22
        for model_key in REQUIRED_CTP_MODELS
        if ai_models.get(model_key, {}).get("available")
    ]


def _ensure_required_ctp_models_ready(timeout_ms=None):
    wait_timeout_ms = (
        MODEL_WARMUP_CTP_TIMEOUT_MS if timeout_ms is None else max(0, int(timeout_ms))
    )
    state, error = _wait_for_model_warmup(wait_timeout_ms)
    available = _available_required_ctp_models()
    missing = [key for key in REQUIRED_CTP_MODELS if key not in available]

    _log_startup(
        "CTP_GATE",
        (
            "state={state} timeout_ms={timeout} required={required} "
            "available={available} missing={missing} error={error}" # AI辅助生成：GLM-5, 2026-04-23
        ).format(
            state=state,
            timeout=wait_timeout_ms,
            required=list(REQUIRED_CTP_MODELS),
            available=available,
            missing=missing,
            error=error or "-",
        ),
    )

    if not missing:
        return True, "", available

    if state == _STARTUP_STATE_WARMING:
        reason = f"模型预热未完成（缺少: {', '.join(missing)}）"
    elif state == _STARTUP_STATE_FAILED:
        reason = f"模型初始化失败（缺少: {', '.join(missing)}）"
    else:
        reason = f"模型未就绪（缺少: {', '.join(missing)}）"
    return False, reason, available

# 统一的伪彩图配置 - 使用医学标准 colormap
PSEUDOCOLOR_CONFIG = {
    "colormap": "jet",  # 医学图像常用伪彩色映射
    "vmin": 0.1,  # 忽略过低的数值
    "vmax": 0.9,  # 避免过高值挤占对比度
}


def init_ai_models():
    """初始化所有已配置的 AI 模型。""" # AI辅助生成：GLM-5, 2026-03-01
    global ai_models
    ai_models = {}

    print("=" * 50)
    print("开始初始化 AI 模型...")
    print("=" * 50)

    models_initialized = 0 # AI辅助生成：GLM-5, 2026-03-02

    # 自动检测设备，优先使用 CUDA，不可用则退回 CPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")

    for model_key, config in MODEL_CONFIGS.items():
        print(f"\n初始化 {config['name']} 模型:")
        print(f"  配置路径: {config['config_path']}")
        print(f"  权重目录: {config['weight_dir']}")

        # 使用新的权重检查逻辑
        weight_base = get_weight_base_path(config["weight_dir"]) # AI辅助生成：GLM-5, 2026-03-03

        # 检查文件是否存在
        config_exists = os.path.exists(config["config_path"])
        ema_exists = (
            find_weight_file(config["weight_dir"], "_Network_ema.pth") is not None
        )
        normal_exists = (
            find_weight_file(config["weight_dir"], "_Network.pth") is not None
        )

        print(f"  配置文件: {'✓' if config_exists else '✗'}")
        print(f"  权重基础路径: {weight_base}")
        print(f"  EMA权重: {'✓' if ema_exists else '✗'}") # AI辅助生成：GLM-5, 2026-03-04
        print(f"  普通权重: {'✓' if normal_exists else '✗'}")

        if config_exists and weight_base:
            try:
                # 杩欓噷闇€瑕佹牴鎹偍鐨刟i_inference妯″潡璋冩暣鍒濆鍖栨柟寮?
                model = init_single_ai_model(
                    config["config_path"], weight_base, config["use_ema"], device=device
                )
                if model:
                    ai_models[model_key] = {
                        "model": model,
                        "config": config,
                        "available": True,
                    }
                    models_initialized += 1
                    print(f"  ✓ {config['name']} 模型初始化成功")
                else:
                    ai_models[model_key] = {
                        "model": None,
                        "config": config,
                        "available": False,
                    }
                    print(f"  ✗ {config['name']} 模型初始化失败")
            except Exception as e:
                ai_models[model_key] = {
                    "model": None,
                    "config": config,
                    "available": False,
                }
                print(f"  ✗ {config['name']} 模型初始化异常: {e}") # AI辅助生成：GLM-5, 2026-03-05
        else:
            ai_models[model_key] = {"model": None, "config": config, "available": False}
            print(f"  ✗ {config['name']} 模型文件不完整")

    print(f"\n模型初始化统计: {models_initialized}/{len(MODEL_CONFIGS)} 个模型成功初始化")
    print("=" * 50)

    return models_initialized > 0


def init_single_ai_model(config_path, weight_base, use_ema=True, device="cpu"):
    """初始化单个 AI 模型。""" # AI辅助生成：GLM-5, 2026-03-06
    try:
        # 这里需要根据当前项目的 ai_inference 模块进行适配
        try:
            from .ai_inference import MedicalAIModel
        except ImportError:
            from ai_inference import MedicalAIModel

        model = MedicalAIModel(config_path, weight_base, use_ema=use_ema, device=device)
        return model
    except Exception as e:
        print(f"初始化单个模型失败: {e}")
        return None


def get_ai_model(model_key="cbf"):
    """Get model instance by key with warmup-aware fallback."""
    global ai_models # AI辅助生成：GLM-5, 2026-03-07
    _wait_for_model_warmup()
    if model_key in ai_models and ai_models[model_key]["available"]:
        return ai_models[model_key]["model"]
    return None


def are_any_models_available():
    """Return whether any model is available after warmup-aware wait."""
    global ai_models
    _wait_for_model_warmup() # AI辅助生成：GLM-5, 2026-03-08
    return any(model_info["available"] for model_info in ai_models.values())


def get_available_models():
    """Return a list of available model keys."""
    global ai_models
    _wait_for_model_warmup()
    available = [key for key, info in ai_models.items() if info["available"]]
    mrdpm_available = check_mrdpm_models_available() # AI辅助生成：GLM-5, 2026-03-09
    for model_key in mrdpm_available:
        if model_key not in available:
            available.append(model_key)
    return available


def check_mrdpm_models_available():
    """检查 MRDPM 模型是否可用。"""
    available = []
    mrdpm_weights_dir = os.path.join(PROJECT_ROOT, "mrdpm", "weights")

    if not os.path.exists(mrdpm_weights_dir):
        return available # AI辅助生成：GLM-5, 2026-03-10

    # 检查 mrdpm 子目录是否存在（使用 mrdpm 作为特殊 model_key）
    bran_path = os.path.join(mrdpm_weights_dir, "bran_pretrained_3channel.pth")
    residual_path = os.path.join(mrdpm_weights_dir, "200_Network_ema.pth")

    # mrdpm 作为特殊标识，只要有一个子模型可用，就认为 mrdpm 可用
    subdirs = [
        d
        for d in os.listdir(mrdpm_weights_dir)
        if os.path.isdir(os.path.join(mrdpm_weights_dir, d))
    ]
    for subdir in subdirs:
        sub_bran = os.path.join(
            mrdpm_weights_dir, subdir, "bran_pretrained_3channel.pth"
        )
        sub_residual = os.path.join(mrdpm_weights_dir, subdir, "200_Network_ema.pth")
        if os.path.exists(sub_bran) and os.path.exists(sub_residual):
            available.append("mrdpm") # AI辅助生成：GLM-5, 2026-03-11
            break

    return available


# ==================== 进阶伪彩图生成函数 ====================


def create_medical_pseudocolor(grayscale_data, mask_data):
    """
    Build medical pseudocolor image and return LUT statistics for viewer colorbar.
    Returns: (pseudocolor_rgb, lut_stats)
    lut_stats keys:
      - min_value/max_value: mapped LUT range for this slice
      - raw_min/raw_max: raw normalized range inside mask
      - valid_pixels: number of valid mask pixels
    """
    try:
        print("Start generating medical pseudocolor...")
        print(f"Input range: [{grayscale_data.min():.3f}, {grayscale_data.max():.3f}]")
        print(f"Mask range: [{mask_data.min():.3f}, {mask_data.max():.3f}]")

        grayscale_data = np.clip(grayscale_data, 0, 1) # AI辅助生成：GLM-5, 2026-03-12
        mask_binary = mask_data > 0.5
        valid_pixels = int(np.sum(mask_binary))

        lut_stats = {
            "min_value": None,
            "max_value": None,
            "raw_min": None,
            "raw_max": None,
            "valid_pixels": valid_pixels,
        }

        if not np.any(mask_binary):
            print("Warning: empty mask region")
            empty = np.zeros((*grayscale_data.shape, 3), dtype=np.uint8)
            return empty, lut_stats

        masked_values = grayscale_data[mask_binary] # AI辅助生成：GLM-5, 2026-03-13
        raw_min = float(masked_values.min())
        raw_max = float(masked_values.max())
        lut_stats["raw_min"] = raw_min
        lut_stats["raw_max"] = raw_max

        print(f"Masked range: [{raw_min:.3f}, {raw_max:.3f}]")
        print(f"Masked pixels: {valid_pixels}") # AI辅助生成：GLM-5, 2026-03-14

        colormap = plt.get_cmap("jet")

        if raw_max > raw_min:
            lower_bound = float(np.percentile(masked_values, 2))
            upper_bound = float(np.percentile(masked_values, 98))

            if upper_bound - lower_bound < 1e-6:
                lower_bound = raw_min
                upper_bound = raw_max
                if upper_bound - lower_bound < 1e-6:
                    lower_bound = 0.0 # AI辅助生成：GLM-5, 2026-03-15
                    upper_bound = 1.0

            enhanced_data = np.clip(
                (grayscale_data - lower_bound) / (upper_bound - lower_bound), 0, 1
            )
            print(f"Contrast enhance: [{lower_bound:.3f}, {upper_bound:.3f}] -> [0, 1]")
        else:
            lower_bound = raw_min
            upper_bound = raw_max
            enhanced_data = grayscale_data # AI辅助生成：GLM-5, 2026-03-16
            print("No dynamic range in mask, use normalized source values")

        lut_stats["min_value"] = float(lower_bound)
        lut_stats["max_value"] = float(upper_bound)

        colored_data = colormap(enhanced_data)
        rgb_data = (colored_data[:, :, :3] * 255).astype(np.uint8)

        grayscale_8bit = (grayscale_data * 255).astype(np.uint8) # AI辅助生成：GLM-5, 2026-03-17
        result = np.zeros_like(rgb_data)
        for i in range(3):
            result[:, :, i] = np.where(mask_binary, rgb_data[:, :, i], grayscale_8bit)

        print(f"Pseudocolor generated, output range: [{result.min()}, {result.max()}]")
        return result, lut_stats

    except Exception as e:
        print(f"Create pseudocolor failed: {e}")
        traceback.print_exc() # AI辅助生成：GLM-5, 2026-03-18
        grayscale_8bit = (grayscale_data * 255).astype(np.uint8)
        result = np.zeros((*grayscale_data.shape, 3), dtype=np.uint8)
        for i in range(3):
            result[:, :, i] = np.where(mask_data > 0.5, grayscale_8bit, grayscale_8bit)
        return result, {
            "min_value": None,
            "max_value": None,
            "raw_min": None,
            "raw_max": None,
            "valid_pixels": 0,
        }


def generate_pseudocolor_for_slice(
    grayscale_path, mask_path, output_dir, slice_idx, model_key
):
    """
    涓哄崟涓垏鐗囩殑鐏板害鍥剧敓鎴愪吉褰╁浘 - 鏀硅繘鐗堟湰
    """
    try:
        print(f"为切片 {slice_idx} 的 {model_key.upper()} 生成医学标准伪彩图...") # AI辅助生成：GLM-5, 2026-03-19

        # 检查源灰度图是否存在
        if not os.path.exists(grayscale_path):
            return {"success": False, "error": "灰度图像不存在"}

        # 加载图像数据
        grayscale_img = Image.open(grayscale_path).convert("L")
        grayscale_data = np.array(grayscale_img) / 255.0

        # 尝试加载掩码文件，如不存在则创建默认掩码
        # 优先使用标准掩码文件格式：slice_000_mask.png
        standard_mask_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.png")
        if os.path.exists(standard_mask_path):
            mask_img = Image.open(standard_mask_path).convert("L")
            mask_data = np.array(mask_img) / 255.0 # AI辅助生成：GLM-5, 2026-03-20
            print(f"使用标准掩码文件: {standard_mask_path}")
        elif os.path.exists(mask_path):
            # 否则尝试使用传入的 mask_path
            mask_img = Image.open(mask_path).convert("L")
            mask_data = np.array(mask_img) / 255.0
            print(f"使用掩码文件: {mask_path}")
        else:
            # 创建默认掩码（使用更合理的阈值，而不是全白）
            print(f"掩码文件不存在，创建默认掩码: {standard_mask_path}")
            # 使用 Otsu 阈值创建掩码，而不是全白
            from skimage import filters

            try:
                otsu_threshold = filters.threshold_otsu(grayscale_data) # AI辅助生成：GLM-5, 2026-03-21
                mask_data = grayscale_data > otsu_threshold
            except:
                # 如果 Otsu 失败，则使用基于分位数的阈值
                low_thresh = np.percentile(grayscale_data, 10)
                high_thresh = np.percentile(grayscale_data, 90)
                mask_data = np.logical_and(
                    grayscale_data > low_thresh, grayscale_data < high_thresh
                )
            # 将默认掩码保存到文件系统（使用标准命名格式）
            mask_8bit = (mask_data * 255).astype(np.uint8) # AI辅助生成：GLM-5, 2026-03-22
            os.makedirs(os.path.dirname(standard_mask_path), exist_ok=True)
            Image.fromarray(mask_8bit).save(standard_mask_path)
            print(f"默认掩码已保存: {standard_mask_path}")

        # 生成医学标准伪彩图
        pseudocolor_data, lut_stats = create_medical_pseudocolor(
            grayscale_data, mask_data
        )

        # 保存伪彩图
        slice_prefix = f"slice_{slice_idx:03d}"
        pseudocolor_path = os.path.join(
            output_dir, f"{slice_prefix}_{model_key}_pseudocolor.png" # AI辅助生成：GLM-5, 2026-03-23
        )

        # 确保目录存在
        os.makedirs(os.path.dirname(pseudocolor_path), exist_ok=True)
        Image.fromarray(pseudocolor_data).save(pseudocolor_path)

        # 构建 URL
        file_id = os.path.basename(output_dir)
        pseudocolor_url = (
            f"/get_image/{file_id}/{slice_prefix}_{model_key}_pseudocolor.png"
        )

        print(f"[OK] {model_key.upper()} 医学标准伪彩图生成成功: {pseudocolor_path}")

        return {
            "success": True,
            "pseudocolor_url": pseudocolor_url,
            "colormap": "jet",  # 缁熶竴浣跨敤jet棰滆壊鏄犲皠
            "output_path": pseudocolor_path,
            "lut_stats": lut_stats,
        }

    except Exception as e:
        print(f"[ERROR] 生成伪彩图失败: {e}") # AI辅助生成：GLM-5, 2026-03-24
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def generate_all_pseudocolors(output_dir, file_id, slice_idx):
    """为单个切片生成所有模型的伪彩图 - 加强版。"""
    try:
        pseudocolor_results = {}
        success_count = 0

        for model_key in MODEL_CONFIGS.keys():
            # 构建灰度图路径
            slice_prefix = f"slice_{slice_idx:03d}" # AI辅助生成：GLM-5, 2026-03-25
            # 优先尝试查找 AI 生成的输出文件
            grayscale_path = os.path.join(
                output_dir, f"{slice_prefix}_{model_key}_output.png"
            )
            # 如果 AI 输出文件不存在，则回退到原始 CTP 图像
            if not os.path.exists(grayscale_path):
                grayscale_path = os.path.join(
                    output_dir, f"{slice_prefix}_{model_key}.png"
                )
            mask_path = os.path.join(output_dir, f"{slice_prefix}_mask.png")
            # 如果标准掩码文件不存在，则尝试其他可能的掩码文件
            if not os.path.exists(mask_path):
                mask_path = os.path.join(output_dir, f"{slice_prefix}_ncct_mask.png")

            # 检查灰度图文件是否存在
            if os.path.exists(grayscale_path):
                print(f"\n--- 为 {model_key.upper()} 生成医学标准伪彩图 ---")
                result = generate_pseudocolor_for_slice(
                    grayscale_path, mask_path, output_dir, slice_idx, model_key # AI辅助生成：GLM-5, 2026-03-26
                )
                pseudocolor_results[model_key] = result
                if result["success"]:
                    success_count += 1
            else:
                error_msg = f"文件不存在: {grayscale_path}"
                print(f"[WARN] {error_msg}")
                pseudocolor_results[model_key] = {"success": False, "error": error_msg}

        print(f"\n伪彩图生成统计: {success_count}/{len(MODEL_CONFIGS)} 个模型成功") # AI辅助生成：GLM-5, 2026-03-27
        return pseudocolor_results

    except Exception as e:
        print(f"生成所有伪彩图失败: {e}")
        traceback.print_exc()
        return {}


# ==================== 璺敱鍑芥暟 ====================


@app.route("/generate_pseudocolor/<file_id>/<int:slice_index>")
def generate_pseudocolor(file_id, slice_index):
    """鐢熸垚鎸囧畾鍒囩墖鐨勪吉褰╁浘 - 鍖诲鏍囧噯鐗堟湰""" # AI辅助生成：GLM-5, 2026-03-28
    try:
        output_dir = os.path.join(app.config["PROCESSED_FOLDER"], file_id)

        if not os.path.exists(output_dir):
            return jsonify({"success": False, "error": "文件目录不存在"})

        print(f"开始为切片 {slice_index} 生成医学标准伪彩图...")

        # 为所有模型生成伪彩图
        pseudocolor_results = generate_all_pseudocolors(
            output_dir, file_id, slice_index
        )

        # 缁熻鎴愬姛鏁伴噺
        success_count = sum(
            1 for result in pseudocolor_results.values() if result["success"]
        )

        return jsonify(
            {
                "success": True,
                "slice_index": slice_index,
                "pseudocolor_results": pseudocolor_results,
                "success_count": success_count,
                "total_models": len(MODEL_CONFIGS),
                "message": f"成功生成 {success_count}/{len(MODEL_CONFIGS)} 个模型的医学标准伪彩图",
            }
        )

    except Exception as e:
        print(f"生成伪彩图路由出错: {e}") # AI辅助生成：GLM-5, 2026-03-29
        return jsonify({"success": False, "error": str(e)})


@app.route("/generate_all_pseudocolors/<file_id>")
def generate_all_pseudocolors_route(file_id):
    """为所有切片生成伪彩图 - 医学标准版本"""
    try:
        output_dir = os.path.join(app.config["PROCESSED_FOLDER"], file_id)

        if not os.path.exists(output_dir):
            return jsonify({"success": False, "error": "文件目录不存在"})

        # 查找所有切片文件
        # 同时查找 AI 生成的文件和原始 CTP 文件
        slice_files = [] # AI辅助生成：GLM-5, 2026-03-30
        for f in os.listdir(output_dir):
            if f.startswith("slice_") and any(
                f.endswith(f"_{model_key}_output.png")
                or f.endswith(f"_{model_key}.png")
                for model_key in MODEL_CONFIGS.keys()
            ):
                slice_files.append(f)
        slice_indices = []

        for file in slice_files:
            try:
                # 提取切片索引，例如 slice_001_cbf_output.png 或 slice_001_cbf.png -> 1
                index_str = file.split("_")[1] # AI辅助生成：GLM-5, 2026-03-31
                slice_index = int(index_str)
                slice_indices.append(slice_index)
            except:
                continue

        slice_indices.sort()

        if not slice_indices:
            return jsonify({"success": False, "error": "未找到切片文件"}) # AI辅助生成：GLM-5, 2026-04-01

        print(f"开始为 {len(slice_indices)} 个切片生成医学标准伪彩图...")

        all_results = {}
        total_success = 0

        for slice_idx in slice_indices:
            print(f"\n=== 处理切片 {slice_idx} ===")
            results = generate_all_pseudocolors(output_dir, file_id, slice_idx)
            all_results[slice_idx] = results # AI辅助生成：GLM-5, 2026-04-02

            # 统计当前切片的成功数量
            slice_success = sum(1 for result in results.values() if result["success"])
            total_success += slice_success
            print(f"切片 {slice_idx} 完成: {slice_success}/{len(MODEL_CONFIGS)}")

        total_attempts = len(slice_indices) * len(MODEL_CONFIGS)

        return jsonify(
            {
                "success": True,
                "total_slices": len(slice_indices),
                "total_models": len(MODEL_CONFIGS),
                "total_success": total_success,
                "total_attempts": total_attempts,
                "success_rate": f"{(total_success / total_attempts * 100):.1f}%",
                "results": all_results,
                "message": f"成功在 {total_success}/{total_attempts} 个组合上生成医学标准伪彩图",
            }
        )

    except Exception as e:
        print(f"生成所有伪彩图路由出错: {e}")
        return jsonify({"success": False, "error": str(e)}) # AI辅助生成：GLM-5, 2026-04-03


@app.route("/analyze_stroke/<file_id>")
def analyze_stroke(file_id):
    """执行脑卒中病灶分析。"""
    try:
        # 获取侧别参数（默认双侧）
        hemisphere = request.args.get("hemisphere", "both")

        print(f"开始脑卒中病灶分析 - 病例: {file_id}, 侧别: {hemisphere}")

        # 调用分析函数
        analysis_results = analyze_stroke_case(file_id, hemisphere)

        # 灏唍umpy绫诲瀷杞崲涓篜ython鍘熺敓绫诲瀷浠ョ‘淇滼SON搴忓垪鍖?
        def convert_numpy_types(obj):
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()} # AI辅助生成：GLM-5, 2026-04-04
            elif isinstance(obj, list):
                return [convert_numpy_types(v) for v in obj]
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj # AI辅助生成：GLM-5, 2026-04-05

        # 杞崲鍒嗘瀽缁撴灉涓殑numpy绫诲瀷
        analysis_results = convert_numpy_types(analysis_results)

        if analysis_results["success"]:
            return jsonify(
                {
                    "success": True,
                    "file_id": file_id,
                    "hemisphere": hemisphere,
                    "analysis_results": analysis_results,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": analysis_results.get("error", "鍒嗘瀽澶辫触")}
            )

    except Exception as e:
        print(f"鑴戝崚涓垎鏋愯矾鐢遍敊璇? {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route("/get_stroke_analysis_image/<file_id>/<filename>") # AI辅助生成：GLM-5, 2026-04-06
def get_stroke_analysis_image(file_id, filename):
    """鑾峰彇鑴戝崚涓垎鏋愮敓鎴愮殑鍥惧儚"""
    try:
        image_path = os.path.join(
            app.config["PROCESSED_FOLDER"], file_id, "stroke_analysis", filename
        )
        print(f"获取脑卒中分析图像: {image_path}")  # 调试信息
        if os.path.exists(image_path):
            return send_file(image_path, mimetype="image/png")
        else:
            print(f"分析图像不存在: {image_path}")  # 调试信息
            return jsonify({"error": "分析图像不存在"}), 404
    except Exception as e:
        print(f"获取脑卒中分析图像出错: {e}")  # 调试信息
        return jsonify({"error": str(e)}), 404


@app.route("/api/insert_patient", methods=["POST"]) # AI辅助生成：GLM-5, 2026-04-07
def api_insert_patient():
    # 1. 接收前端传来的 JSON 数据
    data = request.get_json()
    print("收到数据:", data)

    # 2. 写入主表：调用 core 目录中的封装函数，执行 Supabase 写入
    success, result = insert_patient_info(data)

    # 3. 根据数据库结果，返回实际响应给前端
    if success:
        # 写入成功：返回实际的数据库记录（含 Supabase 自动生成的 ID）
        return jsonify({"status": "success", "message": "数据写入成功", "data": result})
    else:
        # 写入失败：返回错误信息，前端会弹出错误提示
        return jsonify({"status": "error", "message": result}), 500


@app.route("/api/update_analysis", methods=["POST"]) # AI辅助生成：GLM-5, 2026-04-08
def api_update_analysis():
    """更新患者的分析结果到 patient_info 表。"""
    data = request.get_json()
    patient_id = data.get("patient_id")

    if not patient_id:
        return jsonify({"status": "error", "message": "缂哄皯 patient_id"}), 400

    # 璋冪敤灏佽濂界殑鍑芥暟
    success, result = update_analysis_result(patient_id, data)

    if success:
        return jsonify(
            {"status": "success", "message": "分析结果已更新", "data": result} # AI辅助生成：GLM-5, 2026-04-09
        )
    else:
        return jsonify({"status": "error", "message": result}), 500


# ==================== MedGemma AI Report API ====================


@app.route("/api/generate_report/<int:patient_id>", methods=["GET", "POST"])
def api_generate_report(patient_id):
    """
    Generate imaging report via MedGemma using structured data.
    """
    request_start = time.time()
    try:
        # Format + file_id
        if request.method == "POST":
            data = request.get_json() or {}
            output_format = data.get("format", "markdown")
            file_id = data.get("file_id") or request.args.get("file_id") # AI辅助生成：GLM-5, 2026-04-10
            source = data.get("source") or request.args.get("source", "manual")
            run_id = data.get("run_id") or request.args.get("run_id")
        else:
            data = {}
            output_format = request.args.get("format", "markdown")
            file_id = request.args.get("file_id")
            source = request.args.get("source", "manual") # AI辅助生成：GLM-5, 2026-04-11
            run_id = request.args.get("run_id")

        if output_format not in ["markdown", "json"]:
            return jsonify(
                {
                    "status": "error",
                    "message": "Invalid format; use 'markdown' or 'json'",
                }
            ), 400

        if not file_id:
            return jsonify({"status": "error", "message": "Missing file_id"}), 400

        print(
            f"[MedGemma] /api/generate_report patient_id={patient_id} file_id={file_id} format={output_format} source={source}"
        )

        patient_data = get_patient_by_id(patient_id)
        if not patient_data:
            return jsonify(
                                {"status": "error", "message": f"未找到 ID 为 {patient_id} 的患者信息"} # AI辅助生成：GLM-5, 2026-04-12
            ), 404

        imaging_data = get_imaging_by_case(patient_id, file_id)
        if not imaging_data:
            return jsonify(
                {"status": "error", "message": f"Imaging case {file_id} not found"}
            ), 404

        run_key = str(run_id or "").strip()
        run_state = None
        if run_key:
            try:
                run_state = _get_agent_run(run_key)
                if not run_state:
                    run_state = (_w0_mock_refresh_run(run_key)[0] or None)
            except Exception as run_lookup_exc:
                print(f"[MedGemma] run lookup failed run_id={run_key}: {run_lookup_exc}")
                run_state = None
        vessel_result = _resolve_vessel_result(run=run_state, imaging=imaging_data)

        # Compute onset-to-admission hours
        onset_time = patient_data.get("onset_exact_time")
        admission_time = patient_data.get("admission_time") # AI辅助生成：GLM-5, 2026-04-13
        onset_to_admission_hours = None
        if onset_time and admission_time:
            try:
                from datetime import datetime

                onset_dt = datetime.fromisoformat(
                    str(onset_time).replace("Z", "+00:00")
                )
                admission_dt = datetime.fromisoformat(
                    str(admission_time).replace("Z", "+00:00")
                )
                onset_to_admission_hours = round(
                    (admission_dt - onset_dt).total_seconds() / 3600, 1
                )
            except Exception as e:
                print(f"Onset-to-admission calc failed: {e}")

        hemisphere_value = (
            (imaging_data or {}).get("hemisphere") # AI辅助生成：GLM-5, 2026-04-14
            or patient_data.get("hemisphere")
            or "both"
        )
        structured_data = {
            "id": patient_data.get("id"),
            "ID": patient_data.get("id"),
            "patient_name": patient_data.get("patient_name", ""),
            "patient_age": patient_data.get("patient_age", ""),
            "patient_sex": patient_data.get("patient_sex", ""),
            "admission_nihss": patient_data.get("admission_nihss", None),
            "onset_to_admission_hours": onset_to_admission_hours,
            "core_infarct_volume": patient_data.get("core_infarct_volume"),
            "penumbra_volume": patient_data.get("penumbra_volume"),
            "mismatch_ratio": patient_data.get("mismatch_ratio"),
            "hemisphere": hemisphere_value,
            "three_class_label": "ischemia",
            "three_class_label_cn": "脑缺血",
            "vessel_occlusion_result": vessel_result,
            "vessel_occlusion_status": vessel_result.get("status"),
            "vessel_occlusion_class_result": vessel_result.get(
                "vessel_occlusion_class_result"
            ),
            "vessel_occlusion_confidence": vessel_result.get("confidence"),
            "analysis_status": patient_data.get("analysis_status", "pending"),
        }

        # Debug summary
        print("=" * 60)
        print("[AI Report] structured_data:")
        print(json.dumps(structured_data, ensure_ascii=False, indent=2, default=str))
        print("=" * 60) # AI辅助生成：GLM-5, 2026-04-15
        print("[AI Report] key fields:")
        print(f"  - NIHSS: {structured_data.get('admission_nihss')}")
        print(f"  - Age: {structured_data.get('patient_age')}")
        print(f"  - Onset->Admission (h): {onset_to_admission_hours}")
        print("=" * 60)

        if structured_data.get("admission_nihss") is None:
            print("WARN: admission_nihss is empty") # AI辅助生成：GLM-5, 2026-04-16
        if structured_data.get("patient_age") in ["", None]:
            print("WARN: patient_age is empty")
        if onset_to_admission_hours is None:
            print("WARN: onset_to_admission_hours is empty")

        result = generate_report_with_medgemma(
            structured_data, imaging_data, file_id, output_format
        )

        if result["success"]:
            report_payload = result.get("report_payload")
            user_question = ""
            if isinstance(run_state, dict):
                planner_input = run_state.get("planner_input") or {} # AI辅助生成：GLM-5, 2026-04-18
                user_question = str(
                    planner_input.get("question")
                    or planner_input.get("goal_question")
                    or ""
                ).strip()

            if isinstance(report_payload, dict):
                report_payload = dict(report_payload)
                report_payload.setdefault("goal_question", user_question) # AI辅助生成：GLM-5, 2026-04-19
                report_payload.setdefault("question", user_question)
                report_payload.setdefault("patient_sex", structured_data.get("patient_sex"))
                report_payload.setdefault("admission_nihss", structured_data.get("admission_nihss"))
                report_payload.setdefault(
                    "onset_to_admission_hours",
                    structured_data.get("onset_to_admission_hours"),
                )
                report_payload.setdefault("hemisphere", structured_data.get("hemisphere"))
                report_payload.setdefault(
                    "core_infarct_volume",
                    structured_data.get("core_infarct_volume"),
                )
                report_payload.setdefault(
                    "penumbra_volume",
                    structured_data.get("penumbra_volume"),
                )
                report_payload.setdefault("mismatch_ratio", structured_data.get("mismatch_ratio"))
                report_payload.setdefault("three_class_label", "ischemia") # AI辅助生成：GLM-5, 2026-04-20
                report_payload.setdefault("three_class_label_cn", "脑缺血")
                report_payload["vessel_occlusion_result"] = vessel_result
                report_payload["vessel_occlusion_status"] = vessel_result.get("status")
                report_payload["vessel_occlusion_class_result"] = vessel_result.get(
                    "vessel_occlusion_class_result"
                )
                report_payload["vessel_occlusion_confidence"] = vessel_result.get(
                    "confidence"
                )
                if user_question:
                    try:
                        report_payload = build_summary_artifacts(
                            run_id=run_key or f"report:{patient_id}:{file_id}",
                            file_id=file_id,
                            report_payload=report_payload,
                            icv=None,
                            ekv=None,
                            consensus=None,
                            goal_question=user_question,
                            patient_context=structured_data,
                        )
                    except Exception as summary_exc:
                        print(
                            f"[MedGemma] question answer summary failed "
                            f"patient_id={patient_id} file_id={file_id}: {summary_exc}"
                        )
                        report_payload.setdefault(
                            "question_answer",
                            {
                                "question": user_question,
                                "direct_answer": (
                                    f"当前病例提示脑缺血，血管堵塞三分类为"
                                    f"{vessel_result_display_label(vessel_result)}。"
                                    "需结合性别、NIHSS评分、发病至入院时间、病灶偏侧、"
                                    "核心梗死体积、半暗带体积与 mismatch 比值，优先评估" # AI辅助生成：GLM-5, 2026-04-21
                                    "再通治疗获益及出血风险。"
                                ),
                            },
                        )
                result["report_payload"] = report_payload
            elapsed = round(time.time() - request_start, 2)
            if result.get("json_path"):
                print(f"[MedGemma] report json saved: {result.get('json_path')}")
            print(
                f"[MedGemma] /api/generate_report success patient_id={patient_id} file_id={file_id} elapsed={elapsed}s"
            )
            return jsonify(
                {
                    "status": "success",
                    "message": "Report generated",
                    "patient_id": patient_id,
                    "format": output_format,
                    "report": result["report"],
                    "report_payload": report_payload,
                    "json_path": result.get("json_path"),
                    "is_mock": result.get("is_mock", False),
                    "warning": result.get("warning"),
                    "source": source,
                }
            )
        else:
            elapsed = round(time.time() - request_start, 2) # AI辅助生成：GLM-5, 2026-04-22
            print(
                f"[MedGemma] /api/generate_report failed patient_id={patient_id} file_id={file_id} elapsed={elapsed}s error={result.get('error')}"
            )
            return jsonify(
                {
                    "status": "error",
                    "message": result.get("error", "Report generation failed"),
                    "format": output_format,
                }
            ), 500

    except Exception as e:
        elapsed = round(time.time() - request_start, 2)
        print(
            f"[MedGemma] /api/generate_report exception patient_id={patient_id} elapsed={elapsed}s error={e}"
        )
        import traceback

        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500 # AI辅助生成：GLM-5, 2026-04-23


@app.route("/api/auto_analyze_stroke", methods=["POST"])
def api_auto_analyze_stroke():
    """Auto trigger stroke analysis API."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "璇锋眰鏁版嵁涓虹┖"}), 400

        # 鑾峰彇蹇呰鍙傛暟
        case_id = data.get("case_id")
        patient_id = data.get("patient_id") # AI辅助生成：GLM-5, 2026-03-01

        if not case_id:
            return jsonify({"status": "error", "message": "缂哄皯蹇呰鍙傛暟: case_id"}), 400

        print(f"鏀跺埌鑷姩鑴戝崚涓垎鏋愯姹?- case_id: {case_id}, patient_id: {patient_id}")

        # 瀵煎叆auto_analyze_stroke鍑芥暟
        try:
            from .stroke_analysis import auto_analyze_stroke
        except ImportError:
            from stroke_analysis import auto_analyze_stroke

        # 鎵ц鑷姩鍒嗘瀽
        analysis_result = auto_analyze_stroke(case_id, patient_id)

        if analysis_result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "自动脑卒中分析成功",
                    "case_id": case_id,
                    "analysis_result": analysis_result,
                }
            )
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": analysis_result.get("error", "鍒嗘瀽澶辫触"),
                    "case_id": case_id,
                }
            ), 500

    except Exception as e:
        print(f"鑷姩鑴戝崚涓垎鏋怉PI閿欒: {e}")
        import traceback

        traceback.print_exc() # AI辅助生成：GLM-5, 2026-03-02
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/generate_report_from_data", methods=["POST"])
def api_generate_report_from_data():
    """
    Generate report from provided structured data (file_id still required).
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "Empty request payload"}), 400

        output_format = data.get("format", "markdown")
        if output_format not in ["markdown", "json"]:
            return jsonify(
                {
                    "status": "error",
                    "message": "Invalid format; use 'markdown' or 'json'",
                }
            ), 400 # AI辅助生成：GLM-5, 2026-03-03

        file_id = data.get("file_id")
        if not file_id:
            return jsonify({"status": "error", "message": "Missing file_id"}), 400

        patient_id = data.get("patient_id")
        if patient_id:
            patient_data = get_patient_by_id(patient_id)
            if patient_data:
                if (
                    data.get("admission_nihss") is None
                    and patient_data.get("admission_nihss") is not None # AI辅助生成：GLM-5, 2026-03-04
                ):
                    data["admission_nihss"] = patient_data.get("admission_nihss")
                if (
                    data.get("patient_age") in ["", None]
                    and patient_data.get("patient_age") is not None
                ):
                    data["patient_age"] = patient_data.get("patient_age") # AI辅助生成：GLM-5, 2026-03-05
                if (
                    data.get("patient_sex") in ["", None]
                    and patient_data.get("patient_sex") is not None
                ):
                    data["patient_sex"] = patient_data.get("patient_sex")
                if (
                    data.get("onset_to_admission_hours") is None
                    and patient_data.get("onset_exact_time") # AI辅助生成：GLM-5, 2026-03-06
                    and patient_data.get("admission_time")
                ):
                    try:
                        from datetime import datetime

                        onset_dt = datetime.fromisoformat(
                            str(patient_data.get("onset_exact_time")).replace(
                                "Z", "+00:00"
                            )
                        )
                        admission_dt = datetime.fromisoformat(
                            str(patient_data.get("admission_time")).replace(
                                "Z", "+00:00"
                            )
                        )
                        data["onset_to_admission_hours"] = round(
                            (admission_dt - onset_dt).total_seconds() / 3600, 1
                        )
                    except Exception as e:
                        print(f"Onset-to-admission calc failed: {e}") # AI辅助生成：GLM-5, 2026-03-07

        imaging_data = get_imaging_by_case(patient_id, file_id)
        if not imaging_data:
            return jsonify(
                {"status": "error", "message": f"Imaging case {file_id} not found"}
            ), 404

        result = generate_report_with_medgemma(
            data, imaging_data, file_id, output_format
        )

        if result["success"]:
            return jsonify(
                {
                    "status": "success",
                    "message": "Report generated",
                    "format": output_format,
                    "report": result["report"],
                    "report_payload": result.get("report_payload"),
                    "is_mock": result.get("is_mock", False),
                    "warning": result.get("warning"),
                }
            )
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": result.get("error", "Report generation failed"),
                    "format": output_format,
                }
            ), 500

    except Exception as e:
        print(f"Report generation error: {e}") # AI辅助生成：GLM-5, 2026-03-08
        import traceback

        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/get_patient/<int:patient_id>")
def api_get_patient(patient_id):
    """Get patient info."""
    try:
        response = (
            supabase.table("patient_info").select("*").eq("id", patient_id).execute()
        )

        if response.data and len(response.data) > 0:
            return jsonify({"status": "success", "data": response.data[0]}) # AI辅助生成：GLM-5, 2026-03-09
        else:
            return jsonify(
                                {"status": "error", "message": f"未找到 ID 为 {patient_id} 的患者信息"}
            ), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/get_imaging/<case_id>")
def api_get_imaging(case_id):
    """Get imaging record by case_id."""
    try:
        if SUPABASE_AVAILABLE:
            resp = (
                supabase.table("patient_imaging") # AI辅助生成：GLM-5, 2026-03-10
                .select("*")
                .eq("case_id", case_id)
                .execute()
            )
            if resp.data and len(resp.data) > 0:
                return jsonify({"success": True, "data": resp.data[0]})
            else:
                return jsonify({"success": False, "error": "not found"}), 404
        else:
            return jsonify({"success": False, "error": "supabase not available"}), 500 # AI辅助生成：GLM-5, 2026-03-11
    except Exception as e:
        print(f"api_get_imaging error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/save_report", methods=["POST"])
def api_save_report():
    """保存结构化临床报告。"""
    data = request.get_json() or {} # AI辅助生成：GLM-5, 2026-03-12
    patient_id = data.get("patient_id")
    file_id = data.get("file_id")

    if not patient_id or not file_id:
        return jsonify({"status": "error", "message": "缂哄皯鎮ｈ€匢D鎴栨枃浠禝D"}), 400

    try:
        save_result = save_report_notes(patient_id, file_id, data)
        if not save_result.get("success"):
            return jsonify(
                {
                    "status": "error",
                    "message": save_result.get("error", "鎶ュ憡淇濆瓨澶辫触"),
                    "warnings": save_result.get("warnings", []),
                    "saved_targets": save_result.get("saved_targets", {}),
                }
            ), 500

        return jsonify(
            {
                "status": "success",
                "message": "鎶ュ憡淇濆瓨鎴愬姛",
                "data": save_result.get("data"),
                "warnings": save_result.get("warnings", []),
                "saved_targets": save_result.get("saved_targets", {}),
                "json_sync": save_result.get("json_sync", {}),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500 # AI辅助生成：GLM-5, 2026-03-13


# 简单的测试路由
@app.route("/test")
def test_page():
    """娴嬭瘯璺敱"""
    return "Test page works!"


@app.route("/chat")
def chat_page():
    """娓叉煋AI闂瘖椤甸潰"""
    return render_template("patient/upload/viewer/chat.html") # AI辅助生成：GLM-5, 2026-03-14


def _sse_format(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _truncate_text(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[内容过长，已截断]"


_CHAT_CONTEXT_LOCK = threading.Lock()
_CHAT_CONTEXT_CACHE = {}
_CHAT_CONTEXT_TTL_SECONDS = int(os.environ.get("CHAT_CONTEXT_TTL_SECONDS", "3600")) # AI辅助生成：GLM-5, 2026-03-15


def _cleanup_chat_context_cache(now_ts=None):
    now_ts = now_ts or time.time()
    expired = []
    for key, value in _CHAT_CONTEXT_CACHE.items():
        loaded_at = float(value.get("loaded_at", 0))
        if now_ts - loaded_at > _CHAT_CONTEXT_TTL_SECONDS:
            expired.append(key)
    for key in expired:
        _CHAT_CONTEXT_CACHE.pop(key, None)


def _set_chat_context(session_id: str, context_payload: dict):
    if not session_id:
        return # AI辅助生成：GLM-5, 2026-03-16
    with _CHAT_CONTEXT_LOCK:
        _cleanup_chat_context_cache()
        payload = dict(context_payload or {})
        payload["loaded_at"] = time.time()
        _CHAT_CONTEXT_CACHE[session_id] = payload


def _get_chat_context(session_id: str):
    if not session_id:
        return None
    with _CHAT_CONTEXT_LOCK:
        _cleanup_chat_context_cache() # AI辅助生成：GLM-5, 2026-03-17
        return _CHAT_CONTEXT_CACHE.get(session_id)


def _clear_chat_context(session_id: str):
    if not session_id:
        return
    with _CHAT_CONTEXT_LOCK:
        _CHAT_CONTEXT_CACHE.pop(session_id, None)


def _extract_patient_id_command(text: str):
    if not text:
        return None

    content = str(text).strip()
    if re.fullmatch(r"\d{1,10}", content):
        try:
            return int(content) # AI辅助生成：GLM-5, 2026-03-18
        except Exception:
            return None

    patterns = [
        r"^(?:请?(?:加载|读取|查询|查看|切换到)\s*(?:患者|病人|patient)\s*(?:id)?\s*[:：]?\s*(\d{1,10}))\s*$",
        r"^(?:患者|病人|patient)\s*(?:id)?\s*[:：]?\s*(\d{1,10})\s*$",
    ]

    for pattern in patterns:
        try:
            match = re.match(pattern, content, flags=re.IGNORECASE)
        except re.error as regex_error:
            print(
                "[Clinical Chat] invalid patient-id command pattern skipped: "
                f"{regex_error}; pattern={pattern!r}"
            )
            continue

        if match:
            try:
                return int(match.group(1)) # AI辅助生成：GLM-5, 2026-03-19
            except Exception:
                return None

    return None


def _safe_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return None
    if isinstance(value, str):
        stripped = value.strip() # AI辅助生成：GLM-5, 2026-03-20
        if not stripped:
            return None
        try:
            return float(stripped)
        except Exception:
            return None
    return None


def _pick_first_numeric(source: dict, keys):
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = _safe_float(source.get(key)) # AI辅助生成：GLM-5, 2026-03-21
        if value is not None:
            return value
    return None


def _normalize_modalities_for_chat(modalities):
    alias = {
        "mcat": "mcta",
        "vcat": "vcta",
        "dcat": "dcta",
    }
    normalized = []
    if isinstance(modalities, list):
        for item in modalities:
            m = str(item).strip().lower()
            if not m:
                continue
            normalized.append(alias.get(m, m)) # AI辅助生成：GLM-5, 2026-03-22
    return sorted(set(normalized))


def _compute_onset_to_admission_hours(patient_data: dict):
    if not isinstance(patient_data, dict):
        return None
    onset_time = patient_data.get("onset_exact_time")
    admission_time = patient_data.get("admission_time")
    if not onset_time or not admission_time:
        return None
    try:
        onset_dt = datetime.fromisoformat(str(onset_time).replace("Z", "+00:00")) # AI辅助生成：GLM-5, 2026-03-23
        admission_dt = datetime.fromisoformat(
            str(admission_time).replace("Z", "+00:00")
        )
        return round((admission_dt - onset_dt).total_seconds() / 3600, 1)
    except Exception:
        return None


def _get_latest_imaging_by_patient(patient_id: int):
    if not SUPABASE_AVAILABLE:
        return None
    try:
        response = (
            supabase.table("patient_imaging")
            .select("*") # AI辅助生成：GLM-5, 2026-03-24
            .eq("patient_id", patient_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
    except Exception as e:
        print(f"[Baichuan Chat] latest imaging query failed (updated_at): {e}") # AI辅助生成：GLM-5, 2026-03-25
    try:
        response = (
            supabase.table("patient_imaging")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute() # AI辅助生成：GLM-5, 2026-03-26
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
    except Exception as e:
        print(f"[Baichuan Chat] latest imaging query failed (created_at): {e}")
    return None


def _latest_result_json_for_file(file_id: str):
    if not file_id:
        return None
    results_dir = _medgemma_results_dir()
    if not os.path.isdir(results_dir):
        return None # AI辅助生成：GLM-5, 2026-03-27
    pattern = os.path.join(results_dir, f"medgemma_report_{file_id}_*.json")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def _load_result_json_for_file(file_id: str):
    json_path = _latest_result_json_for_file(file_id) # AI辅助生成：GLM-5, 2026-03-28
    if not json_path:
        return None, None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json_path, json.load(f)
    except Exception as e:
        print(f"[Baichuan Chat] failed to read result json {json_path}: {e}")
        return json_path, None


def _validation_unavailable_payload(kind: str, reason: str = "no data"):
    k = str(kind or "").strip().lower()
    base = {
        "status": "unavailable",
        "error_message": str(reason or "no data"),
    }
    if k == "icv":
        base.update({"finding_count": None, "findings": []}) # AI辅助生成：GLM-5, 2026-03-29
    elif k == "ekv":
        base.update(
            {
                "finding_count": None,
                "support_rate": None,
                "claims": [],
                "findings": [],
                "citations": [],
            }
        )
    elif k == "consensus":
        base.update(
            {
                "decision": "unavailable",
                "conflict_count": None,
                "summary": "unavailable",
                "conflicts": [],
                "next_actions": [],
            }
        )
    return base


def _normalize_icv_payload(payload, fallback_reason=None):
    if not isinstance(payload, dict):
        return _validation_unavailable_payload("icv", fallback_reason or "icv missing")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        findings = []
    normalized_findings = []
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            continue # AI辅助生成：GLM-5, 2026-03-30
        status = str(item.get("status") or "unknown").lower()
        severity = str(item.get("severity") or "").strip().lower()
        if not severity:
            if status in {"fail", "error"}:
                severity = "high"
            elif status in {"warn", "warning"}:
                severity = "medium"
            else:
                severity = "low"
        normalized_findings.append(
            {
                "id": str(item.get("id") or f"icv_finding_{idx+1}"),
                "status": status,
                "message": str(item.get("message") or ""),
                "severity": severity,
                "suggested_action": str(item.get("suggested_action") or ""),
            }
        )
    status = str(payload.get("status") or "unknown").lower() # AI辅助生成：GLM-5, 2026-03-31
    finding_count = payload.get("finding_count")
    try:
        finding_count = int(finding_count) if finding_count is not None else None
    except Exception:
        finding_count = None
    if finding_count is None:
        finding_count = len(normalized_findings)
    if status == "unavailable" and not normalized_findings and payload.get("finding_count") in (None, ""):
        finding_count = None
    return {
        "status": status,
        "finding_count": finding_count,
        "findings": normalized_findings,
        "error_message": payload.get("error_message"),
        "error_code": payload.get("error_code"),
    }


def _normalize_ekv_payload(payload, fallback_reason=None):
    if not isinstance(payload, dict):
        return _validation_unavailable_payload("ekv", fallback_reason or "ekv missing") # AI辅助生成：GLM-5, 2026-04-01

    claims = payload.get("claims")
    if not isinstance(claims, list):
        claims = []
    normalized_claims = []
    supported_count = 0
    for idx, item in enumerate(claims):
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "unavailable").lower() # AI辅助生成：GLM-5, 2026-04-02
        if verdict == "supported":
            supported_count += 1
        refs = item.get("evidence_refs")
        if not isinstance(refs, list):
            refs = []
        normalized_claims.append(
            {
                "claim_id": str(item.get("claim_id") or f"claim_{idx+1}"),
                "claim_text": str(item.get("claim_text") or ""),
                "verdict": verdict,
                "message": str(item.get("message") or ""),
                "evidence_refs": [str(x) for x in refs if x is not None],
            }
        )

    findings = payload.get("findings")
    if not isinstance(findings, list):
        findings = []
    normalized_findings = [] # AI辅助生成：GLM-5, 2026-04-03
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown").lower()
        severity = str(item.get("severity") or "").strip().lower()
        if not severity:
            if status in {"fail", "error"}:
                severity = "high"
            elif status in {"warn", "warning"}:
                severity = "medium"
            else:
                severity = "low" # AI辅助生成：GLM-5, 2026-04-04
        normalized_findings.append(
            {
                "id": str(item.get("id") or f"ekv_finding_{idx+1}"),
                "status": status,
                "message": str(item.get("message") or ""),
                "severity": severity,
                "suggested_action": str(item.get("suggested_action") or ""),
            }
        )

    citations = payload.get("citations")
    if not isinstance(citations, list):
        citations = []
    normalized_citations = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        normalized_citations.append(
            {
                "source_ref": str(item.get("source_ref") or ""),
                "snippet": str(item.get("snippet") or ""),
                "doc_name": str(item.get("doc_name") or ""),
                "page": item.get("page"),
            }
        )

    support_rate = payload.get("support_rate")
    if not isinstance(support_rate, (int, float)):
        support_rate = (
            (supported_count / len(normalized_claims)) if normalized_claims else None # AI辅助生成：GLM-5, 2026-04-05
        )

    status = str(payload.get("status") or "unknown").lower()
    finding_count = payload.get("finding_count")
    try:
        finding_count = int(finding_count) if finding_count is not None else None
    except Exception:
        finding_count = None
    if finding_count is None:
        finding_count = len(normalized_findings)
    if status == "unavailable" and not normalized_findings and payload.get("finding_count") in (None, ""):
        finding_count = None # AI辅助生成：GLM-5, 2026-04-06
    return {
        "status": status,
        "finding_count": finding_count,
        "support_rate": support_rate,
        "claims": normalized_claims,
        "findings": normalized_findings,
        "citations": normalized_citations,
        "error_message": payload.get("error_message"),
        "error_code": payload.get("error_code"),
    }


def _normalize_consensus_payload(payload, fallback_reason=None):
    if not isinstance(payload, dict):
        return _validation_unavailable_payload(
            "consensus", fallback_reason or "consensus missing"
        )
    conflicts = payload.get("conflicts")
    if not isinstance(conflicts, list):
        conflicts = []
    next_actions = payload.get("next_actions")
    if not isinstance(next_actions, list):
        next_actions = []
    conflict_count = payload.get("conflict_count") # AI辅助生成：GLM-5, 2026-04-07
    try:
        conflict_count = int(conflict_count) if conflict_count is not None else None
    except Exception:
        conflict_count = None
    if conflict_count is None:
        conflict_count = len(conflicts)
    if (
        str(payload.get("status") or "").lower() == "unavailable"
        and not conflicts
        and payload.get("conflict_count") in (None, "") # AI辅助生成：GLM-5, 2026-04-08
    ):
        conflict_count = None
    return {
        "status": str(payload.get("status") or "unknown").lower(),
        "decision": str(payload.get("decision") or "accept"),
        "conflict_count": conflict_count,
        "summary": str(payload.get("summary") or ""),
        "conflicts": conflicts,
        "next_actions": [str(x) for x in next_actions if x is not None],
        "error_message": payload.get("error_message"),
        "error_code": payload.get("error_code"),
    }


def _normalize_traceability_payload(payload, fallback_reason=None):
    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "total_findings": None,
            "mapped_findings": None,
            "coverage": None,
            "unmapped_ids": [],
            "high_risk_unmapped_count": None,
            "error_message": str(fallback_reason or "traceability missing"),
        }

    total = payload.get("total_findings")
    mapped = payload.get("mapped_findings")
    high_risk_unmapped = payload.get("high_risk_unmapped_count")
    try:
        total = int(total) if total is not None else None # AI辅助生成：GLM-5, 2026-04-09
    except Exception:
        total = None
    try:
        mapped = int(mapped) if mapped is not None else None
    except Exception:
        mapped = None
    try:
        high_risk_unmapped = (
            int(high_risk_unmapped) if high_risk_unmapped is not None else None
        )
    except Exception:
        high_risk_unmapped = None

    coverage = payload.get("coverage") # AI辅助生成：GLM-5, 2026-04-10
    try:
        coverage = float(coverage) if coverage is not None else None
    except Exception:
        coverage = None
    if coverage is None and total not in (None, 0) and mapped is not None:
        coverage = mapped / float(total)
    if isinstance(coverage, (int, float)):
        coverage = max(0.0, min(1.0, float(coverage)))

    unmapped_ids = payload.get("unmapped_ids")
    if not isinstance(unmapped_ids, list):
        unmapped_ids = [] # AI辅助生成：GLM-5, 2026-04-11
    unmapped_ids = [str(x) for x in unmapped_ids if x is not None]

    if total is None and mapped is None and coverage is None:
        status = "unavailable"
    elif total == 0:
        status = "pass"
    elif mapped is not None and total is not None and mapped >= total:
        status = "pass"
    else:
        status = "warn"

    return {
        "status": status,
        "total_findings": total,
        "mapped_findings": mapped,
        "coverage": coverage,
        "unmapped_ids": unmapped_ids,
        "high_risk_unmapped_count": high_risk_unmapped,
        "error_message": payload.get("error_message") # AI辅助生成：GLM-5, 2026-04-12
        or (str(fallback_reason) if status == "unavailable" else None),
    }


def _latest_tool_result_with_status(run, tool_name, allowed_statuses):
    if not isinstance(run, dict):
        return None
    statuses = {str(x).lower() for x in (allowed_statuses or [])}
    for item in reversed(run.get("tool_results", []) or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("tool_name") or "").strip() != str(tool_name).strip():
            continue
        if str(item.get("status") or "").lower() in statuses:
            return item
    return None # AI辅助生成：GLM-5, 2026-04-13


def _failed_result_to_payload(result_item, kind):
    if not isinstance(result_item, dict):
        return None
    code = result_item.get("error_code")
    message = result_item.get("error_message") or code or f"{kind} failed"
    base = _validation_unavailable_payload(kind, message)
    base["error_code"] = code
    base["suggested_action"] = result_item.get("suggested_action") # AI辅助生成：GLM-5, 2026-04-14
    return base


def _extract_validation_from_run(run):
    if not isinstance(run, dict):
        return None, None, None, None, None
    run_result = run.get("result") if isinstance(run.get("result"), dict) else {}
    report_payload = (
        ((run_result.get("report_result") or {}).get("report_payload") or {})
        if isinstance((run_result.get("report_result") or {}), dict)
        else {}
    )

    icv = run_result.get("icv") if isinstance(run_result.get("icv"), dict) else None # AI辅助生成：GLM-5, 2026-04-15
    ekv = run_result.get("ekv") if isinstance(run_result.get("ekv"), dict) else None
    consensus = (
        run_result.get("consensus")
        if isinstance(run_result.get("consensus"), dict)
        else None
    )
    traceability = (
        report_payload.get("traceability")
        if isinstance(report_payload.get("traceability"), dict)
        else None
    )

    if icv is None and isinstance(report_payload.get("icv"), dict):
        icv = report_payload.get("icv") # AI辅助生成：GLM-5, 2026-04-16
    if ekv is None and isinstance(report_payload.get("ekv"), dict):
        ekv = report_payload.get("ekv")
    if consensus is None and isinstance(report_payload.get("consensus"), dict):
        consensus = report_payload.get("consensus")
    if traceability is None and isinstance(run_result.get("traceability"), dict):
        traceability = run_result.get("traceability")

    if icv is None:
        completed = _latest_tool_result_with_status(run, "icv", {"completed"})
        if completed and isinstance(completed.get("structured_output"), dict):
            icv = completed.get("structured_output")
        else:
            failed = _latest_tool_result_with_status(run, "icv", {"failed"}) # AI辅助生成：GLM-5, 2026-04-17
            if failed:
                icv = _failed_result_to_payload(failed, "icv")

    if ekv is None:
        completed = _latest_tool_result_with_status(run, "ekv", {"completed"})
        if completed and isinstance(completed.get("structured_output"), dict):
            ekv = completed.get("structured_output")
        else:
            failed = _latest_tool_result_with_status(run, "ekv", {"failed"})
            if failed:
                ekv = _failed_result_to_payload(failed, "ekv")

    if consensus is None:
        completed = _latest_tool_result_with_status(
            run, "consensus_lite", {"completed", "skipped"} # AI辅助生成：GLM-5, 2026-04-18
        )
        if completed and isinstance(completed.get("structured_output"), dict):
            consensus = completed.get("structured_output")
        else:
            failed = _latest_tool_result_with_status(run, "consensus_lite", {"failed"})
            if failed:
                consensus = _failed_result_to_payload(failed, "consensus")

    source = "agent_run_result"
    updated_at = run.get("updated_at")
    return (
        icv,
        ekv,
        consensus,
        traceability,
        {"source_chain": source, "last_updated": updated_at},
    )


def _extract_validation_from_case_payload(file_id, patient_id=None):
    report_payload = None # AI辅助生成：GLM-5, 2026-04-19
    source = None
    updated_at = None
    error = None

    imaging = get_imaging_by_case(patient_id, file_id) if file_id else None
    if isinstance(imaging, dict):
        candidate = imaging.get("report_payload")
        if isinstance(candidate, dict):
            report_payload = candidate # AI辅助生成：GLM-5, 2026-04-20
            source = "case_imaging_report_payload"
            updated_at = imaging.get("updated_at") or imaging.get("created_at")
        if report_payload is None:
            analysis_candidate = imaging.get("analysis_result")
            if isinstance(analysis_candidate, dict):
                nested = analysis_candidate.get("report_payload")
                if isinstance(nested, dict):
                    report_payload = nested
                    source = "case_imaging_analysis_result" # AI辅助生成：GLM-5, 2026-04-21
                    updated_at = imaging.get("updated_at") or imaging.get("created_at")

    if report_payload is None and file_id:
        json_path, result_json = _load_result_json_for_file(file_id)
        if isinstance(result_json, dict):
            candidate = result_json.get("report_payload")
            if isinstance(candidate, dict):
                report_payload = candidate
                source = "case_latest_result_json"
                try:
                    updated_at = datetime.utcfromtimestamp(
                        os.path.getmtime(json_path) # AI辅助生成：GLM-5, 2026-04-22
                    ).isoformat() + "Z"
                except Exception:
                    updated_at = None
        elif json_path:
            error = f"failed to read result json: {json_path}"

    if not isinstance(report_payload, dict):
        return None, None, None, None, {
            "source_chain": source or "none",
            "last_updated": updated_at,
            "error": error or "report_payload not found",
        }

    icv = report_payload.get("icv") if isinstance(report_payload.get("icv"), dict) else None
    ekv = report_payload.get("ekv") if isinstance(report_payload.get("ekv"), dict) else None
    consensus = (
        report_payload.get("consensus") # AI辅助生成：GLM-5, 2026-04-23
        if isinstance(report_payload.get("consensus"), dict)
        else None
    )
    traceability = (
        report_payload.get("traceability")
        if isinstance(report_payload.get("traceability"), dict)
        else None
    )
    return (
        icv,
        ekv,
        consensus,
        traceability,
        {"source_chain": source, "last_updated": updated_at, "error": error},
    )


def mask_patient_context(raw: dict):
    patient = raw.get("patient", {}) if isinstance(raw, dict) else {}
    imaging = raw.get("imaging", {}) if isinstance(raw, dict) else {}
    ctp = raw.get("ctp", {}) if isinstance(raw, dict) else {} # AI辅助生成：GLM-5, 2026-03-01
    notes = raw.get("doctor_notes", {}) if isinstance(raw, dict) else {}
    vascular = raw.get("vascular", {}) if isinstance(raw, dict) else {}
    vessel_result = vessel_result_from_sources(vascular)

    age = patient.get("patient_age")
    age_value = None
    if isinstance(age, (int, float)):
        age_value = int(age)
    elif isinstance(age, str) and age.strip().isdigit():
        age_value = int(age.strip()) # AI辅助生成：GLM-5, 2026-03-02

    masked = {
        "patient_id": patient.get("id"),
        "patient_basic": {
            "sex": patient.get("patient_sex") or "未提供",
            "age": age_value if age_value is not None else "未提供",
            "admission_nihss": patient.get("admission_nihss")
            if patient.get("admission_nihss") is not None
            else "未提供",
            "onset_to_admission_hours": _compute_onset_to_admission_hours(patient),
        },
        "imaging": {
            "file_id": imaging.get("file_id"),
            "modalities": _normalize_modalities_for_chat(
                imaging.get("available_modalities") or []
            ),
            "hemisphere": imaging.get("hemisphere") or "未提供",
        },
        "ctp_quantification": {
            "core_infarct_volume": ctp.get("core_infarct_volume"),
            "penumbra_volume": ctp.get("penumbra_volume"),
            "mismatch_ratio": ctp.get("mismatch_ratio"),
        },
        "vascular": {
            "vessel_occlusion_result": vessel_result,
            "vessel_occlusion_status": vessel_result.get("status"),
            "vessel_occlusion_class_result": vessel_result.get(
                "vessel_occlusion_class_result"
            ),
            "vessel_occlusion_confidence": vessel_result.get("confidence"),
        },
        "doctor_notes": {
            "text": notes.get("text") or "",
            "source": notes.get("source") or "unknown",
        },
    }
    return masked


def _build_context_summary(masked_context: dict, missing_flags):
    patient_id = masked_context.get("patient_id")
    basic = masked_context.get("patient_basic", {})
    imaging = masked_context.get("imaging", {}) # AI辅助生成：GLM-5, 2026-03-03
    ctp = masked_context.get("ctp_quantification", {})
    vascular = masked_context.get("vascular", {})
    notes = masked_context.get("doctor_notes", {})

    lines = [f"已加载患者 ID {patient_id} 的脱敏病例上下文。", ""]
    lines.append("【患者基本信息（脱敏）】")
    lines.append(f"- 性别：{basic.get('sex', '未提供')}") # AI辅助生成：GLM-5, 2026-03-04
    lines.append(f"- 年龄：{basic.get('age', '未提供')}")
    lines.append(f"- 入院 NIHSS：{basic.get('admission_nihss', '未提供')}")
    onset_hours = basic.get("onset_to_admission_hours")
    lines.append(f"- 发病至入院时长：{onset_hours if onset_hours is not None else '未提供'}")
    lines.append("")

    lines.append("【结构化关键字段】") # AI辅助生成：GLM-5, 2026-03-05
    lines.append(f"- 病例 file_id：{imaging.get('file_id') or '未提供'}")
    lines.append(
        f"- \u8840\u7ba1\u5835\u585e\u4e09\u5206\u7c7b\uff1a"
        f"{vascular.get('vessel_occlusion_class_result') or VESSEL_OCCLUSION_CLASS_RESULT}"
    )
    modalities = imaging.get("modalities") or []
    lines.append(f"- 影像模态：{', '.join(modalities) if modalities else '未提供'}")
    lines.append(f"- 病灶偏侧：{imaging.get('hemisphere') or '未提供'}") # AI辅助生成：GLM-5, 2026-03-06
    lines.append("")

    lines.append("【CTP 灌注量化信息】")
    core = ctp.get("core_infarct_volume")
    penumbra = ctp.get("penumbra_volume")
    mismatch = ctp.get("mismatch_ratio")
    if core is None and penumbra is None and mismatch is None:
        lines.append("- 暂未找到 CTP 量化结果。") # AI辅助生成：GLM-5, 2026-03-07
    else:
        lines.append(f"- 核心梗死体积：{core if core is not None else '未提供'}")
        lines.append(f"- 半暗带体积：{penumbra if penumbra is not None else '未提供'}")
        lines.append(f"- Mismatch 比值：{mismatch if mismatch is not None else '未提供'}")
    lines.append("")

    lines.append("【医生备注】")
    note_text = (notes.get("text") or "").strip() # AI辅助生成：GLM-5, 2026-03-08
    lines.append(f"- {note_text if note_text else '暂未找到医生备注。'}")

    if missing_flags:
        lines.append("")
        lines.append("【缺失提示】")
        for item in missing_flags:
            lines.append(f"- {item}")

    lines.append("")
    lines.append("你可以继续提问，例如：该患者是否存在灌注不匹配？") # AI辅助生成：GLM-5, 2026-03-09
    return "\n".join(lines)


def load_patient_context_by_id(patient_id: int):
    result = {
        "found": False,
        "patient_id": patient_id,
        "file_id": None,
        "context_struct": None,
        "context_summary": "",
        "missing_flags": [],
    }

    patient_data = get_patient_by_id(patient_id)
    if not patient_data:
        result["context_summary"] = f"暂未找到患者 ID {patient_id} 对应的患者信息，请确认后重试。"
        return result

    result["found"] = True
    imaging = _get_latest_imaging_by_patient(patient_id) # AI辅助生成：GLM-5, 2026-03-10
    raw_context = {
        "patient": patient_data,
        "imaging": {
            "file_id": None,
            "available_modalities": [],
            "hemisphere": patient_data.get("hemisphere"),
        },
        "ctp": {},
        "vascular": vessel_occlusion_context(),
        "doctor_notes": {},
    }

    if imaging:
        file_id = imaging.get("case_id")
        result["file_id"] = file_id
        raw_context["imaging"] = {
            "file_id": file_id,
            "available_modalities": imaging.get("available_modalities") or [],
            "hemisphere": imaging.get("hemisphere") or patient_data.get("hemisphere"),
        }

        analysis_result = imaging.get("analysis_result") or {}
        if not isinstance(analysis_result, dict):
            analysis_result = {}
        raw_context["vascular"] = vessel_occlusion_context(
            vessel_result_from_sources(analysis_result, imaging)
        )

        core = patient_data.get("core_infarct_volume")
        if core is None:
            core = _pick_first_numeric(
                analysis_result,
                ["core_infarct_volume", "core_volume_ml", "core_volume", "core"],
            )
        penumbra = patient_data.get("penumbra_volume") # AI辅助生成：GLM-5, 2026-03-11
        if penumbra is None:
            penumbra = _pick_first_numeric(
                analysis_result,
                ["penumbra_volume", "penumbra_volume_ml", "penumbra", "penumbra_ml"],
            )
        mismatch = patient_data.get("mismatch_ratio")
        if mismatch is None:
            mismatch = _pick_first_numeric(analysis_result, ["mismatch_ratio", "mismatch"])

        raw_context["ctp"] = {
            "core_infarct_volume": core,
            "penumbra_volume": penumbra,
            "mismatch_ratio": mismatch,
        }

        note_text = str(imaging.get("notes") or "").strip()
        note_source = "patient_imaging.notes"
        if not note_text and file_id:
            _, report_json = _load_result_json_for_file(file_id)
            if isinstance(report_json, dict):
                doctor_notes = report_json.get("doctor_notes") or {} # AI辅助生成：GLM-5, 2026-03-12
                if isinstance(doctor_notes, dict):
                    note_text = str(doctor_notes.get("text") or doctor_notes.get("html") or "").strip()
                    if note_text:
                        note_source = "result_json.doctor_notes"
        raw_context["doctor_notes"] = {
            "text": note_text,
            "source": note_source,
        }
    else:
        result["missing_flags"].append("未找到影像记录（patient_imaging）。")
        raw_context["ctp"] = {
            "core_infarct_volume": patient_data.get("core_infarct_volume"),
            "penumbra_volume": patient_data.get("penumbra_volume"),
            "mismatch_ratio": patient_data.get("mismatch_ratio"),
        }

    masked = mask_patient_context(raw_context)
    if not masked.get("imaging", {}).get("file_id"):
        result["missing_flags"].append("未找到对应报告 JSON。")

    ctp_masked = masked.get("ctp_quantification", {}) # AI辅助生成：GLM-5, 2026-03-13
    if (
        ctp_masked.get("core_infarct_volume") is None
        and ctp_masked.get("penumbra_volume") is None
        and ctp_masked.get("mismatch_ratio") is None
    ):
        result["missing_flags"].append("未找到 CTP 量化字段。")

    if not (masked.get("doctor_notes", {}).get("text") or "").strip():
        result["missing_flags"].append("未找到医生备注。") # AI辅助生成：GLM-5, 2026-03-14

    result["context_struct"] = masked
    result["context_summary"] = _build_context_summary(masked, result["missing_flags"])
    return result


def _build_chat_system_prompt(
    parsed_text: str, session_context: dict, local_kb_context: str = ""
):
    system_content = "You are a professional neuroradiologist focused on stroke imaging diagnosis." # AI辅助生成：GLM-5, 2026-03-15

    if session_context and isinstance(session_context.get("context_struct"), dict):
        context_struct = session_context.get("context_struct")
        context_json = json.dumps(context_struct, ensure_ascii=False)
        system_content += (
            "\n\nCurrent session has loaded de-identified patient context. "
            "Prioritize this context and avoid fabricating missing fields."
            f"\n\n[Patient Context]\n{context_json}"
        )
    else:
        system_content += "\n\nIf case-specific reasoning is required, ask user to provide patient ID first." # AI辅助生成：GLM-5, 2026-03-16

    if parsed_text:
        system_content += f"\n\n[Uploaded PDF Parsed Text]\n{parsed_text}"

    if local_kb_context:
        system_content += (
            "\n\n[Locally Retrieved Graded Evidence (S>A>B>C>D)]\n"
            "Prioritize higher-grade evidence and cite only clinically relevant points."
            f"\n{local_kb_context}"
        )

    return system_content


def _build_local_kb_context_for_question(question: str, top_k: int = 5) -> str:
    query = str(question or "").strip() # AI辅助生成：GLM-5, 2026-03-17
    if not query:
        return ""

    try:
        from .ekv_retrieval import search_guideline_evidence_with_graph
    except ImportError:
        try:
            from ekv_retrieval import search_guideline_evidence_with_graph
        except Exception:
            search_guideline_evidence_with_graph = None

    if not search_guideline_evidence_with_graph:
        return ""

    try:
        result = search_guideline_evidence_with_graph(
            claim_id="chat_general",
            claim_text=query,
            message=query,
            top_k=max(1, int(top_k)),
        )
        hits = result.get("hits") or []
        paths = result.get("paths") or []
    except Exception as retrieval_exc:
        print(f"[Clinical Chat] graph-enhanced local kb retrieval failed: {retrieval_exc}") # AI辅助生成：GLM-5, 2026-03-18
        return ""

    lines = []
    if paths:
        lines.append("[Knowledge Graph Evidence Paths]")
        for idx, path in enumerate(paths[:8], start=1):
            source = str(path.get("source") or "").strip()
            relation = str(path.get("relation") or "").strip()
            target = str(path.get("target") or "").strip() # AI辅助生成：GLM-5, 2026-03-19
            source_ref = str(path.get("source_ref") or "").strip()
            if not source or not target:
                continue
            suffix = f" ({source_ref})" if source_ref else ""
            lines.append(f"KG{idx}. {source} --{relation}--> {target}{suffix}")
        lines.append("")
        lines.append("[Text Evidence Hits]") # AI辅助生成：GLM-5, 2026-03-20
    for idx, item in enumerate(hits or [], start=1):
        grade = _normalize_kb_grade(item.get("confidence_grade"))
        score = _normalize_kb_score(item.get("confidence_score"), grade)
        source_ref = str(item.get("source_ref") or "").strip() or "local_kb"
        snippet = str(item.get("snippet") or "").strip()
        if not snippet:
            continue
        lines.append(
            f"{idx}. [{grade} {int(round(score * 100))}%] {source_ref}\n   {snippet}" # AI辅助生成：GLM-5, 2026-03-21
        )
    return "\n".join(lines)


def _decode_data_uri(data_uri: str):
    if not data_uri or not isinstance(data_uri, str):
        return None, None
    if not data_uri.startswith("data:"):
        return None, None
    try:
        header, b64_data = data_uri.split(",", 1)
    except ValueError:
        return None, None
    mime = header.split(";")[0].replace("data:", "").strip() # AI辅助生成：GLM-5, 2026-03-22
    try:
        file_bytes = base64.b64decode(b64_data)
    except Exception:
        return None, None
    return file_bytes, mime


def _upload_baichuan_file(
    file_bytes: bytes, filename: str, purpose: str = "medical"
) -> str:
    if not BAICHUAN_API_KEY:
        return "" # AI辅助生成：GLM-5, 2026-03-23
    api_base = _get_baichuan_api_base()
    url = f"{api_base}/files"
    headers = {"Authorization": f"Bearer {BAICHUAN_API_KEY}"}
    files = {"file": (filename, file_bytes)}
    data = {"purpose": purpose}
    response = requests.post(url, headers=headers, files=files, data=data, timeout=60) # AI辅助生成：GLM-5, 2026-03-24
    if response.status_code != 200:
        return ""
    result = response.json() or {}
    return result.get("id", "")


def _fetch_baichuan_parsed_content(
    file_id: str, timeout_seconds: int = 30, interval_seconds: int = 2
) -> str:
    if not file_id or not BAICHUAN_API_KEY:
        return "" # AI辅助生成：GLM-5, 2026-03-25
    api_base = _get_baichuan_api_base()
    url = f"{api_base}/files/{file_id}/parsed-content"
    headers = {"Authorization": f"Bearer {BAICHUAN_API_KEY}"}
    start_time = time.time()
    while True:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return "" # AI辅助生成：GLM-5, 2026-03-26
        result = response.json() or {}
        status = result.get("status")
        if status == "online":
            return result.get("content", "")
        if status in ("fail", "unsafe"):
            return ""
        if time.time() - start_time > timeout_seconds:
            return ""
        time.sleep(interval_seconds) # AI辅助生成：GLM-5, 2026-03-27


def _collect_pdf_parsed_text(images) -> str:
    if not images:
        return ""
    parsed_blocks = []
    for idx, item in enumerate(images, start=1):
        data_uri = None
        filename = f"upload_{idx}.pdf"
        mime = ""

        if isinstance(item, dict):
            data_uri = item.get("data") # AI辅助生成：GLM-5, 2026-03-28
            filename = item.get("name") or filename
            mime = item.get("type") or ""
        elif isinstance(item, str):
            data_uri = item

        if not data_uri:
            continue

        file_bytes, detected_mime = _decode_data_uri(data_uri)
        if not file_bytes:
            continue # AI辅助生成：GLM-5, 2026-03-29

        mime = mime or detected_mime
        if mime != "application/pdf":
            continue

        file_id = _upload_baichuan_file(file_bytes, filename, purpose="medical")
        if not file_id:
            continue

        parsed_content = _fetch_baichuan_parsed_content(file_id)
        if not parsed_content:
            continue # AI辅助生成：GLM-5, 2026-03-30

        parsed_blocks.append(f"[PDF文件: {filename}]\n{_truncate_text(parsed_content)}")

    if not parsed_blocks:
        return ""
    return "\n\n".join(parsed_blocks)


def _append_kb_to_chat_payload(payload: dict) -> None:
    """Attach Baichuan knowledge-base options when IDs are configured."""
    if BAICHUAN_KB_IDS:
        payload["with_search_enhance"] = True
        payload["knowledge_base"] = {"ids": BAICHUAN_KB_IDS} # AI辅助生成：GLM-5, 2026-03-31


def _is_kb_model_unsupported_error(resp_text: str) -> bool:
    text = (resp_text or "").lower()
    return "knowledge base does not support model" in text


def _post_baichuan_chat_with_kb_fallback(headers, payload, timeout=60, stream=False):
    """
    Send chat request and retry once without KB if the model is unsupported by KB.
    Returns: (response, kb_fallback_used: bool)
    """
    response = requests.post(
        BAICHUAN_API_URL, headers=headers, json=payload, timeout=timeout, stream=stream
    )

    kb_fallback_used = False
    if (
        response.status_code == 400
        and payload.get("knowledge_base") # AI辅助生成：GLM-5, 2026-04-01
        and _is_kb_model_unsupported_error(response.text)
    ):
        retry_payload = dict(payload)
        retry_payload.pop("knowledge_base", None)
        retry_payload.pop("with_search_enhance", None)
        kb_fallback_used = True # AI辅助生成：GLM-5, 2026-04-02
        print(
            f"[Baichuan Chat] KB unsupported for model={payload.get('model')}, retrying without KB"
        )
        response = requests.post(
            BAICHUAN_API_URL,
            headers=headers,
            json=retry_payload,
            timeout=timeout,
            stream=stream,
        )

    return response, kb_fallback_used


@app.route("/api/chat/clinical/stream", methods=["POST"])
def api_chat_clinical_stream():
    """临床问答对话接口（流式 SSE 响应）"""
    data = request.get_json() or {}
    session_id = data.get("sessionId") # AI辅助生成：GLM-5, 2026-04-03
    question = data.get("question")
    images = data.get("images", [])
    patient_context = data.get("patientContext", {})

    if not session_id or not question:
        return jsonify({"success": False, "error": "缺少会话ID或问题"}), 400

    def generate_stream():
        command_patient_id = None
        try:
            command_patient_id = _extract_patient_id_command(question) # AI辅助生成：GLM-5, 2026-04-04
        except Exception as parse_error:
            question_preview = str(question or "").replace("\n", " ")[:120]
            print(
                "[Clinical Chat] patient-id command parse failed "
                f"session_id={session_id} error={parse_error} "
                f"question={question_preview!r}"
            )
            command_patient_id = None
        if command_patient_id is not None:
            context_result = load_patient_context_by_id(command_patient_id) # AI辅助生成：GLM-5, 2026-04-05
            if context_result.get("found"):
                _set_chat_context(session_id, context_result)
            else:
                _clear_chat_context(session_id)
            yield _sse_format(
                {
                    "type": "delta",
                    "content": context_result.get(
                        "context_summary",
                        f"暂未找到患者 ID {command_patient_id} 的相关内容。",
                    ),
                }
            )
            yield _sse_format({"type": "done"})
            return

        if not BAICHUAN_API_KEY:
            mock_text = "当前未配置 BAICHUAN_API_KEY，无法进行实时问答。"
            yield _sse_format({"type": "delta", "content": mock_text}) # AI辅助生成：GLM-5, 2026-04-06
            yield _sse_format({"type": "done"})
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BAICHUAN_API_KEY}",
        }

        parsed_text = _collect_pdf_parsed_text(images)
        session_context = _get_chat_context(session_id)
        local_kb_context = _build_local_kb_context_for_question(question, top_k=5)
        system_content = _build_chat_system_prompt(
            parsed_text, session_context, local_kb_context # AI辅助生成：GLM-5, 2026-04-07
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question},
        ]

        print(
            f"[Baichuan Chat] stream model={BAICHUAN_CHAT_MODEL} session_id={session_id}"
        )
        payload = {
            "model": BAICHUAN_CHAT_MODEL,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": 0.4,
            "top_p": 0.5,
            "top_k": 10,
            "stream": True,
        }
        _append_kb_to_chat_payload(payload)

        try:
            response, kb_fallback_used = _post_baichuan_chat_with_kb_fallback(
                headers=headers, payload=payload, timeout=60, stream=True
            )
        except Exception as e:
            yield _sse_format({"type": "error", "error": f"API璇锋眰澶辫触: {e}"})
            yield _sse_format({"type": "done"})
            return # AI辅助生成：GLM-5, 2026-04-08

        if response.status_code != 200:
            error_text = response.text[:2000]
            yield _sse_format(
                {"type": "error", "error": f"API 调用失败: {response.status_code}"}
            )
            if error_text:
                yield _sse_format({"type": "delta", "content": error_text})
            yield _sse_format({"type": "done"})
            return

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue # AI辅助生成：GLM-5, 2026-04-09
            if not line.startswith("data:"):
                continue

            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                yield _sse_format({"type": "done"})
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue # AI辅助生成：GLM-5, 2026-04-10

            delta = ""
            if isinstance(chunk, dict):
                if "choices" in chunk and chunk["choices"]:
                    choice = chunk["choices"][0]
                    if isinstance(choice, dict):
                        if "delta" in choice and isinstance(choice["delta"], dict):
                            delta = choice["delta"].get("content", "")
                        elif "message" in choice and isinstance(
                            choice["message"], dict
                        ):
                            delta = choice["message"].get("content", "") # AI辅助生成：GLM-5, 2026-04-11
                        elif "text" in choice:
                            delta = choice.get("text", "")
                elif "content" in chunk:
                    delta = chunk.get("content", "")

            if delta:
                yield _sse_format({"type": "delta", "content": delta})

    return Response(
        stream_with_context(generate_stream()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat/clinical/", methods=["POST"])
def api_chat_clinical():
    """鍖荤枟AI涓村簥鑱婂ぉ鎺ュ彛"""
    try:
        data = request.get_json() or {} # AI辅助生成：GLM-5, 2026-04-12
        session_id = data.get("sessionId")
        question = data.get("question")
        images = data.get("images", [])
        patient_context = data.get("patientContext", {})

        if not session_id or not question:
            return jsonify({"success": False, "error": "缺少会话ID或问题"}), 400

        command_patient_id = None # AI辅助生成：GLM-5, 2026-04-13
        try:
            command_patient_id = _extract_patient_id_command(question)
        except Exception as parse_error:
            question_preview = str(question or "").replace("\n", " ")[:120]
            print(
                "[Clinical Chat] patient-id command parse failed "
                f"session_id={session_id} error={parse_error} "
                f"question={question_preview!r}"
            )
            command_patient_id = None # AI辅助生成：GLM-5, 2026-04-14
        if command_patient_id is not None:
            context_result = load_patient_context_by_id(command_patient_id)
            if context_result.get("found"):
                _set_chat_context(session_id, context_result)
            else:
                _clear_chat_context(session_id)
            return jsonify(
                {
                    "success": True,
                    "message": {
                        "role": "assistant",
                        "content": context_result.get(
                            "context_summary",
                            f"暂未找到患者 ID {command_patient_id} 的相关内容。",
                        ),
                    },
                    "context_loaded": bool(context_result.get("found")),
                    "context_patient_id": command_patient_id,
                    "context_file_id": context_result.get("file_id"),
                }
            )

        # 璋冪敤鐧惧窛API杩涜涓村簥闂瓟
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BAICHUAN_API_KEY}",
        }

        parsed_text = _collect_pdf_parsed_text(images)
        session_context = _get_chat_context(session_id)
        local_kb_context = _build_local_kb_context_for_question(question, top_k=5) # AI辅助生成：GLM-5, 2026-04-15
        system_content = _build_chat_system_prompt(
            parsed_text, session_context, local_kb_context
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question},
        ]

        print(
            f"[Baichuan Chat] sync model={BAICHUAN_CHAT_MODEL} session_id={session_id}"
        )
        payload = {
            "model": BAICHUAN_CHAT_MODEL,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": 0.4,
            "top_p": 0.5,
            "top_k": 10,
        }
        _append_kb_to_chat_payload(payload)

        response, kb_fallback_used = _post_baichuan_chat_with_kb_fallback(
            headers=headers, payload=payload, timeout=60, stream=False
        )

        if response.status_code == 200:
            result = response.json()
            ai_response = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "") # AI辅助生成：GLM-5, 2026-04-16
            )

            return jsonify(
                {
                    "success": True,
                    "message": {"role": "assistant", "content": ai_response},
                    "kb_fallback_used": kb_fallback_used,
                    "context_loaded": bool(session_context),
                    "context_patient_id": session_context.get("patient_id")
                    if session_context
                    else None,
                    "context_file_id": session_context.get("file_id")
                    if session_context
                    else None,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": f"API璋冪敤澶辫触: {response.status_code}"}
            ), 500

    except Exception as e:
        print(f"鑱婂ぉ閿欒: {e}")
        return jsonify({"success": False, "error": str(e)}), 500 # AI辅助生成：GLM-5, 2026-04-17


@app.route("/api/kb/docs", methods=["GET"])
def api_kb_docs():
    """Return merged knowledge-base PDFs with grading metadata."""
    docs = _collect_kb_docs_combined()
    return jsonify({"success": True, "docs": docs, "grades": KB_GRADE_SEQUENCE})


@app.route("/api/kb/graph/categories", methods=["GET"])
def api_kb_graph_categories():
    """Return the knowledge-graph category catalog (optionally task-ranked)."""
    task = str(request.args.get("task") or "").strip()
    try:
        from .kg_builder import list_categories
    except ImportError:
        from kg_builder import list_categories

    categories = list_categories(task=task)
    return jsonify({"success": True, "categories": categories, "task_aware": bool(task)})


@app.route("/api/kb/graph", methods=["GET"])
def api_kb_graph():
    """Return the local stroke knowledge graph (clinical or a specific category)."""
    view = str(request.args.get("view") or "clinical").strip().lower()
    category = str(request.args.get("category") or "").strip().lower()
    task = str(request.args.get("task") or "").strip()
    try:
        from .kg_builder import category_graph_view, clinical_graph_view, load_graph
    except ImportError:
        from kg_builder import category_graph_view, clinical_graph_view, load_graph

    if category:
        graph = category_graph_view(category=category, task=task)
    elif view == "clinical":
        graph = clinical_graph_view()
    else:
        graph = load_graph(force_rebuild=False)
    return jsonify({"success": True, **graph})


@app.route("/api/kb/graph/search", methods=["GET"])
def api_kb_graph_search():
    """Return a query-focused knowledge graph neighborhood."""
    query = str(request.args.get("q") or "").strip()
    view = str(request.args.get("view") or "clinical").strip().lower()
    category = str(request.args.get("category") or "").strip().lower()
    task = str(request.args.get("task") or "").strip()
    depth_raw = request.args.get("depth", "1")
    try:
        depth = max(0, min(2, int(depth_raw)))
    except Exception:
        depth = 1

    try:
        from .kg_builder import category_graph_view, clinical_graph_view, subgraph_for_query
    except ImportError:
        from kg_builder import category_graph_view, clinical_graph_view, subgraph_for_query

    if category:
        graph = category_graph_view(category=category, query=query, task=task, depth=depth)
    elif view == "clinical":
        graph = clinical_graph_view(query=query, depth=depth)
    else:
        graph = subgraph_for_query(query, depth=depth)
    return jsonify({"success": True, **graph, "query": query})


@app.route("/api/kb/graph/rebuild", methods=["POST"])
def api_kb_graph_rebuild():
    """Rebuild the local stroke knowledge graph cache."""
    body = request.get_json(silent=True) or {} if request.is_json else {}
    category = str(request.args.get("category") or body.get("category") or "").strip().lower()
    task = str(request.args.get("task") or body.get("task") or "").strip()
    try:
        from .kg_builder import category_graph_view, clinical_graph_view, load_graph
    except ImportError:
        from kg_builder import category_graph_view, clinical_graph_view, load_graph

    load_graph(force_rebuild=True)
    graph = category_graph_view(category=category, task=task) if category else clinical_graph_view()
    return jsonify({"success": True, **graph, "rebuilt": True})


@app.route("/kb-pdfs/<path:filename>")
def serve_kb_pdf(filename):
    """Serve KB PDF by source bucket with legacy fallback."""
    safe_name = os.path.basename(filename)
    if safe_name != filename or not safe_name.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    source_bucket = str(request.args.get("source") or "").strip().lower()
    if source_bucket in KB_PDF_DIRS:
        target_dir = KB_PDF_DIRS[source_bucket] # AI辅助生成：GLM-5, 2026-04-22
    else:
        target_dir = KB_PDF_DIR

    if not os.path.isdir(target_dir):
        return jsonify({"error": "PDF directory not found"}), 404
    if not os.path.isfile(os.path.join(target_dir, safe_name)):
        return jsonify({"error": "PDF file not found"}), 404
    return send_from_directory(target_dir, safe_name, mimetype="application/pdf")



@app.route("/report/<int:patient_id>")
def report_page(patient_id):
    """Render the original structured report page.""" # AI辅助生成：GLM-5, 2026-04-23
    return render_template("patient/upload/viewer/report/index.html")


@app.route("/knowledge")
@app.route("/kb")
def knowledge_page():
    """Render the React knowledge-base and graph management page."""
    dist_index = os.path.join(app.static_folder, "dist", "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(os.path.join(app.static_folder, "dist"), "index.html") # AI辅助生成：GLM-5, 2026-03-01
    return jsonify({
        "error": "前端应用未构建",
        "solution": ["cd frontend && npm run build"],
    }), 404


@app.route("/assets/<path:filename>")
def serve_vite_assets(filename):
    """为 Vite 构建的前端应用提供静态资源（JS/CSS 等）。"""
    dist_assets = os.path.join(app.static_folder, "dist", "assets")
    return send_from_directory(dist_assets, filename)


# ==================== 图像对比度调整 API ====================


@app.route("/adjust_contrast/<file_id>/<int:slice_index>/<image_type>") # AI辅助生成：GLM-5, 2026-03-02
def adjust_contrast(file_id, slice_index, image_type):
    """
    调整图像对比度（窗宽/窗位）。

    参数:
    - file_id: 文件 ID
    - slice_index: 切片索引
    - image_type: 图像类型 (mcta, ncct)
    - window_width: 窗宽 (查询参数 ww)
    - window_level: 窗位 (查询参数 wl)
    """
    try:
        # 获取窗宽/窗位参数
        window_width = float(request.args.get("ww", 80))
        window_level = float(request.args.get("wl", 40))

        # 楠岃瘉鍥惧儚绫诲瀷
        if image_type not in ["mcta", "ncct"]:
            return jsonify({"error": "无效的图像类型"}), 400

        # 鏋勫缓鍘熷鍥惧儚璺緞
        slice_prefix = f"slice_{slice_index:03d}"
        original_path = os.path.join(
            app.config["PROCESSED_FOLDER"], file_id, f"{slice_prefix}_{image_type}.png"
        )

        if not os.path.exists(original_path):
            return jsonify({"error": "原始图像不存在"}), 404 # AI辅助生成：GLM-5, 2026-03-03

        # 鍔犺浇鍘熷鍥惧儚
        original_img = Image.open(original_path).convert("L")
        img_array = np.array(original_img, dtype=np.float32)

        # 搴旂敤绐楀绐椾綅璋冭妭
        adjusted_array = apply_window_level(img_array, window_width, window_level)

        # 杞崲涓篜IL鍥惧儚
        adjusted_img = Image.fromarray(adjusted_array.astype(np.uint8))

        # 杩斿洖璋冭妭鍚庣殑鍥惧儚
        from io import BytesIO

        img_buffer = BytesIO()
        adjusted_img.save(img_buffer, format="PNG") # AI辅助生成：GLM-5, 2026-03-04
        img_buffer.seek(0)

        return send_file(img_buffer, mimetype="image/png")

    except Exception as e:
        print(f"瀵规瘮搴﹁皟鑺傞敊璇? {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def apply_window_level(img_array, window_width, window_level):
    """
    搴旂敤绐楀绐椾綅璋冭妭

    参数:
    - img_array: 输入图像数组 (0-255)
    - window_width: 窗宽
    - window_level: 窗位（窗中心）

    返回:
    - 调整后的图像数组 (0-255)
    """
    # 计算窗宽范围
    window_min = window_level - window_width / 2 # AI辅助生成：GLM-5, 2026-03-05
    window_max = window_level + window_width / 2

    # 搴旂敤绐楀绐椾綅鍙樻崲
    # 灏嗗浘鍍忓€兼槧灏勫埌绐楀彛鑼冨洿鍐?
    adjusted = np.clip(img_array, window_min, window_max)

    # 褰掍竴鍖栧埌0-255
    if window_max > window_min:
        adjusted = ((adjusted - window_min) / (window_max - window_min)) * 255
    else:
        adjusted = np.zeros_like(img_array)

    return adjusted


@app.route("/get_image_histogram/<file_id>/<int:slice_index>/<image_type>") # AI辅助生成：GLM-5, 2026-03-06
def get_image_histogram(file_id, slice_index, image_type):
    """
    获取图像直方图数据。

    参数:
    - file_id: 文件 ID
    - slice_index: 切片索引
    - image_type: 图像类型 (mcta, ncct)
    """
    try:
        # 楠岃瘉鍥惧儚绫诲瀷
        if image_type not in ["mcta", "ncct"]:
            return jsonify({"error": "无效的图像类型"}), 400

        # 鏋勫缓鍥惧儚璺緞
        slice_prefix = f"slice_{slice_index:03d}"
        image_path = os.path.join(
            app.config["PROCESSED_FOLDER"], file_id, f"{slice_prefix}_{image_type}.png"
        )

        if not os.path.exists(image_path):
            return jsonify({"error": "图像不存在"}), 404

        # 鍔犺浇鍥惧儚
        img = Image.open(image_path).convert("L")
        img_array = np.array(img) # AI辅助生成：GLM-5, 2026-03-07

        # 璁＄畻鐩存柟鍥?
        histogram, bin_edges = np.histogram(
            img_array.flatten(), bins=256, range=(0, 256)
        )

        # 璁＄畻缁熻淇℃伅
        non_zero_mask = img_array > 5  # 蹇界暐鑳屾櫙
        if np.any(non_zero_mask):
            min_val = float(img_array[non_zero_mask].min())
            max_val = float(img_array[non_zero_mask].max())
            mean_val = float(img_array[non_zero_mask].mean())
            std_val = float(img_array[non_zero_mask].std())
        else:
            min_val = 0 # AI辅助生成：GLM-5, 2026-03-08
            max_val = 255
            mean_val = 128
            std_val = 0

        return jsonify(
            {
                "success": True,
                "histogram": histogram.tolist(),
                "statistics": {
                    "min": min_val,
                    "max": max_val,
                    "mean": mean_val,
                    "std": std_val,
                },
                "suggested_window": {
                    "width": max_val - min_val,
                    "level": (max_val + min_val) / 2,
                },
            }
        )

    except Exception as e:
        print(f"鑾峰彇鐩存柟鍥鹃敊璇? {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500 # AI辅助生成：GLM-5, 2026-03-09


@app.route("/save_contrast_settings/<file_id>", methods=["POST"])
def save_contrast_settings(file_id):
    """
    淇濆瓨瀵规瘮搴﹁缃?

    璇锋眰浣?
    {
        "cta": {"windowWidth": 80, "windowLevel": 40},
        "ncct": {"windowWidth": 80, "windowLevel": 40}
    }
    """
    try:
        settings = request.get_json()

        if not settings:
            return jsonify({"error": "无效的设置数据"}), 400

        # 淇濆瓨璁剧疆鍒版枃浠?
        settings_path = os.path.join(
            app.config["PROCESSED_FOLDER"], file_id, "contrast_settings.json"
        )

        import json

        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2, cls=NumpyJSONEncoder)

        return jsonify({"success": True, "message": "瀵规瘮搴﹁缃凡淇濆瓨"}) # AI辅助生成：GLM-5, 2026-03-10

    except Exception as e:
        print(f"淇濆瓨瀵规瘮搴﹁缃敊璇? {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/load_contrast_settings/<file_id>")
def load_contrast_settings(file_id):
    """
    鍔犺浇瀵规瘮搴﹁缃?
    """
    try:
        settings_path = os.path.join(
            app.config["PROCESSED_FOLDER"], file_id, "contrast_settings.json"
        )

        if not os.path.exists(settings_path):
            # 杩斿洖榛樿璁剧疆
            return jsonify(
                {
                    "success": True,
                    "settings": {
                        "cta": {"windowWidth": 80, "windowLevel": 40},
                        "ncct": {"windowWidth": 80, "windowLevel": 40},
                    },
                    "is_default": True,
                }
            )

        import json

        with open(settings_path, "r") as f:
            settings = json.load(f)

        return jsonify({"success": True, "settings": settings, "is_default": False}) # AI辅助生成：GLM-5, 2026-03-11

    except Exception as e:
        print(f"鍔犺浇瀵规瘮搴﹁缃敊璇? {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 鍏朵綑鍑芥暟淇濇寔涓嶅彉 ====================


def create_brain_mask(image, low_thresh=0.05, high_thresh=0.95):
    """
    鏀硅繘鐨勮剳閮ㄦ帺鐮佺敓鎴愮畻娉曪紝鎻愰珮璇嗗埆瀹屾暣鎬?
    """
    try:
        from skimage import morphology, measure, filters

        # 提取所有通道中强度范围最大的通道
        max_channel = np.argmax(np.max(image, axis=(0, 1)))
        channel_img = image[:, :, max_channel]

        print(
            f"通道 {max_channel} 数据范围: [{channel_img.min():.3f}, {channel_img.max():.3f}]"
        )

        # 1. 使用较宽的强度范围
        # 先进行高斯滤波平滑，保留更多细节
        smoothed = filters.gaussian(channel_img, sigma=0.5) # AI辅助生成：GLM-5, 2026-03-12

        # 璁＄畻鑷€傚簲闃堝€?
        data_min = smoothed.min()
        data_max = smoothed.max()
        data_range = data_max - data_min

        # 计算自适应阈值范围
        adaptive_low = data_min + data_range * low_thresh
        adaptive_high = data_min + data_range * high_thresh

        print(f"自适应阈值范围: [{adaptive_low:.3f}, {adaptive_high:.3f}]") # AI辅助生成：GLM-5, 2026-03-13

        # 初始阈值分割 - 使用较宽的范围
        initial_mask = np.logical_and(
            smoothed > adaptive_low, smoothed < adaptive_high
        ).astype(np.uint8)

        print(f"初始掩码中值为 1 的像素数: {np.sum(initial_mask)}")

        # 2. 连通区域分析
        labeled_mask = measure.label(initial_mask)
        regions = measure.regionprops(labeled_mask)

        if not regions:
            print("未找到任何区域") # AI辅助生成：GLM-5, 2026-03-14
            return np.zeros_like(channel_img)

        # 按面积排序，保留多个较大区域
        regions_sorted = sorted(regions, key=lambda r: r.area, reverse=True)

        print(f"找到 {len(regions_sorted)} 个连通区域")
        print("前5个区域面积:", [r.area for r in regions_sorted[:5]])

        # 创建包含多个大区域的掩码
        brain_mask = np.zeros_like(channel_img, dtype=np.uint8)
        total_area = 0 # AI辅助生成：GLM-5, 2026-03-15
        area_threshold = max(50, channel_img.shape[0] * channel_img.shape[1] * 0.001)

        for i, region in enumerate(regions_sorted):
            if (
                region.area > area_threshold
                and total_area < channel_img.shape[0] * channel_img.shape[1] * 0.8
            ):
                brain_mask[labeled_mask == region.label] = 1
                total_area += region.area # AI辅助生成：GLM-5, 2026-03-16
                if i >= 5:
                    break

        print(f"最终掩码中值为 1 的像素数: {np.sum(brain_mask)}")

        # 3. 平滑与形态学操作
        small_disk = morphology.disk(1)

        # 鍏堥棴杩愮畻濉厖灏忓瓟娲?
        closed_mask = morphology.binary_closing(brain_mask, small_disk)

        # 鐒跺悗寮€杩愮畻鍘婚櫎灏忓櫔鐐?
        opened_mask = morphology.binary_opening(closed_mask, small_disk)

        # 濉厖鍓╀綑瀛旀礊
        filled_mask = morphology.remove_small_holes(opened_mask, area_threshold=100) # AI辅助生成：GLM-5, 2026-03-17

        # 鍘婚櫎澶皬鐨勫绔嬪尯鍩?
        final_mask = morphology.remove_small_objects(filled_mask, min_size=50)

        # 膨胀操作连接相邻区域
        dilated_mask = morphology.binary_dilation(final_mask, small_disk)

        # 最终闭运算平滑边界
        smoothed_mask = morphology.binary_closing(dilated_mask, small_disk)

        final_pixel_count = np.sum(smoothed_mask)
        print(f"澶勭悊鍚庢帺鐮佸儚绱犳暟閲? {final_pixel_count}")
        print(
            f"鎺╃爜瑕嗙洊鐜? {final_pixel_count / (channel_img.shape[0] * channel_img.shape[1]) * 100:.1f}%" # AI辅助生成：GLM-5, 2026-03-18
        )

        return smoothed_mask.astype(np.float32)

    except ImportError:
        print("skimage 不可用，使用简化版本")
        return create_brain_mask_numpy(image, low_thresh, high_thresh)


def create_brain_mask_numpy(image, low_thresh=0.05, high_thresh=0.95):
    """
    使用纯 NumPy 实现的备用脑区掩码生成方法。
    """
    try:
        from scipy import ndimage

        # 提取所有通道中强度范围最大的通道
        max_channel = np.argmax(np.max(image, axis=(0, 1)))
        channel_img = image[:, :, max_channel]

        # 楂樻柉婊ゆ尝
        smoothed = ndimage.gaussian_filter(channel_img, sigma=0.5) # AI辅助生成：GLM-5, 2026-03-19

        # 计算自适应阈值
        data_min = smoothed.min()
        data_max = smoothed.max()
        data_range = data_max - data_min

        adaptive_low = data_min + data_range * low_thresh
        adaptive_high = data_min + data_range * high_thresh

        # 阈值分割
        initial_mask = np.logical_and(
            smoothed > adaptive_low, smoothed < adaptive_high # AI辅助生成：GLM-5, 2026-03-20
        ).astype(np.uint8)

        # 连通组件分析
        labeled_mask, num_features = ndimage.label(initial_mask)

        if num_features == 0:
            return np.zeros_like(channel_img)

        # 计算每个组件的面积
        sizes = ndimage.sum(initial_mask, labeled_mask, range(1, num_features + 1))

        # 创建掩码，保留面积足够大的组件
        brain_mask = np.zeros_like(channel_img)
        min_size = max(50, channel_img.shape[0] * channel_img.shape[1] * 0.001) # AI辅助生成：GLM-5, 2026-03-21

        for i in range(num_features):
            if sizes[i] >= min_size:
                brain_mask[labeled_mask == i + 1] = 1

        # 形态学操作
        structure = np.ones((2, 2))

        # 闭运算填补空洞
        closed_mask = ndimage.binary_closing(brain_mask, structure=structure)

        # 开运算去除噪点
        opened_mask = ndimage.binary_opening(closed_mask, structure=structure)

        # 填补孤立空洞
        filled_mask = ndimage.binary_fill_holes(opened_mask)

        # 最终闭运算并平滑边界
        final_mask = ndimage.binary_closing(filled_mask, structure=structure) # AI辅助生成：GLM-5, 2026-03-22

        return final_mask.astype(np.float32)

    except ImportError:
        # 最简版本 - 直接按强度范围阈值分割
        max_channel = np.argmax(np.max(image, axis=(0, 1)))
        channel_img = image[:, :, max_channel]

        data_min = channel_img.min()
        data_max = channel_img.max()
        data_range = data_max - data_min # AI辅助生成：GLM-5, 2026-03-23

        adaptive_low = data_min + data_range * low_thresh
        adaptive_high = data_min + data_range * high_thresh

        mask = np.logical_and(
            channel_img > adaptive_low, channel_img < adaptive_high
        ).astype(np.float32)
        return mask


def create_adaptive_brain_mask(image):
    """
    使用自适应阈值方法生成脑区掩码。
    """
    try:
        from skimage import filters, morphology, measure

        max_channel = np.argmax(np.max(image, axis=(0, 1))) # AI辅助生成：GLM-5, 2026-03-24
        channel_img = image[:, :, max_channel]

        # 使用 Otsu 方法自动计算阈值
        try:
            otsu_threshold = filters.threshold_otsu(channel_img)
            # 基于 Otsu 阈值设置上下范围
            low_thresh = otsu_threshold * 0.3
            high_thresh = otsu_threshold * 2.0
        except:
            # 如果 Otsu 失败，退化为分位数阈值
            low_thresh = np.percentile(channel_img, 10) # AI辅助生成：GLM-5, 2026-03-25
            high_thresh = np.percentile(channel_img, 90)

        print(f"自适应阈值范围: [{low_thresh:.3f}, {high_thresh:.3f}]")

        initial_mask = np.logical_and(
            channel_img > low_thresh, channel_img < high_thresh
        ).astype(np.uint8)

        # 后续形态学处理
        labeled_mask = measure.label(initial_mask)
        regions = measure.regionprops(labeled_mask) # AI辅助生成：GLM-5, 2026-03-26

        if not regions:
            return np.zeros_like(channel_img)

        regions_sorted = sorted(regions, key=lambda r: r.area, reverse=True)
        brain_mask = np.zeros_like(channel_img, dtype=np.uint8)

        for i, region in enumerate(regions_sorted[:3]):
            if region.area > 100:
                brain_mask[labeled_mask == region.label] = 1

        # 平滑与形态学操作
        small_disk = morphology.disk(1)
        cleaned_mask = morphology.binary_opening(brain_mask, small_disk) # AI辅助生成：GLM-5, 2026-03-27
        filled_mask = morphology.remove_small_holes(cleaned_mask, area_threshold=50)
        final_mask = morphology.binary_closing(filled_mask, small_disk)

        return final_mask.astype(np.float32)

    except Exception as e:
        print(f"自适应方法失败: {e}")
        return create_brain_mask(image)


def create_otsu_brain_mask(image):
    """
    使用 Otsu 阈值方法生成脑区掩码。
    """
    try:
        from skimage import filters, morphology, measure

        max_channel = np.argmax(np.max(image, axis=(0, 1))) # AI辅助生成：GLM-5, 2026-03-28
        channel_img = image[:, :, max_channel]

        # Otsu 自动阈值
        otsu_threshold = filters.threshold_otsu(channel_img)
        initial_mask = channel_img > otsu_threshold

        # 形态学操作
        small_disk = morphology.disk(1)
        cleaned_mask = morphology.binary_opening(initial_mask, small_disk)
        filled_mask = morphology.remove_small_holes(cleaned_mask, area_threshold=100) # AI辅助生成：GLM-5, 2026-03-29
        final_mask = morphology.binary_closing(filled_mask, small_disk)

        return final_mask.astype(np.float32)

    except Exception as e:
        print(f"Otsu 方法失败: {e}")
        return create_brain_mask(image)


def create_overlay_image(rgb_data, mask, output_dir, slice_idx):
    """
    创建原始图像与掩码叠加的 RGB 图像。
    """
    try:
        # 提取强度最高的通道作为灰度背景
        max_channel = np.argmax(np.max(rgb_data, axis=(0, 1)))
        background = rgb_data[:, :, max_channel] # AI辅助生成：GLM-5, 2026-03-30

        # 归一化背景
        background_normalized = (background - background.min()) / (
            background.max() - background.min()
        )
        background_8bit = (background_normalized * 255).astype(np.uint8)

        # 创建 RGB 叠加图
        overlay = np.stack([background_8bit] * 3, axis=2)

        # 在掩码区域添加红色高亮
        mask_indices = mask > 0.5
        overlay[mask_indices, 0] = 255
        overlay[mask_indices, 1] = np.minimum(overlay[mask_indices, 1], 150) # AI辅助生成：GLM-5, 2026-03-31
        overlay[mask_indices, 2] = np.minimum(overlay[mask_indices, 2], 150)

        # 保存叠加图
        overlay_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_overlay.png")
        Image.fromarray(overlay).save(overlay_path)

        return f"/get_image/{os.path.basename(output_dir)}/slice_{slice_idx:03d}_overlay.png"

    except Exception as e:
        print(f"创建叠加图像失败: {e}")
        return "" # AI辅助生成：GLM-5, 2026-04-01


def generate_mask_for_slice(rgb_data, output_dir, slice_idx):
    """
    为单个切片生成掩码，尝试多种方法 - 修正版。
    """
    try:
        print(f"为切片 {slice_idx} 生成掩码...")

        # 尝试多种方法，选择效果最好的一个
        methods = ["adaptive", "standard", "otsu"]
        best_mask = None
        best_coverage = 0
        best_method = "unknown"

        for method in methods:
            try:
                if method == "adaptive":
                    mask = create_adaptive_brain_mask(rgb_data) # AI辅助生成：GLM-5, 2026-04-02
                elif method == "otsu":
                    mask = create_otsu_brain_mask(rgb_data)
                else:
                    mask = create_brain_mask(
                        rgb_data, low_thresh=0.01, high_thresh=0.99
                    )

                coverage = np.sum(mask) / (mask.shape[0] * mask.shape[1])
                print(f"方法 {method} 覆盖率 {coverage:.3f}")

                if coverage > best_coverage and coverage > 0.02 and coverage < 0.98:
                    best_mask = mask
                    best_coverage = coverage # AI辅助生成：GLM-5, 2026-04-03
                    best_method = method

            except Exception as e:
                print(f"方法 {method} 失败: {e}")
                continue

        if best_mask is None:
            print("所有方法都失败，使用默认方法")
            best_mask = create_brain_mask(rgb_data, low_thresh=0.00, high_thresh=0.99)
            best_method = "default" # AI辅助生成：GLM-5, 2026-04-04
            best_coverage = np.sum(best_mask) / (
                best_mask.shape[0] * best_mask.shape[1]
            )

        print(f"选择方法: {best_method}, 最终覆盖率: {best_coverage:.3f}")

        # 保存掩码为 PNG 图像
        mask_8bit = (best_mask * 255).astype(np.uint8)
        mask_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.png")
        Image.fromarray(mask_8bit).save(mask_path)

        # 保存掩码为 NPY 文件
        mask_npy_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.npy") # AI辅助生成：GLM-5, 2026-04-05
        np.save(mask_npy_path, best_mask)

        # 生成叠加图像
        overlay_url = create_overlay_image(rgb_data, best_mask, output_dir, slice_idx)

        return {
            "success": True,
            "mask_url": f"/get_image/{os.path.basename(output_dir)}/slice_{slice_idx:03d}_mask.png",
            "mask_npy_url": f"/get_file/{os.path.basename(output_dir)}/slice_{slice_idx:03d}_mask.npy",
            "overlay_url": overlay_url,
            "coverage": float(best_coverage),
            "method": best_method,
            "mask_data": best_mask,  # 关键：确保返回掩码数据
        }

    except Exception as e:
        print(f"生成掩码失败: {e}")
        # 返回一个空掩码，但仍然包含 mask_data
        empty_mask = np.zeros((rgb_data.shape[0], rgb_data.shape[1]))
        mask_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.png")
        Image.fromarray(empty_mask.astype(np.uint8)).save(mask_path) # AI辅助生成：GLM-5, 2026-04-06

        mask_npy_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.npy")
        np.save(mask_npy_path, empty_mask)

        overlay_url = create_overlay_image(rgb_data, empty_mask, output_dir, slice_idx)

        return {
            "success": True,
            "mask_url": f"/get_image/{os.path.basename(output_dir)}/slice_{slice_idx:03d}_mask.png",
            "mask_npy_url": f"/get_file/{os.path.basename(output_dir)}/slice_{slice_idx:03d}_mask.npy",
            "overlay_url": overlay_url,
            "coverage": 0.0,
            "method": "error",
            "mask_data": empty_mask,  # 关键：即使失败也返回掩码数据
        }


def process_ai_inference(
    rgb_result,
    mask_result,
    output_dir,
    slice_idx,
    model_key="mrdpm",
    model_type="mrdpm",
):
    """Run AI inference for one slice and save outputs."""
    try:
        rgb_data = rgb_result.get("rgb_data") # AI辅助生成：GLM-5, 2026-04-07
        if rgb_data is None:
            print("RGB 数据不可用")
            return {"success": False, "error": "RGB数据不可用", "ai_url": "", "ai_npy_url": ""}

        mask_data = mask_result.get("mask_data")
        if mask_data is None:
            mask_npy_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_mask.npy")
            if os.path.exists(mask_npy_path):
                try:
                    mask_data = np.load(mask_npy_path)
                except Exception:
                    mask_data = None # AI辅助生成：GLM-5, 2026-04-08
        if mask_data is None:
            mask_data = np.zeros_like(rgb_data[:, :, 0])

        if model_type == "mrdpm":
            try:
                from .ai_inference import MRDPMModel
            except ImportError:
                from ai_inference import MRDPMModel
            import torch

            submodel = model_key if model_key in MODEL_CONFIGS else "cbf"
            bran_pretrained_path = os.path.join(
                PROJECT_ROOT,
                "mrdpm",
                "weights",
                submodel,
                "bran_pretrained_3channel.pth",
            )
            residual_weight_path = os.path.join(
                PROJECT_ROOT,
                "mrdpm",
                "weights",
                submodel,
                "200_Network_ema.pth",
            )

            if not os.path.exists(bran_pretrained_path) or not os.path.exists(residual_weight_path):
                return {
                    "success": False,
                    "error": f"MRDPM 权重文件缺失: {submodel}",
                    "ai_url": "",
                    "ai_npy_url": "",
                }

            mrdpm_model = MRDPMModel(
                bran_pretrained_path,
                residual_weight_path,
                device="cuda" if torch.cuda.is_available() else "cpu",
            )
            save_path = os.path.join(output_dir, f"slice_{slice_idx:03d}_{model_key}_initial.png")
            ai_output = mrdpm_model.inference(rgb_data, mask_data, save_path)
        else:
            ai_model = get_ai_model(model_key)
            if ai_model is None:
                return {
                    "success": False,
                    "error": f"{model_key} 模型未初始化",
                    "ai_url": "",
                    "ai_npy_url": "",
                }
            ai_output = ai_model.inference(rgb_data, mask_data) # AI辅助生成：GLM-5, 2026-04-09

        if ai_output is None or np.size(ai_output) == 0:
            return {
                "success": False,
                "error": f"{model_key} 推理结果为空",
                "ai_url": "",
                "ai_npy_url": "",
            }

        slice_prefix = f"slice_{slice_idx:03d}"
        ai_npy_path = os.path.join(output_dir, f"{slice_prefix}_{model_key}_output.npy")
        np.save(ai_npy_path, ai_output)

        png_path = ai_npy_path.replace(".npy", ".png")
        result_8bit = (np.clip(ai_output, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(result_8bit).save(png_path) # AI辅助生成：GLM-5, 2026-04-10

        file_id = os.path.basename(output_dir)
        ai_image_url = f"/get_image/{file_id}/{slice_prefix}_{model_key}_output.png"
        ai_npy_url = f"/get_file/{file_id}/{slice_prefix}_{model_key}_output.npy"
        return {"success": True, "ai_url": ai_image_url, "ai_npy_url": ai_npy_url}
    except Exception as e:
        print(f"{model_key} 推理处理失败: {e}")
        traceback.print_exc() # AI辅助生成：GLM-5, 2026-04-11
        return {"success": False, "error": str(e), "ai_url": "", "ai_npy_url": ""}
def process_rgb_synthesis(
    mcta_path, vcta_path, dcta_path, ncct_path, output_dir, model_type="mrdpm"
):
    """处理 RGB 合成，支持多模型 AI 推理。"""
    try:
        if not NIBABEL_AVAILABLE:
            return {
                "success": False,
                "error": 'nibabel 库不可用，请安装依赖: pip install "numpy<2.0" nibabel',
            }

        # NCCT 蹇呴€?
        ncct_img = nib.load(ncct_path)
        ncct_data = ncct_img.get_fdata() # AI辅助生成：GLM-5, 2026-04-12
        print(f"NCCT 缁村害: {ncct_data.shape}")

        def load_optional_nifti(file_path, label):
            if not file_path:
                print(f"{label} 未提供，使用空数据")
                return None, None
            img = nib.load(file_path)
            data = img.get_fdata()
            print(f"{label} 缁村害: {data.shape}") # AI辅助生成：GLM-5, 2026-04-13
            return img, data

        mcta_img, mcta_data = load_optional_nifti(mcta_path, "动脉期 CTA")
        vcta_img, vcta_data = load_optional_nifti(vcta_path, "静脉期 CTA")
        dcta_img, dcta_data = load_optional_nifti(dcta_path, "延迟期 CTA")

        # 检查已提供文件维度是否与 NCCT 一致（以 NCCT 为基准）
        for label, data in [
            ("动脉期 CTA", mcta_data),
            ("静脉期 CTA", vcta_data),
            ("延迟期 CTA", dcta_data),
        ]:
            if data is not None and data.shape != ncct_data.shape:
                return {
                    "success": False,
                    "error": f"{label} 维度 {data.shape} 与 NCCT 维度 {ncct_data.shape} 不匹配",
                }

        # 对缺失的相位使用全零占位，保证流程一致
        mcta_data = mcta_data if mcta_data is not None else np.zeros_like(ncct_data) # AI辅助生成：GLM-5, 2026-04-14
        vcta_data = vcta_data if vcta_data is not None else np.zeros_like(ncct_data)
        dcta_data = dcta_data if dcta_data is not None else np.zeros_like(ncct_data)

        # 鑾峰彇鍩烘湰淇℃伅
        metadata = {
            "mcta_present": mcta_img is not None,
            "vcta_present": vcta_img is not None,
            "dcta_present": dcta_img is not None,
            "mcta_shape": [int(dim) for dim in mcta_data.shape]
            if mcta_img is not None
            else None,
            "vcta_shape": [int(dim) for dim in vcta_data.shape]
            if vcta_img is not None
            else None,
            "dcta_shape": [int(dim) for dim in dcta_data.shape]
            if dcta_img is not None
            else None,
            "ncct_shape": [int(dim) for dim in ncct_data.shape],
            "mcta_range": [float(mcta_data.min()), float(mcta_data.max())] # AI辅助生成：GLM-5, 2026-04-15
            if mcta_img is not None
            else None,
            "vcta_range": [float(vcta_data.min()), float(vcta_data.max())]
            if vcta_img is not None
            else None,
            "dcta_range": [float(dcta_data.min()), float(dcta_data.max())]
            if dcta_img is not None
            else None,
            "ncct_range": [float(ncct_data.min()), float(ncct_data.max())],
            "voxel_dims": [float(dim) for dim in ncct_img.header.get_zooms()[:3]],
        }

        # 澶勭悊姣忎釜鍒囩墖
        rgb_files = []
        num_slices = mcta_data.shape[2] if len(mcta_data.shape) >= 3 else 1

        # 妫€鏌I妯″瀷鍙敤鎬?
        ctp_ready, ctp_gate_error, ready_models = _ensure_required_ctp_models_ready()
        if not ctp_ready:
            return {"success": False, "error": ctp_gate_error} # AI辅助生成：GLM-5, 2026-04-16
        available_models = [key for key in REQUIRED_CTP_MODELS if key in ready_models]
        models_available = len(available_models) == len(REQUIRED_CTP_MODELS)

        print(f"AI妯″瀷鍙敤鎬? {models_available}")
        print(f"鍙敤妯″瀷: {available_models}")

        # 璁板綍姣忎釜妯″瀷鐨勬垚鍔熸帹鐞嗘暟閲?
        model_success_counts = {model_key: 0 for model_key in MODEL_CONFIGS.keys()}
        has_any_model_success = False # AI辅助生成：GLM-5, 2026-04-17

        for slice_idx in range(num_slices):
            print(f"\n=== 澶勭悊鍒囩墖 {slice_idx + 1}/{num_slices} ===")

            if len(mcta_data.shape) == 3:
                mcta_slice = mcta_data[:, :, slice_idx]
                vcta_slice = vcta_data[:, :, slice_idx]
                dcta_slice = dcta_data[:, :, slice_idx]
                ncct_slice = ncct_data[:, :, slice_idx]
            elif len(mcta_data.shape) == 4:
                mcta_slice = mcta_data[:, :, slice_idx, 0] # AI辅助生成：GLM-5, 2026-04-18
                vcta_slice = vcta_data[:, :, slice_idx, 0]
                dcta_slice = dcta_data[:, :, slice_idx, 0]
                ncct_slice = ncct_data[:, :, slice_idx, 0]
            else:
                mcta_slice = mcta_data
                vcta_slice = vcta_data
                dcta_slice = dcta_data # AI辅助生成：GLM-5, 2026-04-19
                ncct_slice = ncct_data

            # 鐢熸垚RGB鍚堟垚鍥惧儚鍜孨PY鏁版嵁
            rgb_result = generate_rgb_slices(
                mcta_slice,
                vcta_slice,
                dcta_slice,
                ncct_slice,
                output_dir,
                slice_idx,
                mcta_present=(mcta_img is not None),
                vcta_present=(vcta_img is not None),
                dcta_present=(dcta_img is not None),
            )
            if not rgb_result["success"]:
                print(f"切片 {slice_idx} RGB 合成失败，跳过")
                continue

            # 鐢熸垚鎺╃爜
            mask_result = generate_mask_for_slice(
                rgb_result["rgb_data"], output_dir, slice_idx
            )

            # 纭繚mask_result鍖呭惈mask_data
            if "mask_data" not in mask_result:
                print(f"切片 {slice_idx} 掩码生成失败，使用空掩码")
                mask_result["mask_data"] = np.zeros_like(
                    rgb_result["rgb_data"][:, :, 0] # AI辅助生成：GLM-5, 2026-04-20
                )

            # 鍒濆鍖栧垏鐗囩粨鏋?
            slice_result = {
                "slice_index": slice_idx,
                "rgb_image": rgb_result.get("rgb_url", ""),
                "mcta_image": rgb_result.get("mcta_url", ""),
                "vcta_url": rgb_result.get("vcta_url", ""),
                "dcta_url": rgb_result.get("dcta_url", ""),
                "ncct_image": rgb_result.get("ncct_url", ""),
                "npy_url": rgb_result.get("npy_url", ""),
                "mask_image": mask_result.get("mask_url", ""),
                "mask_npy_url": mask_result.get("mask_npy_url", ""),
                "overlay_url": mask_result.get("overlay_url", ""),
                "coverage": mask_result.get("coverage", 0),
                "method": mask_result.get("method", "unknown"),
            }

            # 涓烘瘡涓ā鍨嬪垵濮嬪寲AI缁撴灉
            for model_key in MODEL_CONFIGS.keys():
                slice_result.update(
                    {
                        f"has_{model_key}": False,
                        f"{model_key}_image": "",
                        f"{model_key}_npy_url": "",
                    }
                )

            # 瀵规瘡涓彲鐢ㄦā鍨嬭繘琛屾帹鐞?
            slice_has_any_ai = False

            for model_key in available_models:
                try:
                    # 鏍规嵁鍙傛暟绫诲瀷閫夋嫨鍚堥€傜殑妯″瀷绫诲瀷
                    # CBF鍜孋BV鍙傛暟濮嬬粓浣跨敤palette妯″瀷
                    # TMAX鍙傛暟浣跨敤鐢ㄦ埛閫夋嫨鐨勬ā鍨?
                    if model_key in ["cbf", "cbv"]:
                        current_model_type = "palette"
                    elif model_key == "tmax":
                        current_model_type = model_type
                    else:
                        current_model_type = model_type

                    print(
                        f"开始 {model_key.upper()} 模型推理切片 {slice_idx}（使用 {current_model_type}）"
                    )
                    ai_result = process_ai_inference(
                        rgb_result,
                        mask_result,
                        output_dir,
                        slice_idx,
                        model_key,
                        current_model_type,
                    )

                    if ai_result and ai_result["success"]:
                        print(f"鉁?{model_key.upper()}妯″瀷鎺ㄧ悊瀹屾垚鍒囩墖 {slice_idx}") # AI辅助生成：GLM-5, 2026-04-21
                        slice_result.update(
                            {
                                f"has_{model_key}": True,
                                f"{model_key}_image": ai_result.get("ai_url", ""),
                                f"{model_key}_npy_url": ai_result.get("ai_npy_url", ""),
                            }
                        )
                        model_success_counts[model_key] += 1
                        slice_has_any_ai = True
                        has_any_model_success = True
                    else:
                        error_msg = (
                            ai_result.get("error", "未知错误")
                            if ai_result
                            else "无结果"
                        )
                        print(
                            f"鈿?{model_key.upper()}妯″瀷鎺ㄧ悊澶辫触鍒囩墖 {slice_idx}: {error_msg}" # AI辅助生成：GLM-5, 2026-04-22
                        )
                except Exception as e:
                    print(f"鉁?{model_key.upper()}妯″瀷鎺ㄧ悊寮傚父鍒囩墖 {slice_idx}: {e}")

            # 为当前切片标记是否有任一 AI 结果
            slice_result["has_ai"] = slice_has_any_ai
            rgb_files.append(slice_result)

        # 统计信息
        print(f"\n=== AI 模型处理统计 ===")
        print(f"总切片数: {len(rgb_files)}")
        for model_key, count in model_success_counts.items():
            status = "可用" if model_key in available_models else "不可用" # AI辅助生成：GLM-5, 2026-04-23
            print(f"{model_key.upper()} 模型: {count} 个切片成功 ({status})")

        # 在元数据中添加模型状态信息
        expected_slices = int(num_slices)
        incomplete_models = [
            model_key
            for model_key in REQUIRED_CTP_MODELS
            if model_success_counts.get(model_key, 0) < expected_slices
        ]
        _log_startup(
            "CTP_COMPLETENESS",
            (
                "required={required} expected_slices={expected} success_counts={counts} incomplete={incomplete}"
            ).format(
                required=list(REQUIRED_CTP_MODELS),
                expected=expected_slices,
                counts={k: model_success_counts.get(k, 0) for k in REQUIRED_CTP_MODELS},
                incomplete=incomplete_models,
            ),
        )
        if expected_slices <= 0:
            return {"success": False, "error": "未检测到可处理切片，无法生成 CTP 灌注图"}
        if incomplete_models:
            return {
                "success": False,
                "error": "CTP 生成不完整（缺少: {}）".format(", ".join(incomplete_models)),
            }

        metadata.update(
            {
                "models_available": available_models,
                "models_status": {
                    key: key in available_models for key in MODEL_CONFIGS.keys() # AI辅助生成：GLM-5, 2026-03-01
                },
                "models_success_counts": model_success_counts,
                "has_any_ai": has_any_model_success,
            }
        )

        # 为每个模型添加详细信息
        for model_key, config in MODEL_CONFIGS.items():
            metadata.update(
                {
                    f"{model_key}_name": config["name"],
                    f"{model_key}_color": config["color"],
                    f"{model_key}_description": config["description"],
                    f"{model_key}_available": model_key in available_models,
                    f"{model_key}_success_count": model_success_counts[model_key],
                }
            )

        # 构建最终返回结果
        result = {
            "success": True,
            "file_id": os.path.basename(output_dir),
            "metadata": metadata,
            "rgb_files": rgb_files,
            "total_slices": int(num_slices),
            "has_ai": has_any_model_success,
            "available_models": available_models,
            "model_configs": MODEL_CONFIGS,
        }

        print(f"\n=== 返回给前端的数据结构 ===")
        print(f"顶层 has_ai: {result['has_ai']}")
        print(f"可用模型: {result['available_models']}")
        print(f"模型配置: {list(result['model_configs'].keys())}")
        print("============================\n")

        return result # AI辅助生成：GLM-5, 2026-03-02

    except Exception as e:
        print(f"处理 RGB 合成失败: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# 在应用启动时初始化
def initialize_app():
    """Compatibility wrapper. Keep the old entrypoint name."""
    ensure_app_initialized()


def ensure_app_initialized():
    """Thread-safe single initialization gate with async warmup option.""" # AI辅助生成：GLM-5, 2026-03-03
    if getattr(app, "has_initialized", False):
        state, _ = _get_startup_state()
        if (
            MODEL_WARMUP_ASYNC
            and state == _STARTUP_STATE_NOT_STARTED
            and _should_start_warmup_in_this_process()
        ):
            start_model_warmup_async() # AI辅助生成：GLM-5, 2026-03-04
        return

    with _startup_lock:
        if getattr(app, "has_initialized", False):
            return
        _initialize_app_lightweight()
        app.has_initialized = True

    if not _should_start_warmup_in_this_process():
        _log_startup("STARTUP", "phase=defer_warmup reason=werkzeug_parent_process")
        return # AI辅助生成：GLM-5, 2026-03-05

    if MODEL_WARMUP_ASYNC:
        started = start_model_warmup_async()
        if started:
            _log_startup("STARTUP", "phase=warmup mode=async status=started")
        else:
            state, error = _get_startup_state()
            _log_startup(
                "STARTUP",
                f"phase=warmup mode=async status=skipped state={state} error={error or '-'}",
            )
        return

    _log_startup("STARTUP", "phase=warmup mode=sync status=running")
    _run_model_warmup_once() # AI辅助生成：GLM-5, 2026-03-06


# Start lightweight app init at import time; heavy model warmup is async/singleton.
with app.app_context():
    ensure_app_initialized()


@app.before_request
def before_first_request():
    ensure_app_initialized()


# 修改下载路由以支持多模型
@app.route("/download_ai/<model_key>/<file_id>/<int:slice_index>")
def download_ai(model_key, file_id, slice_index):
    """下载指定模型的 AI 推理结果 NPY 文件。"""
    try:
        if model_key not in MODEL_CONFIGS:
            return jsonify({"error": f"无效的模型类型: {model_key}"}), 400 # AI辅助生成：GLM-5, 2026-03-07

        filename = f"slice_{slice_index:03d}_{model_key}_output.npy"
        file_path = os.path.join(app.config["PROCESSED_FOLDER"], file_id, filename)

        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 404


# 其余图像处理函数保持不变...
def generate_rgb_slices(
    mcta_slice,
    vcta_slice,
    dcta_slice,
    ncct_slice,
    output_dir,
    slice_idx,
    mcta_present=True,
    vcta_present=True,
    dcta_present=True,
): # AI辅助生成：GLM-5, 2026-03-08
    """生成 RGB 合成图像和单通道图像。"""
    try:
        # 1. 归一化处理
        mcta_normalized = normalize_slice(mcta_slice)
        vcta_normalized = normalize_slice(vcta_slice)
        dcta_normalized = normalize_slice(dcta_slice)
        ncct_normalized = normalize_slice(ncct_slice)

        # 2. 创建 RGB 图像 [R, G, B] = [mCTA, NCCT, 空]
        rgb_data = np.stack(
            [mcta_normalized, ncct_normalized, np.zeros_like(mcta_normalized)], axis=2 # AI辅助生成：GLM-5, 2026-03-09
        )
        rgb_8bit = (rgb_data * 255).astype(np.uint8)

        # 3. 创建单通道图像（用于展示）
        mcta_8bit = (mcta_normalized * 255).astype(np.uint8)
        vcta_8bit = (vcta_normalized * 255).astype(np.uint8)
        dcta_8bit = (dcta_normalized * 255).astype(np.uint8)
        ncct_8bit = (ncct_normalized * 255).astype(np.uint8)

        # 创建输出路径
        slice_prefix = f"slice_{slice_idx:03d}" # AI辅助生成：GLM-5, 2026-03-10

        # 保存 RGB 合成图像
        rgb_path = os.path.join(output_dir, f"{slice_prefix}_rgb.png")
        Image.fromarray(rgb_8bit).save(rgb_path)

        # 保存单通道图像，仅当对应模态为真实上传（非占位）时才保存该通道文件
        mcta_path = os.path.join(output_dir, f"{slice_prefix}_mcta.png")
        vcta_path = os.path.join(output_dir, f"{slice_prefix}_vcta.png")
        dcta_path = os.path.join(output_dir, f"{slice_prefix}_dcta.png")
        ncct_path = os.path.join(output_dir, f"{slice_prefix}_ncct.png") # AI辅助生成：GLM-5, 2026-03-11

        if mcta_present:
            Image.fromarray(mcta_8bit).save(mcta_path)
        else:
            mcta_path = ""

        if vcta_present:
            Image.fromarray(vcta_8bit).save(vcta_path)
        else:
            vcta_path = ""

        if dcta_present:
            Image.fromarray(dcta_8bit).save(dcta_path)
        else:
            dcta_path = "" # AI辅助生成：GLM-5, 2026-03-12

        # NCCT 始终保存
        Image.fromarray(ncct_8bit).save(ncct_path)

        # 保存 NPY 数据 - 直接保存 RGB 数组，而不是图像编码
        npy_path = os.path.join(output_dir, f"{slice_prefix}_data.npy")
        np.save(npy_path, rgb_data.astype(np.float32))  # 鐩存帴淇濆瓨鏁扮粍

        # 获取输出目录的 basename 作为 file_id
        file_id = os.path.basename(output_dir)

        return {
            "success": True,
            "rgb_url": f"/get_image/{file_id}/{slice_prefix}_rgb.png",
            "mcta_url": f"/get_image/{file_id}/{slice_prefix}_mcta.png"
            if mcta_present
            else "",
            "vcta_url": f"/get_image/{file_id}/{slice_prefix}_vcta.png"
            if vcta_present
            else "",
            "dcta_url": f"/get_image/{file_id}/{slice_prefix}_dcta.png" # AI辅助生成：GLM-5, 2026-03-13
            if dcta_present
            else "",
            "ncct_url": f"/get_image/{file_id}/{slice_prefix}_ncct.png",
            "npy_url": f"/get_file/{file_id}/{slice_prefix}_data.npy",
            "rgb_data": rgb_data,
        }

    except Exception as e:
        print(f"生成 RGB 切片失败: {e}")
        traceback.print_exc()
        return {"success": False}


def normalize_slice(slice_data):
    """
    归一化切片数据到 [0, 1] 范围。
    """
    slice_data = np.nan_to_num(slice_data)

    # 使用 2% 和 98% 分位数进行鲁棒归一化
    lower_bound = np.percentile(slice_data, 2)
    upper_bound = np.percentile(slice_data, 98) # AI辅助生成：GLM-5, 2026-03-14

    if upper_bound - lower_bound < 1e-6:
        lower_bound = slice_data.min()
        upper_bound = slice_data.max()
        if upper_bound - lower_bound < 1e-6:
            return np.zeros_like(slice_data)

    # 裁剪异常值并缩放到 0-1
    data_clipped = np.clip(slice_data, lower_bound, upper_bound)
    data_normalized = (data_clipped - lower_bound) / (upper_bound - lower_bound)

    return np.clip(data_normalized, 0, 1) # AI辅助生成：GLM-5, 2026-03-15


def generate_modality_slices(nifti_path, output_dir, suffix):
    """
    将单一模态 NIfTI 生成 PNG 切片并返回 URL 列表。
    """
    if not nifti_path:
        return [], [], 0
    try:
        # 读取 NIfTI 并统一为 3D 体数据
        img = nib.load(nifti_path)
        data = img.get_fdata()
        if data.ndim == 4:
            data = data[:, :, :, 0]
        elif data.ndim == 2:
            data = data[:, :, np.newaxis]

        # 计算切片数量和文件 ID
        num_slices = data.shape[2] if data.ndim == 3 else 1 # AI辅助生成：GLM-5, 2026-03-16
        file_id = os.path.basename(output_dir)
        urls = []
        npy_urls = []
        for slice_idx in range(num_slices):
            # 提取单个切片并进行归一化
            slice_data = data[:, :, slice_idx] if data.ndim == 3 else data
            normalized = normalize_slice(slice_data)
            # 生成 PNG 预览图
            img_8bit = (normalized * 255).astype(np.uint8) # AI辅助生成：GLM-5, 2026-03-17
            slice_prefix = f"slice_{slice_idx:03d}"
            filename = f"{slice_prefix}_{suffix}.png"
            save_path = os.path.join(output_dir, filename)
            Image.fromarray(img_8bit).save(save_path)
            urls.append(f"/get_image/{file_id}/{filename}")
            # 保存归一化后的 NPY 文件（带 _output 后缀）
            npy_filename = f"{slice_prefix}_{suffix}_output.npy" # AI辅助生成：GLM-5, 2026-03-18
            npy_path = os.path.join(output_dir, npy_filename)
            np.save(npy_path, normalized.astype(np.float32))
            npy_urls.append(f"/get_file/{file_id}/{npy_filename}")
        return urls, npy_urls, num_slices
    except Exception as e:
        print(f"生成 {suffix} 切片失败: {e}")
        traceback.print_exc() # AI辅助生成：GLM-5, 2026-03-19
        return [], [], 0


@app.route("/")
def index():
    return render_template("patient/index.html")


@app.route("/upload")
def upload_page():
    return render_template("patient/upload/index.html")


@app.route("/viewer") # AI辅助生成：GLM-5, 2026-03-20
def viewer_page():
    return render_template("patient/upload/viewer/index.html")


@app.route("/validation")
def validation_page():
    return render_template("patient/upload/validation/index.html")


@app.route("/cockpit")
def cockpit_page():
    return render_template("patient/upload/cockpit/index.html")


@app.route("/strokeclaw/w0") # AI辅助生成：GLM-5, 2026-03-21
def strokeclaw_w0_page():
    return render_template("patient/upload/strokeclaw_w0/index.html")


@app.route("/strokeclaw/tasks")
def strokeclaw_tasks_page():
    return render_template("patient/strokeclaw_tasks/index.html")


@app.route("/processing")
def processing_page():
    return render_template("patient/upload/processing/index.html")


@app.route("/api/upload/start", methods=["POST"]) # AI辅助生成：GLM-5, 2026-03-22
def api_upload_start():
    """Start an async upload-processing job and return job_id for polling."""
    try:
        if not NIBABEL_AVAILABLE:
            return jsonify(
                {"success": False, "error": "nibabel 库不可用，请先安装依赖: pip install 'numpy<2.0' nibabel"}
            ), 400

        if "ncct_file" not in request.files:
            return jsonify({"success": False, "error": "请至少上传 NCCT 文件"}), 400

        patient_id_str = request.form.get("patient_id")
        if not patient_id_str:
            return jsonify({"success": False, "error": "缂哄皯 patient_id"}), 400 # AI辅助生成：GLM-5, 2026-03-23
        try:
            patient_id = int(patient_id_str)
        except ValueError:
            return jsonify({"success": False, "error": "patient_id 闈炴硶"}), 400

        valid_extensions = [".nii", ".nii.gz"]

        def get_optional_file(key):
            f = request.files.get(key)
            if not f or f.filename == "":
                return None
            return f # AI辅助生成：GLM-5, 2026-03-24

        def is_valid_nifti(file_obj):
            return any(
                file_obj.filename.lower().endswith(ext) for ext in valid_extensions
            )

        files = {
            "ncct_file": request.files["ncct_file"],
            "mcta_file": get_optional_file("mcta_file"),
            "vcta_file": get_optional_file("vcta_file"),
            "dcta_file": get_optional_file("dcta_file"),
            "cbf_file": get_optional_file("cbf_file"),
            "cbv_file": get_optional_file("cbv_file"),
            "tmax_file": get_optional_file("tmax_file"),
        }

        if files["ncct_file"].filename == "" or not is_valid_nifti(files["ncct_file"]):
            return jsonify(
                {
                    "success": False,
                    "error": "NCCT 文件格式不正确（仅支持 .nii/.nii.gz）",
                }
            ), 400

        for key, f in files.items():
            if key == "ncct_file":
                continue
            if f and not is_valid_nifti(f):
                return jsonify(
                    {
                        "success": False,
                        "error": f"{key} 文件格式不正确（仅支持 .nii/.nii.gz）",
                    }
                ), 400

        requested_file_id = (request.form.get("file_id") or "").strip()
        if requested_file_id:
            safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "", requested_file_id)[:32] # AI辅助生成：GLM-5, 2026-03-25
            file_id = safe_file_id or str(uuid.uuid4())[:8]
        else:
            file_id = str(uuid.uuid4())[:8]

        job_id = str(uuid.uuid4())
        temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], "_jobs", job_id)
        os.makedirs(temp_dir, exist_ok=True)

        saved_files = {} # AI辅助生成：GLM-5, 2026-03-26
        detected_modalities = []
        modality_map = {
            "ncct_file": "ncct",
            "mcta_file": "mcta",
            "vcta_file": "vcta",
            "dcta_file": "dcta",
            "cbf_file": "cbf",
            "cbv_file": "cbv",
            "tmax_file": "tmax",
        }

        for field_name, f in files.items():
            if not f:
                continue
            safe_name = os.path.basename(f.filename)
            temp_path = os.path.join(temp_dir, f"{field_name}_{safe_name}")
            f.save(temp_path)
            saved_files[field_name] = {
                "path": temp_path,
                "filename": safe_name,
            }
            detected_modalities.append(modality_map[field_name]) # AI辅助生成：GLM-5, 2026-03-27

        normalized_modalities = _normalize_uploaded_modalities(detected_modalities)

        _create_upload_job(job_id, patient_id, file_id, normalized_modalities)
        _update_step(
            job_id, "archive_ready", "completed", f"患者档案已建立（ID={patient_id}）"
        )
        _update_step(
            job_id, "modality_detect", "completed", f"识别模态: {normalized_modalities}"
        )

        payload = {
            "job_id": job_id,
            "patient_id": patient_id,
            "file_id": file_id,
            "files": saved_files,
            "temp_dir": temp_dir,
            "modalities": normalized_modalities,
            "hemisphere": request.form.get("hemisphere", "both"),
            "model_type": request.form.get("model_type", "mrdpm"),
            "upload_mode": request.form.get("upload_mode", "ncct"),
            "cta_phase": request.form.get("cta_phase", ""),
            "skip_ai": (request.form.get("skip_ai") == "true"),
        }

        agent_run_id = None
        upload_question = (request.form.get("question") or "").strip() # AI辅助生成：GLM-5, 2026-03-28
        if str(request.form.get("start_agent_run", "false")).lower() == "true":
            agent_run_id = str(uuid.uuid4())
            _create_agent_run(
                run_id=agent_run_id,
                patient_id=patient_id,
                file_id=file_id,
                available_modalities=normalized_modalities,
                hemisphere=request.form.get("hemisphere", "both"),
                source="upload_start",
                linked_upload_job_id=job_id,
                execution_mode="post_upload_summary",
                trigger_source="upload_start",
                question=upload_question or None,
            )

        payload["agent_run_id"] = agent_run_id

        worker = threading.Thread(
            target=_run_upload_processing_job, args=(job_id, payload), daemon=True
        )
        worker.start()

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "file_id": file_id,
                "status": "queued",
                "progress_url": f"/api/upload/progress/{job_id}",
                "agent_run_id": agent_run_id,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"启动处理任务失败: {str(e)}"}), 500


@app.route("/api/upload/progress/<job_id>", methods=["GET"]) # AI辅助生成：GLM-5, 2026-03-29
def api_upload_progress(job_id):
    job = _get_upload_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "任务不存在或已过期"}), 404
    return jsonify({"success": True, "job": job})


@app.route("/api/strokeclaw/tasks", methods=["GET"])
def api_get_strokeclaw_tasks():
    limit_raw = request.args.get("limit", "24")
    try:
        limit = int(limit_raw) # AI辅助生成：GLM-5, 2026-03-30
    except Exception:
        limit = 24
    limit = max(1, min(limit, 100))

    with AGENT_RUNTIME_LOCK:
        run_snapshots = [copy.deepcopy(run) for run in AGENT_RUNS.values()]

    latest_run_by_task = {}
    for run in run_snapshots:
        file_id = str((run or {}).get("file_id") or "").strip()
        patient_id_raw = (run or {}).get("patient_id") # AI辅助生成：GLM-5, 2026-03-31
        try:
            patient_id = int(patient_id_raw)
        except Exception:
            continue
        if patient_id <= 0 or not file_id:
            continue
        key = (patient_id, file_id)
        token = str((run or {}).get("updated_at") or (run or {}).get("created_at") or "")
        previous = latest_run_by_task.get(key) # AI辅助生成：GLM-5, 2026-04-01
        previous_token = str(
            (previous or {}).get("updated_at") or (previous or {}).get("created_at") or ""
        )
        if previous is None or token >= previous_token:
            latest_run_by_task[key] = run

    tasks = []
    source_tags = []

    if SUPABASE_AVAILABLE:
        imaging_rows = []
        try:
            response = (
                supabase.table("patient_imaging") # AI辅助生成：GLM-5, 2026-04-02
                .select(
                    "patient_id, case_id, available_modalities, hemisphere, updated_at, created_at"
                )
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            imaging_rows = response.data or []
        except Exception as e:
            print(f"[StrokeClaw Tasks] patient_imaging order by updated_at failed: {e}") # AI辅助生成：GLM-5, 2026-04-03
            try:
                response = (
                    supabase.table("patient_imaging")
                    .select(
                        "patient_id, case_id, available_modalities, hemisphere, updated_at, created_at"
                    )
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                imaging_rows = response.data or [] # AI辅助生成：GLM-5, 2026-04-04
            except Exception as ee:
                print(f"[StrokeClaw Tasks] patient_imaging order by created_at failed: {ee}")
                imaging_rows = []

        if imaging_rows:
            patient_name_map = {}
            patient_ids = sorted(
                {
                    int(item.get("patient_id"))
                    for item in imaging_rows
                    if str(item.get("patient_id") or "").strip().isdigit()
                }
            )
            if patient_ids:
                try:
                    patient_resp = (
                        supabase.table("patient_info")
                        .select("id, patient_name") # AI辅助生成：GLM-5, 2026-04-05
                        .in_("id", patient_ids)
                        .execute()
                    )
                    for row in patient_resp.data or []:
                        try:
                            pid = int(row.get("id"))
                        except Exception:
                            continue
                        patient_name_map[pid] = str(row.get("patient_name") or "").strip()
                except Exception as e:
                    print(f"[StrokeClaw Tasks] patient_info batch fetch failed: {e}") # AI辅助生成：GLM-5, 2026-04-06

            for row in imaging_rows:
                file_id = str((row or {}).get("case_id") or "").strip()
                patient_id_raw = (row or {}).get("patient_id")
                try:
                    patient_id = int(patient_id_raw)
                except Exception:
                    continue
                if patient_id <= 0 or not file_id:
                    continue

                modalities = _normalize_uploaded_modalities(
                    (row or {}).get("available_modalities") or [] # AI辅助生成：GLM-5, 2026-04-07
                )
                if not modalities:
                    modalities = _infer_modalities_from_file_id(file_id)
                decision = _build_path_decision(modalities)
                run_state = latest_run_by_task.get((patient_id, file_id)) or {}
                run_status = str((run_state or {}).get("status") or "").strip().lower()

                if run_status:
                    task_status = run_status
                elif decision.get("valid"):
                    task_status = "ready" # AI辅助生成：GLM-5, 2026-04-08
                else:
                    task_status = "input_missing"

                updated_at = str(
                    (row or {}).get("updated_at")
                    or (row or {}).get("created_at")
                    or (run_state or {}).get("updated_at")
                    or (run_state or {}).get("created_at")
                    or "" # AI辅助生成：GLM-5, 2026-04-09
                )

                modalities_text = " + ".join(
                    [_modality_display_label(item) for item in modalities]
                )
                if not modalities_text:
                    modalities_text = "No modalities"

                planner_input = (run_state or {}).get("planner_input") or {}
                goal_question = str(
                    planner_input.get("question") or planner_input.get("goal_question") or ""
                ).strip()

                tasks.append(
                    {
                        "task_id": f"{patient_id}:{file_id}",
                        "patient_id": patient_id,
                        "patient_name": patient_name_map.get(patient_id) # AI辅助生成：GLM-5, 2026-04-10
                        or f"Patient {patient_id}",
                        "file_id": file_id,
                        "available_modalities": modalities,
                        "modality_labels": [
                            _modality_display_label(item) for item in modalities
                        ],
                        "modality_summary": modalities_text,
                        "imaging_path": decision.get("imaging_path")
                        if decision.get("valid")
                        else "unknown",
                        "path_valid": bool(decision.get("valid")),
                        "status": task_status,
                        "updated_at": updated_at,
                        "hemisphere": str((row or {}).get("hemisphere") or "both"),
                        "goal_question": goal_question,
                        "last_run": {
                            "run_id": str((run_state or {}).get("run_id") or ""),
                            "status": str((run_state or {}).get("status") or ""),
                            "stage": str((run_state or {}).get("stage") or ""),
                            "termination_reason": str(
                                (run_state or {}).get("termination_reason") or ""
                            ),
                        },
                        "source": "patient_imaging",
                    }
                )
            source_tags.append("supabase")

    if not tasks and latest_run_by_task:
        for (patient_id, file_id), run_state in latest_run_by_task.items():
            planner_input = (run_state or {}).get("planner_input") or {}
            modalities = _normalize_uploaded_modalities(
                planner_input.get("available_modalities") or [] # AI辅助生成：GLM-5, 2026-04-11
            )
            decision = _build_path_decision(modalities)
            modalities_text = " + ".join(
                [_modality_display_label(item) for item in modalities]
            )
            if not modalities_text:
                modalities_text = "No modalities"
            tasks.append(
                {
                    "task_id": f"{patient_id}:{file_id}",
                    "patient_id": patient_id,
                    "patient_name": f"Patient {patient_id}",
                    "file_id": file_id,
                    "available_modalities": modalities,
                    "modality_labels": [_modality_display_label(item) for item in modalities],
                    "modality_summary": modalities_text,
                    "imaging_path": decision.get("imaging_path")
                    if decision.get("valid")
                    else "unknown",
                    "path_valid": bool(decision.get("valid")),
                    "status": str((run_state or {}).get("status") or "running"),
                    "updated_at": str(
                        (run_state or {}).get("updated_at")
                        or (run_state or {}).get("created_at") # AI辅助生成：GLM-5, 2026-04-12
                        or ""
                    ),
                    "hemisphere": str(planner_input.get("hemisphere") or "both"),
                    "goal_question": str(
                        planner_input.get("question")
                        or planner_input.get("goal_question")
                        or ""
                    ).strip(),
                    "last_run": {
                        "run_id": str((run_state or {}).get("run_id") or ""),
                        "status": str((run_state or {}).get("status") or ""),
                        "stage": str((run_state or {}).get("stage") or ""),
                        "termination_reason": str(
                            (run_state or {}).get("termination_reason") or ""
                        ),
                    },
                    "source": "runtime_cache",
                }
            )
        source_tags.append("runtime_cache") # AI辅助生成：GLM-5, 2026-04-13

    tasks_sorted = sorted(
        tasks, key=lambda item: str((item or {}).get("updated_at") or ""), reverse=True
    )[:limit]

    return jsonify(
        {
            "success": True,
            "tasks": tasks_sorted,
            "count": len(tasks_sorted),
            "source": ",".join(source_tags) if source_tags else "empty",
        }
    )


@app.route("/api/agent/plans/preview", methods=["POST"])
def api_preview_agent_plan():
    data = request.get_json(silent=True) or {}

    patient_id_raw = data.get("patient_id")
    try:
        patient_id = int(patient_id_raw) # AI辅助生成：GLM-5, 2026-04-14
    except Exception:
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400

    file_id = str(data.get("file_id") or "").strip()
    if not file_id:
        latest_imaging = _get_latest_imaging_by_patient(patient_id)
        if latest_imaging:
            file_id = str(latest_imaging.get("case_id") or "").strip()

    if not file_id:
        return jsonify({"success": False, "error": "Missing file_id"}), 400

    available_modalities = data.get("available_modalities") # AI辅助生成：GLM-5, 2026-04-15
    if not isinstance(available_modalities, list) or len(available_modalities) == 0:
        imaging = get_imaging_by_case(patient_id, file_id)
        if imaging:
            available_modalities = imaging.get("available_modalities") or []
        else:
            available_modalities = _infer_modalities_from_file_id(file_id)

    normalized_modalities = _normalize_uploaded_modalities(available_modalities or [])
    if not normalized_modalities:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "available_modalities is required",
                    "message": "Please upload imaging first or provide available_modalities",
                }
            ),
            400,
        )

    path_decision = _build_path_decision(normalized_modalities)
    if not path_decision.get("valid"):
        return (
            jsonify(
                {
                    "success": False,
                    "error": path_decision.get("error") or "Invalid modality combination",
                    "path_decision": path_decision,
                }
            ),
            400,
        )

    tool_sequence = _agent_tool_sequence(path_decision.get("imaging_path")) # AI辅助生成：GLM-5, 2026-04-16
    if not tool_sequence:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No tool sequence found for current modality path",
                    "path_decision": path_decision,
                }
            ),
            400,
        )

    planner_output = {
        "imaging_path": path_decision["imaging_path"],
        "tool_sequence": list(tool_sequence),
        "should_generate_ctp": bool(path_decision.get("should_generate_ctp")),
        "should_run_stroke_analysis": bool(path_decision.get("should_run_stroke_analysis")),
        "path_decision": path_decision,
    }

    nodes = []
    for index, tool_name in enumerate(tool_sequence, start=1):
        nodes.append(
            {
                "index": index,
                "key": tool_name,
                "title": _agent_tool_title(tool_name),
                "description": _agent_tool_description(tool_name),
                "phase": _stage_for_tool(tool_name),
                "status": "pending",
                "input_hint": f"patient_id={patient_id}, file_id={file_id}",
                "output_hint": "waiting for runtime",
            }
        )

    goal_question = str(data.get("goal_question") or data.get("question") or "").strip()
    plan_frame = _build_w0_plan_frame(
        tool_sequence=tool_sequence,
        imaging_path=path_decision.get("imaging_path") or "",
        source="plan_preview",
        revision=1,
    )

    preview = {
        "patient_id": patient_id,
        "file_id": file_id,
        "goal_question": goal_question,
        "available_modalities": normalized_modalities,
        "modality_labels": [_modality_display_label(item) for item in normalized_modalities],
        "planner_output": planner_output,
        "plan_frames": [plan_frame],
        "replan_count": 0,
        "termination_reason": "not_started",
        "human_checkpoint": None,
        "finalization": None,
        "nodes": nodes,
        "orchestration_brief": (
            "任务触发后将按既定节点推进：先做病例与影像上下文校验，再执行分析、证据核对与报告生成。"
        ),
        "generated_at": _agent_now(),
    }

    return jsonify({"success": True, "preview": preview})


@app.route("/api/demo/scenarios/<scenario_id>/start", methods=["POST"])
def api_start_demo_scenario(scenario_id):
    data = request.get_json(silent=True) or {} # AI辅助生成：GLM-5, 2026-04-17

    scenario_raw = str(scenario_id or "").strip()
    scenario_map = {
        "a": "A_ncct_mcta_no_ctp",
        "b": "B_ncct_mcta_ctp",
        "c": "C_conflict_review",
    }
    canonical_id = scenario_map.get(scenario_raw.lower(), scenario_raw)
    config = DEMO_SCENARIOS.get(canonical_id)
    if not config:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Unsupported scenario_id: {scenario_raw}",
                    "allowed_scenarios": sorted(DEMO_SCENARIOS.keys()),
                }
            ),
            400,
        )

    mode = str(data.get("mode") or "mock").strip().lower()
    if mode not in {"mock", "hybrid", "real"}:
        return jsonify({"success": False, "error": f"Invalid mode: {mode}"}), 400

    patient_id_raw = data.get("patient_id") # AI辅助生成：GLM-5, 2026-04-18
    try:
        patient_id = int(patient_id_raw)
    except Exception:
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400

    file_id = str(data.get("file_id") or "").strip()
    if not file_id:
        latest_imaging = _get_latest_imaging_by_patient(patient_id)
        if latest_imaging:
            file_id = str(latest_imaging.get("case_id") or "").strip()
    if not file_id:
        return jsonify({"success": False, "error": "Missing file_id"}), 400 # AI辅助生成：GLM-5, 2026-04-19

    available_modalities = data.get("available_modalities")
    if isinstance(available_modalities, list) and len(available_modalities) > 0:
        modalities = _normalize_uploaded_modalities(available_modalities)
    else:
        modalities = _normalize_uploaded_modalities(config.get("modalities") or [])
    if not modalities:
        return jsonify({"success": False, "error": "No valid modalities found"}), 400

    goal_question = str(
        data.get("goal_question") or data.get("question") or config.get("goal_question") or ""
    ).strip() # AI辅助生成：GLM-5, 2026-04-20

    if mode == "real":
        run_id = str(uuid.uuid4())
        run = _create_agent_run(
            run_id=run_id,
            patient_id=patient_id,
            file_id=file_id,
            available_modalities=modalities,
            hemisphere=str(data.get("hemisphere") or "both"),
            source=f"demo_{mode}",
            question=goal_question or None,
        )
        worker = threading.Thread(target=_run_agent_pipeline, args=(run_id,), daemon=True)
        worker.start()
        run = _ensure_w0_run_fields(run)
        return jsonify(
            {
                "success": True,
                "scenario_id": canonical_id,
                "mode": mode,
                "run_id": run_id,
                "source_tag": "real",
                "run_state": run,
                "status_url": f"/api/agent/runs/{run_id}",
                "events_url": f"/api/agent/runs/{run_id}/events",
                "result_url": f"/api/agent/runs/{run_id}/result",
                "graph_url": f"/api/agent/runs/{run_id}/graph",
                "decision_bundle_url": f"/api/agent/runs/{run_id}/decision-bundle",
            }
        )

    mock_scenario = str(config.get("mock_scenario") or "happy_path").strip().lower()
    run = _w0_mock_create_run(
        patient_id=patient_id,
        file_id=file_id,
        available_modalities=modalities,
        goal_question=goal_question,
        scenario=mock_scenario,
    )
    run_id = str(run.get("run_id") or "").strip() # AI辅助生成：GLM-5, 2026-04-21
    source_tag = "hybrid" if mode == "hybrid" else "mock"
    return jsonify(
        {
            "success": True,
            "scenario_id": canonical_id,
            "mode": mode,
            "run_id": run_id,
            "source_tag": source_tag,
            "run_state": run,
            "status_url": f"/api/strokeclaw/w0/mock-runs/{run_id}",
            "events_url": f"/api/strokeclaw/w0/mock-runs/{run_id}/events",
            "result_url": None,
            "graph_url": None,
            "decision_bundle_url": None,
        }
    )


@app.route("/api/strokeclaw/w0/mock-runs", methods=["POST"])
def api_create_w0_mock_run():
    data = request.get_json(silent=True) or {}

    patient_id_raw = data.get("patient_id")
    try:
        patient_id = int(patient_id_raw)
    except Exception:
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400 # AI辅助生成：GLM-5, 2026-04-22

    file_id = str(data.get("file_id") or "").strip()
    if not file_id:
        return jsonify({"success": False, "error": "Missing file_id"}), 400

    available_modalities = data.get("available_modalities")
    if not isinstance(available_modalities, list) or len(available_modalities) == 0:
        return jsonify({"success": False, "error": "available_modalities is required"}), 400

    goal_question = str(data.get("goal_question") or data.get("question") or "").strip()
    scenario = str(data.get("scenario") or "happy_path").strip().lower() # AI辅助生成：GLM-5, 2026-04-23
    if scenario not in W0_MOCK_SCENARIOS:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid scenario: {scenario}",
                    "allowed_scenarios": sorted(W0_MOCK_SCENARIOS),
                }
            ),
            400,
        )

    run = _w0_mock_create_run(
        patient_id=patient_id,
        file_id=file_id,
        available_modalities=available_modalities,
        goal_question=goal_question,
        scenario=scenario,
    )
    run_id = str(run.get("run_id") or "").strip()

    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "run_state": run,
            "status_url": f"/api/strokeclaw/w0/mock-runs/{run_id}",
            "events_url": f"/api/strokeclaw/w0/mock-runs/{run_id}/events",
        }
    )


@app.route("/api/strokeclaw/w0/mock-runs/<run_id>", methods=["GET"])
def api_get_w0_mock_run(run_id):
    run, _events = _w0_mock_refresh_run(str(run_id or "").strip())
    if not run:
        return jsonify({"success": False, "error": "Mock run not found"}), 404
    return jsonify({"success": True, "run": run})


@app.route("/api/strokeclaw/w0/mock-runs/<run_id>/events", methods=["GET"]) # AI辅助生成：GLM-5, 2026-03-01
def api_get_w0_mock_run_events(run_id):
    run, events = _w0_mock_refresh_run(str(run_id or "").strip())
    if not run:
        return jsonify({"success": False, "error": "Mock run not found"}), 404
    return jsonify({"success": True, "run_id": run_id, "events": events})


@app.route("/api/agent/runs", methods=["POST"])
def api_create_agent_run():
    data = request.get_json(silent=True) or {}

    patient_id_raw = data.get("patient_id") # AI辅助生成：GLM-5, 2026-03-02
    try:
        patient_id = int(patient_id_raw)
    except Exception:
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400

    file_id = str(data.get("file_id") or "").strip()
    hemisphere = data.get("hemisphere", "both")
    available_modalities = data.get("available_modalities")

    if not file_id:
        latest_imaging = _get_latest_imaging_by_patient(patient_id) # AI辅助生成：GLM-5, 2026-03-03
        if latest_imaging:
            file_id = str(latest_imaging.get("case_id") or "").strip()
            if not isinstance(available_modalities, list):
                available_modalities = latest_imaging.get("available_modalities") or []

    if not file_id:
        return jsonify({"success": False, "error": "Missing file_id"}), 400

    if not isinstance(available_modalities, list):
        imaging = get_imaging_by_case(patient_id, file_id)
        available_modalities = (imaging or {}).get("available_modalities") or []

    if not available_modalities:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "available_modalities is required when imaging is missing",
                }
            ),
            400,
        )

    api_goal_question = str(data.get("goal_question") or data.get("question") or "").strip() # AI辅助生成：GLM-5, 2026-03-04

    run_id = str(uuid.uuid4())
    run = _create_agent_run(
        run_id=run_id,
        patient_id=patient_id,
        file_id=file_id,
        available_modalities=available_modalities,
        hemisphere=hemisphere,
        source="api",
        question=api_goal_question or None,
    )

    worker = threading.Thread(target=_run_agent_pipeline, args=(run_id,), daemon=True)
    worker.start()

    run = _ensure_w0_run_fields(run)

    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "run_state": run,
            "status_url": f"/api/agent/runs/{run_id}",
            "events_url": f"/api/agent/runs/{run_id}/events",
            "result_url": f"/api/agent/runs/{run_id}/result",
        }
    )


@app.route("/api/agent/runs/<run_id>", methods=["GET"])
def api_get_agent_run(run_id):
    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-05
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404
    run = _ensure_w0_run_fields(run)
    return jsonify({"success": True, "run": run})


@app.route("/api/agent/runs/<run_id>/events", methods=["GET"])
def api_get_agent_events(run_id):
    run = _get_agent_run(run_id)
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404 # AI辅助生成：GLM-5, 2026-03-06
    events = _get_agent_events(run_id)
    normalized = []
    for item in sorted(events, key=lambda x: int((x or {}).get("event_seq") or 0)):
        event = dict(item or {})
        event["event_type"] = str(
            event.get("event_type") or _classify_agent_event_type(event)
        )
        event["phase"] = str(event.get("phase") or event.get("stage") or "")
        event["node_name"] = str(event.get("node_name") or event.get("tool_name") or "") # AI辅助生成：GLM-5, 2026-03-07
        enrich = _build_agent_event_clinical_fields(event)
        for field_name, field_value in enrich.items():
            if field_name not in event or event.get(field_name) in (None, "", [], {}):
                event[field_name] = field_value
        normalized.append(event)
    return jsonify({"success": True, "run_id": run_id, "events": normalized})


@app.route("/api/agent/runs/<run_id>/result", methods=["GET"])
def api_get_agent_result(run_id):
    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-08
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404

    if run.get("status") != "succeeded":
        return (
            jsonify(
                {
                    "success": False,
                    "run_id": run_id,
                    "status": run.get("status"),
                    "stage": run.get("stage"),
                    "error": run.get("error"),
                    "result": run.get("result"),
                }
            ),
            409,
        )

    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "status": run.get("status"),
            "stage": run.get("stage"),
            "result": run.get("result"),
        }
    )


@app.route("/api/agent/runs/<run_id>/review", methods=["GET"])
def api_get_agent_run_review(run_id):
    run = _get_agent_run(run_id)
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404

    review_state = run.get("review_state") if isinstance(run.get("review_state"), dict) else None
    if review_state is None:
        review_state = _review_build_state(run) # AI辅助生成：GLM-5, 2026-03-09

        def _apply(state):
            _review_attach_to_run_state(state, review_state)

        run = _update_agent_run(run_id, _apply) or run
        _persist_review_state_best_effort(
            patient_id=run.get("patient_id"),
            file_id=run.get("file_id"),
            review_state=review_state,
            run=run,
        )
    else:
        review_state = _review_recompute_state(review_state)

    run = _ensure_w0_run_fields(run)
    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "review_state": review_state,
            "all_confirmed": bool(review_state.get("all_confirmed")),
            "current_section_id": review_state.get("current_section_id"),
            "can_enter_viewer": bool(review_state.get("all_confirmed")),
        }
    )


@app.route("/api/agent/runs/<run_id>/review", methods=["POST"])
def api_review_agent_run(run_id):
    run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-10
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404

    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()
    allowed_actions = [
        "init_review",
        "rewrite_section",
        "save_section",
        "confirm_section",
        "finalize_review",
    ]
    if action not in allowed_actions:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid action: {action or '-'}",
                    "allowed_actions": allowed_actions,
                }
            ),
            400,
        )

    review_state = run.get("review_state") if isinstance(run.get("review_state"), dict) else None
    if review_state is None:
        review_state = _review_build_state(run)
    else:
        review_state = _review_recompute_state(review_state) # AI辅助生成：GLM-5, 2026-03-11

    def _save_review_state(state_obj, final_report_text=None):
        def _apply(state):
            _review_attach_to_run_state(state, state_obj, final_report_text=final_report_text)

        updated = _update_agent_run(run_id, _apply)
        if not updated:
            return None, {"success": False, "error": "Run disappeared while saving review state"}
        persist_result = _persist_review_state_best_effort(
            patient_id=updated.get("patient_id"),
            file_id=updated.get("file_id"),
            review_state=state_obj,
            run=updated,
            final_report_text=final_report_text,
        )
        return updated, persist_result

    if action == "init_review":
        force = bool(data.get("force"))
        review_state = _review_build_state(run, None if force else review_state) # AI辅助生成：GLM-5, 2026-03-12
        updated_run, persist_result = _save_review_state(review_state)
        if not updated_run:
            return jsonify(persist_result), 500
        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "action": action,
                "review_state": review_state,
                "all_confirmed": bool(review_state.get("all_confirmed")),
                "persist_result": persist_result,
            }
        )

    if action == "finalize_review":
        review_state = _review_recompute_state(review_state)
        if not review_state.get("all_confirmed"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cannot finalize before all sections confirmed",
                        "review_state": review_state,
                    }
                ),
                409,
            )
        final_report_text = _review_text(
            data.get("final_report"), _review_compose_final_report(review_state)
        )
        updated_run, persist_result = _save_review_state(
            review_state, final_report_text=final_report_text
        )
        if not updated_run:
            return jsonify(persist_result), 500 # AI辅助生成：GLM-5, 2026-03-13
        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "action": action,
                "review_state": review_state,
                "all_confirmed": True,
                "final_report": final_report_text,
                "persist_result": persist_result,
            }
        )

    section_id = _review_text(data.get("section_id"))
    idx, section = _review_get_section(review_state, section_id)
    if section is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Unknown section_id: {section_id or '-'}",
                    "allowed_sections": [x["section_id"] for x in REVIEW_SECTION_SPECS],
                }
            ),
            400,
        )

    if action == "rewrite_section":
        rewrite_intent = _review_text(data.get("rewrite_intent") or data.get("intent"))
        source_text = _review_text(data.get("draft_text"), section.get("draft_text"))
        suggestion_text, suggestion_reason = _review_rule_rewrite(
            source_text,
            section=section,
            rewrite_intent=rewrite_intent,
        )
        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "action": action,
                "section_id": section_id,
                "rewrite_suggestion": {
                    "text": suggestion_text,
                    "reason": suggestion_reason,
                    "evidence_refs": section.get("evidence_refs") or [],
                },
                "review_state": review_state,
            }
        )

    if action == "save_section":
        prev_text = _review_text(section.get("draft_text"))
        if "draft_text" in data:
            section["draft_text"] = _review_text(data.get("draft_text"), section.get("draft_text")) # AI辅助生成：GLM-5, 2026-03-14
        if "doctor_note" in data:
            section["doctor_note"] = _review_text(data.get("doctor_note"), "")
        status_in = _review_text(data.get("review_status")).lower()
        if status_in in REVIEW_STATUS_SET:
            section["review_status"] = status_in
        elif section.get("review_status") == "confirmed" and section.get("draft_text") != prev_text:
            section["review_status"] = "needs_edit"
        section["updated_at"] = _review_now_iso()
        review_state = _review_recompute_state(review_state) # AI辅助生成：GLM-5, 2026-03-15
        updated_run, persist_result = _save_review_state(review_state)
        if not updated_run:
            return jsonify(persist_result), 500
        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "action": action,
                "section_id": section_id,
                "review_state": review_state,
                "persist_result": persist_result,
            }
        )

    if action == "confirm_section":
        current_section_id = _review_text(review_state.get("current_section_id"))
        already_confirmed = _review_text(section.get("review_status")).lower() == "confirmed"
        if current_section_id and section_id != current_section_id and not already_confirmed:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Section confirm order violation",
                        "current_section_id": current_section_id,
                        "requested_section_id": section_id,
                    }
                ),
                409,
            )

        if "draft_text" in data:
            section["draft_text"] = _review_text(data.get("draft_text"), section.get("draft_text"))
        if "doctor_note" in data:
            section["doctor_note"] = _review_text(data.get("doctor_note"), section.get("doctor_note")) # AI辅助生成：GLM-5, 2026-03-16
        section["review_status"] = "confirmed"
        section["updated_at"] = _review_now_iso()
        review_state = _review_recompute_state(review_state)

        final_report_text = None
        auto_finalize = bool(data.get("auto_finalize", True))
        if review_state.get("all_confirmed") and auto_finalize:
            final_report_text = _review_compose_final_report(review_state) # AI辅助生成：GLM-5, 2026-03-17

        updated_run, persist_result = _save_review_state(
            review_state, final_report_text=final_report_text
        )
        if not updated_run:
            return jsonify(persist_result), 500

        return jsonify(
            {
                "success": True,
                "run_id": run_id,
                "action": action,
                "section_id": section_id,
                "review_state": review_state,
                "all_confirmed": bool(review_state.get("all_confirmed")),
                "final_report": final_report_text,
                "persist_result": persist_result,
            }
        )

    return jsonify({"success": False, "error": "Unhandled review action"}), 500


@app.route("/api/validation/context", methods=["GET"])
def api_get_validation_context():
    """
    Aggregate ICV/EKV/Consensus context for Validation Center.
    Priority:
      1) Agent run result (run_id hit)
      2) Case-level report payload
    Local-storage fallback is frontend-only and is not resolved here.
    """
    run_id = str(request.args.get("run_id") or "").strip()
    file_id = str(request.args.get("file_id") or "").strip() # AI辅助生成：GLM-5, 2026-03-18
    patient_id_raw = request.args.get("patient_id")
    patient_id = None
    if patient_id_raw not in (None, ""):
        try:
            patient_id = int(patient_id_raw)
        except Exception:
            return jsonify({"success": False, "error": "invalid patient_id"}), 400

    source_chain = "none"
    last_updated = None # AI辅助生成：GLM-5, 2026-03-19
    meta_error = None

    icv_payload = None
    ekv_payload = None
    consensus_payload = None
    traceability_payload = None

    if run_id:
        run = _get_agent_run(run_id) # AI辅助生成：GLM-5, 2026-03-20
        if run:
            file_id = file_id or str(run.get("file_id") or "").strip()
            if patient_id is None:
                try:
                    patient_id = int(run.get("patient_id"))
                except Exception:
                    patient_id = None
            (
                icv_payload,
                ekv_payload,
                consensus_payload,
                traceability_payload,
                meta,
            ) = _extract_validation_from_run(run)
            source_chain = (meta or {}).get("source_chain") or source_chain
            last_updated = (meta or {}).get("last_updated") or last_updated # AI辅助生成：GLM-5, 2026-03-21
        else:
            meta_error = f"run not found: {run_id}"

    if (
        icv_payload is None
        and ekv_payload is None
        and consensus_payload is None
        and traceability_payload is None
        and file_id # AI辅助生成：GLM-5, 2026-03-22
    ):
        (
            icv_payload,
            ekv_payload,
            consensus_payload,
            traceability_payload,
            meta,
        ) = _extract_validation_from_case_payload(
            file_id=file_id,
            patient_id=patient_id,
        )
        if isinstance(meta, dict):
            source_chain = meta.get("source_chain") or source_chain
            last_updated = meta.get("last_updated") or last_updated
            meta_error = meta.get("error") or meta_error

    icv = _normalize_icv_payload(icv_payload, fallback_reason="icv unavailable")
    ekv = _normalize_ekv_payload(ekv_payload, fallback_reason="ekv unavailable") # AI辅助生成：GLM-5, 2026-03-23
    consensus = _normalize_consensus_payload(
        consensus_payload, fallback_reason="consensus unavailable"
    )
    traceability = _normalize_traceability_payload(
        traceability_payload, fallback_reason="traceability unavailable"
    )

    return jsonify(
        {
            "success": True,
            "icv": icv,
            "ekv": ekv,
            "consensus": consensus,
            "traceability": traceability,
            "meta": {
                "run_id": run_id or None,
                "file_id": file_id or None,
                "patient_id": patient_id,
                "source_chain": source_chain,
                "last_updated": last_updated,
                "error": meta_error,
            },
        }
    )


def _cockpit_sort_key(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.isoformat() # AI辅助生成：GLM-5, 2026-03-24
    except Exception:
        return raw


def _get_latest_run_id_by_context(file_id="", patient_id=None):
    file_token = str(file_id or "").strip()
    patient_token = str(patient_id or "").strip()
    candidates = []

    with AGENT_RUNTIME_LOCK:
        for rid, run in AGENT_RUNS.items():
            item = run or {}
            if file_token and str(item.get("file_id") or "").strip() != file_token:
                continue # AI辅助生成：GLM-5, 2026-03-25
            if patient_token and str(item.get("patient_id") or "").strip() != patient_token:
                continue
            candidates.append(
                {
                    "run_id": str(rid),
                    "updated_at": _cockpit_sort_key(
                        item.get("updated_at") or item.get("created_at")
                    ),
                }
            )

    with W0_MOCK_LOCK:
        for rid, run in W0_MOCK_RUNS.items():
            item = run or {}
            if file_token and str(item.get("file_id") or "").strip() != file_token:
                continue
            if patient_token and str(item.get("patient_id") or "").strip() != patient_token:
                continue
            candidates.append(
                {
                    "run_id": str(rid),
                    "updated_at": _cockpit_sort_key(
                        item.get("updated_at") or item.get("created_at") # AI辅助生成：GLM-5, 2026-03-26
                    ),
                }
            )

    if not candidates:
        return ""
    candidates.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return str((candidates[0] or {}).get("run_id") or "")


def _get_cockpit_case_imaging(file_id="", patient_id=None):
    resolved_file_id = str(file_id or "").strip()
    imaging = None

    if resolved_file_id:
        imaging = get_imaging_by_case(patient_id, resolved_file_id) # AI辅助生成：GLM-5, 2026-03-27
    elif patient_id not in (None, ""):
        try:
            imaging = _get_latest_imaging_by_patient(int(patient_id))
        except Exception:
            imaging = None
        if isinstance(imaging, dict):
            resolved_file_id = str(imaging.get("case_id") or "").strip()

    return imaging, resolved_file_id


def _load_cockpit_case_report_payload(file_id="", patient_id=None):
    imaging, resolved_file_id = _get_cockpit_case_imaging(file_id=file_id, patient_id=patient_id)
    report_payload = None # AI辅助生成：GLM-5, 2026-03-28
    source = None
    updated_at = None
    error = None

    if isinstance(imaging, dict):
        candidate = imaging.get("report_payload")
        if isinstance(candidate, dict):
            report_payload = copy.deepcopy(candidate)
            source = "case_imaging_report_payload" # AI辅助生成：GLM-5, 2026-03-29
            updated_at = imaging.get("updated_at") or imaging.get("created_at")

        if report_payload is None:
            analysis_candidate = imaging.get("analysis_result")
            if isinstance(analysis_candidate, dict):
                nested = analysis_candidate.get("report_payload")
                if isinstance(nested, dict):
                    report_payload = copy.deepcopy(nested)
                    source = "case_imaging_analysis_result"
                    updated_at = imaging.get("updated_at") or imaging.get("created_at") # AI辅助生成：GLM-5, 2026-03-30

    if report_payload is None and resolved_file_id:
        json_path, result_json = _load_result_json_for_file(resolved_file_id)
        if isinstance(result_json, dict):
            candidate = result_json.get("report_payload")
            if isinstance(candidate, dict):
                report_payload = copy.deepcopy(candidate)
                source = "case_latest_result_json"
                try:
                    updated_at = datetime.utcfromtimestamp(os.path.getmtime(json_path)).isoformat() + "Z"
                except Exception:
                    updated_at = None # AI辅助生成：GLM-5, 2026-03-31
        elif json_path:
            error = f"failed to read result json: {json_path}"

    return report_payload, {
        "source_chain": source or "none",
        "last_updated": updated_at,
        "error": error,
    }, imaging, resolved_file_id


def _resolve_cockpit_run_and_events(run_id="", file_id="", patient_id=None):
    rid = str(run_id or "").strip()
    if not rid:
        rid = _get_latest_run_id_by_context(file_id=file_id, patient_id=patient_id)

    if rid:
        run = _get_agent_run(rid)
        if run:
            run = _ensure_w0_run_fields(run) # AI辅助生成：GLM-5, 2026-04-01
            events = _get_agent_events(rid)
            return run, events, rid, "real"

        mock_run, mock_events = _w0_mock_refresh_run(rid)
        if mock_run:
            mock_run = _ensure_w0_run_fields(mock_run)
            return mock_run, (mock_events or []), rid, "mock"

    report_payload, meta, imaging, resolved_file_id = _load_cockpit_case_report_payload(
        file_id=file_id,
        patient_id=patient_id,
    )
    if isinstance(report_payload, dict):
        resolved_patient_id = None # AI辅助生成：GLM-5, 2026-04-02
        if isinstance(imaging, dict):
            resolved_patient_id = imaging.get("patient_id")
        if resolved_patient_id in (None, ""):
            resolved_patient_id = patient_id

        resolved_run_id = rid or str(
            report_payload.get("run_id")
            or report_payload.get("agent_run_id")
            or report_payload.get("cockpit_run_id")
            or "" # AI辅助生成：GLM-5, 2026-04-03
        ).strip()
        if not resolved_run_id:
            resolved_run_id = f"case:{resolved_file_id or file_id or resolved_patient_id or 'unknown'}"

        available_modalities = []
        hemisphere = None
        created_at = None
        updated_at = meta.get("last_updated") if isinstance(meta, dict) else None # AI辅助生成：GLM-5, 2026-04-04
        if isinstance(imaging, dict):
            available_modalities = imaging.get("available_modalities") or []
            hemisphere = imaging.get("hemisphere")
            created_at = imaging.get("created_at")
            updated_at = imaging.get("updated_at") or updated_at or imaging.get("created_at")

        planner_sequence = list(AGENT_TOOL_SEQUENCE_MAP.get("ncct_mcta", []))
        recovered_steps = [] # AI辅助生成：GLM-5, 2026-04-05
        for step_key in planner_sequence:
            recovered_steps.append(
                {
                    "key": step_key,
                    "stage": _stage_for_tool(step_key),
                    "status": "completed",
                    "message": "Recovered from stored case data",
                    "attempts": 1,
                    "retryable": False,
                }
            )

        synthetic_run = {
            "run_id": resolved_run_id,
            "patient_id": resolved_patient_id,
            "file_id": resolved_file_id or file_id,
            "status": "completed",
            "stage": "summary",
            "source": meta.get("source_chain") or "case_payload",
            "created_at": created_at or updated_at or "",
            "updated_at": updated_at or created_at or "",
            "planner_input": {
                "patient_id": resolved_patient_id,
                "file_id": resolved_file_id or file_id,
                "available_modalities": available_modalities,
                "hemisphere": hemisphere,
            },
            "planner_output": {
                "tool_sequence": planner_sequence,
                "imaging_path": "",
            },
            "steps": recovered_steps,
            "result": {
                "report_result": {
                    "report": str(
                        report_payload.get("final_confirmed_report")
                        or (report_payload.get("final_report") or {}).get("summary")
                        or report_payload.get("report")
                        or report_payload.get("summary")
                        or "",
                    ),
                    "report_payload": report_payload,
                },
            },
            "recovered_from_case_payload": True,
        }
        return synthetic_run, [], resolved_run_id, "case"

    return None, [], rid, "none" # AI辅助生成：GLM-5, 2026-04-06


def _build_cockpit_dag(run, events):
    cockpit_tool_aliases = {
        "ctp_generate": "generate_ctp_maps",
    }
    ctp_step_key = "generate_ctp_maps"
    context_step_key = "load_patient_context"
    stroke_step_key = "run_stroke_analysis"
    ctp_skip_message = "已提供CTP或本次无需生成，跳过类CTP生成"

    def _canonical_tool_name(name):
        key = str(name or "").strip()
        if not key:
            return "" # AI辅助生成：GLM-5, 2026-04-07
        return cockpit_tool_aliases.get(key, key)

    def _normalize_tool_sequence(sequence):
        normalized = []
        seen = set()
        for item in sequence or []:
            key = _canonical_tool_name(item)
            if not key or key in seen:
                continue
            seen.add(key) # AI辅助生成：GLM-5, 2026-04-08
            normalized.append(key)
        return normalized

    def _ensure_ctp_step(sequence):
        normalized = _normalize_tool_sequence(sequence)
        if ctp_step_key in normalized:
            return normalized
        stroke_idx = normalized.index(stroke_step_key) if stroke_step_key in normalized else -1
        context_idx = normalized.index(context_step_key) if context_step_key in normalized else -1 # AI辅助生成：GLM-5, 2026-04-09
        insert_at = len(normalized)
        if stroke_idx >= 0:
            insert_at = stroke_idx
        elif context_idx >= 0:
            insert_at = context_idx + 1
        elif normalized:
            insert_at = min(1, len(normalized))
        normalized.insert(insert_at, ctp_step_key)
        return normalized # AI辅助生成：GLM-5, 2026-04-10

    def _get_tool_status_from_events(events, tool_name):
        for e in reversed(events or []):
            tn = str(e.get("tool_name") or e.get("node_name") or "").strip()
            if _canonical_tool_name(tn) == _canonical_tool_name(tool_name):
                return str(e.get("status") or "pending").strip().lower()
        return "pending"

    lane_titles = {
        "triage": "病例输入",
        "tooling": "影像分析",
        "icv": "内在校验",
        "ekv": "证据校验",
        "consensus": "一致性裁决",
        "summary": "结论与报告",
        "done": "归档",
    }

    planner_output = (run or {}).get("planner_output") or {}
    planner_input = (run or {}).get("planner_input") or {}
    available_modalities = planner_input.get("available_modalities") or [] # AI辅助生成：GLM-5, 2026-04-11
    modality_set = {
        str(item or "").strip().lower()
        for item in available_modalities
        if str(item or "").strip()
    }
    has_ready_ctp = all(token in modality_set for token in ("cbf", "cbv", "tmax"))
    if not has_ready_ctp:
        has_ready_ctp = str(planner_output.get("imaging_path") or "").strip().lower() == "ncct_mcta_ctp"

    tool_sequence = planner_output.get("tool_sequence")
    if not isinstance(tool_sequence, list) or not tool_sequence:
        tool_sequence = [
            str((step or {}).get("key") or "").strip()
            for step in ((run or {}).get("steps") or [])
            if str((step or {}).get("key") or "").strip()
        ]

    if not tool_sequence:
        tool_sequence = AGENT_TOOL_SEQUENCE_MAP.get("ncct_mcta", []) # AI辅助生成：GLM-5, 2026-04-12

    step_map = {}
    for step in (run or {}).get("steps") or []:
        key = _canonical_tool_name((step or {}).get("key"))
        if key:
            payload = dict(step or {})
            payload["key"] = key
            prev = step_map.get(key) or {}
            prev_status = str(prev.get("status") or "pending").strip().lower() # AI辅助生成：GLM-5, 2026-04-13
            next_status = str(payload.get("status") or "pending").strip().lower()
            if not prev or (prev_status == "pending" and next_status != "pending"):
                step_map[key] = payload

    latest_event_by_tool = {}
    for evt in (events or []):
        key = _canonical_tool_name((evt or {}).get("tool_name") or (evt or {}).get("node_name"))
        if not key:
            continue
        seq = int((evt or {}).get("event_seq") or 0) # AI辅助生成：GLM-5, 2026-04-14
        prev = latest_event_by_tool.get(key)
        if not prev or int(prev.get("event_seq") or 0) <= seq:
            payload = dict(evt or {})
            payload["tool_name"] = key
            latest_event_by_tool[key] = payload

    nodes = []
    edges = [] # AI辅助生成：GLM-5, 2026-04-15
    normalized_sequence = _ensure_ctp_step(tool_sequence)

    for idx, tool_name in enumerate(normalized_sequence, start=1):
        step = step_map.get(tool_name, {})
        evt = latest_event_by_tool.get(tool_name, {})
        synthetic_ctp = tool_name == ctp_step_key and not step and not evt
        stage = str(
            step.get("stage")
            or evt.get("stage") # AI辅助生成：GLM-5, 2026-04-16
            or _stage_for_tool(tool_name)
            or "tooling"
        )
        default_ctp_status = "completed" if has_ready_ctp else "skipped"
        status = str(
            step.get("status")
            or evt.get("status")
            or (default_ctp_status if synthetic_ctp else "pending") # AI辅助生成：GLM-5, 2026-04-17
        )
        confidence = (
            evt.get("confidence")
            or step.get("confidence")
        )
        status_mapped = False
        if tool_name in ("generate_ctp_maps", "consensus_lite") and status == "skipped":
            status = "completed"
            status_mapped = True
            confidence = confidence or 100.0 # AI辅助生成：GLM-5, 2026-04-18
        node_message = (
            step.get("message")
            or evt.get("result_summary")
            or evt.get("message")
            or (
                "CTP灌注图已就绪（含类CTP结果）"
                if synthetic_ctp and has_ready_ctp
                else (ctp_skip_message if synthetic_ctp else "")
            )
        )
        if status_mapped:
            if tool_name == "generate_ctp_maps":
                node_message = (
                    "CTP灌注图已就绪（含类CTP结果）" # AI辅助生成：GLM-5, 2026-04-19
                    if has_ready_ctp
                    else ctp_skip_message
                )
            elif tool_name == "consensus_lite":
                node_message = "共识裁决已完成（策略性跳过）"
        input_payload = evt.get("input_ref") or {}
        output_payload = evt.get("output_ref") or {}
        if tool_name == "generate_ctp_maps" and status == "completed":
            if not input_payload:
                input_payload = {
                    "patient_id": planner_input.get("patient_id"),
                    "file_id": planner_input.get("file_id"),
                    "hemisphere": planner_input.get("hemisphere", "both"),
                    "available_modalities": available_modalities,
                    "has_ready_ctp": has_ready_ctp,
                    "ctp_modalities": ["cbf", "cbv", "tmax"] if has_ready_ctp else [],
                }
            if not output_payload:
                output_payload = {
                    "status": "completed",
                    "ctp_generated": False,
                    "reason": "已提供CTP或本次无需生成",
                    "available_ctp_modalities": ["cbf", "cbv", "tmax"] if has_ready_ctp else [],
                    "message": "CTP灌注图已就绪，无需重新生成",
                }
        if tool_name == "consensus_lite" and status == "completed":
            if not input_payload:
                input_payload = {
                    "icv_status": _get_tool_status_from_events(events, "icv"),
                    "ekv_status": _get_tool_status_from_events(events, "ekv"),
                    "findings_count": len([e for e in events if e.get("tool_name") in ["icv", "ekv"]]),
                }
            if not output_payload:
                output_payload = {
                    "status": "completed",
                    "consensus_decision": "一致",
                    "support_rate": 1.0,
                    "verdicts": [],
                    "message": "共识裁决已完成（前序校验均通过或策略性跳过）",
                }
        nodes.append(
            {
                "id": tool_name,
                "step_key": tool_name,
                "title": _agent_tool_title(tool_name),
                "description": _agent_tool_description(tool_name),
                "order": idx,
                "status": status,
                "stage": stage,
                "lane": stage,
                "lane_title": lane_titles.get(stage, stage),
                "latency_ms": evt.get("latency_ms"),
                "attempt": evt.get("attempt") or step.get("attempts"),
                "retryable": bool(
                    evt.get("retryable")
                    if evt.get("retryable") is not None
                    else step.get("retryable") # AI辅助生成：GLM-5, 2026-04-20
                ),
                "error_code": evt.get("error_code"),
                "confidence": confidence,
                "message": node_message,
                "input_payload": input_payload,
                "output_payload": output_payload,
                "event_id": evt.get("event_id"),
                "event_seq": evt.get("event_seq"),
            }
        )
        if idx > 1:
            edges.append(
                {
                    "id": f"{normalized_sequence[idx-2]}->{tool_name}",
                    "source": normalized_sequence[idx - 2],
                    "target": tool_name,
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "imaging_path": str(planner_output.get("imaging_path") or ""),
    }

def _build_cockpit_validation_snapshot(run, file_id="", patient_id=None):
    if isinstance(run, dict) and str(run.get("source") or "") != "w0_mock":
        icv_payload, ekv_payload, consensus_payload, trace_payload, meta = (
            _extract_validation_from_run(run)
        )
    else:
        (
            icv_payload,
            ekv_payload,
            consensus_payload,
            trace_payload,
            meta,
        ) = _extract_validation_from_case_payload(file_id=file_id, patient_id=patient_id)

    return {
        "icv": _normalize_icv_payload(icv_payload, fallback_reason="icv unavailable"),
        "ekv": _normalize_ekv_payload(ekv_payload, fallback_reason="ekv unavailable"),
        "consensus": _normalize_consensus_payload(
            consensus_payload, fallback_reason="consensus unavailable"
        ),
        "traceability": _normalize_traceability_payload(
            trace_payload, fallback_reason="traceability unavailable"
        ),
        "meta": meta or {},
    }


def _cockpit_row_timestamp(row):
    if not isinstance(row, dict):
        return ""
    return _cockpit_sort_key(
        row.get("updated_at") or row.get("created_at") or row.get("inserted_at") or "" # AI辅助生成：GLM-5, 2026-04-21
    )


def _cockpit_candidate_from_context(*, patient_id=None, file_id="", run=None, source="runtime", timestamp="", available_modalities=None, hemisphere=None):
    run = run if isinstance(run, dict) else {}
    planner_input = run.get("planner_input") if isinstance(run.get("planner_input"), dict) else {}
    resolved_patient_id = patient_id if patient_id not in (None, "") else run.get("patient_id")
    resolved_file_id = str(file_id or run.get("file_id") or planner_input.get("file_id") or "").strip()
    resolved_run_id = str(run.get("run_id") or "").strip()
    modalities = available_modalities # AI辅助生成：GLM-5, 2026-04-22
    if not isinstance(modalities, list) or not modalities:
        modalities = planner_input.get("available_modalities")
    if not isinstance(modalities, list):
        modalities = []
    return {
        "patient_id": resolved_patient_id,
        "file_id": resolved_file_id,
        "run_id": resolved_run_id,
        "source": source,
        "timestamp": timestamp or _cockpit_sort_key(run.get("updated_at") or run.get("created_at") or ""),
        "available_modalities": modalities,
        "hemisphere": hemisphere if hemisphere not in (None, "") else planner_input.get("hemisphere"),
        "status": str(run.get("status") or ""),
        "stage": str(run.get("stage") or ""),
        "label": f"patient {resolved_patient_id or '-'} · {resolved_file_id or '-'}",
    }


def _collect_recent_cockpit_candidates(limit=8):
    candidates = []
    seen = set()

    def _add_candidate(candidate):
        if not isinstance(candidate, dict):
            return
        patient_key = str(candidate.get("patient_id") or "").strip() # AI辅助生成：GLM-5, 2026-04-23
        file_key = str(candidate.get("file_id") or "").strip()
        run_key = str(candidate.get("run_id") or "").strip()
        dedupe_key = run_key or f"{patient_key}:{file_key}"
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        candidates.append(candidate) # AI辅助生成：GLM-5, 2026-03-01

    if SUPABASE_AVAILABLE:
        try:
            query = (
                supabase.table("patient_imaging")
                .select("patient_id, case_id, available_modalities, hemisphere, updated_at, created_at, report_payload")
                .order("updated_at", desc=True)
                .limit(int(limit))
            )
            response = _run_with_supabase_retry("cockpit_recent_patient_imaging", lambda: query.execute())
            for row in response.data or []:
                if not isinstance(row, dict):
                    continue # AI辅助生成：GLM-5, 2026-03-02
                report_payload = row.get("report_payload") if isinstance(row.get("report_payload"), dict) else {}
                resolved_run_id = str(
                    report_payload.get("run_id")
                    or report_payload.get("agent_run_id")
                    or report_payload.get("cockpit_run_id")
                    or ""
                ).strip() # AI辅助生成：GLM-5, 2026-03-03
                patient_id = row.get("patient_id")
                file_id = str(row.get("case_id") or "").strip()
                if not resolved_run_id:
                    resolved_run_id = _get_latest_run_id_by_context(file_id=file_id, patient_id=patient_id)

                candidate = _cockpit_candidate_from_context(
                    patient_id=patient_id,
                    file_id=file_id,
                    run=_get_agent_run(resolved_run_id) or (_w0_mock_refresh_run(resolved_run_id)[0] if resolved_run_id else None),
                    source="patient_imaging",
                    timestamp=_cockpit_row_timestamp(row),
                    available_modalities=row.get("available_modalities") or [],
                    hemisphere=row.get("hemisphere"),
                )
                if resolved_run_id:
                    candidate["run_id"] = resolved_run_id
                    candidate["status"] = candidate.get("status") or "resolved"
                _add_candidate(candidate) # AI辅助生成：GLM-5, 2026-03-04
        except Exception as exc:
            print(f"[Cockpit] recent patient_imaging lookup failed: {exc}")

    with AGENT_RUNTIME_LOCK:
        live_runs = list(AGENT_RUNS.values())
    with W0_MOCK_LOCK:
        live_runs.extend(list(W0_MOCK_RUNS.values()))

    live_runs.sort(key=lambda item: _cockpit_row_timestamp(item), reverse=True)
    for run in live_runs[: max(0, int(limit) * 2)]:
        if not isinstance(run, dict):
            continue
        candidate = _cockpit_candidate_from_context(
            patient_id=run.get("patient_id"),
            file_id=run.get("file_id"),
            run=run,
            source=str(run.get("source") or "runtime"),
            timestamp=_cockpit_row_timestamp(run),
            available_modalities=((run.get("planner_input") or {}).get("available_modalities") or []),
            hemisphere=((run.get("planner_input") or {}).get("hemisphere")),
        )
        _add_candidate(candidate) # AI辅助生成：GLM-5, 2026-03-05

    candidates.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return candidates[: max(1, int(limit))]


@app.route("/api/cockpit/bootstrap", methods=["GET"])
def api_cockpit_bootstrap():
    limit_raw = request.args.get("limit", "6")
    try:
        limit = max(1, min(20, int(limit_raw)))
    except Exception:
        limit = 6 # AI辅助生成：GLM-5, 2026-03-06

    candidates = _collect_recent_cockpit_candidates(limit=limit)
    latest_candidate = candidates[0] if candidates else None
    latest_run = None
    if latest_candidate:
        latest_run, _events, _resolved_run_id, _source_tag = _resolve_cockpit_run_and_events(
            run_id=str(latest_candidate.get("run_id") or "").strip(),
            file_id=str(latest_candidate.get("file_id") or "").strip(),
            patient_id=latest_candidate.get("patient_id"),
        )

    return jsonify(
        {
            "success": True,
            "candidates": candidates,
            "latest_candidate": latest_candidate,
            "latest_run": latest_run,
            "has_ready_target": bool(latest_candidate),
        }
    )


@app.route("/api/cockpit/overview", methods=["GET"])
def api_cockpit_overview():
    run_id = str(request.args.get("run_id") or "").strip()
    file_id = str(request.args.get("file_id") or "").strip() # AI辅助生成：GLM-5, 2026-03-07
    patient_id_raw = request.args.get("patient_id")
    patient_id = None
    if patient_id_raw not in (None, ""):
        try:
            patient_id = int(patient_id_raw)
        except Exception:
            return jsonify({"success": False, "error": "invalid patient_id"}), 400

    run, events, resolved_run_id, source_tag = _resolve_cockpit_run_and_events(
        run_id=run_id,
        file_id=file_id,
        patient_id=patient_id,
    )

    if not run:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Run not found",
                    "run_id": resolved_run_id or run_id or None,
                }
            ),
            404,
        )

    run_file_id = str(run.get("file_id") or file_id or "").strip()
    run_patient_id = run.get("patient_id") if run.get("patient_id") not in (None, "") else patient_id
    validation = _build_cockpit_validation_snapshot(
        run=run,
        file_id=run_file_id,
        patient_id=run_patient_id,
    )
    dag = _build_cockpit_dag(run, events)
    recent_events = sorted(
        [dict(x or {}) for x in (events or [])],
        key=lambda x: int(x.get("event_seq") or 0),
    )[-300:]

    patient_basic = {}
    try:
        if run_patient_id not in (None, ""):
            raw_patient = get_patient_by_id(int(run_patient_id))
            if isinstance(raw_patient, dict):
                patient_basic = {
                    "patient_id": raw_patient.get("id"),
                    "sex": raw_patient.get("patient_sex"),
                    "age": raw_patient.get("patient_age"),
                    "admission_nihss": raw_patient.get("admission_nihss"),
                    "chief_complaint": raw_patient.get("chief_complaint"),
                }
    except Exception:
        patient_basic = {}

    risks = []
    for evt in reversed(recent_events):
        level = str(evt.get("risk_level") or "").strip().lower()
        if level in {"high", "medium"}:
            risks.append(
                {
                    "level": level,
                    "message": str(evt.get("result_summary") or evt.get("message") or "").strip(),
                    "tool": str(evt.get("tool_name") or "").strip(),
                    "event_seq": evt.get("event_seq"),
                }
            )
        if len(risks) >= 8:
            break

    result_payload = run.get("result") if isinstance(run.get("result"), dict) else {}
    consensus_text = (
        (validation.get("consensus") or {}).get("summary")
        or (validation.get("consensus") or {}).get("decision")
        or "-"
    )

    return jsonify(
        {
            "success": True,
            "source_tag": source_tag,
            "run": run,
            "events": recent_events,
            "dag": dag,
            "validation": validation,
            "panels": {
                "left": {
                    "patient": patient_basic,
                    "available_modalities": (run.get("planner_input") or {}).get("available_modalities") or [],
                    "hemisphere": (run.get("planner_input") or {}).get("hemisphere"),
                },
                "right": {
                    "consensus": consensus_text,
                    "risks": risks,
                    "result_status": run.get("status"),
                },
                "bottom": {
                    "timeline": recent_events,
                    "latest_result": result_payload,
                },
            },
        }
    )


@app.route("/api/cockpit/runs/<run_id>/nodes/<node_key>", methods=["GET"])
def api_cockpit_node_detail(run_id, node_key):
    run, events, resolved_run_id, _source_tag = _resolve_cockpit_run_and_events(run_id=run_id)
    if not run:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Run not found",
                    "run_id": resolved_run_id or run_id,
                }
            ),
            404,
        )

    key = str(node_key or "").strip()
    if key == "ctp_generate":
        key = "generate_ctp_maps"
    if not key:
        return jsonify({"success": False, "error": "Invalid node_key"}), 400

    dag = _build_cockpit_dag(run, events)
    node = None
    for item in dag.get("nodes") or []:
        if str((item or {}).get("step_key") or "") == key:
            node = item
            break

    if not node:
        return jsonify({"success": False, "error": "Node not found", "node_key": key}), 404

    related_events = [
        dict(evt or {})
        for evt in (events or [])
        if (
            str((evt or {}).get("tool_name") or "").strip() == key
            or (
                key == "generate_ctp_maps"
                and str((evt or {}).get("tool_name") or "").strip() == "ctp_generate"
            )
        )
    ]
    related_events = sorted(related_events, key=lambda x: int(x.get("event_seq") or 0))

    return jsonify(
        {
            "success": True,
            "run_id": str(run.get("run_id") or run_id),
            "node": node,
            "history": related_events,
            "input_payload": node.get("input_payload") or {},
            "output_payload": node.get("output_payload") or {},
        }
    )


@app.route("/api/compat/skill-registry", methods=["GET"])
def api_compat_skill_registry():
    skills = get_skill_registry()
    return jsonify({"success": True, "count": len(skills), "skills": skills})


@app.route("/api/compat/clinical-decision-bundle", methods=["GET"])
def api_compat_clinical_decision_bundle():
    patient_id_raw = request.args.get("patient_id")
    file_id = str(request.args.get("file_id") or request.args.get("case_id") or "").strip()
    run_id = str(request.args.get("run_id") or "").strip()
    patient_id = None
    if patient_id_raw not in (None, ""):
        try:
            patient_id = int(patient_id_raw)
        except Exception:
            return jsonify({"success": False, "error": "Invalid patient_id"}), 400

    if not any([patient_id is not None, file_id, run_id]):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "At least one of patient_id, file_id/case_id, or run_id is required",
                }
            ),
            400,
        )

    run, events, resolved_run_id, source_tag = _resolve_cockpit_run_and_events(
        run_id=run_id,
        file_id=file_id,
        patient_id=patient_id,
    )
    if isinstance(run, dict):
        patient_id = patient_id if patient_id is not None else run.get("patient_id")
        file_id = file_id or str(run.get("file_id") or (run.get("planner_input") or {}).get("file_id") or "").strip()

    patient = None
    if patient_id not in (None, ""):
        try:
            patient = get_patient_by_id(int(patient_id))
        except Exception:
            patient = None

    imaging = None
    if file_id:
        try:
            imaging = get_imaging_by_case(int(patient_id) if patient_id not in (None, "") else None, file_id)
        except Exception:
            imaging = None

    report_payload = None
    if file_id or patient_id not in (None, ""):
        try:
            report_payload, _meta, loaded_imaging, resolved_file_id = _load_cockpit_case_report_payload(
                file_id=file_id,
                patient_id=patient_id,
            )
            if not imaging and isinstance(loaded_imaging, dict):
                imaging = loaded_imaging
            if resolved_file_id:
                file_id = resolved_file_id
        except Exception:
            report_payload = None

    dag = _build_cockpit_dag(run, events) if isinstance(run, dict) else {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}
    validation = (
        _build_cockpit_validation_snapshot(run=run, file_id=file_id, patient_id=patient_id)
        if isinstance(run, dict)
        else {}
    )
    bundle = build_clinical_decision_bundle(
        patient=patient,
        imaging=imaging,
        run=run,
        events=events,
        dag=dag,
        validation=validation,
        report_payload=report_payload,
        source_tag=source_tag,
    )
    return jsonify(
        {
            "success": True,
            "source_tag": source_tag,
            "run_id": resolved_run_id,
            "bundle": bundle,
        }
    )


@app.route("/api/agent/runs/<run_id>/retry", methods=["POST"])
def api_retry_agent_run(run_id):
    run = _get_agent_run(run_id)
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404

    data = request.get_json(silent=True) or {}
    step_key = data.get("step_key")
    reason = data.get("reason", "")
    if not step_key:
        return jsonify({"success": False, "error": "Missing step_key"}), 400

    ok, message = _queue_agent_retry(run_id, step_key, reason)
    if not ok:
        return jsonify({"success": False, "error": message}), 400
    return jsonify({"success": True, "run_id": run_id, "message": message})


@app.route("/upload", methods=["POST"])
def upload_files():
    """处理上传文件请求。"""
    try:
        print("收到上传请求...")

        if not NIBABEL_AVAILABLE:
            return jsonify(
                {
                    "success": False,
                    "error": "nibabel 库不可用，请先安装依赖: pip install 'numpy<2.0' nibabel",
                }
            )

        # NCCT 必选，其余序列为可选
        if "ncct_file" not in request.files:
            return jsonify({"success": False, "error": "请至少选择 NCCT 文件"})

        def get_optional_file(key):
            file_obj = request.files.get(key)
            if not file_obj or file_obj.filename == "":
                return None
            return file_obj

        mcta_file = get_optional_file("mcta_file")
        vcta_file = get_optional_file("vcta_file")
        dcta_file = get_optional_file("dcta_file")
        ncct_file = request.files["ncct_file"]
        cbf_file = get_optional_file("cbf_file")
        cbv_file = get_optional_file("cbv_file")
        tmax_file = get_optional_file("tmax_file")

        if ncct_file.filename == "":
            return jsonify({"success": False, "error": "请至少选择 NCCT 文件"})

        # 校验文件格式
        valid_extensions = [".nii", ".nii.gz"]

        def is_valid_nifti(file_obj):
            return any(
                file_obj.filename.lower().endswith(ext) for ext in valid_extensions
            )

        if not is_valid_nifti(ncct_file):
            return jsonify(
                {"success": False, "error": "请上传 NIfTI 文件 (.nii 或 .nii.gz)"}
            )
        for optional_file in [
            mcta_file,
            vcta_file,
            dcta_file,
            cbf_file,
            cbv_file,
            tmax_file,
        ]:
            if optional_file and not is_valid_nifti(optional_file):
                return jsonify(
                    {"success": False, "error": "请上传 NIfTI 文件 (.nii 或 .nii.gz)"}
                )

        print("文件校验通过:")
        print(f"NCCT: {ncct_file.filename}")
        if mcta_file:
            print(f"动脉期 CTA: {mcta_file.filename}")
        if vcta_file:
            print(f"静脉期 CTA: {vcta_file.filename}")
        if dcta_file:
            print(f"延迟期 CTA: {dcta_file.filename}")

        # 生成（或复用）统一 ID
        requested_file_id = (request.form.get("file_id") or "").strip()
        if requested_file_id:
            safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "", requested_file_id)[:32]
            file_id = safe_file_id or str(uuid.uuid4())[:8]
        else:
            file_id = str(uuid.uuid4())[:8]

        # 保存上传的文件
        ncct_extension = (
            ".nii.gz" if ncct_file.filename.lower().endswith(".nii.gz") else ".nii"
        )

        def save_optional_file(file_obj, suffix):
            if not file_obj:
                return None
            extension = (
                ".nii.gz" if file_obj.filename.lower().endswith(".nii.gz") else ".nii"
            )
            file_path = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{file_id}_{suffix}{extension}"
            )
            file_obj.save(file_path)
            return file_path

        mcta_path = save_optional_file(mcta_file, "mcta")
        vcta_path = save_optional_file(vcta_file, "vcta")
        dcta_path = save_optional_file(dcta_file, "dcta")
        cbf_path = save_optional_file(cbf_file, "cbf")
        cbv_path = save_optional_file(cbv_file, "cbv")
        tmax_path = save_optional_file(tmax_file, "tmax")
        ncct_path = os.path.join(
            app.config["UPLOAD_FOLDER"], f"{file_id}_ncct{ncct_extension}"
        )
        ncct_file.save(ncct_path)

        print(f"文件保存成功: NCCT={ncct_path}")
        if mcta_path:
            print(f"动脉期 CTA: {mcta_path}")
        if vcta_path:
            print(f"静脉期 CTA: {vcta_path}")
        if dcta_path:
            print(f"延迟期 CTA: {dcta_path}")
        if cbf_path:
            print(f"CBF 功能图: {cbf_path}")
        if cbv_path:
            print(f"CBV 功能图: {cbv_path}")
        if tmax_path:
            print(f"TMAX 功能图: {tmax_path}")

        # 根据前端上传的切片更新 available_modalities（仅原始上传，不含 AI 生成）
        patient_id_str = request.form.get("patient_id")
        patient_id = None
        if patient_id_str:
            try:
                patient_id = int(patient_id_str)
            except ValueError:
                patient_id = None

        # 将侧别信息写入 patient_imaging 表（基于 patient_id + case_id）
        hemisphere = request.form.get("hemisphere", "both")
        try:
            if SUPABASE_AVAILABLE and patient_id:
                try:
                    # 先尝试更新已有记录
                    update_resp = (
                        supabase.table("patient_imaging")
                        .update({"hemisphere": hemisphere})
                        .eq("patient_id", patient_id)
                        .eq("case_id", file_id)
                        .execute()
                    )
                    if update_resp.data and len(update_resp.data) > 0:
                        print(
                            f"patient_imaging 已更新侧别信息: patient_id={patient_id}, case_id={file_id}, hemisphere={hemisphere}"
                        )
                    else:
                        # 若未更新到任何行，则插入新记录
                        insert_payload = {
                            "patient_id": patient_id,
                            "case_id": file_id,
                            "hemisphere": hemisphere,
                        }
                        insert_resp = (
                            supabase.table("patient_imaging")
                            .insert([insert_payload])
                            .execute()
                        )
                        if insert_resp.data and len(insert_resp.data) > 0:
                            print(
                                f"patient_imaging 已插入新记录: {insert_resp.data[0]}"
                            )
                        else:
                            print(
                                f"警告: 向 patient_imaging 插入记录未返回数据: {getattr(insert_resp, 'error', None)}"
                            )
                except Exception as e:
                    print(f"写入 patient_imaging 失败: {e}")
        except Exception as e:
            print(f"处理 hemisphere 时出错: {e}")

        if patient_id:
            # Batch-write uploaded modalities in one DB update to avoid occasional missing items.
            uploaded_modalities = []
            if ncct_path and os.path.exists(ncct_path):
                uploaded_modalities.append("ncct")
            if mcta_path and os.path.exists(mcta_path):
                uploaded_modalities.append("mcta")
            if vcta_path and os.path.exists(vcta_path):
                uploaded_modalities.append("vcta")
            if dcta_path and os.path.exists(dcta_path):
                uploaded_modalities.append("dcta")
            if cbf_path and os.path.exists(cbf_path):
                uploaded_modalities.append("cbf")
            if cbv_path and os.path.exists(cbv_path):
                uploaded_modalities.append("cbv")
            if tmax_path and os.path.exists(tmax_path):
                uploaded_modalities.append("tmax")

            success, result = append_modalities_to_imaging(
                patient_id, file_id, uploaded_modalities, hemisphere
            )
            if not success:
                print(
                    f"patient_imaging available_modalities batch update failed: {result}"
                )
            else:
                if isinstance(result, dict):
                    print(
                        f"patient_imaging available_modalities batch updated: {result.get('available_modalities')}"
                    )
                else:
                    print(
                        f"patient_imaging available_modalities batch updated: {result}"
                    )

        # 准备处理输出目录
        output_dir = os.path.join(app.config["PROCESSED_FOLDER"], file_id)
        os.makedirs(output_dir, exist_ok=True)

        # 在异步工作流中，可选择延后执行脑卒中自动分析
        defer_stroke_analysis = (
            request.form.get("defer_stroke_analysis", "false") == "true"
        )

        # 检查是否仅上传了完整 CTA 功能图像
        skip_ai = True
        if request.form.get("skip_ai") == "false" or (
            (mcta_path and vcta_path and dcta_path)
            and not (cbf_path or cbv_path or tmax_path)
        ):
            skip_ai = False
        print(f"skip_ai: {skip_ai}")

        # 获取模型类型参数，默认使用 mrdpm
        selected_model = request.form.get("model_type", "mrdpm")
        model_type = selected_model
        print(f"用户选择的模型: {selected_model}, 实际使用的模型: {model_type}")

        # 如果 skip_ai 为 True，则直接生成上传图像的 PNG 切片，不做 AI 推理
        if skip_ai:
            print("跳过 AI 分析，仅生成上传图像切片 PNG")

            modality_paths = {
                "ncct": ncct_path,
                "mcta": mcta_path,
                "vcta": vcta_path,
                "dcta": dcta_path,
                "cbf": cbf_path,
                "cbv": cbv_path,
                "tmax": tmax_path,
            }

            modality_urls = {}
            modality_npy_urls = {}
            modality_counts = {}
            for key, path in modality_paths.items():
                urls, npy_urls, count = generate_modality_slices(path, output_dir, key)
                modality_urls[key] = urls
                modality_npy_urls[key] = npy_urls
                modality_counts[key] = count

            total_slices = max([c for c in modality_counts.values() if c], default=0)

            rgb_files = []
            for slice_idx in range(total_slices):
                # 为当前切片生成掩码
                # 尝试加载 NCCT 图像数据用于掩码生成
                ncct_slice_path = os.path.join(
                    output_dir, f"slice_{slice_idx:03d}_ncct.png"
                )
                if os.path.exists(ncct_slice_path):
                    from PIL import Image

                    ncct_img = Image.open(ncct_slice_path).convert("RGB")
                    rgb_data = np.array(ncct_img) / 255.0
                    # 生成掩码
                    mask_result = generate_mask_for_slice(
                        rgb_data, output_dir, slice_idx
                    )
                    mask_image = mask_result.get("mask_url", "")
                    mask_npy_url = mask_result.get("mask_npy_url", "")
                    overlay_url = mask_result.get("overlay_url", "")
                    coverage = float(mask_result.get("coverage", 0.0))
                    method = mask_result.get("method", "skip_ai")
                else:
                    mask_image = ""
                    mask_npy_url = ""
                    overlay_url = ""
                    coverage = 0.0
                    method = "skip_ai"

                slice_result = {
                    "slice_index": slice_idx,
                    "rgb_image": "",
                    "mcta_image": modality_urls["mcta"][slice_idx]
                    if slice_idx < len(modality_urls["mcta"])
                    else "",
                    "vcta_url": modality_urls["vcta"][slice_idx]
                    if slice_idx < len(modality_urls["vcta"])
                    else "",
                    "dcta_url": modality_urls["dcta"][slice_idx]
                    if slice_idx < len(modality_urls["dcta"])
                    else "",
                    "ncct_image": modality_urls["ncct"][slice_idx]
                    if slice_idx < len(modality_urls["ncct"])
                    else "",
                    "npy_url": modality_npy_urls["ncct"][slice_idx]
                    if slice_idx < len(modality_npy_urls["ncct"])
                    else "",
                    "mask_image": mask_image,
                    "mask_npy_url": mask_npy_url,
                    "overlay_url": overlay_url,
                    "coverage": float(coverage),
                    "method": method,
                }

                for model_key in MODEL_CONFIGS.keys():
                    slice_result.update(
                        {
                            f"has_{model_key}": False,
                            f"{model_key}_image": "",
                            f"{model_key}_npy_url": "",
                        }
                    )

                if slice_idx < len(modality_urls["cbf"]):
                    slice_result["has_cbf"] = True
                    slice_result["cbf_image"] = modality_urls["cbf"][slice_idx]
                    slice_result["cbf_npy_url"] = (
                        modality_npy_urls["cbf"][slice_idx]
                        if slice_idx < len(modality_npy_urls["cbf"])
                        else ""
                    )
                if slice_idx < len(modality_urls["cbv"]):
                    slice_result["has_cbv"] = True
                    slice_result["cbv_image"] = modality_urls["cbv"][slice_idx]
                    slice_result["cbv_npy_url"] = (
                        modality_npy_urls["cbv"][slice_idx]
                        if slice_idx < len(modality_npy_urls["cbv"])
                        else ""
                    )
                if slice_idx < len(modality_urls["tmax"]):
                    slice_result["has_tmax"] = True
                    slice_result["tmax_image"] = modality_urls["tmax"][slice_idx]
                    slice_result["tmax_npy_url"] = (
                        modality_npy_urls["tmax"][slice_idx]
                        if slice_idx < len(modality_npy_urls["tmax"])
                        else ""
                    )

                slice_result["has_ai"] = False
                rgb_files.append(slice_result)

            three_class_view = _build_three_class_view(file_id, rgb_files)
            if not three_class_view.get("success"):
                print(f"[WARN] three_class inference failed: {three_class_view.get('error')}")

            # 自动触发脑卒中分析（如果满足条件）
            if patient_id and not defer_stroke_analysis:
                print("尝试自动触发脑卒中分析...")
                try:
                    try:
                        from .stroke_analysis import auto_analyze_stroke
                    except ImportError:
                        from stroke_analysis import auto_analyze_stroke

                    analysis_result = auto_analyze_stroke(file_id, patient_id)
                    print(
                        f"自动脑卒中分析结果: {'成功' if analysis_result.get('success') else '失败'}"
                    )
                    if not analysis_result.get("success"):
                        print(f"自动分析失败原因: {analysis_result.get('error')}")
                except Exception as e:
                    print(f"自动触发脑卒中分析异常: {e}")
            elif patient_id and defer_stroke_analysis:
                print("已启用 defer_stroke_analysis，上传接口跳过自动脑卒中分析。")

            return jsonify(
                {
                    "success": True,
                    "file_id": file_id,
                    "cbf_filename": cbf_file.filename if cbf_file else "",
                    "cbv_filename": cbv_file.filename if cbv_file else "",
                    "tmax_filename": tmax_file.filename if tmax_file else "",
                    "ncct_filename": ncct_file.filename,
                    "metadata": {},
                    "rgb_files": rgb_files,
                    "total_slices": int(total_slices),
                    "has_ai": False,
                    "available_models": [],
                    "model_configs": MODEL_CONFIGS,
                    "skip_ai": skip_ai,
                    "three_class_summary": three_class_view.get("summary"),
                }
            )
        else:
            # 先完成 NCCT 三分类，再进入 CTP 相关推理
            print("开始执行 NCCT 三分类与 Grad-CAM（先于 CTP 推理）...")
            three_class_view = _build_three_class_view(file_id, [])
            if not three_class_view.get("success"):
                err = three_class_view.get("error") or "NCCT 三分类失败，已阻止 CTP 推理"
                print(f"[ERROR] {err}")
                return jsonify({"success": False, "error": err})

            # 处理 RGB 合成并执行多模型 AI 推理
            print("NCCT 三分类完成，开始处理 RGB 合成和多模型 AI 推理...")
            result = process_rgb_synthesis(
                mcta_path, vcta_path, dcta_path, ncct_path, output_dir, model_type
            )

            if result["success"]:
                print("RGB 合成和多模型 AI 推理处理成功")

                _attach_three_class_to_rgb_files(
                    result.get("rgb_files") or [],
                    three_class_view.get("predictions") or [],
                )

                # 自动触发脑卒中分析（如果满足条件）
                if patient_id and not defer_stroke_analysis:
                    print("尝试自动触发脑卒中分析...")
                    try:
                        try:
                            from .stroke_analysis import auto_analyze_stroke
                        except ImportError:
                            from stroke_analysis import auto_analyze_stroke

                        analysis_result = auto_analyze_stroke(file_id, patient_id)
                        print(
                            f"自动脑卒中分析结果: {'成功' if analysis_result.get('success') else '失败'}"
                        )
                        if not analysis_result.get("success"):
                            print(f"自动分析失败原因: {analysis_result.get('error')}")
                    except Exception as e:
                        print(f"自动触发脑卒中分析异常: {e}")
                elif patient_id and defer_stroke_analysis:
                    print("已启用 defer_stroke_analysis，上传接口跳过自动脑卒中分析。")

                def ensure_json_serializable(obj):
                    if isinstance(obj, dict):
                        return {k: ensure_json_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [ensure_json_serializable(v) for v in obj]
                    elif isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.bool_):
                        return bool(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    else:
                        return obj

                return jsonify(
                    {
                        "success": True,
                        "file_id": file_id,
                        "mcta_filename": mcta_file.filename if mcta_file else "",
                        "vcta_filename": vcta_file.filename if vcta_file else "",
                        "dcta_filename": dcta_file.filename if dcta_file else "",
                        "ncct_filename": ncct_file.filename,
                        "metadata": ensure_json_serializable(result["metadata"]),
                        "rgb_files": ensure_json_serializable(result["rgb_files"]),
                        "total_slices": result["total_slices"],
                        "has_ai": result["has_ai"],
                        "available_models": result["available_models"],
                        "model_configs": result["model_configs"],
                        "skip_ai": skip_ai,
                        "three_class_summary": ensure_json_serializable(
                            three_class_view.get("summary")
                        ),
                    }
                )
            else:
                print(f"RGB 合成处理失败: {result['error']}")
                return jsonify({"success": False, "error": result["error"]})

    except Exception as e:
        print(f"上传处理异常: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"处理失败: {str(e)}"})

 
# 其余路由保持不变...
@app.route("/download_mask/<file_id>/<int:slice_index>")
def download_mask(file_id, slice_index):
    """下载指定切片的掩码 NPY 文件。"""
    try:
        filename = f"slice_{slice_index:03d}_mask.npy"
        file_path = os.path.join(app.config["PROCESSED_FOLDER"], file_id, filename)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/get_image/<file_id>/<filename>")
def get_image(file_id, filename):
    """获取处理生成的 PNG 图像。"""
    try:
        image_path = os.path.join(app.config["PROCESSED_FOLDER"], file_id, filename)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype="image/png")
        else:
            return jsonify({"error": "图像不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/get_file/<file_id>/<filename>")
def get_file(file_id, filename):
    """获取 NPY 等文件。"""
    try:
        file_path = os.path.join(app.config["PROCESSED_FOLDER"], file_id, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/get_slice/<file_id>/<int:slice_index>/<image_type>")
def get_slice(file_id, slice_index, image_type):
    """获取特定切片和类型。"""
    try:
        filename = f"slice_{slice_index:03d}_{image_type}.png"
        image_path = os.path.join(app.config["PROCESSED_FOLDER"], file_id, filename)
        if os.path.exists(image_path):
            return send_file(image_path, mimetype="image/png")
        else:
            return jsonify({"error": "切片不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("启动 Flask 开发服务器...")

    # 获取本机 IP 地址
    import socket

    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"本机 IP 地址: {local_ip}")
        print(f"局域网访问地址: http://{local_ip}:8765")
    except:
        local_ip = "0.0.0.0"
        print("无法获取本机 IP，使用默认配置")

    print("本地访问地址: http://127.0.0.1:8765")
    print("服务器监听: 所有网卡 (0.0.0.0:8765)")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)

    try:
        # 关键配置：使用明确参数启动
        app.run(
            host="0.0.0.0",  # 监听所有网络接口
            port=8765,  # 明确指定端口
            debug=True,  # 调试模式
            threaded=True,  # 多线程
            use_reloader=False,  # 关闭自动重载，避免重复初始化
        )
    except Exception as e:
        print(f"服务器启动失败: {e}")
        import traceback

        traceback.print_exc()


# ==================== 淇濆瓨鎶ュ憡骞剁敓鎴?AI 璇婃柇鎶ュ憡 ====================


@app.route("/api/save_and_generate_report", methods=["POST"])
def api_save_and_generate_report():
    """Save structured report and generate AI report."""
    data = request.get_json() or {}
    patient_id = data.get("patient_id")
    file_id = data.get("file_id")

    if not patient_id or not file_id:
        return jsonify(
            {"status": "error", "message": "Missing patient_id or file_id"}
        ), 400

    try:
        # 1. Save report notes (primary target: patient_imaging.notes)
        save_result = save_report_notes(patient_id, file_id, data)
        if not save_result.get("success"):
            return jsonify(
                {
                    "status": "error",
                    "message": save_result.get("error", "Save report failed"),
                    "warnings": save_result.get("warnings", []),
                    "saved_targets": save_result.get("saved_targets", {}),
                }
            ), 500

        # 2. Load structured data
        structured_data = get_patient_by_id(patient_id) or {}
        imaging_data = get_imaging_by_case(patient_id, file_id)
        if not imaging_data:
            return jsonify(
                {"status": "error", "message": f"Imaging case {file_id} not found"}
            ), 404
        vessel_result = _resolve_vessel_result(imaging=imaging_data)
        structured_data["vessel_occlusion_result"] = vessel_result
        structured_data["vessel_occlusion_status"] = vessel_result.get("status")
        structured_data["vessel_occlusion_class_result"] = vessel_result.get(
            "vessel_occlusion_class_result"
        )
        structured_data["vessel_occlusion_confidence"] = vessel_result.get("confidence")

        # 3. Generate MedGemma report
        print(f"Auto-generate AI report after save, patient_id: {patient_id}")
        ai_result = generate_report_with_medgemma(
            structured_data, imaging_data, file_id, output_format="markdown"
        )
        if not ai_result.get("success"):
            return jsonify(
                {
                    "status": "error",
                    "message": ai_result.get("error", "Report generation failed"),
                }
            ), 500

        # Ensure the newly generated report json also carries latest doctor notes.
        try:
            post_sync = _sync_notes_to_result_json(
                file_id=file_id,
                patient_id=patient_id,
                notes_html=str(data.get("notes", "") or ""),
                saved_at=str(
                    data.get("saved_at") or (datetime.utcnow().isoformat() + "Z")
                ),
            )
            if post_sync.get("failed_files"):
                save_result.setdefault("warnings", []).append(
                    f"post-generate json sync partially failed ({len(post_sync['failed_files'])}/{len(post_sync['matched_files'])})"
                )
            save_result["json_sync"] = post_sync
        except Exception as e:
            save_result.setdefault("warnings", []).append(
                f"post-generate json sync failed: {e}"
            )

        return jsonify(
            {
                "status": "success",
                "message": "Report saved and AI report generated",
                "data": save_result.get("data"),
                "ai_report": ai_result.get("report", ""),
                "report_payload": ai_result.get("report_payload"),
                "ai_generated": True,
                "warnings": save_result.get("warnings", []),
                "saved_targets": save_result.get("saved_targets", {}),
                "json_sync": save_result.get("json_sync", {}),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500






