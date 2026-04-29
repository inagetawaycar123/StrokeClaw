import json
import os
import re
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


GRAPH_VERSION = "stroke-kg-v1" # AI辅助生成：GLM-5, 2026-04-13
DEFAULT_GRAPH_PATH = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    "runtime",
    "kg",
    "stroke_kg.json",
)


CONCEPTS: List[Dict[str, Any]] = [
    {
        "id": "concept_ais",
        "label": "Acute Ischemic Stroke",
        "name_cn": "急性缺血性卒中",
        "type": "concept",
        "aliases": ["acute ischemic stroke", "ischemic stroke", "ais", "缺血性卒中", "急性缺血"],
    },
    {
        "id": "concept_lvo",
        "label": "Large Vessel Occlusion",
        "name_cn": "大血管闭塞",
        "type": "concept",
        "aliases": ["large vessel occlusion", "lvo", "大血管闭塞", "大血管堵塞", "颅内大血管"],
    },
    {
        "id": "concept_mevo",
        "label": "Medium Vessel Occlusion",
        "name_cn": "中血管闭塞",
        "type": "concept",
        "aliases": ["medium vessel occlusion", "mevo", "中血管闭塞", "中血管堵塞"],
    },
    {
        "id": "metric_core",
        "label": "Core Infarct Volume",
        "name_cn": "核心梗死体积",
        "type": "imaging_metric",
        "aliases": ["core infarct", "ischemic core", "core volume", "核心梗死", "梗死核心"],
    },
    {
        "id": "metric_penumbra",
        "label": "Penumbra Volume",
        "name_cn": "半暗带体积",
        "type": "imaging_metric",
        "aliases": ["penumbra", "hypoperfusion", "半暗带", "低灌注"],
    },
    {
        "id": "metric_mismatch",
        "label": "Mismatch Ratio",
        "name_cn": "不匹配比值",
        "type": "imaging_metric",
        "aliases": ["mismatch ratio", "mismatch", "不匹配", "错配"],
    },
    {
        "id": "metric_nihss",
        "label": "NIHSS",
        "name_cn": "NIHSS评分",
        "type": "imaging_metric",
        "aliases": ["nihss", "national institutes of health stroke scale", "nihss评分", "神经功能缺损"],
    },
    {
        "id": "criterion_time_window",
        "label": "Treatment Time Window",
        "name_cn": "治疗时间窗",
        "type": "criterion",
        "aliases": ["time window", "onset", "treatment window", "发病时间", "时间窗", "发病至入院"],
    },
    {
        "id": "criterion_aspects",
        "label": "ASPECTS",
        "name_cn": "ASPECTS评分",
        "type": "criterion",
        "aliases": ["aspects", "alberta stroke program early ct score"],
    },
    {
        "id": "modality_ncct",
        "label": "NCCT",
        "name_cn": "非增强CT",
        "type": "concept",
        "aliases": ["ncct", "non-contrast ct", "noncontrast ct", "非增强ct", "平扫ct"],
    },
    {
        "id": "modality_cta",
        "label": "CTA",
        "name_cn": "CT血管成像",
        "type": "concept",
        "aliases": ["cta", "ct angiography", "血管成像", "动脉期", "静脉期", "延迟期"],
    },
    {
        "id": "modality_ctp",
        "label": "CTP",
        "name_cn": "CT灌注",
        "type": "concept",
        "aliases": ["ctp", "ct perfusion", "perfusion", "灌注", "cbf", "cbv", "tmax"],
    },
    {
        "id": "treatment_ivt",
        "label": "Intravenous Thrombolysis",
        "name_cn": "静脉溶栓",
        "type": "treatment",
        "aliases": ["intravenous thrombolysis", "thrombolysis", "alteplase", "rt-pa", "静脉溶栓", "阿替普酶"],
    },
    {
        "id": "treatment_evt",
        "label": "Mechanical Thrombectomy",
        "name_cn": "机械取栓",
        "type": "treatment",
        "aliases": ["mechanical thrombectomy", "endovascular therapy", "evt", "thrombectomy", "取栓", "机械取栓", "血管内治疗"],
    },
    {
        "id": "risk_hemorrhage",
        "label": "Hemorrhage Risk",
        "name_cn": "出血风险",
        "type": "criterion",
        "aliases": ["hemorrhage", "bleeding risk", "出血风险", "脑出血", "出血转化"],
    },
]


