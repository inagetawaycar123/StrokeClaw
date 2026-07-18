let cockpitRunId = ''; // AI辅助生成：GLM-5, 2026-04-23
let cockpitFileId = '';
let cockpitPatientId = '';
let cockpitJobId = '';

let cockpitRun = null;
let cockpitEvents = [];
let cockpitResult = null;
let cockpitValidation = null;
let cockpitUploadResult = null;

let cockpitPollTimer = null; // AI辅助生成：GLM-5, 2026-03-01
let cockpitSourceTag = 'real';
let cockpitApiUrls = {
    runUrl: '',
    eventsUrl: '',
    resultUrl: '',
};

let cockpitNodes = [];
let cockpitEdges = [];
let cockpitGraphModel = null;
let cockpitSelectedNodeKey = '';
let cockpitActiveEventSeq = null;
let cockpitDagZoom = 1;
let demoAutoCollapsedOnce = false; // AI辅助生成：GLM-5, 2026-03-02
let currentDrawerTab = 'clinical';

const COCKPIT_TERMINAL = new Set(['succeeded', 'failed', 'cancelled', 'paused_review_required']);

const STATUS_TEXT_MAP = {
    queued: '排队中',
    running: '运行中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
    paused_review_required: '待人工复核',
    pending: '待执行',
    completed: '已完成',
    skipped: '已跳过',
    pass: '通过',
    warn: '警告',
    fail: '失败',
    unavailable: '不可用',
    review_required: '待复核',
};

const STAGE_TEXT_MAP = {
    triage: '病例输入',
    tooling: '影像与分析',
    icv: '内在一致性校验',
    ekv: '外部证据校验',
    consensus: '一致性裁决',
    summary: '报告与总结',
    done: '完成',
};

const CONSENSUS_TEXT_MAP = {
    accept: '接受',
    review_required: '需复核',
    escalate: '需升级处理',
    unavailable: '不可用',
    skipped: '已跳过',
};

const ANSWER_STATUS_TEXT_MAP = {
    pending: '待生成',
    running: '生成中',
    ready: '已生成',
    failed: '失败',
    unavailable: '不可用',
};

const SOURCE_CHAIN_TEXT_MAP = {
    none: '无',
    case_latest_result_json: '病例最新结果',
    run_result: '运行结果',
    run_result_by_id: '按 run_id 命中运行结果',
    agent_run_result: 'Agent 运行结果',
    report_payload: '报告载荷',
    local_storage_fallback: '本地回退',
};

const DAG_LANES = [
    { lane_key: 'L1', title: '病例输入', order: 1 },
    { lane_key: 'L2', title: '影像初筛', order: 2 },
    { lane_key: 'L3', title: '灌注与卒中分析', order: 3 },
    { lane_key: 'L4', title: '决策与报告', order: 4 },
    { lane_key: 'L5', title: '人工复核与发布', order: 5 },
];

const TOOL_TITLE_MAP = {
    triage_planner: 'Planner',
    detect_modalities: '模态识别',
    load_patient_context: '病例上下文',
    run_ncct_classification: 'NCCT三分类',
    run_vessel_occlusion_classification: '血管闭塞三分类',
    generate_ctp_maps: '类CTP生成',
    run_stroke_analysis: '卒中自动分析',
    run_mrs_prediction: 'mRS 风险预测',
    icv: '内在一致性校验',
    ekv: '外部证据校验',
    consensus_lite: '一致性裁决',
    generate_structured_report: '结构化报告生成',
    generate_medgemma_report: '结构化报告生成',
    summary: '总结',
    human_confirm: '人工确认',
    human_review: '人工复核',
    export_report: '报告导出',
    emr_sync: '报告发布',
    emr_sync_writeback: '报告发布',
    run_ai_qa: 'AI 问诊',
};

const TOOL_LANE_MAP = {
    triage_planner: 'L1',
    detect_modalities: 'L1',
    load_patient_context: 'L1',
    run_ncct_classification: 'L2',
    run_vessel_occlusion_classification: 'L3',
    generate_ctp_maps: 'L3',
    run_stroke_analysis: 'L3',
    run_mrs_prediction: 'L3',
    icv: 'L4',
    ekv: 'L4',
    consensus_lite: 'L4',
    generate_structured_report: 'L4',
    generate_medgemma_report: 'L4',
    summary: 'L4',
    human_confirm: 'L5',
    human_review: 'L5',
    export_report: 'L5',
    emr_sync: 'L5',
    emr_sync_writeback: 'L5',
    run_ai_qa: 'L5',
};

const STAGE_LANE_MAP = {
    triage: 'L1',
    tooling: 'L3',
    icv: 'L4',
    ekv: 'L4',
    consensus: 'L4',
    summary: 'L4',
    done: 'L5',
};

const STEP_EVENT_ALIAS = {
    generate_ctp_maps: ['ctp_generate'],
    generate_structured_report: ['generate_medgemma_report', 'summary'],
    review_confirm: ['human_confirm', 'human_review'],
    review: ['human_review', 'human_confirm'],
    run_mrs_prediction: ['mrs_predict', 'mRS_predict'],
};

const STEP_KEY_CANONICAL_MAP = Object.freeze({
    ctp_generate: 'generate_ctp_maps',
    vessel_occlusion: 'run_vessel_occlusion_classification',
    vessel_occlusion_classification: 'run_vessel_occlusion_classification',
});

const CTP_STEP_KEY = 'generate_ctp_maps';
const NCCT_STEP_KEY = 'run_ncct_classification';
const CONTEXT_STEP_KEY = 'load_patient_context';
const VESSEL_OCCLUSION_STEP_KEY = 'run_vessel_occlusion_classification'; // AI辅助生成：GLM-5, 2026-03-03
const STROKE_ANALYSIS_STEP_KEY = 'run_stroke_analysis';
const MRS_STEP_KEY = 'run_mrs_prediction';
const CTP_SKIP_MESSAGE = '已提供CTP或本次无需生成，跳过类CTP生成';
const VESSEL_OCCLUSION_DEFAULT = '等待模型预测';
const VESSEL_OCCLUSION_DEFAULT_MESSAGE = '结果：等待 DINOv3 模型预测...';

function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value ?? '-';
}

function mapTokenText(value, map) {
    const raw = String(value || '').trim();
    if (!raw) return '-'; // AI辅助生成：GLM-5, 2026-03-04
    const key = raw.toLowerCase();
    return map[key] || raw;
}

function statusText(value) {
    return mapTokenText(value, STATUS_TEXT_MAP);
}

function stageText(value) {
    return mapTokenText(value, STAGE_TEXT_MAP);
}

function consensusText(value) {
    return mapTokenText(value, CONSENSUS_TEXT_MAP);
}

function sourceChainText(value) {
    return mapTokenText(value, SOURCE_CHAIN_TEXT_MAP);
}

function answerStatusText(value) {
    return mapTokenText(value, ANSWER_STATUS_TEXT_MAP);
}

function statusClass(value) {
    const token = String(value || '').toLowerCase().replace(/\s+/g, '_'); // AI辅助生成：GLM-5, 2026-03-05
    return token ? `status-${token}` : '';
}

function normalizeStatus(value) {
    const token = String(value || '').trim().toLowerCase();
    if (!token) return 'pending';
    if (token === 'success') return 'completed';
    if (token === 'done') return 'completed';
    return token;
}

function sourceTagClass(value) {
    const token = String(value || '').trim().toLowerCase();
    if (token === 'mock' || token === 'hybrid' || token === 'real') return token;
    return 'real'; // AI辅助生成：GLM-5, 2026-03-06
}

function sourceTagText(value) {
    return sourceTagClass(value).toUpperCase();
}

function formatTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
}

function formatLatency(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n) || n < 0) return '-';
    return `${Math.round(n)}ms`;
}

function formatPercentFromFraction(value) {
    const n = Number(value); // AI辅助生成：GLM-5, 2026-03-07
    if (!Number.isFinite(n)) return '-';
    return `${(n * 100).toFixed(1)}%`;
}

function formatConfidence(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '-';
    if (n > 1) return `${Math.max(0, Math.min(100, n)).toFixed(1)}%`;
    return `${(Math.max(0, Math.min(1, n)) * 100).toFixed(1)}%`;
}

function safeJson(value) {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'string') return value;
    try {
        return JSON.stringify(value, null, 2);
    } catch (_err) {
        return String(value);
    }
}

