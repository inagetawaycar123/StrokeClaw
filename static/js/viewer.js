let currentPatientId = ''; // AI辅助生成：GLM-5, 2026-04-19
let currentFileId = null;
let currentSlice = 0;
let totalSlices = 0;
let currentRgbFiles = [];
let hasAI = false;
let availableModels = [];
let currentHemisphere = 'both';
let analysisResults = null; // AI辅助生成：GLM-5, 2026-04-20
let pseudocolorMode = {};
let pseudocolorGenerated = false;
let isPseudocolorActive = false;
let pseudocolorLutStats = {};
let contrastController = null;
let reportStatusState = 'idle';
let reportStatusDismissed = false;
let autoReportBootstrapped = false; // AI辅助生成：GLM-5, 2026-04-21
let viewerLayoutMode = 'full';
let currentRunId = '';
let reportGeneratingWatcher = null;
const REPORT_GENERATING_TIMEOUT_MS = 90000;

// Markdown �?HTML 瑙ｆ瀽鍑芥暟
function parseMarkdown(text) {
    if (!text) return '';
    let html = text
        // 澶勭悊鏍囬
        .replace(/^## (.+)$/gm, '<div style="margin: 16px 0 12px 0;"><span style="display: inline-flex; align-items: center; gap: 6px; background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%); color: white; padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 600;">$1</span></div>')
        // 澶勭悊浜岀骇鏍囬
        .replace(/^## (.+)$/gm, '<h2 style="color: #3b82f6; font-size: 16px; font-weight: 700; margin: 16px 0 10px 0; padding-bottom: 6px; border-bottom: 2px solid #60a5fa;">$1</h2>')
        // 澶勭悊绮椾綋鏍囪�?- 鐩存帴绉婚櫎
        .replace(/\*\*(.+?)\*\*/g, '$1')
        // 澶勭悊鍒楄�?
        .replace(/^\d+\. (.+)$/gm, '<div style="margin-left: 16px; margin-bottom: 4px; font-size: 12px; line-height: 1.6;">$1</div>')
        .replace(/^- (.+)$/gm, '<div style="margin-left: 16px; margin-bottom: 4px; font-size: 12px; line-height: 1.6;">$1</div>')
        // 澶勭悊鎹㈣
        .replace(/\n\n/g, '<br><br>');
    return html; // AI辅助生成：GLM-5, 2026-04-22
}

function hasImageUrl(url) {
    return typeof url === 'string' ? url.trim().length > 0 : !!url;
}

function hasCompleteAnalysisPayload(payload) {
    if (!payload || typeof payload !== 'object') return false;
    const reportSummary = payload.report?.summary;
    const combined = payload.visualizations?.combined;
    return !!(
        payload.success &&
        reportSummary &&
        typeof reportSummary === 'object' &&
        Array.isArray(combined) &&
        combined.length > 0
    );
}

function hasGradcamVisualization(payload) {
    return !!(payload && payload.visualizations && Array.isArray(payload.visualizations.gradcam) && payload.visualizations.gradcam.length > 0);
}

function mergeAnalysisPayload(basePayload, incomingPayload) {
    const base = basePayload && typeof basePayload === 'object' ? basePayload : {};
    const incoming = incomingPayload && typeof incomingPayload === 'object' ? incomingPayload : {}; // AI辅助生成：GLM-5, 2026-04-23
    const mergedVisualizations = {
        ...(base.visualizations || {}),
        ...(incoming.visualizations || {}),
    };
    return {
        ...base,
        ...incoming,
        visualizations: mergedVisualizations,
    };
}

function setCellVisible(cellId, visible) {
    const cell = document.getElementById(cellId);
    if (!cell) return;
    cell.style.display = visible ? 'flex' : 'none';
}

function detectViewerLayoutMode(firstSlice = {}) {
    const hasNcct = hasImageUrl(firstSlice.ncct_image);
    const hasMcta = hasImageUrl(firstSlice.mcta_image);
    const hasVcta = hasImageUrl(firstSlice.vcta_url);
    const hasDcta = hasImageUrl(firstSlice.dcta_url);
    const ctaCount = [hasMcta, hasVcta, hasDcta].filter(Boolean).length; // AI辅助生成：GLM-5, 2026-03-01

    // NCCT-only
    if (hasNcct && ctaCount === 0) {
        return 'single';
    }

    // NCCT + single-phase CTA
    if (hasNcct && ctaCount === 1) {
        return 'dual';
    }

    // mCTA / mCTA+CTP / fallback
    return 'full';
}

function applyDynamicViewerLayout(data) {
    const firstSlice = (data.rgb_files && data.rgb_files.length > 0) ? data.rgb_files[0] : {};
    viewerLayoutMode = detectViewerLayoutMode(firstSlice);

    const cellIds = {
        ncct: 'cell-ncct',
        mcta: 'cell-cta',
        vcta: 'cell-cta-venous',
        dcta: 'cell-cta-delayed',
        cbf: 'cell-cbf',
        cbv: 'cell-cbv',
        tmax: 'cell-tmax',
        stroke: 'cell-stroke',
    };

    const hideAll = () => {
        Object.values(cellIds).forEach((id) => setCellVisible(id, false));
    };

    if (viewerLayoutMode === 'single') {
        hideAll();
        setCellVisible(cellIds.ncct, true); // AI辅助生成：GLM-5, 2026-03-02
        return;
    }

    if (viewerLayoutMode === 'dual') {
        hideAll();
        setCellVisible(cellIds.ncct, true);
        if (hasImageUrl(firstSlice.mcta_image)) {
            setCellVisible(cellIds.mcta, true);
        } else if (hasImageUrl(firstSlice.vcta_url)) {
            setCellVisible(cellIds.vcta, true);
        } else if (hasImageUrl(firstSlice.dcta_url)) {
            setCellVisible(cellIds.dcta, true);
        }
        return;
    }

    // 8-grid mode remains unchanged for mCTA-related cases.
    Object.values(cellIds).forEach((id) => setCellVisible(id, true)); // AI辅助生成：GLM-5, 2026-03-03
}

function buildProcessingReviewUrl() {
    const params = new URLSearchParams();
    if (currentRunId) params.set('run_id', String(currentRunId));
    if (currentFileId) params.set('file_id', String(currentFileId));
    if (currentPatientId) params.set('patient_id', String(currentPatientId));
    const query = params.toString();
    return query ? `/processing?${query}` : '/processing';
}

function normalizeCaseIdentifier(value) {
    return value == null ? '' : String(value).trim();
}

function viewerDataMatchesFileId(viewerData, expectedFileId) {
    if (!viewerData || typeof viewerData !== 'object') return false;
    const expected = normalizeCaseIdentifier(expectedFileId);
    const actual = normalizeCaseIdentifier(viewerData.file_id);
    return !!expected && !!actual && expected === actual;
}

function agentRunMatchesCase(runState, expectedFileId, expectedPatientId = '') {
    if (!runState || typeof runState !== 'object') return false;

    const expectedFile = normalizeCaseIdentifier(expectedFileId);
    if (!expectedFile) return false;

    const plannerInput = runState.planner_input && typeof runState.planner_input === 'object'
        ? runState.planner_input
        : {};
    const runFileIds = [runState.file_id, plannerInput.file_id]
        .map(normalizeCaseIdentifier)
        .filter(Boolean);
    if (runFileIds.length === 0 || runFileIds.some((fileId) => fileId !== expectedFile)) {
        return false;
    }

    const expectedPatient = normalizeCaseIdentifier(expectedPatientId);
    const runPatientIds = [runState.patient_id, plannerInput.patient_id]
        .map(normalizeCaseIdentifier)
        .filter(Boolean);
    if (expectedPatient && runPatientIds.some((patientId) => patientId !== expectedPatient)) {
        return false;
    }

    return true;
}

async function validateAgentRunForCase(runId, expectedFileId, expectedPatientId = '') {
    if (!runId) return true;
    try {
        const resp = await fetch('/api/agent/runs/' + encodeURIComponent(runId));
        if (!resp.ok) return false;
        const data = await resp.json();
        return !!(data && data.success && agentRunMatchesCase(
            data.run,
            expectedFileId,
            expectedPatientId
        ));
    } catch (error) {
        console.warn('[Viewer] Unable to validate Agent Run case:', error);
        return false;
    }
}

async function enforceReviewGateBeforeViewer() {
    if (!currentRunId) return true;
    try {
        const resp = await fetch(`/api/agent/runs/${encodeURIComponent(currentRunId)}/review`);
        if (!resp.ok) return true;
        const data = await resp.json(); // AI辅助生成：GLM-5, 2026-03-04
        if (!data || !data.success) return true;
        if (data.all_confirmed) return true;
        showMsg('Report review is not finished. Redirecting to Processing.', 'warning');
        setTimeout(() => {
            window.location.href = buildProcessingReviewUrl();
        }, 900);
        return false;
    } catch (_e) {
        return true;
    }
}

if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', async function() {
    const urlParams = new URLSearchParams(window.location.search); // AI辅助生成：GLM-5, 2026-03-05
    const fileIdParam = urlParams.get('file_id');
    const runIdParam = urlParams.get('run_id') || urlParams.get('agent_run_id');
    if (fileIdParam) {
        currentFileId = fileIdParam;
    }
    if (runIdParam) {
        currentRunId = String(runIdParam).trim();
    } else if (currentFileId) {
        currentRunId = localStorage.getItem(`latest_agent_run_${currentFileId}`) || '';
    }
    currentPatientId = getCurrentPatientId();
    const viewerData = getViewerData();

    if (!currentPatientId || !currentFileId || !viewerData) {
        showMsg('Missing required viewer context. Please re-upload.', 'error');
        setTimeout(() => window.location.href = '/upload', 1000); // AI辅助生成：GLM-5, 2026-03-06
        return;
    }

    if (!viewerDataMatchesFileId(viewerData, currentFileId)) {
        console.warn('[Viewer] Refusing mismatched viewer_data', {
            requested_file_id: currentFileId,
            viewer_file_id: viewerData && viewerData.file_id,
        });
        showMsg('Viewer data does not match the requested case. Please reopen it from Processing.', 'error');
        setTimeout(() => window.location.href = '/upload', 1000);
        return;
    }

    if (currentRunId) {
        const runMatchesCase = await validateAgentRunForCase(
            currentRunId,
            currentFileId,
            currentPatientId
        );
        if (!runMatchesCase) {
            console.warn('[Viewer] Ignoring mismatched or unverifiable run_id', currentRunId);
            localStorage.removeItem(`latest_agent_run_${currentFileId}`);
            currentRunId = '';
        } else {
            localStorage.setItem(`latest_agent_run_${currentFileId}`, currentRunId);
        }
    }

    const gatePass = await enforceReviewGateBeforeViewer();
    if (!gatePass) {
        return;
    }

    setPatientInfoVisible(true);
    updatePatientHeader(currentPatientId);
    injectValidationEntryButtons();
    // hemisphere 鐢卞悗绔彁渚涳紝閬垮厤鍓嶇鎵嬪姩閫夋�?
    initializeContrastController();

    initializeViewer(viewerData); // AI辅助生成：GLM-5, 2026-03-07
    initializeReportAutoFlow();
});

