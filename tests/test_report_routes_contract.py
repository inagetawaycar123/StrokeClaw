from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py"


def test_report_context_route_and_structured_bundle_are_additive():
    source = APP_PATH.read_text(encoding="utf-8")
    adapter = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "compat"
        / "adapters.py"
    ).read_text(encoding="utf-8")

    assert '@app.route("/api/report/context", methods=["GET"])' in source
    assert "ensure_structured_report_v2(" in source
    assert '"structured_report_v2": _as_dict(payload.get("structured_report_v2"))' in adapter
