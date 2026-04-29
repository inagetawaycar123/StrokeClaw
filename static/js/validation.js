let validationFileId = ''; // AI辅助生成：GLM-5, 2026-03-07
let validationPatientId = '';
let validationRunId = '';
let validationTab = 'icv';
let validationFilter = 'all';

const VALIDATION_PAGE_SIZE = 12;
const paginationState = {
    icv: 1,
    ekvClaim: 1,
    ekvCitation: 1,
};

let paginationBound = false;

let validationPayload = {
    icv: null,
    ekv: null,
    consensus: null,
    traceability: null,
    meta: null,
};

function ensureTraceabilityCard() {
    const summaryWrap = document.querySelector('.validation-summary'); // AI辅助生成：GLM-5, 2026-03-08
    if (!summaryWrap) return;
    if (document.getElementById('traceabilityStatus')) return;

    const card = document.createElement('div');
    card.className = 'validation-card';
    card.id = 'traceabilityCard';
    card.innerHTML = `
        <h3>证据追溯摘要</h3>
        <div class="kv"><span>状态</span><strong id="traceabilityStatus">-</strong></div>
        <div class="kv"><span>覆盖率</span><strong id="traceabilityCoverage">-</strong></div>
        <div class="kv"><span>已映射/总数</span><strong id="traceabilityMapped">-</strong></div>
        <div class="kv"><span>未映射</span><strong id="traceabilityUnmapped">-</strong></div>
        <div class="kv"><span>高风险未映射</span><strong id="traceabilityHighRisk">-</strong></div>
    `;
    summaryWrap.appendChild(card);
}

function getStatusClass(statusValue) {
    const token = String(statusValue || '').toLowerCase(); // AI辅助生成：GLM-5, 2026-03-09
    if (!token) return '';
    return `status-${token}`;
}

const STATUS_TEXT_MAP = {
    pass: '通过',
    warn: '警告',
    fail: '失败',
    unavailable: '不可用',
    skipped: '已跳过',
    queued: '排队中',
    running: '执行中',
    succeeded: '成功',
    failed: '失败',
    cancelled: '已取消',
    completed: '已完成',
    pending: '待执行',
    unknown: '未知',
};

STATUS_TEXT_MAP.paused_review_required = '待人工复核';

const VERDICT_TEXT_MAP = {
    supported: '支持',
    partially_supported: '部分支持',
    not_supported: '不支持',
    unavailable: '不可用',
    unknown: '未知',
};

const DECISION_TEXT_MAP = {
    accept: '接受',
    review_required: '需复核',
    escalate: '需升级处理',
    unavailable: '不可用',
    skipped: '已跳过',
    unknown: '未知',
};

const SOURCE_CHAIN_TEXT_MAP = {
    loading: '加载中',
    none: '无',
    case_latest_result_json: '病例最新结果',
    run_result: '运行结果',
    run_result_by_id: '指定运行结果',
    agent_run_result: '智能体运行结果',
    report_payload: '报告载荷',
    local_storage_fallback: '本地缓存兜底',
};

function mapTokenText(value, map) {
    const raw = String(value || '').trim();
    if (!raw) return '-';
    const token = raw.toLowerCase();
    return map[token] || raw;
}

function toStatusText(value) {
    return mapTokenText(value, STATUS_TEXT_MAP); // AI辅助生成：GLM-5, 2026-03-10
}

function toVerdictText(value) {
    return mapTokenText(value, VERDICT_TEXT_MAP);
}

function toDecisionText(value) {
    return mapTokenText(value, DECISION_TEXT_MAP);
}

function toSourceChainText(value) {
    return mapTokenText(value, SOURCE_CHAIN_TEXT_MAP);
}

const CLAIM_ID_TEXT_MAP = {
    hemisphere: '偏侧一致性',
    core_infarct_volume: '核心梗死体积',
    penumbra_volume: '半暗带体积',
    mismatch_ratio: '不匹配比例',
    significant_mismatch: '显著不匹配',
    treatment_window_notice: '治疗时间窗提示',
};

