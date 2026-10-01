"""Dispatch public and internal traffic to 18 handlers of one Django app."""

import os

from django.core.handlers.asgi import ASGIHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Configure the single model registry before constructing per-cell handlers.
_base_application = get_asgi_application()

from .registry import SERVICES, service_for_path  # noqa: E402
from .runtime import (  # noqa: E402
    install_contextual_settings,
    install_default_database_alias,
    install_ninja_namespaces,
    load_original_settings,
    serving,
)

load_original_settings()
install_contextual_settings()
install_default_database_alias()
install_ninja_namespaces()

_handlers = {}
for _service in SERVICES:
    with serving(_service):
        _handlers[_service] = ASGIHandler()


async def application(scope, receive, send):
    if scope["type"] != "http":
        await _base_application(scope, receive, send)
        return
    path = scope.get("path", "/")
    host = next(
        (value.decode("latin1") for key, value in scope.get("headers", []) if key.lower() == b"host"),
        "",
    )
    private = any(
        key.lower() == b"x-plataforma-entrada" and value.lower() == b"privada"
        for key, value in scope.get("headers", [])
    )
    service = scope.get("site_servico")
    if service not in _handlers:
        service, script_name = service_for_path(path, host, private)
    else:
        script_name = ""
    routed_scope = dict(scope)
    routed_scope["root_path"] = script_name
    with serving(service):
        await _handlers[service](routed_scope, receive, send)


def app_do_servico(service):
    """ASGI view of an internal cell, used by in-process HTTP clients."""
    if service not in _handlers:
        raise ValueError(f"serviço desconhecido: {service}")

    async def app(scope, receive, send):
        routed_scope = dict(scope)
        routed_scope["site_servico"] = service
        await application(routed_scope, receive, send)

    return app
