"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

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