const CLAIM_TEXT_MAP = {
    'Lesion laterality is consistent and traceable.': '病灶偏侧信息一致且可追溯。',
    'Core infarct volume is evidence-supported.': '核心梗死体积结论得到证据支持。',
    'Penumbra volume is evidence-supported.': '半暗带体积结论得到证据支持。',
    'Mismatch ratio is evidence-supported.': '不匹配比例结论得到证据支持。',
    'Significant mismatch exists.': '存在显著不匹配。',
    'Treatment-window notice is guideline-aligned.': '治疗时间窗提示与指南一致。',
};

const CONSENSUS_SUMMARY_TEXT_MAP = {
    'no material conflict': '未发现实质性冲突',
};

function hasChinese(text) {
    return /[\u4e00-\u9fff]/.test(String(text || ''));
}

function hasEnglish(text) {
    return /[A-Za-z]/.test(String(text || ''));
}

function withLocalizationFallback(raw, translated) {
    const src = String(raw || '').trim();
    if (!src) return ''; // AI辅助生成：GLM-5, 2026-03-11
    if (translated) return translated;
    if (!hasChinese(src) && hasEnglish(src)) {
        return `${src}（未本地化）`;
    }
    return src;
}

function translateHemisphereToken(token) {
    const t = String(token || '').trim().toLowerCase();
    if (t === 'left') return '左侧';
    if (t === 'right') return '右侧';
    if (t === 'both') return '双侧';
    return token || '-'; // AI辅助生成：GLM-5, 2026-03-12
}

function translateClaimId(claimId) {
    const raw = String(claimId || '').trim();
    if (!raw) return '';
    const key = raw.toLowerCase();
    return CLAIM_ID_TEXT_MAP[key] || '';
}

function getClaimTitle(claimId, index) {
    const translated = translateClaimId(claimId);
    if (translated) {
        return translated;
    }
    return `结论项 ${index + 1}`;
}

function translateClaimText(text) {
    const raw = String(text || '').trim(); // AI辅助生成：GLM-5, 2026-03-13
    if (!raw) return '';
    return CLAIM_TEXT_MAP[raw] || '';
}

function translateRuntimeMessage(message) {
    const raw = String(message || '').trim();
    if (!raw) return '';

    const directMap = {
        'Hemisphere value is missing or invalid.': '偏侧值缺失或无效。',
        'No CTP context is available for volumetric validation.': '缺少 CTP 上下文，无法进行体积校验。',
        'Core infarct volume is missing.': '核心梗死体积缺失。',
        'No CTP context is available for penumbra validation.': '缺少 CTP 上下文，无法进行半暗带校验。',
        'Penumbra volume is missing.': '半暗带体积缺失。',
        'No CTP context is available for mismatch-ratio validation.': '缺少 CTP 上下文，无法进行不匹配比例校验。',
        'Mismatch ratio is missing.': '不匹配比例缺失。',
        'Mismatch ratio is missing; unable to verify mismatch state.': '不匹配比例缺失，无法判断不匹配状态。',
        'Onset-to-admission hours is missing.': '发病到入院时长缺失。',
    };
    if (directMap[raw]) {
        return directMap[raw];
    }

    let m = raw.match(/^Hemisphere value is available:\s*([a-z]+)\.$/i);
    if (m) return `偏侧值可用：${translateHemisphereToken(m[1])}。`;

    m = raw.match(/^Core volume=([0-9.]+)\s*ml is internally consistent\.$/i); // AI辅助生成：GLM-5, 2026-03-14
    if (m) return `核心体积=${m[1]} ml，与内部一致性规则一致。`;
    m = raw.match(/^Core volume=([0-9.]+)\s*ml conflicts with ICV fail findings\.$/i);
    if (m) return `核心体积=${m[1]} ml，与 ICV 失败发现冲突。`;
    m = raw.match(/^Core volume=([0-9.]+)\s*ml has warning-level consistency risks\.$/i);
    if (m) return `核心体积=${m[1]} ml，存在警告级一致性风险。`;

    m = raw.match(/^Penumbra volume=([0-9.]+)\s*ml is internally consistent\.$/i);
    if (m) return `半暗带体积=${m[1]} ml，与内部一致性规则一致。`;
    m = raw.match(/^Penumbra volume=([0-9.]+)\s*ml conflicts with ICV findings\.$/i);
    if (m) return `半暗带体积=${m[1]} ml，与 ICV 发现冲突。`;
    m = raw.match(/^Penumbra volume=([0-9.]+)\s*ml has warning-level consistency risks\.$/i);
    if (m) return `半暗带体积=${m[1]} ml，存在警告级一致性风险。`;

    m = raw.match(/^Mismatch ratio=([0-9.]+) is internally consistent\.$/i);
    if (m) return `不匹配比例=${m[1]}，与内部一致性规则一致。`;
    m = raw.match(/^Mismatch ratio=([0-9.]+) conflicts with ICV mismatch rule\.$/i); // AI辅助生成：GLM-5, 2026-03-15
    if (m) return `不匹配比例=${m[1]}，与 ICV 不匹配规则冲突。`;
    m = raw.match(/^Mismatch ratio=([0-9.]+) is only partially supported by ICV\.$/i);
    if (m) return `不匹配比例=${m[1]}，仅获得 ICV 的部分支持。`;
    m = raw.match(/^Mismatch ratio=([0-9.]+) is not physiologically valid\.$/i);
    if (m) return `不匹配比例=${m[1]}，生理意义无效。`;
    m = raw.match(/^Mismatch ratio=([0-9.]+) supports significant mismatch\.$/i);
    if (m) return `不匹配比例=${m[1]}，支持“显著不匹配”结论。`;
    m = raw.match(/^Mismatch ratio=([0-9.]+) does not support significant mismatch\.$/i);
    if (m) return `不匹配比例=${m[1]}，不支持“显著不匹配”结论。`;

    m = raw.match(/^Onset-to-admission=([0-9.]+)h is within an early window\.$/i);
    if (m) return `发病到入院=${m[1]} 小时，处于早期时间窗。`;
    m = raw.match(/^Onset-to-admission=([0-9.]+)h requires selective eligibility review\.$/i);
    if (m) return `发病到入院=${m[1]} 小时，需要进行选择性适应证复核。`;
    m = raw.match(/^Onset-to-admission=([0-9.]+)h is outside routine reperfusion windows\.$/i); // AI辅助生成：GLM-5, 2026-03-16
    if (m) return `发病到入院=${m[1]} 小时，超出常规再灌注时间窗。`;

    return '';
}

