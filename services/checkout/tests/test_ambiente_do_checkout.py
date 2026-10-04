"""`GET /interno/ambiente`: o painel 'pronto para vender?' pergunta se os
pedidos deste site nascem em teste ou em produção. Só o rótulo: nunca chave,
endereço ou segredo.
"""

import pytest

from conftest import HOST_A, SITE_A

AMBIENTE = "/api/checkout/interno/ambiente"


@pytest.fixture
def sem_provedor_de_producao(settings):
    settings.MP_PUBLIC_KEY = "TEST-aaaa-bbbb"
    settings.APPMAX_API_URL = "https://api.sandboxappmax.com.br"
    settings.APPMAX_PIX_ENABLED_SITES = frozenset()
    settings.APPMAX_PIX_FALLBACK_SITES = frozenset()
    settings.APPMAX_CARD_ENABLED_SITES = frozenset()


@pytest.mark.django_db
def test_chave_de_teste_do_mercado_pago_diz_teste(api, rede, sem_provedor_de_producao):
    corpo = api.get(AMBIENTE).json()
    assert corpo == {"cartao": "teste", "pix": "teste", "modo": "teste"}


@pytest.mark.django_db
def test_chave_de_producao_diz_producao(api, rede, sem_provedor_de_producao, settings):
    settings.MP_PUBLIC_KEY = "APP_USR-xxxx"
    corpo = api.get(AMBIENTE).json()
    assert corpo == {"cartao": "producao", "pix": "producao", "modo": "producao"}


@pytest.mark.django_db
def test_appmax_no_sandbox_conta_como_teste_e_em_producao_nao(api, rede, sem_provedor_de_producao, settings):
    settings.MP_PUBLIC_KEY = "APP_USR-xxxx"
    settings.APPMAX_CARD_ENABLED_SITES = frozenset({SITE_A["id"]})
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    corpo = api.get(AMBIENTE).json()
    assert corpo == {"cartao": "teste", "pix": "teste", "modo": "teste"}
    settings.APPMAX_API_URL = "https://api.appmax.com.br"
    assert api.get(AMBIENTE).json() == {"cartao": "producao", "pix": "producao", "modo": "producao"}


@pytest.mark.django_db
def test_cartao_em_producao_e_pix_em_teste_aparece_separado(api, rede, sem_provedor_de_producao, settings):
    settings.MP_PUBLIC_KEY = "APP_USR-xxxx"
    settings.APPMAX_PIX_ENABLED_SITES = frozenset({SITE_A["id"]})
    corpo = api.get(AMBIENTE).json()
    assert corpo == {"cartao": "producao", "pix": "teste", "modo": "teste"}


@pytest.mark.django_db
def test_a_resposta_nunca_leva_chave_nem_endereco(api, rede, sem_provedor_de_producao, settings):
    settings.MP_PUBLIC_KEY = "TEST-segredo-que-nao-pode-sair"
    texto = api.get(AMBIENTE).content.decode()
    assert "segredo" not in texto and "appmax" not in texto.lower() and "http" not in texto


@pytest.mark.django_db
def test_token_publico_e_visitante_sem_token_nao_alcancam(client, settings, rede):
    settings.TOKENS_ACEITOS = {"publico"}
    settings.TOKENS_PUBLICOS = {"publico"}
    publico = client.get(AMBIENTE, HTTP_AUTHORIZATION="Bearer publico", HTTP_HOST=HOST_A)
    sem_token = client.get(AMBIENTE, HTTP_HOST=HOST_A)
    assert (publico.status_code, sem_token.status_code) == (403, 401)
