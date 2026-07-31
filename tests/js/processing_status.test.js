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
        dagReview: {
            approved: false,
            reviewer: "",
            approvedAt: "",
            fingerprint: "",
            hydratedKey: "",
            error: "",
        },
        review: {
            required: false,
            visible: false,
            loading: false,
            saving: false,
            offlineMode: false,
            error: "",
            info: "",
            state: null,
            currentSectionId: "",
            rewriteSuggestion: null,
            pendingOps: [],
            flushInFlight: false,
            inited: false,
            serverCanEnterViewer: false,
            runStatus: "",
        },
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

test("clinical DAG builder covers all four supported imaging paths with stable ids", () => {
    const cases = [
        [["ncct"], "ncct_only", 5],
        [["ncct", "mcta"], "ncct_single_phase_cta", 6],
        [["ncct", "mcta", "vcta", "dcta"], "ncct_mcta", 9],
        [["ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax"], "ncct_mcta_ctp", 9],
    ];
    cases.forEach(([modalities, path, nodeCount]) => {
        const first = processing.buildClinicalDag(modalities);
        const reversed = processing.buildClinicalDag([...modalities].reverse());
        assert.equal(first.path, path);
        assert.equal(first.dagId, reversed.dagId);
        assert.equal(first.valid, true);
        assert.equal(first.nodes.length, nodeCount);
        assert.equal(
            processing.clinicalDagStructureKey(first),
            processing.clinicalDagStructureKey(reversed),
        );
    });
});

test("clinical DAG uses the server descriptor and keeps collateral capability inactive", () => {
    const serverDag = {
        dag_id: "clinical:server-owned",
        path: "ncct_mcta",
        valid: true,
        available_modalities: ["ncct", "mcta", "vcta", "dcta"],
        nodes: [{ id: "collateral_score", status: "inactive", active: false }],
        edges: [],
        columns: [["collateral_score"]],
    };
    processing.state.latestJob = {
        status: "awaiting_review",
        modalities: ["ncct"],
        clinical_dag: serverDag,
    };

    const resolved = processing.clinicalDagForJob();
    assert.equal(resolved, serverDag);
    assert.equal(resolved.nodes[0].status, "inactive");
    assert.equal(processing.normStatus("awaiting_review"), "waiting");
    assert.equal(processing.normStatus("review_rejected"), "issue");
});

test("three-phase mCTA preserves the dev_zhao nine-node visual DAG", () => {
    const dag = processing.buildClinicalDag(["ncct", "mcta", "vcta", "dcta"]);
    const nodes = new Map(dag.nodes.map((node) => [node.id, node]));

    assert.deepEqual(
        dag.nodes.map((node) => node.title),
        [
            "影像质控",
            "出血 / 缺血排查",
            "血管闭塞识别",
            "类 CTP 生成",
            "侧支循环评估",
            "卒中定量分析",
            "内部一致性校验",
            "外部指南一致性校验",
            "结构化报告生成",
        ],
    );
    assert.equal(nodes.get("collateral_score").riskLevel, "medium");
    assert.ok(
        dag.edges.some(
            (edge) => edge.from === "pseudo_ctp" && edge.to === "stroke_analysis",
        ),
    );
});

test("uploaded CTP replaces pseudo-CTP while retaining the exact review layout", () => {
    const dag = processing.buildClinicalDag([
        "ncct", "mcta", "vcta", "dcta", "cbf", "cbv", "tmax",
    ]);
    const ids = dag.nodes.map((node) => node.id);

    assert.equal(dag.path, "ncct_mcta_ctp");
    assert.ok(ids.includes("ctp_review"));
    assert.ok(!ids.includes("pseudo_ctp"));
});

test("collateral execution metadata remains planned and cannot masquerade as runtime output", () => {
    const dag = processing.buildClinicalDag(["ncct", "mcta", "vcta", "dcta"]);
    const rows = processing.systemExecutionRows(dag);
    const collateral = rows
        .flatMap((row) => row.invocations)
        .find((item) => item.toolName === "collateral_score");

    assert.ok(collateral);
    assert.equal(collateral.capabilityStatus, "planned");
    assert.equal(collateral.status, "pending");
});

test("approved execution cards retain Agent and Skill metadata in the sequential feed", () => {
    const dag = processing.buildClinicalDag(["ncct", "mcta", "vcta", "dcta"]);
    const nodes = [
        {
            id: "upload_image_quality_control",
            key: "image_quality_control",
            subtitle: "图像质量控制",
            detailInput: { available_modalities: ["ncct", "mcta", "vcta", "dcta"] },
            meta: [],
        },
    ];

    const [decorated] = processing.decorateExecutionNodes(dag, nodes);

    assert.equal(decorated.subtitle, "影像质控 · Imaging Quality Agent");
    assert.equal(decorated.detailInput.assigned_agent, "Imaging Quality Agent");
    assert.equal(decorated.detailInput.called_skill_id, "SKILL_IMG_QC");
    assert.equal(decorated.detailInput.skill_name, "image_quality_control");
    assert.ok(decorated.meta.includes("assigned_agent · Imaging Quality Agent"));
});

