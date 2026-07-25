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

const StructuredReportV2View = ({ report, legacyText, runId, fileId, patientId }) => {
    const h = React.createElement;
    const summary = getStructuredReportSummary(report);
    const meta = report.report_meta || {};
    const fields = Array.isArray(report.patient_summary?.fields) ? report.patient_summary.fields : [];
    const metrics = Array.isArray(report.quantitative_metrics) ? report.quantitative_metrics : [];
    const imaging = Array.isArray(report.imaging_findings) ? report.imaging_findings : [];
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
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '关键定量指标')),
            h('div', { className: 'metric-grid' }, metrics.map((metric) =>
                h('article', { className: `metric-card ${metric.status}`, key: metric.metric_id },
                    h('span', { className: 'metric-name' }, metric.display_name),
                    h('strong', { className: 'metric-value' }, reportValue(metric.value, metric.unit)),
                    metric.reference_value !== null && metric.reference_value !== undefined
                        ? h('small', null, `内部参考：${metric.reference_operator || ''} ${reportValue(metric.reference_value, metric.unit)}`)
                        : h('small', null, '未设置判断阈值'),
                    statusBadge(metric.evaluation === 'above_threshold' || metric.evaluation === 'below_threshold' ? 'met' : metric.status)
                )
            ))
        ),
        h('section', { className: 'report-section' },
            h('div', { className: 'section-heading' }, h('h3', null, '影像与模型结果')),
            h('div', { className: 'finding-grid' }, imaging.map((item) =>
                h('article', { className: 'finding-card', key: item.finding_id },
                    h('div', { className: 'finding-heading' }, h('strong', null, item.display_name), statusBadge(item.status)),
                    h('div', { className: 'finding-value' }, item.value || '未获得模型结果'),
                    h('p', null, `来源：${item.source_module || '未知'} · 置信度：${item.confidence == null ? '未提供' : `${(Number(item.confidence) * 100).toFixed(1)}%`}`),
                    item.limitations?.length ? h('p', { className: 'finding-limit' }, item.limitations.join('；')) : null
                )
            ))
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
        vessel_occlusion_status: mergedVesselData.status,
        vessel_occlusion_class_result: mergedVesselData.label,
        vessel_occlusion_confidence: mergedVesselData.confidence,
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
                })
                : React.createElement(React.Fragment, null,
                    React.createElement("div", { className: "legacy-banner" }, "当前为旧版报告展示，结构化证据链不可用。"),
                    React.createElement(PatientInfoModule, { data: patient, isEditing: isEditing, onUpdate: handlePatientUpdate }),
                    React.createElement(ImageFindingsModule, { data: mergedAnalysisData || null, findings: findings, isEditing: isEditing, onUpdate: handleFindingsUpdate }),
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
    };
}

