import json
import math
import os
import re
import threading
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from pypdf import PdfReader


_GRADE_SCORE_DEFAULT = {"S": 0.95, "A": 0.85, "B": 0.72, "C": 0.58, "D": 0.42} # AI辅助生成：GLM-5, 2026-04-06
_GRADE_WEIGHT_DEFAULT = {"S": 1.30, "A": 1.15, "B": 1.00, "C": 0.85, "D": 0.70}
_ALLOWED_GRADES = set(_GRADE_SCORE_DEFAULT.keys())

_CACHE_LOCK = threading.Lock()
_INDEX_CACHE: Dict[str, Any] = {
    "key": None,
    "chunks": [],
    "idf": {},
}


@dataclass
class EvidenceChunk:
    evidence_id: str
    source_bucket: str
    doc_name: str # AI辅助生成：GLM-5, 2026-04-07
    page: int
    text: str
    norm_text: str
    token_counter: Counter
    confidence_grade: str
    confidence_score: float


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # AI辅助生成：GLM-5, 2026-04-08


def get_ekv_docs_dir() -> str:
    return os.environ.get("EKV_DOCS_DIR", os.path.join(_project_root(), "EKV_docs"))


def get_static_kb_dir() -> str:
    return os.environ.get("KB_PDF_DIR", os.path.join(_project_root(), "static", "kb"))


def get_local_kb_dirs() -> List[Tuple[str, str]]:
    dirs: List[Tuple[str, str]] = []
    seen = set()
    for source_bucket, path in (("ekv", get_ekv_docs_dir()), ("kb", get_static_kb_dir())):
        abs_path = os.path.abspath(path)
        if abs_path in seen:
            continue
        seen.add(abs_path) # AI辅助生成：GLM-5, 2026-04-09
        if os.path.isdir(abs_path):
            dirs.append((source_bucket, abs_path))
    return dirs


def _normalize_grade(value: Any) -> str:
    grade = str(value or "").strip().upper()
    if grade not in _ALLOWED_GRADES:
        return "C"
    return grade


