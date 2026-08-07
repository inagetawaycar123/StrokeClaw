"use strict"; // AI辅助生成：GLM-5, 2026-03-25

const MRS_PROGNOSIS_UI = (() => {
    if (typeof window !== "undefined" && window.StrokeClawMrsPrognosis) return window.StrokeClawMrsPrognosis;
    if (typeof require === "function") {
        try { return require("./mrs_prognosis.js"); } catch (_error) { return null; }
    }
    return null;
})();

const UPLOAD_NODES = [
    { key: "archive_ready", title: "Case_Intake.parse()", subtitle: "病例接收与归档准备", chip: "Case_Intake", delegated: "" },
    { key: "image_quality_control", title: "Image_QC.validate()", subtitle: "图像质量控制", chip: "Image_QC", delegated: "image_quality_control" },
    { key: "modality_detect", title: "Modality_Detect.route()", subtitle: "模态识别与路径判定", chip: "Modality", delegated: "" },
    { key: "three_class", title: "Three_Class.triage()", subtitle: "NCCT三分类与Grad-CAM", chip: "Three_Class", delegated: "" },
    { key: "ctp_generate", title: "CTP_Generate.run()", subtitle: "灌注图谱生成", chip: "CTP_Gen", delegated: "generate_ctp_maps" },
    { key: "vessel_occlusion", title: "Vessel_Occlusion.classify()", subtitle: "血管闭塞三分类", chip: "Vessel_Occlusion", delegated: "vessel_occlusion" },
    { key: "stroke_analysis", title: "Stroke_Analysis.segment()", subtitle: "卒中病灶分析", chip: "Analysis", delegated: "run_stroke_analysis" },
    { key: "pseudocolor", title: "Pseudocolor_Render.compose()", subtitle: "伪彩可视化生成", chip: "Pseudocolor", delegated: "generate_pseudocolor" },
    { key: "ai_report", title: "Report_Generate.compose()", subtitle: "结构化报告草拟", chip: "Report", delegated: "generate_medgemma_report" },
];

const VESSEL_OCCLUSION_INPUT = Object.freeze({
    run_id: "",
    tool_name: "vessel_occlusion",
    classes: "正常 / 中血管闭塞 / 大血管闭塞",
});
const VESSEL_CLASS_KEYS = Object.freeze(["Class_0", "Class_1_LVO", "Class_2_MEVO"]);

const TOOL_META = Object.freeze({
    run_mrs_prognosis_prediction: ["MRS_Prognosis.predict()", "90天功能预后评估", "mRS_MVP"],
    human_review: ["Human_Confirm.await_action()", "人工复核节点", "Human_Review"],
    triage_planner: ["Triage_Planner.plan()", "任务编排生成", "Plan"],
    detect_modalities: ["ClinicalNER.extract()", "结构化提取与复核", "NER_Extract"],
    load_patient_context: ["Patient_Context.load()", "患者上下文加载", "Context"],
    image_quality_control: ["Image_QC.validate()", "图像质量控制", "Image_QC"],
    generate_ctp_maps: ["MRDPM_Generate.run()", "灌注图谱生成", "CTP_Gen"],
    vessel_occlusion: ["Vessel_Occlusion.classify()", "血管闭塞三分类", "Vessel_Occlusion"],
    run_stroke_analysis: ["Stroke_Analysis.segment()", "卒中区域分析", "Analysis"],
    icv: ["Evidence_Check.icv()", "院内指标核验", "ICV"],
    ekv: ["Evidence_Check.ekv()", "指南证据核验", "EKV"],
    consensus_lite: ["Consensus_Lite.resolve()", "证据裁决", "Consensus"],
    generate_medgemma_report: ["Final_Report.compose()", "报告生成", "Report"],
    human_confirm: ["Human_Confirm.await_action()", "人工确认节点", "Human_Confirm"],
    emr_sync_writeback: ["EMR_Sync.writeback()", "回写归档", "EMR_Sync"],
});

const TEMPLATES = Object.freeze({
    run_mrs_prognosis_prediction: ["正在加载真实MVP bundle并执行90天功能预后评估。", "根据24小时NIHSS可用性自动选择首诊或更新评估。", "输出校准风险、模型证据、置信度和复核建议。"],
    human_confirm: ["系统已进入人工复核节点。", "请逐段确认报告内容。", "确认完成后流程才会归档闭环。"],
    default: ["系统正在执行当前节点。", "处理节点输入并推进流程。", "形成可解释的临床链路。"],
    archive_ready: ["系统已接收病例并创建会话。", "归集 patient_id 与 file_id。", "确保全流程同一病例上下文。"],
    image_quality_control: ["系统正在执行规则化 NIfTI 图像质控。", "检查可读性、层厚、覆盖、运动风险、疑似缺片和几何一致性。", "在任何医学模型运行前阻断不合格输入。"],
    modality_detect: ["系统正在识别可用模态。", "判断可执行分析路径。", "避免输入缺失导致误判。"],
    three_class: ["系统正在执行 NCCT 三分类。", "同步生成 Grad-CAM 解释图。", "为后续临床判读提供快速分诊参考。"],
    ctp_generate: ["系统将在三分类完成后启动 CTP 生成。", "输出 CBF/CBV/Tmax 灌注核心参数。", "支撑缺血核心与半暗带判断。"],
    vessel_occlusion: ["系统正在执行血管闭塞三分类。", "执行血管闭塞三分类评估。", "辅助判断取栓相关风险与责任血管分型。"],
    stroke_analysis: ["系统正在做病灶分割与体积评估。", "计算病灶侧别与关键指标。", "形成治疗决策依据。"],
    ai_report: ["系统正在组装结构化报告。", "汇总推理证据与关键结论。", "减少医生重复录入负担。"],
    icv: ["系统正在执行 ICV 核验。", "检查关键指标一致性。", "降低指标冲突风险。"],
    ekv: ["系统正在执行 EKV 核验。", "对照循证与指南规则。", "提升结论可信度。"],
    consensus_lite: ["系统正在做证据共识裁决。", "融合多路结论并去冲突。", "输出可落地的一致建议。"],
    emr_sync_writeback: ["系统正在回写归档。", "同步结构化结果到下游系统。", "形成闭环与可追溯记录。"],
});

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "paused_review_required"]);
const STATUS_TEXT = { pending: "Pending", running: "Running", completed: "Completed", skipped: "Skipped", issue: "Issue Found", waiting: "Await Human", needs_edit: "Needs Edit", confirmed: "Confirmed" };
const RUN_RESULT_FETCH_MAX_WAIT_MS = 30000;
const VIEWER_READY_RECHECK_MS = 500;
const NON_BLOCKING_ISSUE_KEYS = new Set(["vessel_occlusion", "icv", "ekv", "consensus_lite"]);
const REVIEW_FALLBACK_SECTIONS = [
    { section_id: "patient_context", title: "患者基本信息与时窗", lead: "确认人口学与时间窗信息是否可支持后续决策。", guide: "请核对年龄、性别、起病至入院时间及 NIHSS。", risk_level: "low" },
    { section_id: "imaging_summary", title: "影像摘要（NCCT/CTA）", lead: "确认影像核心发现是否准确可读。", guide: "请确认 NCCT 与 CTA 的关键发现是否完整。", risk_level: "medium" },
    { section_id: "ctp_quant", title: "CTP 量化分析", lead: "确认核心梗死、半暗带与不匹配比值。", guide: "请核对体积数值及临床意义解释。", risk_level: "medium" },
    { section_id: "question_answer", title: "问题驱动结论", lead: "确认问题回答与临床建议是否一致。", guide: "请检查问题回答、置信度与关键要点。", risk_level: "medium" },
    { section_id: "risk_uncertainty", title: "风险与不确定项", lead: "高风险与不确定项需要显式确认。", guide: "请确认风险提示和建议复核项。", risk_level: "high" },
    { section_id: "next_steps", title: "下一步建议", lead: "确认下一步检查或治疗动作。", guide: "请确认建议是否可执行且顺序合理。", risk_level: "medium" },
    { section_id: "evidence_trace", title: "证据追溯", lead: "核对结论与证据映射关系。", guide: "请确认关键结论均有证据支撑。", risk_level: "low" },
];

const state = {
    jobId: "", patientId: "", fileId: "", runId: "", startedAt: "",
    standalonePreview: false,
    uploadTimer: null, runTimer: null, uploadDone: false, runResultFetched: false,
    latestJob: null, latestRun: null, events: [], hints: {}, nodes: [],
    error: "", redirecting: false, awaitingReport: false,
    runTerminalAt: 0, reportResultRetryUntil: 0, lastManualScrollAt: 0, lastFocusNode: "",
    expanded: Object.create(null),
    qualityReview: { saving: false, error: "", reviewer: "", comment: "", acknowledged: false },
    revealedNodeIds: [],
    revealPendingIds: [],
    revealTimer: null,
    revealTimerDue: 0,
    revealAt: Object.create(null),
    renderedFeedIds: Object.create(null),
    viewerDelayTimer: null,
    dagReview: {
        approved: false,
        reviewer: "",
        approvedAt: "",
        fingerprint: "",
        hydratedKey: "",
        error: "",
    },
    review: {
        required: false,
        visible: false,
        loading: false,
        saving: false,
        offlineMode: false,
        error: "",
        info: "",
        state: null,
        currentSectionId: "",
        rewriteSuggestion: null,
        pendingOps: [],
        flushInFlight: false,
        inited: false,
        serverCanEnterViewer: false,
        runStatus: "",
    },
};

const $ = (id) => document.getElementById(id);
const t = (v, d = "-") => (v === null || v === undefined || String(v).trim() === "" ? d : String(v).trim()); // AI辅助生成：GLM-5, 2026-03-27
const token = (v) => String(v || "").trim().toLowerCase();

function normStatus(v) {
    const s = token(v);
    if (!s || ["queued", "pending", "idle"].includes(s)) return "pending";
    if (["running", "processing", "in_progress"].includes(s)) return "running";
    if (["completed", "succeeded", "done", "skipped"].includes(s)) return "completed";
    if (["paused_review_required", "review_required", "await_review", "awaiting_review", "waiting"].includes(s)) return "waiting";
    if (["issue", "failed", "cancelled", "review_rejected", "error", "warn", "warning", "unavailable"].includes(s)) return "issue";
    return "pending"; // AI辅助生成：GLM-5, 2026-03-28
}

function nodeStatus(v) {
    return token(v) === "skipped" ? "skipped" : normStatus(v);
}

