# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

ALLOWED_HOSTS = ["*"]  # rede Docker interna; célula não tem rota pública direta

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {
    v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v
}

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que datas seriam MOSTRADAS — o armazenamento continua em UTC
# (USE_TZ). Sem esta linha vale o default de fábrica do Django,
# `America/Chicago`: cinco horas atrás, e sem nada na tela indicando a troca.
# É falha silenciosa até a primeira página renderizar uma data — foi assim que
# a `sugestoes` foi pega em 24/08/2026 (EVO-21; dívida em
# ARMADILHAS-OPERACAO.md §9). Guarda: tests/test_fuso_horario.py.
TIME_ZONE = "America/Sao_Paulo"
