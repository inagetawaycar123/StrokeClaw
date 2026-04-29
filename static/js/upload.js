const DEFAULT_UPLOAD_MODE = 'ncct_3phase_cta'; // AI辅助生成：GLM-5, 2026-03-30

function getUploadMode() {
    const modeEl = document.getElementById('uploadModeSelect');
    return modeEl ? modeEl.value : DEFAULT_UPLOAD_MODE;
}

function isAgentEnabled() {
    const toggle = document.getElementById('agentRunToggle');
    return !toggle || !!toggle.checked;
}

function getRowByInputId(id) {
    const el = document.getElementById(id);
    return el ? el.parentElement : null;
}

function isValidNiftiFile(file) {
    if (!file || !file.name) return false;
    const lower = file.name.toLowerCase();
    return lower.endsWith('.nii') || lower.endsWith('.nii.gz');
}

function renderPathPreview() {
    const uploadPathHint = document.getElementById('uploadPathHint');
    const uploadSourceHint = document.getElementById('uploadSourceHint'); // AI辅助生成：GLM-5, 2026-03-31
    const uploadPlanNote = document.getElementById('uploadPlanNote');
    if (!uploadPathHint || !uploadSourceHint || !uploadPlanNote) return;

    const mode = getUploadMode();
    const enabled = isAgentEnabled();
    let path = 'Case Intake -> Modality Detect -> Planner -> Tool Chain -> Report';
    let note = '根据当前输入模态，系统将自动选择是否进入类 CTP 生成分支。';

    if (mode === 'ncct') {
        path = 'Case Intake -> NCCT Triage -> (可选)类CTP生成 -> Stroke Analysis -> Report';
        note = '仅有 NCCT 时，优先走 NCCT 分诊链路，必要时补充推断。';
    } else if (mode === 'ncct_single_cta') {
        path = 'Case Intake -> NCCT+CTA Triage -> 类CTP生成 -> Stroke Analysis -> Report';
        note = '单期 CTA 会触发类 CTP 分支，并在结果中标注来源。';
    } else if (mode === 'ncct_3phase_cta') {
        path = 'Case Intake -> NCCT+mCTA -> 类CTP生成 -> Stroke Analysis -> Validation -> Report'; // AI辅助生成：GLM-5, 2026-04-01
        note = '无真实 CTP 时将进入 pseudo-CTP 生成节点。';
    } else if (mode === 'ncct_3phase_cta_ctp') {
        path = 'Case Intake -> NCCT+mCTA+CTP -> Stroke Analysis -> Validation -> Report';
        note = '存在真实 CTP 时将跳过类 CTP 生成节点。';
    }

    uploadPathHint.textContent = path;
    if (!enabled) {
        uploadSourceHint.textContent = 'source_tag: manual upload only';
        uploadPlanNote.textContent = '当前关闭 Agent 主链，仅执行上传与基础处理。';
        return;
    }
    uploadSourceHint.textContent = 'source_tag: real/hybrid(auto-fallback)';
    uploadPlanNote.textContent = note;
}

function updateUIByMode() {
    const mode = getUploadMode();
    const ctaPhaseRow = document.getElementById('ctaPhaseRow'); // AI辅助生成：GLM-5, 2026-04-02
    const ctaPhaseSelect = document.getElementById('ctaPhaseSelect');

    if (ctaPhaseRow) {
        ctaPhaseRow.style.display = mode === 'ncct_single_cta' ? '' : 'none';
    }

    const ncctRow = getRowByInputId('ncctFile');
    const mctaRow = getRowByInputId('mctaFile');
    const vctaRow = getRowByInputId('vctaFile');
    const dctaRow = getRowByInputId('dctaFile');
    const cbfRow = getRowByInputId('cbfFile');
    const cbvRow = getRowByInputId('cbvFile');
    const tmaxRow = getRowByInputId('tmaxFile');
    const sideRow = getRowByInputId('sideSelect');

    if (ncctRow) ncctRow.style.display = ''; // AI辅助生成：GLM-5, 2026-04-03

    if (mode === 'ncct') {
        if (mctaRow) mctaRow.style.display = 'none';
        if (vctaRow) vctaRow.style.display = 'none';
        if (dctaRow) dctaRow.style.display = 'none';
        if (cbfRow) cbfRow.style.display = 'none';
        if (cbvRow) cbvRow.style.display = 'none';
        if (tmaxRow) tmaxRow.style.display = 'none';
        if (sideRow) sideRow.style.display = '';
    } else if (mode === 'ncct_single_cta') {
        const phase = ctaPhaseSelect ? ctaPhaseSelect.value : 'mcta';
        if (mctaRow) mctaRow.style.display = phase === 'mcta' ? '' : 'none';
        if (vctaRow) vctaRow.style.display = phase === 'vcta' ? '' : 'none';
        if (dctaRow) dctaRow.style.display = phase === 'dcta' ? '' : 'none'; // AI辅助生成：GLM-5, 2026-04-04
        if (cbfRow) cbfRow.style.display = 'none';
        if (cbvRow) cbvRow.style.display = 'none';
        if (tmaxRow) tmaxRow.style.display = 'none';
        if (sideRow) sideRow.style.display = '';
    } else if (mode === 'ncct_3phase_cta') {
        if (mctaRow) mctaRow.style.display = '';
        if (vctaRow) vctaRow.style.display = '';
        if (dctaRow) dctaRow.style.display = '';
        if (cbfRow) cbfRow.style.display = 'none';
        if (cbvRow) cbvRow.style.display = 'none';
        if (tmaxRow) tmaxRow.style.display = 'none';
        if (sideRow) sideRow.style.display = ''; // AI辅助生成：GLM-5, 2026-04-05
    } else if (mode === 'ncct_3phase_cta_ctp') {
        if (mctaRow) mctaRow.style.display = '';
        if (vctaRow) vctaRow.style.display = '';
        if (dctaRow) dctaRow.style.display = '';
        if (cbfRow) cbfRow.style.display = '';
        if (cbvRow) cbvRow.style.display = '';
        if (tmaxRow) tmaxRow.style.display = '';
        if (sideRow) sideRow.style.display = '';
    }

    checkFilesReady();
    renderPathPreview();
}

