"""Lista e ficha do CRM pela API de leads, sem consultar o banco de leads."""

import uuid
from unittest.mock import patch

import pytest
from django.http import Http404
from django.test import RequestFactory

from apps.core import contatos as modulo
from apps.core.clients import LeadsClient


ID = uuid.UUID("24e45be2-77bb-4a32-a388-78d2ce9adcad")


def _pedido(caminho, **filtros):
    pedido = RequestFactory().get(caminho, filtros)
    pedido.admin = {"nome": "Dono"}
    return pedido


def test_cliente_consulta_contatos_dos_quizzes_e_alunos():
    cliente = LeadsClient()
    lista = {"itens": [], "total": 0, "pagina": 2, "por_pagina": 25, "tem_mais": False}
    ficha = {"id": str(ID), "linha_do_tempo": []}
    with patch.object(cliente, "_pedir", return_value=(LeadsClient.OK, lista)) as pedir:
        assert cliente.listar(q="Ana", tag="interessada", pagina=2, por_pagina=25) == (LeadsClient.OK, lista)
    pedir.assert_called_once_with("/leads", {"pagina": 2, "por_pagina": 25, "origem": "crm", "q": "Ana", "tag": "interessada"})
    with patch.object(cliente, "_pedir", return_value=(LeadsClient.OK, ficha)) as pedir:
        assert cliente.ficha(ID) == (LeadsClient.OK, ficha)
    pedir.assert_called_once_with(f"/leads/{ID}", {"origem": "crm"}, aceita_404=True)


def test_lista_filtra_pagina_e_preserva_filtros():
    resposta = {
        "itens": [{"id": str(ID), "nome": "Ana", "tags": ["quente"], "criado_em": "2026-10-03T13:00:00Z"}],
        "total": 51, "por_pagina": 50, "tem_mais": True,
    }
    with patch.object(LeadsClient, "listar", return_value=(LeadsClient.OK, resposta)) as listar, patch.object(modulo, "render", return_value="tela") as render:
        assert modulo.contatos(_pedido("/contatos/", q=" Ana ", tag="quente", site_id="principal", pagina="1")) == "tela"
    listar.assert_called_once_with(q="Ana", tag="quente", site_id="principal", pagina=1, por_pagina=50)
    tela = render.call_args.args[2]["tela"]
    assert tela["total"] == 51
    assert "q=Ana" in tela["link_proxima"] and "tag=quente" in tela["link_proxima"]
    assert tela["itens"][0]["criado_em"].hour == 10
    assert render.call_args.kwargs["status"] == 200


@pytest.mark.parametrize("desfecho", [LeadsClient.NAO_RESPONDEU, LeadsClient.SEM_CONFIGURACAO])
def test_fonte_indisponivel_retorna_503_sem_fingir_lista_vazia(desfecho):
    with patch.object(LeadsClient, "listar", return_value=(desfecho, None)), patch.object(modulo, "render", return_value="indisponivel") as render:
        assert modulo.contatos(_pedido("/contatos/")) == "indisponivel"
    assert render.call_args.kwargs["status"] == 503
    assert "itens" not in render.call_args.args[2]["tela"]


def test_ficha_exibe_somente_dados_humanos_e_pagamento_relevante():
    resposta = {
        "id": str(ID), "nome": "Ana", "email": "ana@example.com", "origem": "pagina-venda",
        "consentimento": {"email_marketing": True, "token_privado": "segredo"},
        "utm": {"email": "outra@example.com"},
        "linha_do_tempo_total": 2,
        "linha_do_tempo": [
            {"evento": "pagamento.aprovado", "ocorrido_em": "2026-10-03T13:00:00Z", "payload": {"amount_cents": 49700, "method": "pix", "token": "segredo"}},
            {"evento": "evento.interno", "payload": {"email": "outra@example.com"}},
        ],
    }
    ficha = modulo.montar_ficha(resposta)
    assert ficha["eventos"][0]["valor"] == "R$ 497,00"
    assert ficha["eventos"][0]["quando"].hour == 10
    assert ficha["eventos"][1]["rotulo"] == "Outra atividade"
    assert ficha["consentimento"] == [("Novidades por e-mail", "Sim")]
    assert "segredo" not in str(ficha) and "outra@example.com" not in str(ficha)


def test_ficha_inexistente_e_fonte_fora_do_ar():
    with patch.object(LeadsClient, "ficha", return_value=(LeadsClient.NAO_EXISTE, None)):
        with pytest.raises(Http404):
            modulo.contato(_pedido(f"/contatos/{ID}/"), ID)
    with patch.object(LeadsClient, "ficha", return_value=(LeadsClient.NAO_RESPONDEU, None)), patch.object(modulo, "render", return_value="indisponivel") as render:
        assert modulo.contato(_pedido(f"/contatos/{ID}/"), ID) == "indisponivel"
    assert render.call_args.kwargs["status"] == 503
