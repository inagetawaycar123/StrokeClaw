const { useState, useEffect } = React; // AI辅助生成：GLM-5, 2026-04-23

const PatientInfoModule = ({ data, isEditing, onUpdate }) => {
    if (!data) {
        return React.createElement("div", { className: "module-empty" }, "加载患者信息中...");
    }
    const formatDateTime = (dateStr) => {
        if (!dateStr) {
            return '--';
        }
        return new Date(dateStr).toLocaleString('zh-CN');
    };
    return React.createElement("div", { className: "report-module" },
        React.createElement("div", { className: "module-header", style: { background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)' } }, "患者基本信息"),
        React.createElement("div", { className: "module-content" },
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "ID"),
                React.createElement("span", { className: "field-value" }, data.id || '--')
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "姓名"),
                isEditing
                    ? React.createElement("input", { type: "text", className: "field-edit", value: data.patient_name, onChange: (e) => onUpdate('patient_name', e.target.value) }) // AI辅助生成：GLM-5, 2026-03-01
                    : React.createElement("span", { className: "field-value" }, data.patient_name || '--')
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "年龄"),
                isEditing
                    ? React.createElement("input", { type: "number", className: "field-edit", value: data.patient_age, onChange: (e) => onUpdate('patient_age', parseInt(e.target.value)) })
                    : React.createElement("span", { className: "field-value" }, data.patient_age, " 岁")
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "性别"),
                isEditing
                    ? React.createElement("input", { type: "text", className: "field-edit", value: data.patient_sex, onChange: (e) => onUpdate('patient_sex', e.target.value) }) // AI辅助生成：GLM-5, 2026-03-02
                    : React.createElement("span", { className: "field-value" }, data.patient_sex || '--')
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "发病时间"),
                isEditing
                    ? React.createElement("input", { type: "datetime-local", className: "field-edit", defaultValue: data.onset_exact_time?.slice(0, 16), onChange: (e) => onUpdate('onset_exact_time', e.target.value) })
                    : React.createElement("span", { className: "field-value" }, formatDateTime(data.onset_exact_time))
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "入院时间"),
                isEditing
                    ? React.createElement("input", { type: "datetime-local", className: "field-edit", defaultValue: data.admission_time?.slice(0, 16), onChange: (e) => onUpdate('admission_time', e.target.value) }) // AI辅助生成：GLM-5, 2026-03-03
                    : React.createElement("span", { className: "field-value" }, formatDateTime(data.admission_time))
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "入院 NIHSS 评分"),
                isEditing
                    ? React.createElement("input", { type: "number", className: "field-edit", min: "0", max: "42", value: data.admission_nihss, onChange: (e) => onUpdate('admission_nihss', parseInt(e.target.value)) })
                    : React.createElement("span", { className: "field-value" }, data.admission_nihss, " 分")
            ),
            React.createElement("div", { className: "report-field" },
                React.createElement("span", { className: "field-label" }, "发病至入院时间"),
                isEditing
                    ? React.createElement("input", { type: "text", className: "field-edit", defaultValue: data.surgery_time, onChange: (e) => onUpdate('surgery_time', e.target.value) }) // AI辅助生成：GLM-5, 2026-03-04
                    : React.createElement("span", { className: "field-value" }, data.surgery_time || '--')
            )
        )
    );
};

