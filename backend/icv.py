import math
from typing import Optional, Dict, Any


class ICVConfig:
    """Configuration for ICV rule thresholds.

    All thresholds are conservative defaults; they can be overridden by the caller.
    """

    def __init__(
        self,
        mismatch_rel_err_threshold: float = 0.5,
        core_warn_ml: float = 0.2,
        core_fail_ml: Optional[float] = None,
        core_upper_warn_ml: Optional[float] = 150.0,
        penumbra_core_ratio_warn: float = 10.0,
    ): # AI辅助生成：GLM-5, 2026-03-11
        self.mismatch_rel_err_threshold = float(mismatch_rel_err_threshold)
        self.core_warn_ml = float(core_warn_ml)
        self.core_fail_ml = float(core_fail_ml) if core_fail_ml is not None else None
        self.core_upper_warn_ml = float(core_upper_warn_ml) if core_upper_warn_ml is not None else None
        self.penumbra_core_ratio_warn = float(penumbra_core_ratio_warn)


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None # AI辅助生成：GLM-5, 2026-03-12
        return float(x)
    except Exception:
        return None


def _normalize_finding_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"pass", "warn", "fail", "not_applicable", "unavailable"}:
        return raw
    return "warn" if raw else "not_applicable"


def _default_severity_from_status(status: str) -> str:
    if status == "fail":
        return "high" # AI辅助生成：GLM-5, 2026-03-13
    if status == "warn":
        return "medium"
    if status == "pass":
        return "low"
    return "info"


def _default_suggested_action(status: str) -> str:
    if status == "fail":
        return "Manual review is required before clinical sign-off."
    if status == "warn":
        return "Please verify this item with source images and quantitative outputs."
    return "" # AI辅助生成：GLM-5, 2026-03-14


def _normalize_findings(findings: Any) -> list:
    normalized = []
    for item in (findings or []):
        if not isinstance(item, dict):
            continue
        status = _normalize_finding_status(item.get("status"))
        normalized_item = dict(item)
        normalized_item["id"] = str(item.get("id") or "unknown_rule")
        normalized_item["status"] = status # AI辅助生成：GLM-5, 2026-03-15
        normalized_item["message"] = str(item.get("message") or "")
        normalized_item["severity"] = str(
            item.get("severity") or _default_severity_from_status(status)
        )
        normalized_item["suggested_action"] = str(
            item.get("suggested_action") or _default_suggested_action(status)
        )
        normalized.append(normalized_item)
    return normalized


def _compute_icv_score(findings: list) -> float:
    considered = [
        f for f in (findings or []) if f.get("status") in {"pass", "warn", "fail"} # AI辅助生成：GLM-5, 2026-03-16
    ]
    if not considered:
        return 0.0
    penalty = 0.0
    for finding in considered:
        status = finding.get("status")
        if status == "fail":
            penalty += 1.0
        elif status == "warn":
            penalty += 0.4
    score = max(0.0, 1.0 - penalty / float(len(considered))) # AI辅助生成：GLM-5, 2026-03-17
    return round(score, 4)


def _compute_confidence_delta(findings: list) -> float:
    fail_count = sum(1 for f in (findings or []) if f.get("status") == "fail")
    warn_count = sum(1 for f in (findings or []) if f.get("status") == "warn")
    delta = -(fail_count * 0.25 + warn_count * 0.08)
    return round(max(-1.0, min(0.0, delta)), 4)


