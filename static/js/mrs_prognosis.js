(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (root) root.StrokeClawMrsPrognosis = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
    'use strict';

    const CONFIDENCE_LABELS = Object.freeze({
        high: '高',
        medium: '中',
        low: '低',
        unknown: '未知',
        unavailable: '不可用',
    });

    const asObject = (value) => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    const asArray = (value) => Array.isArray(value) ? value : [];
    const text = (value) => value == null ? '' : String(value).trim();
    const finite = (value) => {
        if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    };
    const probability = (value) => {
        const parsed = finite(value);
        return parsed !== null && parsed >= 0 && parsed <= 1 ? parsed : null;
    };

    function unavailable(reason, raw) {
        return {
            status: 'unavailable',
            available: false,
            reason: reason || text(asObject(raw).message) || '未生成 90 天 mRS 预测结果。',
            resultMode: text(asObject(raw).result_mode) || null,
            displayMode: text(asObject(raw).display_mode) || null,
            prediction: null,
            confidence: { level: 'unavailable', ensembleStd: null, thresholdMargin: null, reasons: [] },
            clinicalEvidence: [],
            imagingEvidence: [],
            missingClinicalFields: [],
            imageQualityWarnings: [],
            reviewItems: [],
            fallbackUsed: Boolean(asObject(raw).fallback_used),
            fallbackReason: text(asObject(raw).fallback_reason) || null,
            model: {},
            limitations: [],
            deterministicSummary: reason || text(asObject(raw).message) || '未生成 90 天 mRS 预测结果。',
        };
    }

    function unwrap(rawValue) {
        const raw = asObject(rawValue);
        if (Object.keys(asObject(raw.mrs_prognosis_result)).length) return asObject(raw.mrs_prognosis_result);
        if (Object.keys(asObject(raw.prognosis_assessment)).length) return asObject(raw.prognosis_assessment);
        return raw;
    }

    function normalizeMrsPrognosisResult(rawValue) {
        const raw = unwrap(rawValue);
        if (text(raw.status).toLowerCase() !== 'completed') return unavailable('', raw);
        const prediction = asObject(raw.prediction);
        const good = probability(prediction.good_prognosis_probability);
        const poor = probability(prediction.poor_prognosis_risk);
        const threshold = probability(prediction.decision_threshold);
        const predictedClass = Number(prediction.predicted_class);
        if (good === null || poor === null || threshold === null) {
            return unavailable('90 天 mRS 预测概率或决策阈值无效。', raw);
        }
        if (Math.abs(good + poor - 1) > 0.02) {
            return unavailable('90 天 mRS 两类预测概率不互补。', raw);
        }
        const expectedClass = poor >= threshold ? 1 : 0;
        if (![0, 1].includes(predictedClass) || predictedClass !== expectedClass) {
            return unavailable('90 天 mRS 预测类别与决策阈值不一致。', raw);
        }

        const expectedRange = predictedClass === 1 ? 'mRS 3-6' : 'mRS 0-2';
        const classLabel = predictedClass === 1 ? '不良预后' : '良好预后';
        let className = text(prediction.class_name) || `${expectedRange} / ${classLabel}`;
        if (!className.includes(expectedRange)) return unavailable('90 天 mRS 预测类别名称不一致。', raw);
        className = `${expectedRange} / ${classLabel}`;

        const confidenceRaw = asObject(raw.confidence);
        let confidenceLevel = text(confidenceRaw.level).toLowerCase();
        if (!['high', 'medium', 'low'].includes(confidenceLevel)) confidenceLevel = 'unknown';
        const evidence = asObject(raw.key_evidence);
        const quality = asObject(raw.data_quality);
        const review = asObject(raw.doctor_review_recommendation);
        const model = asObject(raw.model);
        const displayMode = text(raw.display_mode)
            || (text(raw.result_mode) === 'update_24h' ? '24小时更新评估' : '首诊初步评估');
        const confidenceCn = CONFIDENCE_LABELS[confidenceLevel];
        const deterministicSummary = text(raw.deterministic_summary) || (
            `${displayMode}模型预测 90 天 mRS 0-2 概率为 ${(good * 100).toFixed(1)}%，`
            + `mRS 3-6 风险为 ${(poor * 100).toFixed(1)}%，当前预测为${classLabel}，`
            + `模型置信度为${confidenceCn}。`
        );

        return {
            status: 'completed',
            available: true,
            reason: '',
            resultMode: text(raw.result_mode) || null,
            displayMode,
            prediction: {
                goodProbability: good,
                poorRisk: poor,
                predictedClass,
                className,
                classRange: expectedRange,
                classLabel,
                decisionThreshold: threshold,
                probabilityCalibrated: prediction.probability_calibrated === true,
            },
            confidence: {
                level: confidenceLevel,
                ensembleStd: finite(confidenceRaw.ensemble_std ?? confidenceRaw.ensemble_probability_std),
                thresholdMargin: finite(confidenceRaw.threshold_margin),
                reasons: asArray(confidenceRaw.reasons).map(text).filter(Boolean),
            },
            clinicalEvidence: asArray(evidence.clinical).slice(0, 3).map((item) => ({
                displayName: text(asObject(item).display_name) || text(asObject(item).feature) || '临床因素',
                value: finite(asObject(item).value),
                contribution: finite(asObject(item).contribution),
                direction: text(asObject(item).direction) || 'unknown',
            })),
            imagingEvidence: asArray(evidence.imaging).slice(0, 3).map((item, index) => ({
                regionLabel: text(asObject(item).region_label) || `NCCT 关注区域 ${index + 1}`,
                attentionScore: probability(asObject(item).attention_score),
                interpretation: text(asObject(item).interpretation)
                    || '模型关注区域；attention 不代表因果贡献或确定病灶。',
            })),
            attributionNotice: text(evidence.attribution_notice) || '模型归因不代表因果关系。',
            missingClinicalFields: asArray(quality.missing_clinical_fields).map(text).filter(Boolean),
            imageQualityWarnings: asArray(quality.image_quality_warnings).map(text).filter(Boolean),
            reviewItems: asArray(review.items).map(text).filter(Boolean),
            fallbackUsed: Boolean(raw.fallback_used),
            fallbackReason: text(raw.fallback_reason) || null,
            model: {
                modelVersion: text(model.model_version) || null,
                bundleVersion: text(model.bundle_version) || null,
                releaseStatus: text(model.release_status) || null,
                externalValidationCompleted: model.external_validation_completed === true,
                productionApproved: model.production_approved === true,
            },
            limitations: asArray(raw.limitations).map(text).filter(Boolean),
            deterministicSummary,
        };
    }

    function extractRunMrsPrognosisResult(runState) {
        const run = asObject(runState);
        const result = asObject(run.result);
        if (Object.keys(asObject(result.mrs_prognosis_result)).length) return result.mrs_prognosis_result;
        const toolResults = asArray(run.tool_results);
        for (let index = toolResults.length - 1; index >= 0; index -= 1) {
            const item = asObject(toolResults[index]);
            if (item.tool_name !== 'run_mrs_prognosis_prediction') continue;
            const output = asObject(item.structured_output);
            if (Object.keys(output).length) return output;
            return { status: item.status === 'completed' ? 'unavailable' : item.status, message: item.error_message };
        }
        const reportPayload = asObject(asObject(result.report_result).report_payload);
        if (Object.keys(asObject(reportPayload.mrs_prognosis_result)).length) return reportPayload.mrs_prognosis_result;
        return null;
    }

    function formatProbability(value) {
        const parsed = probability(value);
        return parsed === null ? '--' : `${(parsed * 100).toFixed(1)}%`;
    }

    function confidenceLabel(level) {
        return CONFIDENCE_LABELS[text(level).toLowerCase()] || '未知';
    }

    function confidenceTone(level) {
        return ['high', 'medium', 'low'].includes(text(level).toLowerCase())
            ? text(level).toLowerCase()
            : 'unknown';
    }

    function prognosisTone(result) {
        const normalized = result && result.available !== undefined ? result : normalizeMrsPrognosisResult(result);
        if (!normalized.available) return 'unavailable';
        return normalized.prediction.predictedClass === 1 ? 'poor' : 'good';
    }

    return {
        normalizeMrsPrognosisResult,
        extractRunMrsPrognosisResult,
        formatProbability,
        confidenceLabel,
        confidenceTone,
        prognosisTone,
    };
});