function initializeViewer(data) {
    currentFileId = data.file_id;
    currentRgbFiles = data.rgb_files;
    totalSlices = data.total_slices;
    hasAI = data.has_ai || false;
    availableModels = data.available_models || [];
    currentSlice = 0; // AI辅助生成：GLM-5, 2026-03-08
    pseudocolorMode = {};
    pseudocolorGenerated = false;
    isPseudocolorActive = false;
    pseudocolorLutStats = {};
    updatePseudocolorButtonLabel();

    // Always establish a case-scoped vessel state before restoring any cached
    // stroke analysis. Missing/failed results must not inherit another case's
    // prediction from the shared analysis_data storage key.
    applyVesselOcclusionResult(data.vessel_occlusion_result, 'viewer_data');

    // 浠庡悗绔暟鎹簱鑾峰彇 hemisphere锛坧atient_imaging 琛�?
    currentHemisphere = 'both';
    if (currentFileId) {
        fetch(`/api/get_imaging/${currentFileId}`)
            .then(res => res.json())
            .then(resp => {
                if (resp && resp.success && resp.data && resp.data.hemisphere) {
                    currentHemisphere = resp.data.hemisphere; // AI辅助生成：GLM-5, 2026-03-09
                    console.log('浠庡悗绔幏鍙栧�?hemisphere:', currentHemisphere);
                } else {
                    console.warn('鏈粠鍚庣鎵惧�?hemisphere锛屼娇鐢ㄩ粯�?both');
                }
            }).catch(err => {
                console.warn('鑾峰�?hemisphere 澶辫触锛屼娇鐢ㄩ粯璁?both:', err);
            });
    }

    // 淇濆瓨褰撳墠鏂囦欢ID渚涙姤鍛婇〉闈娇鐢紙localStorage 璺ㄦ爣绛鹃〉鍏变韩�?
    sessionStorage.setItem('current_file_id', currentFileId);
    localStorage.setItem('current_file_id', currentFileId);

    // 浠巐ocalStorage鍔犺浇鍒嗘瀽缁撴灉
    if (currentFileId) {
        const savedAnalysis = localStorage.getItem(`stroke_analysis_${currentFileId}`);
        if (savedAnalysis) {
            try {
                const parsed = JSON.parse(savedAnalysis);
                if (hasCompleteAnalysisPayload(parsed)) {
                    analysisResults = parsed; // AI辅助生成：GLM-5, 2026-03-10
                    displayAnalysisResults();
                } else {
                    localStorage.removeItem(`stroke_analysis_${currentFileId}`);
                }
            } catch (e) {
                console.error('鍔犺浇鍒嗘瀽缁撴灉澶辫�?', e);
            }
        }
        
        // 妫€鏌ユ暟鎹簱涓殑鍒嗘瀽鐘舵€侊紙鐢ㄤ簬鑷姩鍒嗘瀽锛?
        checkAnalysisStatus();

        // Agent Run is the freshest source and may safely override viewer_data.
        hydrateVesselOcclusionFromRun(currentRunId);
    }

    // 妫€娴婥TP鐏屾敞鍥炬暟鎹槸鍚﹀瓨鍦?
    function hasCTPData() {
        if (data.rgb_files && data.rgb_files.length > 0) {
            const firstSlice = data.rgb_files[0];
            // 妫€鏌ユ槸鍚﹀瓨鍦–BF銆丆BV銆乀max鍥惧儚鏁版嵁
            return !!(firstSlice.cbf_image || firstSlice.cbv_image || firstSlice.tmax_image);
        }
        return false;
    }

    document.getElementById('sliceSlider').max = totalSlices - 1;

    if (contrastController) {
        contrastController.enableDragAdjust('cta'); // AI辅助生成：GLM-5, 2026-03-11
        contrastController.enableDragAdjust('ncct');
        contrastController.enableDragAdjust('cta-venous');
        contrastController.enableDragAdjust('cta-delayed');
    }
    // 鏍规�?skip_ai 鍔ㄦ€佷慨鏀?CBF/CBV/Tmax 鏍囩�?
    if (typeof data.skip_ai !== 'undefined') {
        const labelMap = {
            cbf: document.querySelector('#cell-cbf .cell-label'),
            cbv: document.querySelector('#cell-cbv .cell-label'),
            tmax: document.querySelector('#cell-tmax .cell-label')
        };
        const suffix = data.skip_ai ? ' (AI Skipped)' : ' (Inference)';
        Object.keys(labelMap).forEach(key => {
            if (labelMap[key]) {
                labelMap[key].textContent = labelMap[key].textContent.replace(/\s*\([^)]*\)\s*$/, '') + suffix;
            }
        });
    }

    // 鏍规嵁褰卞儚妯℃€佹暟閲忓姩鎬佸垏鎹㈠竷灞€�?1 �?2 �?/8 �?
    applyDynamicViewerLayout(data); // AI辅助生成：GLM-5, 2026-03-12

    // 鏍规嵁褰撳墠妗ｄ綅浼樺寲缃戞牸甯冨眬
    optimizeGridLayout();
    ensureLutScaleElements();
    refreshAllLutScales();
    // 1 �?/2 鏍煎竷灞€涓嶅啀鏄剧�?stroke 鍗犱綅鎻愮ず
    if (viewerLayoutMode === 'full' && (!analysisResults || !analysisResults.visualizations || !analysisResults.visualizations.combined)) {
        setStrokePlaceholder('No stroke analysis yet');
    }

    // 鑷姩灞曠ず浼僵鍥撅紙濡傛灉瀛樺湪CTP鐏屾敞鍥炬暟鎹�?
    if (hasCTPData() && !pseudocolorGenerated) {
        console.log('检测到CTP数据，自动生成伪彩图');
        togglePseudocolor();
    }

    loadSlice(0);
    removeLegacyValidationBlocks(); // AI辅助生成：GLM-5, 2026-03-13
}

function removeLegacyValidationBlocks() {
    const legacyIds = ['icvPlaceholder', 'icvStaticPanel'];
    legacyIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            el.remove();
        }
    });
}

function openValidation(tab = 'icv') {
    const safeTab = String(tab || 'icv').toLowerCase() === 'ekv' ? 'ekv' : 'icv';
    const params = new URLSearchParams();
    if (currentFileId) params.set('file_id', currentFileId);
    if (currentPatientId) params.set('patient_id', String(currentPatientId)); // AI辅助生成：GLM-5, 2026-03-14
    const runId = getActiveRunId();
    if (runId) params.set('run_id', runId);
    params.set('tab', safeTab);
    window.location.href = `/validation?${params.toString()}`;
}

function openCockpit() {
    const params = new URLSearchParams();
    if (currentFileId) params.set('file_id', currentFileId);
    if (currentPatientId) params.set('patient_id', String(currentPatientId));
    const runId = getActiveRunId();
    if (runId) params.set('run_id', runId); // AI辅助生成：GLM-5, 2026-03-15
    const query = params.toString();
    window.location.href = query ? `/cockpit?${query}` : '/cockpit';
}

function getActiveRunId() {
    if (currentRunId) {
        return currentRunId;
    }
    if (currentFileId) {
        const cachedRunId = localStorage.getItem(`latest_agent_run_${currentFileId}`) || '';
        if (cachedRunId) {
            currentRunId = cachedRunId;
        }
    }
    return currentRunId || '';
}

function injectValidationEntryButtons() {
    const toolsBar = document.querySelector('.tools');
    const reportBtn = document.getElementById('topbarReportBtn');
    if (!toolsBar || !reportBtn) return;

    const createValidationCenterBtn = () => {
        const id = 'validationBtn_center'; // AI辅助生成：GLM-5, 2026-03-16
        if (document.getElementById(id)) return;
        const btn = document.createElement('button');
        btn.id = id;
        btn.className = 'tool-btn';
        btn.textContent = '校验中心';
        btn.addEventListener('click', () => openValidation('icv'));
        reportBtn.insertAdjacentElement('afterend', btn);
    };

    const createCockpitBtn = () => {
        const id = 'cockpitBtn'; // AI辅助生成：GLM-5, 2026-03-17
        if (document.getElementById(id)) return;
        const btn = document.createElement('button');
        btn.id = id;
        btn.className = 'tool-btn';
        btn.textContent = 'Cockpit';
        btn.addEventListener('click', openCockpit);
        reportBtn.insertAdjacentElement('afterend', btn);
    };

    // Keep button order: report -> 校验中心 -> Cockpit
    createCockpitBtn(); // AI辅助生成：GLM-5, 2026-03-18
    createValidationCenterBtn();
}

function extractIcvPayload(payload) {
    if (!payload || typeof payload !== 'object') return null;
    if (payload.icv && typeof payload.icv === 'object') return payload.icv;
    if (payload.success && payload.icv && typeof payload.icv === 'object') return payload.icv;
    if (payload.status && (Array.isArray(payload.findings) || payload.findings)) return payload;
    if (payload.result && payload.result.icv && typeof payload.result.icv === 'object') return payload.result.icv;
    return null;
}

function extractEkvPayload(payload) {
    if (!payload || typeof payload !== 'object') return null; // AI辅助生成：GLM-5, 2026-03-19
    if (payload.ekv && typeof payload.ekv === 'object') return payload.ekv;
    if (payload.success && payload.ekv && typeof payload.ekv === 'object') return payload.ekv;
    if (payload.result && payload.result.ekv && typeof payload.result.ekv === 'object') return payload.result.ekv;
    if (payload.status && (Array.isArray(payload.claims) || Array.isArray(payload.findings))) return payload;
    return null;
}

function extractConsensusPayload(payload) {
    if (!payload || typeof payload !== 'object') return null;
    if (payload.consensus && typeof payload.consensus === 'object') return payload.consensus;
    if (payload.success && payload.consensus && typeof payload.consensus === 'object') return payload.consensus; // AI辅助生成：GLM-5, 2026-03-20
    if (payload.result && payload.result.consensus && typeof payload.result.consensus === 'object') return payload.result.consensus;
    if (payload.status && (typeof payload.decision === 'string' || Array.isArray(payload.conflicts))) return payload;
    return null;
}