test("quality control appears between case context and modality detection", () => {
    processing.state.latestJob = {
        status: "paused_review_required",
        modalities: ["ncct"],
        quality_control_result: {
            qc_status: "failed",
            qc_method: "rule_based_nifti_qc",
            findings: [{ code: "motion", severity: "high", message: "疑似严重运动伪影", overrideable: true }],
        },
        steps: [
            { key: "archive_ready", status: "completed" },
            { key: "image_quality_control", status: "waiting", message: "等待医生复核" },
            { key: "modality_detect", status: "pending" },
            { key: "three_class", status: "pending" },
        ],
    };
    processing.state.latestRun = null;
    processing.state.hints = {};
    const nodes = processing.buildNodes();
    assert.deepEqual(nodes.slice(0, 3).map((node) => node.key), [
        "archive_ready",
        "image_quality_control",
        "modality_detect",
    ]);
    assert.equal(nodes[1].status, "waiting");
    assert.equal(nodes[2].status, "pending");
    assert.deepEqual(nodes[1].riskItems, ["疑似严重运动伪影"]);
});

test("quality warning completes without hiding its risk findings", () => {
    processing.state.latestJob = {
        status: "running",
        modalities: ["ncct"],
        quality_control_result: {
            qc_status: "warning",
            qc_method: "rule_based_nifti_qc",
            qc_input_mode: "single_slice",
            qc_scan_coverage: "not_applicable",
            qc_motion_artifact_level: "not_applicable",
            qc_missing_slice_status: "not_applicable",
            qc_not_applicable_checks: ["axial_coverage", "internal_missing_slices", "inter_slice_motion"],
            findings: [{ code: "single_slice_limited_assessment", severity: "medium", message: "单层影像无法执行三维覆盖、疑似缺片及跨层运动评估", overrideable: true }],
        },
        steps: [
            { key: "archive_ready", status: "completed" },
            { key: "image_quality_control", status: "completed", message: "单层影像：三维质控项目不适用；可执行检查已完成，流程自动继续" },
            { key: "modality_detect", status: "running" },
        ],
    };
    const qualityNode = processing.buildNodes().find((node) => node.key === "image_quality_control");
    assert.equal(qualityNode.status, "completed");
    assert.equal(qualityNode.riskLevel, "medium");
    assert.deepEqual(qualityNode.riskItems, ["单层影像无法执行三维覆盖、疑似缺片及跨层运动评估"]);
    assert.match(qualityNode.fallback, /三维质控项目不适用/);
    assert.equal(qualityNode.detailResult.qc_input_mode, "single_slice");
});

test("NCCT running is the only visible execution node while later steps are pending", () => {
    processing.state.nodes = [
        { id: "three-class", key: "three_class", group: "upload", status: "running" },
        { id: "ctp", key: "ctp_generate", group: "upload", status: "pending" },
        { id: "vessel", key: "vessel_occlusion", group: "upload", status: "pending" },
    ];

    processing.syncRevealQueue();

    assert.deepEqual(processing.state.revealedNodeIds, ["three-class"]);
    assert.deepEqual(processing.state.revealPendingIds, ["ctp", "vessel"]);
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[0]).status,
        "running",
    );
});

test("NCCT completed and CTP running are displayed from the same backend poll", () => {
    processing.state.nodes = [
        { id: "three-class", key: "three_class", group: "upload", status: "completed" },
        { id: "ctp", key: "ctp_generate", group: "upload", status: "running" },
        { id: "vessel", key: "vessel_occlusion", group: "upload", status: "pending" },
    ];

    processing.syncRevealQueue();

    assert.deepEqual(processing.state.revealedNodeIds, ["three-class", "ctp"]);
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[0]).status,
        "completed",
    );
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[1]).status,
        "running",
    );
});

test("CTP completion does not reveal the next pending node", () => {
    processing.state.nodes = [
        { id: "three-class", key: "three_class", group: "upload", status: "completed" },
        { id: "ctp", key: "ctp_generate", group: "upload", status: "completed" },
        { id: "vessel", key: "vessel_occlusion", group: "upload", status: "pending" },
    ];

    processing.syncRevealQueue();

    assert.deepEqual(processing.state.revealedNodeIds, ["three-class", "ctp"]);
    assert.deepEqual(processing.state.revealPendingIds, ["vessel"]);
});

