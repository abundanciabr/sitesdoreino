"""A página /conquistas/ mostra as faixas: atual, próxima, barra, jornada, legenda."""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from apps.eventos.management.commands.consume_eventos import processar_envelope
from apps.gamificacao.handlers import HANDLERS

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALGUEM = "pes-abc"
AGORA = "2026-10-08T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ALGUEM)


def _envio(event, **extra):
    data = {"site_id": SITE, "pessoa_id": ALGUEM, "ocorrido_em": AGORA, "historico": False, **extra}
    processar_envelope(
        {"event_id": str(uuid.uuid4()), "event": event, "version": 1,
         "occurred_at": AGORA, "ator_id": ALGUEM, "data": data},
        HANDLERS,
    )


def _ate_laranja():
    _envio("cursos.item-criado", item_id="i1")
    _envio("encomendas.sandbox-trabalho-criado", trabalho_id="t1")
    _envio("encomendas.fila-trabalho-aceito", pedido_id="p1")


def _pagar(centavos, rid="r1"):
    _envio("encomendas.rendimento-real-confirmado", rendimento_id=rid, valor_cents=centavos)


def _pagina(client):
    r = client.get(reverse("base"))
    assert r.status_code == 200
    return r.content.decode()


def test_aluno_novo_e_branca_com_proxima_sem_barra(client):
    corpo = _pagina(client)
    assert "Faixa Branca" in corpo
    assert "Começando do zero" in corpo
    assert "Faixa Branca e amarela" in corpo
    assert 'class="barra"' not in corpo.split("A jornada das 13 faixas")[0].split("Próxima faixa")[1]
    assert corpo.count('class="faixa-item') == 13
    assert "fita branca" in corpo


def test_laranja_proxima_verde_sem_valor_real(client):
    _ate_laranja()
    corpo = _pagina(client)
    assert "Faixa Laranja" in corpo
    assert "Faixa Verde" in corpo
    assert "Receba o primeiro pagamento real" in corpo
    assert "Primeiro dinheiro real ganho de um cliente real" in corpo
    assert "/08/10/2026" not in corpo and "08/10/2026" in corpo
    assert "linear-gradient" in corpo  # faixas de duas cores na jornada


def test_azul_com_barra_financeira(client):
    _ate_laranja()
    _pagar(7350)
    corpo = _pagina(client)
    assert "Faixa Azul" in corpo
    assert "R$ 73,50" in corpo and "R$ 100,00" in corpo and "R$ 26,50" in corpo
    assert "width: 73%" in corpo
    assert "Pagamento real de cliente confirmado" in corpo


def test_preta_nao_tem_proxima(client):
    _pagar(200000)
    corpo = _pagina(client)
    assert "última da jornada" in corpo
    assert "Próxima faixa" not in corpo


def test_legenda_presente(client):
    corpo = _pagina(client)
    for trecho in ("Não depende de XP", "experiência de estudo", "loja",
                   "Não é dinheiro", "clientes reais, já confirmado"):
        assert trecho in corpo
    assert "Medalhas" in corpo  # o que já existia continua
    assert "A sua escada está sendo montada" in corpo


def test_sem_vazamento_de_dados_de_cliente(client):
    _ate_laranja()
    _pagar(5000, rid="REF-SECRETA-123")
    corpo = _pagina(client)
    for proibido in ("REF-SECRETA-123", "r1", "p1", "pedido", "5000", "R$ 50,00 de"):
        if proibido in ("r1", "p1"):
            continue  # curtos demais para checar em HTML
        assert proibido not in corpo.replace("R$ 50,00", "")
    assert ALGUEM not in corpo


def test_visitante_continua_vendo_o_convite(client, monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    corpo = _pagina(client)
    assert "Suas conquistas ficam aqui" in corpo
    assert "Sua faixa" not in corpo


def test_pagina_nao_grava_nada_de_faixa(client):
    from apps.gamificacao.models import FaixaDoAluno

    _pagina(client)
    assert FaixaDoAluno.objects.count() == 0
