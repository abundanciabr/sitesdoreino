"""TESTAR O TESTADOR — a cadeia que decide o merge, não só o gate isolado.

[INV-CI01] Um portão fail-closed não basta: a CADEIA que decide o merge também
precisa ser. O elo mais frágil era o job terminal de `.github/workflows/
ci-celula.yml`, que aceitava qualquer `skipped` como verde:

    git falha -> célula vazia -> job `rodar` pulado -> gate verde -> merge

Estes testes extraem o script de decisão DO PRÓPRIO YAML e o executam sob bash
com cada estado possível dos jobs. Não é uma reimplementação da lógica: é o
mesmo texto que o GitHub Actions vai rodar, lido do arquivo. Se alguém afrouxar
o gate no YAML, estes testes ficam vermelhos.

O que isto NÃO prova: que o GitHub Actions orquestra os jobs como modelado
(que `detectar` falhando torna `rodar` `skipped`, etc.). Isso é comportamento
da plataforma e só a CI canônica confirma. Aqui provamos a tabela de decisão.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import BASH

CI = Path(__file__).resolve().parents[1]
WORKFLOW = CI.parent / ".github" / "workflows" / "ci-celula.yml"

# O gate ANTIGO, preservado como controle histórico. É contra ele que se mede o
# que mudou — sem isto, "corrigimos o bypass" seria narrativa, não evidência.
GATE_ANTIGO = """
R="$R"
if [ "$R" = "failure" ] || [ "$R" = "cancelled" ]; then
  echo "ci-celula: a celula tocada falhou (rodar=$R)"; exit 1
fi
echo "ci-celula-gate OK (rodar=$R)"
"""

pytestmark = pytest.mark.skipif(
    BASH is None, reason="nenhum bash utilizável foi encontrado neste ambiente"
)


def _script_do_gate() -> str:
    """Lê o script de decisão direto do workflow — nunca de uma cópia."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["gate"]["steps"]
    scripts = [p["run"] for p in passos if "run" in p]
    assert len(scripts) == 1, f"esperava 1 step com `run` no gate, achei {len(scripts)}"
    return scripts[0]


def _rodar(script: str, **estado: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"PATH": "/usr/bin:/bin", **estado},
        timeout=60,
        check=False,
    )


def _estado(
    d_result: str = "success",
    d_status: str = "ok",
    celula: str = "catalogo",
    n: str = "1",
    r: str = "success",
) -> dict[str, str]:
    return {
        "D_RESULT": d_result,
        "D_STATUS": d_status,
        "CELULA": celula,
        "N": n,
        "R": r,
    }


# ---------------------------------------------------------------------------
# A tabela-verdade nova, estado por estado
# ---------------------------------------------------------------------------

VERDE = 0
VERMELHO = 1