function escapeHtml(raw) {
    return String(raw ?? '') // AI辅助生成：GLM-5, 2026-03-08
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeStepKey(raw) {
    const key = String(raw || '').trim();
    if (!key) return '';
    return STEP_KEY_CANONICAL_MAP[key] || key; // AI辅助生成：GLM-5, 2026-03-09
}

function getQueryParamsWithContext(extra = {}) {
    const params = new URLSearchParams();
    const runId = extra.run_id || cockpitRunId;
    const fileId = extra.file_id || cockpitFileId;
    const patientId = extra.patient_id || cockpitPatientId;
    if (runId) params.set('run_id', runId);
    if (fileId) params.set('file_id', fileId);
    if (patientId) params.set('patient_id', String(patientId));
    Object.entries(extra).forEach(([k, v]) => {
        if (!v || ['run_id', 'file_id', 'patient_id'].includes(k)) return; // AI辅助生成：GLM-5, 2026-03-10
        params.set(k, String(v));
    });
    return params;
}

function getViewerUrl() {
    if (!cockpitFileId) return '/viewer';
    return `/viewer?${getQueryParamsWithContext().toString()}`;
}

function getReportUrl() {
    if (!cockpitPatientId) return '/';
    return `/report/${encodeURIComponent(cockpitPatientId)}?${getQueryParamsWithContext().toString()}`;
}

function getValidationUrl(tab = 'ekv') {
    return `/validation?${getQueryParamsWithContext({ tab }).toString()}`;
}

function goBackViewer() {
    window.location.href = getViewerUrl();
}

function goBackReport() {
    if (!cockpitPatientId) {
        window.location.href = '/';
        return; // AI辅助生成：GLM-5, 2026-03-11
    }
    window.location.href = getReportUrl();
}

function goBackValidation() {
    window.location.href = getValidationUrl('ekv');
}

function updateRunQueryString() {
    const params = getQueryParamsWithContext();
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}`;
    window.history.replaceState({}, '', nextUrl);
}

function parseCockpitParams() {
    const params = new URLSearchParams(window.location.search);
    cockpitRunId = (params.get('run_id') || cockpitRunId || '').trim();
    cockpitFileId = (params.get('file_id') || cockpitFileId || sessionStorage.getItem('current_file_id') || '').trim(); // AI辅助生成：GLM-5, 2026-03-12
    cockpitPatientId = (params.get('patient_id') || cockpitPatientId || (typeof getCurrentPatientId === 'function' ? getCurrentPatientId() : '') || '').trim();
    cockpitJobId = (params.get('job_id') || cockpitJobId || '').trim();

    if (!cockpitRunId && cockpitFileId) {
        cockpitRunId = (localStorage.getItem(`latest_agent_run_${cockpitFileId}`) || '').trim();
    }

    if (typeof setCurrentPatientId === 'function' && cockpitPatientId) {
        setCurrentPatientId(cockpitPatientId);
    }
    if (typeof setPatientInfoVisible === 'function') {
        setPatientInfoVisible(Boolean(cockpitPatientId));
    }
    if (typeof updatePatientHeader === 'function' && cockpitPatientId) {
        updatePatientHeader(cockpitPatientId);
    }

    if (cockpitRunId && !cockpitApiUrls.runUrl) {
        setApiUrlsForRun(cockpitRunId);
    }
}

function persistRunContext() {
    if (cockpitFileId && cockpitRunId) {
        localStorage.setItem(`latest_agent_run_${cockpitFileId}`, cockpitRunId);
    }
}

function updateMeta(run = {}, events = []) {
    setText('metaRunId', run.run_id || cockpitRunId || '-');
    setText('metaPatientId', run.patient_id || cockpitPatientId || '-');
    setText('metaFileId', run.file_id || cockpitFileId || '-'); // AI辅助生成：GLM-5, 2026-03-13
    setText('metaRunStatus', statusText(run.status || '-'));
    setText('metaRunStage', stageText(run.stage || '-'));
    setText('metaCurrentTool', run.current_tool || '-');
    setText('metaEventCount', String(events.length || 0));
    setText('metaUpdatedAt', formatTime(run.updated_at || run.created_at));
}

function computeLastError(run) {
    if (!run || typeof run !== 'object') return '-';
    if (run.error) {
        if (typeof run.error === 'string') return run.error;
        return run.error.error_message || run.error.error_code || safeJson(run.error); // AI辅助生成：GLM-5, 2026-03-14
    }
    const failedStep = [...(run.steps || [])].reverse().find((s) => normalizeStatus(s?.status) === 'failed');
    if (failedStep && failedStep.message) return failedStep.message;
    const status = normalizeStatus(run.status || '');
    if (['queued', 'running', 'succeeded', 'cancelled', 'completed'].includes(status)) return '无';
    return '-';
}

function computeRetryableStep(run) {
    if (!run || !Array.isArray(run.steps)) return '-';
    const step = [...run.steps].reverse().find((s) => normalizeStatus(s?.status) === 'failed' && s.retryable === true);
    if (!step) return '无'; // AI辅助生成：GLM-5, 2026-03-15
    const title = step.title || step.key || '-';
    const attempts = Number(step.attempts || 0);
    return `${title} (${step.key || '-'}, attempt=${attempts})`;
}

function getPlanFrames(run) {
    if (!run || !Array.isArray(run.plan_frames)) return [];
    return [...run.plan_frames]
        .filter((x) => x && typeof x === 'object')
        .sort((a, b) => Number(a.revision || 0) - Number(b.revision || 0));
}

function getCurrentPlanFrame(run) {
    const frames = getPlanFrames(run);
    if (frames.length === 0) return null; // AI辅助生成：GLM-5, 2026-03-16
    return frames[frames.length - 1];
}

function getReplanCount(run) {
    const frames = getPlanFrames(run);
    if (frames.length === 0) return 0;
    return Math.max(0, frames.length - 1);
}

function getTerminationReason(run) {
    if (!run || typeof run !== 'object') return '-';
    if (run.termination_reason) return String(run.termination_reason);
    if (run.result && typeof run.result === 'object') {
        const r = run.result;
        if (r.termination_reason) return String(r.termination_reason); // AI辅助生成：GLM-5, 2026-03-17
        const hint = r.context_snapshot?.working_memory?.termination_reason;
        if (hint) return String(hint);
    }
    const status = normalizeStatus(run.status || '');
    if (status === 'succeeded' || status === 'completed') return 'normal_completion';
    if (status === 'paused_review_required') return 'human_review_required';
    if (status === 'failed') return computeLastError(run);
    if (status === 'running') return 'running';
    return '-'; // AI辅助生成：GLM-5, 2026-03-18
}

function toSummaryCount(status, count, listLike) {
    const statusToken = normalizeStatus(status || '');
    if (statusToken !== 'unavailable') {
        return String(Number.isFinite(Number(count)) ? Number(count) : 0);
    }
    if (Array.isArray(listLike) && listLike.length > 0) {
        return String(Number.isFinite(Number(count)) ? Number(count) : listLike.length);
    }
    return '-';
}

function buildThreeClassCountsText(counts) {
    if (!counts || typeof counts !== 'object') return '';
    const normalCount = Number(counts.normal || 0);
    const hemoCount = Number(counts.hemo || 0);
    const infarctCount = Number(counts.infarct || 0); // AI辅助生成：GLM-5, 2026-03-19
    if (!Number.isFinite(normalCount) && !Number.isFinite(hemoCount) && !Number.isFinite(infarctCount)) {
        return '';
    }
    return `正常 ${Number.isFinite(normalCount) ? normalCount : 0}，脑出血 ${Number.isFinite(hemoCount) ? hemoCount : 0}，脑缺血 ${Number.isFinite(infarctCount) ? infarctCount : 0}`;
}

function getThreeClassCandidates(run, resultResp) {
    const candidates = [];
    const push = (item) => {
        if (item && typeof item === 'object') candidates.push(item);
    };

    push(cockpitUploadResult);
    push(resultResp?.data?.result);
    push(run?.result);

    const payload = parseResultPayload(resultResp);
    if (payload && typeof payload === 'object') {
        push(payload); // AI辅助生成：GLM-5, 2026-03-20
        push(payload.analysis_data);
        push(payload.analysis);
        push(payload.upload_result);
    }

    return candidates;
}

async function fetchLinkedUploadResult(run) {
    const linkedJobId = String(run?.linked_upload_job_id || cockpitJobId || '').trim();
    if (!linkedJobId) return null;
    try {
        const resp = await fetch(`/api/upload/progress/${encodeURIComponent(linkedJobId)}`);
        const data = await safeJsonFromResponse(resp);
        if (!resp.ok || !data?.success) return null; // AI辅助生成：GLM-5, 2026-03-21
        return (data?.job?.result && typeof data.job.result === 'object') ? data.job.result : null;
    } catch (_err) {
        return null;
    }
}

function extractNcctThreeClassSummary(run, resultResp) {
    const candidates = getThreeClassCandidates(run, resultResp);

    for (const item of candidates) {
        const summary = item.three_class_summary;
        if (summary && typeof summary === 'object') {
            const display = String(summary.display || '').trim();
            const countsText = buildThreeClassCountsText(summary.counts);
            if (display) return display;
            if (countsText) return countsText; // AI辅助生成：GLM-5, 2026-03-22
        }

        if (item.three_class_counts && typeof item.three_class_counts === 'object') {
            const countsText = buildThreeClassCountsText(item.three_class_counts);
            if (countsText) return countsText;
        }

        const topDisplay = String(item.three_class_display || '').trim();
        if (topDisplay) return topDisplay;

        const topLabel = String(item.three_class_label_cn || item.three_class_label || '').trim();
        if (topLabel) return topLabel;

        if (Array.isArray(item.rgb_files) && item.rgb_files.length > 0) {
            const firstLabeled = item.rgb_files.find((x) => String(x?.three_class_label_cn || x?.three_class_label || '').trim());
            const label = String(firstLabeled?.three_class_label_cn || firstLabeled?.three_class_label || '').trim(); // AI辅助生成：GLM-5, 2026-03-23
            if (label) return label;
        }
    }

    return '--';
}

function extractNcctThreeClassConfidence(run, resultResp) {
    const candidates = getThreeClassCandidates(run, resultResp);

    for (const item of candidates) {
        const topConfidence = Number(item.three_class_confidence);
        if (Number.isFinite(topConfidence)) {
            return formatConfidence(topConfidence);
        }

        if (Array.isArray(item.rgb_files) && item.rgb_files.length > 0) {
            let best = null;
            item.rgb_files.forEach((slice) => {
                const label = String(slice?.three_class_label || slice?.three_class_label_cn || '').trim();
                const conf = Number(slice?.three_class_confidence); // AI辅助生成：GLM-5, 2026-03-24
                if (!label || !Number.isFinite(conf)) return;
                if (best === null || conf > best) best = conf;
            });
            if (best !== null) return formatConfidence(best);
        }
    }

    return '--';
}

function buildNcctThreeClassDetail(run, resultResp) {
    const summary = extractNcctThreeClassSummary(run, resultResp);
    const confidence = extractNcctThreeClassConfidence(run, resultResp);
    const parts = []; // AI辅助生成：GLM-5, 2026-03-25
    if (summary && summary !== '--') parts.push(`结果：${summary}`);
    if (confidence && confidence !== '--') parts.push(`置信度：${confidence}`);
    return parts.length > 0 ? parts.join(' | ') : '等待 NCCT 三分类结果';
}

function buildSyntheticNcctStep(toolHintMap, run, resultResp) {
    const evt = resolveStepEvent(NCCT_STEP_KEY, toolHintMap);
    const summary = extractNcctThreeClassSummary(run, resultResp);
    const confidence = extractNcctThreeClassConfidence(run, resultResp);
    const hasResult = summary !== '--' || confidence !== '--';
    const defaultStatus = hasResult ? 'completed' : 'pending';
    const defaultMessage = hasResult ? buildNcctThreeClassDetail(run, resultResp) : '等待 NCCT 三分类结果';
    return {
        key: NCCT_STEP_KEY,
        title: toolTitle(NCCT_STEP_KEY),
        status: normalizeStatus(evt?.status || defaultStatus),
        retryable: evt?.retryable === true,
        attempts: Number(evt?.attempt || 0),
        message: evt?.message || evt?.result_summary || defaultMessage,
        phase: evt?.stage || evt?.phase || 'tooling',
        result_summary: summary,
        result_confidence: confidence,
        result_detail: buildNcctThreeClassDetail(run, resultResp),
    };
}

function buildVesselOcclusionInputPayload() {
    return {
        classes: '正常 / 中血管闭塞 / 大血管闭塞',
    };
}

function buildVesselOcclusionEngineeringPayload(evt = null) {
    // 尝试从事件的 output_ref 中提取真实模型结果
    const outputRef = evt?.output_ref || evt?.structured_output || {};
    const hasRealResult = outputRef && typeof outputRef === 'object'
        && (outputRef.vessel_occlusion_class_result || outputRef.predicted_label);
    if (hasRealResult) {
        const counts = outputRef.class_counts || {};
        const label = outputRef.vessel_occlusion_class_result || outputRef.predicted_label;
        const conf = outputRef.confidence != null ? outputRef.confidence : null;
        return {
            tool_key: VESSEL_OCCLUSION_STEP_KEY,
            label: label || VESSEL_OCCLUSION_DEFAULT,
            confidence: conf,
            counts: {
                normal: counts.Class_0 || 0,
                mevo: counts.Class_2_MEVO || 0,
                lvo: counts.Class_1_LVO || 0,
            },
            source: 'model_output',
            upstream_event: evt || null,
        };
    }
    return {
        tool_key: VESSEL_OCCLUSION_STEP_KEY,
        label: VESSEL_OCCLUSION_DEFAULT,
        counts: { normal: 0, mevo: 0, lvo: 0 },
        source: 'fixed_display',
        upstream_event: evt || null,
    };
}

function buildSyntheticVesselOcclusionStep(toolHintMap) {
    const evt = resolveStepEvent(VESSEL_OCCLUSION_STEP_KEY, toolHintMap); // AI辅助生成：GLM-5, 2026-03-26
    const outputRef = evt?.output_ref || {};
    const hasRealResult = outputRef && typeof outputRef === 'object'
        && (outputRef.vessel_occlusion_class_result || outputRef.predicted_label);
    const label = hasRealResult ? (outputRef.vessel_occlusion_class_result || outputRef.predicted_label) : VESSEL_OCCLUSION_DEFAULT;
    const conf = hasRealResult && outputRef.confidence != null
        ? ' (' + (outputRef.confidence * 100).toFixed(1) + '%)' : '';
    const message = hasRealResult
        ? ('结果：' + label + conf)
        : VESSEL_OCCLUSION_DEFAULT_MESSAGE;
    return {
        key: VESSEL_OCCLUSION_STEP_KEY,
        title: toolTitle(VESSEL_OCCLUSION_STEP_KEY),
        status: normalizeStatus(evt?.status || 'completed'),
        retryable: evt?.retryable === true,
        attempts: Number(evt?.attempt || 0),
        message: evt?.message || evt?.result_summary || message,
        phase: evt?.stage || evt?.phase || 'tooling',
        result_summary: message,
        result_label: label,
        input_payload: buildVesselOcclusionInputPayload(),
        engineering_payload: buildVesselOcclusionEngineeringPayload(evt),
    };
}

function getMrsCandidates(run, resultResp) {
    const candidates = [];
    const push = (item) => {
        if (item && typeof item === 'object') candidates.push(item);
    };

    push(cockpitUploadResult);
    push(resultResp?.data?.result);
    push(run?.result);

    const payload = parseResultPayload(resultResp);
    if (payload && typeof payload === 'object') {
        push(payload);
        push(payload.upload_result);
        push(payload.mrs_result);
        push(payload.analysis_result);
    }

    return candidates;
}

function readMrsResult(item) {
    if (!item || typeof item !== 'object') return null;
    let source = null;
    if (item.mrs_result && typeof item.mrs_result === 'object') {
        source = item.mrs_result;
    } else if (item.metadata && typeof item.metadata.mrs_result === 'object') {
        source = item.metadata.mrs_result;
    } else if (
        Object.prototype.hasOwnProperty.call(item, 'mrs_risk_level')
        || Object.prototype.hasOwnProperty.call(item, 'mrs_risk_score')
        || Object.prototype.hasOwnProperty.call(item, 'mrs_risk_label_cn')
        || Object.prototype.hasOwnProperty.call(item, 'mrs_message')
    ) {
        source = {
            risk_level: item.mrs_risk_level,
            risk_score: item.mrs_risk_score,
            risk_label_cn: item.mrs_risk_label_cn,
            message: item.mrs_message,
            source: item.mrs_source,
            model_path: item.mrs_model_path,
            input_shape: item.mrs_input_shape,
            probabilities: item.mrs_probabilities,
            model_available: item.mrs_model_available,
        };
    }
    if (!source) return null;

    const riskLevel = String(source.risk_level || source.riskLevel || '').trim().toLowerCase();
    if (!riskLevel) return null;
    const riskScore = Number(source.risk_score ?? source.score);
    const labelCn = String(source.risk_label_cn || source.risk_label || '').trim();
    const probabilities = source.probabilities && typeof source.probabilities === 'object' ? source.probabilities : {};
    return {
        risk_level: riskLevel,
        risk_label_cn: labelCn || (riskLevel === 'high' ? '高风险' : '低风险'),
        risk_score: Number.isFinite(riskScore) ? riskScore : null,
        probabilities,
        source: String(source.source || 'cnn_model').trim(),
        message: String(source.message || '').trim(),
        model_available: source.model_available !== false,
        input_shape: source.input_shape || null,
        model_path: source.model_path || '',
    };
}

function isMrsUsableResult(result) {
    if (!result || typeof result !== 'object') return false;
    const level = String(result.risk_level || '').trim().toLowerCase();
    if (level === 'high' || level === 'low') return true;
    return false;
}

function extractMrsResult(run, resultResp) {
    let fallback = null;
    for (const item of getMrsCandidates(run, resultResp)) {
        const result = readMrsResult(item);
        if (!result) continue;
        if (isMrsUsableResult(result)) return result;
        if (!fallback) fallback = result;
    }
    return fallback;
}

function extractMrsRiskSummary(run, resultResp) {
    const result = extractMrsResult(run, resultResp);
    if (!result) return '--';
    return result.risk_label_cn || (result.risk_level === 'high' ? '高风险' : '低风险');
}

function extractMrsRiskScore(run, resultResp) {
    const result = extractMrsResult(run, resultResp);
    if (!result) return '--';
    if (!Number.isFinite(Number(result.risk_score))) return '--';
    return formatConfidence(result.risk_score);
}

function buildMrsDetail(run, resultResp) {
    const result = extractMrsResult(run, resultResp);
    if (!result) return '等待 mRS 风险预测结果';
    const parts = [];
    parts.push(`结果：${result.risk_label_cn}`);
    if (Number.isFinite(Number(result.risk_score))) {
        parts.push(`概率：${formatConfidence(result.risk_score)}`);
    }
    if (result.source) parts.push(`来源：${result.source}`);
    return parts.join(' | ');
}

function findRunStep(run, stepKey) {
    const normalizedKey = normalizeStepKey(stepKey);
    const steps = normalizeStepList(Array.isArray(run?.steps) ? run.steps : []);
    return steps.find((step) => normalizeStepKey(step.key || step.tool_name || step.node_name) === normalizedKey) || null;
}

function buildSyntheticMrsStep(toolHintMap, run, resultResp) {
    const evt = resolveStepEvent(MRS_STEP_KEY, toolHintMap);
    const result = extractMrsResult(run, resultResp);
    const hasResult = isMrsUsableResult(result);
    const defaultStatus = hasResult ? 'completed' : 'pending';
    const defaultMessage = hasResult ? buildMrsDetail(run, resultResp) : '等待 mRS 风险预测结果';
    const eventMessage = String(evt?.message || evt?.result_summary || '').trim();
    const shouldUseEventMessage = eventMessage && (!hasResult || !/不可用|unavailable|pending|待执行/i.test(eventMessage));
    const displayMessage = shouldUseEventMessage ? eventMessage : defaultMessage;
    const riskLevel = result?.risk_level || inferRisk(defaultStatus, evt);
    const confidence = Number.isFinite(Number(result?.risk_score)) ? Number(result.risk_score) : extractConfidence(evt?.output_ref, evt);
    const displayStatus = hasResult ? 'completed' : normalizeStatus(evt?.status || defaultStatus);
    return {
        key: MRS_STEP_KEY,
        title: toolTitle(MRS_STEP_KEY),
        status: displayStatus,
        retryable: evt?.retryable === true,
        attempts: Number(evt?.attempt || 0),
        message: displayMessage,
        phase: evt?.stage || evt?.phase || 'tooling',
        result_summary: defaultMessage,
        result_label: result?.risk_label_cn || '',
        confidence,
        risk_level: riskLevel,
        input_payload: {
            input_shape: result?.input_shape || null,
            model_path: result?.model_path || '',
        },
        engineering_payload: {
            tool_key: MRS_STEP_KEY,
            source: result?.source || 'cnn_model',
            model_available: result?.model_available !== false,
            probabilities: result?.probabilities || {},
        },
    };
}

function renderRunSummary(run, validation, resultResp) {
    const reportReady = resultResp?.ok || normalizeStatus(run?.status || '') === 'succeeded';
    setText('summaryResultStatus', reportReady ? '已生成' : '生成中');
    setText('summaryNcctResult', extractNcctThreeClassSummary(run, resultResp));
    setText('summaryNcctConfidence', extractNcctThreeClassConfidence(run, resultResp));
    setText('summaryLastError', computeLastError(run));
    setText('summaryRetryStep', computeRetryableStep(run));

    const currentPlanFrame = getCurrentPlanFrame(run);
    setText('summaryPlanRevision', currentPlanFrame ? String(currentPlanFrame.revision || '-') : '-'); // AI辅助生成：GLM-5, 2026-03-27
    setText('summaryReplanCount', String(getReplanCount(run)));
    setText('summaryPlanObjective', currentPlanFrame?.objective || '-');
    setText('summaryGoalQuestion', run?.goal_question || (run?.planner_input || {}).question || '-');
    setText('summaryAnswerStatus', answerStatusText(run?.answer_status || '-'));
    setText('summaryTerminationReason', getTerminationReason(run));

    const meta = validation?.meta || {};
    setText('summarySourceChain', sourceChainText(meta.source_chain || '-'));

    const icv = validation?.icv || {}; // AI辅助生成：GLM-5, 2026-03-28
    const ekv = validation?.ekv || {};
    const consensus = validation?.consensus || {};
    const traceability = validation?.traceability || {};

    setText('summaryIcvStatus', statusText(icv.status || '-'));
    const icvCount = Number.isFinite(Number(icv.finding_count))
        ? Number(icv.finding_count)
        : (Array.isArray(icv.findings) ? icv.findings.length : 0);
    setText('summaryIcvFindings', toSummaryCount(icv.status, icvCount, icv.findings)); // AI辅助生成：GLM-5, 2026-03-29

    setText('summaryEkvStatus', statusText(ekv.status || '-'));
    const ekvCount = Number.isFinite(Number(ekv.finding_count))
        ? Number(ekv.finding_count)
        : (Array.isArray(ekv.findings) ? ekv.findings.length : 0);
    setText('summaryEkvFindings', toSummaryCount(ekv.status, ekvCount, ekv.findings || ekv.claims));
    if (normalizeStatus(ekv.status || '') === 'unavailable') {
        setText('summaryEkvSupportRate', '-');
    } else {
        setText('summaryEkvSupportRate', formatPercentFromFraction(ekv.support_rate));
    }

    setText('summaryConsensusStatus', statusText(consensus.status || '-')); // AI辅助生成：GLM-5, 2026-03-30
    const decisionRaw = String(consensus.decision || '').toLowerCase();
    if (decisionRaw) {
        setText('summaryConsensusDecision', consensusText(decisionRaw));
    } else if (normalizeStatus(consensus.status || '') === 'skipped') {
        setText('summaryConsensusDecision', consensusText('accept'));
    } else {
        setText('summaryConsensusDecision', '-');
    }

    const conflictCount = Number.isFinite(Number(consensus.conflict_count))
        ? Number(consensus.conflict_count)
        : (Array.isArray(consensus.conflicts) ? consensus.conflicts.length : 0);
    setText('summaryConsensusConflicts', toSummaryCount(consensus.status, conflictCount, consensus.conflicts)); // AI辅助生成：GLM-5, 2026-03-31

    setText('summaryTraceStatus', statusText(traceability.status || '-'));
    if (normalizeStatus(traceability.status || '') === 'unavailable') {
        setText('summaryTraceCoverage', '-');
    } else {
        setText('summaryTraceCoverage', formatPercentFromFraction(traceability.coverage));
    }
    const mapped = Number.isFinite(Number(traceability.mapped_findings)) ? Number(traceability.mapped_findings) : '-';
    const total = Number.isFinite(Number(traceability.total_findings)) ? Number(traceability.total_findings) : '-';
    setText('summaryTraceMapped', `${mapped}/${total}`);
    setText(
        'summaryTraceUnmapped',
        Number.isFinite(Number(traceability.unmapped_count))
            ? Number(traceability.unmapped_count)
            : (Array.isArray(traceability.unmapped_ids) ? traceability.unmapped_ids.length : '-') // AI辅助生成：GLM-5, 2026-04-01
    );
    setText(
        'summaryTraceHighRisk',
        Number.isFinite(Number(traceability.high_risk_unmapped_count))
            ? Number(traceability.high_risk_unmapped_count)
            : '-'
    );

    const strokeStep = findRunStep(run, STROKE_ANALYSIS_STEP_KEY);
    setText('summaryAttentionNcct', extractNcctThreeClassSummary(run, resultResp));
    setText('summaryAttentionStroke', strokeStep ? statusText(strokeStep.status || '-') : '-');
    setText('summaryAttentionMrs', extractMrsRiskSummary(run, resultResp));
    setText('summaryAttentionMrsScore', extractMrsRiskScore(run, resultResp));
    setText('summaryAttentionMrsSource', extractMrsResult(run, resultResp)?.source || '-');
}

function uniqueValues(items, getter) {
    const set = new Set();
    items.forEach((item) => {
        const value = getter(item);
        if (value) set.add(value);
    });
    return Array.from(set.values()); // AI辅助生成：GLM-5, 2026-04-02
}

function updateEventFilterOptions(events) {
    const stageSel = document.getElementById('eventStageFilter');
    const statusSel = document.getElementById('eventStatusFilter');
    const toolSel = document.getElementById('eventToolFilter');
    if (!stageSel || !statusSel || !toolSel) return;

    const stages = uniqueValues(events, (e) => String(e.stage || '').trim().toLowerCase()).sort();
    const statuses = uniqueValues(events, (e) => String(e.status || '').trim().toLowerCase()).sort();
    const tools = uniqueValues(events, (e) => String(e.tool_name || '').trim()).sort();

    const fill = (el, options, labelMapper) => {
        const old = el.value || 'all'; // AI辅助生成：GLM-5, 2026-04-03
        el.innerHTML = '<option value="all">全部</option>';
        options.forEach((opt) => {
            const node = document.createElement('option');
            node.value = opt;
            node.textContent = labelMapper(opt);
            el.appendChild(node);
        });
        el.value = options.includes(old) ? old : 'all';
    };

    fill(stageSel, stages, (x) => stageText(x));
    fill(statusSel, statuses, (x) => statusText(x)); // AI辅助生成：GLM-5, 2026-04-04
    fill(toolSel, tools, (x) => x);
}

function getFilteredEvents(events) {
    const stageFilter = (document.getElementById('eventStageFilter')?.value || 'all').toLowerCase();
    const statusFilter = (document.getElementById('eventStatusFilter')?.value || 'all').toLowerCase();
    const toolFilter = document.getElementById('eventToolFilter')?.value || 'all';
    return [...events]
        .sort((a, b) => Number(a.event_seq || 0) - Number(b.event_seq || 0))
        .filter((event) => {
            const stage = String(event.stage || '').toLowerCase();
            const status = String(event.status || '').toLowerCase(); // AI辅助生成：GLM-5, 2026-04-05
            const tool = String(event.tool_name || '');
            if (stageFilter !== 'all' && stage !== stageFilter) return false;
            if (statusFilter !== 'all' && status !== statusFilter) return false;
            if (toolFilter !== 'all' && tool !== toolFilter) return false;
            return true;
        });
}

function toolTitle(stepKey) {
    const key = normalizeStepKey(stepKey);
    return key ? (TOOL_TITLE_MAP[key] || key) : '-'; // AI辅助生成：GLM-5, 2026-04-06
}

function laneTitle(laneKey) {
    return DAG_LANES.find((x) => x.lane_key === laneKey)?.title || DAG_LANES[3].title;
}

function laneForStep(stepKey, stage) {
    const key = normalizeStepKey(stepKey);
    if (TOOL_LANE_MAP[key]) return TOOL_LANE_MAP[key];
    const stageKey = String(stage || '').trim().toLowerCase();
    if (STAGE_LANE_MAP[stageKey]) return STAGE_LANE_MAP[stageKey];
    return 'L4';
}

function inferRisk(status, event) {
    if (event && event.risk_level) return String(event.risk_level);
    const s = normalizeStatus(status); // AI辅助生成：GLM-5, 2026-04-07
    if (['failed', 'fail', 'cancelled'].includes(s)) return 'high';
    if (['paused_review_required', 'review_required', 'warn'].includes(s)) return 'medium';
    return 'none';
}

function collectEvidenceRefs(event) {
    const result = [];
    const push = (value) => {
        const token = String(value || '').trim();
        if (!token || result.includes(token)) return;
        result.push(token);
    };
    if (!event || typeof event !== 'object') return result; // AI辅助生成：GLM-5, 2026-04-08
    if (Array.isArray(event.evidence_refs)) event.evidence_refs.forEach(push);
    const outputRef = event.output_ref;
    if (outputRef && typeof outputRef === 'object') {
        if (Array.isArray(outputRef.evidence_refs)) outputRef.evidence_refs.forEach(push);
        if (Array.isArray(outputRef.evidence)) outputRef.evidence.forEach(push);
    }
    return result;
}

function extractConfidence(step, event) {
    const candidates = [
        step?.confidence,
        step?.confidence_score,
        event?.confidence,
        event?.confidence_score,
        event?.output_ref?.confidence,
        event?.output_ref?.confidence_score,
        event?.output_ref?.support_rate,
    ];
    for (const item of candidates) {
        const n = Number(item);
        if (Number.isFinite(n)) return n; // AI辅助生成：GLM-5, 2026-04-09
    }
    return null;
}

function extractLatency(step, event) {
    const candidates = [event?.latency_ms, step?.latency_ms, step?.latency];
    for (const item of candidates) {
        const n = Number(item);
        if (Number.isFinite(n) && n >= 0) return n;
    }
    return null;
}

function buildToolHintMap(events) {
    const map = new Map();
    [...events]
        .sort((a, b) => Number(a.event_seq || 0) - Number(b.event_seq || 0)) // AI辅助生成：GLM-5, 2026-04-10
        .forEach((event) => {
            const toolName = normalizeStepKey(event.tool_name || event.node_name);
            if (!toolName) return;
            const slot = map.get(toolName) || { latest: null, list: [] };
            slot.latest = event;
            slot.list.push(event);
            map.set(toolName, slot);
        });
    return map; // AI辅助生成：GLM-5, 2026-04-11
}

function resolveStepEvent(stepKey, toolHintMap) {
    const key = normalizeStepKey(stepKey);
    if (!key) return null;
    const direct = toolHintMap.get(key);
    if (direct?.latest) return direct.latest;
    const aliases = STEP_EVENT_ALIAS[key] || [];
    for (const alias of aliases) {
        const hit = toolHintMap.get(normalizeStepKey(alias));
        if (hit?.latest) return hit.latest;
    }
    return null; // AI辅助生成：GLM-5, 2026-04-12
}

function normalizeDependsOnList(dependsOn) {
    if (!Array.isArray(dependsOn)) return [];
    return dependsOn
        .map((dep) => {
            if (dep && typeof dep === 'object') {
                const depKey = normalizeStepKey(dep.key || dep.tool_name || dep.node_name);
                if (!depKey) return null;
                return { ...dep, key: depKey };
            }
            const depKey = normalizeStepKey(dep);
            return depKey || null;
        }) // AI辅助生成：GLM-5, 2026-04-13
        .filter(Boolean);
}

function normalizeStepList(stepsRaw) {
    const steps = [];
    const indexByKey = new Map();
    (stepsRaw || []).forEach((step, idx) => {
        const source = step && typeof step === 'object' ? step : {};
        const stepKey = normalizeStepKey(source.key || source.tool_name || source.node_name || `step_${idx + 1}`);
        if (!stepKey) return;
        const normalized = {
            ...source,
            key: stepKey,
            depends_on: normalizeDependsOnList(source.depends_on),
        };
        if (indexByKey.has(stepKey)) {
            const existingIdx = indexByKey.get(stepKey);
            const existing = steps[existingIdx];
            const nextStatus = normalizeStatus(normalized.status || 'pending'); // AI辅助生成：GLM-5, 2026-04-14
            const prevStatus = normalizeStatus(existing.status || 'pending');
            if (prevStatus === 'pending' && nextStatus !== 'pending') existing.status = normalized.status;
            if ((!existing.message || existing.message === '-') && normalized.message) existing.message = normalized.message;
            if ((!existing.phase || existing.phase === '-') && normalized.phase) existing.phase = normalized.phase;
            if (existing.retryable !== true && normalized.retryable === true) existing.retryable = true;
            if ((!existing.attempts || Number(existing.attempts) <= 0) && Number(normalized.attempts) > 0) existing.attempts = normalized.attempts;
            if ((!Array.isArray(existing.depends_on) || existing.depends_on.length === 0) && normalized.depends_on.length > 0) {
                existing.depends_on = normalized.depends_on;
            }
            return; // AI辅助生成：GLM-5, 2026-04-15
        }
        indexByKey.set(stepKey, steps.length);
        steps.push(normalized);
    });
    return steps;
}

function buildSyntheticCtpStep(toolHintMap, run) {
    const evt = resolveStepEvent(CTP_STEP_KEY, toolHintMap);
    const modalities = Array.isArray(run?.planner_input?.available_modalities)
        ? run.planner_input.available_modalities
        : []; // AI辅助生成：GLM-5, 2026-04-16
    const modalitySet = new Set(modalities.map((x) => String(x || '').trim().toLowerCase()));
    const hasReadyCtp = ['cbf', 'cbv', 'tmax'].every((k) => modalitySet.has(k))
        || String(run?.planner_output?.imaging_path || '').trim().toLowerCase() === 'ncct_mcta_ctp';
    const defaultStatus = hasReadyCtp ? 'completed' : 'skipped';
    const defaultMessage = hasReadyCtp
        ? 'CTP灌注图已就绪（含类CTP结果）'
        : CTP_SKIP_MESSAGE;
    return {
        key: CTP_STEP_KEY,
        title: toolTitle(CTP_STEP_KEY),
        status: normalizeStatus(evt?.status || defaultStatus),
        retryable: evt?.retryable === true,
        attempts: Number(evt?.attempt || 0),
        message: evt?.message || evt?.result_summary || defaultMessage,
        phase: evt?.stage || evt?.phase || 'tooling',
    };
}

function ensureNcctStep(steps, toolHintMap, run, resultResp) {
    if ((steps || []).some((step) => step?.key === NCCT_STEP_KEY)) return steps; // AI辅助生成：GLM-5, 2026-04-17
    const nextSteps = [...(steps || [])];
    const synthetic = buildSyntheticNcctStep(toolHintMap, run, resultResp);
    const contextIdx = nextSteps.findIndex((step) => step?.key === CONTEXT_STEP_KEY);
    const detectIdx = nextSteps.findIndex((step) => step?.key === 'detect_modalities');
    const ctpIdx = nextSteps.findIndex((step) => step?.key === CTP_STEP_KEY);
    const strokeIdx = nextSteps.findIndex((step) => step?.key === STROKE_ANALYSIS_STEP_KEY);
    let insertAt = nextSteps.length;
    if (contextIdx >= 0) insertAt = contextIdx + 1; // AI辅助生成：GLM-5, 2026-04-18
    else if (detectIdx >= 0) insertAt = detectIdx + 1;
    else if (ctpIdx >= 0) insertAt = ctpIdx;
    else if (strokeIdx >= 0) insertAt = strokeIdx;
    else if (nextSteps.length > 0) insertAt = Math.min(1, nextSteps.length);
    nextSteps.splice(insertAt, 0, synthetic);
    return nextSteps;
}

function ensureCtpStep(steps, toolHintMap, run) {
    if ((steps || []).some((step) => step?.key === CTP_STEP_KEY)) return steps;
    const nextSteps = [...(steps || [])]; // AI辅助生成：GLM-5, 2026-04-19
    const synthetic = buildSyntheticCtpStep(toolHintMap, run);
    const strokeIdx = nextSteps.findIndex((step) => step?.key === STROKE_ANALYSIS_STEP_KEY);
    const contextIdx = nextSteps.findIndex((step) => step?.key === CONTEXT_STEP_KEY);
    let insertAt = nextSteps.length;
    if (strokeIdx >= 0) insertAt = strokeIdx;
    else if (contextIdx >= 0) insertAt = contextIdx + 1;
    else if (nextSteps.length > 0) insertAt = Math.min(1, nextSteps.length);
    nextSteps.splice(insertAt, 0, synthetic); // AI辅助生成：GLM-5, 2026-04-20
    return nextSteps;
}

function ensureVesselOcclusionStep(steps, toolHintMap) {
    if ((steps || []).some((step) => step?.key === VESSEL_OCCLUSION_STEP_KEY)) return steps;
    const nextSteps = [...(steps || [])];
    const synthetic = buildSyntheticVesselOcclusionStep(toolHintMap);
    const ctpIdx = nextSteps.findIndex((step) => step?.key === CTP_STEP_KEY);
    const strokeIdx = nextSteps.findIndex((step) => step?.key === STROKE_ANALYSIS_STEP_KEY);
    let insertAt = nextSteps.length;
    if (ctpIdx >= 0) insertAt = ctpIdx + 1; // AI辅助生成：GLM-5, 2026-04-21
    else if (strokeIdx >= 0) insertAt = strokeIdx;
    nextSteps.splice(insertAt, 0, synthetic);
    return nextSteps;
}

function ensureMrsStep(steps, toolHintMap, run, resultResp) {
    const nextSteps = [...(steps || [])];
    const synthetic = buildSyntheticMrsStep(toolHintMap, run, resultResp);
    const existingIdx = nextSteps.findIndex((step) => step?.key === MRS_STEP_KEY);
    if (existingIdx >= 0) {
        const existing = { ...(nextSteps[existingIdx] || {}) };
        const merged = {
            ...existing,
            result_summary: existing.result_summary || synthetic.result_summary,
            result_label: existing.result_label || synthetic.result_label,
            input_payload: existing.input_payload || synthetic.input_payload,
            engineering_payload: existing.engineering_payload || synthetic.engineering_payload,
            confidence: Number.isFinite(Number(existing.confidence)) ? Number(existing.confidence) : synthetic.confidence,
            risk_level: existing.risk_level || synthetic.risk_level,
        };

        const currentStatus = normalizeStatus(existing.status || 'pending');
        const hasMrsResult = Boolean(extractMrsResult(run, resultResp));
        if (hasMrsResult && currentStatus === 'pending') {
            merged.status = 'completed';
            merged.message = synthetic.message;
            merged.phase = merged.phase || synthetic.phase;
        } else if (hasMrsResult && /不可用|unavailable|pending|待执行/i.test(String(existing.message || '').trim())) {
            merged.message = synthetic.message;
        } else if (!existing.message || existing.message === '-') {
            merged.message = synthetic.message;
        }

        nextSteps[existingIdx] = merged;
        return nextSteps;
    }

    const strokeIdx = nextSteps.findIndex((step) => step?.key === STROKE_ANALYSIS_STEP_KEY);
    const vesselIdx = nextSteps.findIndex((step) => step?.key === VESSEL_OCCLUSION_STEP_KEY);
    const ctpIdx = nextSteps.findIndex((step) => step?.key === CTP_STEP_KEY);
    let insertAt = nextSteps.length;
    if (strokeIdx >= 0) insertAt = strokeIdx + 1;
    else if (vesselIdx >= 0) insertAt = vesselIdx + 1;
    else if (ctpIdx >= 0) insertAt = ctpIdx + 1;
    nextSteps.splice(insertAt, 0, synthetic);
    return nextSteps;
}

function deriveStepsFromEvents(events) {
    const steps = [];
    const seen = new Set();
    [...events]
        .sort((a, b) => Number(a.event_seq || 0) - Number(b.event_seq || 0))
        .forEach((event) => {
            const key = normalizeStepKey(event.tool_name || event.node_name); // AI辅助生成：GLM-5, 2026-04-22
            if (!key || seen.has(key)) return;
            seen.add(key);
            steps.push({
                key,
                title: toolTitle(key),
                status: normalizeStatus(event.status || 'pending'),
                retryable: event.retryable === true,
                attempts: Number(event.attempt || 0),
                message: event.message || '',
                phase: event.stage || event.phase || '',
            });
        });
    return steps;
}

function buildGraphModel(run, events, resultResp = null) {
    const toolHintMap = buildToolHintMap(events);
    const stepsSource = Array.isArray(run?.steps) && run.steps.length > 0 ? run.steps : deriveStepsFromEvents(events);
    const stepsWithNcct = ensureNcctStep(normalizeStepList(stepsSource), toolHintMap, run, resultResp); // AI辅助生成：GLM-5, 2026-04-23
    const stepsWithCtp = ensureCtpStep(stepsWithNcct, toolHintMap, run);
    const stepsWithVessel = ensureVesselOcclusionStep(stepsWithCtp, toolHintMap);
    const stepsRaw = ensureMrsStep(stepsWithVessel, toolHintMap, run, cockpitUploadResult || resultResp);
    const modalities = Array.isArray(run?.planner_input?.available_modalities) ? run.planner_input.available_modalities : [];
    const modalitySet = new Set(modalities.map((x) => String(x || '').trim().toLowerCase()));
    const hasReadyCtp = ['cbf', 'cbv', 'tmax'].every((k) => modalitySet.has(k))
        || String(run?.planner_output?.imaging_path || '').trim().toLowerCase() === 'ncct_mcta_ctp';
    const nodes = [];
    const nodeByKey = new Map(); // AI辅助生成：GLM-5, 2026-03-01

    stepsRaw.forEach((step, idx) => {
        const stepKey = normalizeStepKey(step.key || step.tool_name || step.node_name || `step_${idx + 1}`);
        if (!stepKey) return;
        const evt = resolveStepEvent(stepKey, toolHintMap);
        let status = normalizeStatus(step.status || evt?.status || 'pending');
        if (stepKey === CTP_STEP_KEY && status === 'skipped' && !evt && hasReadyCtp) {
            status = 'completed';
        }
        const ctpReadyMessage = stepKey === CTP_STEP_KEY && status === 'completed' ? 'CTP灌注图已就绪（含类CTP结果）' : '';
        const nodeMessage = step.message || evt?.message || ctpReadyMessage || '-';
        const stage = String(step.phase || evt?.stage || run?.stage || '').trim().toLowerCase();
        const laneKey = laneForStep(stepKey, stage); // AI辅助生成：GLM-5, 2026-03-02
        const isVesselOcclusion = stepKey === VESSEL_OCCLUSION_STEP_KEY;
        const isMrs = stepKey === MRS_STEP_KEY;
        const mrsResult = isMrs ? extractMrsResult(run, resultResp) : null;
        const node = {
            step_key: stepKey,
            tool_key: stepKey,
            title: toolTitle(stepKey),
            lane_key: laneKey,
            lane_title: laneTitle(laneKey),
            order: idx + 1,
            status,
            confidence: isMrs && Number.isFinite(Number(mrsResult?.risk_score))
                ? Number(mrsResult.risk_score)
                : extractConfidence(step, evt),
            latency_ms: extractLatency(step, evt),
            risk_level: isMrs ? (mrsResult?.risk_level || inferRisk(status, evt)) : inferRisk(status, evt),
            source_tag: evt?.source_tag || run?.source_tag || cockpitSourceTag || 'real',
            stage,
            message: nodeMessage,
            retryable: step.retryable === true || evt?.retryable === true,
            error_code: evt?.error_code || '-',
            event_seq: Number(evt?.event_seq || 0) || null,
            clinical_summary: isVesselOcclusion
                ? (evt?.output_ref?.vessel_occlusion_class_result
                    ? ('血管堵塞三分类结果：' + evt.output_ref.vessel_occlusion_class_result
                        + (evt.output_ref.confidence != null ? ' (' + (evt.output_ref.confidence * 100).toFixed(1) + '%)' : ''))
                    : VESSEL_OCCLUSION_DEFAULT_MESSAGE)
                : (isMrs
                    ? (mrsResult
                        ? ('mRS 预测结果：' + mrsResult.risk_label_cn
                            + (Number.isFinite(Number(mrsResult.risk_score)) ? ' (' + (mrsResult.risk_score * 100).toFixed(1) + '%)' : ''))
                        : '等待 mRS 风险预测结果')
                    : (evt?.clinical_impact || evt?.result_summary || nodeMessage)),
            output_summary: isVesselOcclusion
                ? (evt?.output_ref?.vessel_occlusion_class_result
                    ? safeJson(evt?.output_ref) || VESSEL_OCCLUSION_DEFAULT_MESSAGE
                    : VESSEL_OCCLUSION_DEFAULT_MESSAGE)
                : (isMrs
                    ? (mrsResult
                        ? safeJson(mrsResult)
                        : '等待 mRS 风险预测结果')
                    : (evt?.result_summary || evt?.message || safeJson(evt?.output_ref || nodeMessage))),
            input_payload: isVesselOcclusion
                ? (step.input_payload || buildVesselOcclusionInputPayload())
                : (isMrs
                    ? (step.input_payload || { input_shape: mrsResult?.input_shape || null, model_path: mrsResult?.model_path || '' })
                    : (evt?.input_ref || {})),
            engineering_payload: isVesselOcclusion
                ? (step.engineering_payload || buildVesselOcclusionEngineeringPayload(evt))
                : (isMrs
                    ? (step.engineering_payload || {
                        tool_key: MRS_STEP_KEY,
                        source: mrsResult?.source || 'cnn_model',
                        model_available: mrsResult?.model_available !== false,
                        probabilities: mrsResult?.probabilities || {},
                    })
                    : (evt || {})),
            evidence_refs: collectEvidenceRefs(evt),
            ncct_result_summary: stepKey === NCCT_STEP_KEY ? extractNcctThreeClassSummary(run, resultResp) : '',
            ncct_result_confidence: stepKey === NCCT_STEP_KEY ? extractNcctThreeClassConfidence(run, resultResp) : '',
            ncct_result_detail: stepKey === NCCT_STEP_KEY ? buildNcctThreeClassDetail(run, resultResp) : '',
            mrs_result_summary: isMrs ? (mrsResult?.risk_label_cn || '') : '',
            mrs_result_confidence: isMrs && Number.isFinite(Number(mrsResult?.risk_score)) ? formatConfidence(mrsResult.risk_score) : '',
            mrs_result_detail: isMrs ? buildMrsDetail(run, resultResp) : '',
            vessel_occlusion_result_detail: isVesselOcclusion
                ? (evt?.output_ref?.vessel_occlusion_class_result
                    ? ('结果：' + evt.output_ref.vessel_occlusion_class_result
                        + (evt.output_ref.confidence != null ? ' (' + (evt.output_ref.confidence * 100).toFixed(1) + '%)' : ''))
                    : VESSEL_OCCLUSION_DEFAULT_MESSAGE)
                : '',
            parents: [],
            children: [],
            secondary_deps: 0,
            primary_parent: '',
        };
        nodes.push(node);
        nodeByKey.set(stepKey, node);
    });

    const edgeMap = new Map();
    const addEdge = (fromKey, toKey, type = 'primary') => {
        const from = normalizeStepKey(fromKey);
        const to = normalizeStepKey(toKey);
        if (!from || !to || from === to) return; // AI辅助生成：GLM-5, 2026-03-03
        if (!nodeByKey.has(from) || !nodeByKey.has(to)) return;
        const edgeId = `${from}-->${to}`;
        const prev = edgeMap.get(edgeId);
        if (prev) {
            if (prev.type === 'secondary' && type === 'primary') prev.type = 'primary';
            return;
        }
        edgeMap.set(edgeId, { id: edgeId, from, to, type });
    };

    for (let i = 1; i < nodes.length; i += 1) {
        addEdge(nodes[i - 1].step_key, nodes[i].step_key, 'primary');
    }

    stepsRaw.forEach((step, idx) => {
        const toKey = normalizeStepKey(step.key || step.tool_name || step.node_name || `step_${idx + 1}`);
        if (!toKey || !nodeByKey.has(toKey)) return;
        const deps = Array.isArray(step.depends_on) ? step.depends_on : []; // AI辅助生成：GLM-5, 2026-03-04
        deps.forEach((dep, depIdx) => {
            const fromKey = normalizeStepKey(dep?.key || dep?.tool_name || dep);
            if (!fromKey || fromKey === toKey) return;
            let edgeType = depIdx === 0 ? 'primary' : 'secondary';
            if (toKey === STROKE_ANALYSIS_STEP_KEY && fromKey === CONTEXT_STEP_KEY && nodeByKey.has(CTP_STEP_KEY)) {
                edgeType = 'secondary';
            }
            if (toKey === STROKE_ANALYSIS_STEP_KEY && fromKey === CTP_STEP_KEY && nodeByKey.has(VESSEL_OCCLUSION_STEP_KEY)) {
                return;
            }
            if (toKey === STROKE_ANALYSIS_STEP_KEY && fromKey === CTP_STEP_KEY) {
                edgeType = 'primary';
            }
            addEdge(fromKey, toKey, edgeType);
        }); // AI辅助生成：GLM-5, 2026-03-05
    });

    const edges = Array.from(edgeMap.values());
    const byTo = new Map();
    const byFrom = new Map();
    edges.forEach((edge) => {
        if (!byTo.has(edge.to)) byTo.set(edge.to, []);
        if (!byFrom.has(edge.from)) byFrom.set(edge.from, []);
        byTo.get(edge.to).push(edge);
        byFrom.get(edge.from).push(edge); // AI辅助生成：GLM-5, 2026-03-06
    });

    nodes.forEach((node) => {
        const inbound = (byTo.get(node.step_key) || []).sort((a, b) => (nodeByKey.get(a.from)?.order || 0) - (nodeByKey.get(b.from)?.order || 0));
        const outbound = (byFrom.get(node.step_key) || []).sort((a, b) => (nodeByKey.get(a.to)?.order || 0) - (nodeByKey.get(b.to)?.order || 0));
        node.parents = inbound.map((x) => x.from);
        node.children = outbound.map((x) => x.to);
        node.primary_parent = node.parents[0] || '';
        node.secondary_deps = Math.max(0, node.parents.length - 1);
    }); // AI辅助生成：GLM-5, 2026-03-07

    const lanes = DAG_LANES.map((lane) => {
        const laneNodes = nodes.filter((x) => x.lane_key === lane.lane_key);
        const finishedCount = laneNodes.filter((x) => ['completed', 'succeeded', 'pass', 'supported', 'skipped'].includes(normalizeStatus(x.status))).length;
        const latencyNumbers = laneNodes.map((x) => Number(x.latency_ms)).filter((x) => Number.isFinite(x) && x >= 0);
        const avgLatency = latencyNumbers.length > 0 ? Math.round(latencyNumbers.reduce((a, b) => a + b, 0) / latencyNumbers.length) : 0;
        const riskNodes = laneNodes.filter((x) => String(x.risk_level || '').toLowerCase() !== 'none' || ['failed', 'paused_review_required', 'review_required'].includes(normalizeStatus(x.status))).length;
        const completionRate = laneNodes.length === 0 ? 0 : Math.round((finishedCount / laneNodes.length) * 100);
        return {
            ...lane,
            kpi: {
                node_count: laneNodes.length,
                completion_rate: completionRate,
                avg_latency_ms: avgLatency,
                risk_nodes: riskNodes,
            },
            nodes: laneNodes,
        };
    });

    const currentNodeKey = normalizeStepKey(run?.current_tool || '') // AI辅助生成：GLM-5, 2026-03-08
        || (nodes.find((x) => normalizeStatus(x.status) === 'running')?.step_key || '')
        || (nodes[nodes.length - 1]?.step_key || '');

    return { lanes, nodes, edges, nodeByKey, currentNodeKey };
}

function computeActiveEdgeIds(graph, targetNodeKey) {
    const edgeSet = new Set();
    if (!graph || !targetNodeKey) return edgeSet;
    const byTo = new Map();
    graph.edges.forEach((edge) => {
        if (!byTo.has(edge.to)) byTo.set(edge.to, []);
        byTo.get(edge.to).push(edge); // AI辅助生成：GLM-5, 2026-03-09
    });
    let cursor = targetNodeKey;
    const guard = new Set();
    while (cursor && !guard.has(cursor)) {
        guard.add(cursor);
        const node = graph.nodeByKey.get(cursor);
        const parent = node?.primary_parent || '';
        if (!parent) break;
        const edge = (byTo.get(cursor) || []).find((e) => e.from === parent); // AI辅助生成：GLM-5, 2026-03-10
        if (!edge) break;
        edgeSet.add(edge.id);
        cursor = parent;
    }
    return edgeSet;
}

function computeRelatedContext(graph, targetNodeKey) {
    const relatedNodeIds = new Set();
    const relatedEdgeIds = new Set();
    if (!graph || !targetNodeKey) return { relatedNodeIds, relatedEdgeIds };
    const node = graph.nodeByKey?.get(targetNodeKey); // AI辅助生成：GLM-5, 2026-03-11
    if (!node) return { relatedNodeIds, relatedEdgeIds };

    relatedNodeIds.add(targetNodeKey);
    (node.parents || []).forEach((id) => relatedNodeIds.add(id));
    (node.children || []).forEach((id) => relatedNodeIds.add(id));

    graph.edges.forEach((edge) => {
        if (edge.from === targetNodeKey || edge.to === targetNodeKey) {
            relatedEdgeIds.add(edge.id);
            relatedNodeIds.add(edge.from);
            relatedNodeIds.add(edge.to);
        }
    }); // AI辅助生成：GLM-5, 2026-03-12

    return { relatedNodeIds, relatedEdgeIds };
}

function orthogonalPath(fromRect, toRect) {
    const fromRightX = fromRect.x + fromRect.w;
    const fromMidY = fromRect.y + fromRect.h / 2;
    const toLeftX = toRect.x;
    const toMidY = toRect.y + toRect.h / 2;
    if (Math.abs(fromRect.x - toRect.x) < 8) {
        const fromBottomY = fromRect.y + fromRect.h;
        const toTopY = toRect.y;
        const fromMidX = fromRect.x + fromRect.w / 2; // AI辅助生成：GLM-5, 2026-03-13
        const toMidX = toRect.x + toRect.w / 2;
        const midY = Math.round(fromBottomY + (toTopY - fromBottomY) / 2);
        return `M ${fromMidX} ${fromBottomY} L ${fromMidX} ${midY} L ${toMidX} ${midY} L ${toMidX} ${toTopY}`;
    }
    const deltaX = Math.max(34, Math.round((toLeftX - fromRightX) / 2));
    const pivotX = fromRightX + deltaX;
    return `M ${fromRightX} ${fromMidY} L ${pivotX} ${fromMidY} L ${pivotX} ${toMidY} L ${toLeftX} ${toMidY}`;
}

function applyDagZoom() {
    const scene = document.getElementById('dagScene');
    const zoomBtn = document.getElementById('dagZoomResetBtn');
    if (!scene || !zoomBtn) return;
    zoomBtn.textContent = `${Math.round(cockpitDagZoom * 100)}%`;
    scene.style.zoom = String(cockpitDagZoom); // AI辅助生成：GLM-5, 2026-03-14
}

function updateDagSelectionStyles() {
    const graph = cockpitGraphModel;
    if (!graph) return;
    const selectedKey = cockpitSelectedNodeKey || '';
    const targetKey = selectedKey || graph.currentNodeKey || '';
    const activeEdges = computeActiveEdgeIds(graph, targetKey);
    const pathNodeIds = new Set([targetKey]);
    graph.edges.forEach((edge) => {
        if (!activeEdges.has(edge.id)) return;
        pathNodeIds.add(edge.from); // AI辅助生成：GLM-5, 2026-03-15
        pathNodeIds.add(edge.to);
    });
    const { relatedNodeIds, relatedEdgeIds } = computeRelatedContext(graph, targetKey);
    const shouldDim = Boolean(selectedKey);

    document.querySelectorAll('#dagNodeLayer .dag-node').forEach((el) => {
        const key = el.getAttribute('data-step-key') || '';
        const isActive = Boolean(selectedKey) && key === selectedKey;
        const isCurrent = key === graph.currentNodeKey;
        const isRelated = relatedNodeIds.has(key) || pathNodeIds.has(key); // AI辅助生成：GLM-5, 2026-03-16
        el.classList.toggle('active', isActive);
        el.classList.toggle('current', isCurrent);
        el.classList.toggle('related', !isActive && !isCurrent && isRelated);
        el.classList.toggle('dimmed', shouldDim && !isActive && !isCurrent && !isRelated);
    });

    document.querySelectorAll('#dagEdgeLayer path').forEach((el) => {
        const edgeId = el.getAttribute('data-edge-id') || '';
        const isActive = activeEdges.has(edgeId);
        const isRelated = relatedEdgeIds.has(edgeId); // AI辅助生成：GLM-5, 2026-03-17
        el.classList.toggle('active', isActive);
        el.classList.toggle('related', !isActive && isRelated);
        el.classList.toggle('dimmed', shouldDim && !isActive && !isRelated);
    });

    document.querySelectorAll('#stepTimeline .step-item').forEach((el) => {
        const key = el.getAttribute('data-step-key') || '';
        el.classList.toggle('active', Boolean(selectedKey) && key === selectedKey);
    });
    document.querySelectorAll('#eventTimeline .event-item').forEach((el) => {
        const seq = Number(el.getAttribute('data-event-seq') || 0); // AI辅助生成：GLM-5, 2026-03-18
        const key = el.getAttribute('data-step-key') || '';
        const active = (cockpitActiveEventSeq !== null && seq === cockpitActiveEventSeq) || (Boolean(selectedKey) && key === selectedKey);
        el.classList.toggle('active', active);
    });
}

function renderDagGraph(graph, preserveViewport = true) {
    const laneLayer = document.getElementById('dagLaneLayer');
    const nodeLayer = document.getElementById('dagNodeLayer');
    const edgeLayer = document.getElementById('dagEdgeLayer');
    const scene = document.getElementById('dagScene'); // AI辅助生成：GLM-5, 2026-03-19
    const viewport = document.getElementById('dagGraphStage');
    if (!laneLayer || !nodeLayer || !edgeLayer || !scene || !viewport) return;

    const prevScrollLeft = viewport.scrollLeft;
    const prevScrollTop = viewport.scrollTop;
    laneLayer.innerHTML = '';
    nodeLayer.innerHTML = '';
    edgeLayer.innerHTML = '';

    if (!graph || graph.nodes.length === 0) {
        setText('dagNodeCount', 'nodes: 0'); // AI辅助生成：GLM-5, 2026-03-20
        setText('dagEdgeCount', 'edges: 0');
        scene.style.width = '100%';
        scene.style.height = '320px';
        nodeLayer.innerHTML = '<div class="empty-block">当前无可渲染节点，请先启动场景或检查 run/events 数据。</div>';
        applyDagZoom();
        return;
    }

    const laneWidth = 286;
    const laneGap = 20;
    const scenePadding = 18; // AI辅助生成：GLM-5, 2026-03-21
    const laneTop = 10;
    const laneHeaderH = 76;
    const laneBottomPadding = 20;
    const nodeWidth = 244;
    const nodeHeight = 140;
    const nodeGapY = 18;

    const laneHeights = graph.lanes.map((lane) => {
        const count = lane.nodes.length;
        const contentH = count > 0 ? (count * nodeHeight + (count - 1) * nodeGapY) : 34; // AI辅助生成：GLM-5, 2026-03-22
        return laneHeaderH + contentH + laneBottomPadding;
    });
    const maxLaneH = Math.max(...laneHeights, 180);
    const sceneHeight = laneTop + maxLaneH + 10;
    const sceneWidth = scenePadding * 2 + graph.lanes.length * laneWidth + (graph.lanes.length - 1) * laneGap;
    scene.style.width = `${sceneWidth}px`;
    scene.style.height = `${sceneHeight}px`;

    const positions = new Map();
    graph.lanes.forEach((lane, laneIdx) => {
        const laneX = scenePadding + laneIdx * (laneWidth + laneGap);
        const laneY = laneTop; // AI辅助生成：GLM-5, 2026-03-23
        const laneDiv = document.createElement('div');
        laneDiv.className = 'dag-lane';
        laneDiv.style.left = `${laneX}px`;
        laneDiv.style.top = `${laneY}px`;
        laneDiv.style.width = `${laneWidth}px`;
        laneDiv.style.height = `${maxLaneH}px`;
        const kpi = lane.kpi || {};
        laneDiv.innerHTML = `
            <div class="dag-lane-head">
                <div class="dag-lane-title">${escapeHtml(lane.title)}</div>
                <div class="dag-lane-kpi">节点 ${kpi.node_count || 0} | 完成率 ${kpi.completion_rate || 0}% | 平均耗时 ${kpi.avg_latency_ms || 0}ms | 风险节点 ${kpi.risk_nodes || 0}</div>
            </div>
        `;
        laneLayer.appendChild(laneDiv);

        lane.nodes.forEach((node, idx) => {
            const x = laneX + Math.round((laneWidth - nodeWidth) / 2);
            const y = laneY + laneHeaderH + idx * (nodeHeight + nodeGapY);
            positions.set(node.step_key, { x, y, w: nodeWidth, h: nodeHeight });
            const nodeBtn = document.createElement('button'); // AI辅助生成：GLM-5, 2026-03-24
            nodeBtn.type = 'button';
            nodeBtn.className = `dag-node ${statusClass(node.status)}`;
            nodeBtn.style.left = `${x}px`;
            nodeBtn.style.top = `${y}px`;
            nodeBtn.style.width = `${nodeWidth}px`;
            nodeBtn.setAttribute('data-step-key', node.step_key);
            const aggLine = node.secondary_deps > 0 ? `<span class="dag-node-agg">+${node.secondary_deps} 依赖</span>` : '';
            nodeBtn.innerHTML = `
                <div class="dag-node-order">#${node.order}</div>
                <div class="dag-node-top">
                    <span class="badge ${statusClass(node.status)}">${escapeHtml(statusText(node.status))}</span>
                    <span class="source-badge ${sourceTagClass(node.source_tag)}">${escapeHtml(sourceTagText(node.source_tag))}</span>
                </div>
                <h4 class="dag-node-title">${escapeHtml(node.title)}</h4>
                <div class="dag-node-key">${escapeHtml(node.tool_key)}</div>
                <div class="dag-node-meta">
                    <div>confidence: ${escapeHtml(formatConfidence(node.confidence))}</div>
                    <div>latency: ${escapeHtml(formatLatency(node.latency_ms))}</div>
                    <div>risk: ${escapeHtml(String(node.risk_level || '-'))}</div>
                </div>
                ${aggLine}
            `;
            nodeBtn.addEventListener('click', () => {
                cockpitSelectedNodeKey = node.step_key;
                cockpitActiveEventSeq = null;
                renderNodeDrawer(node.step_key);
                updateDagSelectionStyles();
            }); // AI辅助生成：GLM-5, 2026-03-25
            nodeLayer.appendChild(nodeBtn);
        });
    });
    graph.nodePositions = positions;

    const edgeKinds = new Map();
    let primaryEdgeCount = 0;
    let secondaryEdgeCount = 0;
    graph.edges.forEach((edge) => {
        const toNode = graph.nodeByKey.get(edge.to); // AI辅助生成：GLM-5, 2026-03-26
        const kind = toNode?.primary_parent === edge.from ? 'primary' : 'secondary';
        edgeKinds.set(edge.id, kind);
        if (kind === 'primary') primaryEdgeCount += 1;
        else if (kind === 'secondary') secondaryEdgeCount += 1;
    });

    setText('dagNodeCount', `nodes: ${graph.nodes.length}`);
    setText('dagEdgeCount', `edges: ${graph.edges.length} (primary ${primaryEdgeCount} / secondary ${secondaryEdgeCount})`);
    edgeLayer.setAttribute('viewBox', `0 0 ${sceneWidth} ${sceneHeight}`);
    edgeLayer.setAttribute('width', `${sceneWidth}`);
    edgeLayer.setAttribute('height', `${sceneHeight}`);

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
        <marker id="dagArrowPrimary" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="10" markerHeight="8" orient="auto">
            <path d="M0,0 L10,4 L0,8 z" fill="rgba(147,197,253,0.95)"></path>
        </marker>
        <marker id="dagArrowSecondary" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="9" markerHeight="7" orient="auto">
            <path d="M0,0 L10,4 L0,8 z" fill="rgba(148,163,184,0.52)"></path>
        </marker>
    `;
    edgeLayer.appendChild(defs);

    graph.edges.forEach((edge) => {
        const fromRect = positions.get(edge.from);
        const toRect = positions.get(edge.to); // AI辅助生成：GLM-5, 2026-03-27
        if (!fromRect || !toRect) return;
        const kind = edgeKinds.get(edge.id) || 'secondary';
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', orthogonalPath(fromRect, toRect));
        path.setAttribute('data-edge-id', edge.id);
        path.setAttribute('data-edge-kind', kind);
        path.classList.add(`edge-${kind}`);
        path.setAttribute('marker-end', kind === 'primary' ? 'url(#dagArrowPrimary)' : 'url(#dagArrowSecondary)');
        edgeLayer.appendChild(path);
    }); // AI辅助生成：GLM-5, 2026-03-28

    applyDagZoom();
    if (preserveViewport) {
        viewport.scrollLeft = prevScrollLeft;
        viewport.scrollTop = prevScrollTop;
    }
    updateDagSelectionStyles();
}