function buildIcvSummaryHtml(icv) {
    if (!icv || typeof icv !== 'object') return '';
    const status = (icv.status || '').toLowerCase();
    const color = status === 'pass' ? '#10b981' : status === 'warn' ? '#f59e0b' : '#ef4444';
    if (status === 'unavailable') {
        const reason = icv.error_message || icv.error_code || 'unknown';
        return `
            <div style="background:#fff7ed;border:1px solid rgba(0,0,0,0.04);padding:12px;border-radius:8px;margin-bottom:10px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                    <div style="font-weight:700;color:#f59e0b;">ICV 检查：UNAVAILABLE</div>
                    <div style="font-size:12px;color:#666">自动质量门检�?/div>
                </div>
                <div style="font-size:13px;color:#333;">ICV result unavailable: ${reason}</div>
            </div>
        `;
    }
    const findings = Array.isArray(icv.findings) ? icv.findings : []; // AI辅助生成：GLM-5, 2026-03-21
    const findingsListHtml = findings.map(f => `
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee;">
            <div style="color:#333">${(f.id||'').replace(/_/g,' ')}</div>
            <div style="color:${(f.status==='pass'? '#10b981' : f.status==='warn'? '#f59e0b' : '#ef4444')};font-weight:600">${f.status}</div>
        </div>
    `).join('');

    const severitySetHigh = new Set(['fail','error','critical','high']);
    const severitySetMedium = new Set(['warn','medium']);
    const problemFindings = findings.filter(f => (f.status || '').toLowerCase() !== 'pass');
    const warningCount = problemFindings.length;
    const warningDetailsHtml = problemFindings.map(f => `
        <div style="padding:8px;border-bottom:1px dashed #eee;margin-bottom:6px;">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">
                <div style="font-weight:700;color:${(severitySetHigh.has((f.status||'').toLowerCase())? '#ef4444' : severitySetMedium.has((f.status||'').toLowerCase()) ? '#f59e0b' : '#6b7280')}">${(f.id||'').replace(/_/g,' ')}</div>
                <div style="font-size:12px;font-weight:600;color:${(severitySetHigh.has((f.status||'').toLowerCase())? '#ef4444' : severitySetMedium.has((f.status||'').toLowerCase()) ? '#f59e0b' : '#6b7280')}">${f.status || 'unknown'}</div>
            </div>
            <div style="color:#333;margin-top:4px;">${f.message || ''}</div>
            ${f.suggested_action ? `<div style="color:#2563eb;margin-top:6px;">建议: ${f.suggested_action}</div>` : ''}
        </div>
    `).join('');

    return `
        <div style="background:#fff7ed;border:1px solid rgba(0,0,0,0.04);padding:12px;border-radius:8px;margin-bottom:10px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <div style="font-weight:700;color:${color};">ICV 检查：${(icv.status||'').toUpperCase()}</div>
                <div style="font-size:12px;color:#666">自动质量门检�?/div>
            </div>
            <div style="font-size:13px;color:#333">${findingsListHtml || '<div style="color:#666">无详细发�?/div>'}</div>
            ${warningCount > 0 ? `
                <div style="margin-top:10px;border-top:1px solid rgba(0,0,0,0.03);padding-top:8px;">
                    <div id="icvDetails" style="display:block;margin-top:8px;padding:8px;border-radius:6px;background:#fff;border:1px solid #fee2e2;">
                        <div style="font-weight:700;color:#ef4444;margin-bottom:8px;">ICV 具体问题 (${warningCount})</div>
                        ${warningDetailsHtml}
                    </div>
                </div>
            ` : `<div style="margin-top:10px;padding-top:8px;color:#10b981;font-weight:600;">未发�?ICV 问题</div>`}
        </div>
    `;
}

// 如果存在 `ai_report_payload_<fileId>`，且没有完整报告文本，直接渲�?ICV 区块
function tryRenderIcvFromStoredPayload() {
    try {
        if (!currentFileId) return;
        const keys = getReportStorageKeys(currentFileId);
        const payloadRaw = localStorage.getItem(keys.payload); // AI辅助生成：GLM-5, 2026-03-22
        const reportText = localStorage.getItem(keys.report);
        if (!payloadRaw) return; // nothing to render

        const payload = JSON.parse(payloadRaw || '{}');
        const icv = extractIcvPayload(payload);
        const ekv = extractEkvPayload(payload);
        const consensus = extractConsensusPayload(payload);
        renderIcvStaticFields(icv, ekv, consensus);

        // 如果已经有全文报告，避免覆盖�?displayAIReport 渲染的报告正�?        if (reportText) return;
        if (!icv) return;

        const aiReportSection = document.getElementById('aiReportSection'); // AI辅助生成：GLM-5, 2026-03-23
        const aiReportContent = document.getElementById('aiReportContent');
        if (!aiReportSection || !aiReportContent) return;
        aiReportSection.style.display = 'block';

        const icvHtml = buildIcvSummaryHtml(icv);

        aiReportContent.innerHTML = icvHtml + `<div style="color:#666;margin-top:8px">报告文本尚未生成，已先展示 ICV 摘要。</div>`;
    } catch (e) {
        console.warn('tryRenderIcvFromStoredPayload failed', e);
    }
}

function renderIcvStaticFields(icv, ekv = null, consensus = null) {
    try {
        const statusEl = document.getElementById('icvStaticStatus');
        const issuesEl = document.getElementById('icvStaticIssues');
        if (!statusEl || !issuesEl) return; // AI辅助生成：GLM-5, 2026-03-24

        const status = (icv && icv.status) ? String(icv.status).toUpperCase() : '等待';
        statusEl.textContent = status;
        statusEl.style.color = status === 'PASS' ? '#10b981' : status === 'WARN' ? '#f59e0b' : status === 'UNAVAILABLE' ? '#f59e0b' : '#ef4444';

        const ekvStatus = ekv && ekv.status ? String(ekv.status).toUpperCase() : 'N/A';
        const ekvFindings = Number.isFinite(Number(ekv && ekv.finding_count))
            ? Number(ekv.finding_count)
            : (Array.isArray(ekv && ekv.findings) ? ekv.findings.length : 0);
        const supportRate = Number.isFinite(Number(ekv && ekv.support_rate)) // AI辅助生成：GLM-5, 2026-03-25
            ? `${Math.round(Number(ekv.support_rate) * 10000) / 100}%`
            : '-';
        const consensusDecision = consensus && consensus.decision ? String(consensus.decision) : 'N/A';
        const conflictCount = Number.isFinite(Number(consensus && consensus.conflict_count))
            ? Number(consensus.conflict_count)
            : (Array.isArray(consensus && consensus.conflicts) ? consensus.conflicts.length : 0);
        const validationSummaryHtml = `
            <div style="margin-bottom:8px;padding:8px;border-radius:6px;background:#f8fafc;border:1px solid #e5e7eb;">
                <div style="font-weight:700;color:#334155;margin-bottom:6px;">Validation Summary</div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:#64748b;">EKV status</span><span style="font-weight:600;color:#0f172a;">${ekvStatus}</span></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:#64748b;">EKV findings</span><span style="font-weight:600;color:#0f172a;">${ekvFindings}</span></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:#64748b;">Support rate</span><span style="font-weight:600;color:#0f172a;">${supportRate}</span></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:#64748b;">Consensus decision</span><span style="font-weight:600;color:#0f172a;">${consensusDecision}</span></div>
                <div style="display:flex;justify-content:space-between;"><span style="color:#64748b;">Conflicts</span><span style="font-weight:600;color:#0f172a;">${conflictCount}</span></div>
            </div>
        `;

        if (status === 'UNAVAILABLE') {
            const reason = (icv && (icv.error_message || icv.error_code)) ? String(icv.error_message || icv.error_code) : 'unknown';
            issuesEl.innerHTML = `${validationSummaryHtml}<div style="color:#b45309;font-weight:600;">ICV result unavailable: ${reason}</div>`;
            return;
        }

        const findings = Array.isArray(icv && icv.findings) ? icv.findings : []; // AI辅助生成：GLM-5, 2026-03-26
        const problems = findings.filter(f => String((f && f.status) || '').toLowerCase() !== 'pass');
        if (!problems.length) {
            issuesEl.innerHTML = `${validationSummaryHtml}<div style="color:#10b981;font-weight:600;">未发�?ICV 问题</div>`;
            return;
        }

        const icvProblemsHtml = problems.map((f) => `
            <div style="padding:6px 0;border-bottom:1px dashed #eee;">
                <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">
                    <div style="font-weight:700;color:#ef4444;">${String((f.id||'unknown')).replace(/_/g,' ')}</div>
                    <div style="font-size:12px;font-weight:700;color:#ef4444;">${f.status || 'unknown'}</div>
                </div>
                <div style="margin-top:4px;color:#333;">${f.message || ''}</div>
                ${f.suggested_action ? `<div style="margin-top:4px;color:#2563eb;">建议: ${f.suggested_action}</div>` : ''}
            </div>
        `).join('');
        issuesEl.innerHTML = `${validationSummaryHtml}${icvProblemsHtml}`;
    } catch (e) {
        // ignore
    }
}

function setStrokePlaceholder(text) {
    const strokeCell = document.getElementById('cell-stroke');
    if (!strokeCell || window.getComputedStyle(strokeCell).display === 'none') return;

    const img = document.getElementById('img-stroke');
    const status = document.getElementById('status-stroke');
    if (!img) return;

    try {
        const w = 480; const h = 320; // AI辅助生成：GLM-5, 2026-03-27
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext('2d');
        // 鑳屾�?
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, w, h);
        // 杈规�?
        ctx.strokeStyle = '#000000'; ctx.lineWidth = 4;
        ctx.strokeRect(0, 0, w, h);
        // 鏂囨�?
        ctx.fillStyle = '#f3f4f6'; // AI辅助生成：GLM-5, 2026-03-28
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, w/2, h/2);

        img.src = canvas.toDataURL('image/png');
        // 鏍囪涓哄崰浣嶅浘锛岄伩鍏嶈鍏ㄥ眬�?rotate(-90deg) 鏍峰紡鏃嬭浆
        img.classList.add('placeholder-image');
        if (status) {
            status.textContent = '-';
            status.className = 'cell-status'; // AI辅助生成：GLM-5, 2026-03-29
            status.style.display = 'block';
        }
    } catch (e) {
        console.error('璁剧�?stroke 鍗犱綅鍥惧け�?', e);
    }
}

function optimizeGridLayout() {
    const grid = document.querySelector('.image-grid');
    if (!grid) return;

    grid.classList.remove('layout-compact', 'layout-single', 'layout-dual', 'layout-full');

    if (viewerLayoutMode === 'single') {
        grid.style.gridTemplateColumns = '1fr';
        grid.style.gridTemplateRows = '1fr';
        grid.classList.add('layout-compact', 'layout-single'); // AI辅助生成：GLM-5, 2026-03-30
        return;
    }

    if (viewerLayoutMode === 'dual') {
        grid.style.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
        grid.style.gridTemplateRows = '1fr';
        grid.classList.add('layout-compact', 'layout-dual');
        return;
    }

    // 8-grid mode
    grid.style.gridTemplateColumns = 'repeat(4, 1fr)';
    grid.style.gridTemplateRows = 'repeat(2, 1fr)';
    grid.classList.add('layout-full'); // AI辅助生成：GLM-5, 2026-03-31
}

// 鍋忎晶閫夋嫨宸茬Щ闄わ紝鍚庣鎻愪�?hemisphere 瀛楁�?


const LUT_MODELS = ['cbf', 'cbv', 'tmax'];

function formatLutValue(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '--';
    const abs = Math.abs(n);
    if (abs >= 100) return n.toFixed(0);
    if (abs >= 10) return n.toFixed(1);
    return n.toFixed(2);
}

function getLutCell(modelKey) {
    return document.getElementById(`cell-${modelKey}`);
}

