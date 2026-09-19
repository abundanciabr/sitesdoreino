"""O CONGELAMENTO — a prova de que um rollback ativo não é desfeito sozinho.

RITOS §4 avisa, desde 23/08/2026: "enquanto o rollback estiver ATIVO, não
mergeie nada que toque `infra/`". Aquele aviso foi escrito quando o merge era
um gesto humano. Desde 13/09/2026 quem integra é `ci/mergear.py --automatico`,
acordado por `workflow_run` e por um cron de 15 minutos, sem etiqueta, sem
revisor e sem ninguém no circuito. Medido em 18/09/2026:

    git grep -ic "rollback\\|revers" -- ci/mergear.py ci/portao_de_deploy.py

devolvia ZERO nos dois. Nada no caminho de integração sabia que existia um
rollback ativo, e um rollback das 2h da manhã podia ser desfeito em silêncio,
com o run verde, em até 15 minutos.

Os dois sentidos são provados aqui, porque um portão que recusa sempre não é
portão, é paralisia: com a célula congelada a integração é RECUSADA, e sem
congelamento (ou com o prazo vencido) ela PASSA.

Tudo roda offline: as referências do servidor e o `git` de escrita são
injetados. Um guarda que só soubesse falar com o GitHub de verdade não
conseguiria encenar justamente os estados que decidem se ele presta.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import mergear  # noqa: E402
import rollback  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
AGORA = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)


def _corpo(celula: str, *, horas: float = 6, **extra: Any) -> dict[str, Any]:
    corpo = {
        "tipo": "congelamento",
        "celula": celula,
        "alvo": "b" * 40,
        "motivo": "checkout devolvendo 500 desde o deploy das 14h",
        "criado_em": AGORA.isoformat(),
        "expira_em": (AGORA + timedelta(hours=horas)).isoformat(),
    }
    corpo.update(extra)
    return corpo


def _par(celula: str, **kwargs: Any) -> tuple[str, str]:
    """O par (referência, mensagem do commit) do jeito que o servidor devolve."""
    return (
        f"{rollback.NS_CONGELAMENTO}/{celula}",
        json.dumps(_corpo(celula, **kwargs), ensure_ascii=False, sort_keys=True),
    )


def _pr(**alteracoes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": 99,
        "title": "um PR de mentira",
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "baseRefName": "main",
        "headRefName": "agent/forum/algo",
        "headRefOid": "a" * 40,
        "author": {"login": "ninguem"},
        "labels": [],
        "files": [{"path": "services/forum/apps/nucleo/views.py"}],
        "statusCheckRollup": [
            {
                "__typename": "CheckRun",
                "name": nome,
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
            for nome in ("muralhas", "ci-celula-gate")
        ],
    }
    base.update(alteracoes)
    return base


def _gh_do_servidor(pares: list[tuple[str, str]]):
    """O `gh` que devolve as referências de congelamento e o corpo de cada uma."""
    refs = [
        {"ref": ref, "object": {"sha": f"{indice:040x}"}}
        for indice, (ref, _) in enumerate(pares)
    ]
    mensagens = {f"{indice:040x}": msg for indice, (_, msg) in enumerate(pares)}

    def falso(args: list[str], raiz: Path, descricao: str, **_: Any) -> str:
        alvo = args[-1]
        if alvo.endswith("/matching-refs/congelamentos"):
            return json.dumps(refs)
        return json.dumps({"message": mensagens[alvo.rsplit("/", 1)[-1]]})

    return falso


def _congelamento(relatorio) -> Any:
    achados = [r for r in relatorio.resultados if r.nome == "congelamento"]
    assert achados, (
        "`conferir` não consultou o congelamento. Sem essa consulta, a "
        "integração automática volta a desfazer o rollback em 15 minutos."
    )
    return achados[0]


# ---------------------------------------------------------------------------
# O portão recusa: o rollback ativo sobrevive ao cron
# ---------------------------------------------------------------------------


def test_pr_da_celula_congelada_e_recusado_pela_integracao(monkeypatch) -> None:
    """O caso que origina a tarefa, encenado inteiro pelo caminho real.

    Passa por `conferir`, e não pela checagem isolada, de propósito: o defeito
    medido não era a ausência de uma função, era a ausência da CONSULTA.
    """
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: RAIZ)
    monkeypatch.setattr(mergear, "carregar_pr", lambda raiz, numero: _pr())
    monkeypatch.setattr(mergear, "_gh", _gh_do_servidor([_par("forum")]))
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA)

    relatorio, _ = mergear.conferir(99)

    assert _congelamento(relatorio).estado is Estado.FAIL
    assert relatorio.estado is Estado.FAIL


def test_infra_nao_entra_com_qualquer_celula_congelada(monkeypatch) -> None:
    """RITOS §4, a frase literal, mecanizada.

    `deploy-infra` termina com `docker compose up -d` sem argumento, o que
    devolve TODAS as células ao `:main` — inclusive a que acabou de voltar.
    Por isso o congelamento de UMA célula fecha `infra/` para todas.
    """
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA)
    monkeypatch.setattr(mergear, "_gh", _gh_do_servidor([_par("checkout")]))

    resultado = mergear.checar_congelamento(
        RAIZ, _pr(files=[{"path": "infra/docker-compose.yml"}])
    )

    assert resultado.estado is Estado.FAIL


# ---------------------------------------------------------------------------
# O portão deixa passar: recusar sempre não é portão, é paralisia
# ---------------------------------------------------------------------------


def test_sem_congelamento_a_integracao_passa(monkeypatch) -> None:
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: RAIZ)
    monkeypatch.setattr(mergear, "carregar_pr", lambda raiz, numero: _pr())
    monkeypatch.setattr(mergear, "_gh", _gh_do_servidor([]))
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA)

    relatorio, _ = mergear.conferir(99)

    assert _congelamento(relatorio).estado is Estado.PASS
    assert relatorio.estado is Estado.PASS


def test_celula_congelada_nao_trava_as_outras(monkeypatch) -> None:
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA)
    monkeypatch.setattr(mergear, "_gh", _gh_do_servidor([_par("checkout")]))

    resultado = mergear.checar_congelamento(RAIZ, _pr())

    assert resultado.estado is Estado.PASS


def test_congelamento_vencido_nao_trava_a_casa_para_sempre(monkeypatch) -> None:
    """O prazo é o que impede um congelamento esquecido de parar a fábrica."""
    monkeypatch.setattr(
        rollback, "agora_utc", lambda: AGORA + timedelta(hours=6, seconds=1)
    )
    monkeypatch.setattr(mergear, "_gh", _gh_do_servidor([_par("forum")]))

    resultado = mergear.checar_congelamento(RAIZ, _pr())

    assert resultado.estado is Estado.PASS


# ---------------------------------------------------------------------------
# Não medir nunca vira verde (INV-CI01)
# ---------------------------------------------------------------------------


def test_servidor_mudo_e_ERROR_nunca_PASS(monkeypatch) -> None:
    def quebrado(*args: Any, **kwargs: Any) -> str:
        raise ErroDeInstrumentacao("o gh não respondeu", "rede caída")

    monkeypatch.setattr(mergear, "_gh", quebrado)

    assert mergear.checar_congelamento(RAIZ, _pr()).estado is Estado.ERROR


def test_congelamento_ilegivel_e_ERROR_nao_ausencia_de_congelamento() -> None:
    """Uma referência que não dá para ler NÃO é 'então não há rollback ativo'."""
    with pytest.raises(ErroDeInstrumentacao):
        rollback.congelamentos_vivos(
            [(f"{rollback.NS_CONGELAMENTO}/forum", "isto não é json")]
        )


def test_congelamento_sem_prazo_e_ERROR() -> None:
    with pytest.raises(ErroDeInstrumentacao):
        rollback.congelamentos_vivos([_par("forum", expira_em="")])


# ---------------------------------------------------------------------------
# Ligar e desligar o estado
# ---------------------------------------------------------------------------


class _Saida:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _sem_congelamento(monkeypatch) -> None:
    monkeypatch.setattr(rollback, "_congelamento_no_servidor", lambda raiz, celula: None)


def test_congelar_cria_a_referencia_com_motivo_e_prazo(monkeypatch) -> None:
    vistos: list[tuple[str, dict, str]] = []

    def falso(raiz, ref, corpo, *, lease="", **kwargs):
        vistos.append((ref, corpo, lease))
        return True

    _sem_congelamento(monkeypatch)
    monkeypatch.setattr(rollback, "criar_ref_atomica", falso)
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA)

    ganhou, recado = rollback.congelar(RAIZ, "checkout", "o checkout caiu às 2h")

    assert ganhou, recado
    ref, corpo, lease = vistos[0]
    assert ref == f"{rollback.NS_CONGELAMENTO}/checkout"
    assert corpo["motivo"] == "o checkout caiu às 2h"
    assert lease == ""
    assert datetime.fromisoformat(corpo["expira_em"]) == AGORA + timedelta(
        hours=rollback.HORAS_DE_CONGELAMENTO
    )


def test_congelar_de_novo_renova_o_prazo_sem_soltar_a_casa(monkeypatch) -> None:
    """A renovação é UMA operação, com lease no sha observado.

    Apagar para recriar deixaria a casa descongelada no intervalo — justo
    durante o incidente que o congelamento existe para atravessar.
    """
    vistos: list[tuple[str, dict, str]] = []

    def falso(raiz, ref, corpo, *, lease="", **kwargs):
        vistos.append((ref, corpo, lease))
        return True

    monkeypatch.setattr(
        rollback,
        "_congelamento_no_servidor",
        lambda raiz, celula: ("f" * 40, _corpo(celula)),
    )
    monkeypatch.setattr(rollback, "criar_ref_atomica", falso)
    monkeypatch.setattr(rollback, "agora_utc", lambda: AGORA + timedelta(hours=5))

    ganhou, _ = rollback.congelar(RAIZ, "checkout", "o incidente continua de pé")

    assert ganhou
    _, corpo, lease = vistos[0]
    assert lease == "f" * 40
    assert datetime.fromisoformat(corpo["expira_em"]) > AGORA + timedelta(hours=6)


def test_congelar_celula_fora_do_manifesto_reprova(monkeypatch) -> None:
    """Um nome digitado errado congelaria o nada, em silêncio, numa emergência."""
    _sem_congelamento(monkeypatch)
    monkeypatch.setattr(
        rollback,
        "criar_ref_atomica",
        lambda *a, **k: pytest.fail("não pode tocar o servidor com célula inválida"),
    )

    with pytest.raises(ErroDeInstrumentacao):
        rollback.congelar(RAIZ, "chekout", "erro de digitação às 2h da manhã")


def test_descongelar_apaga_a_referencia_no_servidor(monkeypatch) -> None:
    vistos: list[list[str]] = []

    def falso(comando, **kwargs):
        vistos.append(comando)
        return _Saida()

    monkeypatch.setattr(rollback, "executar", falso)

    rollback.descongelar(RAIZ, "checkout")

    assert vistos == [
        ["git", "push", "origin", f":{rollback.NS_CONGELAMENTO}/checkout"]
    ]