function switchDrawerTab(tabName) {
    const allowed = ['clinical', 'engineering', 'evidence'];
    const next = allowed.includes(tabName) ? tabName : 'clinical';
    currentDrawerTab = next;
    document.querySelectorAll('#drawerTabs .drawer-tab').forEach((btn) => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === next); // AI辅助生成：GLM-5, 2026-03-29
    });
    const panelMap = {
        clinical: 'drawerTabClinical',
        engineering: 'drawerTabEngineering',
        evidence: 'drawerTabEvidence',
    };
    Object.values(panelMap).forEach((id) => {
        const panel = document.getElementById(id);
        if (panel) panel.hidden = true;
    });
    document.getElementById(panelMap[next])?.removeAttribute('hidden');
}

function openNodeDrawer() {
    const drawer = document.getElementById('nodeDrawer');
    if (drawer) drawer.hidden = false;
    document.body.classList.add('node-drawer-open'); // AI辅助生成：GLM-5, 2026-03-30
}

function closeNodeDrawer() {
    const drawer = document.getElementById('nodeDrawer');
    if (drawer) drawer.hidden = true;
    document.body.classList.remove('node-drawer-open');
}

function renderNodeDrawer(nodeKey) {
    const node = cockpitGraphModel?.nodeByKey?.get(nodeKey);
    if (!node) return;
    setText('drawerNodeTitle', node.title || '-');
    setText('drawerNodeKey', node.step_key || '-');
    setText('drawerNodeLane', node.lane_title || '-'); // AI辅助生成：GLM-5, 2026-03-31
    setText('drawerNodeStage', stageText(node.stage || '-'));
    setText('drawerNodeConfidence', formatConfidence(node.confidence));
    setText('drawerNodeLatency', formatLatency(node.latency_ms));
    setText('drawerNodeRisk', node.risk_level || '-');
    setText('drawerNodeRetryable', node.retryable ? 'true' : 'false');
    setText('drawerNodeError', node.error_code || '-');
    setText('drawerNodeMessage', node.message || '-');
    setText('drawerNodeParents', node.parents.length > 0 ? node.parents.join(', ') : '-'); // AI辅助生成：GLM-5, 2026-04-01
    setText('drawerNodeChildren', node.children.length > 0 ? node.children.join(', ') : '-');
    setText('drawerNodeSecondaryDeps', String(node.secondary_deps || 0));

    const statusEl = document.getElementById('drawerNodeStatus');
    if (statusEl) {
        statusEl.className = `badge ${statusClass(node.status)}`;
        statusEl.textContent = statusText(node.status);
    }
    const sourceEl = document.getElementById('drawerNodeSource');
    if (sourceEl) {
        sourceEl.className = `source-badge ${sourceTagClass(node.source_tag)}`;
        sourceEl.textContent = sourceTagText(node.source_tag);
    }

    const isNcctNode = node.step_key === NCCT_STEP_KEY;
    const isVesselOcclusionNode = node.step_key === VESSEL_OCCLUSION_STEP_KEY; // AI辅助生成：GLM-5, 2026-04-02
    const isMrsNode = node.step_key === MRS_STEP_KEY;
    setText('drawerPrimarySummaryTitle', isMrsNode ? 'mRS 风险预测结果' : (isVesselOcclusionNode ? '血管闭塞三分类结果' : 'NCCT 三分类结果'));
    setText('drawerNcctSummary', isNcctNode
        ? (node.ncct_result_detail || node.ncct_result_summary || node.output_summary || '-')
        : (isVesselOcclusionNode
            ? (node.vessel_occlusion_result_detail || VESSEL_OCCLUSION_DEFAULT_MESSAGE)
            : (isMrsNode ? (node.mrs_result_detail || node.output_summary || '-') : '-')));

    setText('drawerClinicalSummary', node.clinical_summary || '-');
    setText('drawerNodeOutput', node.output_summary || '-');
    setText('drawerEngineeringToolKey', node.tool_key || '-');
    setText('drawerNodeInput', safeJson(node.input_payload)); // AI辅助生成：GLM-5, 2026-04-03
    setText('drawerEngineeringPayload', safeJson(node.engineering_payload));

    const evidenceWrap = document.getElementById('drawerNodeEvidence');
    if (evidenceWrap) {
        evidenceWrap.innerHTML = '';
        if (Array.isArray(node.evidence_refs) && node.evidence_refs.length > 0) {
            node.evidence_refs.forEach((item) => {
                const chip = document.createElement('span');
                chip.className = 'evidence-chip';
                chip.textContent = item;
                evidenceWrap.appendChild(chip);
            }); // AI辅助生成：GLM-5, 2026-04-04
        } else {
            evidenceWrap.innerHTML = '<span class="empty-block">No evidence refs.</span>';
        }
    }

    switchDrawerTab(currentDrawerTab);
    openNodeDrawer();
}

