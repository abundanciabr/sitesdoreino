import json
from importlib import import_module
from pathlib import Path

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import RequestFactory
from django.urls import Resolver404, resolve

from apps.core.views import acesso_local

ROTAS = ("/caixa/radio/", "/caixa/radio/api/", "/caixa/radio/radio.js")
RAIZ = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("rota", ROTAS)
def test_enderecos_do_radio_nao_tem_rota(rota):
    with pytest.raises(Resolver404):
        resolve(rota)


@pytest.mark.parametrize("rota", ROTAS)
@pytest.mark.parametrize("metodo", ("get", "post"))
def test_radio_nao_abre_nem_grava_com_cracha(client, settings, rota, metodo):
    settings.ADMIN_LINK_TOKEN = "convite-teste"
    settings.ADMIN_LOCAL_EMAIL = "dono@casa"
    settings.ADMIN_EMAILS = "dono@casa"
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-teste/"), "convite-teste"
    )
    client.cookies.update(entrada.cookies)
    resposta = getattr(client, metodo)(rota, data={"texto": "nao gravar"})
    assert resposta.status_code == 404


def test_token_antigo_nao_contorna_a_porta(client):
    # guarda: services/admin/apps/core/porta.py:299
    resposta = client.get(
        "/caixa/radio/api/",
        HTTP_AUTHORIZATION="Bearer token-antigo",
        HTTP_ACCEPT="application/json",
    )
    assert resposta.status_code == 302


def test_modelo_nao_esta_disponivel_na_aplicacao():
    with pytest.raises(LookupError):
        apps.get_model("core", "MensagemDoRadio")


def test_mapa_nao_oferece_os_enderecos_removidos():
    mapa = json.loads((RAIZ / "painel/mapa-do-site.json").read_text(encoding="utf-8"))
    assert "caixa/radio/" not in json.dumps(mapa)


def test_retirar_modelo_preserva_mensagens_historicas():
    anterior = MigrationLoader(connection).project_state([("core", "0022_midia")])
    Historico = anterior.apps.get_model("core", "MensagemDoRadio")
    mensagem = Historico.objects.create(
        autor="mantenedor", texto="Registro preservado", tipo="recado"
    )
    migration = import_module(
        "apps.core.migrations.0024_retirar_modelo_do_radio"
    ).Migration("0024_retirar_modelo_do_radio", "core")
    operacao = migration.operations[0]
    assert operacao.database_operations == []
    posterior = migration.apply(anterior, connection.schema_editor(atomic=False))
    with pytest.raises(LookupError):
        posterior.apps.get_model("core", "MensagemDoRadio")
    assert Historico.objects.get(pk=mensagem.pk).texto == "Registro preservado"
    restaurado = migration.unapply(
        MigrationLoader(connection).project_state([("core", "0022_midia")]),
        connection.schema_editor(atomic=False),
    )
    assert (
        restaurado.apps.get_model("core", "MensagemDoRadio")
        .objects.get(pk=mensagem.pk)
        .texto
        == "Registro preservado"
    )
