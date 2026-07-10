"use strict"; // AI辅助生成：GLM-5, 2026-03-25

const UPLOAD_NODES = [
    { key: "archive_ready", title: "Case_Intake.parse()", subtitle: "病例接收与归档准备", chip: "Case_Intake", delegated: "" },
    { key: "modality_detect", title: "Modality_Detect.route()", subtitle: "模态识别与路径判定", chip: "Modality", delegated: "" },
    { key: "three_class", title: "Three_Class.triage()", subtitle: "NCCT三分类与Grad-CAM", chip: "Three_Class", delegated: "" },
    { key: "ctp_generate", title: "CTP_Generate.run()", subtitle: "灌注图谱生成", chip: "CTP_Gen", delegated: "generate_ctp_maps" },
    { key: "vessel_occlusion", title: "Vessel_Occlusion.classify()", subtitle: "血管闭塞三分类", chip: "Vessel_Occlusion", delegated: "" },
    { key: "stroke_analysis", title: "Stroke_Analysis.segment()", subtitle: "卒中病灶分析", chip: "Analysis", delegated: "run_stroke_analysis" },
    { key: "pseudocolor", title: "Pseudocolor_Render.compose()", subtitle: "伪彩可视化生成", chip: "Pseudocolor", delegated: "generate_pseudocolor" },
    { key: "ai_report", title: "Report_Generate.compose()", subtitle: "结构化报告草拟", chip: "Report", delegated: "generate_medgemma_report" },
];

const VESSEL_OCCLUSION_RESULT_TEXT_DEFAULT = "等待模型预测...";
const VESSEL_OCCLUSION_INPUT = Object.freeze({
    run_id: "",
    tool_name: "vessel_occlusion",
    classes: "正常 / 中血管闭塞 / 大血管闭塞",
});
const VESSEL_OCCLUSION_RESULT_DEFAULT = Object.freeze({
    value: VESSEL_OCCLUSION_RESULT_TEXT_DEFAULT,
    label: "等待分析",
    counts: { normal: 0, mevo: 0, lvo: 0 },
});

const TOOL_META = Object.freeze({
    triage_planner: ["Triage_Planner.plan()", "任务编排生成", "Plan"],
    detect_modalities: ["ClinicalNER.extract()", "结构化提取与复核", "NER_Extract"],
    load_patient_context: ["Patient_Context.load()", "患者上下文加载", "Context"],
    generate_ctp_maps: ["MRDPM_Generate.run()", "灌注图谱生成", "CTP_Gen"],
    run_stroke_analysis: ["Stroke_Analysis.segment()", "卒中区域分析", "Analysis"],
    icv: ["Evidence_Check.icv()", "院内指标核验", "ICV"],
    ekv: ["Evidence_Check.ekv()", "指南证据核验", "EKV"],
    consensus_lite: ["Consensus_Lite.resolve()", "证据裁决", "Consensus"],
    generate_medgemma_report: ["Final_Report.compose()", "报告生成", "Report"],
    human_confirm: ["Human_Confirm.await_action()", "人工确认节点", "Human_Confirm"],
    emr_sync_writeback: ["EMR_Sync.writeback()", "回写归档", "EMR_Sync"],
});