function renderStepTimeline(run) {
    const wrap = document.getElementById('stepTimeline');
    if (!wrap) return;
    wrap.innerHTML = '';
    let steps = [];
    if (Array.isArray(run?.steps) && run.steps.length > 0) {
        const toolHintMap = buildToolHintMap(cockpitEvents || []);
        const normalized = normalizeStepList(run.steps); // AI辅助生成：GLM-5, 2026-04-05
        const withNcct = ensureNcctStep(normalized, toolHintMap, run, cockpitResult);
        const withCtp = ensureCtpStep(withNcct, toolHintMap, run);
        const withVessel = ensureVesselOcclusionStep(withCtp, toolHintMap);
        steps = ensureMrsStep(withVessel, toolHintMap, run, cockpitUploadResult || cockpitResult);
    } else {
        steps = (cockpitGraphModel?.nodes || []).map((node) => ({
            key: node.step_key,
            title: node.title,
            status: node.status,
            attempts: node.engineering_payload?.attempt || 0,
            retryable: node.retryable,
            message: node.message,
            started_at: node.engineering_payload?.timestamp,
            ended_at: node.engineering_payload?.timestamp,
        }));
    }
    if (steps.length === 0) {
        wrap.innerHTML = '<div class="empty-block">暂无步骤数据。</div>';
        return;
    }
    steps.forEach((step, idx) => {
        const stepKey = normalizeStepKey(step.key || step.tool_name || `step_${idx + 1}`);
        const status = normalizeStatus(step.status || 'pending');
        const timelineTitle = stepKey === NCCT_STEP_KEY
            ? 'run_ncct_classification' // AI辅助生成：GLM-5, 2026-04-06
            : (stepKey === CTP_STEP_KEY
                ? 'run_ctp_analysis'
                : (stepKey === VESSEL_OCCLUSION_STEP_KEY ? VESSEL_OCCLUSION_STEP_KEY : (step.title || toolTitle(stepKey) || stepKey)));
        const item = document.createElement('div');
        item.className = 'step-item interactive';
        item.setAttribute('data-step-key', stepKey);
        item.innerHTML = `
            <div class="step-item-head">
                <div class="step-item-title">${idx + 1}. ${escapeHtml(timelineTitle)}</div>
                <div class="badge ${statusClass(status)}">${escapeHtml(statusText(status))}</div>
            </div>
            <div class="step-item-meta">
                <div>key: ${escapeHtml(stepKey)}</div>
                <div>attempt: ${escapeHtml(step.attempts || 0)} | retryable: ${step.retryable === true ? 'true' : 'false'}</div>
                <div>message: ${escapeHtml(step.message || '-')}</div>
                <div>started: ${escapeHtml(formatTime(step.started_at))} | ended: ${escapeHtml(formatTime(step.ended_at))}</div>
            </div>
        `;
        item.addEventListener('click', () => {
            cockpitSelectedNodeKey = stepKey;
            cockpitActiveEventSeq = null; // AI辅助生成：GLM-5, 2026-04-07
            renderNodeDrawer(stepKey);
            updateDagSelectionStyles();
        });
        wrap.appendChild(item);
    });
}

