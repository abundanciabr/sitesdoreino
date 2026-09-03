"""O acerto de contas único do fórum (`backfill_pontos_do_forum`).

Pedido do mantenedor em 03/09/2026, depois de uma auditoria: as 3 regras do
fórum nasceram desligadas em 01/09/2026 por um bug de tela (PR #918) e só
foram ligadas em 03/09/2026 — toda participação real nesse intervalo já foi
RECONHECIDA (`ConversaAberta`/`AjudaAceita` gravam com a regra desligada),
mas nunca foi PAGA, porque `vigente_desde` (o mecanismo de "nunca
retroativo") descarta fato anterior à data em que a regra foi ligada.

O que este arquivo trava:

1. **Ensaio por padrão**: sem `--confirmo`, nada é gravado, mas o relatório
   já mostra o resultado certo.
2. **Só paga o que aconteceu ANTES de `vigente_desde`.** Depois disso, o
   caminho normal (`aplicar()`) já pagou — pagar de novo aqui seria duplicar.
3. **Idempotente**: rodar duas vezes com `--confirmo` não credita duas vezes.
4. **Respeita o teto diário** exatamente como o motor ao vivo respeitaria.
5. **Fato antigo nasce DEFINITIVO na hora** (a quarentena dele já venceu há
   dias); fato mais recente que o `vigente_desde` (mas dentro da janela)
   nasce PENDENTE, com a data real de liberação.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.gamificacao.models import (
    AjudaAceita,
    ConversaAberta,
    LancamentoDeXP,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)

pytestmark = pytest.mark.django_db

SITE = "site-do-teste"


def _regra(slug: str, *, vigente_desde, **campos) -> RegraDePontuacao:
    base = {
        "slug": slug,
        "site_id": SITE,
        "evento_gatilho": f"{slug}.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 8,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 24,
        "ativa": True,
        "vigente_desde": vigente_desde,
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _pessoa(id_da_plataforma: str) -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=id_da_plataforma, email=f"{id_da_plataforma}@ex.com"
    )


def _conversa(pessoa: Pessoa, topico_id: str, quando) -> ConversaAberta:
    return ConversaAberta.objects.create(
        pessoa=pessoa, site_id=SITE, topico_id=topico_id, occurred_at=quando
    )


def _ajuda(pessoa: Pessoa, mensagem_id: str, quando) -> AjudaAceita:
    return AjudaAceita.objects.create(
        pessoa=pessoa,
        site_id=SITE,
        mensagem_id=mensagem_id,
        topico_id="t1",
        marcada_por="autor",
        quem_marcou="pes-outro",
        occurred_at=quando,
    )


def _rodar(*, confirmo: bool) -> str:
    saida = StringIO()
    args = ["--site-id", SITE]
    if confirmo:
        args.append("--confirmo")
    call_command("backfill_pontos_do_forum", *args, stdout=saida)
    return saida.getvalue()


def test_ensaio_nao_grava_nada():
    agora = timezone.now()
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", agora - timedelta(days=3))
    _regra("forum-topico-criado", vigente_desde=agora - timedelta(days=1))

    saida = _rodar(confirmo=False)

    assert "ENSAIO" in saida
    assert "1 lançamento(s)" in saida.replace("s) novo", "s)")
    assert LancamentoDeXP.objects.count() == 0
    assert not PerfilJogador.objects.exists()


def test_confirmo_credita_de_verdade_e_recalcula_o_perfil():
    agora = timezone.now()
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", agora - timedelta(days=3))
    _regra("forum-topico-criado", vigente_desde=agora - timedelta(days=1), pontos=8)

    saida = _rodar(confirmo=True)

    assert "Gravado." in saida
    (lancamento,) = LancamentoDeXP.objects.all()
    assert lancamento.pessoa_id == "p1"
    assert lancamento.pontos == 8
    assert lancamento.regra_slug == "forum-topico-criado"
    assert lancamento.origem_event_id == "backfill:topico:t1"
    perfil = PerfilJogador.objects.get(pessoa_id="p1", site_id=SITE)
    assert perfil.xp_total == 8


def test_e_idempotente_rodar_duas_vezes():
    agora = timezone.now()
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", agora - timedelta(days=3))
    _regra("forum-topico-criado", vigente_desde=agora - timedelta(days=1), pontos=8)

    _rodar(confirmo=True)
    saida2 = _rodar(confirmo=True)

    assert LancamentoDeXP.objects.count() == 1
    assert "0 lançamento(s) novo(s)" in saida2
    assert PerfilJogador.objects.get(pessoa_id="p1", site_id=SITE).xp_total == 8


def test_nao_paga_de_novo_o_que_ja_aconteceu_depois_de_vigente_desde():
    """O caminho normal já pagou isso — pagar aqui seria duplicar."""
    agora = timezone.now()
    pessoa = _pessoa("p1")
    vigente_desde = agora - timedelta(days=1)
    _conversa(pessoa, "antigo", agora - timedelta(days=3))
    _conversa(pessoa, "recente", agora - timedelta(hours=2))  # depois de ligar
    _regra("forum-topico-criado", vigente_desde=vigente_desde, pontos=8)

    _rodar(confirmo=True)

    assert LancamentoDeXP.objects.filter(
        origem_event_id="backfill:topico:antigo"
    ).exists()
    assert not LancamentoDeXP.objects.filter(
        origem_event_id="backfill:topico:recente"
    ).exists()


def test_respeita_o_teto_diario_como_o_motor_ao_vivo():
    agora = timezone.now()
    dia = agora - timedelta(days=5)
    pessoa = _pessoa("p1")
    for i in range(4):
        _conversa(pessoa, f"t{i}", dia + timedelta(minutes=i))
    _regra(
        "forum-topico-criado",
        vigente_desde=agora - timedelta(days=1),
        pontos=8,
        acoes_cheias_por_dia=3,
    )

    _rodar(confirmo=True)

    pontos = list(
        LancamentoDeXP.objects.filter(pessoa_id="p1")
        .order_by("occurred_at")
        .values_list("pontos", flat=True)
    )
    # As três primeiras pagam cheio; a quarta decai (mesma régua de pontos_com_teto).
    assert pontos[:3] == [8, 8, 8]
    assert pontos[3] < 8


def test_regra_desligada_e_pulada_sem_erro():
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", timezone.now() - timedelta(days=3))
    RegraDePontuacao.objects.create(
        slug="forum-topico-criado",
        site_id=SITE,
        evento_gatilho="forum.topico-criado.v1",
        pontos=8,
        ativa=False,
        vigente_desde=None,
    )

    saida = _rodar(confirmo=True)

    assert "ainda não está ligada" in saida
    assert LancamentoDeXP.objects.count() == 0


def test_regra_inexistente_e_pulada_sem_erro():
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", timezone.now() - timedelta(days=3))
    # Nenhuma RegraDePontuacao criada — cenário "nunca foi nem semeada".

    saida = _rodar(confirmo=True)

    assert "regra não existe neste site" in saida
    assert LancamentoDeXP.objects.count() == 0


def test_fato_antigo_nasce_definitivo_fato_dentro_da_janela_nasce_pendente():
    agora = timezone.now()
    pessoa = _pessoa("p1")
    vigente_desde = agora - timedelta(hours=2)
    _ajuda(pessoa, "m-antiga", agora - timedelta(days=5))  # quarentena já venceu
    _ajuda(pessoa, "m-recente", agora - timedelta(hours=3))  # ainda dentro das 24h
    _regra(
        "forum-resposta-aceita",
        vigente_desde=vigente_desde,
        pontos=50,
        quarentena_horas=24,
    )

    _rodar(confirmo=True)

    antiga = LancamentoDeXP.objects.get(origem_event_id="backfill:resposta:m-antiga")
    recente = LancamentoDeXP.objects.get(origem_event_id="backfill:resposta:m-recente")
    assert antiga.status == LancamentoDeXP.Status.DEFINITIVO
    assert recente.status == LancamentoDeXP.Status.PENDENTE
    assert recente.liberado_em == agora - timedelta(hours=3) + timedelta(hours=24)
    # Só o definitivo entra no perfil agora; o pendente espera a quarentena.
    assert PerfilJogador.objects.get(pessoa_id="p1", site_id=SITE).xp_total == 50


def test_as_duas_regras_juntas_credita_as_duas():
    agora = timezone.now()
    pessoa = _pessoa("p1")
    _conversa(pessoa, "t1", agora - timedelta(days=3))
    _ajuda(pessoa, "m1", agora - timedelta(days=3))
    _regra("forum-topico-criado", vigente_desde=agora - timedelta(days=1), pontos=8)
    _regra(
        "forum-resposta-aceita",
        vigente_desde=agora - timedelta(days=1),
        pontos=50,
        quarentena_horas=24,
    )

    _rodar(confirmo=True)

    assert LancamentoDeXP.objects.count() == 2
    assert PerfilJogador.objects.get(pessoa_id="p1", site_id=SITE).xp_total == 58