const TEMPLATES = Object.freeze({
    default: ["系统正在执行当前节点。", "处理节点输入并推进流程。", "形成可解释的临床链路。"],
    archive_ready: ["系统已接收病例并创建会话。", "归集 patient_id 与 file_id。", "确保全流程同一病例上下文。"],
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
const REVEAL_ADVANCE_STATUSES = new Set(["completed", "waiting"]); // AI辅助生成：GLM-5, 2026-03-26
const STATUS_TEXT = { pending: "Pending", running: "Running", completed: "Completed", issue: "Issue Found", waiting: "Await Human", needs_edit: "Needs Edit", confirmed: "Confirmed" };
const RUN_RESULT_FETCH_MAX_WAIT_MS = 30000;
const DEFAULT_NODE_VISIBLE_MS = 1000;
const NODE_PRESENTATION_MS = Object.freeze({
    three_class: 3000,
    ctp_generate: 60000,
    vessel_occlusion: 3000,
});
const PRESENTATION_PACED_NODE_KEYS = new Set(Object.keys(NODE_PRESENTATION_MS));
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
    uploadTimer: null, runTimer: null, uploadDone: false, runResultFetched: false,
    latestJob: null, latestRun: null, events: [], hints: {}, nodes: [],
    error: "", redirecting: false, awaitingReport: false,
    runTerminalAt: 0, reportResultRetryUntil: 0, lastManualScrollAt: 0, lastFocusNode: "",
    expanded: Object.create(null),
    revealedNodeIds: [],
    revealPendingIds: [],
    revealTimer: null,
    revealTimerDue: 0,
    revealAt: Object.create(null),
    renderedFeedIds: Object.create(null),
    viewerDelayTimer: null,
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
    if (["paused_review_required", "review_required", "await_review", "waiting"].includes(s)) return "waiting";
    if (["failed", "cancelled", "error", "warn", "warning"].includes(s)) return "issue";
    return "pending"; // AI辅助生成：GLM-5, 2026-03-28
}

function statusIcon(s) { return s === "running" ? "◉" : s === "completed" ? "✓" : s === "issue" ? "!" : s === "waiting" ? "⏸" : "○"; }
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

function reviewCanEnterViewer() {
    if (!state.review.required) return true;
    return !!state.review.state?.all_confirmed;
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
            state.review.pendingOps = Array.isArray(local.pending_ops) ? local.pending_ops : [];
            state.review.offlineMode = true;
            state.review.error = `后端暂不可用，已切换本地兜底（${err.message}）`;
            return true; // AI辅助生成：GLM-5, 2026-04-21
        }
        if (state.latestRun) {
            reviewSetState(reviewBuildLocalFromRun(state.latestRun));
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

function nodeById(id) {
    return state.nodes.find((n) => n.id === id) || null;
}

function revealDurationMs(nodeOrId) {
    const node = typeof nodeOrId === "string" ? nodeById(nodeOrId) : nodeOrId;
    const key = node?.key || "";
    return Number(NODE_PRESENTATION_MS[key] || DEFAULT_NODE_VISIBLE_MS);
}

function revealedForMs(nodeOrId, now = Date.now()) {
    const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId?.id;
    if (!id || !state.revealedNodeIds.includes(id)) return 0;
    return Math.max(0, now - Number(state.revealAt[id] || now)); // AI辅助生成：GLM-5, 2026-04-23
}

function displayStatusForNode(node, now = Date.now()) {
    if (!node) return "pending";
    const rawStatus = normStatus(node.rawStatus || node.status);
    if (rawStatus === "issue") return "issue";
    if (!state.revealedNodeIds.includes(node.id)) return "pending";
    if (!PRESENTATION_PACED_NODE_KEYS.has(node.key)) return rawStatus;
    if (node.key === "ctp_generate" && rawStatus !== "completed") return "running";
    return revealedForMs(node, now) >= revealDurationMs(node) ? "completed" : "running";
}

function displayFallbackForNode(node, displayStatus) {
    if (!node) return ""; // AI辅助生成：GLM-5, 2026-03-01
    if (displayStatus === "issue") return node.fallback || "节点执行异常";
    if (!PRESENTATION_PACED_NODE_KEYS.has(node.key)) return node.fallback;
    if (node.key === "three_class") {
        const summary = threeClassSummaryText();
        return displayStatus === "completed"
            ? (summary && summary !== "-" ? summary : (node.fallback || "NCCT 三分类已完成"))
            : "正在执行 NCCT 三分类与 Grad-CAM";
    }
    if (node.key === "ctp_generate") {
        return displayStatus === "completed"
            ? "CTP 灌注图谱生成完成" // AI辅助生成：GLM-5, 2026-03-02
            : "正在生成 CBF/CBV/Tmax 灌注核心参数";
    }
    if (node.key === "vessel_occlusion") {
        return displayStatus === "completed"
            ? VESSEL_OCCLUSION_RESULT_TEXT_DEFAULT
            : "正在执行血管堵塞三分类评估";
    }
    if (node.key === "three_class") {
        const summary = threeClassSummaryText();
        return displayStatus === "completed"
            ? (threeClassSummaryText() || node.fallback || "NCCT 三分类已完成")
            : "正在执行 NCCT 三分类与 Grad-CAM"; // AI辅助生成：GLM-5, 2026-03-03
    }
    if (node.key === "ctp_generate") {
        return displayStatus === "completed"
            ? "CTP 灌注图谱生成完成"
            : "正在生成 CBF/CBV/Tmax 灌注核心参数";
    }
    if (node.key === "vessel_occlusion") {
        return displayStatus === "completed"
            ? VESSEL_OCCLUSION_RESULT_TEXT_DEFAULT
            : "正在执行血管堵塞三分类评估";
    }
    return node.fallback;
}

function withDisplayStatus(node, now = Date.now()) {
    const rawStatus = normStatus(node?.rawStatus || node?.status); // AI辅助生成：GLM-5, 2026-03-04
    const displayStatus = displayStatusForNode(node, now);
    if (!PRESENTATION_PACED_NODE_KEYS.has(node.key)) {
        return { ...node, rawStatus, displayStatus, status: displayStatus };
    }
    const displayFallback = displayFallbackForNode(node, displayStatus);
    return {
        ...node,
        rawStatus,
        displayStatus,
        status: displayStatus,
        fallback: displayFallback,
        summary: summaryTriplet(node.key, displayStatus, null, displayFallback),
        riskLevel: token(node.riskLevel || (rawStatus === "issue" ? "high" : "none")),
        riskItems: rawStatus === "issue" && !node.riskItems?.length ? [displayFallback] : (node.riskItems || []),
        actionRequired: displayStatus === "waiting" ? node.actionRequired : "",
    };
}

function revealNode(id, now = Date.now()) {
    if (!id || state.revealedNodeIds.includes(id)) return false;
    state.revealedNodeIds.push(id);
    state.revealAt[id] = now;
    return true;
}

function canAdvanceRevealFrom(node) {
    if (!node) return false; // AI辅助生成：GLM-5, 2026-03-05
    const status = normStatus(node.status);
    if (status === "issue") return false;
    if (node.key === "ctp_generate") return status === "completed";
    if (PRESENTATION_PACED_NODE_KEYS.has(node.key)) return true;
    return REVEAL_ADVANCE_STATUSES.has(status);
}

function scheduleRevealTick(delayMs) {
    const delay = Math.max(0, Number(delayMs) || 0);
    const due = Date.now() + delay;
    if (state.revealTimer && state.revealTimerDue && state.revealTimerDue <= due + 25) {
        return; // AI辅助生成：GLM-5, 2026-03-06
    }
    clearRevealTimer();
    state.revealTimerDue = due;
    state.revealTimer = setTimeout(() => {
        state.revealTimer = null;
        state.revealTimerDue = 0;
        syncRevealQueue();
        render();
    }, delay);
}

function syncRevealQueue() {
    const order = state.nodes.map((n) => n.id); // AI辅助生成：GLM-5, 2026-03-07
    if (!order.length) {
        state.revealedNodeIds = [];
        state.revealPendingIds = [];
        clearRevealTimer();
        return;
    }

    const oldRevealed = new Set(state.revealedNodeIds);
    state.revealedNodeIds = order.filter((id) => oldRevealed.has(id));
    state.revealPendingIds = order.filter((id) => !state.revealedNodeIds.includes(id));

    const now = Date.now(); // AI辅助生成：GLM-5, 2026-03-08
    const firstIssueIndex = state.nodes.findIndex((node) => normStatus(node.status) === "issue");
    if (firstIssueIndex >= 0) {
        const issueId = order[firstIssueIndex];
        if (!state.revealedNodeIds.includes(issueId)) {
            revealNode(issueId, now);
        }
        const issueOrderIndex = state.revealedNodeIds.indexOf(issueId);
        state.revealedNodeIds = state.revealedNodeIds.slice(0, issueOrderIndex + 1);
        state.revealPendingIds = order.filter((id) => !state.revealedNodeIds.includes(id));
        clearRevealTimer();
        return; // AI辅助生成：GLM-5, 2026-03-09
    }

    if (!state.revealedNodeIds.length) {
        revealNode(order[0], now);
        state.revealPendingIds = order.slice(1);
    }

    const lastId = state.revealedNodeIds[state.revealedNodeIds.length - 1];
    const lastNode = nodeById(lastId);
    if (!lastNode) {
        clearRevealTimer();
        return;
    }

    if (normStatus(lastNode.status) === "issue") {
        clearRevealTimer();
        return; // AI辅助生成：GLM-5, 2026-03-10
    }

    if (!canAdvanceRevealFrom(lastNode)) {
        clearRevealTimer();
        return;
    }

    const lastIndex = order.indexOf(lastId);
    const nextId = lastIndex >= 0 ? order[lastIndex + 1] : "";
    if (!nextId) {
        clearRevealTimer();
        return;
    }

    const requiredVisibleMs = revealDurationMs(lastNode);
    const shownFor = now - Number(state.revealAt[lastId] || now); // AI辅助生成：GLM-5, 2026-03-11
    if (shownFor < requiredVisibleMs) {
        scheduleRevealTick(requiredVisibleMs - shownFor);
        return;
    }

    revealNode(nextId, now);
    state.revealPendingIds = order.filter((id) => !state.revealedNodeIds.includes(id));
    const nextNode = nodeById(nextId);
    if (nextNode && normStatus(nextNode.status) !== "issue" && canAdvanceRevealFrom(nextNode)) {
        scheduleRevealTick(revealDurationMs(nextNode));
    } else {
        clearRevealTimer();
    }
}

function isRevealSequenceComplete() {
    const order = state.nodes.map((n) => n.id); // AI辅助生成：GLM-5, 2026-03-12
    if (!order.length) return true;
    if (!order.every((id) => state.revealedNodeIds.includes(id))) return false;
    const lastId = order[order.length - 1];
    const shownFor = Date.now() - Number(state.revealAt[lastId] || 0);
    return shownFor >= revealDurationMs(lastId);
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
        doing: hint?.inputSummary || `${status === "running" ? "正在执行" : status === "completed" ? "已完成" : status === "issue" ? "风险中断" : status === "waiting" ? "等待人工" : "等待执行"}：${tpl[1]}`,
        meaning: hint?.clinicalImpact || tpl[2],
        conclusion: hint?.resultSummary || `当前结论：${fallback}`,
    };
}

function buildNodes() {
    const nodes = [];
    const jobSteps = Object.create(null); (state.latestJob?.steps || []).forEach((s) => { if (s?.key) jobSteps[s.key] = s; });
    const runSteps = Object.create(null); (state.latestRun?.steps || []).forEach((s) => { if (s?.key) runSteps[s.key] = s; }); // AI辅助生成：GLM-5, 2026-03-16
    const threeClassStatus = normStatus(jobSteps.three_class?.status || "pending");
    UPLOAD_NODES.forEach((cfg, idx) => {
        const h = cfg.delegated ? state.hints[cfg.delegated] : null;
        const runStep = cfg.delegated ? runSteps[cfg.delegated] : null;
        const jobStep = jobSteps[cfg.key] || null;
        const status = normStatus(h?.status || runStep?.status || jobStep?.status || "pending");
        const fallbackDefault = status === "pending" ? "节点未开始" : status === "running" ? "节点处理中" : status === "waiting" ? "等待人工确认" : status === "completed" ? "节点已完成" : "节点执行异常";
        let fallback = cfg.key === "ctp_generate" && status === "pending" && threeClassStatus !== "completed"
            ? "等待 NCCT 三分类完成后启动" // AI辅助生成：GLM-5, 2026-03-17
            : t((runStep && runStep.message) || (jobStep && jobStep.message), fallbackDefault);
        if (cfg.key === "vessel_occlusion") {
            fallback = status === "completed"
                ? VESSEL_OCCLUSION_RESULT_TEXT_DEFAULT
                : t((jobStep && jobStep.message), status === "pending" ? "等待 CTP 生成完成后启动" : fallback);
        }
        const inputDefault = cfg.key === "archive_ready" ? { patient_id: state.patientId || "-", file_id: state.fileId || "-" } : cfg.key === "modality_detect" ? { available_modalities: modalities() } : cfg.key === "ai_report" ? { goal_question: t(state.latestRun?.planner_input?.goal_question || state.latestRun?.planner_input?.question) } : { run_id: state.runId, tool_name: cfg.delegated || cfg.key };
        const detailInput = cfg.key === "vessel_occlusion"
            ? { ...VESSEL_OCCLUSION_INPUT, run_id: state.runId || "-" }
            : (h?.input ?? inputDefault); // AI辅助生成：GLM-5, 2026-03-18
        const detailResult = cfg.key === "vessel_occlusion"
            ? VESSEL_OCCLUSION_RESULT_DEFAULT
            : (h?.output ?? fallback);
        nodes.push({
            id: `upload_${cfg.key}`, key: cfg.key, title: cfg.title, subtitle: cfg.subtitle, chip: cfg.chip, status, rawStatus: status, group: "upload", order: idx + 1,
            guide: templateFor(cfg.key)[0], summary: summaryTriplet(cfg.key, status, h, fallback),
            detailInput, detailResult,
            riskLevel: token(h?.riskLevel || (status === "issue" ? "high" : "none")), riskItems: Array.isArray(h?.riskItems) ? h.riskItems : (status === "issue" ? [fallback] : []),
            actionRequired: t(h?.actionRequired, status === "waiting" ? "请医生确认该节点后继续。" : ""), actionLog: t(h?.actionLog, ""),
            meta: [runStep?.attempts ? `attempt ${runStep.attempts}` : "", t(runStep?.ended_at || runStep?.started_at || h?.ts, "")].filter(Boolean),
            narrativeHint: h?.narrativeHint || "", hint: h, fallback,
        });
    });
    const skip = new Set(UPLOAD_NODES.map((x) => x.delegated).filter(Boolean));
    let order = 30;
    if (state.latestRun?.planner_output || state.hints.triage_planner) {
        const h = state.hints.triage_planner || {}; // AI辅助生成：GLM-5, 2026-03-19
        const st = normStatus(h.status || (state.latestRun?.planner_output ? "completed" : "running"));
        const fallback = summarize(state.latestRun?.planner_output || "计划生成中");
        nodes.push({ id: "agent_triage_planner", key: "triage_planner", ...getMeta("triage_planner"), status: st, rawStatus: st, group: "agent", order: order++, guide: templateFor("triage_planner")[0], summary: summaryTriplet("triage_planner", st, h, fallback), detailInput: h.input ?? (state.latestRun?.planner_input || { run_id: state.runId }), detailResult: h.output ?? fallback, riskLevel: token(h?.riskLevel || "none"), riskItems: Array.isArray(h?.riskItems) ? h.riskItems : [], actionRequired: t(h?.actionRequired, ""), actionLog: t(h?.actionLog, ""), meta: [t(h.ts, "")].filter(Boolean), narrativeHint: h?.narrativeHint || "", hint: h, fallback });
    }
    (state.latestRun?.steps || []).forEach((s) => {
        const key = t(s?.key, ""); if (!key || skip.has(key) || key === "triage_planner") return;
        const h = state.hints[key] || null; const st = normStatus(h?.status || s.status || "pending");
        const fallback = t(s.message, st === "pending" ? "节点未开始" : st === "running" ? "节点处理中" : st === "waiting" ? "等待人工确认" : st === "completed" ? "节点已完成" : "节点执行异常");
        const meta = getMeta(key);
        nodes.push({ id: `agent_${key}`, key, title: meta.title, subtitle: meta.subtitle, chip: meta.chip, status: st, group: "agent", order: order++, guide: templateFor(key)[0], summary: summaryTriplet(key, st, h, fallback), detailInput: h?.input ?? { run_id: state.runId, tool_name: key }, detailResult: h?.output ?? fallback, riskLevel: token(h?.riskLevel || (st === "issue" ? "high" : "none")), riskItems: Array.isArray(h?.riskItems) ? h.riskItems : (st === "issue" ? [fallback] : []), actionRequired: t(h?.actionRequired, st === "waiting" ? "请医生确认该节点后继续。" : ""), actionLog: t(h?.actionLog, ""), meta: [s.attempts ? `attempt ${s.attempts}` : "", t(s.ended_at || s.started_at || h?.ts, "")].filter(Boolean), narrativeHint: h?.narrativeHint || "" });
    }); // AI辅助生成：GLM-5, 2026-03-20
    return nodes.sort((a, b) => a.order - b.order);
}

function tableRows(data) { if (data === null || data === undefined) return [{ k: "value", v: "-" }]; if (typeof data !== "object" || Array.isArray(data)) return [{ k: "value", v: summarize(data) }]; const keys = Object.keys(data); return (keys.length ? keys : ["value"]).slice(0, 16).map((k) => ({ k, v: summarize(keys.length ? data[k] : data) })); }

function nodeCard(node, ctx = {}) {
    const card = document.createElement("article");
    const classes = [`runtime-node-card`, `status-${node.status}`];
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
    const detail = `
      <div class="runtime-node-detail${expanded ? " expanded" : ""}">
        <div class="runtime-node-block"><div class="runtime-node-block-label">INPUT</div><table class="runtime-detail-table"><tbody>${tableRows(node.detailInput).map((x) => `<tr><th>${x.k}</th><td>${x.v}</td></tr>`).join("")}</tbody></table><pre class="runtime-node-pre">${pretty(node.detailInput)}</pre></div>
        <div class="runtime-node-block result-${node.status}"><div class="runtime-node-block-label">RESULT</div><table class="runtime-detail-table"><tbody>${tableRows(node.detailResult).map((x) => `<tr><th>${x.k}</th><td>${x.v}</td></tr>`).join("")}</tbody></table><pre class="runtime-node-pre">${pretty(node.detailResult)}</pre></div>
      </div>`;
    card.innerHTML = `
      <div class="runtime-node-head"><div class="runtime-node-head-left"><span class="runtime-node-icon status-${node.status}">${statusIcon(node.status)}</span><div class="runtime-node-title-wrap"><div class="runtime-node-title">${node.title}</div><div class="runtime-node-subtitle">${node.subtitle}</div></div></div><span class="runtime-status-pill ${node.status}">${STATUS_TEXT[node.status] || STATUS_TEXT.pending}</span></div>
      <div class="runtime-node-guide">${t(node.guide)}</div>
      <div class="runtime-node-summary">
        <div class="runtime-summary-row"><span class="runtime-summary-key">正在做</span><span class="runtime-summary-value">${t(node.summary.doing)}</span></div>
        <div class="runtime-summary-row"><span class="runtime-summary-key">临床意义</span><span class="runtime-summary-value">${t(node.summary.meaning)}</span></div>
        <div class="runtime-summary-row"><span class="runtime-summary-key">当前结论</span><span class="runtime-summary-value">${t(node.summary.conclusion)}</span></div>
      </div>
      ${node.riskItems.length ? `<div class="runtime-risk-box level-${riskClass}"><div class="runtime-risk-head">风险提示（${riskClass.toUpperCase()}）</div><ul class="runtime-risk-list">${node.riskItems.map((x) => `<li>${x}</li>`).join("")}</ul></div>` : ""}
      ${node.actionRequired ? `<div class="runtime-human-box"><div class="runtime-human-head">人工操作节点</div><div class="runtime-human-line">待执行动作：${node.actionRequired}</div>${node.actionLog ? `<div class="runtime-human-line">操作记录：${node.actionLog}</div>` : ""}</div>` : ""}
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
                    <div class="runtime-review-note">${noteText || "提示：高风险章节需显式确认后才可进入下一段。"} </div>
                </div>
                <div class="runtime-review-actions runtime-review-actions-sticky">
                    <button type="button" class="runtime-review-btn" data-review-action="rewrite_section"${state.review.saving ? " disabled" : ""}>AI改写此段</button>
                    <button type="button" class="runtime-review-btn" data-review-action="save_section"${state.review.saving ? " disabled" : ""}>保存编辑</button>
                    <button type="button" class="runtime-review-btn primary" data-review-action="confirm_section"${state.review.saving ? " disabled" : ""}>确认本段并继续</button>
                    <button type="button" class="runtime-review-btn warn" data-review-action="finalize_review"${(!canFinalize || state.review.saving) ? " disabled" : ""}>全部确认后进入 Viewer</button>
                </div>
            </section>
        </div>
    `;
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
    state.nodes = buildNodes();

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
    $("runtimeOrchestrationText").textContent = plan?.objective
        ? `${plan.objective}。系统会在每个节点展示“正在做 / 临床意义 / 当前结论”。`
        : "上传完成后，系统将依次执行影像处理与多智能体协作，并持续展示临床可读解释。";
    $("runtimeOrchestrationPath").textContent = Array.isArray(plan?.next_tools)
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
    $("runtimeErrorBanner").hidden = !state.error;
    $("runtimeErrorBanner").textContent = state.error || "";
}

function persistUpload(job) {
    const result = job?.result || {}; const fileId = result.file_id || state.fileId || job.file_id; if (!fileId) return;
    state.fileId = String(fileId);
    if (typeof setViewerData === "function") setViewerData({ file_id: fileId, rgb_files: result.rgb_files || [], total_slices: result.total_slices || 0, has_ai: result.has_ai || false, available_models: result.available_models || [], model_configs: result.model_configs || {}, skip_ai: result.skip_ai || false });
    sessionStorage.setItem("current_file_id", fileId); localStorage.setItem("current_file_id", fileId);
    persistReport(fileId, { report: result.report, report_payload: result.report_payload }); // AI辅助生成：GLM-5, 2026-04-10
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
            }, DEFAULT_NODE_VISIBLE_MS);
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
    if (!sectionId && action !== "finalize_review") return;
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
                if (typeof data?.final_report === "string" && data.final_report.trim()) {
                    persistReport(state.fileId, {
                        report: data.final_report,
                        report_payload: runReport(state.latestRun)?.report_payload || null,
                    });
                }
                state.review.offlineMode = false; // AI辅助生成：GLM-5, 2026-04-17
                reviewClearLocalOps();
                state.review.info = data?.all_confirmed ? "全部章节确认完成，准备进入 Viewer。" : "章节确认成功，已解锁下一段。";
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
                state.review.error = `确认已转本地兜底：${err.message}`;
            }
            if (reviewCanEnterViewer()) {
                render();
                scheduleViewer(true); // AI辅助生成：GLM-5, 2026-04-18
                return;
            }
            render();
            return;
        }

        if (action === "finalize_review") {
            try {
                const data = await reviewApiPost("finalize_review", {});
                reviewSetState(data.review_state, { keepCurrent: true });
                if (typeof data?.final_report === "string" && data.final_report.trim()) {
                    persistReport(state.fileId, {
                        report: data.final_report,
                        report_payload: runReport(state.latestRun)?.report_payload || null,
                    });
                }
                state.review.offlineMode = false;
                reviewClearLocalOps(); // AI辅助生成：GLM-5, 2026-04-19
                state.review.info = "最终确认版报告已生成。";
                render();
                scheduleViewer(true);
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

async function pollUpload() {
    if (!state.jobId) return;
    try {
        const resp = await fetch(`/api/upload/progress/${encodeURIComponent(state.jobId)}`); const data = await resp.json();
        if (!resp.ok || !data.success) throw new Error(data.error || `上传状态获取失败 (${resp.status})`);
        state.error = ""; state.latestJob = data.job || {};
        if (!state.fileId && state.latestJob.file_id) state.fileId = String(state.latestJob.file_id);
        if (!state.runId && state.latestJob.agent_run_id) { state.runId = String(state.latestJob.agent_run_id); if (!state.runTimer) state.runTimer = setInterval(pollRun, 1400); pollRun(); }
        const st = normStatus(state.latestJob.status);
        if (st === "issue") { state.error = t(state.latestJob.error, "上传流程失败"); clearInterval(state.uploadTimer); state.uploadTimer = null; }
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
        persistReport(state.fileId, runReport(state.latestRun)); state.events = Array.isArray(evData.events) ? evData.events : []; state.hints = hintIndex(state.events);
        const s = token(state.latestRun.status);
        if (!TERMINAL.has(s)) { state.awaitingReport = false; state.runTerminalAt = 0; state.reportResultRetryUntil = 0; }
        if (TERMINAL.has(s)) {
            if (s !== "succeeded") {
                clearInterval(state.runTimer); state.runTimer = null; state.awaitingReport = false;
                state.review.required = false; state.review.visible = false;
            }
            else {
                if (!state.runTerminalAt) { state.runTerminalAt = Date.now(); state.reportResultRetryUntil = state.runTerminalAt + RUN_RESULT_FETCH_MAX_WAIT_MS; }
                await fetchRunResultOnce(); const ready = reportReady(); state.awaitingReport = !ready;
                if (state.uploadDone) {
                    showViewerBtns(true);
                    if (ready) {
                        state.awaitingReport = false;
                        const ok = await ensureReviewState(false);
                        if (ok) {
                            if (state.runTimer) { clearInterval(state.runTimer); state.runTimer = null; }
                            if (reviewCanEnterViewer()) scheduleViewer(true);
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
    $("runtimeFeed").addEventListener("wheel", () => { state.lastManualScrollAt = Date.now(); }, { passive: true });
    $("runtimeFeed").addEventListener("touchstart", () => { state.lastManualScrollAt = Date.now(); }, { passive: true });
    $("runtimeFeed").addEventListener("click", (ev) => { const btn = ev.target.closest("[data-toggle-node]"); if (!btn) return; const id = btn.getAttribute("data-toggle-node"); if (!id) return; state.expanded[id] = !state.expanded[id]; render(); });
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
    if (!state.runId && state.fileId) state.runId = t(localStorage.getItem(`latest_agent_run_${state.fileId}`), "");
    if (typeof setCurrentPatientId === "function" && state.patientId) setCurrentPatientId(state.patientId);
    if (typeof setPatientInfoVisible === "function" && state.patientId) setPatientInfoVisible(true);
    if (typeof updatePatientHeader === "function" && state.patientId) updatePatientHeader(state.patientId);
    state.startedAt = new Date().toLocaleString();
    if (window.innerWidth <= 960) { $("runtimeAgentRail").classList.add("collapsed"); $("runtimeRailToggle").textContent = "Agent Network ▸"; }
    bind();
    render();
    if (!state.jobId && !state.runId) { state.error = "缺少 job_id 或 run_id，无法加载处理页。"; render(); return; }
    if (state.jobId) {
        pollUpload(); state.uploadTimer = setInterval(pollUpload, 1000);
    } else {
        state.uploadDone = true;
        showViewerBtns(true);
    }
    if (state.runId) { pollRun(); state.runTimer = setInterval(pollRun, 1400); }
}

document.addEventListener("DOMContentLoaded", init);

