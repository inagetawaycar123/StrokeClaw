(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.StrokeClawImagingResults = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    const RULES = Object.freeze({
        core_infarct_volume: Object.freeze({ operator: '<', threshold: 70, unit: 'mL' }),
        mismatch_ratio: Object.freeze({ operator: '>', threshold: 1.8, unit: '' }),
    });
    const TERMINAL_FAILURES = new Set(['failed', 'error']);
    const SKIPPED_STATUSES = new Set(['skipped', 'blocked', 'gated']);
    const COMPLETED_STATUSES = new Set(['completed', 'success', 'succeeded', 'present', 'observed']);
    const NCCT_LABELS = Object.freeze({
        normal: '正常',
        hemo: '脑出血',
        hemorrhage: '脑出血',
        infarct: '脑缺血',
        ischemia: '脑缺血',
    });
    const VESSEL_LABELS = Object.freeze({
        class_0: '无明显狭窄',
        class_1_lvo: '大血管闭塞',
        class_2_mevo: '中血管闭塞',
        normal: '无明显狭窄',
        lvo: '大血管闭塞',
        mevo: '中血管闭塞',
    });

    function object(value) {
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    }

    function firstPresent(...values) {
        return values.find((value) => value !== null && value !== undefined && value !== '');
    }

    function finiteNumber(value) {
        if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function normalizeConfidence(value) {
        if (value === null || value === undefined || value === '') return null;
        const text = String(value).trim();
        if (!text) return null;
        const percent = text.endsWith('%');
        const parsed = finiteNumber(percent ? text.slice(0, -1).trim() : text);
        if (parsed === null) return null;
        const normalized = percent || parsed > 1 ? parsed / 100 : parsed;
        return normalized >= 0 && normalized <= 1 ? normalized : null;
    }

    function normalizeStatus(value, hasResult) {
        const status = String(value || '').trim().toLowerCase();
        if (SKIPPED_STATUSES.has(status)) return 'skipped';
        if (TERMINAL_FAILURES.has(status)) return 'failed';
        if (COMPLETED_STATUSES.has(status)) return hasResult ? 'completed' : 'unavailable';
        return hasResult ? 'completed' : 'unavailable';
    }

    function formatVolume(value) {
        const numeric = finiteNumber(value);
        return numeric === null ? '--' : `${numeric.toFixed(1)} mL`;
    }

    function formatRatio(value) {
        const numeric = finiteNumber(value);
        return numeric === null ? '--' : numeric.toFixed(2);
    }

    function formatConfidence(value) {
        const normalized = normalizeConfidence(value);
        return normalized === null ? '--' : `${(normalized * 100).toFixed(1)}%`;
    }

    function normalizeLimitations(...values) {
        const output = [];
        values.flat(Infinity).forEach((value) => {
            const text = typeof value === 'string' ? value.trim() : '';
            if (text && !output.includes(text)) output.push(text);
        });
        return output;
    }

    function evaluationForCore(value) {
        const numeric = finiteNumber(value);
        if (numeric === null) return { status: 'unavailable', label: '未生成' };
        return numeric < RULES.core_infarct_volume.threshold
            ? { status: 'met', label: '满足内部参考' }
            : { status: 'not_met', label: '达到或超过内部参考值' };
    }

    function evaluationForMismatch(value) {
        const numeric = finiteNumber(value);
        if (numeric === null) return { status: 'unavailable', label: '未生成' };
        return numeric > RULES.mismatch_ratio.threshold
            ? { status: 'attention', label: '达到内部提示阈值' }
            : { status: 'not_met', label: '未达到内部提示阈值' };
    }

    function normalizePerfusionResult(rawValue) {
        const raw = object(rawValue);
        const safetyGate = object(firstPresent(raw.safety_gate, raw.safetyGate));
        const blocked = safetyGate.blocked === true || SKIPPED_STATUSES.has(String(raw.status || '').toLowerCase());
        const core = finiteNumber(firstPresent(raw.core_infarct_volume, raw.core_volume_ml, raw.core_volume, raw.core));
        const penumbra = finiteNumber(firstPresent(raw.penumbra_volume, raw.penumbra_volume_ml, raw.penumbra));
        const mismatch = finiteNumber(firstPresent(raw.mismatch_ratio, raw.mismatch));
        const hasValues = core !== null || penumbra !== null || mismatch !== null;
        const status = blocked ? 'skipped' : normalizeStatus(raw.status, hasValues);
        const showValues = status === 'completed';
        const visibleCore = showValues ? core : null;
        const visiblePenumbra = showValues ? penumbra : null;
        const visibleMismatch = showValues ? mismatch : null;
        const limitations = normalizeLimitations(
            raw.limitations,
            raw.warning,
            raw.error_message,
            blocked ? firstPresent(raw.skip_reason, raw.reason, safetyGate.reason, '因安全门控跳过。') : null
        );
        const coreEvaluation = evaluationForCore(visibleCore);
        const mismatchEvaluation = evaluationForMismatch(visibleMismatch);
        let mismatchStatus = raw.has_mismatch === true ? '存在显著不匹配' : raw.has_mismatch === false ? '未见显著不匹配' : null;
        if (blocked) mismatchStatus = null;
        if (!mismatchStatus && visibleMismatch !== null) mismatchStatus = visibleMismatch > RULES.mismatch_ratio.threshold ? '存在显著不匹配' : '未见显著不匹配';
        const summary = status === 'completed'
            ? [
                visibleCore === null ? null : `核心梗死体积 ${formatVolume(visibleCore)}`,
                visiblePenumbra === null ? null : `半暗带体积 ${formatVolume(visiblePenumbra)}`,
                visibleMismatch === null ? null : `不匹配比值 ${formatRatio(visibleMismatch)}`,
            ].filter(Boolean).join('，')
            : (limitations[0] || '未获得有效灌注定量结果。');
        return {
            status,
            core: visibleCore,
            penumbra: visiblePenumbra,
            mismatch: visibleMismatch,
            mismatchStatus,
            coreEvaluation,
            mismatchEvaluation,
            summary,
            source: String(firstPresent(raw.source_module, raw.source, 'CTPAnalysisAgent') || ''),
            limitations,
            safetyGate,
            modalityAvailability: object(raw.modality_availability),
            reviewStatus: raw.review_status || null,
            clinicianConfirmed: raw.clinician_confirmed === true,
            evidenceIds: Array.isArray(raw.evidence_ids) ? raw.evidence_ids : [],
        };
    }

    function normalizeNcctResult(rawValue) {
        const candidate = object(rawValue);
        const raw = object(candidate.three_class_result && typeof candidate.three_class_result === 'object'
            ? candidate.three_class_result
            : candidate);
        const key = String(firstPresent(raw.three_class_label, raw.label, raw.predicted_class, '') || '').trim().toLowerCase();
        const suppliedLabel = String(firstPresent(raw.three_class_label_cn, raw.label_cn, raw.value, '') || '').trim();
        const label = suppliedLabel || NCCT_LABELS[key] || (key ? key : null);
        const status = normalizeStatus(firstPresent(raw.status, raw.three_class_status, candidate.three_class_status), !!label);
        const safetyGate = object(firstPresent(raw.safety_gate, candidate.safety_gate));
        return {
            status,
            label: status === 'completed' ? label : null,
            labelKey: key,
            confidence: status === 'completed' ? normalizeConfidence(firstPresent(raw.three_class_confidence, raw.confidence)) : null,
            tone: /出血|hemo|hemorrhage/i.test(`${label || ''} ${key}`) ? 'danger'
                : /缺血|infarct|ischemia/i.test(`${label || ''} ${key}`) ? 'attention'
                    : /正常|normal/i.test(`${label || ''} ${key}`) ? 'normal' : 'neutral',
            classCounts: object(firstPresent(raw.class_counts, raw.classCounts, raw.three_class_counts, candidate.three_class_counts)),
            totalSlices: finiteNumber(firstPresent(raw.total_slices, raw.totalSlices, raw.three_class_total_slices, candidate.three_class_total_slices)),
            safetyGate,
            source: String(firstPresent(raw.source_module, raw.source, candidate.source, 'NCCTThreeClassAgent') || ''),
            limitations: normalizeLimitations(raw.limitations, raw.warning, raw.error_message),
            reviewStatus: raw.review_status || null,
            clinicianConfirmed: raw.clinician_confirmed === true,
            evidenceIds: Array.isArray(raw.evidence_ids) ? raw.evidence_ids : [],
        };
    }

    function normalizeVesselResult(rawValue) {
        const candidate = object(rawValue);
        const raw = object(candidate.vessel_occlusion_result && typeof candidate.vessel_occlusion_result === 'object'
            ? candidate.vessel_occlusion_result
            : candidate);
        const key = String(firstPresent(raw.predicted_class, raw.class_name, candidate.vessel_occlusion_predicted_class, '') || '').trim().toLowerCase();
        const suppliedLabel = String(firstPresent(raw.vessel_occlusion_class_result, raw.label, raw.value, candidate.vessel_occlusion_class_result, '') || '').trim();
        const label = suppliedLabel || VESSEL_LABELS[key] || (key ? key : null);
        const status = normalizeStatus(firstPresent(raw.status, candidate.vessel_occlusion_status), !!label);
        return {
            status,
            label: status === 'completed' ? label : null,
            labelKey: key,
            confidence: status === 'completed' ? normalizeConfidence(firstPresent(raw.confidence, candidate.vessel_occlusion_confidence)) : null,
            tone: /大血管|lvo/i.test(`${label || ''} ${key}`) && !/mevo/i.test(key) ? 'danger'
                : /中血管|mevo/i.test(`${label || ''} ${key}`) ? 'attention'
                    : /无明显|normal|class_0/i.test(`${label || ''} ${key}`) ? 'normal' : 'neutral',
            classCounts: object(firstPresent(raw.class_counts, raw.classCounts, candidate.vessel_occlusion_class_counts)),
            totalSlices: finiteNumber(firstPresent(raw.total_slices, raw.totalSlices, candidate.vessel_occlusion_total_slices)),
            validPredictions: finiteNumber(firstPresent(raw.valid_predictions, raw.validPredictions, candidate.vessel_occlusion_valid_predictions)),
            inputPhases: Array.isArray(firstPresent(raw.input_phases, raw.inputPhases, raw.available_modalities, candidate.available_modalities))
                ? firstPresent(raw.input_phases, raw.inputPhases, raw.available_modalities, candidate.available_modalities).map(String)
                : [],
            source: String(firstPresent(raw.source_module, raw.source, candidate.vessel_occlusion_source, 'VesselOcclusionAgent') || ''),
            limitations: normalizeLimitations(raw.limitations, raw.warning, raw.error_message, raw.error),
            reviewStatus: raw.review_status || null,
            clinicianConfirmed: raw.clinician_confirmed === true,
            evidenceIds: Array.isArray(raw.evidence_ids) ? raw.evidence_ids : [],
        };
    }

    function normalizeModalityFindings(findings) {
        const allowed = new Set(['cta_assessment', 'cbf_availability', 'cbv_availability', 'tmax_availability']);
        return (Array.isArray(findings) ? findings : [])
            .filter((item) => item && allowed.has(item.finding_id))
            .map((item) => ({
                id: item.finding_id,
                label: item.display_name || item.finding_id,
                value: item.value || '',
                status: normalizeStatus(item.status, !!item.value),
                source: item.source_module || '',
                limitations: normalizeLimitations(item.limitations),
            }));
    }

    function normalizeAcuteImagingResults(input) {
        const source = object(input);
        return {
            perfusion: normalizePerfusionResult(source.perfusion),
            ncct: normalizeNcctResult(source.ncct),
            vessel: normalizeVesselResult(source.vessel),
            modalities: normalizeModalityFindings(source.modalityFindings),
        };
    }

    function fromStructuredReport(reportValue, fallbackValue) {
        const report = object(reportValue);
        const fallback = object(fallbackValue);
        const metrics = new Map((Array.isArray(report.quantitative_metrics) ? report.quantitative_metrics : []).map((item) => [item.metric_id, item]));
        const findings = new Map((Array.isArray(report.imaging_findings) ? report.imaging_findings : []).map((item) => [item.finding_id, item]));
        const perfusionFinding = object(findings.get('perfusion_analysis'));
        const core = object(metrics.get('core_infarct_volume'));
        const penumbra = object(metrics.get('penumbra_volume'));
        const mismatch = object(metrics.get('mismatch_ratio'));
        const ncctFinding = object(findings.get('ncct_classification'));
        const vesselFinding = object(findings.get('vessel_occlusion_class'));
        const result = normalizeAcuteImagingResults({
            perfusion: {
                ...object(fallback.perfusion),
                status: firstPresent(perfusionFinding.status, fallback.perfusion?.status),
                core_infarct_volume: firstPresent(core.value, fallback.perfusion?.core_infarct_volume, fallback.perfusion?.core),
                penumbra_volume: firstPresent(penumbra.value, fallback.perfusion?.penumbra_volume, fallback.perfusion?.penumbra),
                mismatch_ratio: firstPresent(mismatch.value, fallback.perfusion?.mismatch_ratio, fallback.perfusion?.mismatch),
                source_module: firstPresent(perfusionFinding.source_module, core.source_module, fallback.perfusion?.source),
                limitations: normalizeLimitations(perfusionFinding.limitations, core.limitations, penumbra.limitations, mismatch.limitations, fallback.perfusion?.limitations),
                review_status: firstPresent(perfusionFinding.review_status, core.review_status),
                clinician_confirmed: perfusionFinding.clinician_confirmed === true || core.clinician_confirmed === true,
                evidence_ids: Array.from(new Set([
                    ...(Array.isArray(perfusionFinding.evidence_ids) ? perfusionFinding.evidence_ids : []),
                    core.evidence_id,
                    penumbra.evidence_id,
                    mismatch.evidence_id,
                ].filter(Boolean))),
            },
            ncct: {
                ...object(fallback.ncct),
                status: firstPresent(ncctFinding.status, fallback.ncct?.status),
                value: firstPresent(ncctFinding.value, fallback.ncct?.value, fallback.ncct?.three_class_label_cn),
                confidence: firstPresent(ncctFinding.confidence, fallback.ncct?.confidence, fallback.ncct?.three_class_confidence),
                source_module: firstPresent(ncctFinding.source_module, fallback.ncct?.source),
                limitations: normalizeLimitations(ncctFinding.limitations, fallback.ncct?.limitations),
                review_status: firstPresent(ncctFinding.review_status, fallback.ncct?.reviewStatus),
                clinician_confirmed: ncctFinding.clinician_confirmed === true || fallback.ncct?.clinicianConfirmed === true,
                evidence_ids: ncctFinding.evidence_ids || fallback.ncct?.evidenceIds,
            },
            vessel: {
                ...object(fallback.vessel),
                status: firstPresent(vesselFinding.status, fallback.vessel?.status),
                value: firstPresent(vesselFinding.value, fallback.vessel?.value, fallback.vessel?.vessel_occlusion_class_result),
                confidence: firstPresent(vesselFinding.confidence, fallback.vessel?.confidence),
                source_module: firstPresent(vesselFinding.source_module, fallback.vessel?.source),
                limitations: normalizeLimitations(vesselFinding.limitations, fallback.vessel?.limitations),
                review_status: firstPresent(vesselFinding.review_status, fallback.vessel?.reviewStatus),
                clinician_confirmed: vesselFinding.clinician_confirmed === true || fallback.vessel?.clinicianConfirmed === true,
                evidence_ids: vesselFinding.evidence_ids || fallback.vessel?.evidenceIds,
            },
            modalityFindings: Array.from(findings.values()),
        });
        return result;
    }

    function extractRunAcuteImagingResult(runValue) {
        const run = object(runValue);
        const result = object(run.result);
        let stroke = object(result.analysis_result);
        let ncct = object(result.three_class_result);
        let vessel = object(result.vessel_occlusion_result);
        const toolResults = Array.isArray(run.tool_results) ? run.tool_results : [];
        for (let index = toolResults.length - 1; index >= 0; index -= 1) {
            const tool = object(toolResults[index]);
            const output = object(firstPresent(tool.structured_output, tool.output_ref, tool.output));
            if (!Object.keys(stroke).length && ['run_stroke_analysis', 'stroke_analysis'].includes(tool.tool_name)) stroke = output;
            if (!Object.keys(ncct).length && ['run_ncct_classification', 'ncct_three_class', 'three_class'].includes(tool.tool_name)) ncct = output;
            if (!Object.keys(vessel).length && ['vessel_occlusion', 'run_vessel_occlusion_classification'].includes(tool.tool_name)) vessel = output;
        }
        const planner = object(run.planner_input);
        const modalities = firstPresent(result.available_modalities, planner.available_modalities, []);
        return normalizeAcuteImagingResults({
            perfusion: {
                ...stroke,
                safety_gate: firstPresent(stroke.safety_gate, result.safety_gate, result.three_class_result?.safety_gate),
            },
            ncct: Object.keys(ncct).length ? ncct : object(planner.three_class_result),
            vessel,
            modalityFindings: (Array.isArray(modalities) ? modalities : []).map((name) => ({
                finding_id: ['cbf', 'cbv', 'tmax'].includes(String(name).toLowerCase()) ? `${String(name).toLowerCase()}_availability` : String(name).toLowerCase().includes('cta') ? 'cta_assessment' : '',
                display_name: String(name).toUpperCase(),
                value: '已获得输入',
                status: 'completed',
                source_module: 'detect_modalities',
            })).filter((item) => item.finding_id),
        });
    }

    return {
        RULES,
        finiteNumber,
        normalizeConfidence,
        normalizeStatus,
        formatVolume,
        formatRatio,
        formatConfidence,
        evaluationForCore,
        evaluationForMismatch,
        normalizePerfusionResult,
        normalizeNcctResult,
        normalizeVesselResult,
        normalizeModalityFindings,
        normalizeAcuteImagingResults,
        fromStructuredReport,
        extractRunAcuteImagingResult,
    };
});