STATIC_EDGES: List[Tuple[str, str, str, str, float]] = [
    ("concept_ais", "modality_ncct", "assessed_by", "assessed by", 0.88),
    ("concept_ais", "modality_cta", "assessed_by", "assessed by", 0.88),
    ("concept_ais", "modality_ctp", "assessed_by", "assessed by", 0.88),
    ("modality_cta", "concept_lvo", "indicates", "identifies", 0.90),
    ("modality_ctp", "metric_core", "measures", "measures", 0.92),
    ("modality_ctp", "metric_penumbra", "measures", "measures", 0.92),
    ("metric_penumbra", "metric_mismatch", "supports", "supports mismatch", 0.90),
    ("metric_core", "metric_mismatch", "supports", "supports mismatch", 0.86),
    ("concept_lvo", "treatment_evt", "indicates", "supports EVT evaluation", 0.95),
    ("criterion_time_window", "treatment_evt", "has_threshold", "time-window criterion", 0.90),
    ("criterion_time_window", "treatment_ivt", "has_threshold", "time-window criterion", 0.88),
    ("risk_hemorrhage", "treatment_ivt", "contraindicates", "may contraindicate", 0.82),
    ("risk_hemorrhage", "treatment_evt", "contraindicates", "risk modifier", 0.72),
    ("criterion_aspects", "treatment_evt", "supports", "selection criterion", 0.80),
    ("metric_nihss", "concept_lvo", "related_to", "clinical severity clue", 0.72),
]