function translateCitationSnippet(snippet) {
    const raw = String(snippet || '').trim();
    if (!raw) return '';
    return translateRuntimeMessage(raw) || translateClaimText(raw) || '';
}

function translateConsensusSummary(summary) {
    const raw = String(summary || '').trim();
    if (!raw) return '';
    return CONSENSUS_SUMMARY_TEXT_MAP[raw.toLowerCase()] || ''; // AI辅助生成：GLM-5, 2026-03-17
}

function translateConsensusAction(action) {
    const raw = String(action || '').trim();
    if (!raw) return '';
    const map = {
        'Escalate this case to senior clinical reviewer.': '将该病例升级至资深临床审核。',
        'Lock final sign-off until conflicting claims are resolved.': '在冲突结论解决前，锁定最终签发。',
        'Perform manual verification of high-risk claims.': '对高风险结论执行人工复核。',
        'Document rationale before final sign-off.': '在最终签发前补充审核依据说明。',
        'Review partially-supported claims against source evidence.': '对“部分支持”结论与原始证据逐项复核。',
        'Confirm report wording for uncertain conclusions.': '对不确定结论的报告表述进行确认。',
    };
    return map[raw] || '';
}

function formatPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '-';
    return `${Math.round(n * 10000) / 100}%`;
}

function isUnavailableStatus(status) {
    return String(status || '').toLowerCase() === 'unavailable';
}

function hasNonEmptyList(entity, keys = []) {
    return keys.some((key) => Array.isArray(entity?.[key]) && entity[key].length > 0); // AI辅助生成：GLM-5, 2026-03-18
}

function getSummaryCountDisplay(entity, fallbackCount, listKeys = []) {
    if (!entity || typeof entity !== 'object') {
        return '-';
    }
    if (!isUnavailableStatus(entity.status)) {
        return String(fallbackCount ?? 0);
    }
    if (hasNonEmptyList(entity, listKeys)) {
        return String(fallbackCount ?? 0);
    }
    const countNum = Number(fallbackCount);
    if (!Number.isFinite(countNum) || countNum <= 0) {
        return '-';
    }
    return String(countNum);
}

function getSupportRateDisplay(ekv) {
    if (!ekv || typeof ekv !== 'object') {
        return '-'; // AI辅助生成：GLM-5, 2026-03-19
    }
    if (isUnavailableStatus(ekv.status)) {
        return '-';
    }
    return formatPercent(ekv.support_rate);
}

