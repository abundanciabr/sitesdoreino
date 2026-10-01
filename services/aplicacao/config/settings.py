"""One Django registry with the existing databases kept separate."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .registry import SERVICES, app_configs

BASE_DIR = Path(__file__).resolve().parent.parent
MODULES_ROOT = BASE_DIR / "modules"
ENV_DIR = Path(os.environ.get("APLICACAO_ENV_DIR", BASE_DIR / "env"))


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ImproperlyConfigured(f"ambiente do módulo ausente: {path}")
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if value[:1] in ('"', "'") and value[-1:] == value[:1]:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


SERVICE_ENV = {service: _read_env(ENV_DIR / f"{service}.env") for service in SERVICES}


def _value(service: str, key: str) -> str:
    value = SERVICE_ENV[service].get(key) or os.environ.get(f"{service.upper()}_{key}")
    if not value:
        raise ImproperlyConfigured(f"{key} ausente no ambiente de {service}")
    return value


# The identity key must remain the signer of the existing site-wide session.
SECRET_KEY = _value("identidade", "DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "America/Sao_Paulo"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DATABASES = {}
for service in SERVICES:
    if service != "funil":
        DATABASES[service] = dj_database_url.parse(_value(service, "DATABASE_URL"))
# Django needs a default alias even though every platform model is routed.
DATABASES["default"] = dict(DATABASES["identidade"])
DATABASE_ROUTERS = ["config.registry.ServiceDatabaseRouter"]

INSTALLED_APPS = [
    "config.apps.ApplicationConfig",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
    "huey.contrib.djhuey",
    "site_errors",
    *app_configs(MODULES_ROOT),
]

# An ASGIHandler is constructed for each cell after setup. Its middleware list
# comes from that cell's original settings through the contextual settings proxy.
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": False,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "config.runtime.context_processors",
    ], "loaders": ["config.template_loader.ServiceLoader"]},
}]
