"""Versioned storage and projections for the multi-section stroke knowledge graph."""

import copy
import json
import os
import threading
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


MULTI_KG_VERSION = "stroke-multi-kg-v1"
DEFAULT_MULTI_KG_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    "runtime",
    "kg",
)
KG_FILES = {
    "manifest": "kg_manifest.json",
    "nodes": "kg_nodes.json",
    "edges": "kg_edges.json",
    "sources": "kg_sources.json",
    "bindings": "kg_task_bindings.json",
    "routes": "kg_query_routes.json",
}
MULTI_GRAPH_LANES = [
    {"column": 0, "label": "主题"},
    {"column": 1, "label": "检查与发现"},
    {"column": 2, "label": "判断依据"},
    {"column": 3, "label": "风险与校验"},
    {"column": 4, "label": "行动与解释"},
]

_CACHE_LOCK = threading.Lock()
_BUNDLE_CACHE: Dict[str, Any] = {"signature": None, "bundle": None}


class KnowledgeGraphDataError(ValueError):
    """Raised when the committed graph configuration is inconsistent."""


def get_multi_kg_dir() -> str:
    return os.environ.get("STROKE_MULTI_KG_DIR", DEFAULT_MULTI_KG_DIR)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise KnowledgeGraphDataError(f"{os.path.basename(path)} must contain a JSON object")
    return payload


def _bundle_signature(base_dir: str) -> tuple:
    values = []
    for key in sorted(KG_FILES):
        path = os.path.join(base_dir, KG_FILES[key])
        try:
            stat = os.stat(path)
            values.append((key, int(stat.st_mtime_ns), int(stat.st_size)))
        except OSError:
            values.append((key, 0, 0))
    return tuple(values)