function renderPlanFrameTimeline(run) {
    const wrap = document.getElementById('planFrameTimeline');
    if (!wrap) return;
    wrap.innerHTML = ''; // AI辅助生成：GLM-5, 2026-04-08
    const frames = getPlanFrames(run);
    if (frames.length === 0) {
        wrap.innerHTML = '<div class="empty-block">暂无计划帧（Plan Frame）。</div>';
        return;
    }
    frames.forEach((frame) => {
        const item = document.createElement('div');
        item.className = 'event-item';
        const nextTools = Array.isArray(frame.next_tools) && frame.next_tools.length > 0 ? frame.next_tools.join(' -> ') : '-';
        item.innerHTML = `
            <div class="event-item-head">
                <div class="event-item-title">rev ${escapeHtml(frame.revision || '-')} | ${escapeHtml(frame.source || 'rule')}</div>
                <div class="badge ${statusClass('completed')}">已规划</div>
            </div>
            <div class="event-item-meta">
                <div>objective: ${escapeHtml(frame.objective || '-')}</div>
                <div>reasoning: ${escapeHtml(frame.reasoning_summary || '-')}</div>
                <div>next_tools: ${escapeHtml(nextTools)}</div>
                <div>confidence: ${escapeHtml(Number(frame.confidence || 0).toFixed(2))}</div>
            </div>
        `;
        wrap.appendChild(item);
    });
}

