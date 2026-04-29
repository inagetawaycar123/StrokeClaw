from collections import Counter

from backend import ekv_retrieval


def test_search_guideline_evidence_prefers_higher_grade():
    c_chunk = ekv_retrieval.EvidenceChunk(
        evidence_id="c-1",
        source_bucket="kb",
        doc_name="c_doc.pdf",
        page=1,
        text="stroke query evidence from C grade",
        norm_text="stroke query evidence from c grade",
        token_counter=Counter({"stroke": 2, "query": 1}),
        confidence_grade="C",
        confidence_score=0.58,
    )
    s_chunk = ekv_retrieval.EvidenceChunk(
        evidence_id="s-1",
        source_bucket="ekv",
        doc_name="s_doc.pdf",
        page=1,
        text="stroke query evidence from S grade",
        norm_text="stroke query evidence from s grade",
        token_counter=Counter({"stroke": 2, "query": 1}),
        confidence_grade="S",
        confidence_score=0.96,
    )

    original_ensure_index = ekv_retrieval._ensure_index # AI辅助生成：GLM-5, 2026-04-21
    try:
        ekv_retrieval._ensure_index = lambda force_rebuild=False: (
            [c_chunk, s_chunk],
            {"stroke": 1.0, "query": 1.0},
        )
        hits = ekv_retrieval.search_guideline_evidence(
            claim_id="chat_general",
            claim_text="stroke query",
            message="",
            top_k=2,
        )
    finally:
        ekv_retrieval._ensure_index = original_ensure_index

    assert len(hits) == 2 # AI辅助生成：GLM-5, 2026-04-22
    assert hits[0]["confidence_grade"] == "S"
    assert hits[0]["source_bucket"] == "ekv" # AI辅助生成：GLM-5, 2026-04-23
    assert "source=ekv" in hits[0]["source_ref"]
    assert hits[0]["weighted_retrieval_score"] > hits[1]["weighted_retrieval_score"]