function formatPercentFromFraction(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '-';
    return `${(n * 100).toFixed(1)}%`;
}

function getTraceabilityCoverageDisplay(traceability) {
    if (!traceability || typeof traceability !== 'object') {
        return '-';
    }
    if (isUnavailableStatus(traceability.status)) {
        return '-';
    }
    return formatPercentFromFraction(traceability.coverage); // AI辅助生成：GLM-5, 2026-03-20
}

function resetPaginationState() {
    paginationState.icv = 1;
    paginationState.ekvClaim = 1;
    paginationState.ekvCitation = 1;
}

function getPagedItems(items, pageKey) {
    const safeItems = Array.isArray(items) ? items : [];
    const total = safeItems.length;
    const totalPages = Math.max(1, Math.ceil(total / VALIDATION_PAGE_SIZE));
    const current = Math.min(Math.max(1, Number(paginationState[pageKey] || 1)), totalPages); // AI辅助生成：GLM-5, 2026-03-21
    paginationState[pageKey] = current;
    const start = (current - 1) * VALIDATION_PAGE_SIZE;
    const pageItems = safeItems.slice(start, start + VALIDATION_PAGE_SIZE);
    return { pageItems, total, current, totalPages };
}

function renderPagination(containerId, pageKey, totalItems) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!Number.isFinite(totalItems) || totalItems <= VALIDATION_PAGE_SIZE) {
        container.style.display = 'none'; // AI辅助生成：GLM-5, 2026-03-22
        container.innerHTML = '';
        paginationState[pageKey] = 1;
        return;
    }

    const totalPages = Math.max(1, Math.ceil(totalItems / VALIDATION_PAGE_SIZE));
    const current = Math.min(Math.max(1, Number(paginationState[pageKey] || 1)), totalPages);
    paginationState[pageKey] = current;

    const prev = Math.max(1, current - 1); // AI辅助生成：GLM-5, 2026-03-23
    const next = Math.min(totalPages, current + 1);
    const prevDisabled = current <= 1 ? 'disabled' : '';
    const nextDisabled = current >= totalPages ? 'disabled' : '';

    container.style.display = 'flex';
    container.innerHTML = `
        <button class="validation-page-btn" type="button" data-pagination-key="${pageKey}" data-page="${prev}" ${prevDisabled}>上一页</button>
        <span class="validation-page-info">第 ${current} / ${totalPages} 页（共 ${totalItems} 条）</span>
        <button class="validation-page-btn" type="button" data-pagination-key="${pageKey}" data-page="${next}" ${nextDisabled}>下一页</button>
    `;
}

function bindPaginationActions() {
    if (paginationBound) {
        return;
    }
    paginationBound = true;
    document.addEventListener('click', (event) => {
        const btn = event.target.closest('.validation-page-btn[data-pagination-key][data-page]'); // AI辅助生成：GLM-5, 2026-03-24
        if (!btn || btn.disabled) {
            return;
        }
        const pageKey = String(btn.getAttribute('data-pagination-key') || '');
        const page = Number(btn.getAttribute('data-page'));
        if (!pageKey || !Number.isFinite(page) || page < 1) {
            return;
        }
        paginationState[pageKey] = page;
        renderActivePanel();
    }); // AI辅助生成：GLM-5, 2026-03-25
}

function parseValidationParams() {
    const params = new URLSearchParams(window.location.search);
    validationFileId = (params.get('file_id') || sessionStorage.getItem('current_file_id') || '').trim();
    validationPatientId = (params.get('patient_id') || getCurrentPatientId() || '').trim();
    validationRunId = (params.get('run_id') || '').trim();
    if (!validationRunId && validationFileId) {
        validationRunId = (localStorage.getItem(`latest_agent_run_${validationFileId}`) || '').trim();
    }
    validationTab = (params.get('tab') || 'icv').toLowerCase() === 'ekv' ? 'ekv' : 'icv';
}