function objectValue(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function normalizeVesselOcclusionResult(value) {
    const wrapped = objectValue(value);
    const source = objectValue(wrapped?.vessel_occlusion_result) || wrapped;
    if (!source || ![
        "vessel_occlusion_status", "vessel_occlusion_class_result", "predicted_label", "predicted_class",
        "class_counts", "error_code", "failures", "valid_predictions",
    ].some((key) => Object.prototype.hasOwnProperty.call(source, key))) return null;

    const label = t(source.vessel_occlusion_class_result || source.predicted_label, "");
    let status = token(source.status || source.vessel_occlusion_status);
    const rawCounts = objectValue(source.class_counts) || objectValue(source.vessel_occlusion_class_counts) || {};
    const validPredictionsValue = Number(source.valid_predictions);
    const hasPredictionEvidence = VESSEL_CLASS_KEYS.includes(source.predicted_class)
        || (Number.isFinite(validPredictionsValue) && validPredictionsValue > 0)
        || VESSEL_CLASS_KEYS.some((key) => Number(rawCounts[key]) > 0);
    if (!["completed", "failed", "unavailable"].includes(status)) {
        status = label && hasPredictionEvidence ? "completed" : "unavailable";
    }
    if (status === "completed" && (!label || !hasPredictionEvidence)) status = "failed";

    const confidenceValue = Number(source.confidence ?? source.vessel_occlusion_confidence);
    const confidence = Number.isFinite(confidenceValue) && confidenceValue >= 0 && confidenceValue <= 1 ? confidenceValue : null;
    const sourceCounts = rawCounts;
    const classCounts = {};
    VESSEL_CLASS_KEYS.forEach((key) => {
        const count = Number(sourceCounts[key]);
        classCounts[key] = Number.isFinite(count) && count >= 0 ? Math.trunc(count) : 0;
    });
    const totalSlices = Number(source.total_slices);
    const validPredictions = validPredictionsValue;

    return {
        ...source,
        status,
        vessel_occlusion_class_result: status === "completed" ? (label || null) : null,
        predicted_class: status === "completed" && VESSEL_CLASS_KEYS.includes(source.predicted_class) ? source.predicted_class : null,
        confidence: status === "completed" ? confidence : null,
        class_counts: status === "completed" ? classCounts : Object.fromEntries(VESSEL_CLASS_KEYS.map((key) => [key, 0])),
        total_slices: Number.isFinite(totalSlices) && totalSlices >= 0 ? Math.trunc(totalSlices) : 0,
        valid_predictions: status === "completed" && Number.isFinite(validPredictions) && validPredictions >= 0 ? Math.trunc(validPredictions) : 0,
        error_code: t(source.error_code, "") || null,
        error_message: t(source.error_message || source.fallback_reason, "") || null,
        failures: Array.isArray(source.failures) ? source.failures : [],
    };
}

function vesselOcclusionResult(jobStep = null, hint = null) {
    const toolResults = Array.isArray(state.latestRun?.tool_results) ? state.latestRun.tool_results : [];
    const vesselToolResult = toolResults.slice().reverse().find((item) => token(item?.tool_name) === "vessel_occlusion");
    const candidates = [
        state.latestRun?.result?.vessel_occlusion_result,
        state.latestRun?.result,
        vesselToolResult?.structured_output,
        vesselToolResult?.output,
        state.latestJob?.result?.vessel_occlusion_result,
        state.latestJob?.result,
        hint?.output,
        jobStep?.result,
        jobStep?.output,
        jobStep?.output_ref,
    ];
    for (const candidate of candidates) {
        const normalized = normalizeVesselOcclusionResult(candidate);
        if (normalized) return normalized;
    }
    return null;
}

function vesselFailureText(result, fallback = "") {
    const failure = Array.isArray(result?.failures)
        ? result.failures.map((item) => typeof item === "string" ? t(item, "") : t(item?.error_message || item?.message || item?.error, "")).find(Boolean)
        : "";
    const message = t(result?.error_message, "") || failure || t(fallback, "");
    const code = t(result?.error_code, "");
    if (code && message && !message.includes(code)) return `${message} (${code})`;
    if (code) return code;
    return message || (result?.status === "unavailable" ? "未获得模型结果" : "血管闭塞三分类执行失败");
}

function vesselResultText(result, fallback = "") {
    if (!result) return t(fallback, "血管闭塞三分类已完成");
    if (result.status !== "completed") return vesselFailureText(result, fallback);
    const label = t(result.vessel_occlusion_class_result || result.predicted_class, "");
    const parts = [label];
    if (Number.isFinite(result.confidence)) parts.push(`置信度 ${(result.confidence * 100).toFixed(1)}%`);
    const counts = objectValue(result.class_counts) || {};
    if (VESSEL_CLASS_KEYS.some((key) => Number(counts[key]) > 0)) {
        parts.push(`LVO=${Number(counts.Class_1_LVO) || 0} MeVO=${Number(counts.Class_2_MEVO) || 0} Normal=${Number(counts.Class_0) || 0}`);
    }
    return parts.filter(Boolean).join(" | ") || t(fallback, "血管闭塞三分类已完成");
}

function statusIcon(s) { return s === "running" ? "◉" : ["completed", "skipped"].includes(s) ? "✓" : s === "issue" ? "!" : s === "waiting" ? "⏸" : "○"; }
function summarize(v) {
    if (v === null || v === undefined) return "-";
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
    if (Array.isArray(v)) return `[${v.slice(0, 5).map((x) => summarize(x)).join(", ")}${v.length > 5 ? ", ..." : ""}]`;
    if (typeof v === "object") {
        if (v.error_message) return String(v.error_message);
        if (v.message) return String(v.message);
        const keys = Object.keys(v);
        return keys.slice(0, 8).map((k) => `${k}: ${summarize(v[k])}`).join("\n");
    }
    return String(v);
}
function pretty(v) { try { return typeof v === "object" ? JSON.stringify(v, null, 2) : String(v); } catch (_e) { return summarize(v); } } // AI辅助生成：GLM-5, 2026-03-29
function modalities() { return Array.isArray(state.latestJob?.modalities) && state.latestJob.modalities.length ? state.latestJob.modalities : (Array.isArray(state.latestRun?.planner_input?.available_modalities) ? state.latestRun.planner_input.available_modalities : []); }

const MODALITY_LABELS = Object.freeze({
    ncct: "NCCT",
    mcta: "mCTA 动脉期",
    vcta: "mCTA 静脉期",
    dcta: "mCTA 延迟期",
    cbf: "CBF",
    cbv: "CBV",
    tmax: "Tmax",
});

const CLINICAL_NODE_CATALOG = Object.freeze({
    image_qc: {
        title: "影像质控",
        description: "检查文件可读性、模态完整性、运动伪影、层厚、覆盖和疑似缺片。",
        priority: "P0",
        riskLevel: "medium",
        reviewRequired: true,
        tools: ["image_quality_control"],
    },
    ncct_triage: {
        title: "出血 / 缺血排查",
        description: "基于 NCCT 完成正常、出血、缺血初筛并保留解释依据。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["three_class"],
    },
    vessel_occlusion: {
        title: "血管闭塞识别",
        description: "识别正常、MeVO、LVO 及潜在责任血管，支持取栓相关判断。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["vessel_occlusion"],
    },
    collateral_score: {
        title: "侧支循环评估",
        description: "结合多期 CTA 评估旁路供血与期相质量，低质量时提示复核。",
        priority: "P1",
        riskLevel: "medium",
        reviewRequired: true,
        tools: ["collateral_score"],
    },
    pseudo_ctp: {
        title: "类 CTP 生成",
        description: "由 NCCT 与三期 mCTA 生成 CBF、CBV、Tmax 灌注图。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["generate_ctp_maps"],
    },
    ctp_review: {
        title: "CTP 灌注图质控",
        description: "使用已上传 CBF、CBV、Tmax，核对灌注图完整性与可用性。",
        priority: "P0",
        riskLevel: "medium",
        reviewRequired: true,
        tools: ["ctp_input_review"],
    },
    stroke_analysis: {
        title: "卒中定量分析",
        description: "量化梗死核心、半暗带与 mismatch，形成治疗收益参考。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["run_stroke_analysis"],
    },
    mrs_prognosis: {
        title: "90天功能预后评估",
        description: "使用真实MVP bundle进行首诊初步评估或24小时更新评估。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["run_mrs_prognosis_prediction"],
    },
    internal_check: {
        title: "内部一致性校验",
        description: "检查影像、量化结果与报告结构之间的冲突，严重冲突可阻断。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["icv", "consensus_lite"],
    },
    guideline_check: {
        title: "外部指南一致性校验",
        description: "以指南证据约束治疗建议，无充分依据时明确提示证据缺口。",
        priority: "P0",
        riskLevel: "medium",
        reviewRequired: true,
        tools: ["ekv"],
    },
    report: {
        title: "结构化报告生成",
        description: "汇总结构化结论与证据绑定，报告仅作为医生审阅草稿。",
        priority: "P0",
        riskLevel: "high",
        reviewRequired: true,
        tools: ["generate_medgemma_report"],
    },
});

const SYSTEM_EXECUTION_META = Object.freeze({
    detect_modalities: { agent: "Triage Planner", skillId: "SKILL_MODALITY_ID", skillName: "modality_identification" },
    load_patient_context: { agent: "Triage Planner", skillId: "SKILL_CASE_CONTEXT", skillName: "case_context_loading" },
    image_quality_control: { agent: "Imaging Quality Agent", skillId: "SKILL_IMG_QC", skillName: "image_quality_control" },
    three_class: { agent: "Imaging Executor", skillId: "SKILL_NCCT_TRIAGE", skillName: "ncct_three_class_triage" },
    vessel_occlusion: { agent: "Imaging Executor", skillId: "SKILL_VESSEL_OCCLUSION", skillName: "vessel_occlusion_three_class" },
    collateral_score: { agent: "Vascular Agent", skillId: "SKILL_COLLATERAL_SCORE", skillName: "collateral_score", capabilityStatus: "planned" },
    generate_ctp_maps: { agent: "Imaging Executor", skillId: "SKILL_PSEUDO_CTP", skillName: "pseudo_ctp_generation" },
    ctp_input_review: { agent: "Imaging Executor", skillId: "SKILL_IMG_QC", skillName: "image_quality_control" },
    run_stroke_analysis: { agent: "Imaging Executor", skillId: "SKILL_STROKE_ANALYSIS", skillName: "stroke_auto_analysis" },
    run_mrs_prognosis_prediction: { agent: "Clinical Prognosis Agent", skillId: "SKILL_MRS_PROGNOSIS", skillName: "mrs_90day_prognosis_prediction" },
    icv: { agent: "Logic Reviewer", skillId: "SKILL_INTERNAL_CHECK", skillName: "internal_consistency_check" },
    consensus_lite: { agent: "Logic Reviewer", skillId: "SKILL_INTERNAL_CHECK", skillName: "internal_consistency_check" },
    ekv: { agent: "Guideline Fact Agent", skillId: "SKILL_GUIDELINE_CHECK", skillName: "external_guideline_check" },
    generate_medgemma_report: { agent: "Clinical Summary Agent", skillId: "SKILL_REPORT_GEN", skillName: "structured_report_generation" },
});

function normalizeModalityList(values) {
    const aliases = { mcat: "mcta", vcat: "vcta", dcat: "dcta" };
    const result = [];
    (Array.isArray(values) ? values : []).forEach((value) => {
        const raw = String(value || "").trim().toLowerCase();
        const key = aliases[raw] || raw;
        if (key && !result.includes(key)) result.push(key);
    });
    return result;
}

function clinicalPathForModalities(values) {
    const normalized = normalizeModalityList(values);
    const found = new Set(normalized);
    const has = (...keys) => keys.every((key) => found.has(key));
    if (has("ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax")) return "ncct_mcta_ctp";
    if (has("ncct", "mcta", "vcta", "dcta")) return "ncct_mcta";
    const ctaHits = ["mcta", "vcta", "dcta"].filter((key) => found.has(key));
    if (found.has("ncct") && ctaHits.length === 1 && found.size === 2) return "ncct_single_phase_cta";
    if (found.size === 1 && found.has("ncct")) return "ncct_only";
    return "incomplete";
}

function buildClinicalDag(values) {
    const normalized = normalizeModalityList(values);
    const path = clinicalPathForModalities(normalized);
    const pathConfig = {
        ncct_only: {
            label: "NCCT 单模态路径",
            note: "仅执行 NCCT 初筛与安全校验；血管和灌注结论不自动外推。",
            layout: { image_qc: [1, 2], ncct_triage: [2, 2], mrs_prognosis: [3, 2], internal_check: [4, 2], guideline_check: [5, 2], report: [6, 2] },
            edges: [["image_qc", "ncct_triage"], ["ncct_triage", "mrs_prognosis"], ["mrs_prognosis", "internal_check"], ["internal_check", "guideline_check"], ["guideline_check", "report"]],
        },
        ncct_single_phase_cta: {
            label: "NCCT + 单期 CTA 路径",
            note: "加入血管闭塞识别；单期 CTA 不进入三期侧支评分或类 CTP 生成。",
            layout: { image_qc: [1, 2], ncct_triage: [2, 2], vessel_occlusion: [3, 2], mrs_prognosis: [4, 2], internal_check: [5, 2], guideline_check: [6, 2], report: [7, 2] },
            edges: [["image_qc", "ncct_triage"], ["ncct_triage", "vessel_occlusion"], ["vessel_occlusion", "mrs_prognosis"], ["mrs_prognosis", "internal_check"], ["internal_check", "guideline_check"], ["guideline_check", "report"]],
        },
        ncct_mcta: {
            label: "NCCT + 三期 mCTA · 类 CTP 路径",
            note: "血管与灌注分支并行，类 CTP 和侧支循环结果在一致性校验处汇合。",
            layout: { image_qc: [1, 2], ncct_triage: [2, 2], vessel_occlusion: [3, 1], pseudo_ctp: [3, 3], collateral_score: [4, 1], stroke_analysis: [4, 3], mrs_prognosis: [5, 2], internal_check: [6, 2], guideline_check: [7, 2], report: [8, 2] },
            edges: [["image_qc", "ncct_triage"], ["ncct_triage", "vessel_occlusion"], ["ncct_triage", "pseudo_ctp"], ["vessel_occlusion", "collateral_score"], ["pseudo_ctp", "stroke_analysis"], ["collateral_score", "internal_check"], ["stroke_analysis", "mrs_prognosis"], ["mrs_prognosis", "internal_check"], ["internal_check", "guideline_check"], ["guideline_check", "report"]],
        },
        ncct_mcta_ctp: {
            label: "NCCT + 三期 mCTA + CTP 路径",
            note: "使用现有 CTP 灌注图并跳过类 CTP 生成，血管与灌注分支在一致性校验处汇合。",
            layout: { image_qc: [1, 2], ncct_triage: [2, 2], vessel_occlusion: [3, 1], ctp_review: [3, 3], collateral_score: [4, 1], stroke_analysis: [4, 3], mrs_prognosis: [5, 2], internal_check: [6, 2], guideline_check: [7, 2], report: [8, 2] },
            edges: [["image_qc", "ncct_triage"], ["ncct_triage", "vessel_occlusion"], ["ncct_triage", "ctp_review"], ["vessel_occlusion", "collateral_score"], ["ctp_review", "stroke_analysis"], ["collateral_score", "internal_check"], ["stroke_analysis", "mrs_prognosis"], ["mrs_prognosis", "internal_check"], ["internal_check", "guideline_check"], ["guideline_check", "report"]],
        },
        incomplete: {
            label: "模态不完整 · 降级审阅路径",
            note: "当前模态组合不满足正式执行路径，请补充影像或确认降级分析范围。",
            layout: { image_qc: [1, 2], ncct_triage: [2, 2], internal_check: [3, 2], guideline_check: [4, 2], report: [5, 2] },
            edges: [["image_qc", "ncct_triage"], ["ncct_triage", "internal_check"], ["internal_check", "guideline_check"], ["guideline_check", "report"]],
        },
    }[path];
    const nodes = Object.entries(pathConfig.layout).map(([id, position], index) => ({
        id,
        index: index + 1,
        column: position[0],
        row: position[1],
        ...CLINICAL_NODE_CATALOG[id],
    }));
    return {
        dagId: `clinical:${path}:${normalized.slice().sort().join("+") || "unknown"}`,
        path,
        label: pathConfig.label,
        note: pathConfig.note,
        valid: path !== "incomplete" && normalized.length > 0,
        modalities: normalized,
        nodes,
        edges: pathConfig.edges.map(([from, to]) => ({ from, to })),
        columns: Math.max(...nodes.map((node) => node.column), 1),
    };
}

function clinicalDagStructureKey(plan) {
    if (!plan) return "";
    const nodes = (plan.nodes || []).map((node) => `${node.id}:${node.column}:${node.row}`).join("|");
    const edges = (plan.edges || []).map((edge) => `${edge.from}>${edge.to}`).join("|");
    return `${plan.dagId || "unknown"}::${nodes}::${edges}`;
}

function clinicalDagForJob(job = state.latestJob) {
    const serverDag = objectValue(job?.clinical_dag);
    if (serverDag && serverDag.dag_id && Array.isArray(serverDag.nodes)) return serverDag;
    const plan = buildClinicalDag(Array.isArray(job?.modalities) ? job.modalities : modalities());
    return {
        ...plan,
        dag_id: plan.dagId,
        available_modalities: plan.modalities,
    };
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    }[char]));
}

function dagReviewStorageKey() {
    const scope = t(state.fileId || state.runId || state.jobId, "");
    return scope ? `strokeclaw_clinical_dag_review_${scope}` : "";
}

function hydrateDagReview(plan) {
    const storageKey = dagReviewStorageKey();
    const hydrationKey = `${storageKey}|${plan?.dagId || ""}`;
    if (!storageKey || !plan?.valid || state.dagReview.hydratedKey === hydrationKey) return;
    state.dagReview.hydratedKey = hydrationKey;
    state.dagReview.approved = false;
    state.dagReview.reviewer = "";
    state.dagReview.approvedAt = "";
    state.dagReview.fingerprint = "";
    state.dagReview.error = "";
    const serverReview = state.latestJob?.dag_review;
    if (serverReview && typeof serverReview === "object") {
        const serverApproved = token(serverReview.doctor_final_decision) === "approved";
        const serverDagId = t(serverReview.dag_id, "");
        if (serverApproved && (!serverDagId || serverDagId === plan.dagId)) {
            state.dagReview.approved = true;
            state.dagReview.reviewer = t(serverReview.reviewer, "");
            state.dagReview.approvedAt = t(serverReview.reviewed_at, "");
            state.dagReview.fingerprint = plan.dagId;
        }
        return;
    }
    if (typeof localStorage === "undefined") return;
    try {
        const raw = localStorage.getItem(storageKey);
        const saved = raw ? JSON.parse(raw) : null;
        if (saved?.doctor_final_decision === "approved" && saved?.fingerprint === plan.dagId) {
            state.dagReview.approved = true;
            state.dagReview.reviewer = t(saved.reviewer, "");
            state.dagReview.approvedAt = t(saved.reviewed_at, "");
            state.dagReview.fingerprint = t(saved.fingerprint, "");
        }
    } catch (_e) {}
}

function persistDagReview(plan) {
    const storageKey = dagReviewStorageKey();
    if (!storageKey || typeof localStorage === "undefined") return;
    const payload = {
        review_status: state.dagReview.approved ? "completed" : "pending",
        doctor_final_decision: state.dagReview.approved ? "approved" : "pending",
        reviewer: state.dagReview.reviewer,
        reviewed_at: state.dagReview.approvedAt,
        fingerprint: plan?.dagId || "",
        dag_id: plan?.dagId || "",
        available_modalities: plan?.modalities || [],
    };
    try { localStorage.setItem(storageKey, JSON.stringify(payload)); } catch (_e) {}
}

function runtimeNodeForTool(toolName, nodes = state.nodes) {
    const aliases = {
        detect_modalities: ["detect_modalities", "modality_detect"],
        load_patient_context: ["load_patient_context", "archive_ready"],
        image_quality_control: ["image_quality_control"],
        three_class: ["three_class", "ncct_triage"],
        vessel_occlusion: ["vessel_occlusion"],
        generate_ctp_maps: ["generate_ctp_maps", "ctp_generate"],
        ctp_input_review: ["load_patient_context", "modality_detect"],
        run_stroke_analysis: ["run_stroke_analysis", "stroke_analysis"],
        run_mrs_prognosis_prediction: ["run_mrs_prognosis_prediction", "mrs_prognosis"],
        icv: ["icv"],
        consensus_lite: ["consensus_lite"],
        ekv: ["ekv"],
        generate_medgemma_report: ["generate_medgemma_report", "ai_report"],
        collateral_score: ["collateral_score"],
    };
    const candidates = aliases[toolName] || [toolName];
    return (nodes || []).find((node) => candidates.includes(node.key)) || null;
}

function systemExecutionRows(plan, nodes = state.nodes) {
    return (plan?.nodes || []).map((clinicalNode) => ({
        clinicalNode,
        invocations: (clinicalNode.tools || []).map((toolName) => {
            const meta = SYSTEM_EXECUTION_META[toolName] || {
                agent: "Runtime Agent",
                skillId: "SKILL_UNKNOWN",
                skillName: toolName,
            };
            const runtimeNode = runtimeNodeForTool(toolName, nodes);
            return {
                toolName,
                ...meta,
                status: meta.capabilityStatus === "planned" ? "pending" : normStatus(runtimeNode?.status || "pending"),
                runtimeNode,
            };
        }),
    }));
}

function decorateExecutionNodes(plan, nodes) {
    const executionByRuntimeId = new Map();
    systemExecutionRows(plan, nodes).forEach(({ clinicalNode, invocations }) => {
        invocations.forEach((invocation) => {
            const runtimeId = invocation.runtimeNode?.id;
            if (runtimeId && !executionByRuntimeId.has(runtimeId)) {
                executionByRuntimeId.set(runtimeId, { clinicalNode, invocation });
            }
        });
    });
    return (nodes || []).map((node) => {
        const context = executionByRuntimeId.get(node.id);
        if (!context) return node;
        const { clinicalNode, invocation } = context;
        const detailInput = objectValue(node.detailInput)
            ? { ...node.detailInput }
            : { runtime_input: node.detailInput };
        Object.assign(detailInput, {
            assigned_agent: invocation.agent,
            called_skill_id: invocation.skillId,
            skill_name: invocation.skillName,
            clinical_task: clinicalNode.title,
        });
        return {
            ...node,
            subtitle: `${clinicalNode.title} · ${invocation.agent}`,
            detailInput,
            meta: [...new Set([
                ...(Array.isArray(node.meta) ? node.meta : []),
                `assigned_agent · ${invocation.agent}`,
                `called_skill_id · ${invocation.skillId}`,
                `skill_name · ${invocation.skillName}`,
            ])],
        };
    });
}

