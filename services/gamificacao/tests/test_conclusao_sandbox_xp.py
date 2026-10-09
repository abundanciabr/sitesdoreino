from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.gamificacao.handlers import ao_sandbox_trabalho_concluido
from apps.gamificacao.models import LancamentoDeXP, Pessoa, PerfilJogador, RegraDePontuacao, NivelDefinicao


def envelope():
    return {"event": "encomendas.sandbox-trabalho-concluido", "version": 1,
            "event_id": str(uuid4()), "occurred_at": timezone.now().isoformat(),
            "data": {"site_id": "escola-teste", "pessoa_id": "aluno-concluiu", "trabalho_id": str(uuid4())}}


@pytest.mark.django_db
def test_sem_pontuacao_configurada_nao_inventa_xp():
    ao_sandbox_trabalho_concluido(envelope())
    assert LancamentoDeXP.objects.count() == 0


@pytest.mark.django_db
def test_ativar_bonus_depois_da_conquista_nao_perde_nem_duplica_credito(monkeypatch):
    from apps.gamificacao import motor, bonus_faixas
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    e = envelope()
    ao_sandbox_trabalho_concluido(e)
    bonus_faixas.configurar("escola-teste")
    ao_sandbox_trabalho_concluido(e)
    ao_sandbox_trabalho_concluido(e)
    assert LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").count() == 1
    assert PerfilJogador.objects.get(pessoa_id="aluno-concluiu", site_id="escola-teste").xp_total == 10000


@pytest.mark.django_db
def test_pontuacao_configurada_uma_unica_vez_no_aluno_correto(monkeypatch):
    from apps.gamificacao import motor, bonus_faixas, jornada
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    NivelDefinicao.objects.create(nivel=1, site_id="escola-teste", xp_necessario=0, titulo="Início", ativa=True)
    Pessoa.objects.create(id_da_plataforma="aluno-concluiu", email="aluno@teste.invalid")
    bonus_faixas.configurar("escola-teste")
    e = envelope()
    ao_sandbox_trabalho_concluido(e)
    ao_sandbox_trabalho_concluido(e)
    lancamentos = LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul")
    assert lancamentos.count() == 1 and lancamentos.get().pessoa.id_da_plataforma == "aluno-concluiu"
    assert PerfilJogador.objects.get(pessoa__id_da_plataforma="aluno-concluiu").xp_total == 10000
    jornada.salvar("aluno-concluiu", "escola-teste", {
        "acao": "declaracao", "revisao": jornada.situacao("aluno-concluiu", "escola-teste")["revisao"],
        "passo": 3, "estado": "feito",
    })
    assert lancamentos.count() == 1


@pytest.mark.django_db
def test_todos_bonus_uma_vez_por_aluno_e_por_site(monkeypatch):
    from apps.gamificacao import motor, bonus_faixas
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    for site in ("escola-a", "escola-b"):
        bonus_faixas.configurar(site)
    for pessoa in ("aluno-1", "aluno-2"):
        assert bonus_faixas.conceder(pessoa, "escola-a", range(1, 14)) == 720000
        assert bonus_faixas.conceder(pessoa, "escola-a", range(1, 14)) == 0
    assert bonus_faixas.conceder("aluno-1", "escola-b", [3]) == 10000
    assert PerfilJogador.objects.get(pessoa_id="aluno-1", site_id="escola-a").xp_total == 720000
    assert PerfilJogador.objects.get(pessoa_id="aluno-1", site_id="escola-b").xp_total == 10000


@pytest.mark.django_db
def test_corrigir_e_declarar_de_novo_nao_duplica_bonus(monkeypatch):
    from apps.gamificacao import motor, bonus_faixas, jornada
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    bonus_faixas.configurar("escola-teste")
    ao_sandbox_trabalho_concluido(envelope())
    for estado in ("corrigir", "feito"):
        jornada.salvar("aluno-concluiu", "escola-teste", {
            "acao": "declaracao", "revisao": jornada.situacao("aluno-concluiu", "escola-teste")["revisao"],
            "passo": 3, "estado": estado,
        })
    assert LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("evento,ordem,pontos", [
    ("encomendas.sandbox-trabalho-concluido", 3, 10000),
    ("encomendas.fila-trabalho-concluido", 4, 15000),
])
def test_consumidor_recebe_conclusao_e_nao_duplica_por_outro_trabalho(monkeypatch, evento, ordem, pontos):
    from apps.eventos.management.commands.consume_eventos import STREAMS, processar_envelope
    from apps.gamificacao.handlers import HANDLERS
    from apps.gamificacao import motor, bonus_faixas, jornada
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    bonus_faixas.configurar("escola-teste")
    assert "eventos." + evento in STREAMS
    e = {**envelope(), "event": evento}
    processar_envelope(e, HANDLERS)
    processar_envelope(e, HANDLERS)
    processar_envelope({**e, "event_id": str(uuid4())}, HANDLERS)
    assert PerfilJogador.objects.get(pessoa_id="aluno-concluiu", site_id="escola-teste").xp_total == pontos
    assert jornada.situacao("aluno-concluiu", "escola-teste")["lista"][ordem-1]["alcancada"]


@pytest.mark.django_db
def test_evento_historico_nao_concede_bonus(monkeypatch):
    from apps.gamificacao import bonus_faixas
    bonus_faixas.configurar("escola-teste")
    e = envelope()
    e["data"]["historico"] = True
    ao_sandbox_trabalho_concluido(e)
    assert not LancamentoDeXP.objects.exists()


@pytest.mark.django_db
def test_print_confirmado_concede_todos_degraus_cruzados_sem_repetir(monkeypatch):
    from apps.gamificacao import motor, bonus_faixas, jornada, prints_recebimentos
    from apps.gamificacao.models import RecebimentoDeclarado
    from tests.test_faixas_pagina import imagem
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)
    pessoa, site = "aluno-print", "escola-print"
    bonus_faixas.configurar(site)
    jornada.salvar(pessoa, site, {"acao": "meta", "meta": "100", "revisao": 0})
    jornada.salvar(pessoa, site, {
        "acao": "recebimento", "revisao": jornada.situacao(pessoa, site)["revisao"],
        "chave": str(uuid4()), "valor": "25", "origem": "fora", "recebido_em": "2026-10-01",
    }, arquivo=imagem())
    assert LancamentoDeXP.objects.filter(site_id=site).count() == 0
    r = RecebimentoDeclarado.objects.get(pessoa_id=pessoa, site_id=site)
    monkeypatch.setattr(prints_recebimentos, "ler_modelo", lambda *a, **k: {
        "status": "recebido", "valor_cents": 2500, "moeda": "BRL", "data": "2026-10-01",
    })
    assert prints_recebimentos.processar(r.pk)
    assert PerfilJogador.objects.get(pessoa_id=pessoa, site_id=site).xp_total == 240000
    for meta in ("1000", "100"):
        jornada.salvar(pessoa, site, {"acao": "meta", "meta": meta,
            "revisao": jornada.situacao(pessoa, site)["revisao"]})
    assert LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site).count() == 6
    assert PerfilJogador.objects.get(pessoa_id=pessoa, site_id=site).xp_total == 240000
