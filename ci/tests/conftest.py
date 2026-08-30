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

# A autenticação que CONTRATO_MINIMO declara: /ping não tem `security` própria e
# o documento não tem `security` na raiz — logo, rota pública.
AUTENTICACAO_MINIMA = {"GET /ping": False}

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

    def script(self, celula: str, nome: str, corpo: str) -> list[str]:
        """Instala um script auxiliar com nome PRÓPRIO e devolve o comando.

        O nome explícito existe porque reaproveitar o mesmo arquivo para
        exportador e sonda já causou colisão silenciosa num teste — dois papéis
        diferentes apontando para o mesmo caminho.
        """
        destino = self.raiz / "services" / celula / nome
        destino.write_text(corpo, encoding="utf-8")
        return [sys.executable, nome]

    def sonda_auth(self, celula: str, autenticacao: dict[str, bool]) -> list[str]:
        """Sonda de autenticação de mentira, para o repositório falso.

        A sonda real importa Django e lê `op.auth_callbacks` do django-ninja; o
        repositório falso não tem célula Django nenhuma. O que os testes precisam
        exercitar é a SEMÂNTICA do portão (concorda ⇒ PASS, diverge ⇒ FAIL, não
        rodou ⇒ ERROR), não o django-ninja.
        """
        script = self.raiz / "services" / celula / "sonda_falsa.py"
        corpo = "import json, sys\n" f"sys.stdout.write(json.dumps({autenticacao!r}))\n"
        script.write_text(corpo, encoding="utf-8")
        return [sys.executable, "sonda_falsa.py"]

    def exportador_que_imprime(self, celula: str, doc: dict) -> list[str]:
        corpo = "import json, sys\n" f"sys.stdout.write(json.dumps({doc!r}))\n"
        return self.exportador(celula, corpo)


# ---------------------------------------------------------------------------
# OS GERADOS DE `armadilhas/` NÃO MORAM MAIS NO GIT (30/08/2026, armadilhas/200):
# o índice inteiro era reescrito por todo robô que aprendia uma lição, e dois
# robôs do mesmo lote colidiam sem ter escrito uma linha em comum. Quem os
# materializa passou a ser a integração.
#
# Esta fixture fecha a METADE QUE FALTOU e que deixou a `main` vermelha no mesmo
# dia: o job `guardas do repositório` do `alarme-main` roda esta suíte SEM passar
# pelas muralhas, então numa árvore recém-clonada os testes do sino liam um
# `armadilhas/SINAIS.json` inexistente e morriam em
# `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. O portão de
# deploy então recusou publicar — fail-closed, como devia — e nenhum merge
# chegava ao site.
#
# Por que aqui e não num passo de YAML: um passo conserta UM workflow. Esta
# suíte tem três chamadores — `muralhas`, `alarme-main` e a pessoa que roda
# `pytest ci/tests` na mão — e o terceiro não tem YAML nenhum. Materializar na
# porta da suíte cobre os três de uma vez, que é a mesma escolha de "uma
# definição só" que o resto desta casa faz.
@pytest.fixture(scope="session", autouse=True)
def _materializar_os_gerados_das_armadilhas() -> None:
    """Garante `INDICE.md`, `GUARDAS.json` e `SINAIS.json` antes de qualquer teste."""
    import indice_de_armadilhas

    indice_de_armadilhas.rodar(raiz=CI.parent, conferir=False)


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
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
            }
        }
    )
    return repo
