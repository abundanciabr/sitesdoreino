"""Operações usam o código recebido mesmo com o GitHub indisponível."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("bash") is None, reason="atalho executado em Linux")
def test_operar_nao_depende_de_fetch(tmp_path):
    fonte = tmp_path / "fonte"
    fonte.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(fonte)], check=True, capture_output=True)
    (fonte / "arquivo").write_text("codigo recebido")
    subprocess.run(["git", "-C", str(fonte), "add", "."], check=True)
    subprocess.run(["git", "-C", str(fonte), "-c", "user.name=Teste", "-c",
                    "user.email=teste@example.invalid", "commit", "-m", "base"],
                   check=True, capture_output=True)
    raiz = tmp_path / "plataforma"
    repo = raiz / "codigo" / "repo.git"
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--bare", str(fonte), str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin",
                    str(tmp_path / "github-indisponivel")], check=True)
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "main"], text=True).strip()
    ferramenta = raiz / "codigo" / "ferramentas" / sha / "infra"
    ferramenta.mkdir(parents=True)
    (ferramenta / "publicar.py").write_text("import sys\nprint('EXECUTOU', *sys.argv[1:])\n")
    ambiente = {**os.environ, "PLATAFORMA_DIR": str(raiz)}
    resultado = subprocess.run(["sh", str(ROOT / "infra" / "plataforma.sh"),
                                "operar", "listar"], env=ambiente, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    assert "EXECUTOU operar listar" in resultado.stdout
    receber = subprocess.run(["sh", str(ROOT / "infra" / "plataforma.sh"), "receber"],
                              env=ambiente, capture_output=True, text=True)
    assert receber.returncode != 0  # Receber código novo continua consultando sua origem.