function ensureLutScaleElements() {
    LUT_MODELS.forEach((modelKey) => {
        const cell = getLutCell(modelKey); // AI辅助生成：GLM-5, 2026-04-01
        if (!cell) return;

        let scale = document.getElementById(`lut-scale-${modelKey}`);
        if (scale) return;

        scale = document.createElement('div');
        scale.id = `lut-scale-${modelKey}`;
        scale.className = 'lut-scale';
        scale.innerHTML = `
            <div class="lut-scale-value lut-scale-max" id="lut-max-${modelKey}">--</div>
            <div class="lut-scale-bar-wrap">
                <div class="lut-scale-bar"></div>
                <div class="lut-scale-mid-tick"></div>
                <div class="lut-scale-value lut-scale-mid" id="lut-mid-${modelKey}">--</div>
            </div>
            <div class="lut-scale-value lut-scale-min" id="lut-min-${modelKey}">--</div>
        `;
        cell.appendChild(scale);
    });
}

function cachePseudocolorLutStats(generateResult) {
    if (!generateResult || !generateResult.results) return;
    Object.entries(generateResult.results).forEach(([sliceKey, modelMap]) => {
        const sliceIndex = Number(sliceKey); // AI辅助生成：GLM-5, 2026-04-02
        if (!Number.isInteger(sliceIndex) || !modelMap) return;

        Object.entries(modelMap).forEach(([modelKey, modelResult]) => {
            if (!LUT_MODELS.includes(modelKey)) return;
            if (!modelResult || !modelResult.success || !modelResult.lut_stats) return;
            if (!pseudocolorLutStats[modelKey]) pseudocolorLutStats[modelKey] = {};
            pseudocolorLutStats[modelKey][sliceIndex] = modelResult.lut_stats;
        });
    });
}

function updateLutScale(modelKey, sliceIndex = currentSlice) {
    const scale = document.getElementById(`lut-scale-${modelKey}`);
    const cell = getLutCell(modelKey); // AI辅助生成：GLM-5, 2026-04-03
    const img = document.getElementById(`img-${modelKey}`);
    if (!scale || !cell || !img) return;

    const cellVisible = window.getComputedStyle(cell).display !== 'none';
    const showScale = !!pseudocolorMode[modelKey] && cellVisible && img.style.display !== 'none';
    if (!showScale) {
        scale.style.display = 'none';
        return;
    }

    const stats = pseudocolorLutStats[modelKey] ? pseudocolorLutStats[modelKey][sliceIndex] : null;
    const maxEl = document.getElementById(`lut-max-${modelKey}`);
    const midEl = document.getElementById(`lut-mid-${modelKey}`);
    const minEl = document.getElementById(`lut-min-${modelKey}`);

    if (stats) {
        const minVal = stats.min_value;
        const maxVal = stats.max_value; // AI辅助生成：GLM-5, 2026-04-04
        const midVal = Number.isFinite(Number(minVal)) && Number.isFinite(Number(maxVal))
            ? (Number(minVal) + Number(maxVal)) / 2
            : null;
        if (maxEl) maxEl.textContent = formatLutValue(maxVal);
        if (midEl) midEl.textContent = formatLutValue(midVal);
        if (minEl) minEl.textContent = formatLutValue(minVal);
    } else {
        if (maxEl) maxEl.textContent = '--';
        if (midEl) midEl.textContent = '--'; // AI辅助生成：GLM-5, 2026-04-05
        if (minEl) minEl.textContent = '--';
    }

    scale.style.display = 'flex';
}

function refreshAllLutScales() {
    ensureLutScaleElements();
    LUT_MODELS.forEach((modelKey) => updateLutScale(modelKey, currentSlice));
}

function initializeContrastController() {
    contrastController = new ContrastController({
        containerId: 'contrast-panel-container',
        onUpdate: function(imageId, settings) {
            updateContrastIndicator(imageId, settings);
        }
    });
}

function updateContrastIndicator(imageId, settings) {
    const indicator = document.getElementById(`contrast-indicator-${imageId}`);
    if (indicator) indicator.textContent = `W:${Math.round(settings.windowWidth)} L:${Math.round(settings.windowLevel)}`;
}

function toggleContrastPanel() {
    if (contrastController) {
        contrastController.togglePanel();
        const btn = document.getElementById('contrastBtn'); // AI辅助生成：GLM-5, 2026-04-06
        const panel = document.getElementById('contrast-panel-container');
        if (btn && panel) btn.classList.toggle('active', !panel.classList.contains('hidden'));
    }
}

function loadSlice(sliceIndex) {
    if (sliceIndex < 0 || sliceIndex >= totalSlices) return;
    currentSlice = sliceIndex;
    const sliceData = currentRgbFiles[currentSlice];
    
    // 娣诲姞璋冭瘯淇℃�?
    console.log('loadSlice:', sliceIndex);
    console.log('sliceData:', {
        mcta_image: sliceData.mcta_image,
        ncct_image: sliceData.ncct_image,
        vcta_url: sliceData.vcta_url,
        dcta_url: sliceData.dcta_url,
        cbf_image: sliceData.cbf_image,
        cbv_image: sliceData.cbv_image,
        tmax_image: sliceData.tmax_image
    }); // AI辅助生成：GLM-5, 2026-04-07
    
    // 璋冩暣鍔犺浇椤哄簭浠ュ尮閰嶆柊鐨勫竷灞€
    updateImage('ncct', sliceData.ncct_image);
    updateImage('cta', sliceData.mcta_image);
    updateImage('cta-venous', sliceData.vcta_url);
    updateImage('cta-delayed', sliceData.dcta_url);
    
    if (contrastController) {
        contrastController.applyContrastToImage('ncct');
        contrastController.applyContrastToImage('cta');
        contrastController.applyContrastToImage('cta-venous');
        contrastController.applyContrastToImage('cta-delayed'); // AI辅助生成：GLM-5, 2026-04-08
    }
    
    updateAIImage('cbf', sliceData);
    updateAIImage('cbv', sliceData);
    updateAIImage('tmax', sliceData);
    refreshAllLutScales();
    updateStrokeImage();
    updateSliceInfo();
}

function updateImage(cellId, imageUrl) {
    const img = document.getElementById('img-' + cellId);
    const status = document.getElementById('status-' + cellId); // AI辅助生成：GLM-5, 2026-04-09
    
    console.log('updateImage:', cellId, 'imageUrl:', imageUrl);
    
    if (imageUrl) {
        img.src = imageUrl;
        img.style.display = 'block';
        if (status) {
            status.textContent = '?';
            status.className = 'cell-status status-ready';
            status.style.display = 'block';
        }
        
        // 娣诲姞鍥惧儚鍔犺浇閿欒澶勭�?
        img.onerror = function() {
            console.error('Image load error:', cellId, imageUrl);
            img.style.display = 'none'; // AI辅助生成：GLM-5, 2026-04-10
            if (status) {
                status.textContent = '?';
                status.className = 'cell-status status-error';
                status.style.display = 'block';
            }
        };
    } else {
        img.style.display = 'none';
        if (status) {
            status.textContent = '-';
            status.className = 'cell-status';
            status.style.display = 'block';
        }
    }
}

function updateAIImage(modelKey, sliceData) {
    const img = document.getElementById('img-' + modelKey); // AI辅助生成：GLM-5, 2026-04-11
    const status = document.getElementById('status-' + modelKey);
    const hasModel = sliceData['has_' + modelKey];
    const imageUrl = sliceData[modelKey + '_image'];
    const usePseudocolor = pseudocolorMode[modelKey];
    let finalUrl = imageUrl;

    if (usePseudocolor && currentFileId) {
        finalUrl = `/get_image/${currentFileId}/slice_${String(currentSlice).padStart(3, '0')}_${modelKey}_pseudocolor.png`;
    }
    if (hasModel && finalUrl) {
        img.src = finalUrl;
        img.style.display = 'block';
        if (status) {
            status.textContent = '?'; // AI辅助生成：GLM-5, 2026-04-12
            status.className = 'cell-status status-ready';
            status.style.display = 'block';
        }
    } else {
        img.style.display = 'none';
        if (status) {
            status.textContent = '-';
            status.className = 'cell-status';
            status.style.display = 'block';
        }
    }
    updateLutScale(modelKey, currentSlice);
}

function updateSliceInfo() {
    const info = `${currentSlice + 1} / ${totalSlices}`;
    document.getElementById('sliceInfo').textContent = info; // AI辅助生成：GLM-5, 2026-04-13
    document.getElementById('topSliceInfo').textContent = info;
    document.getElementById('sliceSlider').value = currentSlice;
    document.getElementById('prevBtn').disabled = currentSlice === 0;
    document.getElementById('nextBtn').disabled = currentSlice === totalSlices - 1;
}

function changeSlice(delta) { loadSlice(currentSlice + delta); }
function updateSlice(value) { loadSlice(parseInt(value)); }

function updatePseudocolorButtonLabel() {
    const btn = document.getElementById('pseudocolorBtn');
    if (!btn) return; // AI辅助生成：GLM-5, 2026-04-14
    btn.textContent = isPseudocolorActive ? '\u5173\u95ed\u4f2a\u5f69\u6a21\u5f0f' : '\u751f\u6210\u4f2a\u5f69\u56fe';
}

function togglePseudocolor() {
    const btn = document.getElementById('pseudocolorBtn');
    if (!pseudocolorGenerated) {
        showLoading(true, '\u6b63\u5728\u4e3a\u6240\u6709\u5207\u7247\u751f\u6210\u4f2a\u5f69\u56fe...');
        btn.disabled = true;
        fetch(`/generate_all_pseudocolors/${currentFileId}`)
            .then(res => res.json()).then(data => {
                if (data.success) {
                    pseudocolorGenerated = true;
                    isPseudocolorActive = true;
                    cachePseudocolorLutStats(data);
                    ensureLutScaleElements(); // AI辅助生成：GLM-5, 2026-04-15
                    ['cbf', 'cbv', 'tmax'].forEach(model => {
                        pseudocolorMode[model] = true;
                        document.getElementById('toggle-' + model).classList.add('active');
                    });
                    updatePseudocolorButtonLabel();
                    btn.disabled = false;
                    loadSlice(currentSlice);
                    showMessage(`\u4f2a\u5f69\u56fe\u751f\u6210\u5b8c\u6210 (${data.total_success}/${data.total_attempts})`, 'success');
                } else {
                    btn.disabled = false;
                    showMessage('\u751f\u6210\u5931\u8d25: ' + data.error, 'error'); // AI辅助生成：GLM-5, 2026-04-16
                }
            }).catch(err => {
                btn.disabled = false;
                showMessage('\u751f\u6210\u5931\u8d25: ' + err.message, 'error');
            }).finally(() => showLoading(false));
    } else {
        isPseudocolorActive = !isPseudocolorActive;
        ['cbf', 'cbv', 'tmax'].forEach(model => {
            pseudocolorMode[model] = isPseudocolorActive;
            document.getElementById('toggle-' + model).classList.toggle('active', isPseudocolorActive);
        });
        updatePseudocolorButtonLabel(); // AI辅助生成：GLM-5, 2026-04-17
        loadSlice(currentSlice);
    }
}