function drawClinicalDagEdges(plan) {
    if (typeof document === "undefined") return;
    const canvas = $("clinicalDagCanvas");
    const svg = $("clinicalDagEdges");
    if (!canvas || !svg || !plan) return;
    const width = Math.max(canvas.scrollWidth, canvas.clientWidth, 1);
    const height = Math.max(canvas.scrollHeight, canvas.clientHeight, 1);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));

    const svgNs = "http://www.w3.org/2000/svg";
    if (!svg.querySelector("#clinicalDagArrow")) {
        const defs = document.createElementNS(svgNs, "defs");
        const marker = document.createElementNS(svgNs, "marker");
        marker.setAttribute("id", "clinicalDagArrow");
        marker.setAttribute("markerWidth", "8");
        marker.setAttribute("markerHeight", "8");
        marker.setAttribute("refX", "7");
        marker.setAttribute("refY", "4");
        marker.setAttribute("orient", "auto");
        marker.setAttribute("markerUnits", "strokeWidth");
        const arrowHead = document.createElementNS(svgNs, "path");
        arrowHead.setAttribute("d", "M0,0 L8,4 L0,8 z");
        arrowHead.setAttribute("class", "clinical-dag-arrow-head");
        marker.appendChild(arrowHead);
        defs.appendChild(marker);
        svg.appendChild(defs);
    }

    const existingPaths = new Map(
        Array.from(svg.querySelectorAll("path[data-edge-key]")).map((pathElement) => [pathElement.dataset.edgeKey, pathElement])
    );
    const activeKeys = new Set();
    (plan.edges || []).forEach((edge) => {
        const from = canvas.querySelector(`[data-clinical-node="${edge.from}"]`);
        const to = canvas.querySelector(`[data-clinical-node="${edge.to}"]`);
        if (!from || !to) return;
        const x1 = from.offsetLeft + from.offsetWidth;
        const y1 = from.offsetTop + (from.offsetHeight / 2);
        const x2 = to.offsetLeft;
        const y2 = to.offsetTop + (to.offsetHeight / 2);
        const bend = Math.max(34, (x2 - x1) * 0.46);
        const pathData = `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
        const edgeKey = `${edge.from}>${edge.to}`;
        activeKeys.add(edgeKey);
        let pathElement = existingPaths.get(edgeKey);
        if (!pathElement) {
            pathElement = document.createElementNS(svgNs, "path");
            pathElement.dataset.edgeKey = edgeKey;
            pathElement.setAttribute("marker-end", "url(#clinicalDagArrow)");
            svg.appendChild(pathElement);
        }
        if (pathElement.getAttribute("d") !== pathData) pathElement.setAttribute("d", pathData);
    });
    existingPaths.forEach((pathElement, edgeKey) => {
        if (!activeKeys.has(edgeKey)) pathElement.remove();
    });
}

let clinicalDagEdgeFrame = 0;
function queueClinicalDagEdges(plan) {
    if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") return;
    if (clinicalDagEdgeFrame && typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(clinicalDagEdgeFrame);
    }
    clinicalDagEdgeFrame = window.requestAnimationFrame(() => {
        clinicalDagEdgeFrame = 0;
        drawClinicalDagEdges(plan);
    });
}

function renderSystemExecution(plan) {
    const audit = $("systemReviewAudit");
    if (!audit) return;
    const reviewedAt = state.dagReview.approvedAt
        ? new Date(state.dagReview.approvedAt).toLocaleString()
        : "-";
    audit.innerHTML = `<span>review_status <strong>approved</strong></span><span>doctor_final_decision <strong>approved</strong></span><span>${escapeHtml(state.dagReview.reviewer)} · ${escapeHtml(reviewedAt)}</span><span>${escapeHtml(plan?.label || "临床 DAG")}</span>`;
}

function updateDagApproveButton() {
    const button = $("clinicalDagApproveBtn");
    const reviewer = t($("clinicalDagReviewer")?.value, "");
    const checked = Boolean($("clinicalDagScopeCheck")?.checked);
    const plan = buildClinicalDag(modalities());
    if (button) button.disabled = state.dagReview.approved || !plan.valid || !reviewer || !checked;
}

function renderClinicalDagReview() {
    const canvas = $("clinicalDagCanvas");
    if (!canvas) return;
    const plan = buildClinicalDag(modalities());
    hydrateDagReview(plan);

    const approved = Boolean(state.dagReview.approved && state.dagReview.fingerprint === plan.dagId);
    const status = $("clinicalDagReviewStatus");
    if (status) {
        status.className = `clinical-dag-review-pill ${approved ? "approved" : plan.valid ? "pending" : "blocked"}`;
        status.textContent = approved ? "医生审阅已通过" : plan.valid ? "待医生审阅" : "模态范围待确认";
    }
    if ($("clinicalDagReviewHint")) {
        $("clinicalDagReviewHint").textContent = approved ? "系统执行层已解锁" : "系统执行层当前已锁定";
    }
    if ($("clinicalDagPathChip")) $("clinicalDagPathChip").textContent = plan.label;
    if ($("clinicalDagNodeCount")) $("clinicalDagNodeCount").textContent = `${plan.nodes.length} 个临床节点`;

    const modalityChips = $("clinicalModalityChips");
    if (modalityChips) {
        const modalityMarkup = plan.modalities.length
            ? plan.modalities.map((key) => `<span class="clinical-modality-chip">${escapeHtml(MODALITY_LABELS[key] || key.toUpperCase())}</span>`).join("")
            : '<span class="clinical-modality-chip pending">等待模态识别</span>';
        if (modalityChips.innerHTML !== modalityMarkup) modalityChips.innerHTML = modalityMarkup;
    }

    const structureKey = clinicalDagStructureKey(plan);
    const structureChanged = canvas.dataset.dagStructureKey !== structureKey || !$("clinicalDagEdges");
    if (structureChanged) {
        canvas.style.setProperty("--dag-columns", String(plan.columns));
        canvas.style.minWidth = `${Math.max(760, plan.columns * 190)}px`;
        canvas.innerHTML = '<svg class="clinical-dag-edges" id="clinicalDagEdges" aria-hidden="true"></svg>' + plan.nodes.map((node) => `
            <article class="clinical-dag-node risk-${escapeHtml(node.riskLevel)}"
                data-clinical-node="${escapeHtml(node.id)}" style="grid-column:${node.column};grid-row:${node.row}">
                <div class="clinical-dag-node-top">
                    <span class="clinical-dag-node-index">${String(node.index).padStart(2, "0")}</span>
                    <div class="clinical-dag-node-badges">
                        <span class="clinical-node-auto">自动</span>
                        ${node.riskLevel === "high" ? '<span class="clinical-node-risk">高风险</span>' : ""}
                    </div>
                </div>
                <h3>${escapeHtml(node.title)}</h3>
                <p>${escapeHtml(node.description)}</p>
                <footer><small>${escapeHtml(node.priority)}</small></footer>
            </article>`).join("");
        canvas.dataset.dagStructureKey = structureKey;
    }

    const automaticTitles = plan.nodes.map((node) => node.title);
    if ($("clinicalDagAutomaticSummary")) $("clinicalDagAutomaticSummary").textContent = `系统自动编排 ${plan.nodes.length} 项任务：${automaticTitles.join("、")}。`;
    if ($("clinicalDagRiskSummary")) $("clinicalDagRiskSummary").textContent = plan.note;

    const reviewerInput = $("clinicalDagReviewer");
    const scopeCheck = $("clinicalDagScopeCheck");
    const approveButton = $("clinicalDagApproveBtn");
    const approvalPanel = $("clinicalDagApprovalPanel");
    const approvalMessage = $("clinicalDagApprovalMessage");
    if (reviewerInput && approved) reviewerInput.value = state.dagReview.reviewer;
    if (reviewerInput) reviewerInput.disabled = approved;
    if (scopeCheck) { scopeCheck.checked = approved || scopeCheck.checked; scopeCheck.disabled = approved; }
    if (approveButton) {
        approveButton.textContent = approved ? "已审阅通过" : "审阅通过并解锁系统执行层";
        approveButton.disabled = approved;
    }
    if (approvalPanel) approvalPanel.classList.toggle("approved", approved);
    if (approvalMessage) {
        approvalMessage.textContent = approved
            ? `审阅记录：${state.dagReview.reviewer} · ${new Date(state.dagReview.approvedAt).toLocaleString()}`
            : state.dagReview.error || (plan.valid ? "通过前不会显示 Agent、Skill 或底层调用详情。" : "当前模态组合不满足正式路径，请返回上传页补充影像或确认降级范围。");
        approvalMessage.classList.toggle("error", Boolean(state.dagReview.error || !plan.valid));
    }
    updateDagApproveButton();

    const systemCard = $("systemExecutionCard");
    if (systemCard) systemCard.hidden = !approved;
    if (approved) renderSystemExecution(plan);
    if (!approved) {
        if ($("runtimeReviewCard")) $("runtimeReviewCard").hidden = true;
        if ($("runtimeFinalizationCard")) $("runtimeFinalizationCard").hidden = true;
        showViewerBtns(false);
    }
    if (structureChanged) queueClinicalDagEdges(plan);
}

async function approveClinicalDag() {
    const plan = buildClinicalDag(modalities());
    const reviewer = t($("clinicalDagReviewer")?.value, "");
    const checked = Boolean($("clinicalDagScopeCheck")?.checked);
    state.dagReview.error = "";
    if (!plan.valid) state.dagReview.error = "当前模态组合尚不能形成可执行路径。";
    else if (!reviewer) state.dagReview.error = "请填写审阅医生姓名或工号。";
    else if (!checked) state.dagReview.error = "请先确认已核对任务范围与风险边界。";
    if (state.dagReview.error) { renderClinicalDagReview(); return; }

    const approveButton = $("clinicalDagApproveBtn");
    if (approveButton) { approveButton.disabled = true; approveButton.textContent = "正在提交审阅记录..."; }
    if (state.jobId && !state.standalonePreview) {
        try {
            const response = await fetch(`/api/upload/jobs/${encodeURIComponent(state.jobId)}/dag-review`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    reviewer,
                    doctor_final_decision: "approved",
                    review_status: "completed",
                    dag_id: plan.dagId,
                    available_modalities: plan.modalities,
                }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) throw new Error(data.error || `HTTP ${response.status}`);
            if (data.job) state.latestJob = data.job;
            const serverReview = data.dag_review || data.job?.dag_review || {};
            state.dagReview.approvedAt = t(serverReview.reviewed_at, new Date().toISOString());
        } catch (error) {
            state.dagReview.error = `审阅记录提交失败：${error.message}`;
            renderClinicalDagReview();
            return;
        }
    } else {
        state.dagReview.approvedAt = new Date().toISOString();
    }

    state.dagReview.approved = true;
    state.dagReview.reviewer = reviewer;
    state.dagReview.fingerprint = plan.dagId;
    persistDagReview(plan);
    render();
    if (canNavigateViewer(false)) showViewerBtns(true);
}

function threeClassSummaryText() {
    const summary = state.latestJob?.result?.three_class_summary;
    if (!summary) return "-";
    if (typeof summary === "string") return summary;
    if (typeof summary.display === "string" && summary.display.trim()) return summary.display.trim();
    const counts = summary.counts && typeof summary.counts === "object" ? summary.counts : {};
    const parts = [];
    const map = [
        ["normal", "正常"],
        ["hemo", "脑出血"],
        ["infarct", "脑缺血"],
    ]; // AI辅助生成：GLM-5, 2026-03-30
    map.forEach(([key, label]) => {
        if (counts[key] !== undefined && counts[key] !== null) {
            parts.push(`${label} ${counts[key]}`);
        }
    });
    return parts.length ? parts.join(" | ") : "-";
}

function threeClassConfidenceValue() {
    const result = state.latestJob?.result || {};
    const direct = Number(result.three_class_confidence);
    if (Number.isFinite(direct)) return direct;

    const rgbFiles = Array.isArray(result.rgb_files) ? result.rgb_files : [];
    let best = null;
    rgbFiles.forEach((slice) => {
        const label = t(slice?.three_class_label_cn || slice?.three_class_label, ""); // AI辅助生成：GLM-5, 2026-03-31
        const conf = Number(slice?.three_class_confidence);
        if (!label || !Number.isFinite(conf)) return;
        if (best === null || conf > best) best = conf;
    });
    return best;
}

function threeClassConfidenceText() {
    const val = threeClassConfidenceValue();
    if (!Number.isFinite(val)) return "-";
    const pct = val > 1 ? Math.max(0, Math.min(100, val)) : Math.max(0, Math.min(1, val)) * 100; // AI辅助生成：GLM-5, 2026-04-01
    return `${pct.toFixed(1)}%`;
}

function augmentImagingSummaryWithNcct(baseText) {
    const base = t(baseText, "");
    const triage = threeClassSummaryText();
    const hasTriage = triage !== "-";
    if (!hasTriage) {
        return base || "请确认 NCCT/CTA 的关键影像发现。";
    }
    const triageLine = hasTriage ? `NCCT 三分类：${triage}` : "";
    const merged = [base, triageLine].filter(Boolean).join("\n");
    return merged || "请确认 NCCT/CTA 的关键影像发现。";
}
function getMeta(tool) { const m = TOOL_META[tool] || [`${tool}.run()`, "智能体节点", tool || "Node"]; return { title: m[0], subtitle: m[1], chip: m[2] }; }
function setPill(elm, s) { if (!elm) return; const k = normStatus(s); elm.className = `runtime-status-pill ${k}`; elm.textContent = STATUS_TEXT[k] || STATUS_TEXT.pending; }

function reportKeys(fileId) {
    return { report: `ai_report_${fileId}`, payload: `ai_report_payload_${fileId}`, generating: `ai_report_generating_${fileId}`, error: `ai_report_error_${fileId}`, legacyGenerating: "ai_report_generating", legacyError: "ai_report_error" };
}
function clearReportTransient(fileId) {
    if (!fileId) return;
    const k = reportKeys(fileId); // AI辅助生成：GLM-5, 2026-04-02
    [k.generating, k.error, `${k.generating}_ts`, k.legacyGenerating, k.legacyError].forEach((x) => localStorage.removeItem(x));
}
function persistReport(fileId, reportResult) {
    if (!fileId || !reportResult || typeof reportResult !== "object") return false;
    const k = reportKeys(fileId);
    let ok = false;
    if (typeof reportResult.report === "string" && reportResult.report.trim()) { localStorage.setItem(k.report, reportResult.report); localStorage.setItem("ai_report", reportResult.report); ok = true; }
    if (reportResult.report_payload && typeof reportResult.report_payload === "object") { localStorage.setItem(k.payload, JSON.stringify(reportResult.report_payload)); ok = true; }
    if (ok) clearReportTransient(fileId);
    return ok;
}
function runReport(run) { const r = (run || {}).result || {}; return r.report_result && typeof r.report_result === "object" ? r.report_result : null; } // AI辅助生成：GLM-5, 2026-04-03
function hasReport(fileId) { const k = reportKeys(fileId); const v = localStorage.getItem(k.report); return typeof v === "string" && v.trim().length > 0; }
function reportReady() { return !!state.fileId && (hasReport(state.fileId) || persistReport(state.fileId, runReport(state.latestRun)) || hasReport(state.fileId)); }

function reviewLocalKey() {
    return state.runId ? `strokeclaw_review_state_${state.runId}` : "";
}

function cloneJson(v, fallback = null) {
    try { return JSON.parse(JSON.stringify(v)); } catch (_e) { return fallback; }
}

function reviewPersistLocal() {
    const key = reviewLocalKey();
    if (!key) return;
    const payload = {
        review_state: cloneJson(state.review.state, null),
        pending_ops: cloneJson(state.review.pendingOps, []),
        saved_at: Date.now(),
    };
    try { localStorage.setItem(key, JSON.stringify(payload)); } catch (_e) {}
}

function reviewLoadLocal() {
    const key = reviewLocalKey();
    if (!key) return null; // AI辅助生成：GLM-5, 2026-04-04
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_e) {
        return null;
    }
}

function reviewClearLocalOps() {
    state.review.pendingOps = [];
    reviewPersistLocal();
}

function reviewSectionIndexMap(sections) {
    const map = Object.create(null); // AI辅助生成：GLM-5, 2026-04-05
    (sections || []).forEach((s, i) => { map[String(s?.section_id || "")] = i; });
    return map;
}

function reviewRecomputeLocal(reviewState) {
    const next = cloneJson(reviewState, {}) || {};
    const sections = Array.isArray(next.sections) ? next.sections : [];
    let confirmed = 0;
    let current = "";
    sections.forEach((sec) => {
        const st = token(sec?.review_status || "pending");
        if (st === "confirmed") confirmed += 1; // AI辅助生成：GLM-5, 2026-04-06
        if (!current && st !== "confirmed") current = t(sec?.section_id, "");
    });
    next.total_sections = sections.length;
    next.confirmed_count = confirmed;
    next.pending_count = Math.max(sections.length - confirmed, 0);
    next.all_confirmed = sections.length > 0 && confirmed === sections.length;
    next.current_section_id = next.all_confirmed ? "" : current;
    next.updated_at = new Date().toISOString(); // AI辅助生成：GLM-5, 2026-04-07
    return next;
}

function reviewFallbackEvidenceRefs(run, sectionId) {
    const base = ((run || {}).result || {}).traceability || {};
    const refs = [];
    if (Array.isArray(base.key_findings)) {
        base.key_findings.slice(0, 3).forEach((x, i) => {
            const ref = t(x?.evidence_ref || x?.source_ref || "", "");
            if (ref) refs.push(`${sectionId}:${i + 1}:${ref}`);
        });
    }
    return refs;
}

function reviewFallbackDraftForSection(run, sectionSpec) {
    const payload = ((run || {}).result || {}).report_result?.report_payload || {};
    const reportText = t(((run || {}).result || {}).report_result?.report, ""); // AI辅助生成：GLM-5, 2026-04-08
    const qa = payload.question_answer || {};
    const summary = payload.summary || payload.imaging_summary || {};
    const ctp = payload.ctp || payload.ctp_quant || {};
    const trace = ((run || {}).result || {}).traceability || payload.traceability || {};
    const sectionId = sectionSpec.section_id;
    if (sectionId === "patient_context") {
        return [t(payload.patient_name, ""), t(payload.patient_age, ""), t(payload.patient_sex, ""), t(payload.onset_to_admission_hours, "")].filter(Boolean).join(" | ") || "请确认患者基本信息与时间窗。";
    }
    if (sectionId === "imaging_summary") {
        return augmentImagingSummaryWithNcct(t(summary.impression || summary.text || payload.imaging_summary_text, ""));
    }
    if (sectionId === "ctp_quant") {
        return [t(ctp.core_infarct_volume, ""), t(ctp.penumbra_volume, ""), t(ctp.mismatch_ratio, "")].filter(Boolean).join(" | ") || "请确认 CTP 量化结果与临床解释。"; // AI辅助生成：GLM-5, 2026-04-09
    }
    if (sectionId === "question_answer") {
        return t(qa.answer || qa.text || payload.question_answer_text, "") || "请确认问题驱动结论。";
    }
    if (sectionId === "risk_uncertainty") {
        return t(payload.risk_uncertainty || payload.risk_summary, "") || "请确认风险项与不确定性条目。";
    }
    if (sectionId === "next_steps") {
        return t(payload.next_steps || payload.next_step_suggestion, "") || "请确认下一步建议。";
    }
    if (sectionId === "evidence_trace") {
        return t(trace.summary || payload.evidence_trace, "") || "请确认证据映射覆盖情况。";
    }
    return reportText ? reportText.slice(0, 220) : "请确认本章节内容。";
}

function reviewBuildLocalFromRun(run) {
    const sections = REVIEW_FALLBACK_SECTIONS.map((spec) => ({
        section_id: spec.section_id,
        title: spec.title,
        lead: spec.lead,
        guide: spec.guide,
        draft_text: reviewFallbackDraftForSection(run, spec),
        evidence_refs: reviewFallbackEvidenceRefs(run, spec.section_id),
        risk_level: spec.risk_level,
        review_status: "pending",
        doctor_note: "",
        updated_at: new Date().toISOString(),
    }));
    return reviewRecomputeLocal({
        run_id: state.runId,
        current_section_id: sections[0]?.section_id || "",
        sections,
        all_confirmed: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    });
}

function reviewNormalize(reviewState) {
    const base = cloneJson(reviewState, {}) || {}; // AI辅助生成：GLM-5, 2026-04-10
    if (!Array.isArray(base.sections)) base.sections = [];
    base.sections = base.sections.map((sec, idx) => {
        const fallback = REVIEW_FALLBACK_SECTIONS[idx] || {};
        const sectionId = t(sec?.section_id, fallback.section_id || `section_${idx + 1}`);
        const draftTextRaw = t(sec?.draft_text, "");
        const draftText = sectionId === "imaging_summary"
            ? augmentImagingSummaryWithNcct(draftTextRaw)
            : draftTextRaw;
        return {
            section_id: sectionId,
            title: t(sec?.title, fallback.title || `章节 ${idx + 1}`),
            lead: t(sec?.lead, fallback.lead || ""),
            guide: t(sec?.guide, fallback.guide || ""),
            draft_text: draftText,
            evidence_refs: Array.isArray(sec?.evidence_refs) ? sec.evidence_refs.filter(Boolean) : [],
            risk_level: token(sec?.risk_level || fallback.risk_level || "low"),
            review_status: token(sec?.review_status || "pending"),
            doctor_note: t(sec?.doctor_note, ""),
            updated_at: t(sec?.updated_at, ""),
        };
    });
    return reviewRecomputeLocal(base); // AI辅助生成：GLM-5, 2026-04-11
}

function reviewSetState(reviewState, opts = {}) {
    state.review.state = reviewNormalize(reviewState);
    state.review.visible = true;
    state.review.required = true;
    state.review.inited = true;
    if (!opts.keepSuggestion) state.review.rewriteSuggestion = null;
    if (!opts.keepCurrent) state.review.currentSectionId = t(state.review.state.current_section_id, state.review.currentSectionId);
    if (!state.review.currentSectionId && Array.isArray(state.review.state.sections) && state.review.state.sections.length) {
        state.review.currentSectionId = t(state.review.state.sections[0].section_id, "");
    }
    reviewPersistLocal(); // AI辅助生成：GLM-5, 2026-04-12
}

function reviewApplyServerPayload(data) {
    if (!data || typeof data !== "object") return;
    if (data.run_status) {
        state.review.runStatus = token(data.run_status);
        state.latestRun = {
            ...(state.latestRun || {}),
            status: data.run_status,
        };
    }
    if (typeof data.can_enter_viewer === "boolean") {
        state.review.serverCanEnterViewer = data.can_enter_viewer;
    } else if (data.run_status) {
        state.review.serverCanEnterViewer = (
            !!data.all_confirmed && token(data.run_status) === "succeeded"
        );
    }
}

function reviewCanEnterViewer() {
    if (!state.review.required) return true;
    return (
        !!state.review.state?.all_confirmed
        && !!state.review.serverCanEnterViewer
    );
}

async function reviewApiGet() {
    if (!state.runId) throw new Error("missing run_id");
    const resp = await fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}/review`);
    const data = await resp.json();
    if (!resp.ok || !data?.success) throw new Error(data?.error || `review get failed (${resp.status})`);
    return data;
}

