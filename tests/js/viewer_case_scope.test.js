"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
    agentRunMatchesCase,
    normalizeViewerVesselOcclusionResult,
    toggleAnalysisPanel,
    validateAgentRunForCase,
    viewerDataMatchesFileId,
} = require("../../static/js/viewer.js");

test("viewer_data must match the file requested by the URL", () => {
    assert.equal(viewerDataMatchesFileId({ file_id: "case-a" }, "case-a"), true);
    assert.equal(viewerDataMatchesFileId({ file_id: "case-a" }, "case-b"), false);
    assert.equal(viewerDataMatchesFileId({}, "case-a"), false);
    assert.equal(viewerDataMatchesFileId({ file_id: "case-a" }, null), false);
});

test("Agent Run top-level and planner case identifiers must agree", () => {
    const matchingRun = {
        file_id: "case-a",
        patient_id: "patient-1",
        planner_input: {
            file_id: "case-a",
            patient_id: "patient-1",
        },
    };
    const wrongPlannerFile = {
        ...matchingRun,
        planner_input: {
            ...matchingRun.planner_input,
            file_id: "case-b",
        },
    };
    const wrongPatient = {
        ...matchingRun,
        planner_input: {
            ...matchingRun.planner_input,
            patient_id: "patient-2",
        },
    };

    assert.equal(agentRunMatchesCase(matchingRun, "case-a", "patient-1"), true);
    assert.equal(agentRunMatchesCase(wrongPlannerFile, "case-a", "patient-1"), false);
    assert.equal(agentRunMatchesCase(wrongPatient, "case-a", "patient-1"), false);
    assert.equal(agentRunMatchesCase({}, "case-a", "patient-1"), false);
});

test("Agent Run is validated before it can affect the Viewer case", async () => {
    const originalFetch = global.fetch;
    global.fetch = async () => ({
        ok: true,
        json: async () => ({
            success: true,
            run: {
                file_id: "case-a",
                patient_id: "patient-1",
                planner_input: { file_id: "case-a", patient_id: "patient-1" },
            },
        }),
    });

    try {
        assert.equal(await validateAgentRunForCase("run-1", "case-a", "patient-1"), true);
        assert.equal(await validateAgentRunForCase("run-1", "case-b", "patient-1"), false);
    } finally {
        if (originalFetch) global.fetch = originalFetch;
        else delete global.fetch;
    }
});

test("Viewer rejects completed labels without real prediction evidence", () => {
    const corrupted = normalizeViewerVesselOcclusionResult({
        status: "completed",
        vessel_occlusion_class_result: "大血管闭塞",
        confidence: 0.99,
        valid_predictions: 0,
        class_counts: {
            Class_0: 0,
            Class_1_LVO: 0,
            Class_2_MEVO: 0,
        },
    });
    const valid = normalizeViewerVesselOcclusionResult({
        status: "completed",
        vessel_occlusion_class_result: "大血管闭塞",
        predicted_class: "Class_1_LVO",
        confidence: 0.81,
    });

    assert.equal(corrupted.status, "failed");
    assert.equal(corrupted.label, "未获得模型结果");
    assert.equal(corrupted.confidence, null);
    assert.equal(valid.status, "completed");
    assert.equal(valid.label, "大血管闭塞");
    assert.equal(valid.confidence, 0.81);
});

test("stroke analysis panel opens and closes", () => {
    const classes = new Set();
    const panel = {
        classList: {
            toggle(name) {
                if (classes.has(name)) classes.delete(name);
                else classes.add(name);
            },
        },
    };
    global.document = {
        getElementById: (id) => id === "analysisPanel" ? panel : null,
    };

    try {
        toggleAnalysisPanel();
        assert.equal(classes.has("open"), true);
        toggleAnalysisPanel();
        assert.equal(classes.has("open"), false);
    } finally {
        delete global.document;
    }
});
