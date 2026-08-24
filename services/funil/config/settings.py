import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str) -> str:  # [RECEITA:CONV v1]
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; a resolução de site (Host) é responsabilidade do middleware
# CONV-SITE, ainda não instanciado neste esqueleto (sem regra de negócio).
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "apps.core",
    # i18n da célula (PLANO-I18N fase 1): o AppConfig.ready() valida o
    # catálogo no BOOT (fail-closed) e o congela em memória.
    "apps.i18n",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # [RECEITA:CONV-SITE v1] logo após os middlewares de segurança do Django.
    "apps.core.middleware.SiteResolutionMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

# funil é a única célula sem banco de dados (stateless) — CONTEXTO da célula.
# Vitrine pura: formulários postam em leads, compra redireciona para checkout.
DATABASES = {}

TEMPLATES = [  # [RECEITA:R6 v1] — landing (ilha Alpine)
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        # `request` no contexto: o base_mobile.html lê request.i18n_seo para a
        # emissão SEO de site registrado (D5). Site não registrado não referencia
        # a variável — saída byte-idêntica à anterior (teste de regressão).
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"]
        },
    },
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
