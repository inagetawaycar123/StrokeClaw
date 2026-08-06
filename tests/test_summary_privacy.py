import json

from backend.summary_assembler import (
    _build_llm_question_prompt,
    _build_question_answer,
    _parse_llm_answer_payload,
)


def test_baichuan_prompt_removes_direct_identifiers_and_precise_timestamps():
    from backend import ekv_retrieval

    context = {
        "patient_name": "张三",
        "patient_id": 909,
        "file_id": "file-secret-123",
        "run_id": "run-secret-456",
        "patient_age": 89,
        "patient_sex": "male",
        "admission_nihss": 9,
        "onset_to_admission_hours": 1.02,
        "core_infarct_volume": 6.14,
        "penumbra_volume": 17.21,
        "mismatch_ratio": 2.8,
    }
    original_search = ekv_retrieval.search_guideline_evidence_with_graph
    ekv_retrieval.search_guideline_evidence_with_graph = lambda **_kwargs: {
        "paths": []
    }
    try:
        prompt = _build_llm_question_prompt(
            question=(
                "请分析张三，patient_id=909，file-secret-123，run-secret-456，"
                "采集于2026-07-23T04:14:02.480Z。"
            ),
            key_points=["张三的患者ID 909需要复核"],
            allowed_claim_ids=["significant_mismatch"],
            patient_context=context,
            consensus_decision="review_required",
            next_actions=[],
            uncertainties=["run-secret-456尚未确认"],
        )
    finally:
        ekv_retrieval.search_guideline_evidence_with_graph = original_search

    assert "张三" not in prompt
    assert "file-secret-123" not in prompt
    assert "run-secret-456" not in prompt
    assert "2026-07-23T04:14:02.480Z" not in prompt
    assert "patient_id=909" not in prompt
    assert "核心梗死体积（Core）：6.14 ml" in prompt


def test_unknown_llm_claim_references_are_dropped():
    answer, claim_ids, limitations = _parse_llm_answer_payload(
        json.dumps(
            {
                "direct_answer": "请由医生综合判断。",
                "claim_ids": ["significant_mismatch", "invented_claim"],
                "limitations": ["血管结果缺失"],
            },
            ensure_ascii=False,
        ),
        ["significant_mismatch"],
    )

    assert answer == "请由医生综合判断。"
    assert claim_ids == ["significant_mismatch"]
    assert limitations == ["血管结果缺失"]


def test_no_explicit_question_does_not_call_llm():
    calls = []

    def callback(prompt):
        calls.append(prompt)
        return "{}"

    result, _ledger = _build_question_answer(
        goal_question="",
        key_findings=[
            {
                "finding_id": "f1",
                "claim_id": "significant_mismatch",
                "title": "灌注不匹配",
                "message": "规则满足",
                "verdict": "supported",
                "evidence_ids": [],
            }
        ],
        consensus={"decision": "accept"},
        next_actions=[],
        uncertainties=[],
        evidence_lookup={},
        traceability={},
        base_confidence=0.8,
        patient_context={"mismatch_ratio": 2.8},
        llm_callback=callback,
    )

    assert calls == []
    assert result["llm_enhanced"] is False
