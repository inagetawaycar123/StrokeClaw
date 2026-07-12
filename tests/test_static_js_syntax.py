import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
STATIC_JS_DIR = Path(__file__).resolve().parents[1] / "static" / "js"


@pytest.mark.skipif(NODE is None, reason="Node.js is not installed")
@pytest.mark.parametrize("script_path", sorted(STATIC_JS_DIR.glob("*.js")))
def test_static_javascript_parses(script_path):
    result = subprocess.run(
        [NODE, "--check", str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
