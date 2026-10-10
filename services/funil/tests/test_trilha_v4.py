"""A trilha mostra somente o progresso da própria sessão, sem divulgá-la."""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from conftest import HOST_A, HOST_MESH, SITE_MESH

GAMIFICACAO = "http://gamificacao.teste/api/gamificacao"
COOKIE = "meshcraft_sessao=opaco-de-teste"


def progresso(pessoa="aluna-a", atual=3):
    return {"pessoa_id": pessoa, "site_id": SITE_MESH["id"], "atual_ordem": atual,
        "total_cents": 0, "meta_cents": None, "meta_escolhida": False,
        "etapas": [{"ordem": i, "nome": "Faixa de teste", "alcancada": i in {1, atual},
                    "conquista": "Marco registrado", "meta_cents": None, "alcancada_em": None}
                   for i in range(1, 14)]}


@pytest.fixture
def conta(rede, monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("GAMIFICACAO_API_TOKEN", "token-funil-gamificacao")
    rede["get_session"].respond(200, json={"autenticado": True, "id": "aluna-a", "nome_exibido": "Ana Silva", "papel": "aluno"})
    rede.get(GAMIFICACAO + "/minha-trilha", name="minha_trilha").respond(200, json=progresso())
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


def test_aluno_ve_somente_seu_progresso_e_nao_escolhe_outro(client, conta):
    resposta = abrir(client, "/trilha/?aluno=999&pessoa_id=aluna-b&site_id=outro-site")
    assert resposta.status_code == 200
    payload = dados(resposta)
    assert payload["aluno"] == {"nome": "Ana"}
    assert payload["progresso"] == progresso()
    assert [x["alcancada"] for x in payload["progresso"]["etapas"][:3]] == [True, False, True]
    chamada = conta["minha_trilha"].calls.last.request
    assert not chamada.url.query
    assert chamada.headers["cookie"] == COOKIE
    assert chamada.headers["authorization"] == "Bearer token-funil-gamificacao"
    assert b"/admin/" not in resposta.content
    assert "Acesso administrativo" not in resposta.content.decode()
    privada(resposta)


def test_trocar_de_sessao_troca_dados_sem_cache_compartilhado(client, conta):
    assert dados(abrir(client))["progresso"]["pessoa_id"] == "aluna-a"
    conta["get_session"].respond(200, json={"autenticado": True, "id": "aluna-b", "nome_exibido": "Bia", "papel": "aluno"})
    conta["minha_trilha"].respond(200, json=progresso("aluna-b", atual=4))
    resposta = client.get("/trilha/", HTTP_HOST=HOST_MESH, HTTP_COOKIE="meshcraft_sessao=outra")
    assert dados(resposta)["aluno"]["nome"] == "Bia"
    assert dados(resposta)["progresso"]["atual_ordem"] == 4
    assert b"aluna-a" not in resposta.content
    privada(resposta)


@pytest.mark.parametrize("problema", ["pessoa", "site", "etapas", "atual", "meta", "json"])
def test_nao_mostra_outro_aluno_ou_dados_incompletos(client, conta, problema):
    corpo = progresso()
    if problema == "pessoa": corpo["pessoa_id"] = "aluna-b"
    if problema == "site": corpo["site_id"] = "outro-site"
    if problema == "etapas": corpo["etapas"].pop()
    if problema == "atual": corpo["atual_ordem"] = 13
    if problema == "meta": corpo["meta_escolhida"] = True
    if problema == "json":
        conta["minha_trilha"].respond(200, text="nao-json")
    else:
        conta["minha_trilha"].respond(200, json=corpo)
    resposta = abrir(client)
    assert resposta.status_code == 503
    assert b"trilha-data" not in resposta.content
    privada(resposta)


@pytest.mark.parametrize("status,esperado", [(403, 302), (401, 503), (500, 503)])
def test_falhas_da_consulta_nao_exibem_dados_ficticios(client, conta, status, esperado):
    conta["minha_trilha"].respond(status)
    resposta = abrir(client)
    assert resposta.status_code == esperado
    assert b"trilha-data" not in resposta.content
    privada(resposta)


def test_sessao_invalida_e_indisponibilidade_fecham_o_acesso(client, conta):
    conta["get_session"].respond(200, json={"autenticado": False})
    assert abrir(client).status_code == 302
    assert not conta["minha_trilha"].called
    conta["get_session"].respond(503)
    assert abrir(client).status_code == 503
    conta["get_session"].respond(200, json={"autenticado": "true", "id": "aluna-a"})
    assert abrir(client).status_code == 503
    conta["get_session"].mock(side_effect=httpx.ConnectError("rede fora do ar"))
    assert abrir(client).status_code == 503


def test_sem_configuracao_ou_timeout_nao_usa_demo(client, conta, monkeypatch):
    conta["minha_trilha"].mock(side_effect=httpx.ReadTimeout("demorou"))
    assert abrir(client).status_code == 503
    monkeypatch.delenv("GAMIFICACAO_API_TOKEN")
    assert abrir(client).status_code == 503
    monkeypatch.delenv("IDENTIDADE_API_TOKEN")
    assert abrir(client).status_code == 503


def test_nome_e_conquista_nao_injetam_html(client, conta):
    conta["get_session"].respond(200, json={"autenticado": True, "id": "aluna-a", "nome_exibido": "<script>alert(1)</script>"})
    corpo = progresso()
    corpo["etapas"][0]["conquista"] = "</script><script>alert(2)</script>"
    conta["minha_trilha"].respond(200, json=corpo)
    resposta = abrir(client)
    assert resposta.status_code == 200
    assert b"<script>alert(" not in resposta.content
    assert dados(resposta)["progresso"] == corpo


def test_ativos_autenticados_preservam_css_v4(client, conta):
    raiz = Path(__file__).resolve().parents[3]
    css = abrir(client, "/trilha/style.css")
    js = abrir(client, "/trilha/app.js")
    assert css.status_code == js.status_code == 200
    assert css.content == (raiz / "services/admin/apps/core/trilha_v4/style.css").read_bytes()
    assert b"Consulta administrativa" not in js.content
    privada(css)
    privada(js)
    assert not conta["minha_trilha"].called


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
    assert not conta["minha_trilha"].called