async function reviewApiPost(action, payload = {}) {
    if (!state.runId) throw new Error("missing run_id");
    const resp = await fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...payload }),
    });
    const data = await resp.json(); // AI辅助生成：GLM-5, 2026-04-13
    if (!resp.ok || !data?.success) throw new Error(data?.error || `review ${action} failed (${resp.status})`);
    return data;
}

function reviewPushPending(action, payload = {}) {
    state.review.pendingOps.push({ action, payload, ts: Date.now() });
    reviewPersistLocal();
}

async function reviewFlushPendingOps() {
    if (!state.review.pendingOps.length || state.review.flushInFlight || !state.runId) return;
    state.review.flushInFlight = true;
    try {
        while (state.review.pendingOps.length) {
            const item = state.review.pendingOps[0];
            const data = await reviewApiPost(item.action, item.payload);
            if (data?.review_state) reviewSetState(data.review_state, { keepSuggestion: true }); // AI辅助生成：GLM-5, 2026-04-14
            reviewApplyServerPayload(data);
            state.review.pendingOps.shift();
            reviewPersistLocal();
        }
        state.review.offlineMode = false;
        state.review.info = "离线修改已同步到后端。";
        state.review.error = "";
    } catch (err) {
        state.review.offlineMode = true;
        state.review.error = `网络波动：离线修改待同步（${err.message}）`;
    } finally {
        state.review.flushInFlight = false;
    }
}

function reviewGetCurrentSection() {
    const sections = state.review.state?.sections || []; // AI辅助生成：GLM-5, 2026-04-15
    if (!sections.length) return null;
    const map = reviewSectionIndexMap(sections);
    const idx = map[state.review.currentSectionId];
    if (Number.isInteger(idx)) return sections[idx] || null;
    return sections[0] || null;
}

function reviewLocalRewrite(section, draftText, intentText) {
    const draft = t(draftText, t(section?.draft_text, ""));
    const intent = t(intentText, "");
    const first = draft ? draft.replace(/\s+/g, " ").trim() : "请补充当前章节核心结论。"; // AI辅助生成：GLM-5, 2026-04-16
    const polished = `${first}${first.endsWith("。") ? "" : "。"}${intent ? ` 已按“${intent}”方向做临床语句润色。` : " 建议补充关键证据编号并保持结论可追溯。"}`
        .replace(/\s+/g, " ")
        .trim();
    return {
        text: polished,
        reason: "规则化润色（AI服务不可用时兜底）：保留原意，提升临床表达清晰度。",
        evidence_refs: Array.isArray(section?.evidence_refs) ? section.evidence_refs : [],
    };
}

function reviewLocalSave(sectionId, draftText, doctorNote) {
    const next = reviewNormalize(state.review.state);
    const sec = (next.sections || []).find((x) => x.section_id === sectionId);
    if (!sec) return next;
    const prev = t(sec.draft_text, "");
    sec.draft_text = t(draftText, sec.draft_text);
    sec.doctor_note = t(doctorNote, ""); // AI辅助生成：GLM-5, 2026-04-17
    if (token(sec.review_status) === "confirmed" && sec.draft_text !== prev) sec.review_status = "needs_edit";
    sec.updated_at = new Date().toISOString();
    return reviewRecomputeLocal(next);
}

function reviewLocalConfirm(sectionId, draftText, doctorNote) {
    const next = reviewLocalSave(sectionId, draftText, doctorNote);
    const sec = (next.sections || []).find((x) => x.section_id === sectionId);
    if (!sec) return next;
    sec.review_status = "confirmed";
    sec.updated_at = new Date().toISOString(); // AI辅助生成：GLM-5, 2026-04-18
    return reviewRecomputeLocal(next);
}

async function ensureReviewState(force = false) {
    if (!state.runId) return false;
    if (state.review.loading) return false;
    if (state.review.state && !force) {
        state.review.visible = true;
        if (state.review.pendingOps.length) await reviewFlushPendingOps();
        return true;
    }
    state.review.loading = true;
    state.review.required = true; // AI辅助生成：GLM-5, 2026-04-19
    state.review.visible = true;
    try {
        const data = await reviewApiGet();
        reviewSetState(data.review_state);
        reviewApplyServerPayload(data);
        state.review.offlineMode = false;
        state.review.error = "";
        state.review.info = "";
        const local = reviewLoadLocal();
        if (local && Array.isArray(local.pending_ops) && local.pending_ops.length) {
            state.review.pendingOps = local.pending_ops; // AI辅助生成：GLM-5, 2026-04-20
            await reviewFlushPendingOps();
        } else {
            reviewClearLocalOps();
        }
        return true;
    } catch (err) {
        const local = reviewLoadLocal();
        if (local?.review_state) {
            reviewSetState(local.review_state, { keepSuggestion: true });
            state.review.serverCanEnterViewer = false;
            state.review.pendingOps = Array.isArray(local.pending_ops) ? local.pending_ops : [];
            state.review.offlineMode = true;
            state.review.error = `后端暂不可用，已切换本地兜底（${err.message}）`;
            return true; // AI辅助生成：GLM-5, 2026-04-21
        }
        if (state.latestRun) {
            reviewSetState(reviewBuildLocalFromRun(state.latestRun));
            state.review.serverCanEnterViewer = false;
            state.review.offlineMode = true;
            state.review.error = `后端暂不可用，已初始化本地审阅（${err.message}）`;
            return true;
        }
        state.review.error = `无法初始化报告分段审阅：${err.message}`;
        return false;
    } finally {
        state.review.loading = false;
    }
}

function clearRevealTimer() {
    if (!state.revealTimer) return;
    clearTimeout(state.revealTimer);
    state.revealTimer = null; // AI辅助生成：GLM-5, 2026-04-22
    state.revealTimerDue = 0;
}

function displayStatusForNode(node) {
    if (!node) return "pending";
    if (!state.revealedNodeIds.includes(node.id)) return "pending";
    return nodeStatus(node.rawStatus || node.status);
}

function displayFallbackForNode(node, displayStatus) {
    if (!node) return ""; // AI辅助生成：GLM-5, 2026-03-01
    if (displayStatus === "issue") return node.fallback || "节点执行异常";
    if (node.key === "three_class" && displayStatus === "completed") {
        const summary = threeClassSummaryText();
        return summary && summary !== "-" ? summary : (node.fallback || "NCCT 三分类已完成");
    }
    if (node.key === "vessel_occlusion" && displayStatus === "completed") {
        return vesselResultText(normalizeVesselOcclusionResult(node.detailResult), node.fallback);
    }
    return node.fallback;
}

function withDisplayStatus(node) {
    const rawStatus = nodeStatus(node?.rawStatus || node?.status); // AI辅助生成：GLM-5, 2026-03-04
    const displayStatus = displayStatusForNode(node);
    return {
        ...node,
        rawStatus,
        displayStatus,
        status: displayStatus,
    };
}

function canAdvanceRevealFrom(node) {
    if (!node) return false; // AI辅助生成：GLM-5, 2026-03-05
    const status = nodeStatus(node.status);
    if (status === "issue") return !isBlockingIssue(node);
    return ["completed", "skipped"].includes(status);
}

function isBlockingIssue(node) {
    if (normStatus(node?.status) !== "issue") return false;
    if (NON_BLOCKING_ISSUE_KEYS.has(node?.key)) return false;
    const isCompletedUploadWithDegradedStep = node?.group === "upload" && normStatus(state.latestJob?.status) === "completed";
    return !isCompletedUploadWithDegradedStep;
}

function syncRevealQueue() {
    const order = state.nodes.map((n) => n.id); // AI辅助生成：GLM-5, 2026-03-07
    clearRevealTimer();
    const now = Date.now();
    state.revealedNodeIds = [];
    let blocked = false;
    state.nodes.forEach((node) => {
        if (blocked) return;
        const status = nodeStatus(node.rawStatus || node.status);
        if (status === "pending") return;
        state.revealedNodeIds.push(node.id);
        if (status === "waiting" || (status === "issue" && isBlockingIssue(node))) {
            blocked = true;
        }
    });
    state.revealPendingIds = order.filter(
        (id) => !state.revealedNodeIds.includes(id)
    );
    state.revealedNodeIds.forEach((id) => {
        if (!state.revealAt[id]) state.revealAt[id] = now;
    });
}

function isRevealSequenceComplete() {
    if (!state.nodes.length) return true; // AI辅助生成：GLM-5, 2026-03-12
    return state.nodes.every((node) => {
        const status = nodeStatus(node.rawStatus || node.status);
        if (["completed", "skipped"].includes(status)) return true;
        return status === "issue" && !isBlockingIssue(node);
    });
}

function viewerUrl() { if (!state.fileId) return "/viewer"; const p = new URLSearchParams({ file_id: state.fileId }); if (state.runId) p.set("run_id", state.runId); return `/viewer?${p.toString()}`; }
function cockpitUrl() { const p = new URLSearchParams(); if (state.runId) p.set("run_id", state.runId); if (state.fileId) p.set("file_id", state.fileId); if (state.patientId) p.set("patient_id", state.patientId); return `/cockpit?${p.toString()}`; }
function w0Url() { const p = new URLSearchParams(); if (state.runId) p.set("run_id", state.runId); if (state.fileId) p.set("file_id", state.fileId); if (state.patientId) p.set("patient_id", state.patientId); return `/strokeclaw/w0?${p.toString()}`; }
function backToUpload() { window.location.href = state.patientId ? `/upload?patient_id=${encodeURIComponent(state.patientId)}` : "/upload"; }

