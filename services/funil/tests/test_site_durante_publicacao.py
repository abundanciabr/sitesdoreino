"""A entrada continua servindo durante a indisponibilidade temporária do catálogo."""
from types import SimpleNamespace

import httpx
import pytest

from apps.core import middleware
from tests.conftest import CATALOGO, HOST_DESCONHECIDO, HOST_MESH, SITE_MESH


@pytest.fixture
def relogio(monkeypatch):
    instante = [1000.0]
    monkeypatch.setattr(middleware, "time", SimpleNamespace(time=lambda: instante[0]))
    return instante


FALHAS = [
    httpx.Response(status) for status in (401, 403, 429, 500, 502, 503, 504)
] + [
    httpx.Response(200, text="resposta interrompida"),
    httpx.Response(200, json=[]),
    httpx.Response(200, json={}),
    httpx.ConnectError("indisponível"),
    httpx.ReadTimeout("indisponível"),
]


def responder(rede, host, resultado):
    rota = rede.get(f"{CATALOGO}/sites/by-host/{host}")
    if isinstance(resultado, Exception):
        rota.mock(side_effect=resultado)
    else:
        rota.mock(return_value=resultado)
    return rota


@pytest.mark.parametrize("falha", FALHAS)
def test_home_preserva_configuracao_e_recupera_sem_404(client, rede, relogio, falha):
    inicial = client.get("/", HTTP_HOST=HOST_MESH)
    assert inicial.status_code == 200
    relogio[0] += 61
    rota = responder(rede, HOST_MESH, falha)
    durante = client.get("/", HTTP_HOST=HOST_MESH)
    assert durante.status_code == 200
    assert durante.content == inicial.content
    chamadas = rota.call_count
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    assert rota.call_count == chamadas

    relogio[0] += 6
    responder(rede, HOST_MESH, httpx.Response(200, json={**SITE_MESH, "name": "Nome atualizado"}))
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    assert middleware._CACHE[HOST_MESH][1]["name"] == "Nome atualizado"


@pytest.mark.parametrize("falha", FALHAS)
def test_sem_configuracao_falha_e_temporaria_e_nao_envenena_cache(
    client, rede, relogio, falha
):
    responder(rede, HOST_MESH, falha)
    resposta = client.get("/", HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 503
    assert resposta["Retry-After"] == "5"
    assert resposta["Cache-Control"] == "no-store"

    responder(rede, HOST_MESH, httpx.Response(200, json=SITE_MESH))
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200


def test_404_confirmado_retira_configuracao_antiga(client, rede, relogio):
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    relogio[0] += 61
    responder(rede, HOST_MESH, httpx.Response(404))
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 404
    relogio[0] += 61
    responder(rede, HOST_MESH, httpx.Response(502))
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 503


def test_site_desativado_nao_reaproveita_configuracao_antiga(client, rede, relogio):
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    relogio[0] += 61
    responder(rede, HOST_MESH, httpx.Response(200, json={**SITE_MESH, "active": False}))
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 404


def test_host_diferente_nao_herda_site_durante_falha(client, rede, relogio):
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    responder(rede, HOST_DESCONHECIDO, httpx.Response(502))
    assert client.get("/", HTTP_HOST=HOST_DESCONHECIDO).status_code == 503
    responder(rede, HOST_DESCONHECIDO, httpx.Response(404))
    assert client.get("/", HTTP_HOST=HOST_DESCONHECIDO).status_code == 404


def test_falha_repetida_nao_apaga_a_ultima_configuracao(client, rede, relogio):
    assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
    responder(rede, HOST_MESH, httpx.Response(502))
    for _ in range(5):
        relogio[0] += 61
        assert client.get("/", HTTP_HOST=HOST_MESH).status_code == 200
