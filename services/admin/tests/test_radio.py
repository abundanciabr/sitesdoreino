"""A retirada do rádio fecha os acessos e conserva o histórico no banco."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from django.apps import apps
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import ConnectionHandler
from django.urls import Resolver404, resolve

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer"
DONO = "dono@casa"


@pytest.mark.parametrize(
    "caminho", ["/caixa/radio/", "/caixa/radio/api/", "/caixa/radio/radio.js"]
)
@respx.mock
def test_rotas_do_radio_nao_existem(caminho, client, settings, monkeypatch):
    with pytest.raises(Resolver404):
        resolve(caminho)
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco",
                "nome_exibido": "Dono",
                "email": DONO,
            },
        )
    )
    client.defaults["HTTP_COOKIE"] = COOKIE
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


def test_mapa_nao_oferece_radio():
    raiz = Path(__file__).resolve().parents[3]
    mapa = json.loads((raiz / "painel/mapa-do-site.json").read_text(encoding="utf-8"))
    assert "caixa/radio" not in json.dumps(mapa)


def test_migracao_retira_modelo_sem_apagar_historico():
    banco = ConnectionHandler(
        {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    )["default"]
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
        banco.close()