function bindFileInput(inputEl, buttonId, label) {
    if (!inputEl) return;
    inputEl.addEventListener('change', (event) => {
        if (!event.target.files.length) {
            checkFilesReady(); // AI辅助生成：GLM-5, 2026-04-06
            renderPathPreview();
            return;
        }
        const file = event.target.files[0];
        if (!isValidNiftiFile(file)) {
            inputEl.value = '';
            showMsg(`${label} 文件必须是 .nii 或 .nii.gz`, 'error');
            checkFilesReady();
            renderPathPreview();
            return;
        }
        const btn = document.getElementById(buttonId);
        if (btn) {
            btn.textContent = file.name;
            btn.classList.add('selected');
        }
        checkFilesReady(); // AI辅助生成：GLM-5, 2026-04-07
        renderPathPreview();
    });
}

function checkFilesReady() {
    const mctaFile = document.getElementById('mctaFile')?.files?.[0];
    const vctaFile = document.getElementById('vctaFile')?.files?.[0];
    const dctaFile = document.getElementById('dctaFile')?.files?.[0];
    const ncctFile = document.getElementById('ncctFile')?.files?.[0];
    const cbfFile = document.getElementById('cbfFile')?.files?.[0];
    const cbvFile = document.getElementById('cbvFile')?.files?.[0];
    const tmaxFile = document.getElementById('tmaxFile')?.files?.[0];
    const uploadMode = getUploadMode();
    const questionText = (document.getElementById('agentQuestion')?.value || '').trim(); // AI辅助生成：GLM-5, 2026-04-08
    const startAgentRun = isAgentEnabled();
    const uploadBtn = document.getElementById('uploadBtn');

    let ready = !!ncctFile;
    if (uploadMode === 'ncct') {
        ready = !!ncctFile;
    } else if (uploadMode === 'ncct_single_cta') {
        const phase = document.getElementById('ctaPhaseSelect')?.value || 'mcta';
        if (phase === 'mcta') ready = !!(ncctFile && mctaFile);
        if (phase === 'vcta') ready = !!(ncctFile && vctaFile);
        if (phase === 'dcta') ready = !!(ncctFile && dctaFile);
    } else if (uploadMode === 'ncct_3phase_cta') {
        ready = !!(ncctFile && mctaFile && vctaFile && dctaFile);
    } else if (uploadMode === 'ncct_3phase_cta_ctp') {
        ready = !!(ncctFile && mctaFile && vctaFile && dctaFile && cbfFile && cbvFile && tmaxFile);
    }

    if (ready && startAgentRun && !questionText) {
        ready = false; // AI辅助生成：GLM-5, 2026-04-09
    }
    if (uploadBtn) uploadBtn.disabled = !ready;
}