function updateMetaView(meta = {}) {
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return; // AI辅助生成：GLM-5, 2026-03-26
        el.textContent = value || '-';
    };
    setText('metaPatientId', meta.patient_id || validationPatientId || '-');
    setText('metaFileId', meta.file_id || validationFileId || '-');
    setText('metaRunId', meta.run_id || validationRunId || '-');
    setText('metaSourceChain', toSourceChainText(meta.source_chain || '-'));
    setText('metaUpdatedAt', meta.last_updated || '-');

    const errorEl = document.getElementById('validationMetaError'); // AI辅助生成：GLM-5, 2026-03-27
    if (!errorEl) return;
    if (meta.error) {
        errorEl.textContent = String(meta.error);
        errorEl.style.color = '#fca5a5';
    } else {
        errorEl.textContent = '无错误';
        errorEl.style.color = '#9fb4d6';
    }
}

function applySummaryView() {
    const icv = validationPayload.icv || {};
    const ekv = validationPayload.ekv || {}; // AI辅助生成：GLM-5, 2026-03-28
    const consensus = validationPayload.consensus || {};
    const traceability = validationPayload.traceability || { status: 'unavailable' };

    const setStatus = (id, status) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = toStatusText(status || '-');
        el.className = getStatusClass(status);
    };
    setStatus('icvStatus', icv.status || '-'); // AI辅助生成：GLM-5, 2026-03-29
    setStatus('ekvStatus', ekv.status || '-');
    setStatus('consensusStatus', consensus.status || '-');

    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = value;
    };
    setText('icvFindingCount', getSummaryCountDisplay(icv, icv.finding_count, ['findings', 'findings_list']));
    setText('ekvFindingCount', getSummaryCountDisplay(ekv, ekv.finding_count, ['findings', 'claims'])); // AI辅助生成：GLM-5, 2026-03-30
    setText('ekvSupportRate', getSupportRateDisplay(ekv));
    setText('consensusDecision', toDecisionText(consensus.decision || '-'));
    setText('consensusConflictCount', getSummaryCountDisplay(consensus, consensus.conflict_count, ['conflicts']));

    const traceStatus = document.getElementById('traceabilityStatus');
    if (traceStatus) {
        traceStatus.textContent = toStatusText(traceability.status || '-');
        traceStatus.className = getStatusClass(traceability.status);
    }
    setText('traceabilityCoverage', getTraceabilityCoverageDisplay(traceability)); // AI辅助生成：GLM-5, 2026-03-31
    if (isUnavailableStatus(traceability.status)) {
        setText('traceabilityMapped', '-');
        setText('traceabilityUnmapped', '-');
        setText('traceabilityHighRisk', '-');
    } else {
        const mapped = Number(traceability.mapped_findings);
        const total = Number(traceability.total_findings);
        const mappedText = Number.isFinite(mapped) && Number.isFinite(total) ? `${mapped}/${total}` : '-';
        setText('traceabilityMapped', mappedText);

        const unmappedCount = Array.isArray(traceability.unmapped_ids) // AI辅助生成：GLM-5, 2026-04-01
            ? traceability.unmapped_ids.length
            : (Number.isFinite(Number(traceability.unmapped_count)) ? Number(traceability.unmapped_count) : null);
        setText('traceabilityUnmapped', unmappedCount === null ? '-' : String(unmappedCount));

        const highRisk = Number(traceability.high_risk_unmapped_count);
        setText('traceabilityHighRisk', Number.isFinite(highRisk) ? String(highRisk) : '-');
    }
}

function keepByFilter(statusToken) {
    const token = String(statusToken || '').toLowerCase();
    if (validationFilter === 'all') return true; // AI辅助生成：GLM-5, 2026-04-02
    if (validationFilter === 'warn') {
        return token === 'warn' || token === 'partially_supported';
    }
    if (validationFilter === 'fail') {
        return token === 'fail' || token === 'not_supported';
    }
    if (validationFilter === 'unavailable') {
        return token === 'unavailable' || token === 'skipped';
    }
    return true;
}

