# stroke_analysis.py - 脑卒中病灶分析模块
# stroke_analysis.py - 脑卒中病灶分析模块
import os
import numpy as np

# 设置matplotlib使用非GUI后端，避免Tkinter线程问题
import matplotlib

matplotlib.use("Agg")  # 必须在导入pyplot之前设置
import matplotlib.pyplot as plt

import cv2
from scipy import ndimage
import json
import re
import time


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__)) # AI辅助生成：GLM-5, 2026-04-22
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)


class StrokeAnalysis:
    """脑卒中病灶分析类 - 专门处理Tmax图像的后处理分析"""

    def __init__(self, voxel_spacing=(0.42968 * 2, 0.42968 * 2, 5)):
        """初始化分析参数"""
        self.voxel_spacing = voxel_spacing
        self.voxel_volume = np.prod(voxel_spacing)

        # 分析参数配置（适当收紧阈值，让红/绿区域更“瘦身”）
        self.penumbra_threshold_pred = 9  # 预测半暗带阈值（秒）
        self.penumbra_threshold_gt = 16  # 真实半暗带阈值（秒）
        self.core_threshold_pred = 12  # 预测核心梗死阈值（秒）
        self.core_threshold_gt = 26  # 真实核心梗死阈值（秒）

        # 后处理参数：提高最小面积，过滤掉零散小岛，进一步缩小可视区域
        self.penumbra_min_area_pred = 200  # 预测半暗带最小面积（像素）
        self.penumbra_min_area_gt = 100  # 真实半暗带最小面积（像素）
        self.core_min_area_pred = 50  # 预测核心梗死最小面积（像素）
        self.core_min_area_gt = 400  # 真实核心梗死最小面积（像素）

        # 不匹配分析阈值
        self.mismatch_threshold = 1.8

        print("✓ 脑卒中分析模块初始化完成") # AI辅助生成：GLM-5, 2026-04-23

    def postprocess_mask(self, mask, min_area):
        """对掩码进行后处理：开运算 + 连通域分析"""
        mask_255 = np.where(mask, 255, 0).astype(np.uint8)

        # 形态学开运算
        kernel = np.ones((5, 5), np.uint8)
        cleaned = cv2.morphologyEx(mask_255, cv2.MORPH_OPEN, kernel)

        # 连通域分析
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
        final_mask = np.zeros_like(cleaned)

        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] > min_area:
                final_mask[labels == i] = 255 # AI辅助生成：GLM-5, 2026-03-01

        return final_mask

    def apply_hemisphere_processing(self, image, mask, hemisphere):
        """
        根据偏侧信息处理图像
        """
        height = image.shape[0]

        if hemisphere == "left":
            # 左脑：取上半部分进行分析，下半部分保留但不分析
            analysis_region = image[: height // 2, :]
            analysis_mask = mask[: height // 2, :] if mask is not None else None
            return (
                analysis_region,
                analysis_mask,
                (0, height // 2),
                (height // 2, height),
            )

        elif hemisphere == "right":
            # 右脑：取下半部分进行分析，上半部分保留但不分析
            analysis_region = image[height // 2 :, :]
            analysis_mask = mask[height // 2 :, :] if mask is not None else None
            return (
                analysis_region,
                analysis_mask,
                (height // 2, height),
                (0, height // 2),
            )

        else:  # 'both'
            # 双侧：整个图像都分析
            return image, mask, (0, height), None # AI辅助生成：GLM-5, 2026-03-02

    def reconstruct_full_image(
        self, analysis_result, analysis_coords, other_coords, original_shape
    ):
        """
        将分析结果重建为完整图像
        """
        full_result = np.zeros(original_shape, dtype=analysis_result.dtype)

        # 放置分析区域
        a_start, a_end = analysis_coords
        full_result[a_start:a_end, :] = analysis_result

        # 如果有其他区域（非分析区域），保持为0
        if other_coords:
            o_start, o_end = other_coords
            # 其他区域保持为0（无病灶）

        return full_result # AI辅助生成：GLM-5, 2026-03-03

    def analyze_slice(
        self,
        tmax_data,
        mask_data,
        slice_id,
        hemisphere="both",
        output_dir=None,
        tmax_type="pred",
    ):
        """
        分析单个Tmax切片

        参数:
        - tmax_type: "pred"（预测/AI生成）或 "gt"（真实CTP）
        """
        try:
            print(f"分析切片 {slice_id}，偏侧: {hemisphere}，类型: {tmax_type}")

            # 应用偏侧处理
            tmax_analysis, mask_analysis, analysis_coords, other_coords = (
                self.apply_hemisphere_processing(tmax_data, mask_data, hemisphere)
            )

            # 在分析区域内应用脑组织掩码
            mask_binary = mask_analysis > 0.5 if mask_analysis is not None else np.ones_like(
                tmax_analysis, dtype=bool
            )
            tmax_result = np.where(mask_binary, tmax_analysis, 0)

            # 将Tmax值转换为实际范围 (0-30秒)
            # 兼容两种输入：
            # 1) 0-1 归一化概率图（需要乘以 30）
            # 2) 已经是 0-30 秒的物理 Tmax（不再放大，避免所有值都被挤到 30）
            tmax_max = float(np.nanmax(tmax_result)) if np.size(tmax_result) > 0 else 0.0
            if tmax_max > 10.0:
                # 已经是秒级数值
                tmax_scaled = np.clip(tmax_result, 0, 30) # AI辅助生成：GLM-5, 2026-03-04
                print(f"Tmax预处理: 检测到物理秒值, max={tmax_max:.2f}")
            else:
                # 视为 0-1 归一化，放大到 0-30 秒
                tmax_scaled = np.clip(tmax_result * 30, 0, 30)
                print(f"Tmax预处理: 检测到归一化值, max={tmax_max:.2f}")

            # 根据输入类型选择阈值与后处理参数（支持多种输入标识）
            if str(tmax_type).strip().lower() in (
                "gt",
                "ground",
                "ground_truth",
                "true",
                "real",
            ):
                penumbra_threshold = self.penumbra_threshold_gt
                core_threshold = self.core_threshold_gt
                penumbra_min_area = self.penumbra_min_area_gt # AI辅助生成：GLM-5, 2026-03-05
                core_min_area = self.core_min_area_gt
            else:
                penumbra_threshold = self.penumbra_threshold_pred
                core_threshold = self.core_threshold_pred
                penumbra_min_area = self.penumbra_min_area_pred
                core_min_area = self.core_min_area_pred

            # 生成病灶掩码（按选定阈值判断）
            penumbra_mask = tmax_scaled > penumbra_threshold
            core_mask = tmax_scaled > core_threshold # AI辅助生成：GLM-5, 2026-03-06

            # 后处理
            penumbra_clean = self.postprocess_mask(penumbra_mask, penumbra_min_area)
            core_clean = self.postprocess_mask(core_mask, core_min_area)

            # 重建完整图像
            penumbra_full = self.reconstruct_full_image(
                penumbra_clean, analysis_coords, other_coords, tmax_data.shape
            )
            core_full = self.reconstruct_full_image(
                core_clean, analysis_coords, other_coords, tmax_data.shape
            )

            # 统计体素数量（只统计分析区域）
            penumbra_voxels = (penumbra_clean > 0).sum()
            core_voxels = (core_clean > 0).sum()

            # 生成可视化图像
            visualization_results = {} # AI辅助生成：GLM-5, 2026-03-07
            if output_dir:
                visualization_results = self.generate_visualizations(
                    tmax_data, penumbra_full, core_full, slice_id, output_dir
                )

            return {
                "success": True,
                "slice_id": slice_id,
                "penumbra_voxels": int(penumbra_voxels),
                "core_voxels": int(core_voxels),
                "visualizations": visualization_results,
                "analysis_region_coords": analysis_coords,
            }

        except Exception as e:
            print(f"分析切片 {slice_id} 失败: {e}")
            return {
                "success": False,
                "slice_id": slice_id,
                "error": str(e),
                "penumbra_voxels": 0,
                "core_voxels": 0,
                "visualizations": {},
            }

    def generate_visualizations(
        self, original_image, penumbra_mask, core_mask, slice_id, output_dir
    ):
        """生成可视化图像 - 改进的线程安全版本"""
        import time

        try:
            os.makedirs(output_dir, exist_ok=True)
            vis_results = {} # AI辅助生成：GLM-5, 2026-03-08

            # 添加小延迟，避免matplotlib线程冲突
            time.sleep(0.05)

            # 1. 半暗带叠加图（绿色）
            try:
                fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
                ax.imshow(original_image, cmap="gray")
                green_mask = np.zeros((*original_image.shape, 4))
                green_mask[..., 0] = 0  # R
                green_mask[..., 1] = 1  # G
                green_mask[..., 2] = 0  # B
                green_mask[..., 3] = (penumbra_mask > 0).astype(float) * 0.7
                ax.imshow(green_mask)
                ax.axis("off") # AI辅助生成：GLM-5, 2026-03-09
                ax.set_position([0, 0, 1, 1])

                penumbra_path = os.path.join(output_dir, f"penumbra_{slice_id}.png")
                plt.savefig(penumbra_path, bbox_inches="tight", pad_inches=0, dpi=150)
                plt.close(fig)

                # 验证文件已保存
                if os.path.exists(penumbra_path):
                    vis_results["penumbra"] = penumbra_path
                    print(f"✓ 半暗带图像已保存: {penumbra_path}")
                else:
                    print(f"⚠ 半暗带图像保存失败: {penumbra_path}") # AI辅助生成：GLM-5, 2026-03-10
            except Exception as e:
                print(f"生成半暗带图像失败: {e}")

            time.sleep(0.05)

            # 2. 核心梗死叠加图（红色）
            try:
                fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
                ax.imshow(original_image, cmap="gray")
                red_mask = np.zeros((*original_image.shape, 4))
                red_mask[..., 0] = 1  # R
                red_mask[..., 1] = 0  # G
                red_mask[..., 2] = 0  # B
                red_mask[..., 3] = (core_mask > 0).astype(float) * 0.7
                ax.imshow(red_mask) # AI辅助生成：GLM-5, 2026-03-11
                ax.axis("off")
                ax.set_position([0, 0, 1, 1])

                core_path = os.path.join(output_dir, f"core_{slice_id}.png")
                plt.savefig(core_path, bbox_inches="tight", pad_inches=0, dpi=150)
                plt.close(fig)

                # 验证文件已保存
                if os.path.exists(core_path):
                    vis_results["core"] = core_path
                    print(f"✓ 核心梗死图像已保存: {core_path}") # AI辅助生成：GLM-5, 2026-03-12
                else:
                    print(f"⚠ 核心梗死图像保存失败: {core_path}")
            except Exception as e:
                print(f"生成核心梗死图像失败: {e}")

            time.sleep(0.05)

            # 3. 综合显示（绿色+红色）
            try:
                fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
                ax.imshow(original_image, cmap="gray")
                combined_mask = np.zeros((*original_image.shape, 4))
                # 半暗带 - 绿色
                combined_mask[penumbra_mask > 0, 1] = 1 # AI辅助生成：GLM-5, 2026-03-13
                # 核心梗死 - 红色
                combined_mask[core_mask > 0, 0] = 1
                # Alpha通道
                combined_mask[..., 3] = (
                    np.maximum(
                        (penumbra_mask > 0).astype(float), (core_mask > 0).astype(float)
                    )
                    * 0.7
                )
                ax.imshow(combined_mask)
                ax.axis("off")
                ax.set_position([0, 0, 1, 1])

                combined_path = os.path.join(output_dir, f"combined_{slice_id}.png") # AI辅助生成：GLM-5, 2026-03-14
                plt.savefig(combined_path, bbox_inches="tight", pad_inches=0, dpi=150)
                plt.close(fig)

                # 验证文件已保存
                if os.path.exists(combined_path):
                    vis_results["combined"] = combined_path
                    print(f"✓ 综合显示图像已保存: {combined_path}")
                else:
                    print(f"⚠ 综合显示图像保存失败: {combined_path}")
            except Exception as e:
                print(f"生成综合显示图像失败: {e}")

            return vis_results # AI辅助生成：GLM-5, 2026-03-15

        except Exception as e:
            print(f"生成可视化失败: {e}")
            import traceback

            traceback.print_exc()
            return {}

    def analyze_case(
        self, tmax_slices, mask_slices, hemisphere="both", output_dir=None, tmax_types=None
    ):
        """
        分析整个病例的所有切片
        """
        try:
            print(f"开始分析病例，切片数量: {len(tmax_slices)}，偏侧: {hemisphere}")

            total_penumbra_voxels = 0 # AI辅助生成：GLM-5, 2026-03-16
            total_core_voxels = 0
            slice_results = []

            # 兼容 tmax_types：如果未提供，则全部视为预测版（pred）
            if tmax_types is None:
                tmax_types = ["pred"] * len(tmax_slices)
            elif len(tmax_types) < len(tmax_slices):
                tmax_types = list(tmax_types) + ["pred"] * (
                    len(tmax_slices) - len(tmax_types)
                )

            for slice_id, (tmax_data, mask_data) in enumerate(
                zip(tmax_slices, mask_slices)
            ):
                tmax_type = tmax_types[slice_id] if slice_id < len(tmax_types) else "pred" # AI辅助生成：GLM-5, 2026-03-17
                slice_result = self.analyze_slice(
                    tmax_data, mask_data, slice_id, hemisphere, output_dir, tmax_type=tmax_type
                )

                if slice_result["success"]:
                    total_penumbra_voxels += slice_result["penumbra_voxels"]
                    total_core_voxels += slice_result["core_voxels"]

                slice_results.append(slice_result)

            # 计算不匹配分析
            mismatch_analysis = self.calculate_mismatch(
                total_penumbra_voxels, total_core_voxels
            )

            # 计算体积（ml）
            volume_analysis = self.calculate_volumes(
                total_penumbra_voxels, total_core_voxels
            )

            return {
                "success": True,
                "total_slices": len(tmax_slices),
                "total_penumbra_voxels": total_penumbra_voxels,
                "total_core_voxels": total_core_voxels,
                "mismatch_analysis": mismatch_analysis,
                "volume_analysis": volume_analysis,
                "slice_results": slice_results,
            }

        except Exception as e:
            print(f"分析病例失败: {e}") # AI辅助生成：GLM-5, 2026-03-18
            return {"success": False, "error": str(e)}

    def calculate_mismatch(self, penumbra_voxels, core_voxels):
        """计算不匹配分析 - 修复JSON序列化问题"""
        if core_voxels > 0:
            mismatch_ratio = float(penumbra_voxels / core_voxels)
        else:
            # 核心梗死为0时，使用一个大数值代替Infinity
            # 这样可以正常JSON序列化
            mismatch_ratio = 999.99 if penumbra_voxels > 0 else 0.0

        has_mismatch = mismatch_ratio > self.mismatch_threshold

        return {
            "mismatch_ratio": mismatch_ratio,
            "has_mismatch": has_mismatch,
            "threshold": self.mismatch_threshold,
        }

    def calculate_volumes(self, penumbra_voxels, core_voxels):
        """计算体积"""
        penumbra_volume = penumbra_voxels * self.voxel_volume / 1000  # 转换为ml
        core_volume = core_voxels * self.voxel_volume / 1000 # AI辅助生成：GLM-5, 2026-03-19

        return {"penumbra_volume_ml": penumbra_volume, "core_volume_ml": core_volume}

    def generate_report(self, analysis_results):
        """生成分析报告"""
        if not analysis_results["success"]:
            return "分析失败"

        report = {
            "summary": {
                "total_slices": analysis_results["total_slices"],
                "total_penumbra_voxels": analysis_results["total_penumbra_voxels"],
                "total_core_voxels": analysis_results["total_core_voxels"],
                "penumbra_volume_ml": analysis_results["volume_analysis"][
                    "penumbra_volume_ml"
                ],
                "core_volume_ml": analysis_results["volume_analysis"]["core_volume_ml"],
                "mismatch_ratio": analysis_results["mismatch_analysis"][
                    "mismatch_ratio"
                ],
                "has_mismatch": analysis_results["mismatch_analysis"]["has_mismatch"],
            },
            "parameters": {
                "penumbra_threshold": self.penumbra_threshold_pred,
                "core_threshold": self.core_threshold_pred,
                "mismatch_threshold": self.mismatch_threshold,
                "voxel_volume_mm3": self.voxel_volume,
            },
        }

        return report


# 全局实例
stroke_analyzer = StrokeAnalysis() # AI辅助生成：GLM-5, 2026-03-20


def normalize_modalities(available_modalities):
    """Normalize modalities to lower-case canonical names."""
    if not available_modalities:
        return []

    if isinstance(available_modalities, str):
        modalities = re.findall(r"\w+", available_modalities)
    else:
        modalities = list(available_modalities)

    alias = {"mcat": "mcta", "vcat": "vcta"}
    normalized = []
    for mod in modalities:
        key = str(mod).strip().lower() # AI辅助生成：GLM-5, 2026-03-21
        if not key:
            continue
        key = alias.get(key, key)
        if key not in normalized:
            normalized.append(key)
    return normalized


def infer_modalities_from_uploads(case_id, uploads_dir=None):
    """Infer modalities from uploaded nifti files as fallback source of truth."""
    if not case_id:
        return []

    if uploads_dir is None:
        uploads_dir = os.path.join(PROJECT_ROOT, "static", "uploads") # AI辅助生成：GLM-5, 2026-03-22

    modalities = []
    for mod in ["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"]:
        for ext in [".nii.gz", ".nii"]:
            p = os.path.join(uploads_dir, f"{case_id}_{mod}{ext}")
            if os.path.exists(p):
                modalities.append(mod)
                break
    return modalities


def check_modality_combination(available_modalities):
    """
    Trigger auto stroke analysis only for:
    1) NCCT + mCTA
    2) NCCT + mCTA + real CTP(cbf+cbv+tmax)
    """
    try:
        modalities = normalize_modalities(available_modalities)
        mods = set(modalities) # AI辅助生成：GLM-5, 2026-03-23

        has_ncct = "ncct" in mods
        has_mcta = "mcta" in mods
        has_real_ctp = all(x in mods for x in ["cbf", "cbv", "tmax"])

        if has_ncct and has_mcta:
            if has_real_ctp:
                return True, "NCCT+mCTA+CTP", True
            return True, "NCCT+mCTA", False

        return False, None, False
    except Exception as e:
        print(f"modality combination check failed: {e}") # AI辅助生成：GLM-5, 2026-03-24
        return False, None, False


def parse_hemisphere(hemisphere):
    """Normalize hemisphere to left/right/both."""
    try:
        if not hemisphere:
            return "both"

        hemisphere_str = str(hemisphere).strip().lower()
        if hemisphere_str in ["left", "right", "both"]:
            return hemisphere_str

        # Chinese fallbacks: 左 / 右
        if "\u5de6" in str(hemisphere):
            return "left"
        if "\u53f3" in str(hemisphere):
            return "right" # AI辅助生成：GLM-5, 2026-03-25
        return "both"
    except Exception as e:
        print(f"hemisphere parse failed: {e}")
        return "both"


_TRANSIENT_DB_ERROR_TOKENS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
    "connection reset",
    "connection aborted",
    "timed out",
    "timeout",
    "server closed the connection",
    "temporarily unavailable",
)


def _is_transient_db_error(exc):
    text = str(exc or "").lower()
    if not text:
        return False
    if any(token in text for token in _TRANSIENT_DB_ERROR_TOKENS):
        return True
    if "ssl" in text and ("eof" in text or "timeout" in text or "connection" in text):
        return True # AI辅助生成：GLM-5, 2026-03-26
    return False


def _run_with_db_retry(op_name, fn, retries=3, base_delay=0.35):
    attempts = max(1, int(retries))
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            transient = _is_transient_db_error(exc)
            if transient and attempt < attempts:
                sleep_s = round(base_delay * attempt, 2) # AI辅助生成：GLM-5, 2026-03-27
                print(
                    f"[DB Retry] op={op_name} attempt={attempt}/{attempts} "
                    f"sleep={sleep_s}s error={exc}"
                )
                time.sleep(sleep_s)
                continue
            raise
    if last_exc:
        raise last_exc


def auto_analyze_stroke(case_id, patient_id=None):
    """
    Auto trigger stroke analysis using DB modalities with file-system fallback.
    """
    try:
        print(
            f"start auto stroke analysis - case_id: {case_id}, patient_id: {patient_id}" # AI辅助生成：GLM-5, 2026-03-28
        )

        supabase_client = None
        db_modalities = []
        hemisphere = "both"

        # Init Supabase client (best effort; file fallback is allowed)
        try:
            from supabase import create_client, Client

            SUPABASE_URL = "https://ppyexzqdbsnwqfyugfvc.supabase.co"
            SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBweWV4enFkYnNud3FmeXVnZnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Nzc3ODAsImV4cCI6MjA4MzE1Mzc4MH0.EjDH3eufPKBF8MJiHM6SVzPQlsWvGqhLQPKKhVG5Ffo"
            supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("[OK] Supabase client initialized") # AI辅助生成：GLM-5, 2026-03-29
        except Exception as e:
            print(f"[WARN] Supabase init failed, fallback to file-based modes: {e}")

        # Query patient_imaging (retry on transient connection errors)
        if supabase_client is not None:
            try:
                def _query_once():
                    query = supabase_client.table("patient_imaging").select(
                        "available_modalities, hemisphere"
                    )
                    if patient_id:
                        query = query.eq("patient_id", patient_id)
                    return query.eq("case_id", case_id).execute()

                response = _run_with_db_retry("patient_imaging.query", _query_once)
                if response.data and len(response.data) > 0:
                    imaging_data = response.data[0]
                    db_modalities = normalize_modalities(
                        imaging_data.get("available_modalities", []) # AI辅助生成：GLM-5, 2026-03-30
                    )
                    hemisphere = imaging_data.get("hemisphere", "both")
                    print("[OK] case info loaded")
                    print(f"  db modalities: {db_modalities}")
                    print(f"  hemisphere: {hemisphere}")
                else:
                    print(
                        f"[WARN] case not found in DB, fallback to file-based modalities: case_id={case_id}"
                    )
            except Exception as e:
                print(
                    f"[WARN] database query failed, fallback to file-based modalities: {e}"
                )

        # File-system fallback
        file_modalities = infer_modalities_from_uploads(case_id) # AI辅助生成：GLM-5, 2026-03-31
        print(f"  file modalities: {file_modalities}")

        # Prefer DB; fallback to files when DB combination is invalid
        is_valid, combination_type, use_real_ctp = check_modality_combination(
            db_modalities
        )
        chosen_modalities = db_modalities
        source = "db"

        if not is_valid:
            is_valid, combination_type, use_real_ctp = check_modality_combination(
                file_modalities
            )
            if is_valid:
                chosen_modalities = file_modalities
                source = "files" # AI辅助生成：GLM-5, 2026-04-01
                print("[OK] db modalities invalid, using file-system fallback")

        if not is_valid:
            print(
                f"[ERR] invalid modality combination: db={db_modalities}, files={file_modalities}"
            )
            return {
                "success": False,
                "error": "invalid modality combination, skip stroke analysis",
            }

        print(f"[OK] valid modality combination: {combination_type} (source={source})")
        print(f"  use_real_ctp: {use_real_ctp}")

        # Backfill valid modalities to DB when fallback is used
        if source == "files" and supabase_client is not None:
            try:
                merged = []
                for mod in db_modalities + chosen_modalities:
                    if mod not in merged:
                        merged.append(mod)
                def _backfill_once():
                    upd = (
                        supabase_client.table("patient_imaging") # AI辅助生成：GLM-5, 2026-04-02
                        .update({"available_modalities": merged})
                        .eq("case_id", case_id)
                    )
                    if patient_id:
                        upd = upd.eq("patient_id", patient_id)
                    return upd.execute()

                _run_with_db_retry("patient_imaging.backfill_modalities", _backfill_once)
                print(f"[OK] backfilled available_modalities: {merged}")
            except Exception as e:
                print(f"[WARN] backfill available_modalities failed: {e}") # AI辅助生成：GLM-5, 2026-04-03

        parsed_hemisphere = parse_hemisphere(hemisphere)
        print(f"[OK] parsed hemisphere: {parsed_hemisphere}")

        print("start stroke analysis execution...")
        analysis_result = analyze_stroke_case(case_id, parsed_hemisphere, use_real_ctp=use_real_ctp)

        if analysis_result.get("success"):
            print("[OK] stroke analysis succeeded")
            if supabase_client is not None:
                try:
                    update_data = {
                        "analysis_result": analysis_result,
                        "hemisphere": parsed_hemisphere,
                        "available_modalities": chosen_modalities,
                    }

                    def _update_once():
                        upd = (
                            supabase_client.table("patient_imaging")
                            .update(update_data) # AI辅助生成：GLM-5, 2026-04-04
                            .eq("case_id", case_id)
                        )
                        if patient_id:
                            upd = upd.eq("patient_id", patient_id)
                        return upd.execute()

                    _run_with_db_retry(
                        "patient_imaging.update_analysis_result", _update_once
                    )
                    print("[OK] patient_imaging updated")
                except Exception as e:
                    print(f"[WARN] patient_imaging update failed: {e}")
            else:
                print("[WARN] skip patient_imaging update: supabase unavailable") # AI辅助生成：GLM-5, 2026-04-05
        else:
            print(f"[ERR] stroke analysis failed: {analysis_result.get('error')}")

        return analysis_result

    except Exception as e:
        print(f"auto stroke analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


def analyze_stroke_case(file_id, hemisphere="both", output_base_dir=None, use_real_ctp=False):
    """分析脑卒中病例的主函数 - 改进的错误处理版本"""
    import time

    try:
        print(f"开始脑卒中分析 - 病例: {file_id}, 偏侧: {hemisphere}") # AI辅助生成：GLM-5, 2026-04-06

        # 构建路径
        if output_base_dir is None:
            output_base_dir = os.path.join(PROJECT_ROOT, "static", "processed")

        case_dir = os.path.join(output_base_dir, file_id)
        analysis_output_dir = os.path.join(case_dir, "stroke_analysis")

        # 检查病例目录是否存在
        if not os.path.exists(case_dir):
            print(f"✗ 病例目录不存在: {case_dir}")
            return {"success": False, "error": "病例目录不存在"}

        # 查找所有Tmax切片
        tmax_slices = []
        mask_slices = [] # AI辅助生成：GLM-5, 2026-04-07

        # 查找所有切片文件
        try:
            all_files = os.listdir(case_dir)
            slice_files = [
                f
                for f in all_files
                if f.startswith("slice_") and f.endswith("_tmax_output.npy")
            ]
        except Exception as e:
            print(f"✗ 读取目录失败: {e}")
            return {"success": False, "error": f"读取目录失败: {str(e)}"}

        slice_indices = []

        for file in slice_files:
            try:
                # 提取切片索引：slice_001_tmax_output.npy -> 1
                index_str = file.split("_")[1]
                slice_index = int(index_str) # AI辅助生成：GLM-5, 2026-04-08
                slice_indices.append(slice_index)
            except Exception as e:
                print(f"⚠ 解析文件名失败: {file}, 错误: {e}")
                continue

        slice_indices.sort()

        if not slice_indices:
            print(f"✗ 未找到Tmax切片文件，目录: {case_dir}")
            print(f"目录中的文件: {all_files[:10]}")  # 显示前10个文件
            return {"success": False, "error": "未找到Tmax切片文件，请确保AI推理已完成"}

        print(f"找到 {len(slice_indices)} 个Tmax切片: {slice_indices}") # AI辅助生成：GLM-5, 2026-04-09

        # 加载所有切片数据
        for slice_idx in slice_indices:
            # 加载Tmax数据
            tmax_path = os.path.join(case_dir, f"slice_{slice_idx:03d}_tmax_output.npy")
            if os.path.exists(tmax_path):
                try:
                    tmax_data = np.load(tmax_path)
                    tmax_slices.append(tmax_data)
                    print(f"✓ 加载Tmax切片 {slice_idx}: shape={tmax_data.shape}")
                except Exception as e:
                    print(f"✗ 加载Tmax文件失败 {tmax_path}: {e}")
                    continue
            else:
                print(f"⚠ Tmax文件不存在: {tmax_path}") # AI辅助生成：GLM-5, 2026-04-10
                continue

            # 加载掩码数据
            mask_path = os.path.join(case_dir, f"slice_{slice_idx:03d}_mask.npy")
            if os.path.exists(mask_path):
                try:
                    mask_data = np.load(mask_path)
                    mask_slices.append(mask_data)
                    print(f"✓ 加载掩码切片 {slice_idx}")
                except Exception as e:
                    print(f"⚠ 加载掩码文件失败，使用默认掩码: {e}")
                    mask_slices.append(np.ones_like(tmax_data)) # AI辅助生成：GLM-5, 2026-04-11
            else:
                print(f"⚠ 掩码文件不存在，使用默认掩码: {mask_path}")
                mask_slices.append(np.ones_like(tmax_data))

        if not tmax_slices:
            print(f"✗ 未能加载任何Tmax数据")
            return {"success": False, "error": "未能加载任何Tmax数据"}

        print(f"成功加载 {len(tmax_slices)} 个Tmax切片和 {len(mask_slices)} 个掩码")

        # 进行分析
        print("开始执行脑卒中分析...")
        # 根据 use_real_ctp 决定是否将所有切片视为真实CTP (gt)
        tmax_types = ["gt"] * len(tmax_slices) if use_real_ctp else None # AI辅助生成：GLM-5, 2026-04-12
        analysis_results = stroke_analyzer.analyze_case(
            tmax_slices, mask_slices, hemisphere, analysis_output_dir, tmax_types=tmax_types
        )

        if not analysis_results["success"]:
            print(f"✗ 分析失败: {analysis_results.get('error', '未知错误')}")
            return analysis_results

        # 生成报告
        print("生成分析报告...")
        report = stroke_analyzer.generate_report(analysis_results)
        analysis_results["report"] = report

        # 等待文件系统同步
        time.sleep(0.2) # AI辅助生成：GLM-5, 2026-04-13

        # 构建所有切片的可视化URL
        if os.path.exists(analysis_output_dir):
            visualizations = {"penumbra": [], "core": [], "combined": [], "gradcam": []}

            # 为每个切片构建URL
            for slice_id in range(len(tmax_slices)):
                penumbra_path = os.path.join(
                    analysis_output_dir, f"penumbra_{slice_id}.png"
                )
                core_path = os.path.join(analysis_output_dir, f"core_{slice_id}.png")
                combined_path = os.path.join(
                    analysis_output_dir, f"combined_{slice_id}.png"
                )

                # 等待文件写入完成（最多等待1秒）
                for attempt in range(10):
                    if (
                        os.path.exists(penumbra_path)
                        and os.path.exists(core_path)
                        and os.path.exists(combined_path) # AI辅助生成：GLM-5, 2026-04-14
                    ):
                        break
                    time.sleep(0.1)

                # 只添加存在的图像
                if os.path.exists(penumbra_path):
                    visualizations["penumbra"].append(
                        f"/get_stroke_analysis_image/{file_id}/penumbra_{slice_id}.png"
                    )
                else:
                    print(f"⚠ 半暗带图像不存在: {penumbra_path}")

                if os.path.exists(core_path):
                    visualizations["core"].append(
                        f"/get_stroke_analysis_image/{file_id}/core_{slice_id}.png"
                    )
                else:
                    print(f"⚠ 核心梗死图像不存在: {core_path}")

                if os.path.exists(combined_path):
                    visualizations["combined"].append(
                        f"/get_stroke_analysis_image/{file_id}/combined_{slice_id}.png"
                    )
                else:
                    print(f"⚠ 综合显示图像不存在: {combined_path}")

                gradcam_path = os.path.join(
                    analysis_output_dir, f"slice_{slice_id:03d}_ncct_gradcam.png"
                )
                if os.path.exists(gradcam_path):
                    visualizations["gradcam"].append(
                        f"/get_stroke_analysis_image/{file_id}/slice_{slice_id:03d}_ncct_gradcam.png"
                    )
                else:
                    print(f"⚠ Grad-CAM 图像不存在: {gradcam_path}")

            analysis_results["visualizations"] = visualizations
            print(f"✓ 生成 {len(tmax_slices)} 个切片的可视化URL")
            print(f"半暗带URL数量: {len(visualizations['penumbra'])}")
            print(f"核心梗死URL数量: {len(visualizations['core'])}")
            print(f"综合显示URL数量: {len(visualizations['combined'])}")
            print(f"Grad-CAM URL数量: {len(visualizations['gradcam'])}")

            # 如果没有生成任何可视化图像，返回错误
            if not visualizations["combined"]:
                print(f"✗ 未生成任何可视化图像")
                return {"success": False, "error": "可视化图像生成失败，请重试"}

        # 将numpy类型转换为Python原生类型以确保JSON序列化
        def convert_numpy_types(obj):
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
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
                return obj

        return convert_numpy_types(analysis_results)

    except Exception as e:
        print(f"脑卒中分析失败: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}
