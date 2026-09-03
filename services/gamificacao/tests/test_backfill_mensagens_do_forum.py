"""A segunda metade do acerto de contas do fórum (`backfill_mensagens_do_forum`).

Diferente de `backfill_pontos_do_forum` (tópico e resposta aceita, que lê
tabela-espelho própria), mensagem não tem espelho dentro desta célula — o
histórico vem de fora, em JSON, exportado por `exportar_mensagens_para_backfill`
na célula `forum`. Este arquivo trava:

1. Ensaio por padrão.
2. Só paga o que aconteceu ANTES de `vigente_desde`.
3. Idempotente.
4. Respeita teto diário.
5. Regra desligada/inexistente não quebra.
6. JSON de entrada torto vira erro claro, nunca 500 silencioso.
"""

from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.gamificacao.models import LancamentoDeXP, PerfilJogador, RegraDePontuacao

pytestmark = pytest.mark.django_db

SITE = "site-do-teste"


def _regra(*, vigente_desde, **campos) -> RegraDePontuacao:
    base = {
        "slug": "forum-mensagem",
        "site_id": SITE,
        "evento_gatilho": "forum.mensagem-criada.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 5,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 24,
        "ativa": True,
        "vigente_desde": vigente_desde,
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _msg(pessoa_id: str, mensagem_id: str, quando) -> dict:
    return {
        "pessoa_id": pessoa_id,
        "mensagem_id": mensagem_id,
        "occurred_at": quando.isoformat(),
    }


def _rodar_com_stdin(monkeypatch, mensagens: list[dict], *, confirmo: bool) -> str:
    """`call_command` não liga `input=` a `sys.stdin` — o comando lê stdin de
    verdade, então o dublê precisa ser no próprio `sys.stdin`."""
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(mensagens)))
    saida = StringIO()
    args = ["--site-id", SITE]
    if confirmo:
        args.append("--confirmo")
    call_command("backfill_mensagens_do_forum", *args, stdout=saida)
    return saida.getvalue()


def test_ensaio_nao_grava_nada(monkeypatch):
    agora = timezone.now()
    _regra(vigente_desde=agora - timedelta(days=1))
    mensagens = [_msg("p1", "m1", agora - timedelta(days=3))]

    saida = _rodar_com_stdin(monkeypatch, mensagens, confirmo=False)

    assert "ENSAIO" in saida
    assert "TOTAL: 1 lançamento" in saida
    assert LancamentoDeXP.objects.count() == 0


def test_confirmo_credita_de_verdade(monkeypatch):
    agora = timezone.now()
    _regra(vigente_desde=agora - timedelta(days=1))
    mensagens = [_msg("p1", "m1", agora - timedelta(days=3))]

    saida = _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    assert "Gravado." in saida
    (lancamento,) = LancamentoDeXP.objects.all()
    assert lancamento.pessoa_id == "p1"
    assert lancamento.pontos == 5
    assert lancamento.origem_event_id == "backfill:mensagem:m1"
    assert PerfilJogador.objects.get(pessoa_id="p1", site_id=SITE).xp_total == 5


def test_e_idempotente(monkeypatch):
    agora = timezone.now()
    _regra(vigente_desde=agora - timedelta(days=1))
    mensagens = [_msg("p1", "m1", agora - timedelta(days=3))]

    _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)
    _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    assert LancamentoDeXP.objects.count() == 1


def test_nao_paga_mensagem_depois_de_vigente_desde(monkeypatch):
    agora = timezone.now()
    vigente_desde = agora - timedelta(days=1)
    _regra(vigente_desde=vigente_desde)
    mensagens = [
        _msg("p1", "antiga", agora - timedelta(days=3)),
        _msg("p1", "recente", agora - timedelta(hours=2)),
    ]

    _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    assert LancamentoDeXP.objects.filter(
        origem_event_id="backfill:mensagem:antiga"
    ).exists()
    assert not LancamentoDeXP.objects.filter(
        origem_event_id="backfill:mensagem:recente"
    ).exists()


def test_respeita_o_teto_diario(monkeypatch):
    agora = timezone.now()
    dia = agora - timedelta(days=5)
    _regra(vigente_desde=agora - timedelta(days=1), acoes_cheias_por_dia=3)
    mensagens = [_msg("p1", f"m{i}", dia + timedelta(minutes=i)) for i in range(4)]

    _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    pontos = list(
        LancamentoDeXP.objects.filter(pessoa_id="p1")
        .order_by("occurred_at")
        .values_list("pontos", flat=True)
    )
    assert pontos[:3] == [5, 5, 5]
    assert pontos[3] < 5


def test_regra_inexistente_nao_quebra(monkeypatch):
    agora = timezone.now()
    mensagens = [_msg("p1", "m1", agora - timedelta(days=3))]

    saida = _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    assert "regra não existe neste site" in saida
    assert LancamentoDeXP.objects.count() == 0


def test_regra_desligada_nao_quebra(monkeypatch):
    agora = timezone.now()
    RegraDePontuacao.objects.create(
        slug="forum-mensagem",
        site_id=SITE,
        evento_gatilho="forum.mensagem-criada.v1",
        pontos=5,
        ativa=False,
        vigente_desde=None,
    )
    mensagens = [_msg("p1", "m1", agora - timedelta(days=3))]

    saida = _rodar_com_stdin(monkeypatch, mensagens, confirmo=True)

    assert "ainda não está ligada" in saida
    assert LancamentoDeXP.objects.count() == 0


def test_json_torto_vira_erro_claro(monkeypatch):
    import io

    agora = timezone.now()
    _regra(vigente_desde=agora - timedelta(days=1))
    monkeypatch.setattr("sys.stdin", io.StringIO("isto nao e json"))

    with pytest.raises(CommandError):
        call_command("backfill_mensagens_do_forum", "--site-id", SITE, "--confirmo")

    assert LancamentoDeXP.objects.count() == 0