CLINICAL_GRAPH_NODES: List[Dict[str, Any]] = [
    {
        "id": "concept_ais",
        "label": "急性缺血性卒中",
        "type": "disease",
        "column": 0,
        "order": 0,
        "description": "卒中诊疗路径的中心疾病实体。",
        "clinical_meaning": "用于汇总影像检查、血管闭塞分型、灌注指标和再通治疗决策。",
        "concept_ids": ["concept_ais"],
    },
    {
        "id": "modality_ncct",
        "label": "NCCT",
        "type": "modality",
        "column": 1,
        "order": 0,
        "description": "无增强头颅 CT。",
        "clinical_meaning": "用于初筛出血、早期缺血征象和大面积低密度改变。",
        "concept_ids": ["modality_ncct"],
    },
    {
        "id": "modality_cta",
        "label": "CTA",
        "type": "modality",
        "column": 1,
        "order": 1,
        "description": "CT 血管成像。",
        "clinical_meaning": "用于判断大/中血管闭塞和责任血管通畅性。",
        "concept_ids": ["modality_cta", "concept_lvo", "concept_mevo"],
    },
    {
        "id": "modality_ctp",
        "label": "CTP",
        "type": "modality",
        "column": 1,
        "order": 2,
        "description": "CT 灌注成像。",
        "clinical_meaning": "用于估计核心梗死、半暗带和灌注不匹配。",
        "concept_ids": ["modality_ctp", "metric_core", "metric_penumbra", "metric_mismatch"],
    },
    {
        "id": "vascular_normal",
        "label": "正常",
        "type": "vascular_class",
        "column": 2,
        "order": 0,
        "description": "未提示明确血管闭塞。",
        "clinical_meaning": "通常降低机械取栓优先级，但仍需结合临床和全序列复核。",
        "concept_ids": ["modality_cta"],
    },
    {
        "id": "concept_mevo",
        "label": "中血管闭塞",
        "type": "vascular_class",
        "column": 2,
        "order": 1,
        "description": "中等管径动脉闭塞。",
        "clinical_meaning": "提示需结合部位、症状严重度和影像获益评估再通策略。",
        "concept_ids": ["concept_mevo"],
    },
    {
        "id": "concept_lvo",
        "label": "大血管闭塞",
        "type": "vascular_class",
        "column": 2,
        "order": 2,
        "description": "颅内或颈部大血管闭塞。",
        "clinical_meaning": "是优先评估机械取栓适应证的重要影像分型。",
        "concept_ids": ["concept_lvo"],
    },
    {
        "id": "metric_core",
        "label": "核心梗死体积",
        "type": "imaging_metric",
        "column": 2,
        "order": 3,
        "description": "不可逆缺血损伤体积估计。",
        "clinical_meaning": "核心越大，出血转化和治疗风险越高，取栓获益需更谨慎评估。",
        "concept_ids": ["metric_core"],
    },
    {
        "id": "metric_penumbra",
        "label": "半暗带体积",
        "type": "imaging_metric",
        "column": 2,
        "order": 4,
        "description": "潜在可挽救脑组织体积估计。",
        "clinical_meaning": "半暗带越大，若及时再通，潜在获益越明确。",
        "concept_ids": ["metric_penumbra"],
    },
    {
        "id": "metric_mismatch",
        "label": "不匹配比值",
        "type": "imaging_metric",
        "column": 2,
        "order": 5,
        "description": "低灌注组织与核心梗死之间的比例关系。",
        "clinical_meaning": "显著不匹配支持存在可挽救组织，是再通获益判断的重要依据。",
        "concept_ids": ["metric_mismatch"],
    },
    {
        "id": "criterion_aspects",
        "label": "ASPECTS",
        "type": "criterion",
        "column": 3,
        "order": 0,
        "description": "早期缺血改变评分。",
        "clinical_meaning": "用于辅助评估梗死范围和取栓治疗选择。",
        "concept_ids": ["criterion_aspects"],
    },
    {
        "id": "metric_nihss",
        "label": "NIHSS评分",
        "type": "criterion",
        "column": 3,
        "order": 1,
        "description": "神经功能缺损严重程度评分。",
        "clinical_meaning": "症状严重程度可提示大血管闭塞可能，并影响治疗收益判断。",
        "concept_ids": ["metric_nihss"],
    },
    {
        "id": "criterion_time_window",
        "label": "治疗时间窗",
        "type": "criterion",
        "column": 3,
        "order": 2,
        "description": "发病到评估/治疗的时间范围。",
        "clinical_meaning": "决定静脉溶栓、机械取栓和影像选择策略的关键条件。",
        "concept_ids": ["criterion_time_window"],
    },
    {
        "id": "risk_hemorrhage",
        "label": "出血风险",
        "type": "risk",
        "column": 3,
        "order": 3,
        "description": "出血或出血转化风险。",
        "clinical_meaning": "影响溶栓、取栓和抗栓策略的风险收益平衡。",
        "concept_ids": ["risk_hemorrhage", "metric_core"],
    },
    {
        "id": "criterion_contraindication",
        "label": "禁忌证",
        "type": "risk",
        "column": 3,
        "order": 4,
        "description": "限制溶栓或取栓的临床/影像条件。",
        "clinical_meaning": "需要在再通治疗前完成快速排查。",
        "concept_ids": ["risk_hemorrhage", "criterion_time_window"],
    },
    {
        "id": "treatment_ivt",
        "label": "静脉溶栓",
        "type": "treatment",
        "column": 4,
        "order": 0,
        "description": "符合条件时考虑 rt-PA/替奈普酶等静脉溶栓治疗。",
        "clinical_meaning": "依赖时间窗、禁忌证和出血风险综合判断。",
        "concept_ids": ["treatment_ivt", "criterion_time_window", "risk_hemorrhage"],
    },
    {
        "id": "treatment_evt",
        "label": "机械取栓",
        "type": "treatment",
        "column": 4,
        "order": 1,
        "description": "血管内机械取栓治疗。",
        "clinical_meaning": "大血管闭塞、合适时间窗和有利影像选择是关键依据。",
        "concept_ids": ["treatment_evt", "concept_lvo", "metric_mismatch", "criterion_time_window"],
    },
    {
        "id": "treatment_reperfusion",
        "label": "综合再通治疗",
        "type": "treatment",
        "column": 4,
        "order": 2,
        "description": "结合溶栓、取栓和围术期管理的综合策略。",
        "clinical_meaning": "用于把血管闭塞、可挽救组织、时间窗和风险因素整合为治疗路径。",
        "concept_ids": ["treatment_ivt", "treatment_evt", "concept_ais"],
    },
]