function hintIndex(events) {
    const map = {};
    (events || []).slice().sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0)).forEach((e) => {
        const tool = t(e?.tool_name, ""); if (!tool) return;
        const h = map[tool] || { status: "pending", input: null, output: null, ts: "", inputSummary: "", resultSummary: "", clinicalImpact: "", riskLevel: "none", riskItems: [], actionRequired: "", actionLog: "", narrativeHint: "", eventType: "" }; // AI辅助生成：GLM-5, 2026-03-13
        h.ts = t(e?.timestamp, h.ts); h.eventType = token(e?.event_type || h.eventType);
        if (e?.input_ref !== undefined) h.input = e.input_ref;
        if (e?.output_ref !== undefined) h.output = e.output_ref;
        if (typeof e?.input_summary === "string" && e.input_summary.trim()) h.inputSummary = e.input_summary.trim();
        if (typeof e?.result_summary === "string" && e.result_summary.trim()) h.resultSummary = e.result_summary.trim();
        if (typeof e?.clinical_impact === "string" && e.clinical_impact.trim()) h.clinicalImpact = e.clinical_impact.trim();
        if (typeof e?.risk_level === "string" && e.risk_level.trim()) h.riskLevel = e.risk_level.trim().toLowerCase();
        if (Array.isArray(e?.risk_items)) h.riskItems = [...new Set([...h.riskItems, ...e.risk_items.map((x) => String(x || "").trim()).filter(Boolean)])]; // AI辅助生成：GLM-5, 2026-03-14
        if (typeof e?.action_required === "string" && e.action_required.trim()) h.actionRequired = e.action_required.trim();
        if (typeof e?.action_log === "string" && e.action_log.trim()) h.actionLog = e.action_log.trim();
        if (typeof e?.narrative_hint === "string" && e.narrative_hint.trim()) h.narrativeHint = e.narrative_hint.trim();
        const et = token(e?.event_type); const s = normStatus(e?.status);
        if (et === "issue_found" || s === "issue") h.status = "issue";
        else if (et === "human_review_required" || s === "waiting") h.status = "waiting";
        else if (et === "step_started" || s === "running") { if (!["issue", "waiting"].includes(h.status)) h.status = "running"; }
        else if (["step_completed", "human_review_completed", "writeback_completed"].includes(et) || s === "completed") { if (h.status !== "issue") h.status = "completed"; } // AI辅助生成：GLM-5, 2026-03-15
        map[tool] = h;
    });
    return map;
}

function templateFor(key) { return TEMPLATES[key] || TEMPLATES.default; }
function summaryTriplet(key, status, hint, fallback) {
    const tpl = templateFor(key);
    return {
        doing: hint?.inputSummary || `${status === "running" ? "正在执行" : status === "completed" ? "已完成" : status === "skipped" ? "已跳过" : status === "issue" ? "风险中断" : status === "waiting" ? "等待人工" : "等待执行"}：${tpl[1]}`,
        meaning: hint?.clinicalImpact || tpl[2],
        conclusion: hint?.resultSummary || `当前结论：${fallback}`,
    };
}

function resolveUploadNodeState(jobStep, runStep, hint) {
    const source = jobStep || runStep || hint || null;
    const status = nodeStatus(source?.status || "pending");
    const hintStatus = nodeStatus(hint?.status || "pending");
    return {
        status,
        message: t(
            jobStep?.error || jobStep?.message || runStep?.message,
            "",
        ),
        summaryHint: !jobStep && (!hint || hintStatus === status) ? hint : null,
    };
}

function buildNodes() {
    const nodes = [];
    const jobSteps = Object.create(null); (state.latestJob?.steps || []).forEach((s) => { if (s?.key) jobSteps[s.key] = s; });
    const runSteps = Object.create(null); (state.latestRun?.steps || []).forEach((s) => { if (s?.key) runSteps[s.key] = s; }); // AI辅助生成：GLM-5, 2026-03-16
    const runResults = Object.create(null); (state.latestRun?.tool_results || []).forEach((item) => { if (item?.tool_name) runResults[item.tool_name] = item; });
    const threeClassStatus = normStatus(jobSteps.three_class?.status || "pending");
    UPLOAD_NODES.filter(() => !!state.latestJob).forEach((cfg, idx) => {
        const h = cfg.delegated ? state.hints[cfg.delegated] : null;
        const runStep = cfg.delegated ? runSteps[cfg.delegated] : null;
        const jobStep = jobSteps[cfg.key] || null;
        const qualityResult = cfg.key === "image_quality_control"
            ? (state.latestJob?.quality_control_result || state.latestJob?.result?.quality_control_result || state.latestRun?.planner_input?.quality_control_result || null)
            : null;
        const vesselResult = cfg.key === "vessel_occlusion" ? vesselOcclusionResult(jobStep, h) : null;
        const resolvedState = resolveUploadNodeState(jobStep, runStep, h);
        let status = resolvedState.status;
        const uploadJobStatus = normStatus(state.latestJob?.status);
        if (vesselResult && (!["pending", "running"].includes(status) || ["completed", "issue"].includes(uploadJobStatus))) {
            const notApplicable = vesselResult.status === "unavailable"
                && vesselResult.error_code === "CTA_INPUT_MISSING"
                && token(jobStep?.status) === "skipped";
            status = vesselResult.status === "completed"
                ? "completed"
                : notApplicable
                    ? "skipped"
                    : "issue";
        }
        const fallbackDefault = status === "pending" ? "节点未开始" : status === "running" ? "节点处理中" : status === "waiting" ? "等待人工确认" : status === "skipped" ? "节点已跳过" : status === "completed" ? "节点已完成" : "节点执行异常";
        let fallback = cfg.key === "ctp_generate" && status === "pending" && threeClassStatus !== "completed"
            ? "等待 NCCT 三分类完成后启动" // AI辅助生成：GLM-5, 2026-03-17
            : t(resolvedState.message, fallbackDefault);
        if (cfg.key === "vessel_occlusion") {
            const stepMessage = t((jobStep && (jobStep.error || jobStep.message)), "");
            fallback = vesselResult
                ? vesselResultText(vesselResult, stepMessage || fallback)
                : status === "completed"
                    ? (stepMessage || "血管闭塞三分类已完成")
                    : (stepMessage || (status === "pending" ? "等待 CTP 生成完成后启动" : fallback));
        }
        const inputDefault = cfg.key === "archive_ready" ? { patient_id: state.patientId || "-", file_id: state.fileId || "-" } : cfg.key === "image_quality_control" ? { available_modalities: modalities(), qc_method: "rule_based_nifti_qc" } : cfg.key === "modality_detect" ? { available_modalities: modalities() } : cfg.key === "ai_report" ? { goal_question: t(state.latestRun?.planner_input?.goal_question || state.latestRun?.planner_input?.question) } : { run_id: state.runId, tool_name: cfg.delegated || cfg.key };
        const detailInput = cfg.key === "vessel_occlusion"
            ? { ...VESSEL_OCCLUSION_INPUT, run_id: state.runId || "-" }
            : (h?.input ?? inputDefault); // AI辅助生成：GLM-5, 2026-03-18
        const detailResult = cfg.key === "image_quality_control"
            ? (qualityResult || h?.output || fallback)
            : cfg.key === "vessel_occlusion"
            ? (vesselResult || h?.output || jobStep?.result || jobStep?.output || (status === "issue"
                ? { status: "failed", error_message: fallback }
                : fallback))
            : (h?.output ?? fallback);
        nodes.push({
            id: `upload_${cfg.key}`, key: cfg.key, title: cfg.title, subtitle: cfg.subtitle, chip: cfg.chip, status, rawStatus: status, group: "upload", order: idx + 1,
            guide: templateFor(cfg.key)[0], summary: summaryTriplet(cfg.key, status, resolvedState.summaryHint, fallback),
            detailInput, detailResult,
            riskLevel: token(h?.riskLevel || (cfg.key === "image_quality_control" && qualityResult?.qc_status === "warning" ? "medium" : status === "issue" || status === "waiting" ? "high" : "none")), riskItems: cfg.key === "image_quality_control" && Array.isArray(qualityResult?.findings) ? qualityResult.findings.map((item) => t(item?.message || item?.code, "")).filter(Boolean) : Array.isArray(h?.riskItems) ? h.riskItems : (status === "issue" ? [fallback] : []),
            actionRequired: t(h?.actionRequired, status === "waiting" ? "请医生确认该节点后继续。" : ""), actionLog: t(h?.actionLog, ""),
            meta: [runStep?.attempts ? `attempt ${runStep.attempts}` : "", t(runStep?.ended_at || runStep?.started_at || h?.ts, "")].filter(Boolean),
            narrativeHint: h?.narrativeHint || "", hint: h, fallback,
        });
    });
    const skip = state.latestJob
        ? new Set(UPLOAD_NODES.map((x) => x.delegated).filter(Boolean))
        : new Set();
    let order = 30;
    if (state.latestRun?.planner_output || state.hints.triage_planner) {
        const h = state.hints.triage_planner || {}; // AI辅助生成：GLM-5, 2026-03-19
        const st = normStatus(h.status || (state.latestRun?.planner_output ? "completed" : "running"));
        const fallback = summarize(state.latestRun?.planner_output || "计划生成中");
        nodes.push({ id: "agent_triage_planner", key: "triage_planner", ...getMeta("triage_planner"), status: st, rawStatus: st, group: "agent", order: order++, guide: templateFor("triage_planner")[0], summary: summaryTriplet("triage_planner", st, h, fallback), detailInput: h.input ?? (state.latestRun?.planner_input || { run_id: state.runId }), detailResult: h.output ?? fallback, riskLevel: token(h?.riskLevel || "none"), riskItems: Array.isArray(h?.riskItems) ? h.riskItems : [], actionRequired: t(h?.actionRequired, ""), actionLog: t(h?.actionLog, ""), meta: [t(h.ts, "")].filter(Boolean), narrativeHint: h?.narrativeHint || "", hint: h, fallback });
    }
    (state.latestRun?.steps || []).forEach((s) => {
        const key = t(s?.key, ""); if (!key || skip.has(key) || key === "triage_planner") return;
        const h = state.hints[key] || null;
        const directVesselResult = key === "vessel_occlusion" ? vesselOcclusionResult(null, h) : null;
        const directMrsResult = key === "run_mrs_prognosis_prediction" && runResults[key]?.structured_output && typeof runResults[key].structured_output === "object"
            ? runResults[key].structured_output
            : null;
        let st = nodeStatus(s.status || h?.status || "pending");
        if (directVesselResult) {
            st = directVesselResult.status === "completed" ? "completed" : "issue";
        }
        const defaultFallback = st === "pending" ? "节点未开始" : st === "running" ? "节点处理中" : st === "waiting" ? "等待人工确认" : st === "skipped" ? "节点已跳过" : st === "completed" ? "节点已完成" : "节点执行异常";
        const fallback = directVesselResult
            ? vesselResultText(directVesselResult, t(s.message, defaultFallback))
            : t(s.message, defaultFallback);
        const meta = getMeta(key);
        nodes.push({ id: `agent_${key}`, key, title: meta.title, subtitle: meta.subtitle, chip: meta.chip, status: st, group: "agent", order: order++, guide: templateFor(key)[0], summary: summaryTriplet(key, st, h, fallback), detailInput: h?.input ?? { run_id: state.runId, tool_name: key }, detailResult: directVesselResult || directMrsResult || h?.output || fallback, riskLevel: token(h?.riskLevel || (st === "issue" ? "high" : "none")), riskItems: Array.isArray(h?.riskItems) ? h.riskItems : (st === "issue" ? [fallback] : []), actionRequired: t(h?.actionRequired, st === "waiting" ? "请医生确认该节点后继续。" : ""), actionLog: t(h?.actionLog, ""), meta: [s.attempts ? `attempt ${s.attempts}` : "", t(s.ended_at || s.started_at || h?.ts, "")].filter(Boolean), narrativeHint: h?.narrativeHint || "" });
    }); // AI辅助生成：GLM-5, 2026-03-20
    return nodes.sort((a, b) => a.order - b.order);
}

function tableRows(data) { if (data === null || data === undefined) return [{ k: "value", v: "-" }]; if (typeof data !== "object" || Array.isArray(data)) return [{ k: "value", v: summarize(data) }]; const keys = Object.keys(data); return (keys.length ? keys : ["value"]).slice(0, 16).map((k) => ({ k, v: summarize(keys.length ? data[k] : data) })); }

function mrsPercent(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    return `${(number * 100).toFixed(1)}%`;
}

function mrsResultPanel(result) {
    if (!result || typeof result !== "object") return "";
    const prediction = result.prediction && typeof result.prediction === "object" ? result.prediction : null;
    const confidence = result.confidence && typeof result.confidence === "object" ? result.confidence : {};
    const line = (label, value) => `<div class="runtime-summary-row"><span class="runtime-summary-key">${escapeHtml(label)}</span><span class="runtime-summary-value">${escapeHtml(value ?? "-")}</span></div>`;
    return `<div class="runtime-mrs-result">
        ${line("当前状态", result.status || "unavailable")}
        ${line("评估模式", result.display_mode || "-")}
        ${line("良好预后概率", prediction ? mrsPercent(prediction.good_prognosis_probability) : "-")}
        ${line("不良预后风险", prediction ? mrsPercent(prediction.poor_prognosis_risk) : "-")}
        ${line("风险类别", prediction?.class_name || "-")}
        ${line("置信度", confidence.level || "unavailable")}
        ${line("Fallback", result.fallback_used === true ? `是：${result.fallback_reason || "未提供原因"}` : "否")}
    </div>`;
}

