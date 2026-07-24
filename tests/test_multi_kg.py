import pytest

from backend.kg_context import build_run_context
from backend.kg_query_router import route_query
from backend.kg_store import get_node_detail, graph_for_types, list_graphs, load_bundle
from backend.knowledge_graph_lookup import knowledge_graph_lookup


def _context(**overrides):
    base = {
        "modalities": [],
        "task_keys": [],
        "result_terms": [],
        "negative_result_terms": [],
        "uncertain_result_terms": [],
        "risk_terms": [],
    }
    base.update(overrides)
    return base


def test_multi_kg_catalog_has_ten_sections_and_disabled_case_experience():
    payload = list_graphs()
    assert payload["count"] == 10
    graph_by_type = {item["kg_type"]: item for item in payload["graphs"]}
    assert sum(1 for item in payload["graphs"] if item["enabled"]) == 9
    assert graph_by_type["case_experience"]["enabled"] is False
    assert graph_by_type["case_experience"]["status"] == "planned"
    for kg_type, graph in graph_by_type.items():
        if kg_type != "case_experience":
            assert graph["node_count"] >= 5


def test_multi_kg_nodes_edges_and_sources_have_referential_integrity():
    bundle = load_bundle(force_reload=True)
    node_ids = {node["id"] for node in bundle["nodes"]}
    source_ids = {source["source_id"] for source in bundle["sources"]}
    assert len(node_ids) == len(bundle["nodes"])
    for node in bundle["nodes"]:
        assert node["source_ids"]
        assert set(node["source_ids"]) <= source_ids
    for edge in bundle["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
        assert set(edge.get("source_ids") or []) <= source_ids


def test_medical_rules_are_source_backed_and_review_marked():
    bundle = load_bundle()
    clinical_types = {
        "guideline",
        "imaging_sign",
        "vessel_anatomy",
        "perfusion",
        "risk_contraindication",
        "consistency_check",
    }
    clinical_nodes = [
        node for node in bundle["nodes"] if node["kg_type"] in clinical_types
    ]
    assert clinical_nodes
    assert all(node["source_ids"] for node in clinical_nodes)
    assert all(node["review_status"] == "review_required" for node in clinical_nodes)


def test_vessel_question_routes_to_vessel_guideline_and_model_sections():
    result = route_query(
        "为什么提示大血管闭塞，需要取栓评估吗？",
        _context(
            modalities=["ncct", "mcta"],
            task_keys=["vessel_occlusion_classification"],
            result_terms=["大血管"],
        ),
    )
    assert {"vessel_anatomy", "guideline", "model_explanation"} <= set(
        result["kg_types"]
    )


def test_ncct_task_without_question_still_routes_by_context():
    result = route_query(
        "",
        _context(
            modalities=["ncct"],
            task_keys=["ncct_classification"],
            result_terms=["脑出血"],
            risk_terms=["high"],
        ),
    )
    assert result["matched"] is True
    assert "imaging_sign" in result["kg_types"]
    assert "risk_contraindication" in result["kg_types"]


def test_perfusion_question_returns_related_subgraph_and_evidence():
    result = knowledge_graph_lookup(
        "半暗带和 mismatch 代表什么？",
        _context(
            modalities=["cbf", "cbv", "tmax"],
            task_keys=["stroke_analysis"],
            result_terms=["penumbra", "mismatch"],
        ),
        depth=1,
    )
    assert result["kg_types"][0] == "perfusion"
    assert result["matched_nodes"]
    assert result["subgraph"]["nodes"]
    assert result["evidence_refs"]
    assert result["display_plan"]["review_required"] is True


def test_report_question_routes_to_report_evidence():
    result = route_query(
        "报告结论为什么这么写，证据和引用在哪里？",
        _context(task_keys=["report_generation", "ekv"]),
    )
    assert result["kg_types"][0] == "report_evidence"
    assert "guideline" in result["kg_types"]


def test_model_confidence_question_routes_to_model_explanation():
    result = route_query(
        "血管三分类模型的置信度为什么比较低？",
        _context(task_keys=["vessel_occlusion_classification"]),
    )
    assert result["kg_types"][0] == "model_explanation"


def test_unknown_query_has_no_structured_route():
    result = route_query("完全无关的问题 xyzzy", _context())
    assert result["matched"] is False
    assert result["routes"] == []


def test_graph_projection_and_node_detail_include_sources():
    graph = graph_for_types(["guideline"])
    assert graph["view"] == "multi"
    assert graph["kg_types"] == ["guideline"]
    assert len(graph["nodes"]) >= 5
    detail = get_node_detail("guideline_evt_selection")
    assert detail is not None
    assert detail["node"]["kg_type"] == "guideline"
    assert detail["evidence_refs"]


def test_unknown_graph_type_is_rejected():
    with pytest.raises(KeyError):
        graph_for_types(["not_a_real_graph"])


def test_actual_agent_task_names_are_canonicalized_for_routing():
    context = build_run_context(
        {
            "run_id": "run-1",
            "planner_input": {"available_modalities": ["ncct", "mcta"]},
            "steps": [
                {"key": "detect_modalities"},
                {"key": "load_patient_context"},
                {"key": "vessel_occlusion"},
                {"key": "run_stroke_analysis"},
                {"key": "generate_medgemma_report"},
            ],
        },
        [],
    )
    assert "modality_detection" in context["task_keys"]
    assert "case_intake_parse" in context["task_keys"]
    assert "image_quality_control" in context["task_keys"]
    assert "vessel_occlusion_classification" in context["task_keys"]
    assert "stroke_analysis" in context["task_keys"]
    assert "report_generation" in context["task_keys"]


def test_negated_hemorrhage_is_not_treated_as_positive_risk_signal():
    context = build_run_context(
        {
            "planner_input": {"available_modalities": ["ncct"]},
            "result": {"report": {"summary": "NCCT 未见明显脑出血征象。"}},
        },
        [],
    )
    assert "hemorrhage" not in context["result_terms"]
    assert "脑出血" not in context["result_terms"]
    assert "hemorrhage" in context["negative_result_terms"]
    result = route_query("", context)
    assert "risk_contraindication" not in result["kg_types"]


def test_negated_hemorrhage_question_does_not_route_to_bleeding_risk():
    context = build_run_context(
        {},
        [],
        question="报告显示未见脑出血，需要注意什么？",
    )
    assert "hemorrhage" in context["negative_result_terms"]
    assert "hemorrhage" not in context["result_terms"]
    result = route_query("报告显示未见脑出血，需要注意什么？", context)
    assert "risk_contraindication" not in result["kg_types"]


def test_negated_hemorrhage_filters_the_bleeding_risk_node():
    result = knowledge_graph_lookup(
        "复核当前冲突",
        _context(
            task_keys=["ekv"],
            negative_result_terms=["hemorrhage", "脑出血"],
            risk_terms=["conflict"],
        ),
        depth=1,
    )
    assert "risk_contraindication" in result["kg_types"]
    assert all(
        item.get("id") != "risk_intracranial_hemorrhage"
        for item in result["matched_nodes"]
    )


def test_diagnostic_question_is_uncertain_not_a_positive_finding():
    context = build_run_context({}, [], question="是否有脑出血？")
    assert "hemorrhage" in context["uncertain_result_terms"]
    assert "hemorrhage" not in context["result_terms"]


def test_positive_hemorrhage_routes_to_imaging_and_risk_sections():
    context = build_run_context(
        {
            "planner_input": {"available_modalities": ["ncct"]},
            "result": {"report": {"summary": "NCCT 发现脑出血征象。"}},
        },
        [],
    )
    assert "hemorrhage" in context["result_terms"]
    result = route_query("", context)
    assert "imaging_sign" in result["kg_types"]
    assert "risk_contraindication" in result["kg_types"]


def test_weighted_lexical_node_ranking_returns_explainable_matches():
    result = knowledge_graph_lookup(
        "机械取栓需要评估哪些条件？",
        _context(
            modalities=["ncct", "mcta"],
            task_keys=["vessel_occlusion_classification"],
            result_terms=["lvo"],
        ),
        depth=1,
    )
    assert result["matched_nodes"]
    assert any(
        item["id"] == "guideline_evt_selection"
        for item in result["matched_nodes"]
    )
    assert any(item.get("matched_tokens") for item in result["matched_nodes"])