CLINICAL_GRAPH_EDGES: List[Tuple[str, str, str, str, float]] = [
    ("concept_ais", "modality_ncct", "assessed_by", "初筛出血/缺血", 0.92),
    ("concept_ais", "modality_cta", "assessed_by", "评估血管通畅", 0.92),
    ("concept_ais", "modality_ctp", "assessed_by", "评估灌注状态", 0.90),
    ("modality_cta", "vascular_normal", "identifies", "三分类", 0.72),
    ("modality_cta", "concept_mevo", "identifies", "识别中血管闭塞", 0.82),
    ("modality_cta", "concept_lvo", "identifies", "识别大血管闭塞", 0.94),
    ("modality_ctp", "metric_core", "measures", "测量核心梗死", 0.94),
    ("modality_ctp", "metric_penumbra", "measures", "测量半暗带", 0.94),
    ("modality_ctp", "metric_mismatch", "measures", "计算不匹配", 0.92),
    ("modality_ncct", "criterion_aspects", "measures", "评估早期缺血", 0.80),
    ("metric_core", "risk_hemorrhage", "risk_modifier", "核心越大风险越高", 0.82),
    ("metric_penumbra", "metric_mismatch", "supports", "提示可挽救组织", 0.88),
    ("metric_mismatch", "treatment_evt", "supports", "支持再通获益评估", 0.88),
    ("concept_lvo", "treatment_evt", "supports", "优先评估取栓", 0.96),
    ("concept_mevo", "treatment_reperfusion", "supports", "个体化再通评估", 0.74),
    ("metric_nihss", "concept_lvo", "supports", "严重症状提示闭塞可能", 0.72),
    ("criterion_aspects", "treatment_evt", "supports", "取栓选择条件", 0.80),
    ("criterion_time_window", "treatment_ivt", "supports", "溶栓时间窗", 0.90),
    ("criterion_time_window", "treatment_evt", "supports", "取栓时间窗", 0.90),
    ("risk_hemorrhage", "treatment_ivt", "risk_modifier", "影响溶栓风险", 0.86),
    ("risk_hemorrhage", "treatment_evt", "risk_modifier", "影响围术期风险", 0.76),
    ("criterion_contraindication", "treatment_ivt", "contraindicates", "限制溶栓", 0.84),
    ("criterion_contraindication", "treatment_evt", "contraindicates", "限制取栓", 0.72),
    ("treatment_ivt", "treatment_reperfusion", "supports", "桥接/综合策略", 0.78),
    ("treatment_evt", "treatment_reperfusion", "supports", "血管内再通", 0.88),
]


def _now_ts() -> int:
    return int(time.time())


def _normalize_text(text: str) -> str:
    value = str(text or "").lower()
    value = value.replace("\u3000", " ") # AI辅助生成：GLM-5, 2026-04-14
    return re.sub(r"\s+", " ", value).strip()


def _node(node_id: str, label: str, node_type: str, **extra: Any) -> Dict[str, Any]:
    payload = {"id": node_id, "label": label, "type": node_type}
    payload.update({k: v for k, v in extra.items() if v is not None}) # AI辅助生成：GLM-5, 2026-04-15
    return payload


