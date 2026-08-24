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


# Só estas duas são fail-hard no import, e de propósito: são as únicas que o
# .github/workflows/ci-celula.yml já fornece a TODA célula (armadilha §5.3 —
# variável nova e fail-hard aqui exigiria editar o workflow, que está fora do
# escopo desta célula). Toda variável futura desta célula
# (SUGESTOES_STAFF_EMAILS, ALUNOS_API_URL…) é lida NO PONTO DE USO, com default
# inofensivo — convenção do lote de Huey.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A Caixa serve sob prefixo: meshcraft.top/forms/sugestoes/ (DECISAO-EVO-01 §2).
# O Traefik NÃO remove o prefixo — quem o conhece é esta variável, nunca o
# urls.py. Ver armadilhas/029 e tests/test_healthz_script_name.py.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; a resolução de site (Host) é responsabilidade do middleware
# CONV-SITE, ainda não instanciado neste esqueleto (sem regra de negócio).
ALLOWED_HOSTS = ["*"]

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
