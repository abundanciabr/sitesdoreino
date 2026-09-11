"""Testa ci/resumo_de_teste.py com fixtures de JSON."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "resumo_de_teste.py"


def test_verde(tmp_path):
    result_file = tmp_path / ".test-result.json"
    result_file.write_text(json.dumps({
        "summary": {"total": 5, "passed": 5},
        "tests": []
    }))
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--arquivo", str(result_file)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "✅" in r.stdout


def test_vermelho(tmp_path):
    result_file = tmp_path / ".test-result.json"
    result_file.write_text(json.dumps({
        "summary": {"total": 3, "passed": 2, "failed": 1},
        "tests": [
            {"nodeid": "test_foo.py::test_bar", "outcome": "failed",
             "call": {"crash": {"message": "assert 1 == 2"}}}
        ]
    }))
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--arquivo", str(result_file)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "❌" in r.stdout
    assert "test_foo.py::test_bar" in r.stdout


def test_arquivo_ausente(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--arquivo", str(tmp_path / "nao_existe.json")],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
