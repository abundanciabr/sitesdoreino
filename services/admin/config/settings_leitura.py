"""Processo de leitura da VPS; o painel administrativo roda no localhost."""

from copy import deepcopy

from .settings import *  # noqa: F403

DEBUG = False
FORCE_SCRIPT_NAME = None
ROOT_URLCONF = "config.urls_leitura"
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
DATABASES = deepcopy(DATABASES)  # noqa: F405
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {})[
        "options"
    ] = "-c default_transaction_read_only=on"
