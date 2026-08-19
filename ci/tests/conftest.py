"""Fixtures da suíte que testa o testador.

Cada teste monta um repositório FALSO em tmp_path com as marcas da raiz, uma
célula e um exportador controlável. Assim dá para quebrar o instrumento de
medição de propósito sem encostar no repositório real — que é justamente o que
a prova C (instrumentation failure) exige.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import MARCAS_DA_RAIZ  # noqa: E402


def bash_utilizavel() -> str | None:
    """Devolve um bash que PROVADAMENTE roda, ou None.

    `shutil.which("bash")` no Windows encontra primeiro o stub do WSL em
    System32, que estoura `execvpe(/bin/bash) failed` ao rodar script do Git
    Bash. Procurar não é suficiente: aqui cada candidato é sondado de verdade
    antes de ser aceito — a mesma regra que o resto desta CI segue.
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

CONTRATO_MINIMO = {
    "openapi": "3.1.0",
    "info": {"title": "Falsa API", "version": "1.0.0"},
    "paths": {"/ping": {"get": {"responses": {"200": {"description": "ok"}}}}},
}


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

    def congelar(self, celula: str, doc: dict | str) -> Path:
        destino = self.raiz / "contracts" / f"{celula}.openapi.yaml"
        conteudo = doc if isinstance(doc, str) else json.dumps(doc, indent=2)
        destino.write_text(conteudo, encoding="utf-8")
        return destino

    def exportador(self, celula: str, corpo: str) -> list[str]:
        """Instala um exportador de mentira e devolve o comando que o roda."""
        script = self.raiz / "services" / celula / "exportador_falso.py"
        script.write_text(corpo, encoding="utf-8")
        return [sys.executable, "exportador_falso.py"]

    def exportador_que_imprime(self, celula: str, doc: dict) -> list[str]:
        corpo = "import json, sys\n" f"sys.stdout.write(json.dumps({doc!r}))\n"
        return self.exportador(celula, corpo)


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


@pytest.fixture
def celula_ok(repo: RepoFalso) -> RepoFalso:
    """Repositório falso no estado correto: contrato vivo == congelado."""
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_MINIMO),
            }
        }
    )
    return repo
