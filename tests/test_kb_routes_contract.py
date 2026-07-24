from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py" # AI辅助生成：GLM-5, 2026-03-07


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
