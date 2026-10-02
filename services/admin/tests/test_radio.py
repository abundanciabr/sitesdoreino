"""A retirada do rádio fecha os acessos e conserva o histórico no banco."""

import pytest
from django.apps import apps
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.test import RequestFactory
from django.urls import Resolver404, resolve

from apps.core.views import acesso_local


@pytest.mark.parametrize(
    "caminho", ["/caixa/radio/", "/caixa/radio/api/", "/caixa/radio/radio.js"]
)
def test_rotas_do_radio_nao_existem(caminho, client, settings):
    with pytest.raises(Resolver404):
        resolve(caminho)
    settings.ADMIN_LINK_TOKEN = "convite-teste"
    settings.ADMIN_LOCAL_EMAIL = "dono@casa"
    settings.ADMIN_EMAILS = "dono@casa"
    entrada = acesso_local(
        RequestFactory().get("/acesso-local/convite-teste/"), "convite-teste"
    )
    client.cookies.update(entrada.cookies)
    assert client.get(caminho).status_code == 404
    assert (
        client.post(
            caminho, {"texto": "nao gravar"}, content_type="application/json"
        ).status_code
        == 404
    )


def test_modelo_do_radio_nao_e_carregado():
    with pytest.raises(LookupError):
        apps.get_model("core", "MensagemDoRadio")


def test_migracao_retira_modelo_sem_apagar_historico():
    # O MESMO banco da suíte, como `tests/test_livro.py` já faz. Um
    # `ConnectionHandler` avulso com apelido `default` deixava o registro de
    # migrações (que resolve o apelido pelo handler global) cair no Postgres da
    # suíte enquanto o esquema ia para um SQLite em memória, e a ida e volta
    # passava por acidente até a 35ª migração chegar. No Postgres o DDL é
    # transacional e a transação do teste desfaz tudo; no SQLite o `finally`
    # leva o banco de volta às folhas.
    banco = connection
    folhas = MigrationExecutor(banco).loader.graph.leaf_nodes()
    anterior = [("core", "0022_midia")]
    atual = [("core", "0024_retirar_radio_preservando_historico")]
    try:
        executor = MigrationExecutor(banco)
        executor.migrate(anterior)
        with banco.cursor() as cursor:
            cursor.execute(
                "INSERT INTO core_mensagemdoradio (autor, quando, texto, tarefa, tipo, chave_boletim) VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    "mantenedor",
                    "2026-09-21 12:00:00",
                    "historico preservado",
                    "TAR-001",
                    "recado",
                    "chave-historica",
                ],
            )
            cursor.execute("SELECT * FROM core_mensagemdoradio")
            historico = cursor.fetchall()
        executor = MigrationExecutor(banco)
        executor.migrate(atual)
        with pytest.raises(LookupError):
            executor.loader.project_state(atual).apps.get_model(
                "core", "MensagemDoRadio"
            )
        with banco.cursor() as cursor:
            cursor.execute("SELECT * FROM core_mensagemdoradio")
            assert cursor.fetchall() == historico
        executor = MigrationExecutor(banco)
        executor.migrate(anterior)
        assert executor.loader.project_state(anterior).apps.get_model(
            "core", "MensagemDoRadio"
        )
        with banco.cursor() as cursor:
            cursor.execute("SELECT * FROM core_mensagemdoradio")
            assert cursor.fetchall() == historico
    finally:
        if banco.vendor == "sqlite":
            MigrationExecutor(banco).migrate(folhas)