test("the next node is appended only after its backend status becomes running", () => {
    processing.state.nodes = [
        { id: "three-class", key: "three_class", group: "upload", status: "completed" },
        { id: "ctp", key: "ctp_generate", group: "upload", status: "completed" },
        { id: "vessel", key: "vessel_occlusion", group: "upload", status: "pending" },
    ];

    processing.syncRevealQueue();
    processing.state.nodes[2].status = "running";
    processing.syncRevealQueue();

    assert.deepEqual(
        processing.state.revealedNodeIds,
        ["three-class", "ctp", "vessel"],
    );
});

test("elapsed time cannot complete a running node or reveal a pending node", () => {
    const originalNow = Date.now;
    let now = 1000;
    Date.now = () => now;
    try {
        processing.state.nodes = [
            { id: "ctp", key: "ctp_generate", group: "upload", status: "running" },
            { id: "vessel", key: "vessel_occlusion", group: "upload", status: "pending" },
        ];

        processing.syncRevealQueue();
        now += 10 * 60 * 1000;
        processing.syncRevealQueue();

        assert.deepEqual(processing.state.revealedNodeIds, ["ctp"]);
        assert.equal(
            processing.withDisplayStatus(processing.state.nodes[0]).status,
            "running",
        );
    } finally {
        Date.now = originalNow;
    }
});

test("skipped and waiting states are visible while review blocks later nodes", () => {
    processing.state.nodes = [
        { id: "skipped-step", key: "archive_ready", group: "upload", status: "skipped" },
        { id: "review-step", key: "human_confirm", group: "agent", status: "waiting" },
        { id: "future-step", key: "stroke_analysis", group: "agent", status: "completed" },
    ];

    processing.syncRevealQueue();
    assert.deepEqual(processing.state.revealedNodeIds, ["skipped-step", "review-step"]);
    assert.equal(processing.nodeStatus("skipped"), "skipped");
    assert.equal(processing.canAdvanceRevealFrom(processing.state.nodes[1]), false);
});

test("pending human confirmation stays hidden until the backend reports waiting", () => {
    processing.state.nodes = [
        { id: "report", key: "ai_report", group: "agent", status: "completed" },
        { id: "human", key: "human_confirm", group: "agent", status: "pending" },
    ];

    processing.syncRevealQueue();
    assert.deepEqual(processing.state.revealedNodeIds, ["report"]);

    processing.state.nodes[1].status = "waiting";
    processing.syncRevealQueue();
    assert.deepEqual(processing.state.revealedNodeIds, ["report", "human"]);
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[1]).status,
        "waiting",
    );
});

test("human confirmation completion is driven only by the backend step status", () => {
    processing.state.nodes = [
        { id: "report", key: "ai_report", group: "agent", status: "completed" },
        { id: "human", key: "human_confirm", group: "agent", status: "waiting" },
    ];

    processing.syncRevealQueue();
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[1]).status,
        "waiting",
    );

    processing.state.nodes[1].status = "completed";
    processing.syncRevealQueue();
    assert.equal(
        processing.withDisplayStatus(processing.state.nodes[1]).status,
        "completed",
    );
});

test("viewer entry requires both confirmed sections and server authorization", () => {
    processing.state.review.required = true;
    processing.state.review.state = { all_confirmed: true };
    processing.state.review.serverCanEnterViewer = false;

    assert.equal(processing.reviewCanEnterViewer(), false);

    processing.reviewApplyServerPayload({
        all_confirmed: true,
        run_status: "succeeded",
        can_enter_viewer: true,
    });

    assert.equal(processing.reviewCanEnterViewer(), true);
    assert.equal(processing.state.latestRun.status, "succeeded");
});

test("offline confirmation cannot authorize viewer entry", () => {
    processing.state.review.required = true;
    processing.state.review.state = { all_confirmed: true };

    processing.reviewApplyServerPayload({
        all_confirmed: true,
        run_status: "paused_review_required",
        can_enter_viewer: false,
    });

    assert.equal(processing.reviewCanEnterViewer(), false);
});

test("review editor snapshot restores unsaved values, focus, and selection", () => {
    const originalDocument = global.document;
    const originalElements = {
        runtimeReviewDraft: {
            value: "unsaved draft",
            focus() {},
            setSelectionRange() {},
        },
        runtimeReviewNote: { value: "unsaved note" },
        runtimeReviewRewriteIntent: { value: "concise" },
    };
    let focused = false;
    let restoredRange = null;
    originalElements.runtimeReviewDraft.focus = () => { focused = true; };
    originalElements.runtimeReviewDraft.setSelectionRange = (start, end) => {
        restoredRange = [start, end];
    };
    global.document = {
        activeElement: {
            id: "runtimeReviewDraft",
            selectionStart: 2,
            selectionEnd: 7,
        },
        getElementById(id) {
            return originalElements[id] || null;
        },
    };

    try {
        const snapshot = processing.reviewCaptureEditorSnapshot();
        originalElements.runtimeReviewDraft.value = "server render";
        originalElements.runtimeReviewNote.value = "server note";
        processing.reviewRestoreEditorSnapshot(snapshot);

        assert.equal(originalElements.runtimeReviewDraft.value, "unsaved draft");
        assert.equal(originalElements.runtimeReviewNote.value, "unsaved note");
        assert.equal(focused, true);
        assert.deepEqual(restoredRange, [2, 7]);
    } finally {
        global.document = originalDocument;
    }
});

