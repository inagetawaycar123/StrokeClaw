"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const processing = require("../../static/js/processing.js");

function resetState() {
    processing.clearRevealTimer();
    Object.assign(processing.state, {
        fileId: "",
        runId: "",
        latestJob: null,
        latestRun: null,
        uploadDone: false,
        hints: {},
        nodes: [],
        revealedNodeIds: [],
        revealPendingIds: [],
        revealAt: Object.create(null),
    });
}

function completedVesselResult() {
    return {
        status: "completed",
        vessel_occlusion_class_result: "大血管闭塞",
        predicted_class: "Class_1_LVO",
        confidence: 0.875,
        class_counts: { Class_0: 0, Class_1_LVO: 1, Class_2_MEVO: 0 },
        total_slices: 1,
        valid_predictions: 1,
        error_code: null,
        error_message: null,
        failures: [],
    };
}

test.afterEach(() => {
    resetState();
    delete global.setViewerData;
    delete global.sessionStorage;
    delete global.localStorage;
});

test("normStatus keeps issue idempotent", () => {
    assert.equal(processing.normStatus("issue"), "issue");
    assert.equal(processing.normStatus(processing.normStatus("failed")), "issue");
    assert.equal(processing.normStatus("unavailable"), "issue");
});

test("corrupt completed vessel payload without prediction evidence becomes an issue", () => {
    const normalized = processing.normalizeVesselOcclusionResult({
        status: "completed",
        vessel_occlusion_class_result: "大血管闭塞",
        predicted_class: null,
        confidence: 0.99,
        class_counts: { Class_0: 0, Class_1_LVO: 0, Class_2_MEVO: 0 },
        valid_predictions: 0,
    });

    assert.equal(normalized.status, "failed");
    assert.equal(normalized.vessel_occlusion_class_result, null);
    assert.equal(normalized.predicted_class, null);
    assert.equal(normalized.confidence, null);
    assert.deepEqual(normalized.class_counts, {
        Class_0: 0,
        Class_1_LVO: 0,
        Class_2_MEVO: 0,
    });
});

test("a legacy label without model evidence remains unavailable", () => {
    const result = processing.normalizeVesselOcclusionResult({
        vessel_occlusion_class_result: "大血管闭塞",
    });
    assert.equal(result.status, "unavailable");
    assert.equal(result.vessel_occlusion_class_result, null);
});

test("missing CTA is a completed non-applicable upload step", () => {
    processing.state.latestJob = {
        status: "completed",
        result: {
            vessel_occlusion_result: {
                status: "unavailable",
                error_code: "CTA_INPUT_MISSING",
                error_message: "No CTA slice images found",
            },
        },
        steps: [
            {
                key: "vessel_occlusion",
                status: "skipped",
                message: "No CTA slice images found",
            },
        ],
    };

    const node = processing.buildNodes().find((item) => item.key === "vessel_occlusion");
    assert.equal(node.status, "completed");
    assert.match(node.fallback, /No CTA slice images found/);
    assert.equal(node.riskItems.length, 0);
});

test("completed vessel node displays the structured prediction", () => {
    const result = completedVesselResult();
    processing.state.latestJob = {
        status: "completed",
        result: { vessel_occlusion_result: result },
        steps: [{ key: "vessel_occlusion", status: "completed", message: "模型执行完成" }],
    };

    const node = processing.buildNodes().find((item) => item.key === "vessel_occlusion");
    assert.equal(node.status, "completed");
    assert.match(node.fallback, /大血管闭塞/);
    assert.match(node.fallback, /87\.5%/);
    assert.doesNotMatch(node.fallback, /等待模型预测/);
    assert.deepEqual(node.detailResult, processing.normalizeVesselOcclusionResult(result));
    assert.match(processing.displayFallbackForNode(node, "completed"), /大血管闭塞/);
});

test("failed vessel node retains the contract error and remains a soft issue for a completed upload", () => {
    const result = {
        status: "failed",
        vessel_occlusion_class_result: null,
        predicted_class: null,
        confidence: null,
        class_counts: { Class_0: 0, Class_1_LVO: 0, Class_2_MEVO: 0 },
        total_slices: 1,
        valid_predictions: 0,
        error_code: "ALL_PREDICTIONS_FAILED",
        error_message: "All 1 predictions failed",
        failures: [{ image: "slice_000_mcta.png", error_message: "inference failed" }],
    };
    processing.state.latestJob = {
        status: "completed",
        result: { vessel_occlusion_result: result },
        steps: [{ key: "vessel_occlusion", status: "failed", message: "分类失败" }],
    };

    const node = processing.buildNodes().find((item) => item.key === "vessel_occlusion");
    assert.equal(node.status, "issue");
    assert.equal(processing.normStatus(node.status), "issue");
    assert.match(node.fallback, /All 1 predictions failed/);
    assert.equal(node.detailResult.error_code, "ALL_PREDICTIONS_FAILED");
    assert.equal(processing.isBlockingIssue(node), false);
});

