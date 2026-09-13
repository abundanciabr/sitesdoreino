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
