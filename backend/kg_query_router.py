"""Deterministic routing from a doctor question and run context to KG sections."""

import re
import unicodedata
from collections import defaultdict
from math import log
from typing import Any, Dict, Iterable, List, Sequence, Tuple

try:
    from .kg_store import load_bundle
except ImportError:
    from kg_store import load_bundle


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"\s+", " ", text).strip()


def _normalized_values(values: Iterable[Any]) -> List[str]:
    output = []
    for value in values or []:
        normalized = _normalize_text(value)
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    if re.fullmatch(r"[a-z0-9_.+-]+", normalized_term):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])",
                text,
            )
        )
    return normalized_term in text


def _context_values(context: Dict[str, Any], key: str) -> List[str]:
    raw = context.get(key)
    if isinstance(raw, (list, tuple, set)):
        return _normalized_values(raw)
    if raw in (None, ""):
        return []
    return _normalized_values([raw])


_NEGATED_KEYWORD_GROUPS = (
    (
        {"hemorrhage", "brain hemorrhage", "intracranial hemorrhage", "脑出血"},
        {
            "hemorrhage",
            "brain hemorrhage",
            "intracranial hemorrhage",
            "脑出血",
            "颅内出血",
            "出血",
        },
    ),
)


def _keyword_is_negated(
    keyword: Any,
    positive_terms: set,
    negative_terms: set,
) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return False
    for signal_terms, guarded_keywords in _NEGATED_KEYWORD_GROUPS:
        if not (negative_terms & signal_terms) or positive_terms & signal_terms:
            continue
        if normalized_keyword in guarded_keywords:
            return True
    return False


