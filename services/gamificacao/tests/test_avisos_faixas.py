"""Avisos de progressão correspondem a avaliações reais, nunca ao total de XP."""
import pytest
from django.db import transaction
from django.http import HttpResponse
from apps.core.perfil import perfil_de
from apps.core.trilha_api import _projecao
from apps.gamificacao.bonus_faixas import configurar
from apps.gamificacao.jornada import registrar_avaliacao, situacao
from apps.gamificacao.models import JornadaPessoal, OutboxEvent, PerfilJogador, RegistroDaJornada

pytestmark = pytest.mark.django_db
P, SITE = "aluna-avisos", "site-avisos"

@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.gamificacao.motor.relay_apos_commit", lambda: None)
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    perfil_de(P, SITE)
    configurar(SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE, inicio={"motivo":"ugc"})

def avaliar(ordem, resultado="reconhecida", chave=None):
    return registrar_avaliacao(P, SITE, ordem, resultado, "Realização examinada nesta etapa.", {"chave":chave or str(ordem), "tipo":"ensaio"})

def cartas():
    return list(OutboxEvent.objects.filter(payload__assunto="gamificacao.conquista-concedida"))

def test_avaliacao_emite_faixa_unica_e_repeticao_preserva_xp():
    avaliar(2)
    perfil = PerfilJogador.objects.get(pessoa_id=P, site_id=SITE)
    assert perfil.xp_total == 5000
    assert len(cartas()) == 1
    assert cartas()[0].payload["parametros"] == {"conquista_slug":"trilha-faixa-amarela", "familia":"carreira"}
    avaliar(2)
    avaliar(2, chave="segunda-avaliacao")
    perfil.refresh_from_db()
    assert perfil.xp_total == 5000 and len(cartas()) == 1
    assert not OutboxEvent.objects.filter(payload__assunto="gamificacao.nivel-alcancado").exists()

def test_incompleta_falha_e_etapa_fora_de_ordem_nao_avisam():
    avaliar(2, "incompleta", "incompleta")
    avaliar(2, "falha", "falha")
    avaliar(3)
    assert cartas() == []
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    avaliar(2)
    assert len(cartas()) == 1
    assert cartas()[0].payload["parametros"]["conquista_slug"] == "trilha-faixa-azul"

def test_rollback_nao_deixa_carta_nem_xp():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            avaliar(2)
            raise RuntimeError("ensaio de rollback")
    assert cartas() == []
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 0

def test_celebracao_e_ack_preservam_historico_e_outra_ordem(client):
    avaliar(2)
    dados = _projecao(HttpResponse(), P, SITE, incluir_avaliacoes=True)
    assert dados.celebracao == {"ordem":2, "tipo":"cor"}
    assert _projecao(HttpResponse(), P, SITE).celebracao == {}
    historico = RegistroDaJornada.objects.count()
    url = "/trilha/inventario/api/"
    assert client.post(url, {"acao":"celebracao-vista", "ordem":3}, HTTP_COOKIE="meshcraft_sessao=teste").status_code == 200
    assert situacao(P, SITE)["celebracao"]
    assert client.post(url, {"acao":"celebracao-vista", "ordem":2, "contexto_pessoa":"outra"}, HTTP_COOKIE="meshcraft_sessao=teste").status_code == 403
    assert client.post(url, {"acao":"celebracao-vista", "ordem":2}, HTTP_COOKIE="meshcraft_sessao=teste").status_code == 200
    assert situacao(P, SITE)["celebracao"] == {}
    assert RegistroDaJornada.objects.count() == historico
    assert len(cartas()) == 1

def test_endereco_antigo_redireciona(client):
    resposta = client.get("/")
    assert resposta.status_code == 302 and resposta["Location"] == "/trilha/"
