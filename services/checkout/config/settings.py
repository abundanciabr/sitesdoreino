# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
# golpe-1-red-team: alteração trivial e reversível (02-RED-TEAM.md #1)
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

# Atrás do Traefik. Quem decide se um Host é legítimo é o middleware CONV-SITE
# (consulta o catálogo; desconhecido ⇒ 404 — [INV-P11]), não esta lista.
ALLOWED_HOSTS = ["*"]

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {
    v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v
}

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.pedidos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # [RECEITA:CONV-SITE v1] logo após os middlewares de segurança do Django.
    "apps.core.middleware.SiteResolutionMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [  # [RECEITA:R6 v1] — páginas dados/pix/cartão (ilhas Alpine)
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

USE_TZ = True
