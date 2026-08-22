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


def test_status_context_pendente_e_error() -> None:
    """StatusContext (API legada) não tem `status`; PENDING marca em andamento.

    Sem o `state` mapeado para "ainda rodando", um check nesse formato caía no
    `else: FAIL` — reportando "não passou" para um check que só não tinha
    terminado ainda.
    """
    pr = _pr(
        statusCheckRollup=[
            {"context": "servico-externo", "state": "PENDING"},
            _check("muralhas"),
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


def test_limite_de_arquivos_bate_com_orcamento_de_mudanca() -> None:
    """LIMITE_DE_ARQUIVOS é uma cópia solta do limite em orcamento-de-mudanca.sh.

    Duas fontes independentes para o mesmo número só ficam honestas se algo
    mecânico denuncia quando elas divergirem — do contrário é exatamente o
    tipo de deriva silenciosa que o INV-CI01 existe para eliminar.
    """
    import re

    script = (mergear.raiz_do_repo() / "ci" / "orcamento-de-mudanca.sh").read_text(
        encoding="utf-8"
    )
    match = re.search(r"\(\(\s*N\s*>\s*(\d+)\s*\)\)", script)
    assert (
        match
    ), "não encontrei o limite em ci/orcamento-de-mudanca.sh — script mudou de formato?"
    assert mergear.LIMITE_DE_ARQUIVOS == int(match.group(1))


def test_skips_permitidos_tem_motivo_escrito() -> None:
    """SKIP sem motivo declarado é SKIP inferido, e SKIP inferido é proibido."""
    assert mergear.SKIPS_PERMITIDOS
    for nome, motivo in mergear.SKIPS_PERMITIDOS.items():
        assert motivo.strip(), f"'{nome}' está na lista de skips sem justificativa"


# ---------------------------------------------------------------------------
# O merge em si (desde 22/08/2026 é o agente quem o executa — Lei 4)
# ---------------------------------------------------------------------------


def test_comando_de_merge_nao_usa_yes() -> None:
    """H6: o `gh` 2.97.0 não tem `--yes` em `pr merge` — o portão conferia tudo
    verde e quebrava exatamente na hora de agir. Se a flag voltar, este teste
    acusa antes de o próximo merge real quebrar (ARMADILHAS §5.9.1)."""
    for metodo in ("merge", "squash", "rebase"):
        cmd = mergear.comando_de_merge(99, metodo)
        assert "--yes" not in cmd
        assert "-y" not in cmd
        assert f"--{metodo}" in cmd
        assert "99" in cmd


def _relatorio_verde() -> "mergear.Relatorio":
    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(mergear.Resultado("tudo", Estado.PASS, "verde"))
    return relatorio


def _gh_de_mentira(chamadas: list, estado_apos_merge: str = "MERGED"):
    import json as _json

    def falso(argumentos, raiz, descricao, **kwargs):
        chamadas.append(list(argumentos))
        if argumentos[:2] == ["pr", "view"]:
            return _json.dumps(
                {
                    "state": estado_apos_merge,
                    "mergedBy": {"login": "robo"},
                    "mergeCommit": {"oid": "a" * 40},
                }
            )
        return ""

    return falso


def test_confirmo_errado_recusa_sem_chamar_o_gh(monkeypatch) -> None:
    """A defesa de identidade sobrevive no caminho não-interativo: --confirmo
    com número diferente do PR conferido cancela ANTES de qualquer merge —
    o erro que já aconteceu (PR #21 no lugar do #20) era de identidade."""
    chamadas: list = []
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "98"]) == 1
    assert chamadas == []


def test_confirmo_certo_mergeia_e_confere_o_estado(monkeypatch) -> None:
    """O caminho do agente: --confirmo com o número certo mergeia E confere no
    GitHub que o PR virou MERGED — o veredito nunca é o exit do disparo."""
    chamadas: list = []
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    assert ["pr", "merge", "99", "--merge"] in chamadas
    assert any(c[:2] == ["pr", "view"] for c in chamadas)


def test_merge_que_nao_vira_merged_reprova(monkeypatch) -> None:
    """Se o gh não recusar mas o PR não constar como MERGED, o resultado é
    FAIL — 'o comando não reclamou' não é evidência de merge (Lei 6)."""
    chamadas: list = []
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas, "OPEN"))
    assert mergear.main(["99", "--confirmo", "99"]) == 1
