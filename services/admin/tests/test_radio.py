import json

import pytest
from django.db import DatabaseError
from django.test import RequestFactory
from django.urls import reverse

from apps.core.models import MensagemDoRadio
from apps.core.radio import radio_api, radio_pagina


@pytest.fixture
def cracha():
    return {"id": "mantenedor", "nome": "Mantenedor", "email": "dono@casa"}


def pedido(metodo, caminho, corpo=None, admin=None):
    request = getattr(RequestFactory(), metodo.lower())(
        caminho,
        data=json.dumps(corpo) if corpo is not None else None,
        content_type="application/json",
    )
    request._dont_enforce_csrf_checks = True
    if admin is not None:
        request.admin = admin
    return request


def test_post_sem_cracha_responde_403():
    resposta = radio_api(
        pedido("POST", reverse("radio_pagina"), {"autor": "codex", "texto": "oi"})
    )
    assert resposta.status_code == 403


def test_post_http_sem_cracha_responde_403(client):
    resposta = client.post(
        reverse("radio_api"),
        data=json.dumps({"autor": "codex", "texto": "oi"}),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    assert resposta.status_code == 403


def test_post_e_get_desde_devolvem_somente_o_que_veio_depois(db, cracha):
    primeira = radio_api(
        pedido(
            "POST",
            reverse("radio_pagina"),
            {"autor": "codex", "texto": "primeira"},
            cracha,
        )
    )
    segunda = radio_api(
        pedido(
            "POST",
            reverse("radio_pagina"),
            {"autor": "mantenedor", "texto": "segunda", "tarefa": "TAR-374"},
            cracha,
        )
    )
    assert primeira.status_code == 201
    assert segunda.status_code == 201
    primeira_json = json.loads(primeira.content)
    segunda_json = json.loads(segunda.content)
    desde = primeira_json["sequencia"]
    leitura = radio_api(
        pedido("GET", f"{reverse('radio_pagina')}?desde={desde}", admin=cracha)
    )
    leitura_json = json.loads(leitura.content)
    assert [item["texto"] for item in leitura_json["mensagens"]] == ["segunda"]
    assert leitura_json["ultima_sequencia"] == segunda_json["sequencia"]


@pytest.mark.parametrize("estado", ["vazio", "mensagens"])
def test_pagina_renderiza_estado_normal(db, cracha, estado):
    if estado == "mensagens":
        MensagemDoRadio.objects.create(
            autor="claude", texto="uma mensagem", tarefa="TAR-374"
        )
    resposta = radio_pagina(pedido("GET", reverse("radio_pagina"), admin=cracha))
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Rádio da tríade" in corpo
    assert "textarea" in corpo
    assert ("Nenhuma mensagem" in corpo) is (estado == "vazio")
    assert ("<p>uma mensagem</p>" in corpo) is (estado == "mensagens")


def test_pagina_renderiza_erro_e_primeiro_uso(cracha, monkeypatch):
    monkeypatch.setattr(
        MensagemDoRadio.objects,
        "order_by",
        lambda *args, **kwargs: (_ for _ in ()).throw(DatabaseError("banco fora")),
    )
    resposta = radio_pagina(pedido("GET", reverse("radio_pagina"), admin=cracha))
    assert resposta.status_code == 200
    assert "não consegui carregar" in resposta.content.decode().lower()
    assert "escreva a primeira" in resposta.content.decode().lower()


@pytest.mark.parametrize(
    "cabecalho",
    [{"HTTP_AUTHORIZATION": "Bearer invalido"}, {"HTTP_ACCEPT": "application/json"}],
)
def test_pagina_nao_abre_so_com_cabecalho(client, db, cabecalho):
    resposta = client.get(reverse("radio_pagina"), **cabecalho)
    assert resposta.status_code == 302
    assert "Rádio da tríade" not in resposta.content.decode()


def test_api_aceita_cookie_do_lancador_local(client, db, settings):
    from apps.core.views import acesso_local

    settings.ADMIN_LINK_TOKEN = "convite-radio"
    settings.ADMIN_LOCAL_EMAIL = "dono@casa"
    settings.ADMIN_EMAILS = "dono@casa"
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-radio/"), "convite-radio"
    )
    client.cookies.update(entrada.cookies)
    resposta = client.get(reverse("radio_api"), HTTP_ACCEPT="application/json")
    assert resposta.status_code == 200
    assert resposta.json()["mensagens"] == []