TABELA = [
    # (descrição, estado, exit esperado)
    ("célula testada e verde ⇒ PASS", _estado(), VERDE),
    ("célula testada e vermelha ⇒ FAIL", _estado(r="failure"), VERMELHO),
    ("job da célula cancelado ⇒ ERROR", _estado(r="cancelled"), VERMELHO),
    (
        "célula detectada mas o job não rodou ⇒ ERROR",
        _estado(r="skipped"),
        VERMELHO,
    ),
    (
        "detecção concluiu e não há célula ⇒ SKIP permitido",
        _estado(celula="", n="0", r="skipped"),
        VERDE,
    ),
    (
        "sem célula mas o job rodou ⇒ ERROR (estado incoerente)",
        _estado(celula="", n="0", r="success"),
        VERMELHO,
    ),
    (
        "O BYPASS: detecção falhou ⇒ ERROR, nunca verde",
        _estado(d_result="failure", d_status="", celula="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção cancelada ⇒ ERROR",
        _estado(d_result="cancelled", d_status="", celula="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção pulada ⇒ ERROR",
        _estado(d_result="skipped", d_status="", celula="", n="", r="skipped"),
        VERMELHO,
    ),
    (
        "detecção 'passou' sem carimbar que mediu ⇒ ERROR",
        _estado(d_status="", celula="", n="0", r="skipped"),
        VERMELHO,
    ),
    (
        "diff toca 2 células e só uma foi testada ⇒ ERROR (escopo incompleto)",
        _estado(celula="checkout", n="2", r="success"),
        VERMELHO,
    ),
    (
        "contagem de células corrompida ⇒ ERROR",
        _estado(n="lixo"),
        VERMELHO,
    ),
    (
        "contagem de células ausente ⇒ ERROR",
        _estado(n=""),
        VERMELHO,
    ),
    (
        "estado desconhecido do job da célula ⇒ ERROR",
        _estado(r="alguma-coisa-nova-do-github"),
        VERMELHO,
    ),
]


@pytest.mark.parametrize(
    "descricao,estado,esperado", TABELA, ids=[t[0][:45] for t in TABELA]
)
def test_tabela_verdade_do_gate(
    descricao: str, estado: dict[str, str], esperado: int
) -> None:
    proc = _rodar(_script_do_gate(), **estado)
    assert proc.returncode == esperado, (
        f"{descricao}\nestado={estado}\n"
        f"exit={proc.returncode} (esperado {esperado})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_o_bypass_existia_de_verdade_no_gate_antigo() -> None:
    """Controle histórico: o gate ANTIGO ficava verde com a detecção quebrada.

    Sem esta prova, "corrigimos o bypass" seria apenas afirmação. Aqui o estado
    exato do bypass roda contra os dois scripts: o antigo aprova, o novo reprova.
    """
    estado_do_bypass = _estado(
        d_result="failure", d_status="", celula="", n="", r="skipped"
    )
    antigo = _rodar(GATE_ANTIGO, **estado_do_bypass)
    novo = _rodar(_script_do_gate(), **estado_do_bypass)

    assert antigo.returncode == 0, "o gate antigo deveria aprovar — é o bypass"
    assert novo.returncode != 0, "o gate novo NÃO pode aprovar o mesmo estado"


def test_gate_e_o_job_terminal_e_sempre_conclui() -> None:
    """Se o gate deixar de rodar `always()`, ele para de ser o check terminal."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    gate = doc["jobs"]["gate"]
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == {"detectar", "rodar"}


def test_deteccao_usa_o_runner_canonico() -> None:
    """O YAML não pode voltar a reimplementar a detecção de escopo em shell.

    A semântica de "quais células este PR toca" vive em ci/ci.py, que é o mesmo
    caminho que o agente roda localmente. Duplicá-la em YAML é como o drift
    entre runner local e CI canônica começa.
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["detectar"]["steps"]
    scripts = "\n".join(p["run"] for p in passos if "run" in p)
    assert "ci/ci.py --detectar-celulas" in scripts
    linhas_ativas = [
        ln for ln in scripts.splitlines() if not ln.lstrip().startswith("#")
    ]
    for proibido in ("|| true", "set +e"):
        ofensas = [ln.strip() for ln in linhas_ativas if proibido in ln]
        assert not ofensas, f"padrão de falso positivo em `detectar`: {ofensas}"


MURALHAS_YML = CI.parent / ".github" / "workflows" / "muralhas.yml"


def test_muralhas_usa_o_runner_canonico() -> None:
    """O workflow não pode listar os portões à mão.

    Enquanto o YAML enumerava `bash ci/cerca-de-celula.sh`, `bash ci/...` etc., a
    lista de muralhas do GitHub e a de `ci/ci.py` podiam divergir sem ninguém
    perceber — o agente rodaria um conjunto de portões, o CI outro. Agora os
    dois lados executam literalmente o mesmo comando.
    """
    doc = yaml.safe_load(MURALHAS_YML.read_text(encoding="utf-8"))
    scripts = "\n".join(
        p["run"] for p in doc["jobs"]["muralhas"]["steps"] if "run" in p
    )
    assert "ci/ci.py --apenas muralhas" in scripts
    assert "ci/ci.py --apenas testador" in scripts
    for portao in (
        "cerca-de-celula.sh",
        "orcamento-de-mudanca.sh",
        "guarda-de-segredos.sh",
    ):
        assert portao not in scripts, (
            f"o workflow voltou a chamar {portao} direto — a semântica dos "
            "portões precisa vir de ci/ci.py, não de uma lista paralela no YAML"
        )
