"""O acesso local continua fechado sem token; o comando usa o lançador medido."""

import os
from pathlib import Path
import subprocess
import sys

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