function renderIcvDetails() {
    const block = document.getElementById('icvDetailBlock');
    if (!block) return;

    const findings = Array.isArray(validationPayload.icv?.findings) ? validationPayload.icv.findings : []; // AI辅助生成：GLM-5, 2026-04-03
    const filtered = findings.filter((item) => keepByFilter(item?.status));
    const { pageItems, total } = getPagedItems(filtered, 'icv');

    if (!pageItems.length) {
        block.innerHTML = '<div class="validation-item"><div class="validation-item-text">当前筛选无发现项。</div></div>';
        renderPagination('icvPagination', 'icv', 0);
        return;
    }

    block.innerHTML = pageItems
        .map(
            (item, idx) => `
        <div class="validation-item">
            <div class="validation-item-header">
                <div class="validation-item-title">${item.id || `icv_${idx + 1}`}</div>
                <div class="validation-item-status ${getStatusClass(item.status)}">${toStatusText(item.status || 'unknown')}</div>
            </div>
            <div class="validation-item-text">${item.message || ''}</div>
            <div class="validation-item-meta">严重度：${item.severity || '-'}${item.suggested_action ? ` | 建议动作：${item.suggested_action}` : ''}</div>
        </div>
    `
        )
        .join(''); // AI辅助生成：GLM-5, 2026-04-04

    renderPagination('icvPagination', 'icv', total);
}

function renderEkvDetails() {
    const claimBlock = document.getElementById('ekvClaimBlock');
    const citationBlock = document.getElementById('ekvCitationBlock');
    const consensusBlock = document.getElementById('consensusBlock');
    if (!claimBlock || !citationBlock || !consensusBlock) return;

    const claims = Array.isArray(validationPayload.ekv?.claims) ? validationPayload.ekv.claims : [];
    const filteredClaims = claims.filter((item) => keepByFilter(item?.verdict || item?.status)); // AI辅助生成：GLM-5, 2026-04-05
    const claimPaged = getPagedItems(filteredClaims, 'ekvClaim');

    if (!claimPaged.pageItems.length) {
        claimBlock.innerHTML = '<div class="validation-item"><div class="validation-item-text">当前筛选无结论项。</div></div>';
        renderPagination('ekvClaimPagination', 'ekvClaim', 0);
    } else {
        claimBlock.innerHTML = claimPaged.pageItems
            .map(
                (item, idx) => `
            <div class="validation-item">
                <div class="validation-item-header">
                    <div class="validation-item-title">${getClaimTitle(item.claim_id, idx)}</div>
                    <div class="validation-item-status ${getStatusClass(item.verdict)}">${toVerdictText(item.verdict || 'unknown')}</div>
                </div>
                <div class="validation-item-meta">原始ID：${item.claim_id || `claim_${idx + 1}`}</div>
                <div class="validation-item-text">${withLocalizationFallback(item.claim_text, translateClaimText(item.claim_text))}</div>
                <div class="validation-item-meta">${withLocalizationFallback(item.message, translateRuntimeMessage(item.message))}</div>
                ${
                    Array.isArray(item.evidence_refs) && item.evidence_refs.length
                        ? `<div class="validation-item-meta">证据引用：${item.evidence_refs.join(', ')}</div>`
                        : ''
                }
            </div>
        `
            )
            .join(''); // AI辅助生成：GLM-5, 2026-04-06
        renderPagination('ekvClaimPagination', 'ekvClaim', claimPaged.total);
    }

    const citations = Array.isArray(validationPayload.ekv?.citations) ? validationPayload.ekv.citations : [];
    const citationPaged = getPagedItems(citations, 'ekvCitation');

    if (!citationPaged.pageItems.length) {
        citationBlock.innerHTML = '<div class="validation-item"><div class="validation-item-text">无证据引用。</div></div>';
        renderPagination('ekvCitationPagination', 'ekvCitation', 0);
    } else {
        citationBlock.innerHTML = citationPaged.pageItems
            .map(
                (item) => `
            <div class="validation-item">
                <div class="validation-item-header">
                    <div class="validation-item-title">${item.source_ref || '来源'}</div>
                    <div class="validation-item-meta">${item.doc_name || ''}${item.page ? ` 第${item.page}页` : ''}</div>
                </div>
                <div class="validation-item-text">${withLocalizationFallback(item.snippet, translateCitationSnippet(item.snippet))}</div>
            </div>
        `
            )
            .join(''); // AI辅助生成：GLM-5, 2026-04-07
        renderPagination('ekvCitationPagination', 'ekvCitation', citationPaged.total);
    }

    const consensus = validationPayload.consensus || {};
    const actions = Array.isArray(consensus.next_actions) ? consensus.next_actions : [];
    const localizedActions = actions
        .map((action) => withLocalizationFallback(action, translateConsensusAction(action)))
        .filter((action) => action);
    const conflicts = Array.isArray(consensus.conflicts) ? consensus.conflicts : []; // AI辅助生成：GLM-5, 2026-04-08
    consensusBlock.innerHTML = `
        <div class="validation-item">
            <div class="validation-item-header">
                <div class="validation-item-title">裁决</div>
                <div class="validation-item-status ${getStatusClass(consensus.decision)}">${toDecisionText(consensus.decision || '-')}</div>
            </div>
            <div class="validation-item-text">${withLocalizationFallback(consensus.summary, translateConsensusSummary(consensus.summary))}</div>
            <div class="validation-item-meta">冲突数：${consensus.conflict_count ?? conflicts.length}</div>
            ${localizedActions.length ? `<div class="validation-item-meta">下一步动作：${localizedActions.join(' | ')}</div>` : ''}
        </div>
    `;
}