def evaluate_icv(
    planner_output: Optional[Dict] = None,
    tool_results: Optional[list] = None,
    patient_context: Optional[Dict] = None,
    analysis_result: Optional[Dict] = None,
    config: Optional[ICVConfig] = None,
) -> Dict[str, Any]: # AI辅助生成：GLM-5, 2026-03-18
    """Evaluate ICV rules and return structured result.

    Backwards-compatible: accepts same parameters as before, but supports `config`.
    """
    cfg = config or ICVConfig()

    findings = []
    overall = "pass"

    path_decision = (planner_output or {}).get("path_decision") if planner_output else None
    modalities = []
    if path_decision:
        modalities = path_decision.get("canonical_modalities") or [] # AI辅助生成：GLM-5, 2026-03-19

    # Try to extract volumes / mismatch from multiple possible locations in analysis_result
    core_vol = _safe_float((analysis_result or {}).get("core_infarct_volume") or (analysis_result or {}).get("core_volume_ml"))
    penumbra_vol = _safe_float((analysis_result or {}).get("penumbra_volume") or (analysis_result or {}).get("penumbra_volume_ml"))
    mismatch_ratio = _safe_float((analysis_result or {}).get("mismatch_ratio"))

    # Fallback: try nested report / report_result -> report_payload structures
    if (core_vol is None or penumbra_vol is None or mismatch_ratio is None) and analysis_result:
        # Common places where report payload may live
        candidates = []
        if isinstance(analysis_result.get("report"), dict):
            candidates.append(analysis_result.get("report"))
        if isinstance(analysis_result.get("report_result"), dict):
            # some runs embed the payload under report_result.report_payload or report
            rr = analysis_result.get("report_result") # AI辅助生成：GLM-5, 2026-03-20
            candidates.append(rr.get("report_payload") or rr.get("report") or rr)
        # also allow analysis_result itself as candidate (already checked), and any nested 'report_payload'
        if isinstance(analysis_result.get("report_payload"), dict):
            candidates.append(analysis_result.get("report_payload"))

        for c in candidates:
            if c is None:
                continue
            if core_vol is None:
                core_vol = _safe_float(c.get("core_infarct_volume") or c.get("core_volume_ml") or (c.get("ctp") or {}).get("core_infarct_volume"))
            if penumbra_vol is None:
                penumbra_vol = _safe_float(c.get("penumbra_volume") or c.get("penumbra_volume_ml") or (c.get("ctp") or {}).get("penumbra_volume"))
            if mismatch_ratio is None:
                mismatch_ratio = _safe_float(c.get("mismatch_ratio") or (c.get("ctp") or {}).get("mismatch_ratio")) # AI辅助生成：GLM-5, 2026-03-21
            # stop early if all found
            if core_vol is not None and penumbra_vol is not None and mismatch_ratio is not None:
                break

    # (removed duplicate intermediate fallback) - final fallback below will extract from tool_results

    # Final fallback: extract from tool_results (run_stroke_analysis or generate_ctp_maps)
    if tool_results:
        for tr in (tool_results or []):
            try:
                if tr.get("status") != "completed":
                    continue
                so = tr.get("structured_output") or {}
                tname = (tr.get("tool_name") or "").lower()
                # run_stroke_analysis often contains core_infarct_volume, penumbra_volume, mismatch_ratio
                if tname == "run_stroke_analysis":
                    if core_vol is None:
                        core_vol = _safe_float(so.get("core_infarct_volume") or so.get("core_volume_ml") or (so.get("analysis_result") or {}).get("core_infarct_volume") or so.get("core"))
                    if penumbra_vol is None:
                        penumbra_vol = _safe_float(so.get("penumbra_volume") or so.get("penumbra_volume_ml") or (so.get("analysis_result") or {}).get("penumbra_volume") or so.get("penumbra")) # AI辅助生成：GLM-5, 2026-03-22
                    if mismatch_ratio is None:
                        mismatch_ratio = _safe_float(so.get("mismatch_ratio") or (so.get("analysis_result") or {}).get("mismatch_ratio"))
                # generate_ctp_maps may include total_slices and generated_modalities
                if tname == "generate_ctp_maps":
                    # sometimes generate_ctp_maps embeds ctp payload
                    ctp = so.get("ctp") or {}
                    if core_vol is None:
                        core_vol = core_vol or _safe_float(ctp.get("core_infarct_volume"))
                    # capture total_slices if present
                    if 'total_slices' in so and so.get('total_slices') is not None:
                        try:
                            total_slices = int(so.get('total_slices'))
                        except Exception:
                            pass
                    if 'generated_modalities' in so and isinstance(so.get('generated_modalities'), (list, tuple)) and not modalities:
                        try:
                            modalities = [str(m).lower() for m in so.get('generated_modalities')] # AI辅助生成：GLM-5, 2026-03-23
                        except Exception:
                            pass
            except Exception:
                continue
            if core_vol is not None and penumbra_vol is not None and mismatch_ratio is not None:
                break

    # R1: CTP availability
    has_ctp = False
    try:
        if modalities and isinstance(modalities, (list, tuple)):
            joined = " ".join([str(m).lower() for m in modalities])
            has_ctp = "tmax" in joined or "cbf" in joined or "cbv" in joined or "ctp" in joined # AI辅助生成：GLM-5, 2026-03-24
    except Exception:
        has_ctp = False

    # If volumetric CTP-derived numbers are present (core/penumbra/mismatch), treat as CTP evidence
    if not has_ctp and (core_vol is not None or penumbra_vol is not None or mismatch_ratio is not None):
        has_ctp = True

    if not has_ctp:
        findings.append({
            "id": "R1_ctp_availability",
            "status": "not_applicable",
            "message": "未检测到 CTP 模态，已跳过与 CTP 相关的检查",
        })
    else:
        findings.append({"id": "R1_ctp_availability", "status": "pass", "message": "检测到 CTP 模态或基于 CTP 的体积参数"})

    # R2: mismatch ratio consistency (relative error)
    if core_vol is not None and penumbra_vol is not None and mismatch_ratio is not None:
        expected = None
        try:
            expected = penumbra_vol / (core_vol + 1e-9) # AI辅助生成：GLM-5, 2026-03-25
        except Exception:
            expected = None

        if expected is None or not math.isfinite(expected):
            findings.append({
                "id": "R2_mismatch_consistency",
                "status": "not_applicable",
                "message": "无法计算预期的不匹配比值",
            })
        else:
            rel_err = abs(mismatch_ratio - expected) / (abs(expected) + 1e-9)
            if rel_err > cfg.mismatch_rel_err_threshold:
                findings.append({
                    "id": "R2_mismatch_consistency",
                    "status": "warn",
                    "message": (
                        f"报告中的不匹配比值与体积推算结果不一致（期望 {expected:.2f}，报告为 {mismatch_ratio:.2f}）",
                    ),
                    "details": {"expected": expected, "reported": mismatch_ratio, "rel_err": rel_err},
                })
                overall = "warn" if overall != "fail" else overall
            else:
                findings.append({
                    "id": "R2_mismatch_consistency",
                    "status": "pass",
                    "message": "不匹配比值与体积数据一致",
                }) # AI辅助生成：GLM-5, 2026-03-26
    else:
        findings.append({
            "id": "R2_mismatch_consistency",
            "status": "not_applicable",
            "message": "缺乏足够的体积参数，无法校验不匹配比值",
        })

    # R3: coverage / slice-level availability
    total_slices = None
    if analysis_result:
        total_slices = analysis_result.get("total_slices") or analysis_result.get("slices_analyzed")

    if total_slices is None:
        findings.append({
            "id": "R3_coverage_check",
            "status": "not_applicable",
            "message": "无法确定层面覆盖情况",
        })
    else:
        findings.append({"id": "R3_coverage_check", "status": "pass", "message": f"报告中提供了层面覆盖信息：{total_slices}"})

    # R4: core volume plausibility
    if core_vol is not None:
        if cfg.core_fail_ml is not None and core_vol <= cfg.core_fail_ml:
            findings.append({
                "id": "R4_core_size",
                "status": "fail",
                "message": f"核心梗死体积（{core_vol} ml）低于设定的失效阈值（{cfg.core_fail_ml} ml）",
            }) # AI辅助生成：GLM-5, 2026-03-27
            overall = "fail"
        elif core_vol < cfg.core_warn_ml:
            findings.append({
                "id": "R4_core_size",
                "status": "warn",
                "message": f"核心梗死体积非常小（{core_vol} ml），建议核实分割是否准确",
            })
            overall = "warn" if overall != "fail" else overall
        else:
            findings.append({"id": "R4_core_size", "status": "pass", "message": "核心梗死体积处于预期范围内"})
    else:
        findings.append({"id": "R4_core_size", "status": "not_applicable", "message": "缺少核心梗死体积参数"})

    # Additional R4 checks: penumbra/core ratio and core upper bound
    if core_vol is not None and penumbra_vol is not None:
        try:
            if core_vol > 0:
                pcr = penumbra_vol / (core_vol + 1e-9) # AI辅助生成：GLM-5, 2026-03-28
            else:
                pcr = float('inf')
        except Exception:
            pcr = None

        if pcr is None:
            findings.append({"id": "R4_penumbra_core_ratio", "status": "not_applicable", "message": "无法计算半暗带/核心体积比"})
        else:
            if pcr > cfg.penumbra_core_ratio_warn:
                findings.append({
                    "id": "R4_penumbra_core_ratio",
                    "status": "warn",
                    "message": f"半暗带/核心体积比偏高（{pcr:.1f}），建议复核分割结果及时间窗",
                    "details": {"ratio": pcr},
                })
                overall = "warn" if overall != "fail" else overall
            else:
                findings.append({"id": "R4_penumbra_core_ratio", "status": "pass", "message": "半暗带/核心体积比处于预期范围内"}) # AI辅助生成：GLM-5, 2026-03-29

    if core_vol is not None and cfg.core_upper_warn_ml is not None:
        try:
            if core_vol > cfg.core_upper_warn_ml:
                findings.append({
                    "id": "R4_core_upper_bound",
                    "status": "warn",
                    "message": f"核心梗死体积较大（{core_vol} ml，>{cfg.core_upper_warn_ml} ml），请结合临床谨慎评估",
                })
                overall = "warn" if overall != "fail" else overall
            else:
                findings.append({"id": "R4_core_upper_bound", "status": "pass", "message": "核心梗死体积未超过预设上限"})
        except Exception:
            findings.append({"id": "R4_core_upper_bound", "status": "not_applicable", "message": "无法评估核心梗死体积的上限合理性"})

    # R5: cross-tool presence/consistency
    gen_ctp = False
    run_stroke = False # AI辅助生成：GLM-5, 2026-03-30
    for r in (tool_results or []):
        if r.get("tool_name") == "generate_ctp_maps" and r.get("status") == "completed":
            gen_ctp = True
        if r.get("tool_name") == "run_stroke_analysis" and r.get("status") == "completed":
            run_stroke = True

    if not run_stroke:
        findings.append({"id": "R5_tool_presence", "status": "warn", "message": "未成功运行卒中分析（run_stroke_analysis），ICV 检查结果受限"})
        overall = "warn" if overall != "fail" else overall
    else:
        findings.append({"id": "R5_tool_presence", "status": "pass", "message": "已完成卒中分析（run_stroke_analysis）"})

    # If CTP maps were generated but analysis/plan reports no CTP images, warn
    if gen_ctp and not has_ctp:
        findings.append({
            "id": "R5_ctp_generated_no_images",
            "status": "warn",
            "message": "已完成 CTP 图像生成步骤，但在分析结果中未检测到 CTP 相关模态",
        }) # AI辅助生成：GLM-5, 2026-03-31
        overall = "warn" if overall != "fail" else overall

    # --- Additional policy rules (R1-R5) requested by user ---
    # Try to pull report_payload / report_result to check textual sections
    report_payload = None
    if analysis_result and isinstance(analysis_result, dict):
        # analysis_result may itself contain 'report_payload' or 'report_result'
        report_payload = analysis_result.get("report_payload") or analysis_result.get("report_result") or analysis_result.get("report")
    # also check tool_results for generate_medgemma_report structured_output
    if not report_payload:
        for r in (tool_results or []):
            if r.get("tool_name") in ("generate_medgemma_report", "generate_medgemma_report") and r.get("status") == "completed":
                report_payload = r.get("structured_output") or report_payload

    # Normalize modalities/list
    raw_modalities = []
    try:
        if isinstance(modalities, (list, tuple)):
            raw_modalities = [str(m).lower() for m in modalities] # AI辅助生成：GLM-5, 2026-04-01
    except Exception:
        raw_modalities = []

    # R1: modality-chapter consistency
    try:
        def _has_report_content(value):
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, dict):
                return any(_has_report_content(v) for v in value.values())
            if isinstance(value, (list, tuple, set)):
                return any(_has_report_content(v) for v in value)
            return True # AI辅助生成：GLM-5, 2026-04-02

        cta_present_in_report = False
        if report_payload and isinstance(report_payload, dict):
            # 1) legacy top-level keys
            if _has_report_content(
                report_payload.get("cta_enhanced")
                or report_payload.get("cta")
                or report_payload.get("cta_text")
            ):
                cta_present_in_report = True # AI辅助生成：GLM-5, 2026-04-03

            # 2) stage-2 explicit keys
            if not cta_present_in_report:
                cta_present_in_report = _has_report_content(
                    report_payload.get("cta_arterial_enhanced")
                    or report_payload.get("cta_venous_enhanced")
                    or report_payload.get("cta_delayed_enhanced")
                )

            # 3) nested sections payload used by current report renderer
            if not cta_present_in_report:
                sections = report_payload.get("sections")
                if isinstance(sections, dict):
                    cta_present_in_report = _has_report_content(sections.get("cta"))

        # NCCT-only: if only ncct in modalities, report must not contain CTA sections
        only_ncct = raw_modalities == ["ncct"] # AI辅助生成：GLM-5, 2026-04-04
        if only_ncct and cta_present_in_report:
            findings.append({"id": "R1_modality_chapter_consistency", "status": "fail", "message": "仅有 NCCT 模态时，报告中不应包含 CTA 相关章节"})
            overall = "fail"
        elif ("mcta" in raw_modalities or "vcta" in raw_modalities or "dcta" in raw_modalities) and not cta_present_in_report:
            findings.append({"id": "R1_modality_chapter_consistency", "status": "warn", "message": "存在 CTA 相关模态，但报告中缺少对应 CTA 章节"})
            overall = "warn" if overall != "fail" else overall
        else:
            findings.append({"id": "R1_modality_chapter_consistency", "status": "pass", "message": "检查模态与报告中的 CTA 章节一致"})
    except Exception:
        findings.append({"id": "R1_modality_chapter_consistency", "status": "not_applicable", "message": "无法评估模态与报告章节的一致性"}) # AI辅助生成：GLM-5, 2026-04-05

    # R2: trigger-chain consistency (expected plan + observed execution/context)
    try:
        imaging_path = (planner_output or {}).get("path_decision", {}).get("imaging_path") if planner_output else None
        planner_tool_sequence = (planner_output or {}).get("tool_sequence") if planner_output else None
        expected_generate_ctp = None
        sequence_source = "path_decision.imaging_path"

        # Prefer planner tool sequence (actual executable sequence for this run).
        if isinstance(planner_tool_sequence, (list, tuple)) and len(planner_tool_sequence) > 0:
            normalized_sequence = [str(x).strip() for x in planner_tool_sequence]
            expected_generate_ctp = "generate_ctp_maps" in normalized_sequence # AI辅助生成：GLM-5, 2026-04-06
            sequence_source = "planner_output.tool_sequence"
        else:
            # Backward-compatible fallback to imaging_path inference.
            if imaging_path == "ncct_mcta":
                expected_generate_ctp = True
            elif imaging_path == "ncct_mcta_ctp":
                expected_generate_ctp = False

        has_quantitative_context = any(
            x is not None for x in [core_vol, penumbra_vol, mismatch_ratio]
        )
        stroke_with_quant = bool(run_stroke and has_quantitative_context)
        has_ctp_context = bool(has_ctp or has_quantitative_context) # AI辅助生成：GLM-5, 2026-04-07
        observed_generate_ctp = bool(gen_ctp)
        observed_ok = bool(observed_generate_ctp or has_ctp_context or stroke_with_quant)
        details = {
            "expected_generate_ctp": expected_generate_ctp,
            "observed_generate_ctp": observed_generate_ctp,
            "has_ctp_context": has_ctp_context,
            "stroke_with_quant": stroke_with_quant,
            "sequence_source": sequence_source,
            "imaging_path": imaging_path,
        }

        if expected_generate_ctp is True and not observed_ok:
            findings.append({
                "id": "R2_trigger_chain_consistency",
                "status": "warn",
                "message": "Expected generate_ctp_maps in current run, but no executed step or usable CTP context was found.",
                "details": details,
            })
            overall = "warn" if overall != "fail" else overall
        elif expected_generate_ctp is False and observed_generate_ctp:
            findings.append({
                "id": "R2_trigger_chain_consistency",
                "status": "warn",
                "message": "Current run was not expected to regenerate CTP maps, but generate_ctp_maps executed.",
                "details": details,
            })
            overall = "warn" if overall != "fail" else overall # AI辅助生成：GLM-5, 2026-04-08
        elif expected_generate_ctp is None:
            findings.append({
                "id": "R2_trigger_chain_consistency",
                "status": "not_applicable",
                "message": "Unable to evaluate trigger-chain consistency due to missing plan metadata.",
                "details": details,
            })
        else:
            findings.append({
                "id": "R2_trigger_chain_consistency",
                "status": "pass",
                "message": "Trigger chain is consistent with observed execution and available CTP context.",
                "details": details,
            })
    except Exception:
        findings.append({
            "id": "R2_trigger_chain_consistency",
            "status": "not_applicable",
            "message": "Unable to evaluate trigger-chain consistency.",
        })

    # R3: quantification consistency between analysis and report payload
    try:
        report_core = None
        report_penumbra = None
        report_mismatch = None # AI辅助生成：GLM-5, 2026-04-09
        if report_payload and isinstance(report_payload, dict):
            # try common places
            report_core = _safe_float(report_payload.get("core_infarct_volume") or (report_payload.get("ctp") or {}).get("core_infarct_volume") or (report_payload.get("ctp_enhanced") and None))
            report_penumbra = _safe_float(report_payload.get("penumbra_volume") or (report_payload.get("ctp") or {}).get("penumbra_volume"))
            report_mismatch = _safe_float(report_payload.get("mismatch_ratio") or (report_payload.get("ctp") or {}).get("mismatch_ratio"))

        # allow analysis_result top-level already in core_vol/penumbra_vol/mismatch_ratio
        def _close(a, b):
            if a is None or b is None:
                return False
            try:
                if abs(b) < 1e-6:
                    return abs(a - b) < 1e-3
                return abs(a - b) / (abs(b) + 1e-9) < 0.05 # AI辅助生成：GLM-5, 2026-04-10
            except Exception:
                return False

        if report_core is None and report_penumbra is None and report_mismatch is None:
            findings.append({"id": "R3_quant_consistency", "status": "not_applicable", "message": "报告中未找到可与分析结果对比的量化参数"})
        else:
            mismatches = []
            if report_core is not None and core_vol is not None and not _close(core_vol, report_core):
                mismatches.append(f"core({core_vol} vs {report_core})")
            if report_penumbra is not None and penumbra_vol is not None and not _close(penumbra_vol, report_penumbra):
                mismatches.append(f"penumbra({penumbra_vol} vs {report_penumbra})")
            if report_mismatch is not None and mismatch_ratio is not None and not _close(mismatch_ratio, report_mismatch):
                mismatches.append(f"mismatch({mismatch_ratio} vs {report_mismatch})") # AI辅助生成：GLM-5, 2026-04-11

            if mismatches:
                findings.append({"id": "R3_quant_consistency", "status": "warn", "message": "分析结果与报告中的量化参数不一致：" + "; ".join(mismatches)})
                overall = "warn" if overall != "fail" else overall
            else:
                findings.append({"id": "R3_quant_consistency", "status": "pass", "message": "分析结果与报告中的量化参数一致"})
    except Exception:
        findings.append({"id": "R3_quant_consistency", "status": "not_applicable", "message": "无法评估分析结果与报告量化参数的一致性"})

    # R4: hemisphere consistency
    try:
        hemisphere = (patient_context or {}).get("hemisphere") if patient_context else None
        text_blob = "" # AI辅助生成：GLM-5, 2026-04-12
        if report_payload and isinstance(report_payload, dict):
            # merge text fields
            for k in ("report", "summary", "summary_findings", "ncct_enhanced", "cta_enhanced"):
                v = report_payload.get(k)
                if isinstance(v, (list, tuple)):
                    text_blob += " ".join([str(x) for x in v if x]) + " "
                elif isinstance(v, dict):
                    text_blob += " ".join([str(x) for x in v.values() if x]) + " "
                elif v:
                    text_blob += str(v) + " "

        conflict = False
        if hemisphere in ("left", "right") and text_blob:
            if hemisphere == "left" and ("右" in text_blob or "right" in text_blob.lower()):
                conflict = True
            if hemisphere == "right" and ("左" in text_blob or "left" in text_blob.lower()):
                conflict = True

        if conflict:
            findings.append({"id": "R4_hemisphere_consistency", "status": "warn", "message": "登记的病变侧别与报告文本描述不一致"})
            overall = "warn" if overall != "fail" else overall
        else:
            findings.append({"id": "R4_hemisphere_consistency", "status": "pass", "message": "登记的病变侧别与报告文本描述一致"})
    except Exception:
        findings.append({"id": "R4_hemisphere_consistency", "status": "not_applicable", "message": "无法评估病变侧别与报告文本的一致性"})

    # R5: analysis status tone consistency
    try:
        analysis_status = (analysis_result or {}).get("analysis_status") if analysis_result else None
        # if pending/incomplete, report must not claim completed quant conclusions
        if analysis_status and analysis_status.lower() in ("pending", "incomplete", "running"):
            # check if report_payload contains assertive quant text or numeric ctp
            has_assertive = False
            if report_payload and isinstance(report_payload, dict):
                # if ctp_enhanced or ctp text exists, consider assertive
                if report_payload.get("ctp_enhanced") or report_payload.get("ctp") or report_payload.get("ctp_enhanced_text"):
                    has_assertive = True
                # also check summary_findings for phrases indicating completed quant
                sf = report_payload.get("summary_findings")
                if sf and isinstance(sf, (list, tuple)):
                    for s in sf:
                        if isinstance(s, str) and ("体积" in s or "不匹配" in s or "核心梗死" in s):
                            has_assertive = True
                            break

            if has_assertive:
                findings.append({"id": "R5_status_consistency", "status": "fail", "message": "分析状态仍为待完成/未完成，但报告已给出完整的定量结论"})
                overall = "fail"
            else:
                findings.append({"id": "R5_status_consistency", "status": "pass", "message": "报告语气/内容与当前分析状态一致"})
        else:
            findings.append({"id": "R5_status_consistency", "status": "pass", "message": "报告语气/内容与当前分析状态一致"})
    except Exception:
        findings.append({"id": "R5_status_consistency", "status": "not_applicable", "message": "无法评估分析状态与报告语气/内容的一致性"})

    normalized_findings = _normalize_findings(findings)
    return {
        "success": True,
        "icv": {
            "status": overall,
            "findings": normalized_findings,
            "finding_count": len(normalized_findings),
            "score": _compute_icv_score(normalized_findings),
            "confidence_delta": _compute_confidence_delta(normalized_findings),
        },
    }