@pytest.fixture
def navegador_radio(settings):
    from django.test import Client
    from apps.core.views import acesso_local

    settings.ADMIN_LINK_TOKEN = "convite-radio"
    settings.ADMIN_LOCAL_EMAIL = "dono@casa"
    settings.ADMIN_EMAILS = "dono@casa"
    cliente = Client(enforce_csrf_checks=True)
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-radio/"), "convite-radio"
    )
    cliente.cookies.update(entrada.cookies)
    cliente.get(reverse("radio_pagina"))
    return cliente


def test_formulario_sem_javascript_grava_e_volta_para_tela(
    db, navegador_radio, settings
):
    # guarda: services/admin/apps/core/radio.py:112
    cliente = navegador_radio
    resposta = cliente.post(
        reverse("radio_pagina"),
        {
            "texto": "Mensagem humana",
            "csrfmiddlewaretoken": cliente.cookies[settings.CSRF_COOKIE_NAME].value,
        },
    )
    assert resposta.status_code == 302
    assert resposta.url == reverse("radio_pagina")
    assert MensagemDoRadio.objects.get().autor == "mantenedor"
    tela = cliente.get(resposta.url).content.decode()
    assert "Mensagem humana" in tela
    assert 'action="' + reverse("radio_pagina") + '"' in tela


@pytest.mark.parametrize("texto", ["   ", "x" * 2001])
def test_formulario_invalido_preserva_texto_na_tela(
    db, navegador_radio, settings, texto
):
    resposta = navegador_radio.post(
        reverse("radio_pagina"),
        {
            "texto": texto,
            "csrfmiddlewaretoken": navegador_radio.cookies[
                settings.CSRF_COOKIE_NAME
            ].value,
        },
    )
    assert resposta.status_code == 400
    assert texto in resposta.content.decode()
    assert "2.000" in resposta.content.decode()
    assert not MensagemDoRadio.objects.exists()


def test_formulario_recusa_csrf_ausente(db, navegador_radio):
    resposta = navegador_radio.post(reverse("radio_pagina"), {"texto": "nao gravar"})
    assert resposta.status_code == 403
    assert not MensagemDoRadio.objects.exists()


def test_falha_ao_gravar_preserva_texto(db, navegador_radio, settings, monkeypatch):
    def falha(**kwargs):
        raise DatabaseError("indisponivel")

    monkeypatch.setattr(MensagemDoRadio.objects, "create", falha)
    resposta = navegador_radio.post(
        reverse("radio_pagina"),
        {
            "texto": "Preserve esta mensagem",
            "csrfmiddlewaretoken": navegador_radio.cookies[
                settings.CSRF_COOKIE_NAME
            ].value,
        },
    )
    assert resposta.status_code == 503
    assert "Preserve esta mensagem" in resposta.content.decode()
    assert "tente novamente" in resposta.content.decode()


def test_javascript_externo_permitido_pela_csp(db, navegador_radio):
    from html.parser import HTMLParser

    class Scripts(HTMLParser):
        encontrados = []

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                self.encontrados.append(dict(attrs))

    tela = navegador_radio.get(reverse("radio_pagina"))
    parser = Scripts()
    parser.feed(tela.content.decode())
    assert parser.encontrados
    assert all(item.get("src") for item in parser.encontrados)
    resposta = navegador_radio.get(parser.encontrados[-1]["src"])
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("application/javascript")
    assert "setTimeout" in resposta.content.decode()


def test_api_json_com_cookie_exige_csrf(db, navegador_radio):
    resposta = navegador_radio.post(
        reverse("radio_api"),
        data=json.dumps({"autor": "mantenedor", "texto": "nao gravar"}),
        content_type="application/json",
    )
    assert resposta.status_code == 403
    assert not MensagemDoRadio.objects.exists()


def test_api_bearer_continua_gravando_sem_cookie_ou_csrf(db, settings):
    from django.test import Client

    settings.ADMIN_RADIO_TOKEN = "token-da-maquina"
    resposta = Client(enforce_csrf_checks=True).post(
        reverse("radio_api"),
        data=json.dumps({"autor": "codex", "texto": "mensagem CLI"}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer token-da-maquina",
    )
    assert resposta.status_code == 201
    assert MensagemDoRadio.objects.get().texto == "mensagem CLI"