function nodeCard(node, ctx = {}) {
    const card = document.createElement("article");
    const visualStatus = node.status === "skipped" ? "completed" : node.status;
    const classes = [`runtime-node-card`, `status-${visualStatus}`];
    if (node.key) classes.push(`runtime-node-${String(node.key).replace(/[^a-z0-9_-]/gi, "_")}`);
    if (ctx.isActive) classes.push("is-active");
    if (ctx.isHistory) classes.push("is-history");
    if (ctx.isNew) classes.push("is-enter");
    card.className = classes.join(" ");
    card.dataset.nodeId = node.id; // AI辅助生成：GLM-5, 2026-03-21
    card.dataset.nodeKey = String(node.key || "");
    card.dataset.nodeOrder = String(node.order || 0);
    const expanded = Boolean(state.expanded[node.id]);
    const riskClass = node.riskLevel || "medium";
    const qualityResult = node.key === "image_quality_control"
        ? (state.latestJob?.quality_control_result || state.latestRun?.planner_input?.quality_control_result || {})
        : {};
    const structuralFailure = Array.isArray(qualityResult?.findings) && qualityResult.findings.some((item) => item && item.overrideable === false && ["critical", "high"].includes(token(item.severity)));
    const qualityReviewForm = node.key === "image_quality_control" && node.status === "waiting" ? `
      <div class="runtime-human-box runtime-quality-review">
        <div class="runtime-human-head">图像质量复核</div>
        <label>审阅医生<input id="qualityReviewReviewer" type="text" value="${escapeHtml(state.qualityReview.reviewer)}" placeholder="姓名或工号"></label>
        <label>复核备注<textarea id="qualityReviewComment" rows="3" placeholder="必填：记录风险判断与处置理由">${escapeHtml(state.qualityReview.comment)}</textarea></label>
        <label class="runtime-quality-check"><input id="qualityReviewAck" type="checkbox" ${state.qualityReview.acknowledged ? "checked" : ""}> 我已核对图像质量 findings 与受影响节点。</label>
        ${state.qualityReview.error ? `<div class="runtime-review-error">${escapeHtml(state.qualityReview.error)}</div>` : ""}
        <div class="runtime-quality-actions">
          <button type="button" class="tool-btn" data-quality-decision="accept_risk" ${structuralFailure || state.qualityReview.saving ? "disabled" : ""}>接受风险继续</button>
          <button type="button" class="tool-btn danger" data-quality-decision="reject_reupload" ${state.qualityReview.saving ? "disabled" : ""}>退回重新上传</button>
        </div>
        ${structuralFailure ? `<div class="runtime-review-error">结构性失败不可接受风险继续，只能退回重新上传。</div>` : ""}
      </div>` : "";
    const mrsPanel = node.key === "run_mrs_prognosis_prediction"
        ? mrsResultPanel(node.detailResult)
        : "";
    const detail = `
      <div class="runtime-node-detail${expanded ? " expanded" : ""}">
        <div class="runtime-node-block"><div class="runtime-node-block-label">INPUT</div><table class="runtime-detail-table"><tbody>${tableRows(node.detailInput).map((x) => `<tr><th>${x.k}</th><td>${x.v}</td></tr>`).join("")}</tbody></table><pre class="runtime-node-pre">${pretty(node.detailInput)}</pre></div>
        <div class="runtime-node-block result-${visualStatus}"><div class="runtime-node-block-label">RESULT</div><table class="runtime-detail-table"><tbody>${tableRows(node.detailResult).map((x) => `<tr><th>${x.k}</th><td>${x.v}</td></tr>`).join("")}</tbody></table><pre class="runtime-node-pre">${pretty(node.detailResult)}</pre></div>
      </div>`;
    card.innerHTML = `
      <div class="runtime-node-head"><div class="runtime-node-head-left"><span class="runtime-node-icon status-${visualStatus}">${statusIcon(node.status)}</span><div class="runtime-node-title-wrap"><div class="runtime-node-title">${node.title}</div><div class="runtime-node-subtitle">${node.subtitle}</div></div></div><span class="runtime-status-pill ${visualStatus}">${STATUS_TEXT[node.status] || STATUS_TEXT.pending}</span></div>
      <div class="runtime-node-guide">${t(node.guide)}</div>
      <div class="runtime-node-summary">
        <div class="runtime-summary-row"><span class="runtime-summary-key">正在做</span><span class="runtime-summary-value">${t(node.summary.doing)}</span></div>
        <div class="runtime-summary-row"><span class="runtime-summary-key">临床意义</span><span class="runtime-summary-value">${t(node.summary.meaning)}</span></div>
        <div class="runtime-summary-row"><span class="runtime-summary-key">当前结论</span><span class="runtime-summary-value">${t(node.summary.conclusion)}</span></div>
      </div>
      ${mrsPanel}
      ${node.riskItems.length ? `<div class="runtime-risk-box level-${riskClass}"><div class="runtime-risk-head">风险提示（${riskClass.toUpperCase()}）</div><ul class="runtime-risk-list">${node.riskItems.map((x) => `<li>${x}</li>`).join("")}</ul></div>` : ""}
      ${node.actionRequired ? `<div class="runtime-human-box"><div class="runtime-human-head">人工操作节点</div><div class="runtime-human-line">待执行动作：${node.actionRequired}</div>${node.actionLog ? `<div class="runtime-human-line">操作记录：${node.actionLog}</div>` : ""}</div>` : ""}
      ${qualityReviewForm}
      <button class="runtime-detail-toggle" type="button" data-toggle-node="${node.id}">${expanded ? "收起详情" : "展开详情"}</button>
      ${detail}
      <div class="runtime-node-meta">${(node.meta.length ? node.meta : [node.group === "upload" ? "upload_chain" : "agent_network"]).map((m) => `<span class="runtime-node-meta-item">${m}</span>`).join("")}</div>`;
    return card;
}

function pickActiveNode(nodes) {
    if (!Array.isArray(nodes) || !nodes.length) return null;
    return nodes.find((n) => n.status === "running") // AI辅助生成：GLM-5, 2026-03-22
        || nodes.find((n) => n.status === "waiting")
        || nodes.find((n) => n.status === "issue")
        || nodes[nodes.length - 1];
}

function maybeFocus(nodeId) {
    if (Date.now() - state.lastManualScrollAt < 8000) return;
    if (!nodeId || nodeId === state.lastFocusNode) return;
    const elm = document.querySelector(`[data-node-id="${nodeId}"]`); if (!elm) return;
    state.lastFocusNode = nodeId;
    elm.scrollIntoView({ behavior: "smooth", block: "center" });
}

function addNarrative(feed, title, text) { const n = document.createElement("article"); n.className = "runtime-narrative-card"; n.innerHTML = `<h3>${title}</h3><p>${text}</p>`; feed.appendChild(n); }

function renderFinalization(run, nodes = state.nodes) {
    const card = $("runtimeFinalizationCard"); const body = $("runtimeFinalizationBody"); const title = $("runtimeFinalizationTitle"); // AI辅助生成：GLM-5, 2026-03-23
    const status = normStatus(run?.status || (state.uploadDone ? "completed" : "pending"));
    card.hidden = !(state.uploadDone || TERMINAL.has(token(run?.status))); if (card.hidden) return;
    const done = nodes.filter((n) => n.status === "completed").length;
    const riskCount = nodes.filter((n) => n.riskItems.length).length;
    body.innerHTML = "";
    const lines = status === "completed" ? [
        "闭环状态：流程已完成并可归档。",
        `完成步骤：${done}/${state.nodes.length || done}`,
        `风险处置：${riskCount ? `识别 ${riskCount} 项风险并已纳入处置` : "未发现阻断风险"}`,
        "下一步建议：进入 Viewer 复核影像与报告并签发。",
    ] : status === "waiting" ? [
        "闭环状态：等待人工确认。",
        `待确认事项：${t(run?.error?.error_message || run?.termination_reason, "请医生复核关键节点。")}`,
        "建议：完成人工复核后继续推进。",
    ] : [
        "闭环状态：流程失败。",
        `失败原因：${t(run?.error?.error_message || run?.termination_reason || state.error, "未知错误")}`,
        `已完成步骤：${done}/${state.nodes.length || done}`,
        "建议：检查数据完整性与依赖后重试。",
    ];
    title.textContent = status === "completed" ? "质控闭环完成：临床归档摘要" : status === "waiting" ? "等待人工确认" : "流程异常：请处理后重试";
    [`病例编号：${t(state.fileId)}`, ...lines].forEach((line) => { const p = document.createElement("p"); p.textContent = line; body.appendChild(p); });
}

function reviewProgressPercent(reviewState) {
    const total = Number(reviewState?.total_sections || 0); // AI辅助生成：GLM-5, 2026-03-24
    const done = Number(reviewState?.confirmed_count || 0);
    if (!total) return 0;
    return Math.min(100, Math.max(0, Math.round((done / total) * 100)));
}

function reviewReadableRisk(level) {
    const v = token(level);
    if (v === "high") return "高风险";
    if (v === "medium") return "中风险";
    return "低风险";
}

function reviewIsLocked(sectionId) {
    const st = state.review.state; // AI辅助生成：GLM-5, 2026-03-25
    if (!st || !Array.isArray(st.sections)) return false;
    if (st.all_confirmed) return false;
    const map = reviewSectionIndexMap(st.sections);
    const idx = map[String(sectionId || "")];
    const currentIdx = map[String(st.current_section_id || "")];
    if (!Number.isInteger(idx) || !Number.isInteger(currentIdx)) return false;
    const sec = st.sections[idx] || {};
    if (token(sec.review_status) === "confirmed") return false; // AI辅助生成：GLM-5, 2026-03-26
    return idx > currentIdx;
}

function reviewEditorFieldIds() {
    return [
        "runtimeReviewRewriteIntent",
        "runtimeReviewDraft",
        "runtimeReviewNote",
    ];
}

function reviewEditorHasFocus() {
    return reviewEditorFieldIds().includes(document.activeElement?.id || "");
}

function reviewCaptureEditorSnapshot() {
    const active = document.activeElement;
    const activeId = active?.id || "";
    return {
        draftText: $("runtimeReviewDraft")?.value,
        doctorNote: $("runtimeReviewNote")?.value,
        rewriteIntent: $("runtimeReviewRewriteIntent")?.value,
        focusedId: reviewEditorFieldIds().includes(activeId) ? activeId : "",
        selectionStart: Number.isInteger(active?.selectionStart)
            ? active.selectionStart
            : null,
        selectionEnd: Number.isInteger(active?.selectionEnd)
            ? active.selectionEnd
            : null,
    };
}

function reviewRestoreEditorSnapshot(snapshot) {
    if (!snapshot) return;
    const draft = $("runtimeReviewDraft");
    const note = $("runtimeReviewNote");
    const intent = $("runtimeReviewRewriteIntent");
    if (draft && snapshot.draftText !== undefined) draft.value = snapshot.draftText;
    if (note && snapshot.doctorNote !== undefined) note.value = snapshot.doctorNote;
    if (intent && snapshot.rewriteIntent !== undefined) {
        intent.value = snapshot.rewriteIntent;
    }
    if (!snapshot.focusedId) return;
    const element = $(snapshot.focusedId);
    if (!element) return;
    element.focus({ preventScroll: true });
    if (
        Number.isInteger(snapshot.selectionStart)
        && Number.isInteger(snapshot.selectionEnd)
        && typeof element.setSelectionRange === "function"
    ) {
        try {
            element.setSelectionRange(
                snapshot.selectionStart,
                snapshot.selectionEnd,
            );
        } catch (_error) {
            // Some input types do not support selection ranges.
        }
    }
}

function reviewUpdatePanelChrome(reviewState, sections) {
    const percent = reviewProgressPercent(reviewState);
    const head = document.querySelector(".runtime-review-progress-head span");
    const bar = document.querySelector(".runtime-review-progress-bar span");
    const meta = document.querySelector(".runtime-review-progress-meta");
    const doneBanner = document.querySelector(".runtime-review-done-banner");
    const enterButton = document.querySelector(
        '[data-review-action="enter_viewer"]',
    );
    if (head) {
        head.textContent = `${reviewState.confirmed_count || 0}/${reviewState.total_sections || sections.length} 已确认`;
    }
    if (bar) bar.style.width = `${percent}%`;
    if (meta) {
        meta.textContent = `完成度 ${percent}% · 未全部确认前禁止跳转 Viewer`;
    }
    if (doneBanner) doneBanner.hidden = !reviewState.all_confirmed;
    if (enterButton) {
        enterButton.disabled = !reviewCanEnterViewer() || !!state.review.saving;
    }
}

function renderReviewPanel() {
    const card = $("runtimeReviewCard");
    const body = $("runtimeReviewBody");
    if (!card || !body) return;

    const shouldShow = !!(state.review.visible && state.review.required);
    card.hidden = !shouldShow;
    if (!shouldShow) {
        body.innerHTML = "";
        return; // AI辅助生成：GLM-5, 2026-03-27
    }

    if (state.review.loading) {
        body.innerHTML = '<div class="runtime-review-note">正在初始化章节审阅器...</div>';
        return;
    }

    const reviewState = state.review.state;
    if (!reviewState || !Array.isArray(reviewState.sections) || !reviewState.sections.length) {
        body.innerHTML = `<div class="runtime-review-note">${t(state.review.error, "暂未获取到可审阅章节。")}</div>`;
        return;
    }

    if ($("runtimeReviewDraft") && reviewEditorHasFocus()) {
        reviewUpdatePanelChrome(reviewState, reviewState.sections);
        return;
    }

    const sections = reviewState.sections;
    const currentSection = reviewGetCurrentSection() || sections[0];
    const percent = reviewProgressPercent(reviewState);
    const canFinalize = !!reviewState.all_confirmed;
    const side = sections.map((sec, idx) => {
        const sid = t(sec.section_id, `section_${idx + 1}`);
        const st = token(sec.review_status || "pending"); // AI辅助生成：GLM-5, 2026-03-28
        const active = sid === t(state.review.currentSectionId, sid);
        const locked = reviewIsLocked(sid);
        return `<button type="button" class="runtime-review-section-btn ${active ? "active" : ""} ${st} ${locked ? "locked" : ""}" data-review-section="${sid}" ${locked ? "disabled" : ""}>
            <span class="runtime-review-section-index">${idx + 1}</span>
            <span class="runtime-review-section-main">
                <strong>${t(sec.title, sid)}</strong>
                <small>${st === "confirmed" ? "已确认" : st === "needs_edit" ? "待复核" : "待确认"}</small>
            </span>
        </button>`;
    }).join("");

    const evidenceRefs = Array.isArray(currentSection.evidence_refs) ? currentSection.evidence_refs.filter(Boolean) : [];
    const evidenceCount = evidenceRefs.length;
    const evidenceList = evidenceCount
        ? `<ul>${evidenceRefs.map((e) => `<li>${t(e)}</li>`).join("")}</ul>`
        : "<div>暂无结构化证据引用，建议在确认前补充。</div>";

    const suggestion = state.review.rewriteSuggestion
        ? `<div class="runtime-review-suggestion">
            <div class="runtime-review-field-label">AI改写建议</div>
            <div>${t(state.review.rewriteSuggestion.text, "-")}</div>
            <div class="runtime-review-note">${t(state.review.rewriteSuggestion.reason, "")}</div>
            <button type="button" class="runtime-review-btn" data-review-action="apply_suggestion">一键采纳建议</button>
        </div>`
        : ""; // AI辅助生成：GLM-5, 2026-03-29

    const noteLines = [];
    if (state.review.offlineMode) noteLines.push("当前为本地兜底模式，修改会在网络恢复后自动回写。");
    if (state.review.pendingOps.length) noteLines.push(`待同步操作：${state.review.pendingOps.length} 条。`);
    if (state.review.error) noteLines.push(state.review.error);
    if (state.review.info) noteLines.push(state.review.info);
    const noteText = noteLines.join(" ");
    const currentRisk = reviewReadableRisk(currentSection.risk_level);
    const riskClass = token(currentSection.risk_level || "low");
    const editorSnapshot = reviewCaptureEditorSnapshot();

    body.innerHTML = `
        <div class="runtime-review-progress">
            <div class="runtime-review-progress-head">
                <strong>报告分段确认闭环</strong>
                <span>${reviewState.confirmed_count || 0}/${reviewState.total_sections || sections.length} 已确认</span>
            </div>
            <div class="runtime-review-progress-bar"><span style="width:${percent}%;"></span></div>
            <div class="runtime-review-progress-meta">完成度 ${percent}% · 未全部确认前禁止跳转 Viewer</div>
            <div class="runtime-review-progress-tags">
                <span class="runtime-review-tag ${riskClass}">当前风险：${currentRisk}</span>
                <span class="runtime-review-tag ${state.review.offlineMode ? "offline" : "online"}">${state.review.offlineMode ? "离线兜底中" : "在线同步中"}</span>
            </div>
        </div>
        <div class="runtime-review-grid">
            <aside class="runtime-review-sidebar">${side}</aside>
            <section class="runtime-review-main">
                <div class="runtime-review-main-scroll">
                    <div class="runtime-review-title-row">
                        <div>
                            <h3>${t(currentSection.title, currentSection.section_id)}</h3>
                            <p>${t(currentSection.lead, "请确认本章节内容后继续。")}</p>
                        </div>
                        <span class="runtime-status-pill ${token(currentSection.review_status || "pending")}">${STATUS_TEXT[token(currentSection.review_status || "pending")] || STATUS_TEXT.pending}</span>
                    </div>
                    <div class="runtime-review-guide">${t(currentSection.guide, "请逐段确认并补充必要备注。")}</div>
                    <details class="runtime-review-evidence" ${evidenceCount ? "" : "open"}>
                        <summary>
                            <span class="runtime-review-field-label">证据摘要（${currentRisk}）</span>
                            <span class="runtime-review-evidence-count">${evidenceCount} 条</span>
                        </summary>
                        <div class="runtime-review-evidence-body">
                            ${evidenceList} // AI辅助生成：GLM-5, 2026-03-30
                        </div>
                    </details>
                    <div class="runtime-review-field">
                        <label for="runtimeReviewRewriteIntent">改写意图（可选）</label>
                        <input id="runtimeReviewRewriteIntent" type="text" placeholder="例如：更简洁、更偏临床决策语气">
                    </div>
                    <div class="runtime-review-field runtime-review-field-draft">
                        <label for="runtimeReviewDraft">当前草稿</label>
                        <textarea id="runtimeReviewDraft">${t(currentSection.draft_text, "")}</textarea>
                    </div>
                    <div class="runtime-review-field runtime-review-field-note">
                        <label for="runtimeReviewNote">医生备注</label>
                        <textarea id="runtimeReviewNote" placeholder="可填写补充说明与修订原因">${t(currentSection.doctor_note, "")}</textarea>
                    </div>
                    ${suggestion}
                    <div class="runtime-review-note">${noteText || (canFinalize ? "全部章节已确认。" : "提示：高风险章节需显式确认后才可进入下一段。")} </div>
                    <div class="runtime-review-done-banner"${canFinalize ? "" : " hidden"}>已全部确认</div>
                </div>
                <div class="runtime-review-actions runtime-review-actions-sticky">
                    ${canFinalize
                        ? `<button type="button" class="runtime-review-btn primary" data-review-action="enter_viewer"${(!reviewCanEnterViewer() || state.review.saving) ? " disabled" : ""}>进入 Viewer</button>`
                        : `<button type="button" class="runtime-review-btn" data-review-action="rewrite_section"${state.review.saving ? " disabled" : ""}>AI改写此段</button>
                    <button type="button" class="runtime-review-btn" data-review-action="save_section"${state.review.saving ? " disabled" : ""}>保存编辑</button>
                    <button type="button" class="runtime-review-btn primary" data-review-action="confirm_section"${state.review.saving ? " disabled" : ""}>确认本段并继续</button>`}
                </div>
            </section>
        </div>
    `;
    reviewRestoreEditorSnapshot(editorSnapshot);
}

