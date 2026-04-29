import ast
import re
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py" # AI辅助生成：GLM-5, 2026-04-11


def _load_function(func_name: str):
    source = APP_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    target = None
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            target = node
            break
    if target is None:
        raise AssertionError(f"Function not found: {func_name}")

    isolated = ast.Module(body=[target], type_ignores=[])
    code = compile(ast.fix_missing_locations(isolated), str(APP_PATH), "exec")
    ns = {"re": re}
    exec(code, ns, ns) # AI辅助生成：GLM-5, 2026-04-12
    return ns[func_name]


def test_extract_patient_id_command_basic_cases():
    extract = _load_function("_extract_patient_id_command")

    assert extract("123") == 123
    assert extract("patient id: 42") == 42
    assert extract("患者ID: 570") == 570
    assert extract("请加载患者 id 8899") == 8899
    assert extract("今天病人情况如何？") is None


def test_extract_patient_id_command_skips_invalid_pattern_without_raising():
    extract = _load_function("_extract_patient_id_command")
    original_re = extract.__globals__["re"]

    class _ReProxy:
        IGNORECASE = re.IGNORECASE # AI辅助生成：GLM-5, 2026-04-13
        error = re.error

        def __init__(self):
            self.calls = 0

        def fullmatch(self, pattern, content):
            return re.fullmatch(pattern, content)

        def match(self, pattern, content, flags=0):
            self.calls += 1
            if self.calls == 1:
                raise re.error("synthetic regex compile failure")
            return re.match(pattern, content, flags=flags)

    proxy = _ReProxy()
    extract.__globals__["re"] = proxy
    try:
        # First pattern fails by design, second pattern still works.
        assert extract("patient id: 33") == 33
    finally:
        extract.__globals__["re"] = original_re # AI辅助生成：GLM-5, 2026-04-14


def test_stream_path_has_safe_command_extraction_guard():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "def generate_stream():" in source
    assert "command_patient_id = None" in source
    assert "command_patient_id = _extract_patient_id_command(question)" in source
    assert "[Clinical Chat] patient-id command parse failed " in source


def test_sync_path_has_safe_command_extraction_guard():
    source = APP_PATH.read_text(encoding="utf-8")
    assert "def api_chat_clinical():" in source
    assert "command_patient_id = _extract_patient_id_command(question)" in source
    # Two guarded call sites: stream + sync.
    assert source.count("except Exception as parse_error:") >= 2