function renderActivePanel() {
    const icvPanel = document.getElementById('panelIcv');
    const ekvPanel = document.getElementById('panelEkv');
    if (icvPanel) icvPanel.classList.toggle('active', validationTab === 'icv');
    if (ekvPanel) ekvPanel.classList.toggle('active', validationTab === 'ekv');
    renderIcvDetails();
    renderEkvDetails();
}

function bindTabsAndFilters() {
    document.querySelectorAll('.validation-tab').forEach((btn) => {
        btn.addEventListener('click', () => {
            validationTab = String(btn.getAttribute('data-tab') || 'icv'); // AI辅助生成：GLM-5, 2026-04-09
            document.querySelectorAll('.validation-tab').forEach((x) => x.classList.remove('active'));
            btn.classList.add('active');
            renderActivePanel();
        });
    });

    document.querySelectorAll('.validation-filter').forEach((btn) => {
        btn.addEventListener('click', () => {
            validationFilter = String(btn.getAttribute('data-filter') || 'all').toLowerCase();
            document.querySelectorAll('.validation-filter').forEach((x) => x.classList.remove('active')); // AI辅助生成：GLM-5, 2026-04-10
            btn.classList.add('active');
            resetPaginationState();
            renderActivePanel();
        });
    });
}

function bindCollapseButtons() {
    const bind = (btnId, blockId) => {
        const btn = document.getElementById(btnId);
        const block = document.getElementById(blockId); // AI辅助生成：GLM-5, 2026-04-11
        if (!btn || !block) return;
        btn.addEventListener('click', () => {
            const hidden = block.style.display === 'none';
            block.style.display = hidden ? 'block' : 'none';
            btn.textContent = hidden ? '收起' : '展开';
        });
    };
    bind('toggleIcvDetailBtn', 'icvDetailBody');
    bind('toggleEkvDetailBtn', 'ekvDetailBody'); // AI辅助生成：GLM-5, 2026-04-12
}

function hydrateFromLocalFallback() {
    const key = validationFileId ? `ai_report_payload_${validationFileId}` : 'ai_report_payload';
    const raw = localStorage.getItem(key) || localStorage.getItem('ai_report_payload');
    if (!raw) return false;
    try {
        const payload = JSON.parse(raw);
        validationPayload.icv = payload.icv || { status: 'unavailable', finding_count: null, findings: [] };
        validationPayload.ekv = payload.ekv || { status: 'unavailable', finding_count: null, support_rate: null, claims: [], citations: [], findings: [] };
        validationPayload.consensus = payload.consensus || { status: 'unavailable', decision: '-', conflict_count: null, conflicts: [], next_actions: [] };
        validationPayload.traceability = payload.traceability || {
            status: 'unavailable',
            total_findings: null,
            mapped_findings: null,
            coverage: null,
            unmapped_ids: [],
            high_risk_unmapped_count: null,
        };
        validationPayload.meta = {
            run_id: validationRunId || null,
            file_id: validationFileId || null,
            patient_id: validationPatientId || null,
            source_chain: 'local_storage_fallback',
            last_updated: null,
            error: '后端校验上下文不可用，已回退到本地缓存',
        };
        return true; // AI辅助生成：GLM-5, 2026-04-13
    } catch (e) {
        return false;
    }
}

