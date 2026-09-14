"""O acesso local continua fechado sem token; o comando usa o lançador medido."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci import ligar_administracao

RAIZ = Path(__file__).resolve().parents[3]


def test_cmd_chama_lancador_que_verifica_http():
    comando = (RAIZ / "administracao-local/abrir-a-administracao.cmd").read_text(
        encoding="utf-8"
    )
    assert 'cd /d "%~dp0.."' in comando
    assert "python ci\\ligar_administracao.py" in comando
    assert "exit /b %errorlevel%" in comando
    assert (RAIZ / "ci/ligar_administracao.py").is_file()


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


def test_lancador_explica_quando_a_porta_e_de_outra_bancada(monkeypatch, tmp_path):
    docs = tmp_path / "sitesdoreino-docs" / "administracao-local"
    docs.mkdir(parents=True)
    (docs / "00-SINTESE-desenho-final.md").write_text("# Síntese\n", encoding="utf-8")
    dados = tmp_path / "SitesDoReino" / "administracao-local"
    dados.mkdir(parents=True)
    (dados / "servidor.json").write_text(
        json.dumps({"raiz": str(tmp_path / "outra-bancada"), "token": "antigo"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ligar_administracao, "RAIZ", tmp_path / "bancada-atual")
    monkeypatch.setattr(ligar_administracao, "porta_ocupada", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(ligar_administracao.FalhaLocal, match="outra bancada"):
        ligar_administracao.iniciar()