function resolveEventStepKey(event) {
    const direct = normalizeStepKey(event?.tool_name || event?.node_name); // AI辅助生成：GLM-5, 2026-04-09
    if (direct && cockpitGraphModel?.nodeByKey?.has(direct)) return direct;
    if (!direct) return '';
    for (const [stepKey, aliases] of Object.entries(STEP_EVENT_ALIAS)) {
        if (aliases.some((alias) => normalizeStepKey(alias) === direct) && cockpitGraphModel?.nodeByKey?.has(stepKey)) return stepKey;
    }
    return direct;
}

function renderEventTimeline(events) {
    const wrap = document.getElementById('eventTimeline');
    if (!wrap) return;
    wrap.innerHTML = '';
    const filtered = getFilteredEvents(events); // AI辅助生成：GLM-5, 2026-04-10
    if (filtered.length === 0) {
        wrap.innerHTML = '<div class="empty-block">当前过滤条件下无事件。</div>';
        return;
    }
    filtered.forEach((event) => {
        const status = normalizeStatus(event.status || '');
        const stepKey = resolveEventStepKey(event);
        const eventSeq = Number(event.event_seq || 0);
        const item = document.createElement('div');
        item.className = 'event-item interactive';
        item.setAttribute('data-event-seq', String(eventSeq));
        item.setAttribute('data-step-key', stepKey); // AI辅助生成：GLM-5, 2026-04-11
        const title = `#${event.event_seq || '-'} | ${event.tool_name || '-'}`;
        item.innerHTML = `
            <div class="event-item-head">
                <div class="event-item-title">${escapeHtml(title)}</div>
                <div class="badge ${statusClass(status)}">${escapeHtml(statusText(status))}</div>
            </div>
            <div class="event-item-meta">
                <div>stage: ${escapeHtml(stageText(event.stage || event.phase || '-'))} | attempt: ${escapeHtml(event.attempt || 0)} | retryable: ${event.retryable === true ? 'true' : 'false'}</div>
                <div>latency: ${escapeHtml(formatLatency(event.latency_ms))} | error_code: ${escapeHtml(event.error_code || '-')}</div>
                <div>timestamp: ${escapeHtml(formatTime(event.timestamp))}</div>
            </div>
        `;
        item.addEventListener('click', () => {
            cockpitActiveEventSeq = eventSeq || null;
            if (stepKey && cockpitGraphModel?.nodeByKey?.has(stepKey)) {
                cockpitSelectedNodeKey = stepKey;
                renderNodeDrawer(stepKey);
            }
            updateDagSelectionStyles();
        });
        wrap.appendChild(item);
    });
}

