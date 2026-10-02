"""`/avisos` redireciona para a página única `/notificacoes`.
O destino é caminho absoluto, e as rotas de marcar como lido não existem mais."""

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

PREFIXO = "/forms/sugestoes"
DESTINO = "/notificacoes"


def test_avisos_redireciona_para_a_pagina_unica(dentro):
    resposta = dentro.client.get(reverse("avisos"))

    assert resposta.status_code == 302
    assert resposta["Location"] == DESTINO


def test_o_anonimo_tambem_e_redirecionado_sem_tocar_a_rede(client):
    resposta = client.get(reverse("avisos"))

    assert resposta.status_code == 302
    assert resposta["Location"] == DESTINO


def test_o_destino_nao_leva_o_prefixo_da_celula(settings):
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    try:
        resposta = async_to_sync(AsyncClient().get)(
            f"{PREFIXO}/avisos", headers={"x-forwarded-proto": "https"}
        )
    finally:
        clear_script_prefix()

    assert resposta.status_code == 302
    assert resposta["Location"] == DESTINO


def test_post_em_avisos_nao_e_aceito(dentro):
    assert dentro.client.post(reverse("avisos")).status_code == 405


@pytest.mark.parametrize("caminho", ["/avisos/1/lido", "/avisos/marcar-tudo"])
def test_as_rotas_de_marcar_como_lido_nao_existem_mais(dentro, caminho):
    assert dentro.client.post(caminho).status_code == 404