def _rows(payload: Dict[str, Any], key: str, filename: str) -> List[Dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise KnowledgeGraphDataError(f"{filename}.{key} must be an array")
    return [dict(row) for row in rows if isinstance(row, dict)]


def _validate_bundle(bundle: Dict[str, Any]) -> None:
    graph_types = {
        str(row.get("kg_type") or "").strip()
        for row in bundle["graphs"]
        if str(row.get("kg_type") or "").strip()
    }
    if len(graph_types) != len(bundle["graphs"]):
        raise KnowledgeGraphDataError("kg_manifest.json contains missing or duplicate kg_type values")

    node_ids: Set[str] = set()
    source_ids = {
        str(row.get("source_id") or "").strip()
        for row in bundle["sources"]
        if str(row.get("source_id") or "").strip()
    }
    for node in bundle["nodes"]:
        node_id = str(node.get("id") or "").strip()
        kg_type = str(node.get("kg_type") or "").strip()
        if not node_id or node_id in node_ids:
            raise KnowledgeGraphDataError(f"missing or duplicate node id: {node_id!r}")
        if kg_type not in graph_types:
            raise KnowledgeGraphDataError(f"node {node_id} references unknown kg_type {kg_type!r}")
        missing_sources = [
            source_id
            for source_id in node.get("source_ids") or []
            if str(source_id) not in source_ids
        ]
        if missing_sources:
            raise KnowledgeGraphDataError(
                f"node {node_id} references unknown sources: {missing_sources}"
            )
        node_ids.add(node_id)

    edge_ids: Set[str] = set()
    for edge in bundle["edges"]:
        edge_id = str(edge.get("id") or "").strip()
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not edge_id or edge_id in edge_ids:
            raise KnowledgeGraphDataError(f"missing or duplicate edge id: {edge_id!r}")
        if source not in node_ids or target not in node_ids:
            raise KnowledgeGraphDataError(
                f"edge {edge_id} references unknown nodes: {source!r} -> {target!r}"
            )
        missing_sources = [
            source_id
            for source_id in edge.get("source_ids") or []
            if str(source_id) not in source_ids
        ]
        if missing_sources:
            raise KnowledgeGraphDataError(
                f"edge {edge_id} references unknown sources: {missing_sources}"
            )
        edge_ids.add(edge_id)


def load_bundle(force_reload: bool = False) -> Dict[str, Any]:
    base_dir = get_multi_kg_dir()
    signature = _bundle_signature(base_dir)
    with _CACHE_LOCK:
        if (
            not force_reload
            and _BUNDLE_CACHE.get("bundle") is not None
            and _BUNDLE_CACHE.get("signature") == signature
        ):
            return copy.deepcopy(_BUNDLE_CACHE["bundle"])

        payloads = {
            key: _read_json(os.path.join(base_dir, filename))
            for key, filename in KG_FILES.items()
        }
        manifest = payloads["manifest"]
        version = str(manifest.get("version") or MULTI_KG_VERSION)
        bundle = {
            "version": version,
            "graphs": _rows(manifest, "graphs", KG_FILES["manifest"]),
            "nodes": _rows(payloads["nodes"], "nodes", KG_FILES["nodes"]),
            "edges": _rows(payloads["edges"], "edges", KG_FILES["edges"]),
            "sources": _rows(payloads["sources"], "sources", KG_FILES["sources"]),
            "bindings": _rows(payloads["bindings"], "bindings", KG_FILES["bindings"]),
            "routes": _rows(payloads["routes"], "routes", KG_FILES["routes"]),
        }
        _validate_bundle(bundle)
        _BUNDLE_CACHE["signature"] = signature
        _BUNDLE_CACHE["bundle"] = copy.deepcopy(bundle)
        return bundle


def list_graphs(enabled: Optional[bool] = None) -> Dict[str, Any]:
    bundle = load_bundle()
    node_count: Dict[str, int] = defaultdict(int)
    edge_count: Dict[str, int] = defaultdict(int)
    for node in bundle["nodes"]:
        node_count[str(node.get("kg_type") or "")] += 1
    node_type_by_id = {
        str(node.get("id") or ""): str(node.get("kg_type") or "")
        for node in bundle["nodes"]
    }
    for edge in bundle["edges"]:
        edge_types = {
            node_type_by_id.get(str(edge.get("source") or "")),
            node_type_by_id.get(str(edge.get("target") or "")),
        }
        for kg_type in edge_types:
            if kg_type:
                edge_count[kg_type] += 1

    graphs = []
    for graph in sorted(bundle["graphs"], key=lambda row: int(row.get("order") or 0)):
        is_enabled = bool(graph.get("enabled"))
        if enabled is not None and is_enabled is not enabled:
            continue
        item = dict(graph)
        kg_type = str(item.get("kg_type") or "")
        item["node_count"] = node_count.get(kg_type, 0)
        item["edge_count"] = edge_count.get(kg_type, 0)
        graphs.append(item)
    return {"version": bundle["version"], "graphs": graphs, "count": len(graphs)}


def _normalize_types(bundle: Dict[str, Any], kg_types: Optional[Sequence[str]]) -> List[str]:
    graph_by_type = {
        str(row.get("kg_type") or ""): row
        for row in bundle["graphs"]
        if str(row.get("kg_type") or "")
    }
    if not kg_types:
        return [
            kg_type
            for kg_type, row in graph_by_type.items()
            if bool(row.get("enabled"))
        ]

    normalized = []
    for raw_type in kg_types:
        kg_type = str(raw_type or "").strip()
        if not kg_type:
            continue
        if kg_type not in graph_by_type:
            raise KeyError(kg_type)
        if kg_type not in normalized:
            normalized.append(kg_type)
    return normalized


def _expand_neighbors(
    edges: Sequence[Dict[str, Any]],
    seeds: Iterable[str],
    allowed_ids: Set[str],
    depth: int,
) -> Set[str]:
    selected = {str(seed) for seed in seeds if str(seed) in allowed_ids}
    if not selected:
        return set()
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in allowed_ids and target in allowed_ids:
            adjacency[source].add(target)
            adjacency[target].add(source)

    queue = deque((node_id, 0) for node_id in selected)
    while queue:
        node_id, distance = queue.popleft()
        if distance >= max(0, int(depth)):
            continue
        for neighbor in adjacency.get(node_id, set()):
            if neighbor in selected:
                continue
            selected.add(neighbor)
            queue.append((neighbor, distance + 1))
    return selected


def _source_evidence(source: Dict[str, Any], node_ids: Sequence[str]) -> Dict[str, Any]:
    source_ref = str(source.get("url") or source.get("local_path") or "")
    return {
        "evidence_id": source.get("source_id"),
        "source_id": source.get("source_id"),
        "source_ref": source_ref,
        "title": source.get("title"),
        "doc_name": source.get("title"),
        "organization": source.get("organization"),
        "publication_date": source.get("publication_date"),
        "version": source.get("version"),
        "url": source.get("url"),
        "local_path": source.get("local_path"),
        "section": source.get("section"),
        "snippet": source.get("summary"),
        "confidence_grade": source.get("evidence_grade") or "B",
        "confidence_score": float(source.get("confidence_score") or 0.72),
        "review_status": source.get("review_status") or "review_required",
        "node_ids": list(node_ids),
    }


def graph_for_types(
    kg_types: Optional[Sequence[str]] = None,
    seed_node_ids: Optional[Sequence[str]] = None,
    depth: int = 1,
) -> Dict[str, Any]:
    bundle = load_bundle()
    selected_types = _normalize_types(bundle, kg_types)
    selected_type_set = set(selected_types)
    graph_by_type = {
        str(row.get("kg_type") or ""): row for row in bundle["graphs"]
    }
    source_by_id = {
        str(row.get("source_id") or ""): row for row in bundle["sources"]
    }

    eligible_nodes = [
        dict(node)
        for node in bundle["nodes"]
        if str(node.get("kg_type") or "") in selected_type_set
    ]
    eligible_ids = {str(node.get("id") or "") for node in eligible_nodes}
    if seed_node_ids:
        selected_ids = _expand_neighbors(
            bundle["edges"],
            seed_node_ids,
            eligible_ids,
            depth=max(0, min(2, int(depth))),
        )
        if selected_ids:
            eligible_nodes = [
                node for node in eligible_nodes if str(node.get("id") or "") in selected_ids
            ]
            eligible_ids = selected_ids

    source_to_nodes: Dict[str, List[str]] = defaultdict(list)
    for node in eligible_nodes:
        kg_type = str(node.get("kg_type") or "")
        node["chapter_label"] = (graph_by_type.get(kg_type) or {}).get("label") or kg_type
        for source_id in node.get("source_ids") or []:
            source_to_nodes[str(source_id)].append(str(node.get("id") or ""))
        node["top_evidence"] = [
            _source_evidence(source_by_id[str(source_id)], [str(node.get("id") or "")])
            for source_id in node.get("source_ids") or []
            if str(source_id) in source_by_id
        ]
        node["evidence_count"] = len(node["top_evidence"])

    selected_edges = [
        dict(edge)
        for edge in bundle["edges"]
        if str(edge.get("source") or "") in eligible_ids
        and str(edge.get("target") or "") in eligible_ids
    ]
    for edge in selected_edges:
        for source_id in edge.get("source_ids") or []:
            source_to_nodes[str(source_id)].extend(
                [str(edge.get("source") or ""), str(edge.get("target") or "")]
            )

    evidence = [
        _source_evidence(source_by_id[source_id], sorted(set(node_ids)))
        for source_id, node_ids in source_to_nodes.items()
        if source_id in source_by_id
    ]
    evidence.sort(
        key=lambda item: (
            -float(item.get("confidence_score") or 0),
            str(item.get("publication_date") or ""),
        )
    )
    eligible_nodes.sort(
        key=lambda node: (
            selected_types.index(str(node.get("kg_type") or "")),
            int(node.get("column") or 0),
            int(node.get("order") or 0),
        )
    )
    return {
        "version": bundle["version"],
        "view": "multi",
        "kg_types": selected_types,
        "nodes": eligible_nodes,
        "edges": selected_edges,
        "evidence": evidence,
        "lanes": copy.deepcopy(MULTI_GRAPH_LANES),
        "stats": {
            "view": "multi",
            "chapter_count": len(selected_types),
            "subgraph_node_count": len(eligible_nodes),
            "subgraph_edge_count": len(selected_edges),
            "evidence_count": len(evidence),
            "seed_ids": [str(item) for item in seed_node_ids or []],
        },
    }


def get_node_detail(node_id: str) -> Optional[Dict[str, Any]]:
    bundle = load_bundle()
    target_id = str(node_id or "").strip()
    node = next(
        (dict(item) for item in bundle["nodes"] if str(item.get("id") or "") == target_id),
        None,
    )
    if not node:
        return None
    graph = graph_for_types([str(node.get("kg_type") or "")])
    edges = [
        edge
        for edge in graph["edges"]
        if str(edge.get("source") or "") == target_id
        or str(edge.get("target") or "") == target_id
    ]
    evidence = [
        item
        for item in graph["evidence"]
        if target_id in {str(value) for value in item.get("node_ids") or []}
    ]
    graph_meta = next(
        (
            dict(item)
            for item in bundle["graphs"]
            if str(item.get("kg_type") or "") == str(node.get("kg_type") or "")
        ),
        {},
    )
    return {
        "node": node,
        "edges": edges,
        "evidence_refs": evidence,
        "graph": graph_meta,
    }
