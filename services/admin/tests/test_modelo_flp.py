import base64
import re
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
import re
from io import BytesIOspx
from django.test import Client
from django.urls import get_script_prefix, set_script_prefix

from apps.core.modelo_flp import PACOTE, pagina_embutida

ROTAS = ["/modelos-de-paginas/flp-0", "/modelos-de-paginas/flp-0/conteudo"]
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
def test_porta_preservada(rota):
    assert Client().get(rota).status_code == 302
    assert entrar("aluno@example.com").get(rota).status_code == 404
    cliente = entrar()
    assert cliente.get(rota).status_code == 200
    respx.get(SESSAO).mock(side_effect=httpx.ConnectError("indisponível"))
    assert cliente.get(rota).status_code == 503


@respx.mock
def test_moldura_opaca_e_prefixo():
    anterior = get_script_prefix()
    try:
        set_script_prefix("/admin/")
        resposta = entrar().get(ROTAS[0] + "?utm_source=teste")
    finally:
        set_script_prefix(anterior)
    html = resposta.content.decode()
    assert 'sandbox="allow-scripts allow-forms"' in html
    assert "allow-same-origin" not in html
    assert 'src="/admin/modelos-de-paginas/flp-0/conteudo?utm_source=teste"' in html
    assert resposta["Cache-Control"] == "no-store"


@respx.mock
def test_conteudo_direto_tambem_isolado():
    resposta = entrar().get(ROTAS[1])
    csp = resposta["Content-Security-Policy"]
    assert "sandbox allow-scripts allow-forms;" in csp
    assert "allow-same-origin" not in csp
    assert "connect-src https://webhook.crazyleads.com.br;" in csp
    assert "frame-ancestors 'self'" in csp
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Referrer-Policy"] == "no-referrer"
    assert resposta["Cache-Control"] == "no-store"


def test_recursos_incorporados_sem_rotas_publicas():
    html = pagina_embutida()
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        assert len(pacote.namelist()) == 66
        for nome in pacote.namelist():
            if nome != "index.html":
                assert "/" + nome not in html
    scripts = re.findall(r'<script[^>]*src="([^"]+)"', html)
    assert len(scripts) == 19
    assert all(s.startswith("data:text/javascript;base64,") for s in scripts)
    codigo = "\n".join(base64.b64decode(s.split(",", 1)[1]).decode() for s in scripts)
    assert "https://webhook.crazyleads.com.br/form/" in codigo
    assert "document.cookie" not in codigo
    assert "../media/" not in "\n".join(
        base64.b64decode(s).decode()
        for s in re.findall(r"data:text/css;base64,([A-Za-z0-9+/=]+)", html)
    )


@pytest.mark.parametrize("rota", ROTAS)
@respx.mock
def test_so_leitura(rota):
    assert entrar().post(rota).status_code == 405