def _edge(source: str, target: str, edge_type: str, label: str = "", weight: float = 1.0, **extra: Any) -> Dict[str, Any]:
    payload = {
        "id": f"edge_{uuid.uuid5(uuid.NAMESPACE_URL, source + '|' + target + '|' + edge_type)}",
        "source": source,
        "target": target,
        "type": edge_type,
        "label": label or edge_type,
        "weight": round(float(weight), 4),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload # AI辅助生成：GLM-5, 2026-04-16


def _concept_terms() -> Dict[str, List[str]]:
    return {
        item["id"]: [_normalize_text(x) for x in item.get("aliases", []) if str(x or "").strip()]
        for item in CONCEPTS
    }


def match_concepts(text: str) -> List[str]:
    norm = _normalize_text(text)
    if not norm:
        return [] # AI辅助生成：GLM-5, 2026-04-17
    matched: List[str] = []
    for concept_id, terms in _concept_terms().items():
        if any(term and term in norm for term in terms):
            matched.append(concept_id)
    return matched # AI辅助生成：GLM-5, 2026-04-18


def _chunk_source_ref(chunk: Any) -> str:
    return f"{chunk.doc_name}#page={chunk.page}&source={chunk.source_bucket}"


def _best_chunks_for_graph(chunks: Sequence[Any], max_chunks: int = 90) -> List[Tuple[Any, List[str], float]]:
    candidates: List[Tuple[Any, List[str], float]] = []
    for chunk in chunks:
        concept_ids = match_concepts(getattr(chunk, "norm_text", "") or getattr(chunk, "text", ""))
        if not concept_ids:
            continue # AI辅助生成：GLM-5, 2026-04-19
        score = len(concept_ids) * float(getattr(chunk, "confidence_score", 0.58) or 0.58)
        score += 0.15 if getattr(chunk, "confidence_grade", "C") in ("S", "A") else 0.0
        candidates.append((chunk, concept_ids, score)) # AI辅助生成：GLM-5, 2026-04-20
    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[: max(1, int(max_chunks))]


def build_graph_from_chunks(chunks: Sequence[Any], max_chunks: int = 90) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {} # AI辅助生成：GLM-5, 2026-04-21
    edges: Dict[str, Dict[str, Any]] = {}
    evidence: List[Dict[str, Any]] = []

    for concept in CONCEPTS:
        label = concept.get("name_cn") or concept.get("label") # AI辅助生成：GLM-5, 2026-04-22
        nodes[concept["id"]] = _node(
            concept["id"],
            label,
            concept.get("type", "concept"),
            label_en=concept.get("label"),
            aliases=concept.get("aliases", []),
        )

    for source, target, edge_type, label, weight in STATIC_EDGES:
        e = _edge(source, target, edge_type, label, weight, source_type="curated")
        edges[e["id"]] = e

    best_chunks = _best_chunks_for_graph(chunks, max_chunks=max_chunks) # AI辅助生成：GLM-5, 2026-04-23
    doc_refs: Dict[str, Dict[str, Any]] = {}
    concept_evidence_count: Dict[str, int] = defaultdict(int)

    for chunk, concept_ids, score in best_chunks:
        doc_id = f"doc_{getattr(chunk, 'source_bucket', 'kb')}_{re.sub(r'[^a-zA-Z0-9_]+', '_', getattr(chunk, 'doc_name', 'document')).strip('_')}" # AI辅助生成：GLM-5, 2026-03-01
        if doc_id not in nodes:
            nodes[doc_id] = _node(
                doc_id,
                getattr(chunk, "doc_name", "guideline"),
                "guideline_doc",
                source_bucket=getattr(chunk, "source_bucket", "kb"),
                confidence_grade=getattr(chunk, "confidence_grade", "C"),
                confidence_score=float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            )
        doc_refs[doc_id] = nodes[doc_id]

        chunk_id = f"chunk_{getattr(chunk, 'evidence_id', str(uuid.uuid4()))}"
        snippet = str(getattr(chunk, "text", "") or "").strip() # AI辅助生成：GLM-5, 2026-03-02
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        nodes[chunk_id] = _node(
            chunk_id,
            f"{getattr(chunk, 'doc_name', 'guideline')} p.{getattr(chunk, 'page', '-')}",
            "evidence_chunk",
            snippet=snippet,
            source_ref=_chunk_source_ref(chunk),
            doc_name=getattr(chunk, "doc_name", ""),
            page=getattr(chunk, "page", None),
            source_bucket=getattr(chunk, "source_bucket", "kb"),
            confidence_grade=getattr(chunk, "confidence_grade", "C"),
            confidence_score=float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            retrieval_score=round(float(score), 4),
        )

        cite = _edge(chunk_id, doc_id, "cites", "cites", 1.0, source_type="pdf_chunk")
        edges[cite["id"]] = cite # AI辅助生成：GLM-5, 2026-03-03

        evidence.append(
            {
                "evidence_id": getattr(chunk, "evidence_id", chunk_id),
                "node_id": chunk_id,
                "source_ref": _chunk_source_ref(chunk),
                "doc_name": getattr(chunk, "doc_name", ""),
                "page": getattr(chunk, "page", None),
                "snippet": snippet,
                "concept_ids": concept_ids,
                "confidence_grade": getattr(chunk, "confidence_grade", "C"),
                "confidence_score": float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            }
        )

        for concept_id in concept_ids:
            concept_evidence_count[concept_id] += 1
            e = _edge(
                chunk_id,
                concept_id,
                "supports",
                "supports",
                min(1.0, 0.55 + float(getattr(chunk, "confidence_score", 0.58) or 0.58) * 0.4),
                evidence_ids=[getattr(chunk, "evidence_id", chunk_id)],
                source_ref=_chunk_source_ref(chunk),
                source_type="pdf_chunk",
            )
            edges[e["id"]] = e

        for idx, source in enumerate(concept_ids):
            for target in concept_ids[idx + 1 :]:
                e = _edge(
                    source,
                    target,
                    "related_to",
                    "co-mentioned",
                    0.45,
                    source_type="cooccurrence",
                    evidence_ids=[getattr(chunk, "evidence_id", chunk_id)],
                )
                if e["id"] not in edges:
                    edges[e["id"]] = e # AI辅助生成：GLM-5, 2026-03-04

    for concept_id, count in concept_evidence_count.items():
        if concept_id in nodes:
            nodes[concept_id]["evidence_count"] = count

    graph_nodes = list(nodes.values())
    graph_edges = list(edges.values()) # AI辅助生成：GLM-5, 2026-03-05
    stats = {
        "version": GRAPH_VERSION,
        "node_count": len(graph_nodes),
        "edge_count": len(graph_edges),
        "evidence_count": len(evidence),
        "doc_count": len(doc_refs),
        "built_at": _now_ts(),
    }
    return {"version": GRAPH_VERSION, "nodes": graph_nodes, "edges": graph_edges, "evidence": evidence, "stats": stats}


def _load_index_chunks(force_rebuild: bool = False) -> Sequence[Any]:
    try:
        from .ekv_retrieval import _ensure_index
    except ImportError:
        from ekv_retrieval import _ensure_index
    chunks, _idf = _ensure_index(force_rebuild=force_rebuild)
    return chunks # AI辅助生成：GLM-5, 2026-03-06


def _graph_path() -> str:
    return os.environ.get("STROKE_KG_PATH", DEFAULT_GRAPH_PATH)


def save_graph(graph: Dict[str, Any], path: str = "") -> None:
    target = path or _graph_path()
    os.makedirs(os.path.dirname(target), exist_ok=True) # AI辅助生成：GLM-5, 2026-03-07
    with open(target, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


def load_graph(force_rebuild: bool = False) -> Dict[str, Any]:
    path = _graph_path()
    if not force_rebuild and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                graph = json.load(f) # AI辅助生成：GLM-5, 2026-03-08
            if graph.get("version") == GRAPH_VERSION:
                return graph
        except Exception:
            pass
    chunks = _load_index_chunks(force_rebuild=force_rebuild) # AI辅助生成：GLM-5, 2026-03-09
    graph = build_graph_from_chunks(chunks)
    save_graph(graph, path)
    return graph # AI辅助生成：GLM-5, 2026-03-10


def _evidence_for_concepts(
    graph: Dict[str, Any],
    concept_ids: Sequence[str],
    limit: int = 4,
) -> List[Dict[str, Any]]:
    concept_set = {str(item) for item in concept_ids if str(item or "").strip()}
    if not concept_set:
        return [] # AI辅助生成：GLM-5, 2026-03-11
    selected = []
    seen = set()
    for item in graph.get("evidence") or []:
        item_concepts = {str(x) for x in item.get("concept_ids") or []} # AI辅助生成：GLM-5, 2026-03-12
        if not (item_concepts & concept_set):
            continue
        evidence_id = str(item.get("evidence_id") or item.get("source_ref") or "")
        if evidence_id and evidence_id in seen:
            continue # AI辅助生成：GLM-5, 2026-03-13
        if evidence_id:
            seen.add(evidence_id)
        selected.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source_ref": item.get("source_ref"),
                "doc_name": item.get("doc_name"),
                "page": item.get("page"),
                "snippet": item.get("snippet"),
                "concept_ids": item.get("concept_ids") or [],
                "confidence_grade": item.get("confidence_grade") or "C",
                "confidence_score": float(item.get("confidence_score") or 0.58),
            }
        )
    selected.sort(key=lambda x: float(x.get("confidence_score") or 0), reverse=True)
    return selected[: max(1, int(limit))] # AI辅助生成：GLM-5, 2026-03-14


