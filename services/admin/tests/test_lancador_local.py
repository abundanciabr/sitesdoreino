"""A guarda mede o caminho que o mantenedor realmente usa."""

from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RAIZ = Path(__file__).resolve().parents[3]
LANCADOR = RAIZ / "administracao-local" / "abrir-a-administracao.cmd"


def _dados(texto: str) -> tuple[str, str, str]:
    script = re.search(r'set "SCRIPT_NAME=([^\"]*)"', texto)
    pasta = re.search(
        r'if not defined ADMIN_PLANOS_DIR set "ADMIN_PLANOS_DIR=([^\"]+)"', texto
    )
    endereco = re.search(r"echo (http://127\.0\.0\.1:8000/[^\r\n]+)", texto)
    assert script, "o launcher não declara SCRIPT_NAME de forma legível"
    assert pasta, "o launcher não declara o padrão de ADMIN_PLANOS_DIR"
    assert endereco, "o launcher não imprime um endereço local"
    return script.group(1), pasta.group(1), endereco.group(1)


def validar_lancador(texto: str) -> None:
    _garantir_rota_local_para_a_prova()
    script_name, pasta_crua, endereco_cru = _dados(texto)
    assert "C:\\Users\\" not in texto, "o launcher crava caminho de usuário"

    endereco = endereco_cru.replace("%ADMIN_LINK_TOKEN%", "token-de-teste")
    caminho = urlsplit(endereco).path
    if script_name and caminho.startswith(script_name):
        caminho = caminho[len(script_name) :]
    from django.urls import get_script_prefix, resolve, set_script_prefix

    prefixo_anterior = get_script_prefix()
    set_script_prefix(script_name or "/")
    try:
        try:
            resultado = resolve(caminho)
        except Exception as erro:  # Resolver404 é a falha que a mutação mede.
            raise AssertionError(f"o endereço não resolve: {caminho}") from erro
        assert resultado.url_name == "acesso_local"
    finally:
        set_script_prefix(prefixo_anterior)
    assert "next=" not in endereco, "o launcher imprime destino secundário"

    pasta = Path(
        pasta_crua.replace("%~dp0", str(RAIZ / "administracao-local") + "\\")
    ).resolve()
    assert pasta.is_dir(), f"a pasta padrão não existe: {pasta}"


def _garantir_rota_local_para_a_prova() -> None:
    """Mantém a prova positiva independente do ambiente do pytest."""
    from django.conf import settings
    from django.urls import path

    from apps.core.views import acesso_local
    import config.urls as urls

    if not any(getattr(padrao, "name", None) == "acesso_local" for padrao in urls.urlpatterns):
        settings.ADMIN_LINK_TOKEN = "token-de-teste"
        urls.urlpatterns.append(
            path("acesso-local/<str:token>/", acesso_local, name="acesso_local")
        )


def test_o_lancador_imprime_endereco_resolvivel_e_pasta_existente():
    validar_lancador(LANCADOR.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mutacao",
    (
        lambda texto: texto.replace(
            "echo http://127.0.0.1:8000/acesso-local/",
            "echo http://127.0.0.1:8000/admin/acesso-local/",
        ),
        lambda texto: texto.replace(
            r"%~dp0..\docs\administracao-local", r"%~dp0..\docs\nao-existe"
        ),
        lambda texto: texto + '\nset "USUARIO=C:\\Users\\alguem"\n',
    ),
)
def test_as_tres_mutacoes_obrigatorias_ficam_vermelhas(mutacao):
    with pytest.raises(AssertionError):
        validar_lancador(mutacao(LANCADOR.read_text(encoding="utf-8")))


def test_sem_token_a_rota_local_nao_e_registrada():
    ambiente = os.environ.copy()
    ambiente.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": "teste-guarda",
            "DATABASE_URL": "sqlite:///teste-local.sqlite3",
            "SCRIPT_NAME": "",
        }
    )
    ambiente.pop("ADMIN_LINK_TOKEN", None)
    script = """
import django
django.setup()
from django.test import Client
from django.urls import NoReverseMatch, reverse
try:
    reverse('acesso_local')
except NoReverseMatch:
    pass
else:
    raise SystemExit('reverse aceitou acesso_local sem token')
assert Client().get('/acesso-local/qualquer-token/').status_code == 404
"""
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=RAIZ / "services" / "admin",
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr or resultado.stdout
