"""Teste-guarda do H10.1 (ARMADILHAS §4.10): /healthz sob o env de produção.

Em produção o checkout sobe atrás do Traefik com SCRIPT_NAME=/checkout
(FORCE_SCRIPT_NAME). No Django 5.0.x isso faz request.path incluir o prefixo
("/checkout/healthz"); uma isenção do middleware CONV-SITE escrita sobre
request.path deixa de casar, a sonda cai na resolução de site (Host sem
cadastro ⇒ 404) e o healthcheck do container nunca fica healthy — medido em
21/08/2026 nas 8 células: só o checkout respondia 404. A comparação correta é
request.path_info, que segue "/healthz" independente do prefixo do gateway.
"""

import httpx
import pytest
import respx


@pytest.fixture
def env_de_producao(settings):
    """O que o env real da VPS faz: SCRIPT_NAME=/checkout via FORCE_SCRIPT_NAME."""
    settings.FORCE_SCRIPT_NAME = "/checkout"


def test_healthz_responde_200_com_force_script_name(client, env_de_producao):
    # Nenhum host cadastrado no catálogo: se o middleware tentar resolver o
    # site (o bug), recebe 404 — exatamente o cenário medido em produção, onde
    # a sonda chega com Host "localhost".
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=r".*/sites/by-host/.*").mock(
            return_value=httpx.Response(404)
        )
        resp = client.get("/healthz")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}


def test_static_isento_do_conv_site_com_force_script_name(client, env_de_producao):
    # A MESMA isenção cobre /static/ — se o middleware interceptar, o 404 vem
    # do CONV-SITE (site desconhecido) e não do arquivo; aqui só provamos que a
    # requisição NÃO morre na resolução de site (o catálogo nunca é chamado).
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.get(url__regex=r".*/sites/by-host/.*").mock(
            return_value=httpx.Response(404)
        )
        client.get("/static/checkout/api.js")
    assert not rota.called