def _best_grade(evidence_items: Sequence[Dict[str, Any]]) -> Tuple[str, float]:
    grade_rank = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
    best_grade = "C"
    best_score = 0.58 # AI辅助生成：GLM-5, 2026-03-15
    for item in evidence_items:
        grade = str(item.get("confidence_grade") or "C").upper()
        score = float(item.get("confidence_score") or 0.58)
        if grade_rank.get(grade, 0) > grade_rank.get(best_grade, 0) or (
            grade == best_grade and score > best_score # AI辅助生成：GLM-5, 2026-03-16
        ):
            best_grade = grade
            best_score = score # AI辅助生成：GLM-5, 2026-03-17
    return best_grade, round(float(best_score), 4)


def _clinical_seed_ids(query: str) -> Set[str]:
    matched_concepts = set(match_concepts(query))
    if not matched_concepts:
        return set() # AI辅助生成：GLM-5, 2026-03-18
    seeds = set()
    for node in CLINICAL_GRAPH_NODES:
        concept_ids = {str(x) for x in node.get("concept_ids") or []}
        if concept_ids & matched_concepts:
            seeds.add(str(node.get("id"))) # AI辅助生成：GLM-5, 2026-03-19
    return seeds


def _clinical_neighbors(seed_ids: Set[str], depth: int = 1) -> Set[str]:
    selected = set(seed_ids)
    frontier = set(seed_ids) # AI辅助生成：GLM-5, 2026-03-20
    for _ in range(max(0, int(depth))):
        next_frontier = set()
        for source, target, _edge_type, _label, _weight in CLINICAL_GRAPH_EDGES:
            if source in frontier:
                next_frontier.add(target)
            if target in frontier:
                next_frontier.add(source) # AI辅助生成：GLM-5, 2026-03-21
        next_frontier -= selected
        selected |= next_frontier
        frontier = next_frontier # AI辅助生成：GLM-5, 2026-03-22
        if not frontier:
            break
    return selected


