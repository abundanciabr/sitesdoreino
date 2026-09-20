"""O processo da VPS serve leitura sem abrir o painel administrativo."""

import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
from django.test import Client, override_settings


def cliente_leitura():
    assert importlib.util.find_spec("config.settings_leitura") is not None
    config = importlib.import_module("config.settings_leitura")
    return override_settings(
        ROOT_URLCONF=config.ROOT_URLCONF,
        MIDDLEWARE=config.MIDDLEWARE,
        FORCE_SCRIPT_NAME=config.FORCE_SCRIPT_NAME,
        DEBUG=config.DEBUG,
    )


def test_documentos_publicos_continuam_vivos_e_privados_ficam_fechados():
    from apps.core.models import Documento

    Documento.objects.create(
        nome="aberto", titulo="Aberto", corpo="Texto atual", publico=True
    )
    Documento.objects.create(nome="fechado", titulo="Segredo", corpo="Texto privado")
    Documento.objects.create(
        nome="antigo", titulo="Antigo", publico=True, arquivado=True
    )
    with cliente_leitura():
        client = Client()
        assert client.get("/docs/").status_code == 200
        resposta = client.get("/docs/aberto")
        assert resposta.status_code == 200
        assert b"Texto atual" in resposta.content
        assert client.get("/docs/fechado").status_code == 404
        assert client.get("/docs/antigo").status_code == 404
        assert client.post("/docs/aberto", {}).status_code == 405


@pytest.mark.parametrize(
    "caminho",
    [
        "/",
        "/admin/",
        "/admin/docs/",
        "/painel/",
        "/caixa/",
        "/escola/",
        "/entrar",
        "/entrar/google",
        "/acesso-local",
        "/documentos/novo",
        "/documentos/aberto/salvar",
        "/interno/docs",
        "/interno/openapi.json",
        "/interno/administradores/promover",
        "/mapa-ia/segredo.md",
    ],
)
def test_painel_login_escrita_e_demais_endpoints_nao_existem(caminho):
    with cliente_leitura():
        client = Client()
        assert client.get(caminho).status_code == 404
        assert client.post(caminho, {}).status_code == 404


def test_mapa_preserva_o_indice_publico():
    with cliente_leitura():
        assert Client().get("/healthz").status_code == 200
        resposta = Client().get("/mapa-ia/")
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/plain")


def test_consulta_interna_preserva_autenticacao_e_resposta():
    with cliente_leitura(), override_settings(
        TOKENS_ACEITOS={"par-teste"}, ADMIN_EMAILS="dono@example.org"
    ):
        client = Client()
        endereco = "/interno/administradores/consultar"
        assert (
            client.post(
                endereco, {"email": "dono@example.org"}, content_type="application/json"
            ).status_code
            == 401
        )
        resposta = client.post(
            endereco,
            {"email": "dono@example.org"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer par-teste",
        )
        assert resposta.status_code == 200
        assert resposta.json() == {"e_administrador": True}


def test_configuracao_de_leitura_nao_carrega_porta_nem_prefixo_local():
    with cliente_leitura():
        config = importlib.import_module("config.settings_leitura")
        assert config.DEBUG is False
        assert config.FORCE_SCRIPT_NAME is None
        assert "apps.core.porta.PortaAdministrativa" not in config.MIDDLEWARE


def test_urlconf_nao_deixa_chegar_a_tela_do_painel():
    # guarda: services/admin/config/settings_leitura.py:9
    with cliente_leitura():
        assert Client().get("/painel/").status_code == 404


def test_postgres_do_processo_recusa_transacoes_de_escrita():
    ambiente = {
        **os.environ,
        "DATABASE_URL": "postgresql://leitura:teste@localhost/admin_db",
    }
    resultado = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings_leitura import DATABASES; print(DATABASES['default']['OPTIONS']['options'])",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert resultado.stdout.strip() == "-c default_transaction_read_only=on"
