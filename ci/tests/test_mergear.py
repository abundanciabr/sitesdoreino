"""TESTAR O TESTADOR — o merge guardado.

[INV-CI01] Este portão é o único que fica entre um PR vermelho e a `main`,
porque o GitHub não oferece required checks em repositório privado de conta
pessoal. Se ele errar para o lado do verde, não há segunda barreira.

Todos os testes aqui são offline: alimentam as funções com a resposta que o
`gh` devolveria, e conferem o veredito. O que se valida é a SEMÂNTICA, não o
formato das mensagens.

O caso que mais importa é `test_sem_checks_e_error`: um PR sem check algum é
indistinguível de um PR cujos workflows nem dispararam. Ler isso como "não vi
nada errado, então pode" é o falso positivo original em outra roupa.
"""

from __future__ import annotations

from typing import Any

import pytest

import mergear
from _nucleo import Estado


def _check(nome: str, conclusao: str = "SUCCESS", status: str = "COMPLETED") -> dict:
    return {
        "__typename": "CheckRun",
        "name": nome,
        "status": status,
        "conclusion": conclusao,
    }


def _pr(**alteracoes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": 99,
        "title": "um PR de mentira",
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "baseRefName": "main",
        "headRefName": "agent/falso",
        "url": "https://example.invalid/pr/99",
        "author": {"login": "ninguem"},
        "labels": [],
        "files": [{"path": "ci/algo.py"}],
        "commits": [{"oid": "abc"}],
        "statusCheckRollup": [
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("detectar"),
        ],
    }
    base.update(alteracoes)
    return base


def _pior(resultados) -> Estado:
    return max((r.estado for r in resultados), key=lambda e: e.gravidade)


# ---------------------------------------------------------------------------
# Checks — o coração do portão
# ---------------------------------------------------------------------------


def test_tudo_verde_passa() -> None:
    assert _pior(mergear.checar_checks(_pr())) is Estado.PASS


def test_sem_checks_e_error() -> None:
    """Nenhum check reportado NÃO é sinal verde.

    Um PR sem check é indistinguível de um PR cujos workflows não chegaram a
    rodar. Aprovar isso seria mergear sem que nada tenha sido medido.
    """
    resultados = mergear.checar_checks(_pr(statusCheckRollup=[]))
    assert _pior(resultados) is Estado.ERROR


def test_check_vermelho_reprova() -> None:
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas", "FAILURE"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


@pytest.mark.parametrize(
    "conclusao", ["FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", ""]
)
def test_qualquer_conclusao_que_nao_seja_sucesso_reprova(conclusao: str) -> None:
    pr = _pr(
        statusCheckRollup=[_check("muralhas", conclusao), _check("ci-celula-gate")]
    )
    assert _pior(mergear.checar_checks(pr)) is not Estado.PASS


def test_check_ainda_rodando_e_error() -> None:
    """Mergear com check em andamento é aprovar antes da medição terminar."""
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas", "", "IN_PROGRESS"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.ERROR


def test_skip_declarado_e_permitido() -> None:
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("ci-celula", "SKIPPED"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.PASS


def test_skip_nao_declarado_reprova() -> None:
    """Pulo sem declaração é pulo inferido — o buraco que o INV-CI01 fecha."""
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("algum-check-novo", "SKIPPED"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


@pytest.mark.parametrize("ausente", list(mergear.CHECKS_OBRIGATORIOS))
def test_check_obrigatorio_ausente_e_error(ausente: str) -> None:
    """Workflow renomeado, desabilitado ou que não disparou não é aprovação."""
    rollup = [_check(n) for n in mergear.CHECKS_OBRIGATORIOS if n != ausente]
    assert _pior(mergear.checar_checks(_pr(statusCheckRollup=rollup))) is Estado.ERROR


# ---------------------------------------------------------------------------
# Estado do PR e mergeabilidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["MERGED", "CLOSED"])
def test_pr_que_nao_esta_aberto_reprova(estado: str) -> None:
    assert mergear.checar_estado(_pr(state=estado)).estado is Estado.FAIL


def test_rascunho_reprova() -> None:
    assert mergear.checar_estado(_pr(isDraft=True)).estado is Estado.FAIL


def test_conflito_reprova() -> None:
    assert (
        mergear.checar_mergeabilidade(_pr(mergeable="CONFLICTING")).estado
        is Estado.FAIL
    )


def test_mergeabilidade_desconhecida_e_error() -> None:
    """O GitHub calcula isso de forma assíncrona; 'não sei' não é 'pode'."""
    assert (
        mergear.checar_mergeabilidade(_pr(mergeable="UNKNOWN")).estado is Estado.ERROR
    )


# ---------------------------------------------------------------------------
# Labels — as mesmas regras das muralhas, conferidas antes do clique
# ---------------------------------------------------------------------------


def test_orcamento_estourado_sem_label_reprova() -> None:
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS + 1)]
    assert _pior(mergear.checar_labels(_pr(files=arquivos))) is Estado.FAIL


def test_orcamento_estourado_com_label_passa() -> None:
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS + 1)]
    pr = _pr(files=arquivos, labels=[{"name": "arquitetural"}])
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


def test_contrato_sem_label_reprova() -> None:
    pr = _pr(files=[{"path": "contracts/catalogo.openapi.yaml"}])
    assert _pior(mergear.checar_labels(pr)) is Estado.FAIL


def test_contrato_com_label_passa() -> None:
    pr = _pr(
        files=[{"path": "contracts/catalogo.openapi.yaml"}],
        labels=[{"name": "contrato"}],
    )
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


# ---------------------------------------------------------------------------
# Fronteira
# ---------------------------------------------------------------------------


def test_excecao_inesperada_vira_error() -> None:
    def estoura() -> int:
        raise RuntimeError("bug dentro do próprio portão")

    assert mergear._blindar("mergear", estoura)() == 2


def test_skips_permitidos_tem_motivo_escrito() -> None:
    """SKIP sem motivo declarado é SKIP inferido, e SKIP inferido é proibido."""
    assert mergear.SKIPS_PERMITIDOS
    for nome, motivo in mergear.SKIPS_PERMITIDOS.items():
        assert motivo.strip(), f"'{nome}' está na lista de skips sem justificativa"