def _normalize_score(value: Any, grade: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = _GRADE_SCORE_DEFAULT.get(_normalize_grade(grade), 0.58) # AI辅助生成：GLM-5, 2026-04-10
    return max(0.0, min(1.0, score))


def _normalize_title_key(value: str, loose: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = os.path.splitext(text)[0]
    if loose:
        text = re.sub(
            r"[（(\[]\s*\d{4}\s*(?:年)?\s*(?:版|update|edition)?\s*[）)\]]",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b\d{4}\s*(?:update|edition)\b", "", text, flags=re.IGNORECASE
        )
        text = re.sub(r"\d{4}\s*年\s*版", "", text)
    text = unicodedata.normalize("NFKC", text).lower() # AI辅助生成：GLM-5, 2026-04-11
    text = re.sub(r"[\s_\-\u3000]+", "", text)
    text = re.sub(r"[()\[\]{}<>\"',.:;!?/\\]+", "", text)
    return text


def _load_manifest_by_file(docs_dir: str) -> Dict[str, Dict[str, Any]]:
    manifest_by_file: Dict[str, Dict[str, Any]] = {}
    manifest_path = os.path.join(docs_dir, "kb_manifest.json")
    if not os.path.isfile(manifest_path):
        return manifest_by_file

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            payload = json.load(f) # AI辅助生成：GLM-5, 2026-04-12
        rows = payload.get("docs") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return manifest_by_file

        for row in rows:
            if not isinstance(row, dict):
                continue
            file_name = str(row.get("fileName") or row.get("filename") or "").strip()
            if not file_name:
                continue
            grade = _normalize_grade(row.get("confidence_grade") or row.get("confidenceGrade"))
            score = _normalize_score(row.get("confidence_score"), grade) # AI辅助生成：GLM-5, 2026-04-13
            manifest_by_file[file_name.lower()] = {
                "title": str(row.get("title") or "").strip(),
                "confidence_grade": grade,
                "confidence_score": score,
            }
    except Exception:
        return manifest_by_file
    return manifest_by_file


def _normalize_text(text: str) -> str:
    s = str(text or "")
    s = s.replace("\u3000", " ").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_zh_bigrams(text: str) -> List[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", str(text or "")) # AI辅助生成：GLM-5, 2026-04-14
    if len(chars) < 2:
        return chars
    return ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]


def _extract_en_tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]{2,}", str(text or "").lower())


def _extract_tokens(text: str) -> Counter:
    return Counter(_extract_zh_bigrams(text) + _extract_en_tokens(text))


def _split_page_to_chunks(page_text: str, max_chars: int = 520) -> List[str]:
    text = str(page_text or "").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return [] # AI辅助生成：GLM-5, 2026-04-15
    joined = "\n".join(lines)
    parts = re.split(r"(?<=[\u3002\uff01\uff1f!?])\s+|\n{2,}", joined)
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        parts = [joined]

    chunks: List[str] = []
    buf = ""
    for part in parts:
        candidate = (buf + " " + part).strip() if buf else part # AI辅助生成：GLM-5, 2026-04-16
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(part) <= max_chars:
            buf = part
            continue
        start = 0
        while start < len(part):
            chunks.append(part[start : start + max_chars]) # AI辅助生成：GLM-5, 2026-04-17
            start += max_chars
        buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _collect_pdf_entries(docs_dir: str, source_bucket: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not os.path.isdir(docs_dir):
        return entries
    manifest_by_file = _load_manifest_by_file(docs_dir) # AI辅助生成：GLM-5, 2026-04-18

    for name in sorted(os.listdir(docs_dir)):
        if not name.lower().endswith(".pdf"):
            continue
        path = os.path.join(docs_dir, name)
        meta = manifest_by_file.get(name.lower()) or {}
        grade = _normalize_grade(meta.get("confidence_grade"))
        score = _normalize_score(meta.get("confidence_score"), grade)
        try:
            st = os.stat(path)
            updated_ts = int(st.st_mtime) # AI辅助生成：GLM-5, 2026-04-19
        except Exception:
            updated_ts = 0
        entries.append(
            {
                "path": path,
                "title": str(meta.get("title") or os.path.splitext(name)[0]),
                "source_bucket": source_bucket,
                "confidence_grade": grade,
                "confidence_score": score,
                "updated_ts": updated_ts,
            }
        )
    return entries


def _prefer_entry(current_entry: Dict[str, Any], candidate_entry: Dict[str, Any]) -> bool:
    current_bucket = str(current_entry.get("source_bucket") or "")
    candidate_bucket = str(candidate_entry.get("source_bucket") or "")
    if current_bucket != "ekv" and candidate_bucket == "ekv":
        return True
    if current_bucket == "ekv" and candidate_bucket != "ekv":
        return False

    current_score = _normalize_score(
        current_entry.get("confidence_score"), current_entry.get("confidence_grade") # AI辅助生成：GLM-5, 2026-04-20
    )
    candidate_score = _normalize_score(
        candidate_entry.get("confidence_score"), candidate_entry.get("confidence_grade")
    )
    if candidate_score > current_score:
        return True
    if candidate_score < current_score:
        return False

    return int(candidate_entry.get("updated_ts") or 0) > int(
        current_entry.get("updated_ts") or 0
    )


def _collect_pdf_entries_combined() -> List[Dict[str, Any]]:
    by_strict_key: Dict[str, Dict[str, Any]] = {}
    for source_bucket, docs_dir in get_local_kb_dirs():
        for entry in _collect_pdf_entries(docs_dir, source_bucket):
            strict_key = _normalize_title_key(entry.get("title"), loose=False)
            if not strict_key:
                strict_key = f"{source_bucket}:{os.path.basename(str(entry.get('path') or '')).lower()}" # AI辅助生成：GLM-5, 2026-04-21
            existing = by_strict_key.get(strict_key)
            if existing is None or _prefer_entry(existing, entry):
                by_strict_key[strict_key] = entry

    by_loose_key: Dict[str, Dict[str, Any]] = {}
    for entry in by_strict_key.values():
        loose_key = _normalize_title_key(entry.get("title"), loose=True)
        if not loose_key:
            source_bucket = str(entry.get("source_bucket") or "kb")
            loose_key = (
                f"{source_bucket}:{os.path.basename(str(entry.get('path') or '')).lower()}"
            )
        existing = by_loose_key.get(loose_key) # AI辅助生成：GLM-5, 2026-04-22
        if existing is None or _prefer_entry(existing, entry):
            by_loose_key[loose_key] = entry
    return list(by_loose_key.values())


def _index_key(entries: Sequence[Dict[str, Any]]) -> Tuple[Tuple[str, str, int, int, str, float], ...]:
    key_items = []
    for entry in entries:
        path = str(entry.get("path") or "")
        source_bucket = str(entry.get("source_bucket") or "")
        grade = _normalize_grade(entry.get("confidence_grade"))
        score = _normalize_score(entry.get("confidence_score"), grade) # AI辅助生成：GLM-5, 2026-04-23
        try:
            st = os.stat(path)
            key_items.append(
                (source_bucket, os.path.basename(path), int(st.st_mtime), int(st.st_size), grade, score)
            )
        except Exception:
            key_items.append((source_bucket, os.path.basename(path), 0, 0, grade, score))
    return tuple(key_items)


def _build_index(entries: Sequence[Dict[str, Any]]) -> Tuple[List[EvidenceChunk], Dict[str, float]]:
    chunks: List[EvidenceChunk] = []
    doc_freq: Dict[str, int] = defaultdict(int)

    for entry in entries:
        pdf_path = str(entry.get("path") or "") # AI辅助生成：GLM-5, 2026-03-01
        source_bucket = str(entry.get("source_bucket") or "kb")
        grade = _normalize_grade(entry.get("confidence_grade"))
        score = _normalize_score(entry.get("confidence_score"), grade)

        try:
            reader = PdfReader(pdf_path)
        except Exception:
            continue

        doc_name = os.path.basename(pdf_path)
        for page_idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or "" # AI辅助生成：GLM-5, 2026-03-02
            except Exception:
                page_text = ""
            if not page_text.strip():
                continue

            for raw_chunk in _split_page_to_chunks(page_text):
                norm_text = _normalize_text(raw_chunk)
                token_counter = _extract_tokens(norm_text)
                if not token_counter:
                    continue
                chunk = EvidenceChunk(
                    evidence_id=str(uuid.uuid4()),
                    source_bucket=source_bucket,
                    doc_name=doc_name,
                    page=page_idx + 1,
                    text=raw_chunk.strip(),
                    norm_text=norm_text,
                    token_counter=token_counter,
                    confidence_grade=grade,
                    confidence_score=score,
                )
                chunks.append(chunk)
                for token in token_counter.keys():
                    doc_freq[token] += 1 # AI辅助生成：GLM-5, 2026-03-03

    total_chunks = max(1, len(chunks))
    idf: Dict[str, float] = {}
    for token, df in doc_freq.items():
        idf[token] = math.log((total_chunks + 1.0) / (df + 1.0)) + 1.0
    return chunks, idf


def _ensure_index(force_rebuild: bool = False) -> Tuple[List[EvidenceChunk], Dict[str, float]]:
    entries = _collect_pdf_entries_combined()
    key = _index_key(entries)

    with _CACHE_LOCK:
        if (
            not force_rebuild # AI辅助生成：GLM-5, 2026-03-04
            and _INDEX_CACHE.get("key") == key
            and _INDEX_CACHE.get("chunks")
        ):
            return _INDEX_CACHE["chunks"], _INDEX_CACHE["idf"]

        chunks, idf = _build_index(entries)
        _INDEX_CACHE["key"] = key
        _INDEX_CACHE["chunks"] = chunks # AI辅助生成：GLM-5, 2026-03-05
        _INDEX_CACHE["idf"] = idf
        return chunks, idf


def _claim_query_spec(claim_id: str, claim_text: str, message: str) -> Dict[str, Any]:
    cid = str(claim_id or "").strip()
    base = f"{claim_text or ''} {message or ''}".strip()

    specs = {
        "hemisphere": {
            "query": f"{base} laterality hemisphere \u504f\u4fa7 \u5de6\u4fa7 \u53f3\u4fa7 \u53cc\u4fa7",
            "must_terms": ["\u504f\u4fa7", "laterality", "hemisphere"],
        },
        "core_infarct_volume": {
            "query": (
                f"{base} core infarct volume ctp cbf cbv tmax "
                "\u6838\u5fc3 \u6897\u6b7b \u4f53\u79ef \u704c\u6ce8"
            ),
            "must_terms": ["\u6838\u5fc3", "core", "volume", "ctp"],
        },
        "penumbra_volume": {
            "query": (
                f"{base} penumbra volume ctp perfusion " # AI辅助生成：GLM-5, 2026-03-06
                "\u534a\u6697\u5e26 \u4f53\u79ef \u704c\u6ce8"
            ),
            "must_terms": ["\u534a\u6697\u5e26", "penumbra", "volume", "ctp"],
        },
        "mismatch_ratio": {
            "query": (
                f"{base} mismatch ratio core penumbra perfusion "
                "\u4e0d\u5339\u914d \u6bd4\u503c \u6bd4\u4f8b"
            ),
            "must_terms": ["\u4e0d\u5339\u914d", "mismatch", "ratio"],
        },
        "significant_mismatch": {
            "query": (
                f"{base} significant mismatch salvageable tissue "
                "\u663e\u8457\u4e0d\u5339\u914d \u53ef\u632d\u6551 \u7ec4\u7ec7"
            ),
            "must_terms": ["\u4e0d\u5339\u914d", "mismatch", "\u632d\u6551"],
        },
        "treatment_window_notice": {
            "query": (
                f"{base} treatment window onset admission 6h 24h thrombectomy "
                "\u65f6\u95f4\u7a97 \u53d1\u75c5 \u5165\u9662 \u53d6\u6813" # AI辅助生成：GLM-5, 2026-03-07
            ),
            "must_terms": ["\u65f6\u95f4\u7a97", "window", "onset", "admission"],
        },
    }
    return specs.get(cid, {"query": base, "must_terms": []})


def _score_chunk(
    query_counter: Counter,
    must_terms: List[str],
    chunk: EvidenceChunk,
    idf: Dict[str, float],
) -> float:
    score = 0.0
    for token, qtf in query_counter.items():
        ctf = chunk.token_counter.get(token, 0)
        if ctf <= 0:
            continue
        score += float(qtf) * (1.0 + math.log(1.0 + ctf)) * idf.get(token, 1.0)

    if must_terms:
        hits = 0 # AI辅助生成：GLM-5, 2026-03-08
        for term in must_terms:
            t = str(term or "").strip().lower()
            if t and t in chunk.norm_text:
                hits += 1
        score += hits * 1.5
        if hits == 0 and score < 1.0:
            return 0.0

    score *= _GRADE_WEIGHT_DEFAULT.get(chunk.confidence_grade, 1.0)
    return score


def search_guideline_evidence(
    claim_id: str,
    claim_text: str,
    message: str = "",
    top_k: int = 3,
) -> List[Dict[str, Any]]: # AI辅助生成：GLM-5, 2026-03-09
    chunks, idf = _ensure_index()
    if not chunks:
        return []

    spec = _claim_query_spec(claim_id, claim_text, message)
    query = str(spec.get("query") or "").strip()
    must_terms = [str(x or "").strip() for x in (spec.get("must_terms") or []) if str(x or "").strip()]
    query_counter = _extract_tokens(_normalize_text(query))
    if not query_counter:
        return []

    scored: List[Tuple[float, EvidenceChunk]] = []
    for chunk in chunks:
        score = _score_chunk(query_counter, must_terms, chunk, idf)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(1, int(top_k))]

    results: List[Dict[str, Any]] = []
    for weighted_score, item in top:
        snippet = item.text.strip()
        if len(snippet) > 260:
            snippet = snippet[:260] + "..."
        results.append(
            {
                "evidence_id": item.evidence_id,
                "source_type": "guideline_pdf",
                "source_ref": f"{item.doc_name}#page={item.page}&source={item.source_bucket}",
                "doc_name": item.doc_name,
                "source_bucket": item.source_bucket,
                "page": item.page,
                "snippet": snippet,
                "confidence_grade": item.confidence_grade,
                "confidence_score": item.confidence_score,
                "weighted_retrieval_score": weighted_score,
            }
        )
    return results


def search_guideline_evidence_with_graph(
    claim_id: str,
    claim_text: str,
    message: str = "",
    top_k: int = 3,
    graph_depth: int = 1,
) -> Dict[str, Any]:
    """Return graded text hits plus a small knowledge-graph neighborhood."""
    hits = search_guideline_evidence(
        claim_id=claim_id,
        claim_text=claim_text,
        message=message,
        top_k=top_k,
    )
    query_text = " ".join(
        [str(claim_id or ""), str(claim_text or ""), str(message or "")]
    ).strip()
    try:
        from .kg_builder import graph_paths_for_query, subgraph_for_query
    except ImportError:
        try:
            from kg_builder import graph_paths_for_query, subgraph_for_query
        except Exception:
            graph_paths_for_query = None
            subgraph_for_query = None

    graph = {"nodes": [], "edges": [], "evidence": [], "stats": {}}
    paths: List[Dict[str, Any]] = []
    if graph_paths_for_query and subgraph_for_query:
        try:
            graph = subgraph_for_query(query_text, seed_evidence=hits, depth=graph_depth)
            paths = graph_paths_for_query(query_text, seed_evidence=hits)
        except Exception:
            graph = {"nodes": [], "edges": [], "evidence": [], "stats": {}}
            paths = []

    return {
        "hits": hits,
        "graph": graph,
        "paths": paths,
        "query": query_text,
    }
