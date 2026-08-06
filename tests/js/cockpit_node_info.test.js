"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


class FakeElement {
    constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.className = "";
        this.textContent = "";
        this.innerHTML = "";
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    append(...children) {
        this.children.push(...children);
    }
}


function loadCockpitScript() {
    const scriptPath = path.resolve(__dirname, "../../static/js/cockpit.js");
    const source = fs.readFileSync(scriptPath, "utf8");
    const classList = { add() {}, remove() {} };
    const sandbox = {
        console,
        URL,
        URLSearchParams,
        setInterval,
        clearInterval,
        fetch: async () => {
            throw new Error("network access is not expected in this test");
        },
        localStorage: { getItem() { return null; }, setItem() {} },
        sessionStorage: { getItem() { return null; }, setItem() {} },
        document: {
            addEventListener() {},
            createElement(tagName) {
                return new FakeElement(tagName);
            },
            getElementById() {
                return null;
            },
            body: { classList },
        },
        window: {
            location: { pathname: "/cockpit", search: "", href: "" },
            history: { replaceState() {} },
            innerWidth: 1600,
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox, { filename: scriptPath });
    return sandbox;
}


test("confidence levels use the dev_yang_new thresholds", () => {
    const cockpit = loadCockpitScript();

    assert.equal(cockpit.confidenceLevel(0.85).className, "confidence-high");
    assert.equal(cockpit.confidenceLevel(84).className, "confidence-medium");
    assert.equal(cockpit.confidenceLevel(0.69).className, "confidence-low");
    assert.equal(cockpit.confidenceLevel("invalid").className, "confidence-unknown");
});


test("graph model merges event node_info over step metadata and retains tool result", () => {
    const cockpit = loadCockpitScript();
    const run = {
        planner_input: { available_modalities: ["ncct"] },
        planner_output: {
            imaging_path: "ncct_only",
            tool_sequence: ["ekv"],
        },
        steps: [
            {
                key: "ekv",
                status: "completed",
                node_info: {
                    agent_name: "Step Agent",
                    skill_id: "STEP_SKILL",
                    skill_name: "Step Skill",
                    confidence_score: 0.4,
                },
            },
        ],
        tool_results: [
            {
                tool_name: "ekv",
                status: "completed",
                attempt: 2,
                structured_output: { summary: "verified" },
            },
        ],
    };
    const events = [
        {
            event_seq: 1,
            tool_name: "ekv",
            status: "completed",
            node_info: {
                agent_name: "Evidence Agent",
                skill_id: "SKILL_EKV",
                skill_name: "Evidence Skill",
                confidence_score: 0.62,
                evidence_refs: ["E-1"],
                conflict_status: "conflict",
            },
        },
    ];

    const graph = cockpit.buildGraphModel(run, events);
    const node = graph.nodes.find((item) => item.step_key === "ekv");

    assert.ok(node);
    assert.equal(node.node_info.agent_name, "Evidence Agent");
    assert.equal(node.node_info.skill_id, "SKILL_EKV");
    assert.equal(node.confidence, 0.62);
    assert.deepEqual(Array.from(node.evidence_refs), ["E-1"]);
    assert.equal(node.tool_result.attempt, 2);
});


test("skill execution result prefers tool result fields and preserves false values", () => {
    const cockpit = loadCockpitScript();
    const result = cockpit.resolveSkillExecutionResult(
        {
            status: "completed",
            retryable_value: true,
            tool_result: {
                status: "completed",
                attempt: 2,
                version: "1.2.0",
                failure_strategy: "manual_review",
                retryable: false,
                error_code: "NONE",
                structured_output: { summary: "verified" },
            },
            engineering_payload: {
                output_ref: { status: "stale" },
            },
        },
        { output_summary: "fallback" },
    );

    assert.equal(result.skillStatus, "completed");
    assert.equal(result.attempt, 2);
    assert.equal(result.version, "1.2.0");
    assert.equal(result.failureStrategy, "manual_review");
    assert.equal(result.retryable, false);
    assert.equal(result.errorCode, "NONE");
    assert.equal(result.structuredOutput.summary, "verified");
});


test("evidence renderer supports structured records without HTML injection", () => {
    const cockpit = loadCockpitScript();
    const card = cockpit.renderEvidenceSource(
        {
            evidence_id: "E-1",
            title: "<script>alert(1)</script>",
            type: "guideline",
            source: "Synthetic source",
        },
        0,
    );

    assert.equal(card.className, "evidence-source-item");
    assert.equal(card.children[0].textContent, "Evidence 1:");
    const renderedText = card.children
        .slice(1)
        .flatMap((row) => row.children || [])
        .map((child) => child.textContent);
    assert.ok(renderedText.includes("<script>alert(1)</script>"));
    assert.equal(cockpit.escapeHtml("<script>"), "&lt;script&gt;");
});


test("cockpit template exposes all node detail fields", () => {
    const templatePath = path.resolve(
        __dirname,
        "../../backend/templates/patient/upload/cockpit/index.html",
    );
    const template = fs.readFileSync(templatePath, "utf8");
    [
        "drawerNodeAgentName",
        "drawerNodeSkillId",
        "drawerNodeSkillName",
        "drawerNodeConfidenceScore",
        "drawerNodeConflictStatus",
        "drawerNodeInputSummary",
        "drawerNodeOutputSummary",
        "drawerSkillResultStructuredOutput",
        "drawerNodeEvidence",
    ].forEach((id) => {
        assert.match(template, new RegExp(`id="${id}"`));
    });
});
