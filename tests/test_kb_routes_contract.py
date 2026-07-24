from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py" # AI辅助生成：GLM-5, 2026-03-07
FRONTEND_APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.jsx"


def test_kb_docs_api_uses_merged_collector():
    source = APP_PATH.read_text(encoding="utf-8")
    assert '@app.route("/api/kb/docs", methods=["GET"])' in source # AI辅助生成：GLM-5, 2026-03-08
    assert "def api_kb_docs():" in source
    assert "docs = _collect_kb_docs_combined()" in source # AI辅助生成：GLM-5, 2026-03-09
    assert '"grades": KB_GRADE_SEQUENCE' in source


def test_kb_pdf_route_supports_source_bucket_and_path_guard():
    source = APP_PATH.read_text(encoding="utf-8") # AI辅助生成：GLM-5, 2026-03-10
    assert '@app.route("/kb-pdfs/<path:filename>")' in source
    assert "safe_name = os.path.basename(filename)" in source
    assert 'source_bucket = str(request.args.get("source") or "").strip().lower()' in source
    assert "if source_bucket in KB_PDF_DIRS:" in source


def test_multi_kg_routes_are_registered_without_replacing_legacy_routes():
    source = APP_PATH.read_text(encoding="utf-8")
    assert '@app.route("/api/kb/graph", methods=["GET"])' in source
    assert '@app.route("/api/kb/graphs", methods=["GET"])' in source
    assert '@app.route("/api/kb/graph/route-query", methods=["POST"])' in source
    assert '@app.route("/api/kb/node/<node_id>", methods=["GET"])' in source
    assert "if kg_type:" in source
    assert "clinical_graph_view() if view == \"clinical\"" in source


def test_route_query_uses_privacy_minimized_run_context():
    source = APP_PATH.read_text(encoding="utf-8")
    assert (
        'def _build_kg_run_context(run, events, current_dag_node="", question=""):'
        in source
    )
    assert "from .kg_context import build_run_context" in source
    assert "modality_normalizer=_normalize_uploaded_modalities" in source


def test_route_query_accepts_real_run_case_context_and_question_only_inputs():
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'file_id = str(data.get("file_id") or "").strip()' in source
    assert "patient_id_raw = data.get(\"patient_id\")" in source
    assert 'run_id.lower().startswith("case:")' in source
    assert '"source": source' in source
    assert '"confidence_cap": confidence_cap' in source
    assert '"negative_result_terms": context.get("negative_result_terms") or []' in source


def test_related_graph_keeps_selection_and_requires_explicit_run_context():
    source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    assert "选择本轮任务" in source
    assert "onSelectCandidate={selectKnowledgeCandidate}" in source
    assert 'requestedType === "related" && !runId && !fileId && !patientId && !q' in source
    assert 'setKbSelectedType(requestedType === "related" && !(runId || q) ? "all" : requestedType)' not in source


def test_file_or_patient_context_resolves_run_before_related_graph_load():
    source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    assert "const needsRunResolution = Boolean(" in source
    assert 'await loadKbGraph("", true, "related", resolvedContext)' in source
    assert "无法根据当前 file_id/patient_id 定位有效任务" in source


def test_frontend_distinguishes_agent_runs_from_recovered_cases():
    source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    assert "Agent 任务" in source
    assert "历史病例" in source
    assert "病例上下文" in source
    assert "kg nodes 待选择任务" in source
    assert "negative_result_terms" in source
