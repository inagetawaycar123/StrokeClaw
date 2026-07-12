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
    getReportStorageKeys,
    getCaseScopedViewerData,
    getSafeVesselDisplayData,
    injectVesselOcclusionIntoMarkdown,
} = require("../../static/js/report.js");

test.after(() => {
    delete global.React;
    delete global.window;
});

test("report shows only a completed model result", () => {
    const result = getSafeVesselDisplayData({
        vessel_occlusion_result: {
            status: "completed",
            vessel_occlusion_class_result: "无明显狭窄",
            predicted_class: "Class_0",
            confidence: 0.519,
        },
    });

    assert.deepEqual(result, {
        label: "无明显狭窄",
        confidence: 0.519,
        status: "completed",
    });
});

test("report renders a failed result as unavailable", () => {
    const result = getSafeVesselDisplayData({
        vessel_occlusion_result: {
            status: "failed",
            vessel_occlusion_class_result: null,
            error_code: "ALL_PREDICTIONS_FAILED",
        },
    });

    assert.equal(result.label, "未获得模型结果");
    assert.equal(result.confidence, null);
    assert.equal(result.status, "failed");
});

test("legacy hard-coded LVO without completed status is rejected", () => {
    const result = getSafeVesselDisplayData({
        vessel_occlusion_class_result: "大血管闭塞",
    });

    assert.equal(result.label, "未获得模型结果");
    assert.equal(result.confidence, null);
    assert.equal(result.status, "unavailable");
});

test("completed label without prediction evidence is rejected", () => {
    const result = getSafeVesselDisplayData({
        vessel_occlusion_result: {
            status: "completed",
            vessel_occlusion_class_result: "大血管闭塞",
            confidence: 0.99,
            valid_predictions: 0,
            class_counts: {
                Class_0: 0,
                Class_1_LVO: 0,
                Class_2_MEVO: 0,
            },
        },
    });

    assert.deepEqual(result, {
        label: "未获得模型结果",
        confidence: null,
        status: "unavailable",
    });
});

test("completed result with null confidence does not render zero percent", () => {
    const result = getSafeVesselDisplayData({
        vessel_occlusion_result: {
            status: "completed",
            vessel_occlusion_class_result: "无明显狭窄",
            predicted_class: "Class_0",
            confidence: null,
        },
        vessel_occlusion_confidence: null,
    });

    assert.equal(result.label, "无明显狭窄");
    assert.equal(result.confidence, null);
    assert.equal(result.status, "completed");
});

test("report cache is accepted only for the requested file", () => {
    const cached = {
        file_id: "case-a",
        vessel_occlusion_class_result: "大血管闭塞",
    };

    assert.equal(getCaseScopedViewerData(cached, "case-a"), cached);
    assert.deepEqual(getCaseScopedViewerData(cached, "case-b"), {});
    assert.deepEqual(getCaseScopedViewerData(cached, null), {});
});

test("report cache fails closed when file_id is missing", () => {
    assert.equal(getReportStorageKeys(null), null);
    assert.equal(getReportStorageKeys(""), null);
    assert.deepEqual(getReportStorageKeys("case-a"), {
        report: "ai_report_case-a",
        generating: "ai_report_generating_case-a",
        error: "ai_report_error_case-a",
        payload: "ai_report_payload_case-a",
    });
});

test("cached markdown vessel line is replaced with the current safe label", () => {
    const markdown = "## 影像摘要\n血管堵塞三分类：大血管闭塞\n其他内容";
    const updated = injectVesselOcclusionIntoMarkdown(markdown, "未获得模型结果");

    assert.match(updated, /血管堵塞三分类：未获得模型结果/);
    assert.doesNotMatch(updated, /血管堵塞三分类：大血管闭塞/);
});
