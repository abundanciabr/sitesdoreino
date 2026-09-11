"""A criação e a lista de aulas avulsas do painel da escola."""

import json
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.auditoria.models import Registro
from apps.core.clients import CursosClient

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-do-par-admin-cursos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _cliente() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _site():
    return respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )


def _aula(titulo="Como vender seu primeiro item", slug="como-vender-seu-primeiro-item"):
    return {
        "titulo": titulo,
        "slug": slug,
        "video_url": "https://www.youtube.com/watch?v=abcdefghijk",
        "descricao": "Uma resposta objetiva para a dúvida da turma.",
        "estado": "publicada",
        "publicada_em": "2026-09-11T12:00:00+00:00",
    }


@respx.mock
def test_cliente_lista_e_cria_pela_porta_do_contrato():
    lista = respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=[_aula()])
    )
    criar = respx.post(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(201, json=_aula())
    )

    cliente = CursosClient()
    assert cliente.aulas_avulsas(SITE_ID) == (CursosClient.OK, [_aula()])
    assert cliente.criar_aula_avulsa(
        SITE_ID,
        {
            "titulo": "Nome",
            "video_url": "https://youtu.be/abcdefghijk",
            "descricao": "",
        },
    ) == (CursosClient.OK, _aula())
    assert lista.called and criar.called
    assert json.loads(criar.calls[0].request.content) == {
        "titulo": "Nome",
        "video_url": "https://youtu.be/abcdefghijk",
        "descricao": "",
    }


@respx.mock
def test_tela_lista_cria_e_mostra_o_link_final_do_servico():
    _site()
    respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=[_aula()])
    )
    resposta = _cliente().get(reverse("escola_aulas_avulsas"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Aulas avulsas" in html
    assert "Como vender seu primeiro item" in html
    assert 'name="titulo"' in html
    assert 'name="video_url"' in html
    assert 'name="descricao"' in html
    assert 'name="slug"' not in html
    assert "A URL final é criada ao publicar" in html

    _site()
    criar = respx.post(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            201, json=_aula(slug="slug-que-o-servidor-escolheu")
        )
    )
    respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            200, json=[_aula(slug="slug-que-o-servidor-escolheu")]
        )
    )
    resposta = _cliente().post(
        reverse("escola_aula_avulsa_criar"),
        {
            "titulo": "Como vender seu primeiro item",
            "video_url": "https://youtu.be/abcdefghijk",
            "descricao": "Uma resposta objetiva para a dúvida da turma.",
        },
    )
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert criar.called
    assert "/aulas/slug-que-o-servidor-escolheu/" in html
    assert "Copiar o link" in html
    registro = Registro.objects.get()
    assert (registro.acao, registro.alvo, registro.desfecho) == (
        Registro.CRIAR_AULA_AVULSA,
        "slug-que-o-servidor-escolheu",
        Registro.OK,
    )


@respx.mock
def test_criacao_preserva_o_link_quando_a_lista_nao_responde():
    _site()
    respx.post(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(201, json=_aula(slug="resposta-da-sala"))
    )
    respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(503, json={"detail": "ocupada"})
    )

    resposta = _cliente().post(
        reverse("escola_aula_avulsa_criar"),
        {
            "titulo": "Como vender seu primeiro item",
            "video_url": "https://youtu.be/abcdefghijk",
            "descricao": "Uma resposta objetiva para a dúvida da turma.",
        },
    )

    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "A aula foi publicada" in html
    assert "/aulas/resposta-da-sala/" in html
    assert "não respondeu" in html


@respx.mock
@pytest.mark.parametrize(
    ("status", "texto", "desfecho"),
    [
        (422, "não aceitou", Registro.RECUSADO_PELA_CELULA),
        (409, "endereço", Registro.RECUSADO_PELA_CELULA),
        (403, "recusou a admin", Registro.NAO_RESPONDEU),
        (503, "não respondeu", Registro.NAO_RESPONDEU),
    ],
)
def test_criacao_da_aula_traduz_cada_desfecho(status, texto, desfecho):
    _site()
    respx.post(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(status, json={"detail": "motivo da recusa"})
    )
    respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=[])
    )
    resposta = _cliente().post(
        reverse("escola_aula_avulsa_criar"),
        {
            "titulo": "Nome",
            "video_url": "https://youtu.be/abcdefghijk",
            "descricao": "",
        },
    )
    assert resposta.status_code == (
        409 if status == 409 else 503 if status in (403, 503) else 400
    )
    assert texto in resposta.content.decode().lower()
    registro = Registro.objects.get()
    assert (registro.acao, registro.alvo, registro.desfecho) == (
        Registro.CRIAR_AULA_AVULSA,
        "Nome",
        desfecho,
    )


@respx.mock
def test_previa_javascript_gera_endereco_sem_virar_campo_editavel():
    _site()
    respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=[])
    )
    html = _cliente().get(reverse("escola_aulas_avulsas")).content.decode()

    script = re.search(r"<script>(.*?)</script>", html, re.S)
    assert script, "a prévia precisa nascer com o formulário"
    codigo = script.group(1)
    assert 'normalize("NFKD"' in codigo
    assert 'titulo.addEventListener("input"' in codigo
    assert "previa.dataset.base" in codigo
    assert "navigator.clipboard" in codigo
    assert "Não consegui copiar o link" in codigo
    assert 'data-base="/aulas/"' in html
    assert 'name="slug"' not in html


@respx.mock
def test_links_da_tela_respeitam_script_name():
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        _site()
        respx.get(f"{CURSOS}/aulas-avulsas", params={"site_id": SITE_ID}).mock(
            return_value=httpx.Response(200, json=[])
        )
        html = _cliente().get("/escola/aulas-avulsas/").content.decode()
        assert 'action="/admin/escola/aulas-avulsas/criar"' in html
        assert 'data-base="/aulas/"' in html
    finally:
        set_script_prefix(anterior)
