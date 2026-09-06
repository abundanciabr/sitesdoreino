"""O orçamento de mudança mede CÓDIGO, não a papelada que a casa obriga.

O teto de 15 arquivos existe para "corrigir o Pix" não voltar com 42 arquivos.
Só que ele contava tudo o que aparece no diff, e desde 31/08/2026 a casa obriga
cada PR a carregar a própria escrituração: o registro do livro (o portão recusa
pouso sem ele), os eventos da fila, o mapa do site. Seis arquivos que ninguém
pode remover passaram a comer o orçamento do trabalho de verdade.

O caso medido é o PR #1161 (degrau 06 da escada do portfólio): 19 arquivos, 13
de código e 6 de escrituração, reprovado por um contador que nunca teve a
intenção de barrar aquilo. Para vencer o contador, a sessão aplicou a etiqueta
`arquitetural` num PR que não é arquitetural, e é assim que uma etiqueta morre:
virando senha de contador em vez de significar "este PR muda a arquitetura".

O que estes testes prendem, e é a metade que importa: a isenção vale SÓ para
os caminhos de escrituração. PR com 16 arquivos de código continua reprovando,
tenha ele escrituração junto ou não. Se a isenção pudesse salvar código, o
portão teria morrido no mesmo dia.

Os dois guardas do orçamento são medidos aqui, porque uma divergência entre
eles é o pior desfecho possível (muralha verde e a pista recusando o pouso, ou
o contrário): `ci/orcamento-de-mudanca.sh` (as muralhas, rodando de verdade sob
bash contra um repositório git descartável) e `ci/mergear.py` (a catraca da
pista, alimentada com a resposta que o `gh` devolveria).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import mergear
from _nucleo import Estado
from conftest import BASH
from divida_do_livro import PASTAS_DE_ESCRITURACAO

CI = Path(__file__).resolve().parents[1]
SCRIPT = CI / "orcamento-de-mudanca.sh"

PASS = 0
FAIL = 1

# Os seis arquivos de escrituração do PR #1161, na ordem em que apareceram no
# diff. Não é amostra inventada: é o caso que motivou a mudança.
ESCRITURACAO_DO_1161 = [
    "fila/eventos/20260906-013910-TAR-182-reivindicada.json",
    "fila/eventos/20260906-015957-TAR-215-bloqueada.json",
    "fila/eventos/20260906-020336-TAR-182-concluida.json",
    "fila/tarefas/215-portfolio-do-aluno-os-dois-pares.json",
    "painel/mapa-do-site.json",
    "painel/registros/20260906-021-a-prancheta-reconhece-o-aluno.js",
]


def _codigo(n: int) -> list[str]:
    return [f"services/pages/apps/core/modulo_{i}.py" for i in range(n)]


# ---------------------------------------------------------------------------
# A catraca da pista (ci/mergear.py)
# ---------------------------------------------------------------------------


def _pr(caminhos: list[str], labels: tuple[str, ...] = ()) -> dict:
    return {
        "labels": [{"name": nome} for nome in labels],
        "files": [{"path": caminho} for caminho in caminhos],
    }


def _pior(resultados) -> Estado:
    return max((r.estado for r in resultados), key=lambda e: e.gravidade)


def test_catraca_a_codigo_dentro_do_teto_com_escrituracao_passa() -> None:
    """(a) O caso do PR #1161: 12 de código + 6 de escrituração = 18 no diff."""
    caminhos = _codigo(12) + ESCRITURACAO_DO_1161
    assert len(caminhos) > mergear.LIMITE_DE_ARQUIVOS
    assert _pior(mergear.checar_labels(_pr(caminhos))) is Estado.PASS


def test_catraca_b_codigo_acima_do_teto_sozinho_reprova() -> None:
    """(b) Sem escrituração nenhuma, o teto é exatamente o de sempre."""
    caminhos = _codigo(mergear.LIMITE_DE_ARQUIVOS + 1)
    assert _pior(mergear.checar_labels(_pr(caminhos))) is Estado.FAIL


