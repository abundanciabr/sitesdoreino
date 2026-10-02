"""A mídia do admin unificado fica no volume montado, fora de /app:ro."""

import os
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from config import runtime


SETTINGS_ADMIN = Path(__file__).resolve().parents[2] / "admin" / "config" / "settings.py"
COMPOSE = Path(__file__).resolve().parents[3] / "infra" / "docker-compose.yml"
VOLUME = "/opt/plataforma/admin-midia"


def _configurar(**ambiente):
    with patch.dict(os.environ, {
        "DJANGO_SECRET_KEY": "synthetic-admin",
        "DATABASE_URL": "sqlite:///:memory:",
        **ambiente,
    }, clear=True):
        return runpy.run_path(str(SETTINGS_ADMIN))


def test_admin_unificado_usa_volume_montado_quando_env_omite_raiz():
    configuracao = _configurar(APLICACAO_ENV_DIR="/run/plataforma-env")
    assert configuracao["MEDIA_ROOT"] == VOLUME
    compose = COMPOSE.read_text(encoding="utf-8")
    aplicacao = compose.split("  aplicacao:\n", 1)[1].split("\n  traefik:\n", 1)[0]
    assert "${APLICACAO_CODIGO:?defina APLICACAO_CODIGO}:/app:ro" in aplicacao
    assert f"{VOLUME}:{VOLUME}" in aplicacao

    anterior = runtime._service_settings.get("admin")
    runtime._service_settings["admin"] = {"MEDIA_ROOT": configuracao["MEDIA_ROOT"]}
    try:
        with runtime.serving("admin"):
            contextual = runtime.ContextualSettings(SimpleNamespace(MEDIA_ROOT="/app/midia"))
            assert contextual.MEDIA_ROOT == VOLUME
    finally:
        if anterior is None:
            del runtime._service_settings["admin"]
        else:
            runtime._service_settings["admin"] = anterior


def test_raiz_explicita_permanece_gravavel(tmp_path):
    raiz = tmp_path / "midia"
    configuracao = _configurar(
        APLICACAO_ENV_DIR="/run/plataforma-env", ADMIN_MIDIA_RAIZ=str(raiz)
    )
    assert Path(configuracao["MEDIA_ROOT"]) == raiz
    raiz.mkdir()
    (raiz / "existente.png").write_bytes(b"imagem antiga")
    (raiz / "prova.png").write_bytes(b"png de teste")
    assert (raiz / "existente.png").read_bytes() == b"imagem antiga"
    assert (raiz / "prova.png").read_bytes() == b"png de teste"


def test_celula_isolada_conserva_fallback_local():
    configuracao = _configurar()
    assert configuracao["MEDIA_ROOT"] == str(SETTINGS_ADMIN.parents[1] / "midia")
