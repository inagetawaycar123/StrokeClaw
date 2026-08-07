const { useState, useEffect } = React; // AI辅助生成：GLM-5, 2026-04-23
const ACUTE_IMAGING_UI = (() => {
    if (typeof window !== 'undefined' && window.StrokeClawImagingResults) return window.StrokeClawImagingResults;
    if (typeof require === 'function') {
        try { return require('./imaging_results.js'); } catch (_error) { return null; }
    }
    return null;
})();
const MRS_PROGNOSIS_UI = (() => {
    if (typeof window !== 'undefined' && window.StrokeClawMrsPrognosis) return window.StrokeClawMrsPrognosis;
    if (typeof require === 'function') {
        try { return require('./mrs_prognosis.js'); } catch (_error) { return null; }
    }
    return null;
})();

function firstDefined(...values) {
    return values.find((value) => value !== null && value !== undefined && value !== '');
}

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
    const singleLabel = data.three_class_label_cn || data.three_class_label || '';

    let countsText = '';
    if (threeClassCounts && typeof threeClassCounts === 'object') {
        const normalCount = Number(threeClassCounts.normal || 0);
        const hemoCount = Number(threeClassCounts.hemo || 0);
        const infarctCount = Number(threeClassCounts.infarct || 0); // AI辅助生成：GLM-5, 2026-03-06
        countsText = `正常 ${normalCount}，脑出血 ${hemoCount}，脑缺血 ${infarctCount}`;
    }

    const ncctResultText = singleLabel || threeClassDisplay || countsText || '未获得模型结果';
    const safeVessel = getSafeVesselDisplayData(data);
    const vesselOcclusionResultText = safeVessel.label;
    const vesselOcclusionConf = safeVessel.confidence;
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
                    React.createElement("strong", null, reportValue(data.core_volume, "mL", 1)) // AI辅助生成：GLM-5, 2026-03-09
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "半暗带体积："),
                    React.createElement("strong", null, reportValue(data.penumbra_volume, "mL", 1))
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "不匹配比值："),
                    React.createElement("strong", null, reportValue(data.mismatch_ratio, "", 2))
                ),
                React.createElement("div", { className: "metric" },
                    React.createElement("span", null, "不匹配状态："),
                    React.createElement(
                        "strong",
                        null,
                        data.mismatch_ratio == null
                            ? '数据不足'
                            : (data.has_mismatch ? '存在明显不匹配' : '无明显不匹配')
                    )
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

const VESSEL_OCCLUSION_CLASS_RESULT = '未获得模型结果';

function getCaseScopedViewerData(data, expectedFileId) {
    const source = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
    const expected = expectedFileId == null ? '' : String(expectedFileId).trim();
    const actual = source.file_id == null ? '' : String(source.file_id).trim();
    return expected && actual && expected === actual ? source : {};
}

function getSafeVesselDisplayData(data) {
    const source = (data && typeof data === 'object') ? data : {};
    const nested = (source.vessel_occlusion_result && typeof source.vessel_occlusion_result === 'object')
        ? source.vessel_occlusion_result
        : null;
    const selected = nested || source;
    const status = String(nested ? nested.status : source.vessel_occlusion_status || '').trim().toLowerCase();
    const label = String(
        (nested ? nested.vessel_occlusion_class_result : source.vessel_occlusion_class_result) || ''
    ).trim();
    const predictedClass = String(
        (nested ? nested.predicted_class : (source.vessel_occlusion_predicted_class || source.predicted_class)) || ''
    ).trim();
    const classCounts = nested
        ? nested.class_counts
        : (source.vessel_occlusion_class_counts || source.class_counts);
    const validPredictions = Number(
        nested ? nested.valid_predictions : (source.vessel_occlusion_valid_predictions || source.valid_predictions)
    );
    const hasPredictionEvidence = ['Class_0', 'Class_1_LVO', 'Class_2_MEVO'].includes(predictedClass)
        || validPredictions > 0
        || (classCounts && typeof classCounts === 'object'
            && Object.values(classCounts).some((value) => Number(value) > 0));
    const confidenceValue = nested ? nested.confidence : source.vessel_occlusion_confidence;
    const hasConfidence = confidenceValue != null && confidenceValue !== '';
    const confidence = hasConfidence ? Number(confidenceValue) : NaN;
    const isLegacyFallback = selected.fallback === true
        || String(selected.source || source.vessel_occlusion_source || '').trim().toLowerCase() === 'hardcoded';
    const completed = status === 'completed' && !!label && hasPredictionEvidence && !isLegacyFallback;
    return {
        label: completed && label ? label : VESSEL_OCCLUSION_CLASS_RESULT,
        confidence: completed && Number.isFinite(confidence) && confidence >= 0 && confidence <= 1 ? confidence : null,
        status: completed ? 'completed' : (status === 'failed' ? 'failed' : 'unavailable'),
    };
}

function injectVesselOcclusionIntoMarkdown(markdown, vesselLabel) {
    if (!markdown) return '';

    const label = vesselLabel || VESSEL_OCCLUSION_CLASS_RESULT;
    const line = `血管堵塞三分类：${label}`;
    let replacedExistingLine = false;
    const replacedMarkdown = markdown.replace(
        /^(\s*(?:[-*+]\s*)?)(?:\*\*)?血管(?:堵塞|闭塞)三分类(?:结果)?(?:\*\*)?\s*(?:[：:]|为)\s*.*$/gm,
        (_match, prefix) => {
            replacedExistingLine = true;
            return `${prefix}${line}`;
        }
    );
    if (replacedExistingLine) {
        return replacedMarkdown;
    }

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

const REPORT_STATUS_TEXT = {
    present: '已获得',
    completed: '已完成',
    missing: '缺失',
    not_run: '未运行',
    met: '满足',
    not_met: '不满足',
    unknown: '数据不足',
    conflict: '冲突',
    not_applicable: '不适用',
    supported: '有支持',
    partially_supported: '部分支持',
    unsupported: '不支持',
    pending: '待确认',
    confirmed: '已确认',
    needs_edit: '需修改',
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    routine: '常规',
    attention: '需关注',
    urgent: '紧急',
    warning: '警告',
    unavailable: '不可用',
    failed: '失败',
};

function reportStatusText(status) {
    const token = String(status || 'unknown').toLowerCase();
    return REPORT_STATUS_TEXT[token] || status || '未知';
}

function reportStatusClass(status) {
    const token = String(status || 'unknown').toLowerCase();
    if (['met', 'supported', 'confirmed', 'completed', 'present'].includes(token)) return 'ok';
    if (['not_met', 'conflict', 'high', 'failed'].includes(token)) return 'danger';
    if (['missing', 'unknown', 'not_run', 'unavailable'].includes(token)) return 'unknown';
    return 'attention';
}

function reportValue(value, unit, digits) {
    if (value === null || value === undefined || value === '') return '未获得';
    if (value === 'male') return '男性';
    if (value === 'female') return '女性';
    const numeric = Number(value);
    const rendered = Number.isFinite(numeric) && typeof value !== 'boolean'
        ? numeric.toFixed(digits == null ? (Number.isInteger(numeric) ? 0 : 2) : digits)
        : String(value);
    return unit ? `${rendered} ${unit}` : rendered;
}

function getStructuredReportSummary(report) {
    const safe = report && typeof report === 'object' ? report : {};
    const metrics = Array.isArray(safe.quantitative_metrics) ? safe.quantitative_metrics : [];
    const fields = Array.isArray(safe.patient_summary?.fields) ? safe.patient_summary.fields : [];
    const byId = {};
    [...fields, ...metrics].forEach((item) => {
        const id = item.field_id || item.metric_id;
        if (id) byId[id] = item;
    });
    return {
        riskLevel: safe.report_meta?.risk_level || 'unknown',
        urgency: safe.report_meta?.urgency || 'unknown',
        reviewStatus: safe.clinician_review?.overall_status || safe.report_meta?.review_status || 'pending',
        missingCount: Array.isArray(safe.missing_information) ? safe.missing_information.length : 0,
        warningCount: Array.isArray(safe.warnings) ? safe.warnings.length : 0,
        metrics: byId,
    };
}

function withPerfusionFindingFallback(findings, metrics) {
    const safeFindings = Array.isArray(findings) ? findings : [];
    const safeMetrics = Array.isArray(metrics) ? metrics : [];
    const metricById = Object.fromEntries(
        safeMetrics.map((item) => [item.metric_id, item])
    );
    const perfusionFallback = [
        metricById.core_infarct_volume?.value != null
            ? `Core ${reportValue(metricById.core_infarct_volume.value, 'mL')}`
            : '',
        metricById.penumbra_volume?.value != null
            ? `Penumbra ${reportValue(metricById.penumbra_volume.value, 'mL')}`
            : '',
        metricById.mismatch_ratio?.value != null
            ? `Mismatch ${reportValue(metricById.mismatch_ratio.value, '')}`
            : '',
    ].filter(Boolean).join(' · ');
    return safeFindings.map((item) => (
        item?.finding_id === 'perfusion_analysis'
        && item?.status === 'completed'
        && !item?.value
        && perfusionFallback
            ? { ...item, value: perfusionFallback }
            : item
    ));
}

function buildReportAcuteFallback(sourceValue) {
    const source = sourceValue && typeof sourceValue === 'object' ? sourceValue : {};
    return {
        perfusion: {
            status: source.perfusion_status || source.analysis_status,
            core_infarct_volume: firstDefined(source.core_volume, source.core_infarct_volume, source.sections?.ctp?.core_infarct_volume),
            penumbra_volume: firstDefined(source.penumbra_volume, source.sections?.ctp?.penumbra_volume),
            mismatch_ratio: firstDefined(source.mismatch_ratio, source.sections?.ctp?.mismatch_ratio),
            has_mismatch: source.has_mismatch,
            safety_gate: source.safety_gate || source.three_class_result?.safety_gate,
            source: source.perfusion_source || 'CTPAnalysisAgent',
        },
        ncct: source.three_class_result || {
            status: source.three_class_status,
            three_class_label: source.three_class_label,
            three_class_label_cn: source.three_class_label_cn,
            three_class_confidence: source.three_class_confidence,
            class_counts: source.three_class_counts,
            total_slices: source.three_class_total_slices,
            safety_gate: source.safety_gate,
        },
        vessel: source.vessel_occlusion_result || {
            status: source.vessel_occlusion_status,
            vessel_occlusion_class_result: source.vessel_occlusion_class_result,
            confidence: source.vessel_occlusion_confidence,
            predicted_class: source.vessel_occlusion_predicted_class,
            class_counts: source.vessel_occlusion_class_counts,
            valid_predictions: source.vessel_occlusion_valid_predictions,
            input_phases: source.available_modalities,
            source: source.vessel_occlusion_source,
        },
    };
}

function getReportAcuteImaging(report, fallback) {
    if (!ACUTE_IMAGING_UI) return null;
    return ACUTE_IMAGING_UI.fromStructuredReport(report, buildReportAcuteFallback(fallback));
}

function unifiedStatusLabel(status) {
    return {
        completed: '已完成',
        skipped: '已跳过',
        failed: '失败',
        unavailable: '未生成',
    }[status] || '未生成';
}

function unifiedCountsText(counts) {
    const safe = counts && typeof counts === 'object' && !Array.isArray(counts) ? counts : {};
    const entries = Object.entries(safe).filter(([, value]) => Number.isFinite(Number(value)));
    return entries.length ? entries.map(([key, value]) => `${key} ${Number(value)}`).join(' · ') : '未提供';
}

function renderUnifiedFact(h, label, value, tone) {
    return h('div', { className: `unified-model-fact ${tone || ''}` },
        h('span', null, label),
        h('strong', null, value == null || value === '' ? '未生成' : String(value))
    );
}

function renderUnifiedStatus(h, status) {
    return h('span', { className: `unified-model-status ${status || 'unavailable'}` }, unifiedStatusLabel(status));
}

function renderUnifiedModelCard(h, options) {
    const details = Array.isArray(options.details) ? options.details.filter((item) => item && item.value != null && item.value !== '') : [];
    const limitations = Array.isArray(options.limitations) ? options.limitations.filter(Boolean) : [];
    return h('article', {
        className: `unified-model-card ${options.tone || 'neutral'} ${options.status || 'unavailable'} ${options.fullWidth ? 'full-width' : ''}`,
        key: options.key,
    },
    h('header', { className: 'unified-model-header' },
        h('div', null,
            h('span', { className: 'unified-model-kicker' }, options.kicker || '模型结果'),
            h('h4', null, options.title)
        ),
        h('div', { className: 'unified-model-badges' },
            ...(Array.isArray(options.badges) ? options.badges.map((badge, index) => h('span', { className: `unified-model-badge ${badge.tone || ''}`, key: `${options.key}-badge-${index}` }, badge.label)) : []),
            renderUnifiedStatus(h, options.status)
        )
    ),
    h('div', { className: 'unified-model-primary' },
        h('strong', null, options.primary || '未生成'),
        options.summary ? h('p', null, options.summary) : null
    ),
    options.facts?.length
        ? h('div', { className: 'unified-model-facts' }, options.facts.map((fact, index) => h(React.Fragment, { key: `${options.key}-fact-${index}` }, renderUnifiedFact(h, fact.label, fact.value, fact.tone))))
        : null,
    options.bar || null,
    details.length
        ? h('div', { className: 'unified-model-details' }, details.map((item, index) => renderUnifiedFact(h, item.label, item.value, item.tone)))
        : null,
    options.extra || null,
    limitations.length
        ? h('div', { className: 'unified-model-limitations' },
            h('strong', null, '限制与复核提示'),
            h('ul', null, limitations.map((item, index) => h('li', { key: `${options.key}-limitation-${index}` }, item)))
        )
        : null,
    h('footer', { className: 'unified-model-footer' },
        h('span', null, `来源：${options.source || '未记录'}`),
        h('span', null, `医生审核：${reportStatusText(options.reviewStatus || 'pending')}`)
    ));
}

function renderAcuteImagingCards(h, acute) {
    if (!acute || !ACUTE_IMAGING_UI) return [];
    const perfusion = acute.perfusion;
    const ncct = acute.ncct;
    const vessel = acute.vessel;
    const modalityChips = acute.modalities.length
        ? h('div', { className: 'unified-modality-chips' }, acute.modalities.map((item) => h('span', { key: item.id }, item.label)))
        : null;
    const confidenceBar = (value, label) => {
        const width = value == null ? 0 : Math.max(0, Math.min(100, value * 100));
        return h('div', { className: 'unified-confidence' },
            h('div', null, h('span', null, label), h('strong', null, ACUTE_IMAGING_UI.formatConfidence(value))),
            h('div', { className: 'unified-confidence-track', 'aria-hidden': 'true' }, h('span', { style: { width: `${width}%` } }))
        );
    };
    const perfusionTone = perfusion.status === 'completed'
        ? (perfusion.mismatchEvaluation.status === 'attention' ? 'attention' : perfusion.coreEvaluation.status === 'met' ? 'normal' : 'neutral')
        : perfusion.status;
    return [
        renderUnifiedModelCard(h, {
            key: 'perfusion', kicker: '灌注定量', title: '缺血核心与半暗带', status: perfusion.status, tone: perfusionTone,
            primary: perfusion.status === 'completed' ? (perfusion.mismatchStatus || '灌注定量已完成') : unifiedStatusLabel(perfusion.status),
            summary: perfusion.summary,
            facts: [
                { label: '核心梗死体积', value: ACUTE_IMAGING_UI.formatVolume(perfusion.core), tone: perfusion.coreEvaluation.status },
                { label: '半暗带体积', value: ACUTE_IMAGING_UI.formatVolume(perfusion.penumbra) },
                { label: '不匹配比值', value: ACUTE_IMAGING_UI.formatRatio(perfusion.mismatch), tone: perfusion.mismatchEvaluation.status },
            ],
            details: [
                { label: '核心内部参考', value: perfusion.core == null ? '< 70 mL' : `${perfusion.coreEvaluation.label}（< 70 mL）` },
                { label: '不匹配内部提示', value: perfusion.mismatch == null ? '> 1.80' : `${perfusion.mismatchEvaluation.label}（> 1.80）` },
            ],
            extra: modalityChips,
            limitations: perfusion.limitations,
            source: perfusion.source,
            reviewStatus: perfusion.reviewStatus,
        }),
        renderUnifiedModelCard(h, {
            key: 'ncct', kicker: 'NCCT 三分类', title: '出血 / 缺血排查', status: ncct.status, tone: ncct.tone,
            primary: ncct.label || unifiedStatusLabel(ncct.status),
            summary: ncct.status === 'completed' ? `分类置信度 ${ACUTE_IMAGING_UI.formatConfidence(ncct.confidence)}。` : (ncct.limitations[0] || '未获得有效 NCCT 三分类结果。'),
            bar: confidenceBar(ncct.confidence, '分类置信度'),
            facts: [
                { label: '分类结果', value: ncct.label || '未生成', tone: ncct.tone },
                { label: '切片总数', value: ncct.totalSlices == null ? '未提供' : ncct.totalSlices },
                { label: '安全门控', value: ncct.safetyGate?.blocked ? `已阻断：${ncct.safetyGate.reason || '疑似出血'}` : '未触发' },
            ],
            details: [{ label: '类别计数', value: unifiedCountsText(ncct.classCounts) }],
            limitations: ncct.limitations,
            source: ncct.source,
            reviewStatus: ncct.reviewStatus,
        }),
        renderUnifiedModelCard(h, {
            key: 'vessel', kicker: '血管闭塞三分类', title: '闭塞等级识别', status: vessel.status, tone: vessel.tone,
            primary: vessel.label || unifiedStatusLabel(vessel.status),
            summary: vessel.status === 'completed' ? `分类置信度 ${ACUTE_IMAGING_UI.formatConfidence(vessel.confidence)}。` : (vessel.limitations[0] || '未获得有效血管闭塞分类结果。'),
            bar: confidenceBar(vessel.confidence, '分类置信度'),
            facts: [
                { label: '分类结果', value: vessel.label || '未生成', tone: vessel.tone },
                { label: '有效预测数', value: vessel.validPredictions == null ? '未提供' : vessel.validPredictions },
                { label: '输入期相', value: vessel.inputPhases.length ? vessel.inputPhases.join('、') : '未提供' },
            ],
            details: [{ label: '类别计数', value: unifiedCountsText(vessel.classCounts) }],
            limitations: vessel.limitations,
            source: vessel.source,
            reviewStatus: vessel.reviewStatus,
        }),
    ];
}

function getReportMrsPrognosis(report, fallback) {
    if (!MRS_PROGNOSIS_UI) return null;
    const source = report?.prognosis_assessment || fallback || null;
    return MRS_PROGNOSIS_UI.normalizeMrsPrognosisResult(source);
}

function renderLegacyMrsPrognosisReportSection(h, prognosis) {
    if (!prognosis) return null;
    if (!prognosis.available) {
        return h('section', { className: 'report-section mrs-report-section unavailable' },
            h('div', { className: 'section-heading' },
                h('h3', null, '90 天功能预后预测'),
                h('span', { className: 'mrs-report-research-badge' }, '研究性 MVP')
            ),
            h('div', { className: 'empty-state' }, prognosis.reason || '当前病例未生成有效的 90 天 mRS 预测。'),
            h('p', { className: 'mrs-report-disclaimer' }, '未生成状态不会被替换为 0% 或启发式概率，也不新增阻塞性的医生必审分段。')
        );
    }

    const prediction = prognosis.prediction;
    const confidence = prognosis.confidence;
    const confidenceLabel = MRS_PROGNOSIS_UI.confidenceLabel(confidence.level);
    const clinicalItems = prognosis.clinicalEvidence.map((item) => {
        const direction = item.direction === 'increase_poor_prognosis_risk'
            ? '与较高不良预后风险相关'
            : item.direction === 'decrease_poor_prognosis_risk'
                ? '与较低不良预后风险相关'
                : '关联方向中性';
        return `${item.displayName}${item.value == null ? '' : `（值 ${item.value}）`}：${direction}`;
    });
    const imagingItems = prognosis.imagingEvidence.map((item) => (
        `${item.regionLabel}${item.attentionScore == null ? '' : `（关注权重 ${MRS_PROGNOSIS_UI.formatProbability(item.attentionScore)}）`}：${item.interpretation}`
    ));
    const qualityItems = [
        ...prognosis.missingClinicalFields.map((item) => `缺失临床字段：${item}`),
        ...prognosis.imageQualityWarnings.map((item) => `图像质量提示：${item}`),
        ...(prognosis.fallbackUsed ? [`已降级评估：${prognosis.fallbackReason || '24小时更新模型不可用'}`] : []),
    ];
    const list = (title, items) => h('div', { className: 'mrs-report-detail-card' },
        h('strong', null, title),
        items.length
            ? h('ul', null, items.map((item, index) => h('li', { key: `${title}-${index}` }, item)))
            : h('p', null, '未提供')
    );

    return h('section', { className: `report-section mrs-report-section ${MRS_PROGNOSIS_UI.prognosisTone(prognosis)}` },
        h('div', { className: 'section-heading' },
            h('h3', null, '90 天功能预后预测'),
            h('div', { className: 'mrs-report-heading-badges' },
                h('span', { className: 'mrs-report-mode-badge' }, prognosis.displayMode),
                h('span', { className: 'mrs-report-research-badge' }, '研究性 MVP')
            )
        ),
        h('div', { className: 'mrs-report-summary' },
            h('div', null,
                h('span', { className: 'mrs-report-kicker' }, prediction.classRange),
                h('strong', { className: 'mrs-report-class' }, prediction.classLabel),
                h('p', null, prognosis.deterministicSummary)
            ),
            h('div', { className: 'mrs-report-facts' },
                h('div', null, h('span', null, '模型置信度'), h('strong', { className: `confidence-${MRS_PROGNOSIS_UI.confidenceTone(confidence.level)}` }, confidenceLabel)),
                h('div', null, h('span', null, '决策阈值'), h('strong', null, MRS_PROGNOSIS_UI.formatProbability(prediction.decisionThreshold))),
                h('div', null, h('span', null, '外部验证'), h('strong', null, prognosis.model.externalValidationCompleted ? '已完成' : '未完成')),
                h('div', null, h('span', null, '生产批准'), h('strong', null, prognosis.model.productionApproved ? '已批准' : '未批准'))
            )
        ),
        h('div', { className: 'mrs-report-probability-bar', 'aria-label': '90 天 mRS 两组预测概率' },
            h('span', { className: 'mrs-report-good-bar', style: { width: `${prediction.goodProbability * 100}%` } }),
            h('span', { className: 'mrs-report-poor-bar', style: { width: `${prediction.poorRisk * 100}%` } }),
            h('span', {
                className: 'mrs-report-threshold-marker',
                style: { left: `${(1 - prediction.decisionThreshold) * 100}%` },
                title: `mRS 3-6 判定阈值 ${MRS_PROGNOSIS_UI.formatProbability(prediction.decisionThreshold)}`,
            })
        ),
        h('div', { className: 'mrs-report-probability-values' },
            h('span', null, '良好预后（mRS 0–2）', h('strong', null, MRS_PROGNOSIS_UI.formatProbability(prediction.goodProbability))),
            h('span', null, '不良预后风险（mRS 3–6）', h('strong', null, MRS_PROGNOSIS_UI.formatProbability(prediction.poorRisk)))
        ),
        h('div', { className: 'mrs-report-detail-grid' },
            h('div', { className: 'mrs-report-detail-card' },
                h('strong', null, '模型可靠性信息'),
                h('p', null, `阈值距离：${confidence.thresholdMargin == null ? '--' : confidence.thresholdMargin.toFixed(3)}`),
                h('p', null, `集成标准差：${confidence.ensembleStd == null ? '--' : confidence.ensembleStd.toFixed(3)}`),
                h('p', null, `概率校准：${prediction.probabilityCalibrated ? '是' : '未确认'}`),
                h('p', null, `模型版本：${prognosis.model.modelVersion || prognosis.model.bundleVersion || '--'}`),
                confidence.reasons.length ? h('ul', null, confidence.reasons.map((item, index) => h('li', { key: `confidence-${index}` }, item))) : null
            ),
            list('主要临床影响因素', clinicalItems),
            list('影像关注摘要', imagingItems),
            list('数据质量', qualityItems),
            list('医生复核建议', prognosis.reviewItems)
        ),
        h('div', { className: 'mrs-report-safety-note' },
            h('strong', null, '使用限制'),
            h('p', null, prognosis.attributionNotice),
            h('ul', null, (prognosis.limitations.length ? prognosis.limitations : [
                '该输出只表示 mRS 0-2 与 mRS 3-6 两组概率，不代表具体 mRS 分数。',
                '该结果不改变本报告顶部急性期风险、紧急程度或治疗建议。',
            ]).map((item, index) => h('li', { key: `limitation-${index}` }, item)))
        )
    );
}

function renderMrsPrognosisReportSection(h, prognosis) {
    const unavailable = !prognosis || !prognosis.available;
    if (unavailable) {
        return renderUnifiedModelCard(h, {
            key: 'mrs-prognosis',
            kicker: '90 天功能预后预测',
            title: '研究性功能预后评估',
            status: 'unavailable',
            tone: 'neutral',
            fullWidth: true,
            badges: [{ label: '研究性 MVP', tone: 'research' }],
            primary: '未生成',
            summary: prognosis?.reason || '当前病例未生成有效的 90 天 mRS 预测。',
            limitations: [
                '未生成状态不会被替换为 0% 或启发式概率。',
                '该结果不改变报告顶部急性期风险、紧急程度或治疗建议。',
            ],
            source: 'mRS Prognosis Agent',
            reviewStatus: 'not_applicable',
        });
    }

    const prediction = prognosis.prediction;
    const confidence = prognosis.confidence;
    const confidenceLabel = MRS_PROGNOSIS_UI.confidenceLabel(confidence.level);
    const clinicalItems = prognosis.clinicalEvidence.map((item) => {
        const direction = item.direction === 'increase_poor_prognosis_risk'
            ? '与较高不良预后风险相关'
            : item.direction === 'decrease_poor_prognosis_risk'
                ? '与较低不良预后风险相关'
                : '关联方向中性';
        return `${item.displayName}${item.value == null ? '' : `（值 ${item.value}）`}：${direction}`;
    });
    const imagingItems = prognosis.imagingEvidence.map((item) => (
        `${item.regionLabel}${item.attentionScore == null ? '' : `（关注权重 ${MRS_PROGNOSIS_UI.formatProbability(item.attentionScore)}）`}：${item.interpretation}`
    ));
    const qualityItems = [
        ...prognosis.missingClinicalFields.map((item) => `缺失临床字段：${item}`),
        ...prognosis.imageQualityWarnings.map((item) => `图像质量提示：${item}`),
        ...(prognosis.fallbackUsed ? [`已降级评估：${prognosis.fallbackReason || '24小时更新模型不可用'}`] : []),
    ];
    const detailList = (title, items) => h('div', { className: 'unified-model-list' },
        h('strong', null, title),
        items.length
            ? h('ul', null, items.map((item, index) => h('li', { key: `${title}-${index}` }, item)))
            : h('p', null, '未提供')
    );
    const probabilityBar = h(React.Fragment, null,
        h('div', { className: 'unified-mrs-probability-bar', 'aria-label': '90 天 mRS 两组预测概率' },
            h('span', { className: 'good', style: { width: `${prediction.goodProbability * 100}%` } }),
            h('span', { className: 'poor', style: { width: `${prediction.poorRisk * 100}%` } }),
            h('span', {
                className: 'threshold',
                style: { left: `${(1 - prediction.decisionThreshold) * 100}%` },
                title: `mRS 3-6 判定阈值 ${MRS_PROGNOSIS_UI.formatProbability(prediction.decisionThreshold)}`,
            })
        ),
        h('div', { className: 'unified-mrs-probability-values' },
            h('span', null, '良好预后（mRS 0–2）', h('strong', null, MRS_PROGNOSIS_UI.formatProbability(prediction.goodProbability))),
            h('span', null, '不良预后风险（mRS 3–6）', h('strong', null, MRS_PROGNOSIS_UI.formatProbability(prediction.poorRisk)))
        )
    );
    const reliabilityItems = [
        `阈值距离：${confidence.thresholdMargin == null ? '--' : confidence.thresholdMargin.toFixed(3)}`,
        `集成标准差：${confidence.ensembleStd == null ? '--' : confidence.ensembleStd.toFixed(3)}`,
        `概率校准：${prediction.probabilityCalibrated ? '是' : '未确认'}`,
        `模型版本：${prognosis.model.modelVersion || prognosis.model.bundleVersion || '--'}`,
        ...confidence.reasons,
    ];
    return renderUnifiedModelCard(h, {
        key: 'mrs-prognosis',
        kicker: '90 天功能预后预测',
        title: '研究性功能预后评估',
        status: 'completed',
        tone: MRS_PROGNOSIS_UI.prognosisTone(prognosis),
        fullWidth: true,
        badges: [
            { label: prognosis.displayMode, tone: 'mode' },
            { label: '研究性 MVP', tone: 'research' },
        ],
        primary: `${prediction.classRange} · ${prediction.classLabel}`,
        summary: prognosis.deterministicSummary,
        facts: [
            { label: '模型置信度', value: confidenceLabel, tone: `confidence-${MRS_PROGNOSIS_UI.confidenceTone(confidence.level)}` },
            { label: '决策阈值', value: MRS_PROGNOSIS_UI.formatProbability(prediction.decisionThreshold) },
            { label: '外部验证', value: prognosis.model.externalValidationCompleted ? '已完成' : '未完成' },
            { label: '生产批准', value: prognosis.model.productionApproved ? '已批准' : '未批准' },
        ],
        bar: probabilityBar,
        extra: h('div', { className: 'unified-model-list-grid' },
            detailList('模型可靠性信息', reliabilityItems),
            detailList('主要临床影响因素', clinicalItems),
            detailList('影像关注摘要', imagingItems),
            detailList('数据质量', qualityItems),
            detailList('医生复核建议', prognosis.reviewItems)
        ),
        limitations: Array.from(new Set([
            prognosis.attributionNotice,
            ...(prognosis.limitations.length ? prognosis.limitations : [
                '该输出只表示 mRS 0-2 与 mRS 3-6 两组概率，不代表具体 mRS 分数。',
                '该结果不改变本报告顶部急性期风险、紧急程度或治疗建议。',
            ]),
        ].filter(Boolean))),
        source: `mRS Prognosis Agent · ${prognosis.model.modelVersion || prognosis.model.bundleVersion || '未记录版本'}`,
        reviewStatus: prognosis.reviewStatus || 'pending',
    });
}

const StructuredReportV2View = ({ report, legacyText, runId, fileId, patientId, mrsFallback, acuteFallback }) => {
    const h = React.createElement;
    const summary = getStructuredReportSummary(report);
    const meta = report.report_meta || {};
    const fields = Array.isArray(report.patient_summary?.fields) ? report.patient_summary.fields : [];
    const metrics = Array.isArray(report.quantitative_metrics) ? report.quantitative_metrics : [];
    const rawImaging = Array.isArray(report.imaging_findings) ? report.imaging_findings : [];
    const acute = getReportAcuteImaging(report, acuteFallback);
    const prognosis = getReportMrsPrognosis(report, mrsFallback);
    const rules = Array.isArray(report.rule_evaluations) ? report.rule_evaluations : [];
    const claims = Array.isArray(report.evidence_chain) ? report.evidence_chain : [];
    const evidence = Array.isArray(report.evidence_catalog) ? report.evidence_catalog : [];
    const evidenceById = {};
    evidence.forEach((item) => { if (item?.evidence_id) evidenceById[item.evidence_id] = item; });
    const assessments = Array.isArray(report.clinical_assessment) ? report.clinical_assessment : [];
    const recommendations = Array.isArray(report.recommendations) ? report.recommendations : [];
    const warnings = Array.isArray(report.warnings) ? report.warnings : [];
    const missing = Array.isArray(report.missing_information) ? report.missing_information : [];
    const uncertainties = Array.isArray(report.uncertainties) ? report.uncertainties : [];
    const narrative = report.narrative_summary || {};
    const review = report.clinician_review || {};
    const query = new URLSearchParams();
    if (runId) query.set('run_id', runId);
    if (fileId) query.set('file_id', fileId);
    if (patientId) query.set('patient_id', patientId);
    const reviewUrl = `/processing${query.toString() ? `?${query.toString()}` : ''}`;

    const statusBadge = (status) => h('span', {
        className: `report-status ${reportStatusClass(status)}`,
    }, reportStatusText(status));

    const evidenceDetails = (claim) => {
        const rows = (claim.evidence_ids || []).map((id) => evidenceById[id]).filter(Boolean);
        return h('details', { className: 'evidence-details', key: `${claim.claim_id}-evidence` },
            h('summary', null, `查看证据（${rows.length}）`),
            rows.length
                ? h('div', { className: 'evidence-list' }, rows.map((item) =>
                    h('article', { className: 'evidence-item', key: item.evidence_id },
                        h('div', { className: 'evidence-head' },
                            h('span', { className: 'source-tag' }, item.evidence_type || 'unknown'),
                            statusBadge(item.binding_status === 'bound' ? 'supported' : 'unknown')
                        ),
                        h('strong', null, item.display_name || item.source_record || item.evidence_id),
                        item.value !== null && item.value !== undefined
                            ? h('div', { className: 'evidence-value' }, reportValue(item.value, item.unit))
                            : null,
                        h('div', { className: 'evidence-meta' },
                            `来源：${item.source_module || '未记录'} · 记录：${item.source_record || '未记录'}`
                        ),
                        item.confidence !== null && item.confidence !== undefined
                            ? h('div', { className: 'evidence-meta' }, `置信度：${(Number(item.confidence) * 100).toFixed(1)}%`)
                            : h('div', { className: 'evidence-meta' }, '置信度：未提供'),
                        item.document_title || item.source_ref
                            ? h('div', { className: 'evidence-meta' },
                                `依据：${item.document_title || item.source_ref}${item.page ? ` · 第 ${item.page} 页` : ''}`
                            )
                            : null,
                        item.snippet ? h('p', { className: 'evidence-snippet' }, item.snippet) : null
                    )
                ))
                : h('div', { className: 'empty-state compact' }, '该结论尚未绑定可展示证据。')
        );
    };

    const claimCard = (claim) => h('article', { className: 'claim-card', key: claim.claim_id },
        h('div', { className: 'claim-heading' },
            h('strong', null, claim.claim),
            statusBadge(claim.support_status)
        ),
        claim.limitations?.length
            ? h('ul', { className: 'limitation-list' }, claim.limitations.map((item, index) =>
                h('li', { key: `${claim.claim_id}-lim-${index}` }, item)
            ))
            : null,
        h('div', { className: 'claim-review' },
            `医生审核：${reportStatusText(claim.review_status || 'pending')}`
        ),
        evidenceDetails(claim)
    );

    const issueGroup = (title, items, tone) => items.length
        ? h('section', { className: `report-section issue-section ${tone}` },
            h('div', { className: 'section-heading' }, h('h3', null, title), h('span', { className: 'section-count' }, items.length)),
            h('div', { className: 'issue-list' }, items.map((item) =>
                h('article', { className: 'issue-card', key: item.issue_id },
                    h('div', { className: 'issue-title' },
                        h('strong', null, item.message),
                        statusBadge(item.status)
                    ),
                    h('p', null, `影响：${item.impact || '未说明'}`),
                    h('p', null, `建议：${item.recommended_action || '请人工复核'}`)
                )
            ))
        )
        : null;

    return h('div', { className: 'structured-report-v2' },
        meta.legacy_mode
            ? h('div', { className: 'legacy-banner' }, '这是旧版报告的安全降级视图；未从正文反向推断临床事实或证据。')
            : null,
        h('section', { className: `report-hero risk-${summary.riskLevel}` },
            h('div', null,
                h('span', { className: 'eyebrow' }, 'STRUCTURED CLINICAL REPORT · V2'),
                h('h2', null, assessments[0]?.claim || '当前结构化信息需医生复核'),
                h('p', null, narrative.deterministic_summary || '当前没有可用的确定性摘要。')
            ),
            h('div', { className: 'hero-status-grid' },
                h('div', null, h('span', null, '风险'), h('strong', null, reportStatusText(summary.riskLevel))),
                h('div', null, h('span', null, '紧急程度'), h('strong', null, reportStatusText(summary.urgency))),
                h('div', null, h('span', null, '缺失项'), h('strong', null, summary.missingCount)),
                h('div', null, h('span', null, '医生审核'), h('strong', null, reportStatusText(summary.reviewStatus)))
            )
        ),
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '患者与临床信息')),
            h('div', { className: 'metric-grid patient-grid' }, fields.map((field) =>
                h('article', { className: `metric-card ${field.status}`, key: field.field_id },
                    h('span', { className: 'metric-name' }, field.display_name),
                    h('strong', { className: 'metric-value' }, reportValue(field.value, field.unit)),
                    h('small', null, `${field.source_module || '未知来源'} · ${reportStatusText(field.review_status)}`)
                )
            ))
        ),
        h('section', { className: 'report-section unified-model-section' },
            h('div', { className: 'section-heading' },
                h('div', null,
                    h('h3', null, '模型量化与预测结果'),
                    h('p', { className: 'section-description' }, '急性期影像模型与研究性预后模型采用统一展示结构，指标医学含义保持独立。')
                )
            ),
            h('div', { className: 'unified-model-grid' },
                ...renderAcuteImagingCards(h, acute),
                renderMrsPrognosisReportSection(h, prognosis)
            )
        ),
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '规则评估')),
            h('div', { className: 'rule-table-wrap' },
                h('table', { className: 'rule-table' },
                    h('thead', null, h('tr', null,
                        h('th', null, '规则'),
                        h('th', null, '患者数据'),
                        h('th', null, '判断条件'),
                        h('th', null, '结果'),
                        h('th', null, '依据')
                    )),
                    h('tbody', null, rules.map((rule) =>
                        h('tr', { key: rule.rule_id },
                            h('td', null, h('strong', null, rule.rule_name), h('small', null, rule.rule_id)),
                            h('td', null, reportValue(rule.input_value, rule.rule_id.includes('VOLUME') ? 'mL' : rule.rule_id.includes('ONSET') ? 'h' : '')),
                            h('td', null, `${rule.operator || ''} ${reportValue(rule.threshold, rule.rule_id.includes('VOLUME') ? 'mL' : rule.rule_id.includes('ONSET') ? 'h' : '')}`),
                            h('td', null, statusBadge(rule.result)),
                            h('td', null, `${rule.source?.title || '内部规则'} ${rule.source?.version || ''}`)
                        )
                    ))
                )
            )
        ),
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '临床判断与证据链')),
            assessments.length
                ? h('div', { className: 'claim-list' }, assessments.map(claimCard))
                : h('div', { className: 'empty-state' }, '当前没有证据充分的临床判断。')
        ),
        issueGroup('高风险与冲突', warnings, 'danger'),
        issueGroup('关键数据缺失', missing, 'unknown'),
        issueGroup('不确定性', uncertainties, 'attention'),
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '临床建议')),
            h('div', { className: 'claim-list' }, recommendations.map(claimCard))
        ),
        h('section', { className: 'report-section narrative-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '自然语言总结')),
            h('h4', null, '确定性摘要'),
            h('p', null, narrative.deterministic_summary || '当前没有可用摘要。'),
            narrative.ai_supplement
                ? h(React.Fragment, null,
                    h('h4', null, 'AI 综合说明'),
                    h('div', { className: 'ai-supplement-note' }, '以下内容属于智能体综合推理，不等同于原始临床证据。'),
                    h('p', null, narrative.ai_supplement)
                )
                : null,
            meta.legacy_mode && (narrative.legacy_text || legacyText)
                ? h('details', { className: 'legacy-text-details' },
                    h('summary', null, '查看旧版原始报告'),
                    h('div', { dangerouslySetInnerHTML: { __html: renderMarkdownToHtml(narrative.legacy_text || legacyText) } })
                )
                : null
        ),
        h('section', { className: 'report-section review-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '医生审核')),
            h('div', { className: 'review-summary' },
                h('div', null, '总体状态：', statusBadge(review.overall_status || 'pending')),
                h('div', null, `证据覆盖率：${meta.evidence_coverage == null ? '未计算' : `${(Number(meta.evidence_coverage) * 100).toFixed(1)}%`}`),
                h('a', { className: 'action-btn primary review-link', href: reviewUrl }, '进入分段审核')
            )
        ),
        h('div', { className: 'clinical-disclaimer' }, '本报告为临床决策支持材料，不能替代临床医生对原始影像、禁忌证及患者整体情况的最终判断。')
    );
};