test("upload job completion cannot be overwritten by stale Agent running hints", () => {
    const resolved = processing.resolveUploadNodeState(
        { status: "completed", message: "CTP 灌注图生成完成" },
        { status: "running", message: "Tool running" },
        { status: "running", inputSummary: "正在调用旧 Agent" },
    );

    assert.equal(resolved.status, "completed");
    assert.equal(resolved.message, "CTP 灌注图生成完成");
    assert.equal(resolved.summaryHint, null);
});

test("backend CTP progress text remains authoritative while the node is running", () => {
    processing.state.latestJob = {
        status: "running",
        steps: [{
            key: "ctp_generate",
            status: "running",
            message: "正在生成 CTP 灌注图：CBV · 切片 2/4 · 41%",
        }],
    };
    processing.state.latestRun = {
        steps: [{
            key: "generate_ctp_maps",
            status: "completed",
            message: "stale completion",
        }],
    };
    processing.state.hints = {
        generate_ctp_maps: {
            status: "completed",
            resultSummary: "旧 Agent 已完成",
        },
    };

    const node = processing.buildNodes().find((item) => item.key === "ctp_generate");

    assert.equal(node.status, "running");
    assert.match(node.fallback, /CBV · 切片 2\/4 · 41%/);
    assert.match(node.summary.doing, /正在执行/);
    assert.doesNotMatch(node.summary.doing, /旧 Agent 已完成/);
});

test("completed NCCT card does not retain a stale executing conclusion", () => {
    processing.state.latestJob = {
        status: "running",
        result: {
            three_class_summary: {
                display: "正常 2 | 脑出血 0 | 脑缺血 1",
            },
        },
        steps: [{
            key: "three_class",
            status: "completed",
            message: "正常 2 | 脑出血 0 | 脑缺血 1",
        }],
    };

    const node = processing.buildNodes().find((item) => item.key === "three_class");

    assert.equal(node.status, "completed");
    assert.match(node.summary.doing, /已完成/);
    assert.doesNotMatch(node.summary.doing, /正在执行/);
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

test("missing CTA is a skipped non-applicable upload step", () => {
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
    assert.equal(node.status, "skipped");
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

test("persistUpload copies NCCT and vessel case-level contracts", () => {
    const vesselResult = completedVesselResult();
    const threeClassResult = {
        status: "completed",
        three_class_label: "normal",
        three_class_label_cn: "正常",
        three_class_confidence: 0.923,
    };
    const writes = {};
    let viewerData = null;
    global.setViewerData = (value) => { viewerData = value; };
    global.sessionStorage = { setItem: (key, value) => { writes[`session:${key}`] = value; }, removeItem: () => {} };
    global.localStorage = { setItem: (key, value) => { writes[`local:${key}`] = value; }, removeItem: () => {} };
    processing.state.latestJob = {
        status: "completed",
        result: {
            file_id: "case-1",
            three_class_result: threeClassResult,
            vessel_occlusion_result: vesselResult,
        },
    };

    processing.persistUpload(processing.state.latestJob);

    assert.equal(viewerData.file_id, "case-1");
    assert.deepEqual(viewerData.three_class_result, threeClassResult);
    assert.equal(viewerData.three_class_status, "completed");
    assert.equal(viewerData.three_class_label, "normal");
    assert.equal(viewerData.three_class_label_cn, "正常");
    assert.equal(viewerData.three_class_confidence, 0.923);
    assert.deepEqual(viewerData.vessel_occlusion_result, processing.normalizeVesselOcclusionResult(vesselResult));
    assert.equal(viewerData.vessel_occlusion_status, "completed");
    assert.equal(viewerData.vessel_occlusion_class_result, "大血管闭塞");
    assert.equal(viewerData.vessel_occlusion_confidence, 0.875);
    assert.equal(viewerData.predicted_class, "Class_1_LVO");
    assert.deepEqual(viewerData.class_counts, vesselResult.class_counts);
    assert.equal(writes["session:current_file_id"], "case-1");
    assert.equal(writes["local:current_file_id"], "case-1");

});
