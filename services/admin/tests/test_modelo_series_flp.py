import base64
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, set_script_prefix

from apps.core.modelo_series_flp import PACOTE, pagina_embutida

ROTAS = [
    "/modelos-de-paginas/series-flp-gpt",
    "/modelos-de-paginas/series-flp-gpt/conteudo",
]
SESSAO = "http://identidade:8000/interno/sessao/completa"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@example.com"
    settings.DEBUG = False
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "teste")


def entrar(email="dono@example.com"):
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "teste",
                "email": email,
                "nome_exibido": "Teste",
                "papel": None,
            },
        )
    )
    return Client(HTTP_COOKIE="meshcraft_sessao=teste")


@pytest.mark.parametrize("rota", ROTAS)
@respx.mock
def test_porta_administrativa_preservada(rota):
    assert Client().get(rota).status_code == 302
    assert entrar("aluno@example.com").get(rota).status_code == 404
    cliente = entrar()
    assert cliente.get(rota).status_code == 200
    assert cliente.post(rota).status_code == 405
    respx.get(SESSAO).mock(side_effect=httpx.ConnectError("indisponível"))
    assert cliente.get(rota).status_code == 503


@respx.mock
def test_moldura_encaminha_apenas_episodio_valido():
    prefixo = get_script_prefix()
    try:
        set_script_prefix("/admin/")
        resposta = entrar().get(ROTAS[0] + "?ep=2&playerHost=https://example.com")
    finally:
        set_script_prefix(prefixo)
    html = resposta.content.decode()
    assert 'sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"' in html
    assert "allow-same-origin" not in html
    assert 'src="/admin/modelos-de-paginas/series-flp-gpt/conteudo?ep=2"' in html
    assert "playerHost" not in html
    assert "location.assign('?ep=' + episodio)" in html
    assert "'sha256-" in resposta["Content-Security-Policy"]
    assert resposta["Cache-Control"] == "no-store"
    assert "frame-ancestors 'self'" in resposta["Content-Security-Policy"]
    assert "script-src 'self'" in resposta["Content-Security-Policy"]


@respx.mock
def test_episodio_invalido_abre_primeiro():
    resposta = entrar().get(ROTAS[0] + "?ep=6")
    assert (
        'src="/modelos-de-paginas/series-flp-gpt/conteudo"' in resposta.content.decode()
    )


@respx.mock
def test_conteudo_direto_permanece_opaco_e_sem_cache():
    resposta = entrar().get(ROTAS[1] + "?ep=1")
    csp = resposta["Content-Security-Policy"]
    assert "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox;" in csp
    assert "allow-same-origin" not in csp
    assert "script-src data: https://scripts.converteai.net;" in csp
    assert "connect-src https://cdn.converteai.net https://license.vturb.com;" in csp
    assert "form-action 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Referrer-Policy"] == "no-referrer"
    assert resposta["Cache-Control"] == "no-store"


def test_clone_fica_embutido_e_link_externo_abre_fora_do_sandbox():
    pagina = pagina_embutida()
    assert PACOTE.is_file()
    assert "./assets/" not in pagina
    assert 'href="./base.css"' not in pagina
    assert 'src="./app.js"' not in pagina
    assert len(re.findall(r'<link[^>]+href="data:text/css;base64,', pagina)) == 3
    assert pagina.count('target="_blank" rel="noopener noreferrer" data-cl-cta=') == 2
    assert (
        "https://vendatodosantodia.com.br/formula-de-lancamento-pago/bf-26/" in pagina
    )
    scripts = re.findall(
        r'<script[^>]+src="(data:text/javascript;base64,[^"]+)', pagina
    )
    assert len(scripts) == 2
    memoria = base64.b64decode(scripts[0].split(",", 1)[1]).decode()
    assert "Object.defineProperty(window,nome" in memoria
    codigo = base64.b64decode(scripts[1].split(",", 1)[1]).decode()
    assert "parent.postMessage({episodio:index+1}" in codigo
    assert "if(!ready) showError();" in codigo
    assert "assets/player" not in codigo
    assert codigo.count("data:text/javascript;base64,") == 2
    provedores = [
        base64.b64decode(script).decode()
        for script in re.findall(
            r"data:text/javascript;base64,([A-Za-z0-9+/=]+)", codigo
        )
    ]
    assert all(
        "https://scripts.converteai.net/lib/js/smartplayer-wc/" in script
        for script in provedores
    )
    assert "https://www.googletagmanager.com" not in pagina
    assert "connect.facebook.net" not in pagina