def test_catraca_c_escrituracao_nao_salva_codigo_estourado() -> None:
    """(c) A isenção não é uma segunda válvula: 16 de código reprovam do mesmo
    jeito com 6 de escrituração ao lado. É este teste que impede o portão de
    virar porta aberta ("metade do meu PR é painel/, então posso 40")."""
    caminhos = _codigo(mergear.LIMITE_DE_ARQUIVOS + 1) + ESCRITURACAO_DO_1161
    assert _pior(mergear.checar_labels(_pr(caminhos))) is Estado.FAIL


def test_catraca_conta_apenas_o_codigo_na_mensagem() -> None:
    """Quem lê o veredito precisa ver o número que foi medido, não o do diff."""
    caminhos = _codigo(12) + ESCRITURACAO_DO_1161
    (resultado,) = [
        r for r in mergear.checar_labels(_pr(caminhos)) if r.nome == "orçamento"
    ]
    assert "12" in resultado.resumo, resultado.resumo


@pytest.mark.parametrize("pasta", PASTAS_DE_ESCRITURACAO)
def test_catraca_isenta_toda_pasta_de_escrituracao(pasta: str) -> None:
    """A lista de pastas isentas é a de `ci/divida_do_livro.py`, e este teste
    percorre a constante em vez de repeti-la: pasta nova entra aqui sozinha, e
    uma segunda lista escondida no portão fica vermelha na hora."""
    caminhos = _codigo(mergear.LIMITE_DE_ARQUIVOS) + [f"{pasta}algum-arquivo.json"]
    assert len(caminhos) > mergear.LIMITE_DE_ARQUIVOS
    assert _pior(mergear.checar_labels(_pr(caminhos))) is Estado.PASS


# ---------------------------------------------------------------------------
# As muralhas (ci/orcamento-de-mudanca.sh) — o script real, sob bash
# ---------------------------------------------------------------------------

bash_e_git = pytest.mark.skipif(
    BASH is None or shutil.which("git") is None,
    reason="o portão precisa de bash utilizável E git no PATH",
)


def _git(raiz: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"git {args} falhou:\n{proc.stderr}"
    return (proc.stdout or "").strip()


@pytest.fixture
def repo_git(tmp_path: Path) -> tuple[Path, str]:
    raiz = tmp_path / "repo-git"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "ci@teste.local")
    _git(raiz, "config", "user.name", "Suite do orcamento")
    _git(raiz, "config", "commit.gpgsign", "false")
    (raiz / "README.md").write_text("base\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    return raiz, _git(raiz, "rev-parse", "HEAD")


def _comitar(raiz: Path, caminhos: list[str]) -> None:
    for rel in caminhos:
        arquivo = raiz / rel
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("conteudo\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "mudança do cenário")


def _rodar_portao(raiz: Path, base: str, labels: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "BASE_REF": base, "PR_LABELS": labels}
    return subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
        check=False,
    )


@bash_e_git
def test_muralha_a_codigo_dentro_do_teto_com_escrituracao_passa(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, _codigo(12) + ESCRITURACAO_DO_1161)
    proc = _rodar_portao(raiz, base)
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


@bash_e_git
def test_muralha_b_codigo_acima_do_teto_sozinho_reprova(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, _codigo(16))
    proc = _rodar_portao(raiz, base)
    assert proc.returncode == FAIL, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "arquitetural" in proc.stdout


@bash_e_git
def test_muralha_c_escrituracao_nao_salva_codigo_estourado(repo_git) -> None:
    raiz, base = repo_git
    _comitar(raiz, _codigo(16) + ESCRITURACAO_DO_1161)
    proc = _rodar_portao(raiz, base)
    assert proc.returncode == FAIL, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "16 arquivos de código" in proc.stdout, (
        "a recusa precisa dizer que o número medido é o de CÓDIGO, senão quem "
        f"lê procura os 22 do diff:\n{proc.stdout}"
    )


@bash_e_git
@pytest.mark.parametrize("pasta", PASTAS_DE_ESCRITURACAO)
def test_muralha_isenta_toda_pasta_de_escrituracao(repo_git, pasta: str) -> None:
    """Mesmo guarda de deriva da catraca, do lado do bash: o script lê as pastas
    de `ci/divida_do_livro.py` em vez de guardar uma cópia."""
    raiz, base = repo_git
    _comitar(raiz, _codigo(15) + [f"{pasta}algum-arquivo.json"])
    proc = _rodar_portao(raiz, base)
    assert proc.returncode == PASS, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
