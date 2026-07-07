from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py"


def test_compat_routes_are_additive_and_do_not_replace_existing_cockpit_route():
    source = APP_PATH.read_text(encoding="utf-8")

    assert '@app.route("/api/cockpit/overview", methods=["GET"])' in source
    assert '@app.route("/api/compat/skill-registry", methods=["GET"])' in source
    assert '@app.route("/api/compat/clinical-decision-bundle", methods=["GET"])' in source
    assert "build_clinical_decision_bundle(" in source
    assert "get_skill_registry()" in source
