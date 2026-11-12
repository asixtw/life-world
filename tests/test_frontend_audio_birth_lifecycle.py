"""由既有 pytest 入口執行實際前端腳本；DOM／Audio 替身並非原生瀏覽器驗收。"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("filename", ["frontend_audio_lifecycle.cjs", "frontend_birth_lifecycle.cjs", "frontend_quantity.cjs"])
def test_frontend_lifecycle_contract(filename):
    """Node 保留每個子測試的輸出，任何失敗都回傳非零狀態。"""
    node = os.environ.get("LIFEWORLD_NODE") or shutil.which("node")
    if not node:
        pytest.skip("需要 Node.js 執行實際前端生命週期契約")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, "--test", str(root / "tests" / filename)], cwd=root,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