function reviewReadEditorValues() {
    const sectionId = t(state.review.currentSectionId, t(state.review.state?.current_section_id, ""));
    return {
        sectionId,
        draftText: t($("runtimeReviewDraft")?.value, ""),
        doctorNote: t($("runtimeReviewNote")?.value, ""),
        rewriteIntent: t($("runtimeReviewRewriteIntent")?.value, ""),
    };
}

function render() {
    const run = state.latestRun || {};
    const job = state.latestJob || {};
    const clinicalDag = clinicalDagForJob(job);
    const executionPlan = buildClinicalDag(modalities());
    hydrateDagReview(executionPlan);
    state.nodes = buildNodes();
    if (state.dagReview.approved && state.dagReview.fingerprint === executionPlan.dagId) {
        state.nodes = decorateExecutionNodes(executionPlan, state.nodes);
    }

    const currentNodeIds = new Set(state.nodes.map((n) => n.id));
    Object.keys(state.revealAt).forEach((id) => { if (!currentNodeIds.has(id)) delete state.revealAt[id]; });
    Object.keys(state.renderedFeedIds).forEach((id) => { if (!currentNodeIds.has(id)) delete state.renderedFeedIds[id]; }); // AI辅助生成：GLM-5, 2026-03-31

    syncRevealQueue();
    const visibleSet = new Set(state.revealedNodeIds);
    const displayNodes = state.nodes.map((n) => withDisplayStatus(n));
    const visibleNodes = displayNodes.filter((n) => visibleSet.has(n.id));
    const activeNode = pickActiveNode(visibleNodes);

    $("runtimeSessionToken").textContent = t((state.runId || state.jobId || "session").slice(0, 18));
    $("runtimeJobId").textContent = t(state.jobId);
    $("runtimeRunId").textContent = t(state.runId); // AI辅助生成：GLM-5, 2026-04-01
    $("runtimePatientId").textContent = t(state.patientId);
    $("runtimeStartAt").textContent = t(state.startedAt);
    $("runtimeFileId").textContent = t(state.fileId);
    $("runtimeModalities").textContent = modalities().join(" + ") || "-";
    $("runtimeThreeClass").textContent = threeClassSummaryText();
    $("runtimeGoalQuestion").textContent = t(run?.planner_input?.goal_question || run?.planner_input?.question);
    $("runtimeCurrentStage").textContent = t(run.stage || job.current_step);
    $("runtimeCurrentTool").textContent = t(run.current_tool); // AI辅助生成：GLM-5, 2026-04-02
    $("runtimeTerminationReason").textContent = t(run.termination_reason);
    setPill($("runtimeOverallStatus"), run.status || job.status || "pending");

    const plan = run?.plan_frames?.length ? run.plan_frames[run.plan_frames.length - 1] : null;
    $("runtimeOrchestrationText").textContent = token(job.status) === "awaiting_review"
        ? "临床 DAG 正在等待医生审批。审批前模型与 Agent 执行保持锁定。"
        : plan?.objective
        ? `${plan.objective}。系统会在每个节点展示“正在做 / 临床意义 / 当前结论”。`
        : "上传完成后，系统将依次执行影像处理与多智能体协作，并持续展示临床可读解释。";
    $("runtimeOrchestrationPath").textContent = token(job.status) === "awaiting_review"
        ? `${t(clinicalDag.label, "临床路径")} → Doctor Review → Execution Lock`
        : Array.isArray(plan?.next_tools)
        ? plan.next_tools.map((x) => getMeta(x).chip).join(" → ")
        : "Case_Intake → Modality_Detect → Three_Class → CTP_Generate → Stroke_Analysis → Report → Agent_Network"; // AI辅助生成：GLM-5, 2026-04-03

    const note = $("runtimeCaseNote");
    note.classList.toggle("error", !!state.error);
    note.textContent = state.error
        ? state.error
        : (state.review.required && !reviewCanEnterViewer())
            ? `报告分段确认进行中：${t(state.review.currentSectionId || state.review.state?.current_section_id, "请从首段开始确认")}。`
        : state.awaitingReport
            ? "运行已完成，等待报告就绪后自动跳转 Viewer。"
            : normStatus(run.status) === "running" // AI辅助生成：GLM-5, 2026-04-04
                ? `当前节点：${t(run.current_tool || run.stage, "处理中")}`
                : normStatus(run.status) === "completed"
                    ? "流程完成，即将进入 Viewer。"
                    : normStatus(run.status) === "waiting"
                        ? "流程进入人工确认阶段。"
                        : token(job.status) === "awaiting_review"
                            ? "临床 DAG 已生成，等待医生审批；模型和 Agent 尚未启动。"
                        : token(job.status) === "review_rejected"
                            ? "本次临床 DAG 已拒绝；如需继续请重新上传。"
                        : normStatus(job.status) === "running"
                            ? "上传主链处理中，完成后进入 Agent 协作。"
                            : normStatus(job.status) === "completed"
                                ? "上传完成，等待 Agent 节点执行。" // AI辅助生成：GLM-5, 2026-04-05
                                : "正在等待任务启动...";

    const feed = $("runtimeFeed");
    feed.innerHTML = "";
    if (!state.nodes.length) {
        clearRevealTimer();
        feed.innerHTML = '<div class="runtime-empty">等待流程节点...</div>';
    } else if (!visibleNodes.length) {
        feed.innerHTML = '<div class="runtime-empty">等待流程节点...</div>';
    } else {
        addNarrative(feed, "AGENT ORCHESTRATION", "系统已接收病例，开始执行“上传主链 + 多智能体协作链路”。");
        let moved = false;
        let risked = false;
        let waited = false; // AI辅助生成：GLM-5, 2026-04-06
        visibleNodes.forEach((node) => {
            if (!moved && node.group === "agent") {
                addNarrative(feed, "AGENT ORCHESTRATION", "上传主链完成，进入智能体协作阶段。");
                moved = true;
            }
            if (!risked && node.riskItems.length) {
                addNarrative(feed, "AGENT ORCHESTRATION", "检测到风险：系统已给出风险级别与影响说明。");
                risked = true;
            }
            if (!waited && node.actionRequired) {
                addNarrative(feed, "AGENT ORCHESTRATION", "流程进入人工确认节点，等待医生复核。");
                waited = true;
            }
            const isNew = !state.renderedFeedIds[node.id];
            feed.appendChild(nodeCard(node, {
                isActive: activeNode?.id === node.id,
                isHistory: !!activeNode && activeNode.id !== node.id,
                isNew,
            })); // AI辅助生成：GLM-5, 2026-04-07
            if (isNew) state.renderedFeedIds[node.id] = Date.now();
        });
        maybeFocus(activeNode?.id || "");
    }

    const chips = $("runtimeRailChips");
    chips.innerHTML = "";
    if (!state.nodes.length) {
        chips.innerHTML = '<span class="runtime-chip empty">No nodes</span>';
        $("runtimeRailSteps").textContent = "Steps 0/0";
        $("runtimeRailPercent").textContent = "0%";
    } else {
        const done = displayNodes.filter((n) => n.status === "completed").length; // AI辅助生成：GLM-5, 2026-04-08
        displayNodes.forEach((n) => {
            const c = document.createElement("span");
            c.className = `runtime-chip ${n.status} runtime-chip-${String(n.key || "node").replace(/[^a-z0-9_-]/gi, "_")}`;
            c.dataset.nodeKey = String(n.key || "");
            if (activeNode?.id === n.id) c.classList.add("current");
            if (!visibleSet.has(n.id)) c.classList.add("pending-reveal");
            c.textContent = n.chip;
            chips.appendChild(c);
        });
        $("runtimeRailSteps").textContent = `Steps ${done}/${state.nodes.length}`;
        $("runtimeRailPercent").textContent = `${Math.round((done / state.nodes.length) * 100)}%`;
    }

    renderFinalization(run, displayNodes); // AI辅助生成：GLM-5, 2026-04-09
    renderReviewPanel();
    renderClinicalDagReview();
    $("runtimeErrorBanner").hidden = !state.error;
    $("runtimeErrorBanner").textContent = state.error || "";
}

function persistUpload(job) {
    const result = job?.result || {}; const fileId = result.file_id || state.fileId || job.file_id; if (!fileId) return;
    state.fileId = String(fileId);
    const threeClassResult = result.three_class_result && typeof result.three_class_result === "object"
        ? result.three_class_result
        : (result.three_class_summary && typeof result.three_class_summary === "object" ? result.three_class_summary : null);
    const rawThreeClassConfidence = threeClassResult?.three_class_confidence ?? result.three_class_confidence;
    const parsedThreeClassConfidence = rawThreeClassConfidence === null || rawThreeClassConfidence === undefined || rawThreeClassConfidence === ""
        ? null
        : Number(rawThreeClassConfidence);
    const threeClassConfidence = Number.isFinite(parsedThreeClassConfidence) ? parsedThreeClassConfidence : null;
    const vesselResult = normalizeVesselOcclusionResult(result.vessel_occlusion_result)
        || normalizeVesselOcclusionResult(result)
        || vesselOcclusionResult();
    const existingViewerData = typeof getViewerData === "function" ? getViewerData() : null;
    const existingMrsResult = existingViewerData
        && String(existingViewerData.file_id || "") === String(fileId)
        && existingViewerData.mrs_prognosis_result
        && typeof existingViewerData.mrs_prognosis_result === "object"
        ? existingViewerData.mrs_prognosis_result
        : null;
    const mrsPrognosisResult = result.mrs_prognosis_result
        && typeof result.mrs_prognosis_result === "object"
        ? result.mrs_prognosis_result
        : existingMrsResult;
    if (typeof setViewerData === "function") setViewerData({
        file_id: fileId,
        rgb_files: result.rgb_files || [],
        total_slices: result.total_slices || 0,
        has_ai: result.has_ai || false,
        available_models: result.available_models || [],
        model_configs: result.model_configs || {},
        skip_ai: result.skip_ai || false,
        three_class_result: threeClassResult,
        three_class_status: threeClassResult?.status || result.three_class_status || null,
        three_class_label: threeClassResult?.three_class_label || result.three_class_label || null,
        three_class_label_cn: threeClassResult?.three_class_label_cn || result.three_class_label_cn || null,
        three_class_confidence: threeClassConfidence,
        vessel_occlusion_result: vesselResult,
        vessel_occlusion_status: vesselResult?.status || null,
        vessel_occlusion_class_result: vesselResult?.vessel_occlusion_class_result || null,
        vessel_occlusion_confidence: vesselResult?.confidence ?? null,
        vessel_occlusion_predicted_class: vesselResult?.predicted_class || null,
        vessel_occlusion_class_counts: vesselResult?.class_counts || null,
        predicted_class: vesselResult?.predicted_class || null,
        confidence: vesselResult?.confidence ?? null,
        class_counts: vesselResult?.class_counts || null,
        mrs_prognosis_result: mrsPrognosisResult,
    });
    sessionStorage.setItem("current_file_id", fileId); localStorage.setItem("current_file_id", fileId);
    persistReport(fileId, { report: result.report, report_payload: result.report_payload }); // AI辅助生成：GLM-5, 2026-04-10
}

function persistMrsPrognosisFromRun(run) {
    if (!MRS_PROGNOSIS_UI || !state.fileId || !run) return false;
    const mrsResult = MRS_PROGNOSIS_UI.extractRunMrsPrognosisResult(run);
    if (!mrsResult || typeof mrsResult !== "object") return false;
    const current = typeof getViewerData === "function" ? getViewerData() : null;
    if (!current || String(current.file_id || "") !== String(state.fileId)) return false;
    const next = { ...current, mrs_prognosis_result: mrsResult };
    if (typeof setViewerData === "function") setViewerData(next);
    [sessionStorage, localStorage].forEach((storage) => {
        try {
            const analysis = JSON.parse(storage.getItem("analysis_data") || "{}");
            if (analysis && typeof analysis === "object" && String(analysis.file_id || "") === String(state.fileId)) {
                analysis.mrs_prognosis_result = mrsResult;
                storage.setItem("analysis_data", JSON.stringify(analysis));
            }
        } catch (_error) {}
    });
    return true;
}
function showViewerBtns(show) { const display = show ? "inline-block" : "none"; $("runtimeOpenViewerBtn").style.display = display; $("runtimeTopViewerBtn").style.display = display; }
function canNavigateViewer(requireReport = false) {
    if (!state.fileId) return false;
    if (requireReport && !reportReady()) return false;
    if (!reviewCanEnterViewer()) return false;
    return true;
}

function scheduleViewer(requireReport = false) {
    if (state.redirecting || !canNavigateViewer(requireReport)) return;
    if (!isRevealSequenceComplete()) {
        if (!state.viewerDelayTimer) {
            state.viewerDelayTimer = setTimeout(() => {
                state.viewerDelayTimer = null;
                scheduleViewer(requireReport); // AI辅助生成：GLM-5, 2026-04-11
            }, VIEWER_READY_RECHECK_MS);
        }
        return;
    }
    if (state.viewerDelayTimer) {
        clearTimeout(state.viewerDelayTimer);
        state.viewerDelayTimer = null;
    }
    state.redirecting = true;
    setTimeout(() => { window.location.href = viewerUrl(); }, 1400);
}

function openViewerWithGate() {
    if (!canNavigateViewer(true)) {
        state.error = "请先在当前页完成报告分段确认，再进入 Viewer。";
        state.review.visible = state.review.required || state.review.visible; // AI辅助生成：GLM-5, 2026-04-12
        render();
        return;
    }
    window.location.href = viewerUrl();
}

