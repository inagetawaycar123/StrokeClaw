"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

global.React = {
    useState: () => {},
    useEffect: () => {},
    createElement: () => null,
};
global.window = {};

const {
    getStructuredReportSummary,
    reportStatusText,
    reportValue,
    withPerfusionFindingFallback,
    getReportMrsPrognosis,
    getReportAcuteImaging,
    renderAcuteImagingCards,
    renderMrsPrognosisReportSection,
} = require("../../static/js/report.js");

test.after(() => {
    delete global.React;
    delete global.window;
});

test("structured report summary exposes risk, review and issue counts", () => {
    const summary = getStructuredReportSummary({
        report_meta: { risk_level: "high", urgency: "urgent" },
        clinician_review: { overall_status: "pending" },
        patient_summary: {
            fields: [{ field_id: "age", value: 89, unit: "岁" }],
        },
        quantitative_metrics: [
            { metric_id: "mismatch_ratio", value: 2.8, unit: "" },
        ],
        missing_information: [{ issue_id: "missing-vessel" }],
        warnings: [{ issue_id: "conflict" }],
    });

    assert.equal(summary.riskLevel, "high");
    assert.equal(summary.missingCount, 1);
    assert.equal(summary.warningCount, 1);
    assert.equal(summary.metrics.age.value, 89);
    assert.equal(summary.metrics.mismatch_ratio.value, 2.8);
});

test("zero remains visible and statuses are localized", () => {
    assert.equal(reportValue(0, "mL"), "0 mL");
    assert.equal(reportValue(null, "mL"), "未获得");
    assert.equal(reportStatusText("urgent"), "紧急");
    assert.equal(reportStatusText("high"), "高风险");
});

test("legacy completed perfusion finding recovers its quantitative values", () => {
    const findings = withPerfusionFindingFallback(
        [{ finding_id: "perfusion_analysis", status: "completed", value: null }],
        [
            { metric_id: "core_infarct_volume", value: 6.14 },
            { metric_id: "penumbra_volume", value: 17.21 },
            { metric_id: "mismatch_ratio", value: 2.8 },
        ],
    );
    assert.equal(
        findings[0].value,
        "Core 6.14 mL · Penumbra 17.21 mL · Mismatch 2.80",
    );
});

test("unified report cards preserve acute model semantics", () => {
    const acute = getReportAcuteImaging({
        quantitative_metrics: [
            { metric_id: "core_infarct_volume", value: 0 },
            { metric_id: "penumbra_volume", value: 16.59 },
            { metric_id: "mismatch_ratio", value: 2.57 },
        ],
        imaging_findings: [
            { finding_id: "perfusion_analysis", status: "completed", source_module: "CTPAnalysisAgent" },
            { finding_id: "ncct_classification", status: "completed", value: "正常", confidence: 1 },
            { finding_id: "vessel_occlusion_class", status: "completed", value: "无明显狭窄", confidence: 0.519 },
            { finding_id: "cbf_availability", status: "completed", display_name: "CBF 灌注图", value: "已纳入" },
        ],
    });
    assert.equal(acute.perfusion.core, 0);
    assert.equal(acute.ncct.confidence, 1);
    assert.equal(acute.vessel.confidence, 0.519);
    assert.deepEqual(acute.modalities.map((item) => item.id), ["cbf_availability"]);

    const h = (type, props, ...children) => ({ type, props: props || {}, children });
    const cards = renderAcuteImagingCards(h, acute);
    assert.equal(cards.length, 3);
    assert.ok(cards.every((card) => card.props.className.includes("unified-model-card")));
});

test("structured prognosis assessment outranks report payload fallback", () => {
    const current = {
        status: "completed",
        display_mode: "24小时更新评估",
        prediction: {
            good_prognosis_probability: 0.316,
            poor_prognosis_risk: 0.684,
            predicted_class: 1,
            class_name: "mRS 3-6 / 不良预后",
            decision_threshold: 0.55,
            probability_calibrated: true,
        },
        confidence: { level: "low", ensemble_std: 0.04, threshold_margin: 0.134 },
        key_evidence: { clinical: [], imaging: [] },
        data_quality: { missing_clinical_fields: [], image_quality_warnings: [] },
        doctor_review_recommendation: { items: ["请复核"] },
        model: { external_validation_completed: false, production_approved: false },
    };
    const stale = {
        ...current,
        prediction: {
            ...current.prediction,
            good_prognosis_probability: 0.8,
            poor_prognosis_risk: 0.2,
            predicted_class: 0,
            class_name: "mRS 0-2 / 良好预后",
        },
    };

    const normalized = getReportMrsPrognosis(
        { prognosis_assessment: current },
        stale,
    );
    assert.equal(normalized.prediction.classLabel, "不良预后");
    assert.equal(normalized.prediction.poorRisk, 0.684);
    assert.equal(normalized.confidence.level, "low");

    const h = (type, props, ...children) => ({ type, props: props || {}, children });
    const card = renderMrsPrognosisReportSection(h, normalized);
    assert.match(card.props.className, /unified-model-card/);
    assert.match(card.props.className, /full-width/);
    assert.doesNotMatch(card.props.className, /mrs-report-section/);
});

test("missing or invalid prognosis remains unavailable instead of 0 percent", () => {
    const invalid = getReportMrsPrognosis(null, {
        status: "completed",
        prediction: {
            good_prognosis_probability: 0,
            poor_prognosis_risk: 0,
            predicted_class: 0,
            class_name: "mRS 0-2 / 良好预后",
            decision_threshold: 0.55,
        },
    });
    assert.equal(invalid.available, false);
    assert.equal(invalid.prediction, null);
});

test("report unifies acute imaging and mRS before acute rule evaluation", () => {
    const source = fs.readFileSync(
        path.join(__dirname, "../../static/js/report.js"),
        "utf8",
    );
    const structuredStart = source.indexOf("const StructuredReportV2View");
    const structuredEnd = source.indexOf("const getReportStorageKeys", structuredStart);
    const view = source.slice(structuredStart, structuredEnd);
    const imagingIndex = view.indexOf("模型量化与预测结果");
    const acuteCardsIndex = view.indexOf("renderAcuteImagingCards(h, acute)");
    const prognosisIndex = view.indexOf("renderMrsPrognosisReportSection(h, prognosis)");
    const rulesIndex = view.indexOf("规则评估");

    assert.ok(imagingIndex >= 0);
    assert.ok(acuteCardsIndex > imagingIndex);
    assert.ok(prognosisIndex > acuteCardsIndex);
    assert.ok(rulesIndex > prognosisIndex);
    assert.doesNotMatch(view, /关键定量指标/);
    assert.doesNotMatch(view, /h\('h3', null, '影像与模型结果'\)/);
    assert.doesNotMatch(
        source.slice(
            source.indexOf("function renderMrsPrognosisReportSection"),
            source.indexOf("const StructuredReportV2View"),
        ),
        /dangerouslySetInnerHTML/,
    );
});

test("report template loads shared model normalizers before the report renderer", () => {
    const template = fs.readFileSync(
        path.join(__dirname, "../../backend/templates/patient/upload/viewer/report/index.html"),
        "utf8",
    );
    const imagingIndex = template.indexOf("/static/js/imaging_results.js");
    const mrsIndex = template.indexOf("/static/js/mrs_prognosis.js");
    const reportIndex = template.indexOf("/static/js/report.js");
    assert.ok(imagingIndex >= 0);
    assert.ok(mrsIndex > imagingIndex);
    assert.ok(reportIndex > mrsIndex);
});