def _lexical_tokens(value: Any) -> set:
    text = _normalize_text(value)
    tokens = set(re.findall(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*", text))
    for segment in re.findall(r"[\u3400-\u9fff]+", text):
        if len(segment) <= 4:
            tokens.add(segment)
        for size in (2, 3, 4):
            if len(segment) < size:
                continue
            tokens.update(
                segment[index : index + size]
                for index in range(len(segment) - size + 1)
            )
    return {token for token in tokens if token}


def _node_lexical_tokens(node: Dict[str, Any]) -> set:
    values = [
        node.get("label"),
        node.get("label_en"),
        *(node.get("aliases") or []),
        *(node.get("keywords") or []),
        node.get("description"),
        node.get("clinical_meaning"),
    ]
    tokens = set()
    for value in values:
        tokens.update(_lexical_tokens(value))
    return tokens


def _risk_node_is_negated(
    node: Dict[str, Any],
    positive_terms: set,
    negative_terms: set,
) -> bool:
    if str(node.get("kg_type") or "") != "risk_contraindication":
        return False
    values = [
        node.get("label"),
        node.get("label_en"),
        *(node.get("aliases") or []),
        *(node.get("keywords") or []),
    ]
    return any(
        _keyword_is_negated(value, positive_terms, negative_terms)
        for value in values
    )


def _binding_match(binding: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str]:
    binding_type = str(binding.get("binding_type") or "").strip().lower()
    value = _normalize_text(binding.get("value"))
    if not binding_type or not value:
        return False, ""
    context_key = {
        "modality": "modalities",
        "task": "task_keys",
        "dag_node": "task_keys",
        "result": "result_terms",
        "risk": "risk_terms",
    }.get(binding_type)
    if not context_key:
        return False, ""
    values = _context_values(context, context_key)
    if binding_type in {"result", "risk"}:
        matched = any(_contains_term(item, value) for item in values)
    else:
        matched = value in values
    return matched, f"{binding_type}:{value}" if matched else ""


def route_query(question: str, context: Dict[str, Any]) -> Dict[str, Any]:
    bundle = load_bundle()
    question_text = _normalize_text(question)
    result_text = " ".join(_context_values(context, "result_terms"))
    risk_text = " ".join(_context_values(context, "risk_terms"))
    searchable_text = " ".join(value for value in (question_text, result_text, risk_text) if value)
    task_keys = set(_context_values(context, "task_keys"))
    modalities = set(_context_values(context, "modalities"))
    positive_terms = set(_context_values(context, "result_terms"))
    negative_terms = set(_context_values(context, "negative_result_terms"))

    graph_by_type = {
        str(graph.get("kg_type") or ""): graph
        for graph in bundle["graphs"]
        if graph.get("enabled")
    }
    scores: Dict[str, float] = defaultdict(float)
    reasons: Dict[str, List[str]] = defaultdict(list)

    for route in bundle["routes"]:
        route_types = [
            str(item)
            for item in route.get("kg_types") or []
            if str(item) in graph_by_type
        ]
        if not route_types:
            continue
        hit_keywords = [
            str(keyword)
            for keyword in route.get("keywords") or []
            if searchable_text and _contains_term(searchable_text, str(keyword))
            and not _keyword_is_negated(keyword, positive_terms, negative_terms)
        ]
        hit_modalities = [
            str(value)
            for value in route.get("modalities") or []
            if _normalize_text(value) in modalities
        ]
        hit_tasks = [
            str(value)
            for value in route.get("task_keys") or []
            if _normalize_text(value) in task_keys
        ]
        route_score = (
            len(hit_keywords) * float(route.get("keyword_weight") or 3.0)
            + len(hit_modalities) * float(route.get("modality_weight") or 1.5)
            + len(hit_tasks) * float(route.get("task_weight") or 2.0)
        )
        # Intent routes require a semantic keyword/result hit. Task- and
        # modality-only routing is handled by the explicit bindings below.
        if not hit_keywords or route_score <= 0:
            continue
        for rank, kg_type in enumerate(route_types):
            type_score = route_score * max(0.55, 1.0 - rank * 0.16)
            scores[kg_type] += type_score
            if hit_keywords:
                reasons[kg_type].append("问题/结果：" + "、".join(hit_keywords[:4]))
            if hit_modalities:
                reasons[kg_type].append("上传模态：" + "、".join(hit_modalities[:4]))
            if hit_tasks:
                reasons[kg_type].append("任务节点：" + "、".join(hit_tasks[:4]))

    for binding in bundle["bindings"]:
        matched, reason = _binding_match(binding, context)
        if not matched:
            continue
        for rank, kg_type in enumerate(binding.get("kg_types") or []):
            kg_type = str(kg_type)
            if kg_type not in graph_by_type:
                continue
            scores[kg_type] += float(binding.get("weight") or 1.5) * max(
                0.65, 1.0 - rank * 0.12
            )
            reasons[kg_type].append(reason)

    ranked = sorted(
        (
            (kg_type, score)
            for kg_type, score in scores.items()
            if score > 0 and kg_type in graph_by_type
        ),
        key=lambda item: (
            -item[1],
            int((graph_by_type.get(item[0]) or {}).get("order") or 0),
        ),
    )[:3]
    max_score = ranked[0][1] if ranked else 0.0
    routes = []
    for kg_type, score in ranked:
        graph = graph_by_type[kg_type]
        unique_reasons = []
        for reason in reasons.get(kg_type, []):
            if reason and reason not in unique_reasons:
                unique_reasons.append(reason)
        routes.append(
            {
                "kg_type": kg_type,
                "label": graph.get("label") or kg_type,
                "score": round(score, 4),
                "confidence": round(min(0.99, score / max(6.0, max_score + 1.5)), 4),
                "reasons": unique_reasons[:5],
            }
        )
    return {
        "routes": routes,
        "kg_types": [route["kg_type"] for route in routes],
        "confidence": routes[0]["confidence"] if routes else 0.0,
        "matched": bool(routes),
    }


def match_nodes(
    question: str,
    context: Dict[str, Any],
    kg_types: Sequence[str],
    limit: int = 12,
) -> List[Dict[str, Any]]:
    bundle = load_bundle()
    allowed_types = {str(item) for item in kg_types}
    searchable_text = " ".join(
        [
            _normalize_text(question),
            " ".join(_context_values(context, "result_terms")),
            " ".join(_context_values(context, "risk_terms")),
            " ".join(_context_values(context, "modalities")),
        ]
    ).strip()
    task_keys = set(_context_values(context, "task_keys"))
    positive_terms = set(_context_values(context, "result_terms"))
    negative_terms = set(_context_values(context, "negative_result_terms"))
    candidate_nodes = [
        node
        for node in bundle["nodes"]
        if str(node.get("kg_type") or "") in allowed_types
        and not _risk_node_is_negated(node, positive_terms, negative_terms)
    ]
    query_tokens = _lexical_tokens(searchable_text)
    node_tokens = {
        str(node.get("id") or ""): _node_lexical_tokens(node)
        for node in candidate_nodes
    }
    document_frequency: Dict[str, int] = defaultdict(int)
    for tokens in node_tokens.values():
        for token in tokens:
            document_frequency[token] += 1
    document_count = max(1, len(candidate_nodes))
    scored = []
    for node in candidate_nodes:
        terms = [
            node.get("label"),
            node.get("label_en"),
            *(node.get("aliases") or []),
            *(node.get("keywords") or []),
        ]
        matched_terms = [
            str(term)
            for term in terms
            if searchable_text and _contains_term(searchable_text, str(term))
        ]
        related_tasks = {
            _normalize_text(value) for value in node.get("related_tasks") or []
        }
        matched_tasks = sorted(related_tasks & task_keys)
        matched_tokens = sorted(
            query_tokens & node_tokens.get(str(node.get("id") or ""), set())
        )
        lexical_score = sum(
            1.0 + log((document_count + 1.0) / (document_frequency[token] + 1.0))
            for token in matched_tokens
        )
        score = (
            len(matched_terms) * 3.0
            + len(matched_tasks) * 2.0
            + min(6.0, lexical_score * 0.45)
            + float(node.get("priority") or 0.5)
        )
        scored.append(
            (
                score,
                int(node.get("order") or 0),
                {
                    "id": node.get("id"),
                    "kg_type": node.get("kg_type"),
                    "label": node.get("label"),
                    "score": round(score, 4),
                    "matched_terms": matched_terms[:5],
                    "matched_tasks": matched_tasks[:5],
                    "matched_tokens": matched_tokens[:8],
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1], str(item[2].get("label") or "")))
    selected = [item[2] for item in scored if item[0] > 1.0][: max(1, int(limit))]
    if selected:
        return selected

    # A route can be relevant without an exact node phrase. In that case show
    # a small, deterministic set of high-priority chapter entry points.
    by_type: Dict[str, int] = defaultdict(int)
    fallback = []
    for _score, _order, item in scored:
        kg_type = str(item.get("kg_type") or "")
        if by_type[kg_type] >= 2:
            continue
        item["matched_terms"] = []
        item["matched_tasks"] = []
        item["reason"] = "章节高优先级入口"
        fallback.append(item)
        by_type[kg_type] += 1
        if len(fallback) >= max(1, int(limit)):
            break
    return fallback