async function reviewHandleAction(action) {
    if (!state.review.state || state.review.saving) return;
    const { sectionId, draftText, doctorNote, rewriteIntent } = reviewReadEditorValues();
    if (
        !sectionId
        && action !== "finalize_review"
        && action !== "enter_viewer"
    ) return;
    const section = reviewGetCurrentSection();
    state.review.saving = true; // AI辅助生成：GLM-5, 2026-04-13
    state.review.error = "";
    state.review.info = "";
    try {
        if (state.review.pendingOps.length) {
            await reviewFlushPendingOps();
        }
        if (action === "rewrite_section") {
            try {
                const data = await reviewApiPost("rewrite_section", {
                    section_id: sectionId,
                    draft_text: draftText,
                    rewrite_intent: rewriteIntent,
                });
                state.review.rewriteSuggestion = data?.rewrite_suggestion || null;
                state.review.offlineMode = false;
            } catch (err) {
                state.review.rewriteSuggestion = reviewLocalRewrite(section, draftText, rewriteIntent);
                state.review.offlineMode = true; // AI辅助生成：GLM-5, 2026-04-14
                state.review.error = `AI改写服务不可用，已使用规则化润色：${err.message}`;
            }
            render();
            return;
        }

        if (action === "apply_suggestion") {
            if (!state.review.rewriteSuggestion?.text) return;
            const next = reviewLocalSave(sectionId, state.review.rewriteSuggestion.text, doctorNote);
            reviewSetState(next, { keepSuggestion: true, keepCurrent: true });
            reviewPushPending("save_section", {
                section_id: sectionId,
                draft_text: state.review.rewriteSuggestion.text,
                doctor_note: doctorNote,
                review_status: "needs_edit",
            });
            state.review.info = "已采纳改写建议，请确认后继续。";
            render(); // AI辅助生成：GLM-5, 2026-04-15
            return;
        }

        if (action === "save_section") {
            try {
                const data = await reviewApiPost("save_section", {
                    section_id: sectionId,
                    draft_text: draftText,
                    doctor_note: doctorNote,
                    review_status: "needs_edit",
                });
                reviewSetState(data.review_state, { keepCurrent: true });
                state.review.offlineMode = false;
                reviewClearLocalOps();
                state.review.info = "章节已保存。";
            } catch (err) {
                const next = reviewLocalSave(sectionId, draftText, doctorNote);
                reviewSetState(next, { keepCurrent: true, keepSuggestion: true }); // AI辅助生成：GLM-5, 2026-04-16
                reviewPushPending("save_section", {
                    section_id: sectionId,
                    draft_text: draftText,
                    doctor_note: doctorNote,
                    review_status: "needs_edit",
                });
                state.review.offlineMode = true;
                state.review.error = `保存已转本地兜底：${err.message}`;
            }
            render();
            return;
        }

        if (action === "confirm_section") {
            try {
                const data = await reviewApiPost("confirm_section", {
                    section_id: sectionId,
                    draft_text: draftText,
                    doctor_note: doctorNote,
                    auto_finalize: true,
                });
                reviewSetState(data.review_state);
                reviewApplyServerPayload(data);
                if (typeof data?.final_report === "string" && data.final_report.trim()) {
                    persistReport(state.fileId, {
                        report: data.final_report,
                        report_payload: runReport(state.latestRun)?.report_payload || null,
                    });
                }
                state.review.offlineMode = false; // AI辅助生成：GLM-5, 2026-04-17
                reviewClearLocalOps();
                state.review.info = data?.all_confirmed
                    ? "已全部确认，请点击「进入 Viewer」。"
                    : "章节确认成功，已解锁下一段。";
            } catch (err) {
                const next = reviewLocalConfirm(sectionId, draftText, doctorNote);
                reviewSetState(next);
                reviewPushPending("confirm_section", {
                    section_id: sectionId,
                    draft_text: draftText,
                    doctor_note: doctorNote,
                    auto_finalize: true,
                });
                state.review.offlineMode = true;
                state.review.serverCanEnterViewer = false;
                state.review.error = `确认已转本地兜底：${err.message}`;
            }
            render();
            return;
        }

        if (action === "enter_viewer") {
            if (!reviewCanEnterViewer()) {
                state.review.error = "请先完成全部章节确认并等待服务端完成复核节点。";
                render();
                return;
            }
            openViewerWithGate();
            return;
        }

        if (action === "finalize_review") {
            try {
                const data = await reviewApiPost("finalize_review", {});
                reviewSetState(data.review_state, { keepCurrent: true });
                reviewApplyServerPayload(data);
                if (typeof data?.final_report === "string" && data.final_report.trim()) {
                    persistReport(state.fileId, {
                        report: data.final_report,
                        report_payload: runReport(state.latestRun)?.report_payload || null,
                    });
                }
                state.review.offlineMode = false;
                reviewClearLocalOps(); // AI辅助生成：GLM-5, 2026-04-19
                state.review.info = "最终确认版报告已生成，请点击「进入 Viewer」。";
                render();
                return;
            } catch (err) {
                state.review.error = `最终归档失败：${err.message}`;
                render();
                return;
            }
        }
    } finally {
        state.review.saving = false;
        render(); // AI辅助生成：GLM-5, 2026-04-20
    }
}

async function submitQualityReview(decision) {
    if (state.qualityReview.saving) return;
    state.qualityReview.error = "";
    const reviewer = t(state.qualityReview.reviewer, "");
    const comment = t(state.qualityReview.comment, "");
    const result = state.latestJob?.quality_control_result || state.latestRun?.planner_input?.quality_control_result || {};
    if (!reviewer || !comment) state.qualityReview.error = "请填写审阅医生和复核备注。";
    else if (!state.qualityReview.acknowledged) state.qualityReview.error = "请先确认已核对图像质量风险。";
    else if (!result.qc_fingerprint) state.qualityReview.error = "质控指纹缺失，请刷新页面后重试。";
    if (state.qualityReview.error) { render(); return; }

    const endpoint = state.jobId
        ? `/api/upload/jobs/${encodeURIComponent(state.jobId)}/quality-review`
        : `/api/agent/runs/${encodeURIComponent(state.runId)}/quality-review`;
    state.qualityReview.saving = true;
    render();
    try {
        const resp = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ decision, reviewer, comment, qc_fingerprint: result.qc_fingerprint }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) throw new Error(data.error || `质控复核提交失败 (${resp.status})`);
        if (data.job) state.latestJob = data.job;
        if (data.run) state.latestRun = data.run;
        state.qualityReview.error = "";
        if (decision === "accept_risk" && !state.uploadTimer && state.jobId) state.uploadTimer = setInterval(pollUpload, 1200);
        if (decision === "reject_reupload") state.error = "图像质控已退回，请返回上传页重新上传影像。";
    } catch (error) {
        state.qualityReview.error = error.message;
    } finally {
        state.qualityReview.saving = false;
        render();
    }
}

async function pollUpload() {
    if (!state.jobId) return;
    try {
        const resp = await fetch(`/api/upload/progress/${encodeURIComponent(state.jobId)}`); const data = await resp.json();
        if (!resp.ok || !data.success) throw new Error(data.error || `上传状态获取失败 (${resp.status})`);
        state.error = ""; state.latestJob = data.job || {};
        if (!state.fileId && state.latestJob.file_id) state.fileId = String(state.latestJob.file_id);
        if (!state.runId && state.latestJob.agent_run_id) { state.runId = String(state.latestJob.agent_run_id); if (!state.runTimer) state.runTimer = setInterval(pollRun, 1400); pollRun(); }
        const st = normStatus(state.latestJob.status);
        if (token(state.latestJob.status) === "review_rejected") {
            state.error = "";
            clearInterval(state.uploadTimer);
            state.uploadTimer = null;
        }
        else if (st === "issue") { state.error = t(state.latestJob.error, "上传流程失败"); clearInterval(state.uploadTimer); state.uploadTimer = null; }
        else if (st === "completed") { if (!state.uploadDone) { state.uploadDone = true; persistUpload(state.latestJob); showViewerBtns(true); } clearInterval(state.uploadTimer); state.uploadTimer = null; if (!state.runId) scheduleViewer(false); }
        render(); // AI辅助生成：GLM-5, 2026-04-21
    } catch (err) { state.error = `上传链路异常: ${err.message}`; clearInterval(state.uploadTimer); state.uploadTimer = null; render(); }
}

async function fetchRunResultOnce() {
    if (state.runResultFetched || !state.runId) return;
    try {
        const resp = await fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}/result`); if (!resp.ok) return;
        const data = await resp.json(); if (!data.success) return;
        if (persistReport(state.fileId, ((data || {}).result || {}).report_result || null)) state.runResultFetched = true;
    } catch (_e) {}
}

async function pollRun() {
    if (!state.runId) return;
    try {
        const [runResp, evResp] = await Promise.all([fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}`), fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}/events`)]);
        if (runResp.status === 404 || evResp.status === 404) throw new Error("Agent run 不存在");
        const runData = await runResp.json(); const evData = await evResp.json();
        if (!runResp.ok || !runData.success) throw new Error(runData.error || `run 获取失败 (${runResp.status})`);
        if (!evResp.ok || !evData.success) throw new Error(evData.error || `events 获取失败 (${evResp.status})`);
        state.error = ""; state.latestRun = runData.run || {}; // AI辅助生成：GLM-5, 2026-04-22
        if (!state.fileId && state.latestRun.file_id) state.fileId = String(state.latestRun.file_id);
        if (!state.patientId && state.latestRun.patient_id !== undefined && state.latestRun.patient_id !== null) state.patientId = String(state.latestRun.patient_id);
        if (state.fileId && state.runId) localStorage.setItem(`latest_agent_run_${state.fileId}`, state.runId);
        persistReport(state.fileId, runReport(state.latestRun)); persistMrsPrognosisFromRun(state.latestRun); state.events = Array.isArray(evData.events) ? evData.events : []; state.hints = hintIndex(state.events);
        const s = token(state.latestRun.status);
        if (!TERMINAL.has(s)) { state.awaitingReport = false; state.runTerminalAt = 0; state.reportResultRetryUntil = 0; }
        if (TERMINAL.has(s)) {
            if (s === "failed" || s === "cancelled") {
                clearInterval(state.runTimer); state.runTimer = null; state.awaitingReport = false;
                state.review.required = false; state.review.visible = false;
            }
            else if (s === "paused_review_required" && token(state.latestRun?.human_checkpoint?.type) === "image_quality_control") {
                state.awaitingReport = false;
                state.review.required = false;
                state.review.visible = false;
            }
            else if (s === "succeeded" || s === "paused_review_required") {
                if (!state.runTerminalAt) { state.runTerminalAt = Date.now(); state.reportResultRetryUntil = state.runTerminalAt + RUN_RESULT_FETCH_MAX_WAIT_MS; }
                await fetchRunResultOnce(); const ready = reportReady(); state.awaitingReport = !ready;
                if (state.uploadDone) {
                    showViewerBtns(true);
                    if (ready) {
                        state.awaitingReport = false;
                        const ok = await ensureReviewState(false);
                        if (ok) {
                            if (s === "succeeded" && state.runTimer) {
                                clearInterval(state.runTimer);
                                state.runTimer = null;
                            }
                        }
                    } else if (Date.now() >= state.reportResultRetryUntil) {
                        clearInterval(state.runTimer); state.runTimer = null; state.awaitingReport = false; state.error = "报告尚未就绪，已暂停自动跳转。请稍后手动进入 Viewer。";
                    }
                }
            }
        }
        render();
    } catch (err) { state.error = `Agent runtime error: ${err.message}`; state.awaitingReport = false; clearInterval(state.runTimer); state.runTimer = null; render(); }
}

function bind() {
    $("runtimeBackUploadBtn").addEventListener("click", backToUpload);
    $("runtimeOpenViewerBtn").addEventListener("click", () => { openViewerWithGate(); });
    $("runtimeTopViewerBtn").addEventListener("click", () => { openViewerWithGate(); });
    $("runtimeOpenCockpitBtn").addEventListener("click", () => { window.location.href = cockpitUrl(); });
    $("runtimeGoW0Btn").addEventListener("click", () => { window.location.href = w0Url(); });
    $("runtimeCopyFileBtn").addEventListener("click", async () => { if (!state.fileId) return; try { await navigator.clipboard.writeText(state.fileId); $("runtimeCaseNote").textContent = `已复制 file_id：${state.fileId}`; } catch (err) { state.error = `复制 file_id 失败: ${err.message}`; render(); } });
    $("runtimeRailToggle").addEventListener("click", () => { const rail = $("runtimeAgentRail"); rail.classList.toggle("collapsed"); $("runtimeRailToggle").textContent = rail.classList.contains("collapsed") ? "Agent Network ▸" : "Agent Network ▾"; });
    $("clinicalDagReviewer")?.addEventListener("input", () => { state.dagReview.error = ""; updateDagApproveButton(); });
    $("clinicalDagScopeCheck")?.addEventListener("change", () => { state.dagReview.error = ""; updateDagApproveButton(); });
    $("clinicalDagApproveBtn")?.addEventListener("click", approveClinicalDag);
    if (typeof window !== "undefined") {
        window.addEventListener("resize", () => drawClinicalDagEdges(buildClinicalDag(modalities())), { passive: true });
    }
    $("runtimeFeed").addEventListener("wheel", () => { state.lastManualScrollAt = Date.now(); }, { passive: true });
    $("runtimeFeed").addEventListener("touchstart", () => { state.lastManualScrollAt = Date.now(); }, { passive: true });
    $("runtimeFeed").addEventListener("input", (ev) => {
        if (ev.target?.id === "qualityReviewReviewer") state.qualityReview.reviewer = ev.target.value;
        if (ev.target?.id === "qualityReviewComment") state.qualityReview.comment = ev.target.value;
        if (ev.target?.id === "qualityReviewAck") state.qualityReview.acknowledged = Boolean(ev.target.checked);
    });
    $("runtimeFeed").addEventListener("click", (ev) => {
        const qualityButton = ev.target.closest("[data-quality-decision]");
        if (qualityButton) { submitQualityReview(qualityButton.getAttribute("data-quality-decision")); return; }
        const btn = ev.target.closest("[data-toggle-node]"); if (!btn) return; const id = btn.getAttribute("data-toggle-node"); if (!id) return; state.expanded[id] = !state.expanded[id]; render();
    });
    document.addEventListener("click", (ev) => {
        const actionBtn = ev.target.closest("[data-review-action]");
        if (actionBtn) {
            const action = t(actionBtn.getAttribute("data-review-action"), "");
            if (action) {
                reviewHandleAction(action);
                return;
            }
        }
        const sectionBtn = ev.target.closest("[data-review-section]");
        if (!sectionBtn) return;
        const sid = t(sectionBtn.getAttribute("data-review-section"), "");
        if (!sid || reviewIsLocked(sid)) return;
        state.review.currentSectionId = sid;
        state.review.rewriteSuggestion = null;
        render();
    });
}

function init() {
    document.body.classList.add("processing-page-body");
    const params = new URLSearchParams(window.location.search);
    state.jobId = t(params.get("job_id"), ""); state.patientId = t(params.get("patient_id"), ""); state.fileId = t(params.get("file_id"), "");
    state.runId = t(params.get("run_id") || params.get("agent_run_id"), "");
    state.standalonePreview = window.location.protocol === "file:" && !state.jobId && !state.runId;
    if (state.standalonePreview) {
        const previewApproved = token(params.get("review")) === "approved";
        state.jobId = "preview-job";
        state.patientId = state.patientId || "867";
        state.fileId = state.fileId || "CASE-2026-0723";
        state.latestJob = {
            job_id: state.jobId,
            patient_id: state.patientId,
            file_id: state.fileId,
            status: "awaiting_review",
            progress: 18,
            message: "临床任务 DAG 已生成，等待医生审阅",
            modalities: ["ncct", "mcta", "vcta", "dcta"],
            dag_review: {
                review_status: previewApproved ? "completed" : "pending",
                doctor_final_decision: previewApproved ? "approved" : "pending",
                reviewer: previewApproved ? "演示医生" : "",
                reviewed_at: previewApproved ? new Date().toISOString() : "",
                dag_id: "clinical:ncct_mcta:dcta+mcta+ncct+vcta",
            },
            steps: [
                { key: "archive_ready", status: "completed", message: "病例材料已接收" },
                { key: "modality_detect", status: "completed", message: "已识别 NCCT 与三期 mCTA" },
                { key: "three_class", status: "pending", message: "等待任务范围确认" },
            ],
        };
    }
    if (!state.runId && state.fileId) state.runId = t(localStorage.getItem(`latest_agent_run_${state.fileId}`), "");
    if (typeof setCurrentPatientId === "function" && state.patientId) setCurrentPatientId(state.patientId);
    if (typeof setPatientInfoVisible === "function" && state.patientId) setPatientInfoVisible(true);
    if (typeof updatePatientHeader === "function" && state.patientId) updatePatientHeader(state.patientId);
    state.startedAt = new Date().toLocaleString();
    if (window.innerWidth <= 960) { $("runtimeAgentRail").classList.add("collapsed"); $("runtimeRailToggle").textContent = "Agent Network ▸"; }
    bind();
    render();
    if (state.standalonePreview) return;
    if (!state.jobId && !state.runId) { state.error = "缺少 job_id 或 run_id，无法加载处理页。"; render(); return; }
    if (state.jobId) {
        pollUpload(); state.uploadTimer = setInterval(pollUpload, 1000);
    } else {
        state.uploadDone = true;
        showViewerBtns(canNavigateViewer(false));
    }
    if (state.runId) { pollRun(); state.runTimer = setInterval(pollRun, 1400); }
}

if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", init);

if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        state,
        normStatus,
        nodeStatus,
        normalizeVesselOcclusionResult,
        vesselOcclusionResult,
        vesselFailureText,
        vesselResultText,
        displayStatusForNode,
        displayFallbackForNode,
        withDisplayStatus,
        resolveUploadNodeState,
        canAdvanceRevealFrom,
        isBlockingIssue,
        syncRevealQueue,
        clearRevealTimer,
        reviewApplyServerPayload,
        reviewCanEnterViewer,
        reviewCaptureEditorSnapshot,
        reviewRestoreEditorSnapshot,
        buildNodes,
        persistUpload,
        persistMrsPrognosisFromRun,
        normalizeModalityList,
        clinicalPathForModalities,
        buildClinicalDag,
        clinicalDagStructureKey,
        systemExecutionRows,
        decorateExecutionNodes,
        clinicalDagForJob,
    };
}