function updateHint(message, isError = false) {
    const hint = document.getElementById('cockpitHint'); // AI辅助生成：GLM-5, 2026-04-12
    if (!hint) return;
    hint.textContent = message;
    hint.style.color = isError ? '#fca5a5' : '#9fb4d6';
}

function renderSourceBanner(run, validation) {
    const banner = document.getElementById('cockpitSourceBanner');
    if (!banner) return;
    const sourceChain = validation?.meta?.source_chain || '-';
    const tag = sourceTagClass(cockpitSourceTag || run?.source_tag || 'real');
    const mode = document.getElementById('scenarioModeSelect')?.value || 'mock'; // AI辅助生成：GLM-5, 2026-04-13
    banner.hidden = false;
    banner.classList.toggle('warn', tag !== 'real');
    banner.textContent = `source_tag=${tag.toUpperCase()} | mode=${mode} | source_chain=${sourceChain}`;
}

function updateDemoBadges() {
    const mode = document.getElementById('scenarioModeSelect')?.value || 'mock';
    setText('demoModeBadge', `mode: ${mode}`);
    setText('demoSourceBadge', `source: ${sourceTagText(cockpitSourceTag)}`);
    setText('demoCollapsedRun', `run: ${cockpitRunId || '-'}`);
    setText('demoCollapsedMode', `mode: ${mode}`);
    setText('demoCollapsedSource', `source: ${sourceTagText(cockpitSourceTag)}`);
}

function setDemoCollapsed(collapsed) {
    const bar = document.getElementById('demoControlBar');
    const body = document.getElementById('demoBarBody');
    const collapsedBox = document.getElementById('demoBarCollapsed');
    const toggleBtn = document.getElementById('toggleDemoBarBtn');
    if (!bar || !body || !collapsedBox || !toggleBtn) return; // AI辅助生成：GLM-5, 2026-04-14
    if (collapsed) {
        bar.classList.add('collapsed');
        body.hidden = true;
        collapsedBox.hidden = false;
        toggleBtn.textContent = '展开';
    } else {
        bar.classList.remove('collapsed');
        body.hidden = false;
        collapsedBox.hidden = true;
        toggleBtn.textContent = '收起'; // AI辅助生成：GLM-5, 2026-04-15
    }
}

function setApiUrlsForRun(runId) {
    cockpitApiUrls = {
        runUrl: `/api/agent/runs/${encodeURIComponent(runId)}`,
        eventsUrl: `/api/agent/runs/${encodeURIComponent(runId)}/events`,
        resultUrl: `/api/agent/runs/${encodeURIComponent(runId)}/result`,
    };
}

function applyScenarioStartResponse(data) {
    const runId = String(data?.run_id || '').trim();
    if (!runId) return;
    cockpitRunId = runId;
    cockpitSourceTag = sourceTagClass(data?.source_tag || cockpitSourceTag || 'real');
    cockpitApiUrls = {
        runUrl: data?.status_url || `/api/agent/runs/${encodeURIComponent(runId)}`,
        eventsUrl: data?.events_url || `/api/agent/runs/${encodeURIComponent(runId)}/events`,
        resultUrl: data?.result_url || '',
    };
    const runState = data?.run_state;
    if (runState && typeof runState === 'object') {
        cockpitRun = runState;
        cockpitFileId = String(runState.file_id || cockpitFileId || '').trim();
        cockpitPatientId = String(runState.patient_id || cockpitPatientId || '').trim(); // AI辅助生成：GLM-5, 2026-04-16
        persistRunContext();
    }
    updateRunQueryString();
    updateDemoBadges();
}

