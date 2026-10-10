"""A trilha mostra somente o progresso da própria sessão, sem divulgá-la."""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from conftest import HOST_A, HOST_MESH, SITE_MESH

COOKIE = "meshcraft_sessao=opaco-de-teste"


@pytest.fixture
def conta(rede):
    rede["get_session"].respond(200, json={"autenticado": True, "id": "aluna-a", "nome_exibido": "Ana Silva", "papel": "aluno"})
    return rede


def abrir(client, caminho="/trilha/", **kwargs):
    return client.get(caminho, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE, **kwargs)


def dados(resposta):
    script = re.search(r'<script id="trilha-data" type="application/json">(.*?)</script>', resposta.content.decode(), re.S)
    assert script
    return json.loads(script[1])


def privada(resposta):
    assert "private" in resposta["Cache-Control"] and "no-store" in resposta["Cache-Control"]
    assert "Cookie" in resposta["Vary"]
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"


@pytest.mark.parametrize("caminho", ["/trilha/", "/trilha/style.css", "/trilha/app.js"])
def test_visitante_entra_na_conta_e_volta_para_a_trilha(client, rede, caminho):
    resposta = client.get(caminho, HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 302
    assert urlsplit(resposta["Location"]).path == "/login"
    assert parse_qs(urlsplit(resposta["Location"]).query) == {"next": ["/trilha/"]}
    privada(resposta)
    assert b"trilha-data" not in resposta.content


def test_aluno_recebe_contexto_proprio_sem_depender_da_ponte_da_gamificacao(client, conta, monkeypatch):
    monkeypatch.delenv("GAMIFICACAO_API_URL", raising=False)
    monkeypatch.delenv("GAMIFICACAO_API_TOKEN", raising=False)
    resposta = abrir(client, "/trilha/?aluno=999&pessoa_id=aluna-b&site_id=outro-site")
    assert resposta.status_code == 200
    assert dados(resposta) == {"aluno": {"nome": "Ana"}, "pessoa_id": "aluna-a", "site_id": SITE_MESH["id"]}
    assert all("gamificacao" not in str(c.request.url) for c in conta.calls)
    assert b"/admin/" not in resposta.content
    assert b'aria-busy="true"' in resposta.content
    privada(resposta)


def test_trocar_de_sessao_troca_contexto_sem_cache_compartilhado(client, conta):
    assert dados(abrir(client))["pessoa_id"] == "aluna-a"
    conta["get_session"].respond(200, json={"autenticado": True, "id": "aluna-b", "nome_exibido": "Bia", "papel": "aluno"})
    resposta = client.get("/trilha/", HTTP_HOST=HOST_MESH, HTTP_COOKIE="meshcraft_sessao=outra")
    assert dados(resposta)["aluno"]["nome"] == "Bia"
    assert dados(resposta)["pessoa_id"] == "aluna-b"
    assert b"aluna-a" not in resposta.content
    privada(resposta)


def test_sessao_invalida_e_indisponibilidade_fecham_o_acesso(client, conta):
    conta["get_session"].respond(200, json={"autenticado": False})
    assert abrir(client).status_code == 302
    conta["get_session"].respond(503)
    assert abrir(client).status_code == 503
    conta["get_session"].respond(200, json={"autenticado": "true", "id": "aluna-a"})
    assert abrir(client).status_code == 503
    conta["get_session"].mock(side_effect=httpx.ConnectError("rede fora do ar"))
    assert abrir(client).status_code == 503


def test_sem_identidade_nao_serve_pagina(client, conta, monkeypatch):
    monkeypatch.delenv("IDENTIDADE_API_TOKEN")
    assert abrir(client).status_code == 503


def test_nome_nao_injeta_html(client, conta):
    conta["get_session"].respond(200, json={"autenticado": True, "id": "aluna-a", "nome_exibido": "<script>alert(1)</script>"})
    resposta = abrir(client)
    assert resposta.status_code == 200
    assert b"<script>alert(" not in resposta.content
    assert dados(resposta)["aluno"]["nome"] == "<script>alert(1)</script>"


def test_ativos_autenticados_preservam_css_v4(client, conta):
    raiz = Path(__file__).resolve().parents[3]
    css = abrir(client, "/trilha/style.css")
    js = abrir(client, "/trilha/app.js")
    assert css.status_code == js.status_code == 200
    assert css.content.startswith((raiz / "services/admin/apps/core/trilha_v4/style.css").read_bytes())
    assert b"Consulta administrativa" not in js.content
    privada(css)
    privada(js)


@pytest.mark.parametrize("caminho", ["/static/funil/trilha-v4/index.html", "/static/funil/trilha-v4/style.css", "/static/funil/trilha-v4/app.js"])
def test_copia_publica_antiga_nao_existe(client, rede, caminho):
    assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404


def test_endereco_direto_sem_barra_e_outro_host(client, rede):
    resposta = client.get("/trilha", HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 301 and resposta["Location"] == "/trilha/"
    assert client.get("/trilha/", HTTP_HOST=HOST_A).status_code == 404


@pytest.mark.parametrize("caminho", ["/", "/sitemap.xml", "/llms.txt"])
def test_endereco_nao_divulgado_no_site(client, rede, caminho):
    resposta = client.get(caminho, HTTP_HOST=HOST_MESH, follow=True)
    assert resposta.status_code == 200
    assert "/trilha/" not in resposta.content.decode()


def test_nao_altera_progresso(client, conta):
    assert client.post("/trilha/", HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE).status_code == 405