const getReportStorageKeys = (fileId) => {
    const caseId = fileId == null ? '' : String(fileId).trim();
    if (!caseId) return null;
    return {
        report: `ai_report_${caseId}`,
        generating: `ai_report_generating_${caseId}`,
        error: `ai_report_error_${caseId}`,
        payload: `ai_report_payload_${caseId}`
    };
};
const REPORT_GENERATING_TIMEOUT_MS = 90000;
const getGeneratingTsKey = (keys) => `${keys.generating}_ts`;
const clearGeneratingState = (keys) => {
    if (!keys) return;
    localStorage.removeItem(keys.generating); // AI辅助生成：GLM-5, 2026-03-15
    localStorage.removeItem(getGeneratingTsKey(keys));
    localStorage.removeItem('ai_report_generating');
};
const StructuredReport = ({ patientId, fileId, runId, analysisData }) => {
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
    const [error, setError] = useState(null);
    const [reportSourceMeta, setReportSourceMeta] = useState(null);
    const [reportContextWarning, setReportContextWarning] = useState('');
    // 报告缓存按 file_id 隔离，避免跨病例串数据
    useEffect(() => {
        const keys = getReportStorageKeys(fileId); // AI辅助生成：GLM-5, 2026-03-17
        if (!keys) {
            setAiReport(null);
            setReportPayload(null);
            setIsGeneratingReport(false);
            return undefined;
        }
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
        if (!patientId && !fileId && !runId) return undefined;
        const controller = new AbortController();
        const query = new URLSearchParams();
        if (patientId) query.set('patient_id', String(patientId));
        if (fileId) query.set('file_id', String(fileId));
        if (runId) query.set('run_id', String(runId));
        const loadReportContext = async () => {
            try {
                const response = await fetch(`/api/report/context?${query.toString()}`, {
                    signal: controller.signal,
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || '结构化报告上下文不可用');
                }
                if (data.report_payload && typeof data.report_payload === 'object') {
                    setReportPayload(data.report_payload);
                }
                if (typeof data.report_text === 'string' && data.report_text.trim()) {
                    setAiReport(data.report_text);
                }
                setReportSourceMeta(data.source_meta || null);
                setReportContextWarning('');
            } catch (contextErr) {
                if (contextErr.name === 'AbortError') return;
                setReportContextWarning(`服务器报告上下文不可用，已使用本地病例缓存：${contextErr.message}`);
            }
        };
        loadReportContext();
        return () => controller.abort();
    }, [patientId, fileId, runId]);

    useEffect(() => {
        const keys = getReportStorageKeys(fileId); // AI辅助生成：GLM-5, 2026-03-22
        if (!keys) return undefined;
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
        if (!fileId) {
            setError('缺少病例 file_id，已拒绝读取全局报告缓存。');
            setLoading(false);
            return;
        }
        loadPatientInfo();
    }, [patientId, fileId]);
    
    const loadPatientInfo = async () => {
        try {
            const res = await fetch(`/api/get_patient/${patientId}`);
            const data = await res.json();
            if (data.status === 'success') {
                setPatient(data.data);
                generateImageFindings(data.data); // AI辅助生成：GLM-5, 2026-03-26
            } else {
                setReportContextWarning((current) =>
                    current || `患者信息加载失败：${data.message || '未知错误'}`
                );
            }
        } catch (err) {
            setReportContextWarning((current) =>
                current || `患者信息网络错误：${err.message}`
            );
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
        }[analysisData.hemisphere] || '侧别未获得的';
        const coreValue = analysisData.core_volume;
        const penumbraValue = analysisData.penumbra_volume;
        const mismatchValue = analysisData.mismatch_ratio;
        const coreText = coreValue == null
            ? '未获得核心梗死体积。'
            : `自动分析输出：${hemName}核心梗死体积 ${Number(coreValue).toFixed(2)} ml。`;
        const penumbraText = penumbraValue == null
            ? '未获得半暗带体积。'
            : `自动分析输出：半暗带体积 ${Number(penumbraValue).toFixed(2)} ml。`;
        const vesselText = analysisData.vessel_occlusion_class_result
            ? `血管闭塞分类模型输出：${analysisData.vessel_occlusion_class_result}。`
            : '未获得有效血管闭塞分类结果，需结合原始 CTA/MRA 人工复核。'; // AI辅助生成：GLM-5, 2026-03-27
        const perfusionText = `灌注参数分析：
- CBF/CBV/Tmax：请查看对应算法图和运行状态。
- 不匹配比值：${mismatchValue == null ? '--' : Number(mismatchValue).toFixed(2)}。
- 说明：以上为自动分析数据摘要，不替代原始灌注图复核。`;
        setFindings({
            core: coreText,
            penumbra: penumbraText,
            vessel: vesselText,
            perfusion: perfusionText,
        });
    };

    const mergedVesselData = getSafeVesselDisplayData({
        ...((analysisData && typeof analysisData === 'object') ? analysisData : {}),
        ...((reportPayload && typeof reportPayload === 'object') ? reportPayload : {}),
    });
    const firstPresent = (...values) => values.find((value) => value !== null && value !== undefined && value !== '');
    const mergedAnalysisData = {
        ...(analysisData || {}),
        ...((reportPayload && typeof reportPayload === 'object') ? reportPayload : {}),
        core_volume: firstPresent(analysisData?.core_volume, reportPayload?.core_infarct_volume, reportPayload?.sections?.ctp?.core_infarct_volume),
        penumbra_volume: firstPresent(analysisData?.penumbra_volume, reportPayload?.penumbra_volume, reportPayload?.sections?.ctp?.penumbra_volume),
        mismatch_ratio: firstPresent(analysisData?.mismatch_ratio, reportPayload?.mismatch_ratio, reportPayload?.sections?.ctp?.mismatch_ratio),
        question_answer: (reportPayload && reportPayload.question_answer) || (analysisData && analysisData.question_answer) || null,
        goal_question: (reportPayload && (reportPayload.goal_question || reportPayload.question)) || (analysisData && analysisData.goal_question) || '',
        three_class_label_cn: firstPresent(analysisData?.three_class_label_cn, reportPayload?.three_class_label_cn),
        three_class_status: firstPresent(analysisData?.three_class_status, reportPayload?.three_class_status),
        three_class_confidence: firstPresent(analysisData?.three_class_confidence, reportPayload?.three_class_confidence),
        three_class_result: firstPresent(analysisData?.three_class_result, reportPayload?.three_class_result),
        three_class_counts: firstPresent(analysisData?.three_class_counts, reportPayload?.three_class_counts),
        three_class_total_slices: firstPresent(analysisData?.three_class_total_slices, reportPayload?.three_class_total_slices),
        vessel_occlusion_status: mergedVesselData.status,
        vessel_occlusion_class_result: mergedVesselData.label,
        vessel_occlusion_confidence: mergedVesselData.confidence,
        available_modalities: firstPresent(analysisData?.available_modalities, reportPayload?.available_modalities, reportPayload?.modalities) || [],
    };
    const mrsFallback = firstPresent(
        reportPayload?.mrs_prognosis_result,
        reportPayload?.prognosis_assessment,
        analysisData?.mrs_prognosis_result,
        analysisData?.prognosis_assessment,
    ) || null;
    const acuteFallback = mergedAnalysisData;
    
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
    const structuredReportV2 = reportPayload && typeof reportPayload.structured_report_v2 === 'object'
        ? reportPayload.structured_report_v2
        : null;
    const hasLegacyAnalysis = !!analysisData && (
        analysisData.core_volume !== null
        && analysisData.core_volume !== undefined
    );
    
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
                React.createElement("button", { className: `action-btn ${isEditing ? 'cancel' : 'primary'}`, onClick: () => setIsEditing(!isEditing) }, isEditing ? '取消编辑' : (structuredReportV2 ? '编辑备注' : '编辑报告')),
                isEditing && React.createElement("button", { className: "action-btn primary", onClick: saveReport, disabled: isSaving }, isSaving ? '保存中...' : '保存报告'),
                !isEditing && React.createElement("button", { className: "action-btn", onClick: exportPDF }, "导出 PDF")
            )
        ),
        React.createElement("div", { className: "report-body" },
            reportContextWarning && React.createElement("div", { className: "context-warning" }, reportContextWarning),
            reportSourceMeta && React.createElement("div", { className: "report-source-meta" },
                `报告来源：${reportSourceMeta.source_chain || 'unknown'}${reportSourceMeta.fallback ? '（降级读取）' : ''}`
            ),
            structuredReportV2
                ? React.createElement(StructuredReportV2View, {
                    report: structuredReportV2,
                    legacyText: aiReport,
                    runId: runId,
                    fileId: fileId,
                    patientId: patientId,
                    mrsFallback: mrsFallback,
                    acuteFallback: acuteFallback,
                })
                : React.createElement(React.Fragment, null,
                    React.createElement("div", { className: "legacy-banner" }, "当前为旧版报告展示，结构化证据链不可用。"),
                    React.createElement(PatientInfoModule, { data: patient, isEditing: isEditing, onUpdate: handlePatientUpdate }),
                    React.createElement('section', { className: 'report-section unified-model-section' },
                        React.createElement('div', { className: 'section-heading' },
                            React.createElement('div', null,
                                React.createElement('h3', null, '模型量化与预测结果'),
                                React.createElement('p', { className: 'section-description' }, '当前为旧版报告数据，结果按统一展示模型安全降级。')
                            )
                        ),
                        React.createElement('div', { className: 'unified-model-grid' },
                            ...renderAcuteImagingCards(React.createElement, getReportAcuteImaging(null, acuteFallback)),
                            renderMrsPrognosisReportSection(
                                React.createElement,
                                getReportMrsPrognosis(null, mrsFallback),
                            )
                        )
                    ),
                    !hasLegacyAnalysis
                        ? React.createElement("div", { className: "report-module empty-state" },
                            React.createElement("h3", null, "请先完成脑卒中分析"),
                            React.createElement("p", null, "完成影像自动分析后再生成 AI 报告。")
                        )
                        : (isGeneratingReport && !aiReport)
                            ? React.createElement("div", { className: "report-module empty-state" },
                                React.createElement("h3", null, "正在生成 AI 报告..."),
                                React.createElement("p", null, "StrokeClaw 正在分析影像数据，请稍候。")
                            )
                            : aiReport
                                ? React.createElement("div", { className: "report-module" },
                                    React.createElement("div", { className: "module-header" }, "StrokeClaw 旧版诊断意见"),
                                    React.createElement("div", {
                                        className: "ai-report-content",
                                        dangerouslySetInnerHTML: { __html: renderMarkdownToHtml(aiReport, mergedAnalysisData.vessel_occlusion_class_result) }
                                    })
                                )
                                : React.createElement("div", { className: "report-module empty-state" },
                                    React.createElement("h3", null, "请生成 AI 报告"),
                                    React.createElement("p", null, "请在脑卒中分析页面生成报告。")
                                )
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

if (typeof window !== 'undefined') {
    window.StructuredReport = StructuredReport;
    window.getCaseScopedViewerData = getCaseScopedViewerData;
}
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getReportStorageKeys,
        getCaseScopedViewerData,
        getSafeVesselDisplayData,
        injectVesselOcclusionIntoMarkdown,
        reportStatusText,
        reportStatusClass,
        reportValue,
        getStructuredReportSummary,
        withPerfusionFindingFallback,
        getReportMrsPrognosis,
        buildReportAcuteFallback,
        getReportAcuteImaging,
        unifiedStatusLabel,
        renderAcuteImagingCards,
        renderMrsPrognosisReportSection,
        renderUnifiedModelCard,
    };
}

