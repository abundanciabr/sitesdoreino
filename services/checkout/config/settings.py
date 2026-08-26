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
    # [RECEITA:R8 v1] dá o entrypoint `python manage.py run_huey` (django.setup
    # + autodiscover de tasks.py — sem isso o worker sobe com registro vazio e
    # não executa nada, ARMADILHAS §4.11). É o comando que o compose usará.
    "huey.contrib.djhuey",
    "apps.core",
    "apps.pedidos",
]

# O run_huey do djhuey consome a MESMA instância onde as tasks se registram
# (config/huey.py — leitura de HUEY_REDIS_URL nunca fail-hard no import).
from config.huey import huey as HUEY  # noqa: E402

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

# O fuso em que o checkout MOSTRA hora — o armazenamento continua em UTC
# (USE_TZ). Sem esta linha vale o default de fábrica do Django,
# `America/Chicago`: cinco horas atrás, capaz de trocar até o DIA perto da
# virada, sem nada acusando a troca. Aqui o estrago tem nome próprio: prazo de
# Pix e horário de pedido são hora que o CLIENTE lê para decidir se ainda dá
# tempo de pagar. Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Guarda: tests/test_fuso_horario.py (armadilhas/099).
TIME_ZONE = "America/Sao_Paulo"