test("a degraded step does not stop reveal after the upload job completed", () => {
    processing.state.latestJob = { status: "completed" };
    processing.state.nodes = [
        { id: "soft-issue", key: "vessel_occlusion", group: "upload", status: "issue" },
        { id: "next-step", key: "stroke_analysis", group: "upload", status: "completed" },
    ];
    processing.state.revealedNodeIds = ["soft-issue"];
    processing.state.revealAt["soft-issue"] = Date.now() - 5000;

    processing.syncRevealQueue();
    processing.clearRevealTimer();
    assert.deepEqual(processing.state.revealedNodeIds, ["soft-issue", "next-step"]);
});

test("direct Agent vessel soft failure is deduplicated and does not block downstream nodes", () => {
    const failed = {
        status: "failed",
        error_code: "ALL_PREDICTIONS_FAILED",
        error_message: "All 1 predictions failed",
        total_slices: 1,
        failures: [{ slice_file: "slice_000_mcta.png", error_message: "boom" }],
    };
    processing.state.latestRun = {
        status: "succeeded",
        result: { vessel_occlusion_result: failed },
        tool_results: [{
            tool_name: "vessel_occlusion",
            status: "failed",
            structured_output: failed,
        }],
        steps: [
            { key: "vessel_occlusion", status: "failed", message: "All 1 predictions failed" },
            { key: "generate_medgemma_report", status: "completed", message: "Tool completed" },
        ],
    };

    const nodes = processing.buildNodes();
    const vesselNodes = nodes.filter((node) => node.key === "vessel_occlusion");
    const reportNode = nodes.find((node) => node.key === "generate_medgemma_report");

    assert.equal(vesselNodes.length, 1);
    assert.equal(vesselNodes[0].status, "issue");
    assert.equal(vesselNodes[0].detailResult.error_code, "ALL_PREDICTIONS_FAILED");
    assert.equal(processing.isBlockingIssue(vesselNodes[0]), false);
    assert.equal(processing.canAdvanceRevealFrom(vesselNodes[0]), true);
    assert.equal(reportNode.status, "completed");
});

test("an upload job failure still blocks reveal at its issue", () => {
    processing.state.latestJob = { status: "failed" };
    processing.state.nodes = [
        { id: "hard-issue", key: "ctp_generate", group: "upload", status: "issue" },
        { id: "next-step", key: "stroke_analysis", group: "upload", status: "completed" },
    ];
    processing.state.revealedNodeIds = ["hard-issue"];
    processing.state.revealAt["hard-issue"] = Date.now() - 65000;

    processing.syncRevealQueue();
    assert.deepEqual(processing.state.revealedNodeIds, ["hard-issue"]);
    assert.equal(processing.isBlockingIssue(processing.state.nodes[0]), true);
});

test("persistUpload copies the vessel contract and flattened compatibility fields", () => {
    const vesselResult = completedVesselResult();
    const writes = {};
    let viewerData = null;
    global.setViewerData = (value) => { viewerData = value; };
    global.sessionStorage = { setItem: (key, value) => { writes[`session:${key}`] = value; }, removeItem: () => {} };
    global.localStorage = { setItem: (key, value) => { writes[`local:${key}`] = value; }, removeItem: () => {} };
    processing.state.latestJob = {
        status: "completed",
        result: { file_id: "case-1", vessel_occlusion_result: vesselResult },
    };

    processing.persistUpload(processing.state.latestJob);

    assert.equal(viewerData.file_id, "case-1");
    assert.deepEqual(viewerData.vessel_occlusion_result, processing.normalizeVesselOcclusionResult(vesselResult));
    assert.equal(viewerData.vessel_occlusion_status, "completed");
    assert.equal(viewerData.vessel_occlusion_class_result, "大血管闭塞");
    assert.equal(viewerData.vessel_occlusion_confidence, 0.875);
    assert.equal(viewerData.predicted_class, "Class_1_LVO");
    assert.deepEqual(viewerData.class_counts, vesselResult.class_counts);
    assert.equal(writes["session:current_file_id"], "case-1");
    assert.equal(writes["local:current_file_id"], "case-1");

});
