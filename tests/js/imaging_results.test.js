const test = require('node:test');
const assert = require('node:assert/strict');

const imaging = require('../../static/js/imaging_results.js');

test('formats zero as a real result and rejects missing values', () => {
    assert.equal(imaging.formatVolume(0), '0.0 mL');
    assert.equal(imaging.formatRatio(0), '0.00');
    assert.equal(imaging.formatConfidence(0), '0.0%');
    assert.equal(imaging.formatVolume(null), '--');
    assert.equal(imaging.formatRatio('bad'), '--');
    assert.equal(imaging.formatConfidence(undefined), '--');
});

test('locks the existing core and mismatch threshold boundaries', () => {
    assert.deepEqual(imaging.RULES.core_infarct_volume, { operator: '<', threshold: 70, unit: 'mL' });
    assert.deepEqual(imaging.RULES.mismatch_ratio, { operator: '>', threshold: 1.8, unit: '' });
    assert.equal(imaging.evaluationForCore(69.99).status, 'met');
    assert.equal(imaging.evaluationForCore(70).status, 'not_met');
    assert.equal(imaging.evaluationForMismatch(1.8).status, 'not_met');
    assert.equal(imaging.evaluationForMismatch(1.81).status, 'attention');
});

test('normalizes decimal, percentage and legacy confidence forms', () => {
    assert.equal(imaging.normalizeConfidence(0.519), 0.519);
    assert.equal(imaging.normalizeConfidence(51.9), 0.519);
    assert.equal(imaging.normalizeConfidence('51.9%'), 0.519);
    assert.equal(imaging.formatConfidence('51.9%'), '51.9%');
    assert.equal(imaging.normalizeConfidence(101), null);
});

test('keeps clinical classification tone independent from confidence', () => {
    const normal = imaging.normalizeNcctResult({ status: 'completed', three_class_label: 'normal', confidence: 0.2 });
    const hemorrhage = imaging.normalizeNcctResult({ status: 'completed', three_class_label: 'hemo', confidence: 0.99 });
    const mevo = imaging.normalizeVesselResult({ status: 'completed', predicted_class: 'Class_2_MEVO', confidence: 0.99 });
    assert.equal(normal.tone, 'normal');
    assert.equal(hemorrhage.tone, 'danger');
    assert.equal(mevo.tone, 'attention');
    assert.equal(imaging.formatConfidence(normal.confidence), '20.0%');
});

test('preserves completed, skipped, failed and unavailable states', () => {
    assert.equal(imaging.normalizePerfusionResult({ core_volume_ml: 0 }).status, 'completed');
    const skipped = imaging.normalizePerfusionResult({ status: 'skipped', reason: '出血门控', core_volume_ml: 8 });
    assert.equal(skipped.status, 'skipped');
    assert.equal(skipped.core, null);
    assert.match(skipped.summary, /出血门控/);
    assert.equal(imaging.normalizePerfusionResult({ status: 'failed', core_volume_ml: 8 }).core, null);
    assert.equal(imaging.normalizeNcctResult({ status: 'failed', value: '正常' }).status, 'failed');
    assert.equal(imaging.normalizeVesselResult({ status: 'completed' }).status, 'unavailable');
});

test('structured report values override fallback while fallback keeps detail fields', () => {
    const result = imaging.fromStructuredReport({
        quantitative_metrics: [
            { metric_id: 'core_infarct_volume', value: 6.03, source_module: 'StrokeAnalysisAgent' },
            { metric_id: 'penumbra_volume', value: 13.59, source_module: 'StrokeAnalysisAgent' },
            { metric_id: 'mismatch_ratio', value: 2.25, source_module: 'StrokeAnalysisAgent' },
        ],
        imaging_findings: [
            { finding_id: 'perfusion_analysis', status: 'completed', source_module: 'CTPAnalysisAgent' },
            { finding_id: 'ncct_classification', status: 'completed', value: '正常', confidence: 1 },
            { finding_id: 'vessel_occlusion_class', status: 'completed', value: '无明显狭窄', confidence: 0.519 },
            { finding_id: 'cta_assessment', status: 'completed', display_name: 'CTA / 多期 CTA', value: '已获得影像' },
        ],
    }, {
        ncct: { class_counts: { normal: 3 }, total_slices: 3 },
        vessel: { valid_predictions: 4 },
    });
    assert.equal(result.perfusion.core, 6.03);
    assert.equal(result.ncct.label, '正常');
    assert.deepEqual(result.ncct.classCounts, { normal: 3 });
    assert.equal(result.vessel.validPredictions, 4);
    assert.deepEqual(result.modalities.map((item) => item.id), ['cta_assessment']);
});

test('modality input findings never become quantitative model results', () => {
    const result = imaging.fromStructuredReport({
        quantitative_metrics: [],
        imaging_findings: [
            { finding_id: 'cbf_availability', display_name: 'CBF 灌注图', value: '已纳入', status: 'completed' },
            { finding_id: 'perfusion_analysis', display_name: '灌注分析', value: null, status: 'not_run' },
        ],
    });
    assert.equal(result.perfusion.status, 'unavailable');
    assert.equal(result.modalities.length, 1);
    assert.equal(result.modalities[0].id, 'cbf_availability');
});

test('dynamic text remains plain data for safe DOM and React rendering', () => {
    const result = imaging.normalizeNcctResult({
        status: 'completed',
        value: '<img src=x onerror=alert(1)>',
        confidence: 0.8,
    });
    assert.equal(result.label, '<img src=x onerror=alert(1)>');
    assert.equal(typeof result.label, 'string');
});

test('Agent Run extraction uses aggregate results and legacy tool-result fallbacks', () => {
    const aggregate = imaging.extractRunAcuteImagingResult({
        result: {
            analysis_result: { core_infarct_volume: 7, penumbra_volume: 12, mismatch_ratio: 1.71 },
            three_class_result: { status: 'completed', three_class_label: 'normal', confidence: 0.9 },
            vessel_occlusion_result: { status: 'completed', predicted_class: 'Class_0', confidence: 0.8, valid_predictions: 1 },
        },
    });
    assert.equal(aggregate.perfusion.core, 7);
    assert.equal(aggregate.ncct.label, '正常');
    assert.equal(aggregate.vessel.label, '无明显狭窄');

    const fallback = imaging.extractRunAcuteImagingResult({
        tool_results: [
            { tool_name: 'run_ncct_classification', structured_output: { status: 'completed', three_class_label: 'infarct', confidence: 0.7 } },
            { tool_name: 'run_stroke_analysis', structured_output: { core_infarct_volume: 0, penumbra_volume: 1, mismatch_ratio: 0 } },
        ],
    });
    assert.equal(fallback.ncct.label, '脑缺血');
    assert.equal(fallback.perfusion.core, 0);
});
