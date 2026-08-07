"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
    normalizeMrsPrognosisResult,
    extractRunMrsPrognosisResult,
    formatProbability,
    confidenceTone,
} = require("../../static/js/mrs_prognosis.js");

function completedMrs(overrides = {}) {
    const poor = overrides.poor ?? 0.316;
    const predictedClass = poor >= 0.55 ? 1 : 0;
    return {
        status: "completed",
        result_mode: overrides.mode || "baseline",
        display_mode: overrides.mode === "update_24h" ? "24小时更新评估" : "首诊初步评估",
        prediction: {
            good_prognosis_probability: 1 - poor,
            poor_prognosis_risk: poor,
            predicted_class: predictedClass,
            class_name: predictedClass ? "mRS 3-6 / 不良预后" : "mRS 0-2 / 良好预后",
            decision_threshold: 0.55,
            probability_calibrated: true,
        },
        confidence: {
            level: overrides.confidence || "medium",
            ensemble_std: 0.03,
            threshold_margin: Math.abs(poor - 0.55),
            reasons: ["research model"],
        },
        key_evidence: {
            clinical: [
                { display_name: "入院 NIHSS", value: 9, direction: "increase_poor_prognosis_risk" },
            ],
            imaging: [
                { source_file: "private.nii", attention_score: 0.72, interpretation: "模型关注区域" },
            ],
        },
        data_quality: { missing_clinical_fields: [], image_quality_warnings: [] },
        doctor_review_recommendation: { items: ["请复核"] },
        model: { model_version: "mrs-v1", external_validation_completed: false, production_approved: false },
        fallback_used: false,
    };
}

test("normalizer exposes only two outcome groups and one-decimal probabilities", () => {
    const good = normalizeMrsPrognosisResult(completedMrs());
    const poor = normalizeMrsPrognosisResult(completedMrs({ poor: 0.684 }));

    assert.equal(good.available, true);
    assert.equal(good.prediction.classLabel, "良好预后");
    assert.equal(good.prediction.classRange, "mRS 0-2");
    assert.equal(poor.prediction.classLabel, "不良预后");
    assert.equal(poor.prediction.classRange, "mRS 3-6");
    assert.equal(formatProbability(0.684), "68.4%");
});

test("probability, complement and class validation never fabricate zero", () => {
    const invalidRange = completedMrs();
    invalidRange.prediction.good_prognosis_probability = 1.2;
    const invalidSum = completedMrs();
    invalidSum.prediction.good_prognosis_probability = 0.4;
    const invalidClass = completedMrs();
    invalidClass.prediction.predicted_class = 1;

    for (const raw of [invalidRange, invalidSum, invalidClass, { status: "failed" }]) {
        const normalized = normalizeMrsPrognosisResult(raw);
        assert.equal(normalized.available, false);
        assert.equal(normalized.prediction, null);
        assert.notEqual(formatProbability(null), "0.0%");
    }
});

test("current run result outranks report payload and tool result fallback is supported", () => {
    const current = completedMrs({ poor: 0.684 });
    const stale = completedMrs({ poor: 0.316 });
    assert.equal(
        extractRunMrsPrognosisResult({
            result: {
                mrs_prognosis_result: current,
                report_result: { report_payload: { mrs_prognosis_result: stale } },
            },
        }),
        current,
    );
    assert.deepEqual(
        extractRunMrsPrognosisResult({
            result: {
                report_result: { report_payload: { mrs_prognosis_result: stale } },
            },
            tool_results: [
                {
                    tool_name: "run_mrs_prognosis_prediction",
                    status: "completed",
                    structured_output: current,
                },
            ],
        }),
        current,
    );
});

test("baseline, update, confidence and fallback metadata remain distinct", () => {
    const normalized = normalizeMrsPrognosisResult({
        ...completedMrs({ mode: "update_24h", confidence: "low" }),
        fallback_used: true,
        fallback_reason: "update bundle unavailable",
    });

    assert.equal(normalized.displayMode, "24小时更新评估");
    assert.equal(normalized.confidence.level, "low");
    assert.equal(confidenceTone(normalized.confidence.level), "low");
    assert.equal(normalized.fallbackUsed, true);
});