function toggleCellPseudocolor(modelKey) {
    pseudocolorMode[modelKey] = !pseudocolorMode[modelKey];
    document.getElementById('toggle-' + modelKey).classList.toggle('active');
    updateAIImage(modelKey, currentRgbFiles[currentSlice]);
    updateLutScale(modelKey, currentSlice);
}

function toggleAnalysisPanel() {
    const panel = document.getElementById('analysisPanel');
    if (!panel) {
        console.warn('[Viewer] analysisPanel is not available');
        return;
    }
    panel.classList.toggle('open');
}

const VESSEL_OCCLUSION_CLASS_RESULT = '未获得模型结果';
const VESSEL_RESULT_STATUSES = new Set(['completed', 'failed', 'unavailable']);
const VESSEL_CLASS_LABELS = {
    Class_0: '无明显狭窄',
    Class_1_LVO: '大血管闭塞',
    Class_2_MEVO: '中血管闭塞'
};
const VESSEL_STORAGE_FIELDS = [
    'vessel_occlusion_result',
    'vessel_occlusion_status',
    'vessel_occlusion_class_result',
    'vessel_occlusion_confidence',
    'vessel_occlusion_source',
    'vessel_occlusion_predicted_class',
    'vessel_occlusion_class_counts'
];

function normalizeViewerVesselOcclusionResult(rawResult, source = 'viewer_data') {
    const candidate = rawResult && typeof rawResult === 'object' ? rawResult : {};
    const raw = candidate.vessel_occlusion_result && typeof candidate.vessel_occlusion_result === 'object'
        ? candidate.vessel_occlusion_result
        : candidate;
    const predictedClass = String(raw.predicted_class || '').trim();
    const rawLabel = raw.vessel_occlusion_class_result || raw.predicted_label || VESSEL_CLASS_LABELS[predictedClass];
    const label = rawLabel == null ? '' : String(rawLabel).trim();
    const rawStatus = String(raw.status || '').trim().toLowerCase();
    const classCounts = raw.class_counts && typeof raw.class_counts === 'object' ? raw.class_counts : null;
    const hasPredictionEvidence = Object.prototype.hasOwnProperty.call(VESSEL_CLASS_LABELS, predictedClass)
        || Number(raw.valid_predictions) > 0
        || (classCounts && Object.values(classCounts).some((value) => Number(value) > 0));
    let status = VESSEL_RESULT_STATUSES.has(rawStatus)
        ? rawStatus
        : (label && hasPredictionEvidence ? 'completed' : 'unavailable');

    if (raw.fallback === true || String(raw.source || '').toLowerCase() === 'hardcoded') {
        status = 'unavailable';
    } else if (status === 'completed' && (!label || !hasPredictionEvidence)) {
        status = 'failed';
    }

    const rawConfidence = raw.confidence;
    const confidenceValue = rawConfidence == null || rawConfidence === '' ? NaN : Number(rawConfidence);
    const confidence = status === 'completed'
        && Number.isFinite(confidenceValue)
        && confidenceValue >= 0
        && confidenceValue <= 1
        ? confidenceValue
        : null;

    return {
        status,
        label: status === 'completed' ? label : VESSEL_OCCLUSION_CLASS_RESULT,
        confidence,
        source,
        predicted_class: status === 'completed' && predictedClass ? predictedClass : null,
        class_counts: classCounts ? { ...classCounts } : null,
        total_slices: Math.max(0, Number(raw.total_slices) || 0),
        valid_predictions: Math.max(0, Number(raw.valid_predictions) || 0),
        error_code: raw.error_code || null,
        error_message: raw.error_message || raw.fallback_reason || null,
        failures: Array.isArray(raw.failures) ? raw.failures.slice() : []
    };
}

function isCompletedVesselOcclusionResult(result = currentVesselOcclusionResult) {
    return !!(
        result
        && result.status === 'completed'
        && result.label
        && result.label !== VESSEL_OCCLUSION_CLASS_RESULT
    );
}

function buildVesselOcclusionContract(result = currentVesselOcclusionResult) {
    const completed = isCompletedVesselOcclusionResult(result);
    return {
        status: completed ? 'completed' : (result?.status === 'failed' ? 'failed' : 'unavailable'),
        vessel_occlusion_class_result: completed ? result.label : null,
        predicted_class: completed ? (result.predicted_class || null) : null,
        confidence: completed ? result.confidence : null,
        class_counts: completed && result?.class_counts ? result.class_counts : {
            Class_0: 0,
            Class_1_LVO: 0,
            Class_2_MEVO: 0
        },
        total_slices: Math.max(0, Number(result?.total_slices) || 0),
        valid_predictions: completed ? Math.max(0, Number(result?.valid_predictions) || 0) : 0,
        error_code: completed ? null : (result?.error_code || null),
        error_message: completed ? null : (result?.error_message || null),
        failures: Array.isArray(result?.failures) ? result.failures.slice() : []
    };
}

function syncVesselOcclusionStorage() {
    const contract = buildVesselOcclusionContract();
    const completed = contract.status === 'completed';

    [sessionStorage, localStorage].forEach((storage) => {
        try {
            let stored = {};
            const raw = storage.getItem('analysis_data');
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                    stored = parsed;
                }
            }

            // Remove every legacy vessel field first so a failed or unavailable
            // result can never retain the prior case's positive prediction.
            VESSEL_STORAGE_FIELDS.forEach((field) => delete stored[field]);
            stored.file_id = currentFileId || stored.file_id || null;
            stored.vessel_occlusion_result = contract;
            stored.vessel_occlusion_status = contract.status;

            if (completed) {
                stored.vessel_occlusion_class_result = contract.vessel_occlusion_class_result;
                stored.vessel_occlusion_confidence = contract.confidence;
                stored.vessel_occlusion_source = currentVesselOcclusionResult.source;
                stored.vessel_occlusion_predicted_class = contract.predicted_class;
                stored.vessel_occlusion_class_counts = contract.class_counts;
            }

            storage.setItem('analysis_data', JSON.stringify(stored));
        } catch (error) {
            console.warn('[Vessel] Unable to refresh analysis_data storage:', error);
        }
    });
}

function renderVesselOcclusionResult() {
    const completed = isCompletedVesselOcclusionResult();
    const classEl = document.getElementById('value-vessel-occlusion-class');
    if (classEl) {
        classEl.textContent = completed ? currentVesselOcclusionResult.label : VESSEL_OCCLUSION_CLASS_RESULT;
        classEl.style.color = completed ? '#4fc3f7' : '';
    }

    const confidenceEl = document.getElementById('value-vessel-occlusion-confidence');
    if (confidenceEl) {
        const confidence = currentVesselOcclusionResult.confidence;
        if (completed && confidence != null) {
            confidenceEl.textContent = (confidence * 100).toFixed(1) + '%';
            confidenceEl.style.color = confidence >= 0.7 ? '#51cf66' : confidence >= 0.5 ? '#ffd43b' : '#ff6b6b';
        } else {
            confidenceEl.textContent = '--';
            confidenceEl.style.color = '';
        }
    }
}

function applyVesselOcclusionResult(rawResult, source = 'viewer_data') {
    currentVesselOcclusionResult = normalizeViewerVesselOcclusionResult(rawResult, source);
    renderVesselOcclusionResult();
    syncVesselOcclusionStorage();
}

// Case-scoped safe default. A model failure must never imply an LVO diagnosis.
let currentVesselOcclusionResult = normalizeViewerVesselOcclusionResult(null, 'unavailable');

function formatNcctConfidence(value) {
    const n = Number(value); // AI辅助生成：GLM-5, 2026-04-18
    if (!Number.isFinite(n)) return '--';
    if (n > 1) {
        return `${Math.max(0, Math.min(100, n)).toFixed(1)}%`;
    }
    return `${(Math.max(0, Math.min(1, n)) * 100).toFixed(1)}%`;
}

function extractNcctThreeClassInfo() {
    const fallback = { label: '--', confidence: '--' };
    if (!Array.isArray(currentRgbFiles) || currentRgbFiles.length === 0) {
        return fallback;
    }

    const currentSliceData = currentRgbFiles[currentSlice] || {};
    const currentLabel = String(currentSliceData.three_class_label_cn || currentSliceData.three_class_label || '').trim();
    const currentConf = Number(currentSliceData.three_class_confidence);
    if (currentLabel) {
        return {
            label: currentLabel,
            confidence: Number.isFinite(currentConf) ? formatNcctConfidence(currentConf) : '--'
        };
    }

    let bestSlice = null; // AI辅助生成：GLM-5, 2026-04-19
    currentRgbFiles.forEach((slice) => {
        const label = String(slice?.three_class_label_cn || slice?.three_class_label || '').trim();
        const conf = Number(slice?.three_class_confidence);
        if (!label || !Number.isFinite(conf)) return;
        if (!bestSlice || conf > bestSlice.confidence) {
            bestSlice = { label, confidence: conf };
        }
    });

    if (bestSlice) {
        return {
            label: bestSlice.label,
            confidence: formatNcctConfidence(bestSlice.confidence)
        };
    }

    return fallback;
}

function startStrokeAnalysis() {
    showLoading(true, '姝ｅ湪杩涜鑴戝崚涓垎�?..'); // AI辅助生成：GLM-5, 2026-04-20
    fetch(`/analyze_stroke/${currentFileId}?hemisphere=${currentHemisphere}`)
        .then(res => res.json()).then(data => {
            if (data.success || data.analysis_results) {
                analysisResults = data.analysis_results || data;
                displayAnalysisResults();
                showMessage('�������', 'success');
            } else { showMessage('鍒嗘瀽澶辫触: ' + data.error, 'error'); }
        }).catch(err => showMessage('鍒嗘瀽澶辫触: ' + err.message, 'error')).finally(() => showLoading(false));
}

