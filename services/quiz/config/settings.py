# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from config.huey import huey as _huey

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
# (cadastro LOCAL — [INV-P11], ver LICOES.md), não esta lista.
ALLOWED_HOSTS = ["*"]

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # [RECEITA:R8 v1] traz `manage.py run_huey` (o worker de produção sobe com
    # esse comando) e o autodiscover de apps/*/tasks.py — sem isso o worker
    # subiria com o TaskRegistry VAZIO (ARMADILHAS §4.11).
    "huey.contrib.djhuey",
    "apps.core",
    "apps.quiz",
]

# [RECEITA:R8 v1] djhuey lê settings.HUEY; sendo a INSTÂNCIA de config/huey.py
# (não um dict), worker e web compartilham exatamente o mesmo registro de
# tasks — `run_huey` executa o que apps/quiz/tasks.py registra.
HUEY = _huey

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # [RECEITA:CONV-SITE v1] logo após os middlewares de segurança do Django.
    "apps.core.middleware.SiteResolutionMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True
