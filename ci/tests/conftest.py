"""Fixtures da suíte de `ci/`: raiz falsa em tmp_path e um bash que roda de verdade."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

# UTF-8 em todo filho que esta suíte criar: no Windows um filho Python escreve
# pela codepage do console enquanto o teste lê utf-8, e a asserção de texto
# reprova sozinha. As ferramentas de `ci/` se protegem em
# `_nucleo.configurar_saida()`; o pytest não passa por lá.
os.environ.setdefault("PYTHONUTF8", "1")

from _nucleo import MARCAS_DA_RAIZ  # noqa: E402


def bash_utilizavel() -> str | None:
    """Devolve um bash que PROVADAMENTE roda, ou None.

    `shutil.which("bash")` no Windows encontra primeiro o stub do WSL em
    System32, que estoura `execvpe(/bin/bash) failed` ao rodar script do Git
    Bash. Cada candidato é sondado de verdade antes de ser aceito.
    """
    import shutil
    import subprocess

    candidatos = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        "/usr/bin/bash",
        "/bin/bash",
    ]
    encontrado = shutil.which("bash")
    if encontrado:
        candidatos.append(encontrado)
    for candidato in candidatos:
        if not Path(candidato).exists():
            continue
        try:
            proc = subprocess.run(
                [candidato, "-c", "printf sondagem-ok"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except OSError:
            continue
        if proc.returncode == 0 and "sondagem-ok" in (proc.stdout or ""):
            return candidato
    return None


BASH = bash_utilizavel()


@pytest.fixture(autouse=True)
def recarga_da_aplicacao_para_provisionadores(request, tmp_path, monkeypatch):
    """Os testes de env executam Bash real; a recarga externa fica simulada."""
    if not request.node.path.name.startswith("test_provisionar_"):
        return
    binarios = tmp_path / "bin-aplicacao"
    binarios.mkdir()
    programa = binarios / "python3"
    programa.write_text(
        "#!/usr/bin/env bash\n"
        'case "${1:-}" in\n'
        '  */recarregar-aplicacao.py)\n'
        '    if [ "${PROVISIONAR_RECARGA_FALHA:-0}" = 1 ]; then exit 37; fi\n'
        '    printf "%s\\n" APLICACAO-RECARREGADA-E-PROVADA\n'
        '    exit 0 ;;\n'
        'esac\n'
        'exec python "$@"\n',
        encoding="utf-8",
    )
    programa.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binarios}{os.pathsep}{os.environ.get('PATH', '')}")


@dataclass
class RepoFalso:
    raiz: Path

    @property
    def manifesto(self) -> Path:
        return self.raiz / "ci" / "manifesto-de-contratos.json"

    def declarar(self, celulas: dict) -> None:
        self.manifesto.write_text(
            json.dumps({"celulas": celulas}, ensure_ascii=False), encoding="utf-8"
        )

    def criar_celula(self, nome: str) -> Path:
        destino = self.raiz / "services" / nome
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "Makefile").write_text("ci:\n\t@echo falso\n", encoding="utf-8")
        return destino


@pytest.fixture
def repo(tmp_path: Path) -> RepoFalso:
    raiz = tmp_path / "repo-falso"
    for marca in MARCAS_DA_RAIZ:
        alvo = raiz / marca
        if "." in marca:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(f"# {marca} de mentira\n", encoding="utf-8")
        else:
            alvo.mkdir(parents=True, exist_ok=True)
    return RepoFalso(raiz=raiz)