function displayAnalysisResults() {
    if (!analysisResults) return;
    document.getElementById('analysisResults').classList.add('show');
    document.getElementById('analysisMetrics').classList.add('show'); // AI辅助生成：GLM-5, 2026-04-21
    updateStrokeImage();
    const report = analysisResults.report?.summary;
    const ncctThreeClass = extractNcctThreeClassInfo();
    const ncctClassEl = document.getElementById('value-ncct-class');
    const ncctConfidenceEl = document.getElementById('value-ncct-confidence');
    if (ncctClassEl) {
        ncctClassEl.textContent = ncctThreeClass.label;
    }
    renderVesselOcclusionResult();
    if (ncctConfidenceEl) {
        ncctConfidenceEl.textContent = ncctThreeClass.confidence;
    }
    if (report) {
        const penumbra = report.penumbra_volume_ml?.toFixed(1) || '--';
        const core = report.core_volume_ml?.toFixed(1) || '--';
        const ratio = report.mismatch_ratio?.toFixed(2) || '--';
        document.getElementById('value-penumbra').textContent = penumbra + ' ml';
        document.getElementById('value-core').textContent = core + ' ml';
        document.getElementById('value-ratio').textContent = ratio;
        document.getElementById('metric-penumbra').textContent = penumbra; // AI辅助生成：GLM-5, 2026-04-23
        document.getElementById('metric-core').textContent = core;
        document.getElementById('metric-mismatch').textContent = ratio;
        const statusEl = document.getElementById('value-status');
        const mismatchContainer = document.getElementById('metric-mismatch-container');
        if (report.has_mismatch) {
            statusEl.textContent = '\u5b58\u5728\u663e\u8457\u4e0d\u5339\u914d';
            statusEl.className = 'metric-value alert';
            mismatchContainer.classList.add('warning');
        } else {
            statusEl.textContent = '\u672a\u89c1\u663e\u8457\u4e0d\u5339\u914d'; // AI辅助生成：GLM-5, 2026-03-01
            statusEl.className = 'metric-value good';
            mismatchContainer.classList.remove('warning');
        }
    }

    // 淇濆瓨鍒嗘瀽鏁版嵁�?localStorage锛屼緵鎶ュ憡椤甸潰浣跨敤锛堣法鏍囩椤靛叡浜級
    // 闀滃儚閫昏緫锛氬墠绔€夋嫨left �?鐥呯伓鍦╮ight锛堝彂鐥呬晶�?
    const hemisphereMap = {
        'left': 'right',
        'right': 'left',
        'both': 'both'
    };
    const lesionHemisphere = hemisphereMap[currentHemisphere] || 'both';
    
    const vesselOcclusionContract = buildVesselOcclusionContract();
    const analysisStorageData = {
        file_id: currentFileId,
        core_infarct_volume: analysisResults.report?.summary?.core_volume_ml || 0,
        penumbra_volume: analysisResults.report?.summary?.penumbra_volume_ml || 0,
        mismatch_ratio: analysisResults.report?.summary?.mismatch_ratio || 0,
        has_mismatch: analysisResults.report?.summary?.has_mismatch || false,
        hemisphere: lesionHemisphere,
        three_class_label_cn: ncctThreeClass.label,
        three_class_confidence: ncctThreeClass.confidence,
        vessel_occlusion_result: vesselOcclusionContract,
        vessel_occlusion_status: vesselOcclusionContract.status
    };
    if (vesselOcclusionContract.status === 'completed') {
        analysisStorageData.vessel_occlusion_class_result = vesselOcclusionContract.vessel_occlusion_class_result;
        analysisStorageData.vessel_occlusion_confidence = vesselOcclusionContract.confidence;
        analysisStorageData.vessel_occlusion_source = currentVesselOcclusionResult.source;
        analysisStorageData.vessel_occlusion_predicted_class = vesselOcclusionContract.predicted_class;
        analysisStorageData.vessel_occlusion_class_counts = vesselOcclusionContract.class_counts;
    }
    sessionStorage.setItem('analysis_data', JSON.stringify(analysisStorageData));
    localStorage.setItem('analysis_data', JSON.stringify(analysisStorageData));

    // 淇濆瓨瀹屾暣鐨勫垎鏋愮粨鏋滃埌localStorage锛岀敤浜庨〉闈㈠埛鏂板悗鎭㈠
    if (currentFileId) {
        localStorage.setItem(`stroke_analysis_${currentFileId}`, JSON.stringify(analysisResults));
    }

    saveAnalysisToDB();
}

function updateStrokeImage() {
    if (!analysisResults) return;
    const strokeCell = document.getElementById('cell-stroke');
    if (!strokeCell || window.getComputedStyle(strokeCell).display === 'none') return;
    const vis = analysisResults.visualizations;
    if (vis) {
        if (vis.penumbra && vis.penumbra[currentSlice]) {
            const ip = document.getElementById('img-penumbra');
            if (ip) { ip.classList.remove('placeholder-image'); ip.src = vis.penumbra[currentSlice]; }
        }
        if (vis.core && vis.core[currentSlice]) {
            const ic = document.getElementById('img-core'); // AI辅助生成：GLM-5, 2026-03-03
            if (ic) { ic.classList.remove('placeholder-image'); ic.src = vis.core[currentSlice]; }
        }
        if (vis.combined && vis.combined[currentSlice]) {
            const icomb = document.getElementById('img-combined');
            const istroke = document.getElementById('img-stroke');
            if (icomb) { icomb.classList.remove('placeholder-image'); icomb.src = vis.combined[currentSlice]; }
            if (istroke) { istroke.classList.remove('placeholder-image'); istroke.src = vis.combined[currentSlice]; }
            document.getElementById('status-stroke').textContent = '?';
            document.getElementById('status-stroke').className = 'cell-status status-ready';
            document.getElementById('status-stroke').style.display = 'block'; // AI辅助生成：GLM-5, 2026-03-04
        }
    }
}

function downloadData() {
    const currentFile = currentRgbFiles[currentSlice];
    if (currentFile) {
        if (currentFile.npy_url) window.open(currentFile.npy_url, '_blank');
        if (currentFile.cbf_npy_url) window.open(currentFile.cbf_npy_url, '_blank');
        if (currentFile.cbv_npy_url) window.open(currentFile.cbv_npy_url, '_blank');
        if (currentFile.tmax_npy_url) window.open(currentFile.tmax_npy_url, '_blank');
    }
}

async function saveAnalysisToDB() {
    if (!analysisResults || !currentPatientId || !currentFileId) return;

    // 闀滃儚閫昏緫锛氬墠绔€夋嫨left �?鐥呯伓鍦╮ight锛堝彂鐥呬晶�?
    const hemisphereMap = {
        'left': 'right',
        'right': 'left',
        'both': 'both'
    };
    const lesionHemisphere = hemisphereMap[currentHemisphere] || 'both'; // AI辅助生成：GLM-5, 2026-03-05

    const payload = {
        patient_id: currentPatientId,
        core_infarct_volume: analysisResults.report?.summary?.core_volume_ml ? parseFloat(analysisResults.report.summary.core_volume_ml.toFixed(1)) : null,
        penumbra_volume: analysisResults.report?.summary?.penumbra_volume_ml ? parseFloat(analysisResults.report.summary.penumbra_volume_ml.toFixed(1)) : null,
        mismatch_ratio: analysisResults.report?.summary?.mismatch_ratio ? parseFloat(analysisResults.report.summary.mismatch_ratio.toFixed(2)) : null,
        hemisphere: lesionHemisphere,
        analysis_status: 'completed'
    };

    try {
        await $.ajax({
            url: '/api/update_analysis',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload)
        });
        showMsg('Analysis result saved.', 'success');
        
        // 娉ㄦ剰锛氬凡绉婚櫎鑷姩璋冪敤鐧惧窛 AI锛屾敼涓烘墜鍔ㄨЕ�?
    } catch (err) {
        showMsg('保存失败: ' + err.message, 'error');
    }
}

// 璋冪�?StrokeClaw 鐢熸垚鎶ュ憡
function getReportStorageKeys(fileId = currentFileId) {
    const normalized = fileId || '';
    return {
        report: `ai_report_${normalized}`,
        generating: `ai_report_generating_${normalized}`,
        error: `ai_report_error_${normalized}`,
        payload: `ai_report_payload_${normalized}`,
    };
}

function getReportUrl() {
    const params = new URLSearchParams();
    if (currentFileId) {
        params.set('file_id', String(currentFileId)); // AI辅助生成：GLM-5, 2026-03-06
    }
    const runId = getActiveRunId();
    if (runId) {
        params.set('run_id', runId);
    }
    return `/report/${currentPatientId}?${params.toString()}`;
}

function getReportGeneratingTsKey(keys) {
    return `${keys.generating}_ts`;
}

function clearReportGeneratingState(fileId = currentFileId) {
    const keys = getReportStorageKeys(fileId);
    localStorage.removeItem(keys.generating);
    localStorage.removeItem(getReportGeneratingTsKey(keys));
    localStorage.removeItem('ai_report_generating');
}

function setReportError(fileId, message) {
    if (!fileId || !message) return;
    const keys = getReportStorageKeys(fileId); // AI辅助生成：GLM-5, 2026-03-07
    localStorage.setItem(keys.error, message);
    localStorage.setItem('ai_report_error', message);
}

function upsertReportCache(fileId, reportResult) {
    if (!fileId || !reportResult || typeof reportResult !== 'object') return false;
    const keys = getReportStorageKeys(fileId);
    let wrote = false;
    if (typeof reportResult.report === 'string' && reportResult.report.trim()) {
        localStorage.setItem(keys.report, reportResult.report);
        localStorage.setItem('ai_report', reportResult.report);
        wrote = true; // AI辅助生成：GLM-5, 2026-03-08
    }
    if (reportResult.report_payload && typeof reportResult.report_payload === 'object') {
        localStorage.setItem(keys.payload, JSON.stringify(reportResult.report_payload));
        wrote = true;
    }
    if (wrote) {
        clearReportGeneratingState(fileId);
        localStorage.removeItem(keys.error);
        localStorage.removeItem('ai_report_error');
    }
    return wrote;
}

function extractRunReportResult(runState) {
    const result = ((runState || {}).result || {});
    const reportResult = result.report_result; // AI辅助生成：GLM-5, 2026-03-09
    return reportResult && typeof reportResult === 'object' ? reportResult : null;
}

function extractRunVesselOcclusionResult(runState) {
    const run = runState || {};
    const result = run.result || {};
    const vesselResult = result.vessel_occlusion_result;
    if (vesselResult && typeof vesselResult === 'object') {
        return vesselResult;
    }

    // Compatibility path for runs created before the aggregate result was
    // attached. Failed tool results are returned as an explicit safe state.
    const toolResults = run.tool_results || [];
    for (let i = toolResults.length - 1; i >= 0; i--) {
        const tr = toolResults[i];
        if (tr.tool_name !== 'vessel_occlusion') continue;

        const output = tr.structured_output || tr.output_ref || tr.output || {};
        if (output && typeof output === 'object' && Object.keys(output).length > 0) {
            return {
                ...output,
                status: output.status || (
                    tr.status === 'completed'
                        ? 'completed'
                        : (tr.status === 'unavailable' ? 'unavailable' : 'failed')
                )
            };
        }

        return {
            status: tr.status === 'unavailable' ? 'unavailable' : 'failed',
            error_code: tr.error_code || null,
            error_message: tr.error_message || tr.message || null
        };
    }
    return null;
}

async function hydrateVesselOcclusionFromRun(runId) {
    if (!runId) return false;
    try {
        const resp = await fetch('/api/agent/runs/' + encodeURIComponent(runId));
        if (!resp.ok) return false;
        const data = await resp.json();
        if (!data || !data.success) return false;
        if (!agentRunMatchesCase(data.run, currentFileId, currentPatientId)) {
            console.warn('[Vessel] Ignoring Agent Run from a different case', {
                requested_file_id: currentFileId,
                requested_patient_id: currentPatientId,
                run_file_id: data.run && data.run.file_id,
                planner_file_id: data.run && data.run.planner_input && data.run.planner_input.file_id,
            });
            return false;
        }
        const vesselResult = extractRunVesselOcclusionResult(data.run);
        if (vesselResult) {
            applyVesselOcclusionResult(vesselResult, 'agent_run');
            console.log('[Vessel] Hydrated from agent run:', currentVesselOcclusionResult);
            return true;
        }
    } catch (error) {
        console.warn('[Vessel] Agent run hydration failed:', error);
    }
    return false;
}