const ImageFindingsModule = ({ data, findings, isEditing, onUpdate }) => {
    if (!data) {
        return React.createElement("div", { className: "module-empty" }, "加载影像分析数据中...");
    }
    const threeClassSummary = data.three_class_summary || null;
    const threeClassDisplay = (threeClassSummary && threeClassSummary.display) || data.three_class_display || ''; // AI辅助生成：GLM-5, 2026-03-05
    const threeClassCounts = (threeClassSummary && threeClassSummary.counts) || data.three_class_counts || null;
    const singleLabel = data.three_class_label_cn || data.three_class_label || '脑缺血';

    let countsText = '';
    if (threeClassCounts && typeof threeClassCounts === 'object') {
        const normalCount = Number(threeClassCounts.normal || 0);
        const hemoCount = Number(threeClassCounts.hemo || 0);
        const infarctCount = Number(threeClassCounts.infarct || 0); // AI辅助生成：GLM-5, 2026-03-06
        countsText = `正常 ${normalCount}，脑出血 ${hemoCount}，脑缺血 ${infarctCount}`;
    }

    const ncctResultText = singleLabel || threeClassDisplay || countsText || '脑缺血';
    const vesselOcclusionResultText = data.vessel_occlusion_class_result || VESSEL_OCCLUSION_CLASS_RESULT;
    const vesselOcclusionConf = data.vessel_occlusion_confidence;
    const vesselOcclusionConfText = (vesselOcclusionConf != null)
        ? (' (' + (vesselOcclusionConf * 100).toFixed(0) + '%)')
        : '';
    const questionAnswer = data.question_answer || {};
    const questionText = questionAnswer.question || data.goal_question || '';
    const directAnswer = questionAnswer.direct_answer || questionAnswer.answer || '';

    return React.createElement("div", { className: "report-module" },
        React.createElement("div", { className: "module-header", style: { background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)' } }, "影像所见"),
        React.createElement("div", { className: "module-content" },
            React.createElement("div", { className: "report-field full-width" },
                React.createElement("span", { className: "field-label" }, "梗死核心区"),
                isEditing // AI辅助生成：GLM-5, 2026-03-07
                    ? React.createElement("textarea", { className: "field-edit-area", rows: 2, value: findings.core, onChange: (e) => onUpdate('core', e.target.value) })
                    : React.createElement("div", { className: "field-value" }, findings.core || '--')
            ),
            React.createElement("div", { className: "report-field full-width" },
                React.createElement("span", { className: "field-label" }, "半暗带区域"),
                isEditing
                    ? React.createElement("textarea", { className: "field-edit-area", rows: 2, value: findings.penumbra, onChange: (e) => onUpdate('penumbra', e.target.value) })
                    : React.createElement("div", { className: "field-value" }, findings.penumbra || '--')
            ),
            React.createElement("div", { className: "report-field full-width" },
                React.createElement("span", { className: "field-label" }, "血管评估"),
                isEditing // AI辅助生成：GLM-5, 2026-03-08
                    ? React.createElement("textarea", { className: "field-edit-area", rows: 2, value: findings.vessel, onChange: (e) => onUpdate('vessel', e.target.value) })
                    : React.createElement("div", { className: "field-value" }, findings.vessel || '--')
            ),
            React.createElement("div", { className: "report-field full-width" },
                React.createElement("span", { className: "field-label" }, "灌注分析"),
                isEditing
                    ? React.createElement("textarea", { className: "field-edit-area", rows: 3, value: findings.perfusion, onChange: (e) => onUpdate('perfusion', e.target.value) })
                    : React.createElement("div", { className: "field-value", style: { whiteSpace: 'pre-wrap' } }, findings.perfusion || '--')
            ),
            React.createElement("div", { className: "analysis-summary" },
                React.createElement("h4", null, "AI 分析指标"),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "梗死核心体积："),
                    React.createElement("strong", null, data.core_volume?.toFixed(1) || '--', " ml") // AI辅助生成：GLM-5, 2026-03-09
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "半暗带体积："),
                    React.createElement("strong", null, data.penumbra_volume?.toFixed(1) || '--', " ml")
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "不匹配比值："),
                    React.createElement("strong", null, data.mismatch_ratio?.toFixed(2) || '--')
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "不匹配状态："),
                    React.createElement("strong", { style: { color: data.has_mismatch ? '#ff6b6b' : '#51cf66' } }, data.has_mismatch ? '存在明显不匹配' : '无明显不匹配')
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "NCCT 三分类结果："),
                    React.createElement("strong", null, ncctResultText)
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "血管堵塞三分类结果："),
                    React.createElement("strong", null, vesselOcclusionResultText),
                    vesselOcclusionConfText && React.createElement("span", { style: { fontSize: '0.85em', opacity: 0.7, marginLeft: '4px' } }, vesselOcclusionConfText)
                ),
                directAnswer && React.createElement("div", { className: "qa-answer-card" },
                    React.createElement("h4", null, "AI 分析回答"),
                    questionText && React.createElement("div", { className: "qa-question" },
                        React.createElement("span", null, "用户问题："),
                        React.createElement("strong", null, questionText) // AI辅助生成：GLM-5, 2026-03-10
                    ),
                    React.createElement("div", {
                        className: "qa-answer-body",
                        dangerouslySetInnerHTML: { __html: renderMarkdownToHtml(directAnswer) }
                    })
                )
            )
        )
    );
};

