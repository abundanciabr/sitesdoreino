"""Keep each former cell's settings local to its request in one process."""

import contextvars
import importlib
import os
from collections.abc import MutableMapping
from contextlib import contextmanager

from django.conf import settings
from django.conf import LazySettings
from django.utils.module_loading import import_string

from .registry import SERVICES

_current_service = contextvars.ContextVar("site_service", default=None)
_service_settings = {}
_service_environments = {}
_original_environment = os.environ

TOPOLOGY = {
    "identidade": 12, "forum": 1, "gamificacao": 1, "cursos": 9,
    "pages": 10, "encomendas": 11, "catalogo": 1, "quiz": 2,
    "leads": 3, "checkout": 4, "pagamentos": 5, "alunos": 6,
    "mensageria": 7, "sugestoes": 8,
}


@contextmanager
def serving(service):
    token = _current_service.set(service)
    try:
        yield
    finally:
        _current_service.reset(token)


def current_service():
    return _current_service.get()


def _source_environment(service):
    values = dict(settings.SERVICE_ENV[service])
    values.setdefault("REDIS_STREAMS_URL", "redis://redis:6379/0")
    if service in TOPOLOGY:
        values.setdefault("HUEY_REDIS_URL", f"redis://redis:6379/{TOPOLOGY[service]}")
    values.setdefault("SCRIPT_NAME", "")
    return values


def load_original_settings():
    """Import the copied configuration once, with its own existing env file."""
    original_environment = dict(os.environ)
    try:
        for service in SERVICES:
            values = _source_environment(service)
            _service_environments[service] = values
            os.environ.update(values)
            source = importlib.import_module(f"modules.{service}.config.settings")
            _service_settings[service] = {
                key: value for key, value in vars(source).items() if key.isupper()
            }
            os.environ.clear()
            os.environ.update(original_environment)
    finally:
        os.environ.clear()
        os.environ.update(original_environment)


_CENTRAL = frozenset({
    "DATABASES", "DATABASE_ROUTERS", "INSTALLED_APPS", "TEMPLATES",
    "SERVICE_ENV", "MODULES_ROOT", "ENV_DIR", "STATIC_ROOT",
})


class ContextualSettings:
    def __init__(self, base):
        object.__setattr__(self, "_base", base)

    def __getattr__(self, key):
        service = current_service()
        if service and key not in _CENTRAL:
            values = _service_settings.get(service, {})
            if key in values:
                return values[key]
        return getattr(self._base, key)

    def __setattr__(self, key, value):
        setattr(self._base, key, value)

    def __delattr__(self, key):
        delattr(self._base, key)


_lazy_getattribute = LazySettings.__getattribute__


def _contextual_getattribute(self, key):
    # LazySettings normally caches uppercase values on first access. Bypass
    # that cache only for the singleton serving the unified application.
    if self is settings and key.isupper():
        return getattr(object.__getattribute__(self, "_wrapped"), key)
    return _lazy_getattribute(self, key)


def install_contextual_settings():
    if not isinstance(settings._wrapped, ContextualSettings):
        settings._wrapped = ContextualSettings(settings._wrapped)
    if LazySettings.__getattribute__ is not _contextual_getattribute:
        LazySettings.__getattribute__ = _contextual_getattribute
    if not isinstance(os.environ, ContextualEnvironment):
        os.environ = ContextualEnvironment(_original_environment)
    install_default_database_alias()
    install_ninja_namespaces()


def install_ninja_namespaces():
    from ninja import NinjaAPI

    if getattr(NinjaAPI.__init__, "_site_contextual", False):
        return
    original = NinjaAPI.__init__

    def init(self, *args, **kwargs):
        service = current_service()
        if service and kwargs.get("urls_namespace") is None:
            kwargs["urls_namespace"] = f"api-{service}"
        original(self, *args, **kwargs)

    init._site_contextual = True
    NinjaAPI.__init__ = init


def install_default_database_alias():
    """Make transaction.atomic(), on_commit() and django.db.connection local."""
    from django.db.utils import ConnectionHandler

    if getattr(ConnectionHandler.__getitem__, "_site_contextual", False):
        return
    original = ConnectionHandler.__getitem__

    def getitem(self, alias):
        if alias == "default" and (service := current_service()):
            alias = service
        return original(self, alias)

    getitem._site_contextual = True
    ConnectionHandler.__getitem__ = getitem


class ContextualEnvironment(MutableMapping):
    """Expose each mounted env file to reads made during that cell's request."""

    def __init__(self, base):
        self.base = base

    def __getitem__(self, key):
        service = current_service()
        if service and key in _service_environments[service]:
            return _service_environments[service][key]
        return self.base[key]

    def __setitem__(self, key, value):
        self.base[key] = value

    def __delitem__(self, key):
        del self.base[key]

    def __iter__(self):
        service = current_service()
        if service:
            return iter(set(self.base) | set(_service_environments[service]))
        return iter(self.base)

    def __len__(self):
        return len(set(iter(self)))


def context_processors(request):
    """Run only processors belonging to the selected former cell."""
    service = current_service()
    if not service:
        return {}
    result = {}
    for backend in _service_settings[service].get("TEMPLATES", []):
        for path in backend.get("OPTIONS", {}).get("context_processors", []):
            if path == "django.template.context_processors.request":
                continue
            result.update(import_string(path)(request))
    return result