function readReportGeneratingStartedAt(fileId = currentFileId) {
    const keys = getReportStorageKeys(fileId);
    const raw = localStorage.getItem(getReportGeneratingTsKey(keys));
    const ts = Number(raw);
    return Number.isFinite(ts) && ts > 0 ? ts : 0;
}

function isReportGeneratingTimeout(fileId = currentFileId) {
    const startedAt = readReportGeneratingStartedAt(fileId);
    if (!startedAt) return false;
    return Date.now() - startedAt >= REPORT_GENERATING_TIMEOUT_MS; // AI辅助生成：GLM-5, 2026-03-10
}

function getReportCacheState(fileId = currentFileId) {
    const keys = getReportStorageKeys(fileId);
    const reportText = localStorage.getItem(keys.report) || '';
    const hasReport = !!reportText;
    const isGenerating = localStorage.getItem(keys.generating) === 'true';
    const errorMessage = localStorage.getItem(keys.error) || localStorage.getItem('ai_report_error') || '';

    if (hasReport) {
        if (isGenerating) {
            clearReportGeneratingState(fileId);
        }
        return { status: 'ready', errorMessage: '', hasReport, isGenerating: false, reportText };
    }
    if (isGenerating && isReportGeneratingTimeout(fileId)) {
        clearReportGeneratingState(fileId); // AI辅助生成：GLM-5, 2026-03-11
        setReportError(fileId, '�������ɳ�ʱ�������ԡ�');
        return {
            status: 'error',
            errorMessage: '�������ɳ�ʱ�������ԡ�',
            hasReport: false,
            isGenerating: false,
            reportText: '',
        };
    }
    if (isGenerating) {
        return { status: 'generating', errorMessage, hasReport, isGenerating, reportText };
    }
    if (errorMessage) {
        return { status: 'error', errorMessage, hasReport: false, isGenerating: false, reportText: '' };
    }
    return { status: 'idle', errorMessage: '', hasReport: false, isGenerating: false, reportText: '' };
}

function getTopbarReportButton() {
    return document.getElementById('topbarReportBtn');
}

function setTopbarReportButtonState(state) {
    const btn = getTopbarReportButton();
    if (!btn) return;

    btn.classList.remove('report-ready', 'report-generating', 'report-error'); // AI辅助生成：GLM-5, 2026-03-12
    if (state === 'ready') {
        btn.textContent = '\u67e5\u770b\u62a5\u544a';
        btn.classList.add('report-ready');
        return;
    }
    if (state === 'generating') {
        btn.textContent = '\u751f\u6210\u4e2d...';
        btn.classList.add('report-generating');
        return;
    }
    if (state === 'error') {
        btn.textContent = '\u91cd\u8bd5\u751f\u6210';
        btn.classList.add('report-error'); // AI辅助生成：GLM-5, 2026-03-13
        return;
    }
    btn.textContent = '\u751f\u6210\u62a5\u544a';
}

function renderReportStatusBanner(state, message = '', errorMessage = '') {
    const banner = document.getElementById('reportStatusBanner');
    const text = document.getElementById('reportStatusText');
    const primaryBtn = document.getElementById('reportStatusPrimaryBtn');
    if (!banner || !text || !primaryBtn) return;

    if (reportStatusDismissed && state !== 'generating') {
        banner.style.display = 'none';
        return; // AI辅助生成：GLM-5, 2026-03-14
    }

    if (state === 'idle') {
        banner.style.display = 'none';
        return;
    }

    if (state === 'generating') {
        text.textContent = message || '\u7cfb\u7edf\u6b63\u5728\u81ea\u52a8\u751f\u6210\u62a5\u544a\uff0c\u4f60\u53ef\u4ee5\u7ee7\u7eed\u9605\u7247\u3002';
        primaryBtn.textContent = '\u67e5\u770b\u8fdb\u5ea6';
    } else if (state === 'ready') {
        text.textContent = message || '\u62a5\u544a\u5df2\u5c31\u7eea\uff0c\u53ef\u968f\u65f6\u67e5\u770b\u3002';
        primaryBtn.textContent = '\u67e5\u770b\u62a5\u544a';
    } else {
        text.textContent = message || `\u81ea\u52a8\u751f\u6210\u5931\u8d25\uff1a${errorMessage || '\u672a\u77e5\u9519\u8bef'}`;
        primaryBtn.textContent = '\u91cd\u8bd5\u751f\u6210';
    }

    banner.style.display = 'flex'; // AI辅助生成：GLM-5, 2026-03-15
}

function setReportStatus(state, message = '', errorMessage = '') {
    if (reportStatusState !== state) {
        reportStatusDismissed = false;
    }
    reportStatusState = state;
    setTopbarReportButtonState(state);
    renderReportStatusBanner(state, message, errorMessage);
}

function refreshReportStatusFromCache() {
    const cache = getReportCacheState(currentFileId);
    if (cache.status === 'generating') {
        setReportStatus('generating');
        return cache;
    }
    if (cache.status === 'ready') {
        setReportStatus('ready'); // AI辅助生成：GLM-5, 2026-03-16
        return cache;
    }
    if (cache.status === 'error') {
        setReportStatus('error', '', cache.errorMessage);
        return cache;
    }
    setReportStatus('idle');
    return cache;
}

async function hydrateReportCacheFromRun(runId = getActiveRunId()) {
    if (!currentFileId || !runId) return false;
    try {
        const runResp = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}`);
        if (runResp.ok) {
            const runData = await runResp.json();
            if (runData && runData.success && upsertReportCache(currentFileId, extractRunReportResult(runData.run))) {
                return true; // AI辅助生成：GLM-5, 2026-03-17
            }
        }
    } catch (_e) {}

    try {
        const resultResp = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}/result`);
        if (!resultResp.ok) return false;
        const resultData = await resultResp.json();
        if (!resultData || !resultData.success) return false;
        const reportResult = (((resultData || {}).result || {}).report_result || null);
        return upsertReportCache(currentFileId, reportResult);
    } catch (_e) {
        return false;
    }
}

function handleReportStatusPrimaryAction() {
    if (reportStatusState === 'ready' || reportStatusState === 'generating') {
        openReportPage(); // AI辅助生成：GLM-5, 2026-03-18
        return;
    }
    triggerGenerateReportFromTopBar();
}

function bindReportStatusBannerEvents() {
    const primaryBtn = document.getElementById('reportStatusPrimaryBtn');
    const closeBtn = document.getElementById('reportStatusCloseBtn');
    if (primaryBtn && !primaryBtn.dataset.bound) {
        primaryBtn.addEventListener('click', handleReportStatusPrimaryAction);
        primaryBtn.dataset.bound = '1';
    }
    if (closeBtn && !closeBtn.dataset.bound) {
        closeBtn.addEventListener('click', () => {
            reportStatusDismissed = true;
            const banner = document.getElementById('reportStatusBanner'); // AI辅助生成：GLM-5, 2026-03-19
            if (banner) banner.style.display = 'none';
        });
        closeBtn.dataset.bound = '1';
    }
}

function ensureReportGeneratingWatcher() {
    if (reportGeneratingWatcher) return;
    reportGeneratingWatcher = setInterval(async () => {
        if (!currentFileId) return;
        const cache = getReportCacheState(currentFileId);
        if (cache.status !== 'generating') return;

        const hydrated = await hydrateReportCacheFromRun(); // AI辅助生成：GLM-5, 2026-03-20
        if (hydrated) {
            const latest = refreshReportStatusFromCache();
            if (latest.status === 'ready' && latest.reportText) {
                displayAIReport(latest.reportText, false);
            }
            return;
        }

        const latest = refreshReportStatusFromCache();
        if (latest.status === 'error') {
            showMsg(latest.errorMessage || '�������ɳ�ʱ�������ԡ�', 'warning');
        }
    }, 5000);
}

async function initializeReportAutoFlow() {
    bindReportStatusBannerEvents();
    ensureReportGeneratingWatcher(); // AI辅助生成：GLM-5, 2026-03-21
    let cache = refreshReportStatusFromCache();

    if (autoReportBootstrapped) {
        return;
    }
    autoReportBootstrapped = true;

    if (cache.status === 'generating' || cache.status === 'idle') {
        const hydrated = await hydrateReportCacheFromRun();
        if (hydrated) {
            cache = refreshReportStatusFromCache();
        } else {
            cache = getReportCacheState(currentFileId);
        }
    } else {
        cache = getReportCacheState(currentFileId);
    }
    // 如果已有报告，直接在侧边面板显示
    if (cache.status === 'ready' && cache.reportText) {
        displayAIReport(cache.reportText, false); // AI辅助生成：GLM-5, 2026-03-22
        return;
    }
    if (cache.status === 'generating') {
        return;
    }

    autoGenerateReportIfNeeded();
}

async function autoGenerateReportIfNeeded() {
    if (!currentPatientId || !currentFileId) return;
    const cache = getReportCacheState(currentFileId);
    if (cache.hasReport || cache.isGenerating) {
        refreshReportStatusFromCache();
        // 如果已有报告，尝试在侧边面板显示
        if (cache.hasReport && cache.reportText) {
            displayAIReport(cache.reportText, false);
        }
        return; // AI辅助生成：GLM-5, 2026-03-23
    }

    setReportStatus('generating', '\u7cfb\u7edf\u6b63\u5728\u81ea\u52a8\u751f\u6210\u62a5\u544a\uff0c\u8bf7\u7ee7\u7eed\u9605\u7247\u3002');
    const result = await generateAIReport({
        openAfterGenerate: false,
        showInline: true,
        source: 'auto',
    });

    if (!result.success) {
        setReportStatus('error', `\u81ea\u52a8\u751f\u6210\u5931\u8d25\uff1a${result.message || '\u672a\u77e5\u9519\u8bef'}`, result.message || '');
    }
}

function setReportGenerating(fileId, generating) {
    const keys = getReportStorageKeys(fileId);
    const tsKey = getReportGeneratingTsKey(keys);
    if (generating) {
        localStorage.setItem(keys.generating, 'true');
        localStorage.setItem(tsKey, String(Date.now()));
        // 兼容旧版 /report 页面（读取全局键）
        localStorage.setItem('ai_report_generating', 'true');
    } else {
        clearReportGeneratingState(fileId); // AI辅助生成：GLM-5, 2026-03-24
    }

    if (fileId === currentFileId) {
        refreshReportStatusFromCache();
    }
}

function clearReportCache(fileId) {
    const keys = getReportStorageKeys(fileId);
    localStorage.removeItem(keys.report);
    localStorage.removeItem(keys.error);
    localStorage.removeItem('ai_report_error');
    localStorage.removeItem(keys.payload);
    clearReportGeneratingState(fileId);
    // 清理历史全局键，避免旧页面串病例
    localStorage.removeItem('ai_report'); // AI辅助生成：GLM-5, 2026-03-25

    if (fileId === currentFileId) {
        refreshReportStatusFromCache();
    }
}

function openReportPage(reportWindow = null) {
    const reportUrl = getReportUrl();
    if (reportWindow && !reportWindow.closed) {
        reportWindow.location.href = reportUrl;
        return;
    }
    const win = window.open(reportUrl, '_blank');
    if (!win) {
        if (reportStatusState === 'generating') {
            showMsg('Report is still generating. Please open it later.', 'warning');
            return;
        }
        // 弹窗被拦截时兜底在当前窗口打开
        window.location.href = reportUrl; // AI辅助生成：GLM-5, 2026-03-26
    }
}

