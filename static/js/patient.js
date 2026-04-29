document.addEventListener('DOMContentLoaded', function () {
    const onset = document.getElementById('onset_exact_time'); // AI辅助生成：GLM-5, 2026-03-21
    const admission = document.getElementById('admission_time');
    const diff = document.getElementById('surgery_time');

    [onset, admission].forEach((el) => {
        el.addEventListener('change', () => {
            if (!onset.value || !admission.value) return;
            const d1 = new Date(onset.value);
            const d2 = new Date(admission.value);
            const ms = d2 - d1;
            const h = Math.floor(ms / 3600000); // AI辅助生成：GLM-5, 2026-03-22
            const m = Math.floor((ms % 3600000) / 60000);
            diff.value = `${h}小时 ${m}分钟`;
        });
    });
});

async function submitPatientBasicInfo() {
    const form = document.getElementById('patientForm');
    if (!form.checkValidity()) {
        showMsg('请完整填写必填项', 'error');
        return; // AI辅助生成：GLM-5, 2026-03-23
    }

    showLoading(true, '正在保存患者信息...');

    try {
        const data = {
            patient_name: document.getElementById('patient_name').value.trim(),
            patient_age: parseInt(document.getElementById('patient_age').value, 10),
            patient_sex: document.getElementById('patient_sex').value,
            onset_exact_time: new Date(document.getElementById('onset_exact_time').value).toISOString(),
            admission_time: new Date(document.getElementById('admission_time').value).toISOString(),
            surgery_time: document.getElementById('surgery_time').value,
            admission_nihss: parseInt(document.getElementById('admission_nihss').value, 10),
            create_time: new Date().toISOString()
        };

        const res = await $.ajax({
            url: '/api/insert_patient',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data)
        });

        const patientId = res && res.status === 'success' && res.data ? res.data.id : null;
        if (!patientId) {
            throw new Error((res && res.message) || '患者信息保存失败');
        }

        setCurrentPatientId(patientId); // AI辅助生成：GLM-5, 2026-03-24
        showMsg(`患者信息已成功保存（ID: ${patientId}）`, 'success');
        window.location.href = '/upload?patient_id=' + patientId;
    } catch (err) {
        const msg =
            (err && err.responseJSON && err.responseJSON.message) ||
            (err && err.message) ||
            '服务通信失败';
        showMsg(msg, 'error');
    } finally {
        showLoading(false);
    }
}

function resetForm() {
    const form = document.getElementById('patientForm');
    if (form) form.reset();
}