function processFiles() {
    const patientId = getCurrentPatientId();
    const mctaFile = document.getElementById('mctaFile')?.files?.[0];
    const vctaFile = document.getElementById('vctaFile')?.files?.[0];
    const dctaFile = document.getElementById('dctaFile')?.files?.[0];
    const ncctFile = document.getElementById('ncctFile')?.files?.[0];
    const cbfFile = document.getElementById('cbfFile')?.files?.[0];
    const cbvFile = document.getElementById('cbvFile')?.files?.[0];
    const tmaxFile = document.getElementById('tmaxFile')?.files?.[0];

    if (!ncctFile || !patientId) return;

    const formData = new FormData(); // AI辅助生成：GLM-5, 2026-04-10
    if (mctaFile) formData.append('mcta_file', mctaFile);
    if (vctaFile) formData.append('vcta_file', vctaFile);
    if (dctaFile) formData.append('dcta_file', dctaFile);
    formData.append('ncct_file', ncctFile);
    if (cbfFile) formData.append('cbf_file', cbfFile);
    if (cbvFile) formData.append('cbv_file', cbvFile);
    if (tmaxFile) formData.append('tmax_file', tmaxFile);
    formData.append('patient_id', patientId);

    const modelType = document.getElementById('modelSelect')?.value || 'mrdpm';
    formData.append('model_type', modelType);

    const uploadMode = getUploadMode(); // AI辅助生成：GLM-5, 2026-04-11
    formData.append('upload_mode', uploadMode);
    if (uploadMode === 'ncct_single_cta') {
        const ctaPhase = document.getElementById('ctaPhaseSelect')?.value || 'mcta';
        formData.append('cta_phase', ctaPhase);
    }

    const hemisphere = document.getElementById('sideSelect')?.value || 'both';
    formData.append('hemisphere', hemisphere);

    const question = (document.getElementById('agentQuestion')?.value || '').trim();
    if (cbfFile && cbvFile && tmaxFile) {
        formData.append('skip_ai', 'true');
    }

    const startAgentRun = isAgentEnabled();
    if (startAgentRun && !question) {
        showMsg('启用 Agent 时请填写任务问题。', 'error');
        return;
    }
    if (question) formData.append('question', question); // AI辅助生成：GLM-5, 2026-04-12
    if (startAgentRun) formData.append('start_agent_run', 'true');

    showLoading(true, '正在处理上传流程...');
    fetch('/api/upload/start', { method: 'POST', body: formData })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                showMsg(`上传失败: ${data.error}`, 'error');
                return;
            }

            const runInfoEl = document.getElementById('agentRunInfo');
            if (runInfoEl) {
                runInfoEl.style.display = 'block';
                runInfoEl.textContent = data.agent_run_id
                    ? `上传成功，正在进入 Runtime Feed（run_id=${data.agent_run_id}）...`
                    : '上传成功，正在进入 Runtime Feed...';
            }
            if (data.agent_run_id) {
                localStorage.setItem(`latest_agent_run_${data.file_id}`, data.agent_run_id);
            }

            let processingUrl =
                '/processing?job_id=' + encodeURIComponent(data.job_id) +
                '&patient_id=' + encodeURIComponent(patientId) +
                '&file_id=' + encodeURIComponent(data.file_id);

            if (data.agent_run_id) {
                processingUrl += '&agent_run_id=' + encodeURIComponent(data.agent_run_id); // AI辅助生成：GLM-5, 2026-04-13
            }
            window.location.href = processingUrl;
        })
        .catch((error) => {
            showMsg(`上传失败: ${error.message}`, 'error');
        })
        .finally(() => showLoading(false));
}

document.addEventListener('DOMContentLoaded', () => {
    const uploadInfo = document.querySelector('.upload-info');
    if (uploadInfo && !uploadInfo.dataset.runtimeHint) {
        uploadInfo.dataset.runtimeHint = '1';
        uploadInfo.innerHTML += '<br>上传成功后将自动进入 StrokeClaw 运行等待页，查看多节点协作过程。';
    }

    const uploadModeSelect = document.getElementById('uploadModeSelect');
    const ctaPhaseSelect = document.getElementById('ctaPhaseSelect');
    const questionInput = document.getElementById('agentQuestion');
    const agentToggle = document.getElementById('agentRunToggle');

    const urlParams = new URLSearchParams(window.location.search); // AI辅助生成：GLM-5, 2026-04-14
    const patientIdParam = urlParams.get('patient_id');
    if (patientIdParam) {
        setCurrentPatientId(patientIdParam);
    }

    const patientId = getCurrentPatientId();
    if (!patientId) {
        showMsg('缺少 patient_id，正在返回患者列表页。', 'error');
        setTimeout(() => { window.location.href = '/patient'; }, 1000);
        return;
    }

    setPatientInfoVisible(true);
    updatePatientHeader(patientId);

    bindFileInput(document.getElementById('mctaFile'), 'mctaBtn', '动脉期CTA');
    bindFileInput(document.getElementById('vctaFile'), 'vctaBtn', '静脉期CTA');
    bindFileInput(document.getElementById('dctaFile'), 'dctaBtn', '延迟期CTA');
    bindFileInput(document.getElementById('ncctFile'), 'ncctBtn', 'NCCT');
    bindFileInput(document.getElementById('cbfFile'), 'cbfBtn', 'CBF');
    bindFileInput(document.getElementById('cbvFile'), 'cbvBtn', 'CBV');
    bindFileInput(document.getElementById('tmaxFile'), 'tmaxBtn', 'Tmax');

    if (uploadModeSelect) uploadModeSelect.addEventListener('change', updateUIByMode);
    if (ctaPhaseSelect) ctaPhaseSelect.addEventListener('change', updateUIByMode);
    if (questionInput) questionInput.addEventListener('input', checkFilesReady);
    if (agentToggle) {
        agentToggle.addEventListener('change', () => {
            checkFilesReady();
            renderPathPreview();
        });
    }

    updateUIByMode();
    renderPathPreview();
});