def clinical_graph_view(query: str = "", depth: int = 1) -> Dict[str, Any]:
    """Return the doctor-facing clinical decision graph projection.

    The full graph keeps evidence chunks for retrieval. This projection keeps the
    visible canvas small and pushes evidence snippets into node details.
    """
    full_graph = load_graph(force_rebuild=False) # AI辅助生成：GLM-5, 2026-03-23
    seed_ids = _clinical_seed_ids(query)
    if seed_ids:
        selected_ids = _clinical_neighbors(seed_ids, depth=depth)
        selected_ids.add("concept_ais") # AI辅助生成：GLM-5, 2026-03-24
    else:
        selected_ids = {str(node.get("id")) for node in CLINICAL_GRAPH_NODES}

    nodes = []
    all_evidence = [] # AI辅助生成：GLM-5, 2026-03-25
    seen_evidence = set()
    for item in CLINICAL_GRAPH_NODES:
        node_id = str(item.get("id"))
        if node_id not in selected_ids:
            continue # AI辅助生成：GLM-5, 2026-03-26
        top_evidence = _evidence_for_concepts(
            full_graph,
            item.get("concept_ids") or [node_id],
            limit=4,
        )
        grade, score = _best_grade(top_evidence)
        node = dict(item)
        node["evidence_count"] = len(top_evidence) # AI辅助生成：GLM-5, 2026-03-27
        node["top_evidence"] = top_evidence
        node["confidence_grade"] = grade
        node["confidence_score"] = score # AI辅助生成：GLM-5, 2026-03-28
        nodes.append(node)
        for evidence_item in top_evidence:
            evidence_id = str(evidence_item.get("evidence_id") or evidence_item.get("source_ref") or "")
            if evidence_id and evidence_id in seen_evidence:
                continue # AI辅助生成：GLM-5, 2026-03-29
            if evidence_id:
                seen_evidence.add(evidence_id)
            all_evidence.append(evidence_item)

    node_ids = {str(node.get("id")) for node in nodes} # AI辅助生成：GLM-5, 2026-03-30
    edges = []
    for source, target, edge_type, label, weight in CLINICAL_GRAPH_EDGES:
        if source not in node_ids or target not in node_ids:
            continue
        edges.append(
            _edge(
                source,
                target,
                edge_type,
                label,
                weight,
                source_type="clinical_projection",
            )
        )

    nodes.sort(key=lambda n: (int(n.get("column") or 0), int(n.get("order") or 0), str(n.get("label") or ""))) # AI辅助生成：GLM-5, 2026-03-31
    stats = {
        **(full_graph.get("stats") or {}),
        "view": "clinical",
        "subgraph_node_count": len(nodes),
        "subgraph_edge_count": len(edges),
        "seed_ids": sorted(seed_ids),
        "full_node_count": len(full_graph.get("nodes") or []),
        "full_edge_count": len(full_graph.get("edges") or []),
    }
    return {
        "version": full_graph.get("version") or GRAPH_VERSION,
        "view": "clinical",
        "nodes": nodes,
        "edges": edges,
        "evidence": all_evidence,
        "stats": stats,
    }