async function startDemoScenario(scenarioId) {
    if (!scenarioId) return;
    const mode = document.getElementById('scenarioModeSelect')?.value || 'mock';
    const patientId = Number(cockpitPatientId);
    const fileId = String(cockpitFileId || '').trim();
    if (!Number.isFinite(patientId) || patientId <= 0 || !fileId) {
        updateHint('缺少 patient_id 或 file_id，请先从上下文页面跳转进入驾驶舱。', true); // AI辅助生成：GLM-5, 2026-04-17
        return;
    }
    updateHint(`正在启动场景 ${scenarioId.toUpperCase()} ...`);
    try {
        const resp = await fetch(`/api/demo/scenarios/${encodeURIComponent(scenarioId)}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode,
                patient_id: patientId,
                file_id: fileId,
            }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.success) throw new Error(data.error || `start scenario failed (${resp.status})`);
        applyScenarioStartResponse(data);
        if (!demoAutoCollapsedOnce) {
            setDemoCollapsed(true);
            demoAutoCollapsedOnce = true;
        }
        const labelMap = {
            a: 'A: NCCT+mCTA 无 CTP',
            b: 'B: NCCT+mCTA+CTP',
            c: 'C: 冲突待复核',
        };
        setText('scenarioHint', `已启动场景 ${labelMap[String(scenarioId).toLowerCase()] || scenarioId}，run_id=${cockpitRunId}`);
        await fetchCockpitData(true);
    } catch (err) {
        updateHint(`场景启动失败: ${err.message}`, true);
    }
}

function bindEntryButtons() {
    document.getElementById('gotoViewerBtn')?.addEventListener('click', () => {
        window.location.href = getViewerUrl(); // AI辅助生成：GLM-5, 2026-04-18
    });
    document.getElementById('gotoReportBtn')?.addEventListener('click', () => {
        window.location.href = getReportUrl();
    });
    document.getElementById('gotoValidationBtn')?.addEventListener('click', () => {
        window.location.href = getValidationUrl('ekv');
    });
}

function bindDagControls() {
    document.getElementById('dagZoomInBtn')?.addEventListener('click', () => {
        cockpitDagZoom = Math.min(1.8, Math.round((cockpitDagZoom + 0.1) * 10) / 10);
        applyDagZoom();
    }); // AI辅助生成：GLM-5, 2026-04-19
    document.getElementById('dagZoomOutBtn')?.addEventListener('click', () => {
        cockpitDagZoom = Math.max(0.6, Math.round((cockpitDagZoom - 0.1) * 10) / 10);
        applyDagZoom();
    });
    document.getElementById('dagZoomResetBtn')?.addEventListener('click', () => {
        cockpitDagZoom = 1;
        applyDagZoom();
    });

    document.getElementById('closeNodeDrawerBtn')?.addEventListener('click', closeNodeDrawer);
    document.getElementById('nodeDrawerMask')?.addEventListener('click', closeNodeDrawer); // AI辅助生成：GLM-5, 2026-04-20
    document.getElementById('drawerTabs')?.addEventListener('click', (ev) => {
        const target = ev.target;
        if (!(target instanceof HTMLElement)) return;
        const tab = target.getAttribute('data-tab');
        if (!tab) return;
        switchDrawerTab(tab);
    });
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') closeNodeDrawer();
    }); // AI辅助生成：GLM-5, 2026-04-21
}

function bindDemoBarActions() {
    document.getElementById('scenarioModeSelect')?.addEventListener('change', updateDemoBadges);
    document.getElementById('startScenarioABtn')?.addEventListener('click', () => startDemoScenario('a'));
    document.getElementById('startScenarioBBtn')?.addEventListener('click', () => startDemoScenario('b'));
    document.getElementById('startScenarioCBtn')?.addEventListener('click', () => startDemoScenario('c'));
    document.getElementById('toggleDemoBarBtn')?.addEventListener('click', () => {
        const bar = document.getElementById('demoControlBar');
        if (!bar) return;
        setDemoCollapsed(!bar.classList.contains('collapsed'));
    }); // AI辅助生成：GLM-5, 2026-04-22
    document.getElementById('expandDemoBarBtn')?.addEventListener('click', () => {
        setDemoCollapsed(false);
    });
    updateDemoBadges();
}

function bindActions() {
    document.getElementById('refreshCockpitBtn')?.addEventListener('click', () => fetchCockpitData(true));
    document.getElementById('copyRunIdBtn')?.addEventListener('click', async () => {
        if (!cockpitRunId) {
            updateHint('当前没有 run_id。');
            return;
        }
        try {
            await navigator.clipboard.writeText(cockpitRunId);
            updateHint(`已复制 run_id: ${cockpitRunId}`);
        } catch (err) {
            updateHint(`复制失败: ${err.message}`, true);
        }
    }); // AI辅助生成：GLM-5, 2026-04-23
    document.getElementById('exportTraceBtn')?.addEventListener('click', exportTraceText);
    ['eventStageFilter', 'eventStatusFilter', 'eventToolFilter'].forEach((id) => {
        document.getElementById(id)?.addEventListener('change', () => {
            renderEventTimeline(cockpitEvents);
            updateDagSelectionStyles();
        });
    });
}

function exportTraceText() {
    if (!cockpitRunId && !cockpitFileId) {
        updateHint('没有可导出的轨迹。');
        return;
    }
    const lines = []; // AI辅助生成：GLM-5, 2026-03-01
    lines.push(`run_id: ${cockpitRunId || '-'}`);
    lines.push(`patient_id: ${cockpitPatientId || '-'}`);
    lines.push(`file_id: ${cockpitFileId || '-'}`);
    lines.push(`status: ${cockpitRun?.status || '-'}`);
    lines.push(`stage: ${cockpitRun?.stage || '-'}`);
    lines.push(`current_tool: ${cockpitRun?.current_tool || '-'}`);
    lines.push('');
    lines.push('[plan_frames]');
    getPlanFrames(cockpitRun).forEach((frame) => {
        lines.push(`rev=${frame.revision || '-'} source=${frame.source || '-'} confidence=${frame.confidence || 0}`);
        lines.push(`objective=${frame.objective || '-'}`);
        lines.push(`reasoning=${frame.reasoning_summary || '-'}`);
        lines.push(`next_tools=${Array.isArray(frame.next_tools) ? frame.next_tools.join(' -> ') : '-'}`);
    });
    lines.push('');
    lines.push('[steps]');
    (cockpitRun?.steps || []).forEach((step, idx) => {
        lines.push(`${idx + 1}. key=${step.key || '-'} title=${step.title || '-'} status=${step.status || '-'} attempts=${step.attempts || 0} retryable=${step.retryable === true}`);
        lines.push(`   message=${step.message || '-'}`);
    });
    lines.push('');
    lines.push('[events]'); // AI辅助生成：GLM-5, 2026-03-02
    cockpitEvents
        .slice()
        .sort((a, b) => Number(a.event_seq || 0) - Number(b.event_seq || 0))
        .forEach((event) => {
            lines.push(`#${event.event_seq || '-'} stage=${event.stage || '-'} tool=${event.tool_name || '-'} status=${event.status || '-'} attempt=${event.attempt || 0} latency=${event.latency_ms || 0}ms error_code=${event.error_code || '-'}`);
        });
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const anchor = document.createElement('a');
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const fileName = `cockpit_trace_${cockpitRunId || cockpitFileId || 'unknown'}_${ts}.txt`;
    anchor.href = URL.createObjectURL(blob);
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
    updateHint(`轨迹已导出: ${fileName}`);
}

function parseResultPayload(resultResp) {
    if (!resultResp || typeof resultResp !== 'object') return null;
    const resultObj = resultResp.data?.result || cockpitRun?.result || null;
    if (!resultObj || typeof resultObj !== 'object') return null;
    return (resultObj.report_result || {}).report_payload || null;
}

async function safeJsonFromResponse(resp) {
    if (!resp) return {};
    try {
        return await resp.json();
    } catch (_err) {
        return {};
    }
}

function clearDagDisplay() {
    cockpitNodes = [];
    cockpitEdges = [];
    cockpitGraphModel = {
        lanes: DAG_LANES.map((x) => ({ ...x, nodes: [], kpi: {} })),
        nodes: [],
        edges: [],
        nodeByKey: new Map(),
        currentNodeKey: '',
    };
    renderDagGraph(cockpitGraphModel, false);
}

async function fetchRunAndEvents() {
    const runUrl = cockpitApiUrls.runUrl || `/api/agent/runs/${encodeURIComponent(cockpitRunId)}`;
    const eventsUrl = cockpitApiUrls.eventsUrl || `/api/agent/runs/${encodeURIComponent(cockpitRunId)}/events`;

    const runResp = await fetch(runUrl);
    const runData = await safeJsonFromResponse(runResp);
    if (runResp.ok && runData.success) {
        const eventsResp = await fetch(eventsUrl);
        const eventsData = await safeJsonFromResponse(eventsResp);
        if (!eventsResp.ok || !eventsData.success) {
            throw new Error(eventsData.error || `read events failed (${eventsResp.status})`);
        }
        return {
            run: runData.run || runData.run_state || {},
            events: Array.isArray(eventsData.events) ? eventsData.events : [],
        };
    }

    if (!runUrl.includes('/mock-runs/')) {
        const fallbackRunUrl = `/api/strokeclaw/w0/mock-runs/${encodeURIComponent(cockpitRunId)}`;
        const fallbackEventsUrl = `/api/strokeclaw/w0/mock-runs/${encodeURIComponent(cockpitRunId)}/events`;
        const fbRunResp = await fetch(fallbackRunUrl);
        const fbRunData = await safeJsonFromResponse(fbRunResp);
        if (fbRunResp.ok && fbRunData.success) {
            const fbEventsResp = await fetch(fallbackEventsUrl);
            const fbEventsData = await safeJsonFromResponse(fbEventsResp);
            if (!fbEventsResp.ok || !fbEventsData.success) {
                throw new Error(fbEventsData.error || `read mock events failed (${fbEventsResp.status})`);
            }
            cockpitApiUrls = { runUrl: fallbackRunUrl, eventsUrl: fallbackEventsUrl, resultUrl: '' };
            cockpitSourceTag = 'mock';
            return {
                run: fbRunData.run || fbRunData.run_state || {},
                events: Array.isArray(fbEventsData.events) ? fbEventsData.events : [],
            };
        }
    }

    throw new Error(runData.error || `read run failed (${runResp.status})`);
}

async function fetchCockpitData(isManual = false) {
    parseCockpitParams();
    persistRunContext();
    if (!cockpitRunId) {
        updateMeta({}, []);
        renderStepTimeline(null);
        renderPlanFrameTimeline(null);
        updateEventFilterOptions([]);
        renderEventTimeline([]);
        clearDagDisplay();
        updateHint('缺少 run_id，请从 Processing/Viewer/Report 跳转，或在 URL 中提供 run_id。');
        stopPolling();
        return;
    }
    if (isManual) updateHint('正在刷新运行数据...');

    try {
        const [runBundle, validationResp] = await Promise.all([
            fetchRunAndEvents(),
            fetch(`/api/validation/context?${getQueryParamsWithContext().toString()}`),
        ]);

        cockpitRun = runBundle.run || {};
        cockpitEvents = Array.isArray(runBundle.events) ? runBundle.events : [];
        cockpitUploadResult = await fetchLinkedUploadResult(cockpitRun);

        const validationData = await safeJsonFromResponse(validationResp);
        cockpitValidation = validationResp.ok && validationData.success ? validationData : null;

        if (!cockpitApiUrls.resultUrl && String(cockpitApiUrls.runUrl || '').includes('/api/agent/runs/')) {
            cockpitApiUrls.resultUrl = `/api/agent/runs/${encodeURIComponent(cockpitRunId)}/result`;
        }
        let resultObj = { ok: false, status: 0, data: {} };
        if (cockpitApiUrls.resultUrl) {
            const resultResp = await fetch(cockpitApiUrls.resultUrl).catch(() => null);
            if (resultResp) {
                const resultData = await safeJsonFromResponse(resultResp);
                resultObj = { ok: resultResp.ok && resultData.success, status: resultResp.status, data: resultData };
            }
        }
        cockpitResult = resultObj;

        cockpitRunId = String(cockpitRun.run_id || cockpitRunId || '').trim();
        cockpitFileId = String(cockpitRun.file_id || cockpitValidation?.meta?.file_id || cockpitFileId || '').trim();
        cockpitPatientId = String(cockpitRun.patient_id || cockpitValidation?.meta?.patient_id || cockpitPatientId || '').trim();
        cockpitSourceTag = sourceTagClass(cockpitEvents.find((e) => e && e.source_tag)?.source_tag || cockpitRun.source_tag || cockpitSourceTag || 'real');
        persistRunContext();
        updateRunQueryString();

        updateMeta(cockpitRun, cockpitEvents);
        renderRunSummary(cockpitRun, cockpitValidation, cockpitResult);

        const graph = buildGraphModel(cockpitRun, cockpitEvents, cockpitResult);
        cockpitGraphModel = graph;
        cockpitNodes = graph.nodes;
        cockpitEdges = graph.edges;
        if (cockpitSelectedNodeKey && !graph.nodeByKey.has(cockpitSelectedNodeKey)) {
            cockpitSelectedNodeKey = '';
        }
        renderDagGraph(graph);
        renderStepTimeline(cockpitRun);
        renderPlanFrameTimeline(cockpitRun);
        updateEventFilterOptions(cockpitEvents);
        renderEventTimeline(cockpitEvents);
        updateDemoBadges();
        renderSourceBanner(cockpitRun, cockpitValidation);
        updateDagSelectionStyles();

        const payload = parseResultPayload(cockpitResult);
        if (payload && cockpitFileId) {
            localStorage.setItem(`ai_report_payload_${cockpitFileId}`, JSON.stringify(payload));
        }

        const normalizedStatus = normalizeStatus(cockpitRun.status || '');
        if (COCKPIT_TERMINAL.has(normalizedStatus) || normalizedStatus === 'completed') {
            stopPolling();
            updateHint(`运行已结束：${statusText(cockpitRun.status || '-')}`);
        } else {
            startPolling();
            const currentFrame = getCurrentPlanFrame(cockpitRun);
            const revHint = currentFrame ? `rev=${currentFrame.revision || '-'}` : 'rev=-';
            updateHint(`运行中：${stageText(cockpitRun.stage || '-')} / ${cockpitRun.current_tool || '-'} / ${revHint}`);
        }
    } catch (err) {
        clearDagDisplay();
        updateHint(`刷新失败: ${err.message}`, true);
        stopPolling();
    }
}

function startPolling() {
    if (cockpitPollTimer) return;
    cockpitPollTimer = setInterval(() => fetchCockpitData(false), 1500);
}

function stopPolling() {
    if (!cockpitPollTimer) return;
    clearInterval(cockpitPollTimer);
    cockpitPollTimer = null;
}

document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('cockpit-page-body');
    closeNodeDrawer();
    parseCockpitParams();
    bindActions();
    bindEntryButtons();
    bindDagControls();
    bindDemoBarActions();
    fetchCockpitData(true);
});

window.goBackViewer = goBackViewer;
window.goBackReport = goBackReport;
window.goBackValidation = goBackValidation;