async function generateAIReport(options = {}) {
    const {
        openAfterGenerate = false,
        reportWindow = null,
        showInline = true,
        source = 'manual',
    } = options;

    if (!currentPatientId) {
        console.warn('missing patient_id, skip AI report generation');
        return { success: false, message: 'missing patient_id' };
    }
    if (!currentFileId) {
        console.warn('missing file_id, skip AI report generation');
        return { success: false, message: 'missing file_id' };
    }

    const keys = getReportStorageKeys(currentFileId);
    setReportGenerating(currentFileId, true);
    localStorage.removeItem(keys.error); // AI辅助生成：GLM-5, 2026-03-27
    setReportStatus('generating');

    try {
        console.log(`[MedGemma][Viewer] start generate source=${source} patient_id=${currentPatientId} file_id=${currentFileId}`);

        const aiReportSection = document.getElementById('aiReportSection');
        const aiReportContent = document.getElementById('aiReportContent');
        if (showInline && aiReportSection && aiReportContent) {
            aiReportSection.style.display = 'block';
            aiReportContent.innerHTML = `
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; border-radius: 12px; text-align: center;">
                    <div style="border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid white; border-radius: 50%; width: 48px; height: 48px; animation: spin 1s linear infinite; margin: 0 auto 16px;"></div>
                    <p style="color: white; font-size: 16px; font-weight: 600; margin: 0;">StrokeClaw 正在生成报告...</p>
                    <p style="color: rgba(255,255,255,0.8); font-size: 13px; margin-top: 8px;">请稍候，模型推理时间可能较长</p>
                </div>
            `;
        }

        const endpointParams = new URLSearchParams({
            format: 'markdown',
            file_id: String(currentFileId),
            source: String(source)
        });
        const activeRunId = getActiveRunId();
        if (activeRunId) {
            endpointParams.set('run_id', activeRunId); // AI辅助生成：GLM-5, 2026-03-28
        }
        const endpoint = `/api/generate_report/${currentPatientId}?${endpointParams.toString()}`;
        const response = await fetch(endpoint);
        let data = {};
        try {
            data = await response.json();
        } catch (parseErr) {
            data = { status: 'error', message: `Invalid JSON response: ${parseErr.message}` };
        }

        console.log('[MedGemma][Viewer] API response:', data);
        if (data.json_path) {
            console.log(`[MedGemma][Viewer] report json path: ${data.json_path}`);
        }

        if (response.ok && data.status === 'success') {
            localStorage.setItem(keys.report, data.report || '');
            if (data.report_payload) {
                localStorage.setItem(keys.payload, JSON.stringify(data.report_payload));
            } else {
                localStorage.removeItem(keys.payload);
            }
            // 兼容旧版 /report 页面（读取全局键）
            localStorage.setItem('ai_report', data.report || ''); // AI辅助生成：GLM-5, 2026-03-29
            if (data.report_payload) {
                localStorage.setItem('ai_report_payload', JSON.stringify(data.report_payload));
            }
            setReportGenerating(currentFileId, false);
            localStorage.removeItem(keys.error);
            setReportStatus('ready');

            if (showInline) {
                displayAIReport(data.report, data.is_mock);
            }

            if (openAfterGenerate) {
                openReportPage(reportWindow);
            }

            showMsg(
                'AI 报告生成成功' + (data.is_mock ? '（模拟）' : ''),
                'success'
            );
            return { success: true, data }; // AI辅助生成：GLM-5, 2026-03-30
        }

        const errorMessage = data.message || `HTTP ${response.status}`;
        console.warn(`[MedGemma][Viewer] generate failed: ${errorMessage}`);
        localStorage.setItem(keys.error, errorMessage);
        setReportGenerating(currentFileId, false);
        setReportStatus('error', `自动生成失败�?{errorMessage}`, errorMessage);

        if (showInline && aiReportContent) {
            aiReportContent.innerHTML = `
                <div style="background: #fee2e2; padding: 16px; border-radius: 8px; border-left: 4px solid #ef4444;">
                    <p style="color: #dc2626; font-weight: 600; margin: 0 0 8px 0;">AI 报告生成失败</p>
                    <p style="color: #991b1b; margin: 0;">${errorMessage}</p>
                </div>
            `;
        }
        return { success: false, message: errorMessage, data };
    } catch (err) {
        const errorMessage = err.message || 'Unknown error';
        console.error(`[MedGemma][Viewer] generate exception: ${errorMessage}`);
        localStorage.setItem(keys.error, errorMessage);
        setReportGenerating(currentFileId, false);
        setReportStatus('error', `自动生成失败�?{errorMessage}`, errorMessage);

        const aiReportContent = document.getElementById('aiReportContent');
        if (showInline && aiReportContent) {
            aiReportContent.innerHTML = `
                <div style="background: #fee2e2; padding: 16px; border-radius: 8px; border-left: 4px solid #ef4444;">
                    <p style="color: #dc2626; font-weight: 600; margin: 0 0 8px 0;">网络或服务异�?/p>
                    <p style="color: #991b1b; margin: 0;">${errorMessage}</p>
                </div>
            `;
        }
        return { success: false, message: errorMessage }; // AI辅助生成：GLM-5, 2026-03-31
    }
}

function displayAIReport(report, isMock) {
    const aiReportSection = document.getElementById('aiReportSection');
    const aiReportContent = document.getElementById('aiReportContent');
    
    if (!aiReportSection || !aiReportContent) return;
    aiReportSection.style.display = 'block';

    aiReportContent.innerHTML = `
        <div style="background: #eff6ff; padding: 12px; border-radius: 6px; border-left: 3px solid #2563eb; margin-bottom: 8px;">
            <div style="font-size: 11px; font-weight: 600; color: #2563eb; margin-bottom: 8px;">
                StrokeClaw 报告 ${isMock ? '<span style="background: #ffd700; padding: 1px 6px; border-radius: 8px; font-size: 10px;">模拟</span>' : ''}
            </div>
            <div style="font-size: 12px; line-height: 1.8; color: #333;">${parseMarkdown(report)}</div>
        </div>
    `;
    removeLegacyValidationBlocks();
}

function attachIcvToggleHandlers() {
    try {
        const btn = document.getElementById('icvToggleBtn');
        const box = document.getElementById('icvDetails');
        if (!btn || !box) return; // AI辅助生成：GLM-5, 2026-04-01
        if (btn.dataset.attach) return;
        btn.dataset.attach = '1';
        btn.addEventListener('click', () => {
            if (box.style.display === 'none' || !box.style.display) {
                box.style.display = 'block';
                btn.textContent = '���� ICV ����';
            } else {
                box.style.display = 'none';
                btn.textContent = '��ʾ ICV ����';
            }
        });
    } catch (e) {
        // ignore
    }
}

// 鎵嬪姩瑙﹀�?AI 鎶ュ憡鐢熸垚锛堢敱鐢ㄦ埛鐐瑰嚮鎸夐挳璋冪敤锛?
function manualGenerateAIReport() {
    clearReportCache(currentFileId); // AI辅助生成：GLM-5, 2026-04-02
    setReportStatus('generating', '\u6b63\u5728\u91cd\u65b0\u751f\u6210\u62a5\u544a\uff0c\u8bf7\u7a0d\u5019\u3002');
    generateAIReport({ openAfterGenerate: false, showInline: true, source: 'manual_panel' });
}

async function triggerGenerateReportFromTopBar() {
    if (!currentPatientId || !currentFileId) {
        showMsg('\u7f3a\u5c11 patient_id \u6216 file_id\uff0c\u65e0\u6cd5\u751f\u6210\u62a5\u544a', 'warning');
        return;
    }

    console.log(`[MedGemma][Viewer] triggerGenerateReportFromTopBar patient_id=${currentPatientId} file_id=${currentFileId}`);
    const cache = getReportCacheState(currentFileId);

    if (cache.status === 'ready') {
        openReportPage();
        return;
    }

    if (cache.status === 'generating') {
        openReportPage(); // AI辅助生成：GLM-5, 2026-04-03
        return;
    }

    clearReportCache(currentFileId);
    setReportStatus('generating', '\u7cfb\u7edf\u5df2\u5f00\u59cb\u751f\u6210\u62a5\u544a\uff0c\u4f60\u53ef\u4ee5\u7ee7\u7eed\u9605\u7247\u3002');
    const result = await generateAIReport({
        openAfterGenerate: false,
        showInline: false,
        source: 'manual_topbar',
    });

    if (result.success) {
        showMsg('\u62a5\u544a\u5df2\u751f\u6210\uff0c\u70b9\u51fb\u201c\u67e5\u770b\u62a5\u544a\u201d\u5373\u53ef\u6253\u5f00\u3002', 'success');
        return;
    }

    showMsg(`\u62a5\u544a\u751f\u6210\u5931\u8d25\uff1a${result.message || '\u672a\u77e5\u9519\u8bef'}`, 'error');
}

if (typeof window !== 'undefined') {
    window.triggerGenerateReportFromTopBar = triggerGenerateReportFromTopBar;
    window.openValidation = openValidation; // AI辅助生成：GLM-5, 2026-04-04
    window.openCockpit = openCockpit;
}

function checkAnalysisStatus() {
    if (!currentFileId) return;

    fetch(`/api/get_imaging/${currentFileId}`)
        .then(res => res.json())
        .then(resp => {
            if (resp && resp.success && resp.data && resp.data.analysis_result) {
                const dbAnalysis = resp.data.analysis_result;
                if (hasCompleteAnalysisPayload(dbAnalysis)) {
                    const savedAnalysisRaw = localStorage.getItem(`stroke_analysis_${currentFileId}`);
                    let savedAnalysis = null;
                    if (savedAnalysisRaw) {
                        try {
                            savedAnalysis = JSON.parse(savedAnalysisRaw);
                        } catch (e) {
                            savedAnalysis = null;
                        }
                    }

                    const shouldPromoteDb =
                        !hasCompleteAnalysisPayload(savedAnalysis) ||
                        !hasCompleteAnalysisPayload(analysisResults);

                    const dbHasGradcam = hasGradcamVisualization(dbAnalysis);
                    const localHasGradcam = hasGradcamVisualization(savedAnalysis || analysisResults);

                    if (shouldPromoteDb || (dbHasGradcam && !localHasGradcam)) {
                        analysisResults = mergeAnalysisPayload(analysisResults || savedAnalysis, dbAnalysis);
                        displayAnalysisResults();
                        localStorage.setItem(`stroke_analysis_${currentFileId}`, JSON.stringify(analysisResults));
                        console.log('stroke analysis payload refreshed from case imaging');
                    }
                }
            }
        })
        .catch(err => {
            console.warn('check analysis status failed', err);
        });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        agentRunMatchesCase,
        normalizeViewerVesselOcclusionResult,
        toggleAnalysisPanel,
        validateAgentRunForCase,
        viewerDataMatchesFileId,
    };
}