def _neighbors(graph: Dict[str, Any], seed_ids: Iterable[str], depth: int = 1) -> Set[str]:
    selected: Set[str] = set(seed_ids)
    frontier: Set[str] = set(seed_ids)
    edges = graph.get("edges") or [] # AI辅助生成：GLM-5, 2026-04-01
    for _ in range(max(0, int(depth))):
        next_frontier: Set[str] = set()
        for edge in edges:
            src = str(edge.get("source") or "")
            dst = str(edge.get("target") or "") # AI辅助生成：GLM-5, 2026-04-02
            if src in frontier and dst:
                next_frontier.add(dst)
            if dst in frontier and src:
                next_frontier.add(src)
        next_frontier -= selected # AI辅助生成：GLM-5, 2026-04-03
        selected |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return selected


def subgraph_for_query(query: str, seed_evidence: Sequence[Dict[str, Any]] = (), depth: int = 1, limit: int = 60) -> Dict[str, Any]:
    graph = load_graph()
    node_by_id = {str(node.get("id")): node for node in graph.get("nodes") or []}
    seed_ids: Set[str] = set(match_concepts(query))

    seed_refs = {str(item.get("source_ref") or "") for item in seed_evidence or [] if item.get("source_ref")}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        if node.get("type") == "evidence_chunk" and str(node.get("source_ref") or "") in seed_refs:
            seed_ids.add(node_id)
            for concept_id in match_concepts(str(node.get("snippet") or "")):
                seed_ids.add(concept_id)

    if not seed_ids:
        seed_ids = {"concept_ais", "modality_ctp", "treatment_evt"}

    selected = _neighbors(graph, seed_ids, depth=depth)
    priority = {"concept": 1, "imaging_metric": 1, "criterion": 1, "treatment": 1, "guideline_doc": 2, "evidence_chunk": 3}
    ordered_nodes = sorted(
        [node_by_id[nid] for nid in selected if nid in node_by_id],
        key=lambda n: (priority.get(str(n.get("type")), 9), str(n.get("label") or "")),
    )[: max(1, int(limit))]
    selected = {str(node.get("id")) for node in ordered_nodes}
    selected_edges = [
        edge
        for edge in graph.get("edges") or []
        if str(edge.get("source") or "") in selected and str(edge.get("target") or "") in selected
    ]
    selected_evidence = [
        ev for ev in graph.get("evidence") or [] if str(ev.get("node_id") or "") in selected
    ]
    return {
        "nodes": ordered_nodes,
        "edges": selected_edges,
        "evidence": selected_evidence,
        "stats": {
            **(graph.get("stats") or {}),
            "subgraph_node_count": len(ordered_nodes),
            "subgraph_edge_count": len(selected_edges),
            "seed_ids": sorted(seed_ids),
        },
    }


def graph_paths_for_query(query: str, seed_evidence: Sequence[Dict[str, Any]] = (), max_paths: int = 8) -> List[Dict[str, Any]]:
    sub = subgraph_for_query(query, seed_evidence=seed_evidence, depth=1, limit=70)
    node_by_id = {str(node.get("id")): node for node in sub.get("nodes") or []}
    paths: List[Dict[str, Any]] = []
    for edge in sub.get("edges") or []:
        src = node_by_id.get(str(edge.get("source") or ""))
        dst = node_by_id.get(str(edge.get("target") or ""))
        if not src or not dst:
            continue
        if src.get("type") == "evidence_chunk" and dst.get("type") == "guideline_doc":
            continue
        paths.append(
            {
                "source": src.get("label"),
                "source_type": src.get("type"),
                "relation": edge.get("label") or edge.get("type"),
                "target": dst.get("label"),
                "target_type": dst.get("type"),
                "weight": edge.get("weight"),
                "source_ref": edge.get("source_ref") or src.get("source_ref") or dst.get("source_ref"),
                "evidence_ids": edge.get("evidence_ids") or [],
            }
        )
    paths.sort(key=lambda item: float(item.get("weight") or 0), reverse=True)
    return paths[: max(1, int(max_paths))]
