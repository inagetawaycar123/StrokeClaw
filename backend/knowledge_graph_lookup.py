"""Context-aware multi-section knowledge graph lookup service."""

from typing import Any, Dict

try:
    from .kg_query_router import match_nodes, route_query
    from .kg_store import graph_for_types
except ImportError:
    from kg_query_router import match_nodes, route_query
    from kg_store import graph_for_types


def _fallback_pdf_evidence(question: str, depth: int) -> Dict[str, Any]:
    query = str(question or "").strip()
    if not query:
        return {
            "used": True,
            "reason": "no_structured_route",
            "message": "未命中结构化图谱，且没有可用于文档检索的问题。",
            "hits": [],
        }
    try:
        try:
            from .ekv_retrieval import search_guideline_evidence_with_graph
        except ImportError:
            from ekv_retrieval import search_guideline_evidence_with_graph
        result = search_guideline_evidence_with_graph(
            claim_id="multi_kg_fallback",
            claim_text=query,
            message=query,
            top_k=5,
            graph_depth=depth,
        )
        return {
            "used": True,
            "reason": "no_structured_route",
            "message": "未命中结构化图谱，已降级到本地指南文档检索。",
            "hits": result.get("hits") or [],
            "legacy_graph": result.get("graph") or {},
            "paths": result.get("paths") or [],
        }
    except Exception as exc:
        return {
            "used": True,
            "reason": "fallback_unavailable",
            "message": "结构化图谱和本地文档证据均暂不可用，请医生复核。",
            "hits": [],
            "error": str(exc),
        }


def knowledge_graph_lookup(
    question: str,
    context: Dict[str, Any],
    depth: int = 1,
) -> Dict[str, Any]:
    safe_depth = max(0, min(2, int(depth)))
    routed = route_query(question, context)
    if not routed.get("matched"):
        fallback = _fallback_pdf_evidence(question, safe_depth)
        legacy_graph = fallback.get("legacy_graph")
        return {
            "routes": [],
            "kg_types": [],
            "matched_nodes": [],
            "subgraph": legacy_graph
            if isinstance(legacy_graph, dict)
            else {
                "version": "stroke-multi-kg-v1",
                "view": "multi",
                "nodes": [],
                "edges": [],
                "evidence": fallback.get("hits") or [],
                "stats": {"subgraph_node_count": 0, "subgraph_edge_count": 0},
            },
            "evidence_refs": fallback.get("hits") or [],
            "confidence": 0.0,
            "display_plan": {
                "mode": "fallback",
                "default_view": "related",
                "review_required": True,
            },
            "fallback": fallback,
        }

    kg_types = routed.get("kg_types") or []
    matched_nodes = match_nodes(question, context, kg_types)
    seed_ids = [str(item.get("id") or "") for item in matched_nodes if item.get("id")]
    subgraph = graph_for_types(
        kg_types=kg_types,
        seed_node_ids=seed_ids,
        depth=safe_depth,
    )
    evidence_refs = subgraph.get("evidence") or []
    confidence = float(routed.get("confidence") or 0.0)
    review_required = any(
        str(node.get("review_status") or "") != "approved"
        for node in subgraph.get("nodes") or []
    )
    no_evidence = not bool(evidence_refs)
    return {
        "routes": routed.get("routes") or [],
        "kg_types": kg_types,
        "matched_nodes": matched_nodes,
        "subgraph": subgraph,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "display_plan": {
            "mode": "structured",
            "default_view": "related",
            "highlight_node_ids": seed_ids,
            "review_required": review_required,
            "evidence_status": "missing" if no_evidence else "available",
            "confidence_level": "low" if confidence < 0.35 else "medium" if confidence < 0.7 else "high",
        },
        "fallback": {
            "used": False,
            "reason": "",
            "message": (
                "相关知识节点缺少来源，请医生复核。"
                if no_evidence
                else "结构化图谱已命中。"
            ),
        },
    }
