"""A prévia e seus arquivos ficam restritos a admins, inclusive a visão visitante."""
import httpx
import pytest
import respx
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.core.feed_previa import feed_previa, feed_previa_asset

BASE = "http://identidade:8000/interno"


@pytest.fixture(autouse=True)
def porta(settings, monkeypatch):
    settings.ADMIN_EMAILS = "admin@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-de-teste")


def cliente():
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=exemplo"
    return c


def sessao(email, papel):
    return {"autenticado": True, "id": "pessoa-exemplo", "nome_exibido": "Pessoa",
            "email": email, "papel": papel}


@respx.mock
@pytest.mark.parametrize("nome", [None, "feed.js", "feed.css", "hero.png"])
def test_admin_recebe_pagina_e_assets_privados(nome):
    respx.get(f"{BASE}/sessao/completa").mock(return_value=httpx.Response(
        200, json=sessao("admin@exemplo.com", "admin")))
    url = reverse("feed_previa_asset", args=[nome]) if nome else reverse("feed_previa")
    r = cliente().get(url)
    assert r.status_code == 200
    assert r["Cache-Control"] == "no-store"
    if not nome:
        assert b"PR\xc3\x89VIA PRIVADA" in r.content
        assert "script-src 'self'" in r["Content-Security-Policy"]
        assert "media-src 'self' blob:" in r["Content-Security-Policy"]
        assert r["X-Robots-Tag"] == "noindex, nofollow"
    else:
        assert b"".join(r.streaming_content)


@respx.mock
@pytest.mark.parametrize("papel", ["aluno", "professor"])
@pytest.mark.parametrize("nome", [None, "feed.js", "hero.png"])
def test_alunos_e_professores_nao_recebem_previa_nem_arquivos(papel, nome):
    respx.get(f"{BASE}/sessao/completa").mock(return_value=httpx.Response(
        200, json=sessao("outra@exemplo.com", papel)))
    url = reverse("feed_previa_asset", args=[nome]) if nome else reverse("feed_previa")
    r = cliente().get(url)
    assert r.status_code == 403
    assert b"Minha primeira" not in r.content


def test_equipe_por_aparelho_nao_abre_a_previa():
    req = RequestFactory().get("/comunidade/feed/previa/")
    req.admin = {"id": "equipe-exemplo", "equipe_apenas": True}
    assert feed_previa(req).status_code == 404
    assert feed_previa_asset(req, "feed.js").status_code == 404


def test_arquivo_fora_da_lista_nao_e_servido():
    req = RequestFactory().get("/comunidade/feed/previa/assets/segredo")
    req.admin = {"id": "admin-exemplo", "equipe_apenas": False}
    assert feed_previa_asset(req, "../models.py").status_code == 404


@respx.mock
def test_endpoint_da_pagina_nao_aceita_post_de_xp():
    respx.get(f"{BASE}/sessao/completa").mock(return_value=httpx.Response(
        200, json=sessao("admin@exemplo.com", "admin")))
    assert cliente().post(reverse("feed_previa"), {"xp": 999}).status_code == 405


@respx.mock
def test_sem_sessao_nao_recebe_a_pagina():
    respx.get(f"{BASE}/sessao/completa").mock(return_value=httpx.Response(
        200, json={"autenticado": False}))
    r = cliente().get(reverse("feed_previa"))
    assert r.status_code == 302
    assert "/entrar/google" in r["Location"]