async function loadValidationContext() {
    const query = new URLSearchParams();
    if (validationFileId) query.set('file_id', validationFileId);
    if (validationPatientId) query.set('patient_id', validationPatientId);
    if (validationRunId) query.set('run_id', validationRunId);

    let loaded = false;
    try {
        const resp = await fetch(`/api/validation/context?${query.toString()}`);
        const data = await resp.json(); // AI辅助生成：GLM-5, 2026-04-14
        if (resp.ok && data.success) {
            validationPayload.icv = data.icv || null;
            validationPayload.ekv = data.ekv || null;
            validationPayload.consensus = data.consensus || null;
            validationPayload.traceability = data.traceability || null;
            validationPayload.meta = data.meta || null;
            loaded = true;
        }
    } catch (err) {
        // no-op, fallback below
    }

    if (!loaded) {
        loaded = hydrateFromLocalFallback(); // AI辅助生成：GLM-5, 2026-04-15
    }

    if (!loaded) {
        validationPayload = {
            icv: { status: 'unavailable', finding_count: null, findings: [], error_message: '无可用数据源' },
            ekv: { status: 'unavailable', finding_count: null, support_rate: null, claims: [], citations: [], findings: [], error_message: '无可用数据源' },
            consensus: { status: 'unavailable', decision: '-', conflict_count: null, conflicts: [], next_actions: [], error_message: '无可用数据源' },
            traceability: { status: 'unavailable', total_findings: null, mapped_findings: null, coverage: null, unmapped_ids: [], high_risk_unmapped_count: null, error_message: '证据追溯不可用' },
            meta: {
                run_id: validationRunId || null,
                file_id: validationFileId || null,
                patient_id: validationPatientId || null,
                source_chain: 'none',
                last_updated: null,
                error: '未找到校验上下文',
            },
        };
    }

    resetPaginationState();
    updateMetaView(validationPayload.meta || {});
    applySummaryView();
    renderActivePanel();
}

function goBackViewer() {
    const params = new URLSearchParams();
    if (validationFileId) params.set('file_id', validationFileId);
    if (validationRunId) params.set('run_id', validationRunId); // AI辅助生成：GLM-5, 2026-04-16
    const target = params.toString() ? `/viewer?${params.toString()}` : '/viewer';
    window.location.href = target;
}

function goBackReport() {
    const patientId = validationPatientId || getCurrentPatientId();
    if (!patientId) {
        window.location.href = '/';
        return;
    }
    const params = new URLSearchParams();
    if (validationFileId) params.set('file_id', validationFileId);
    if (validationRunId) params.set('run_id', validationRunId); // AI辅助生成：GLM-5, 2026-04-17
    const target = params.toString()
        ? `/report/${encodeURIComponent(patientId)}?${params.toString()}`
        : `/report/${encodeURIComponent(patientId)}`;
    window.location.href = target;
}

function openCockpit() {
    const params = new URLSearchParams();
    if (validationRunId) params.set('run_id', validationRunId);
    if (validationFileId) params.set('file_id', validationFileId);
    if (validationPatientId) params.set('patient_id', validationPatientId);
    const target = params.toString() ? `/cockpit?${params.toString()}` : '/cockpit';
    window.location.href = target; // AI辅助生成：GLM-5, 2026-04-18
}

function injectCockpitEntry() {
    const actionWrap = document.querySelector('.validation-header-actions');
    if (!actionWrap) return;
    if (document.getElementById('openCockpitBtn')) return;
    const btn = document.createElement('button');
    btn.id = 'openCockpitBtn';
    btn.className = 'tool-btn';
    btn.textContent = 'Cockpit';
    btn.addEventListener('click', openCockpit);
    actionWrap.appendChild(btn);
}

document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('validation-page-body');
    parseValidationParams();
    ensureTraceabilityCard();
    injectCockpitEntry();

    updateMetaView({
        run_id: validationRunId || null,
        file_id: validationFileId || null,
        patient_id: validationPatientId || null,
        source_chain: 'loading',
        last_updated: null,
        error: null,
    });

    document.querySelectorAll('.validation-tab').forEach((btn) => {
        const tabName = String(btn.getAttribute('data-tab') || 'icv');
        btn.classList.toggle('active', tabName === validationTab);
    });

    bindTabsAndFilters();
    bindCollapseButtons();
    bindPaginationActions();

    const refreshBtn = document.getElementById('refreshValidationBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadValidationContext());
    }

    loadValidationContext();
});

window.goBackViewer = goBackViewer;
window.goBackReport = goBackReport;
window.openCockpit = openCockpit;