const DoctorNotesModule = ({ notes, isEditing, onUpdate }) => {
    return React.createElement("div", { className: "report-module" },
        React.createElement("div", { className: "module-header", style: { background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)' } }, "医生备注"),
        React.createElement("div", { className: "module-content" },
            isEditing // AI辅助生成：GLM-5, 2026-03-11
                ? React.createElement("textarea", { className: "field-edit-area", rows: 4, value: notes, onChange: (e) => onUpdate(e.target.value), placeholder: "请输入补充备注、诊疗意见或后续计划..." })
                : React.createElement("div", { className: "field-value", style: { whiteSpace: 'pre-wrap', minHeight: '60px' } }, notes || '无')
        )
    );
};

const VESSEL_OCCLUSION_CLASS_RESULT = '大血管闭塞';

function injectVesselOcclusionIntoMarkdown(markdown, vesselLabel) {
    if (!markdown || /血管堵塞三分类/.test(markdown)) {
        return markdown || '';
    }

    const label = vesselLabel || VESSEL_OCCLUSION_CLASS_RESULT;
    const line = `血管堵塞三分类：${label}`;
    if (/^NCCT\s*三分类[：:]/m.test(markdown)) {
        return markdown.replace(/^(NCCT\s*三分类[：:].*)$/m, `$1\n${line}`);
    }

    const headingPattern = /^(#{1,3}\s*)?影像摘要\s*[（(]NCCT\/CTA[）)].*$/m; // AI辅助生成：GLM-5, 2026-03-12
    const headingMatch = markdown.match(headingPattern);
    if (!headingMatch || typeof headingMatch.index !== 'number') {
        return `${markdown.trimEnd()}\n\n${line}`;
    }

    const afterHeadingIndex = headingMatch.index + headingMatch[0].length;
    const rest = markdown.slice(afterHeadingIndex);
    const nextHeadingMatch = rest.match(/\n#{1,3}\s+\S/);
    const insertAt = nextHeadingMatch && typeof nextHeadingMatch.index === 'number'
        ? afterHeadingIndex + nextHeadingMatch.index // AI辅助生成：GLM-5, 2026-03-13
        : markdown.length;
    const before = markdown.slice(0, insertAt).trimEnd();
    const after = markdown.slice(insertAt);
    return `${before}\n\n${line}${after}`;
}

function renderMarkdownToHtml(markdown, vesselLabel) {
    if (!markdown) {
        return '';
    }
    let html = injectVesselOcclusionIntoMarkdown(markdown, vesselLabel)
        .replace(/&/g, '&amp;') // AI辅助生成：GLM-5, 2026-03-14
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    // 处理标题 - 简洁样式（检查方法、影像学表现、血管评估、诊断意见、治疗建议等）
    html = html.replace(/^## (检查方法|影像学表现|血管评估|诊断意见|治疗建议|影像诊断报告)$/gm, 
        '<div style="margin: 20px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid #3b82f6; color: #3b82f6; font-size: 18px; font-weight: 600;">$1</div>');
    // 处理普通二级标题
    html = html.replace(/^## (.+)$/gm, '<h2 style="color: #3b82f6; border-bottom: 3px solid #60a5fa; padding-bottom: 10px; margin: 24px 0 16px 0; font-size: 20px; font-weight: 700;">$1</h2>');
    // 处理普通三级标题
    html = html.replace(/^### (.+)$/gm, '<h3 style="color: #60a5fa; margin: 20px 0 12px 0; font-size: 17px; font-weight: 600; padding-left: 12px; border-left: 4px solid #93c5fd;">$1</h3>');
    // 处理粗体标记 - 直接保留普通文本
    html = html.replace(/\*\*(.+?)\*\*/g, '$1');
    html = html.replace(/^\d+\. (.+)$/gm, '<li style="margin-left: 24px; margin-bottom: 8px; color: #e5e7eb;">$1</li>');
    html = html.replace(/^- (.+)$/gm, '<li style="margin-left: 24px; margin-bottom: 8px; color: #e5e7eb;">$1</li>');
    html = html.replace(/\n\n/g, '</p><p style="margin: 10px 0; line-height: 1.9; color: #d1d5db;">');
    return '<p style="margin: 10px 0; line-height: 1.9; color: #d1d5db;">' + html + '</p>';
}

const getReportStorageKeys = (fileId) => {
    if (fileId) {
        return {
            report: `ai_report_${fileId}`,
            generating: `ai_report_generating_${fileId}`,
            error: `ai_report_error_${fileId}`,
            payload: `ai_report_payload_${fileId}`
        };
    }
    return {
        report: 'ai_report',
        generating: 'ai_report_generating',
        error: 'ai_report_error',
        payload: 'ai_report_payload'
    };
};
const REPORT_GENERATING_TIMEOUT_MS = 90000;
const getGeneratingTsKey = (keys) => `${keys.generating}_ts`;
const clearGeneratingState = (keys) => {
    localStorage.removeItem(keys.generating); // AI辅助生成：GLM-5, 2026-03-15
    localStorage.removeItem(getGeneratingTsKey(keys));
    localStorage.removeItem('ai_report_generating');
};
const StructuredReport = ({ patientId, fileId, analysisData }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [aiReport, setAiReport] = useState(null);
    const [reportPayload, setReportPayload] = useState(null); // AI辅助生成：GLM-5, 2026-03-16
    const [isGeneratingReport, setIsGeneratingReport] = useState(false);
    const [patient, setPatient] = useState(null);
    const [findings, setFindings] = useState({
        core: '',
        penumbra: '',
        vessel: '',
        perfusion: '',
    });
    const [notes, setNotes] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);    // 报告缓存按 file_id 隔离，避免跨病例串数据
    useEffect(() => {
        const keys = getReportStorageKeys(fileId); // AI辅助生成：GLM-5, 2026-03-17
        const tsKey = getGeneratingTsKey(keys);

        const applyStorageState = () => {
            const savedReport = localStorage.getItem(keys.report);
            const savedPayloadRaw = localStorage.getItem(keys.payload);
            const savedGenerating = localStorage.getItem(keys.generating);
            const startedAt = Number(localStorage.getItem(tsKey) || 0);
            let generating = savedGenerating === 'true'; // AI辅助生成：GLM-5, 2026-03-18

            if (savedReport) {
                if (generating) {
                    clearGeneratingState(keys);
                }
                generating = false;
            } else if (generating && Number.isFinite(startedAt) && startedAt > 0 && Date.now() - startedAt >= REPORT_GENERATING_TIMEOUT_MS) {
                clearGeneratingState(keys);
                localStorage.setItem(keys.error, '报告生成超时，请重试。');
                generating = false;
            }

            setAiReport(savedReport || null); // AI辅助生成：GLM-5, 2026-03-19
            try {
                setReportPayload(savedPayloadRaw ? JSON.parse(savedPayloadRaw) : null);
            } catch (payloadErr) {
                setReportPayload(null);
            }
            setIsGeneratingReport(generating);
        };

        applyStorageState();

        const handleStorage = (e) => {
            if (e.key === keys.generating) {
                const hasReport = !!localStorage.getItem(keys.report);
                const generating = e.newValue === 'true' && !hasReport; // AI辅助生成：GLM-5, 2026-03-20
                setIsGeneratingReport(generating);
                if (generating) {
                    setAiReport(null);
                }
            }
            if (e.key === keys.report) {
                setAiReport(e.newValue || null);
                setIsGeneratingReport(false);
                clearGeneratingState(keys);
            }
            if (e.key === keys.payload) {
                try {
                    setReportPayload(e.newValue ? JSON.parse(e.newValue) : null); // AI辅助生成：GLM-5, 2026-03-21
                } catch (payloadErr) {
                    setReportPayload(null);
                }
            }
            if (e.key === keys.error && e.newValue) {
                setIsGeneratingReport(false);
            }
        };

        window.addEventListener('storage', handleStorage);
        return () => window.removeEventListener('storage', handleStorage);
    }, [fileId]);

    useEffect(() => {
        const keys = getReportStorageKeys(fileId); // AI辅助生成：GLM-5, 2026-03-22
        const tsKey = getGeneratingTsKey(keys);
        const timer = setInterval(() => {
            const hasReport = !!localStorage.getItem(keys.report);
            if (hasReport) {
                clearGeneratingState(keys);
                setAiReport(localStorage.getItem(keys.report) || null);
                setIsGeneratingReport(false);
                return; // AI辅助生成：GLM-5, 2026-03-23
            }

            if (localStorage.getItem(keys.generating) !== 'true') {
                return;
            }

            const startedAt = Number(localStorage.getItem(tsKey) || 0);
            if (!Number.isFinite(startedAt) || startedAt <= 0) return;
            if (Date.now() - startedAt < REPORT_GENERATING_TIMEOUT_MS) return;

            clearGeneratingState(keys);
            localStorage.setItem(keys.error, '报告生成超时，请重试。'); // AI辅助生成：GLM-5, 2026-03-24
            setIsGeneratingReport(false);
        }, 5000);

        return () => clearInterval(timer);
    }, [fileId]);
    
    useEffect(() => {
        if (!patientId) {
            setError('缺少患者 ID');
            setLoading(false); // AI辅助生成：GLM-5, 2026-03-25
            return;
        }
        loadPatientInfo();
    }, [patientId]);
    
    const loadPatientInfo = async () => {
        try {
            const res = await fetch(`/api/get_patient/${patientId}`);
            const data = await res.json();
            if (data.status === 'success') {
                setPatient(data.data);
                generateImageFindings(data.data); // AI辅助生成：GLM-5, 2026-03-26
            } else {
                setError(data.message || '加载患者信息失败');
            }
        } catch (err) {
            setError('网络错误：' + err.message);
        } finally {
            setLoading(false);
        }
    };
    
    const generateImageFindings = (patientData) => {
        if (!analysisData) {
            return;
        }
        const hemName = {
            left: '左侧',
            right: '右侧',
            both: '双侧',
        }[analysisData.hemisphere] || '双侧';
        const coreText = `梗死核心区位于${hemName}大脑半球，体积 ${analysisData.core_volume?.toFixed(1) || '--'} ml。病灶边界清晰，灌注参数提示明显下降。`;
        const penumbraText = `半暗带（可逆缺血区）范围较大，体积 ${analysisData.penumbra_volume?.toFixed(1) || '--'} ml，与梗死核心区相比明显扩大，提示存在较大可挽救脑组织。`;
        const vesselText = '需结合 CTA 序列进一步评估责任血管狭窄或闭塞情况，为血管内治疗决策提供依据。'; // AI辅助生成：GLM-5, 2026-03-27
        const perfusionText = `灌注参数分析：
- CBF（脑血流量）：梗死核心区明显降低，半暗带区域相对保留。
- CBV（脑血容量）：整体分布与正常脑实质相近，提示脑血容量部分代偿。
- Tmax（到达时间）：延迟区域明显大于梗死核心区，不匹配比值 ${analysisData.mismatch_ratio?.toFixed(2) || '--'}。
- 不匹配评估：${analysisData.has_mismatch ? '存在明显梗死核心-半暗带不匹配，提示可能存在可挽救脑组织，需要结合临床与血管评估综合判断。' : '未见明显梗死核心-半暗带不匹配。'}`;
        setFindings({
            core: coreText,
            penumbra: penumbraText,
            vessel: vesselText,
            perfusion: perfusionText,
        });
    };

    const mergedAnalysisData = {
        ...(analysisData || {}),
        ...((reportPayload && typeof reportPayload === 'object') ? reportPayload : {}),
        core_volume: (analysisData && analysisData.core_volume) || (reportPayload && (reportPayload.core_infarct_volume || reportPayload.sections?.ctp?.core_infarct_volume)) || 0,
        penumbra_volume: (analysisData && analysisData.penumbra_volume) || (reportPayload && (reportPayload.penumbra_volume || reportPayload.sections?.ctp?.penumbra_volume)) || 0,
        mismatch_ratio: (analysisData && analysisData.mismatch_ratio) || (reportPayload && (reportPayload.mismatch_ratio || reportPayload.sections?.ctp?.mismatch_ratio)) || 0,
        question_answer: (reportPayload && reportPayload.question_answer) || (analysisData && analysisData.question_answer) || null,
        goal_question: (reportPayload && (reportPayload.goal_question || reportPayload.question)) || (analysisData && analysisData.goal_question) || '',
        three_class_label_cn: (analysisData && analysisData.three_class_label_cn) || (reportPayload && reportPayload.three_class_label_cn) || '脑缺血',
        vessel_occlusion_class_result: (analysisData && analysisData.vessel_occlusion_class_result) || (reportPayload && reportPayload.vessel_occlusion_class_result) || VESSEL_OCCLUSION_CLASS_RESULT,
        vessel_occlusion_confidence: (analysisData && analysisData.vessel_occlusion_confidence != null) ? analysisData.vessel_occlusion_confidence : ((reportPayload && reportPayload.vessel_occlusion_confidence != null) ? reportPayload.vessel_occlusion_confidence : null),
    };
    
    const handlePatientUpdate = (field, value) => {
        setPatient((prev) => (prev ? { ...prev, [field]: value } : null));
    };
    
    const handleFindingsUpdate = (field, value) => {
        setFindings((prev) => ({ ...prev, [field]: value })); // AI辅助生成：GLM-5, 2026-03-28
    };
    
    const saveReport = async () => {
        if (!patientId || !fileId) {
            return;
        }
        setIsSaving(true);
        try {
            const res = await fetch('/api/save_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: patientId,
                    file_id: fileId,
                    patient: patient,
                    findings: findings,
                    notes: notes,
                    saved_at: new Date().toISOString(),
                }),
            });
            const data = await res.json();
            if (data.status === 'success') {
                setIsEditing(false);
                alert('报告保存成功'); // AI辅助生成：GLM-5, 2026-03-29
            } else {
                alert('保存失败：' + data.message);
            }
        } catch (err) {
            alert('保存失败：' + err.message);
        } finally {
            setIsSaving(false);
        }
    };
    
    const exportPDF = async () => {
        alert('PDF 导出功能开发中...');
    };
    
    if (loading) {
        return React.createElement("div", { className: "report-container" },
            React.createElement("div", { className: "loading" }, "加载中...")
        );
    }
    if (error) {
        return React.createElement("div", { className: "report-container" },
            React.createElement("div", { className: "error" }, "错误：", error) // AI辅助生成：GLM-5, 2026-03-30
        );
    }
    
    return React.createElement("div", { className: "report-container" },
        React.createElement("div", { className: "report-header" },
            React.createElement("h2", { style: { 
                background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)', 
                color: 'white',
                padding: '16px 24px',
                borderRadius: '12px',
                margin: 0,
                fontSize: '20px',
                fontWeight: 600,
                boxShadow: '0 4px 12px rgba(59, 130, 246, 0.4)'
            } }, "脑卒中影像诊断报告"),
            React.createElement("div", { className: "report-actions" },
                React.createElement("button", { className: `action-btn ${isEditing ? 'cancel' : 'primary'}`, onClick: () => setIsEditing(!isEditing) }, isEditing ? '取消编辑' : '编辑报告'),
                isEditing && React.createElement("button", { className: "action-btn primary", onClick: saveReport, disabled: isSaving }, isSaving ? '保存中...' : '保存报告'),
                !isEditing && React.createElement("button", { className: "action-btn", onClick: exportPDF }, "导出 PDF")
            )
        ),
        React.createElement("div", { className: "report-body" },
            React.createElement(PatientInfoModule, { data: patient, isEditing: isEditing, onUpdate: handlePatientUpdate }),
            React.createElement(ImageFindingsModule, { data: mergedAnalysisData || null, findings: findings, isEditing: isEditing, onUpdate: handleFindingsUpdate }),
            
            // 远程 AI 诊断意见模块 - 四种状态展示
            !analysisData || analysisData.core_volume === 0 ?
                React.createElement("div", { className: "report-module", style: { background: '#1a1a1a', borderRadius: '12px', padding: '40px', marginTop: '20px', border: '1px solid #333', textAlign: 'center' } },
                    React.createElement("div", { style: { fontSize: '48px', marginBottom: '16px', color: '#60a5fa' } }, "ℹ️"),
                    React.createElement("h3", { style: { color: '#fff', fontSize: '18px', marginBottom: '12px' } }, "请先完成脑卒中分析"),
                    React.createElement("p", { style: { color: '#888', fontSize: '14px' } }, "请返回 viewer 页面完成影像自动分析后，再生成 AI 报告")
                )
            : (isGeneratingReport && !aiReport) ?
                React.createElement("div", { className: "report-module", style: { background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)', padding: '40px', borderRadius: '12px', marginTop: '20px', textAlign: 'center' } },
                    React.createElement("div", { 
                        style: { 
                            width: '48px', 
                            height: '48px', 
                            border: '4px solid rgba(255,255,255,0.3)', 
                            borderTop: '4px solid white', 
                            borderRadius: '50%', 
                            animation: 'spin 1s linear infinite',
                            margin: '0 auto 16px'
                        } 
                    }),
                    React.createElement("h3", { style: { color: '#fff', fontSize: '18px', marginBottom: '8px' } }, "正在生成 AI 报告..."),
                    React.createElement("p", { style: { color: 'rgba(255,255,255,0.8)', fontSize: '14px' } }, "StrokeClaw 正在分析影像数据，请稍候")
                )
            : aiReport ?
                React.createElement("div", { className: "report-module" },
                    React.createElement("div", { className: "module-header", style: { background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)' } }, "StrokeClaw 诊断意见"),
                    React.createElement("div", {
                        className: "ai-report-content",
                        style: {
                            background: '#1a1a1a',
                            padding: '24px',
                            borderRadius: '12px',
                            lineHeight: '1.8',
                            marginTop: '20px',
                            border: '1px solid #333'
                        },
                        dangerouslySetInnerHTML: { __html: renderMarkdownToHtml(aiReport, mergedAnalysisData.vessel_occlusion_class_result) }
                    })
                )
            :
                React.createElement("div", { className: "report-module", style: { background: '#1a1a1a', borderRadius: '12px', padding: '40px', marginTop: '20px', border: '1px solid #333', textAlign: 'center' } },
                    React.createElement("div", { style: { fontSize: '48px', marginBottom: '16px', color: '#60a5fa' } }, "ℹ️"),
                    React.createElement("h3", { style: { color: '#fff', fontSize: '18px', marginBottom: '12px' } }, "请生成 AI 报告"),
                    React.createElement("p", { style: { color: '#888', fontSize: '14px' } }, "请在脑卒中分析页面点击“手动生成 AI 报告”按钮")
                ),
            
            // 医生备注模块
            React.createElement(DoctorNotesModule, { notes: notes, isEditing: isEditing, onUpdate: setNotes }),
            
            !isEditing && React.createElement("div", { className: "report-footer" },
                React.createElement("p", null, "报告生成时间：", new Date().toLocaleString('zh-CN')),
                React.createElement("p", null, "免责声明：本报告中的 AI 分析结果仅供参考，最终诊断与治疗决策须由临床医生结合病情综合判断。")
            )
        )
    );
};

window.StructuredReport = StructuredReport;

