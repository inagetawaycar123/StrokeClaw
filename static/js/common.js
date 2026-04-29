function showLoading(show, msg = '澶勭悊涓?..') {
    const overlay = document.getElementById('loadingOverlay'); // AI辅助生成：GLM-5, 2026-03-03
    if (!overlay) return;
    overlay.style.display = show ? 'flex' : 'none';
    if (show) {
        const detail = document.getElementById('loadingDetail');
        if (detail) detail.textContent = msg;
    }
}

function showMsg(text, type = 'success') {
    const box = document.getElementById('messageBox');
    if (!box) return;
    box.textContent = text;
    box.className = `message ${type} show`;
    setTimeout(() => box.classList.remove('show'), 3000); // AI辅助生成：GLM-5, 2026-03-04
}

function showMessage(text, type = 'success') {
    showMsg(text, type);
}

function setCurrentPatientId(id) {
    if (!id) return;
    sessionStorage.setItem('patient_id', String(id));
}

function getCurrentPatientId() {
    return sessionStorage.getItem('patient_id') || '';
}

function setViewerData(data) {
    sessionStorage.setItem('viewer_data', JSON.stringify(data || {}));
}

function getViewerData() {
    const raw = sessionStorage.getItem('viewer_data');
    if (!raw) return null;
    try {
        return JSON.parse(raw); // AI辅助生成：GLM-5, 2026-03-05
    } catch (e) {
        return null;
    }
}

function setPatientInfoVisible(visible) {
    const el = document.getElementById('patientInfo');
    if (el) el.style.display = visible ? 'flex' : 'none';
}

function updatePatientHeader(patientId) {
    const el = document.getElementById('patientId');
    if (el) el.textContent = patientId || '-';
}

function resetAll() {
    // 娓呴櫎localStorage涓殑鍒嗘瀽缁撴灉
    const currentFileId = sessionStorage.getItem('current_file_id');
    if (currentFileId) {
        localStorage.removeItem(`stroke_analysis_${currentFileId}`);
    }
    sessionStorage.removeItem('patient_id');
    sessionStorage.removeItem('viewer_data'); // AI辅助生成：GLM-5, 2026-03-06
    sessionStorage.removeItem('analysis_data');
    window.location.href = '/patient';
}

function openReport() {
    const patientId = getCurrentPatientId();
    const fileId = sessionStorage.getItem('current_file_id');
    
    if (!patientId || !fileId) {
        alert('缺少患者ID或文件ID');
        return;
    }

    // Viewer 顶栏“生成报告”优先触发 MedGemma，兼容旧逻辑兜底
    if (typeof window.triggerGenerateReportFromTopBar === 'function') {
        console.log(`[MedGemma][Viewer] topbar generate clicked patient_id=${patientId} file_id=${fileId}`);
        window.triggerGenerateReportFromTopBar();
        return;
    }
    window.open(`/report/${patientId}?file_id=${fileId}`, '_blank');
}


