"""Dispatch public and internal traffic to 18 handlers of one Django app."""

import os
from importlib import import_module

from django.core.handlers.asgi import ASGIHandler
from django.core.asgi import get_asgi_application
from django.urls import get_script_prefix, get_urlconf, set_script_prefix, set_urlconf

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Configure the single model registry before constructing per-cell handlers.
_base_application = get_asgi_application()

from .registry import ACTIVE_SERVICES as SERVICES, service_for_path  # noqa: E402
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
        # Pages has an ASGI wrapper for legacy /pages and /estudio redirects.
        # Constructing a bare Django handler would silently bypass it.
        _handlers[_service] = (
            import_module("modules.pages.config.asgi").application
            if _service == "pages" else ASGIHandler()
        )


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
    # Nomes Docker internos mantêm o contrato usado pelo transporte HTTP.
    # O gateway público só encaminha os hosts públicos configurados.
    service = scope.get("site_servico")
    if service is None and host.split(":", 1)[0] in SERVICES:
        service = host.split(":", 1)[0]
    if service not in _handlers:
        service, script_name = service_for_path(path, host, private)
    else:
        script_name = ""
    if len(SERVICES) == 1:
        service = SERVICES[0]
    routed_scope = dict(scope)
    routed_scope["root_path"] = script_name
    # Django leaves both values in asgiref.local.Local after a response. An
    # in-process HTTP call can nest inside another module's rendering; restore
    # the outer request's URL state before its templates reverse links.
    old_prefix, old_urlconf = get_script_prefix(), get_urlconf()
    try:
        with serving(service):
            await _handlers[service](routed_scope, receive, send)
    finally:
        set_script_prefix(old_prefix)
        set_urlconf(old_urlconf)


def app_do_servico(service):
    """ASGI view of an internal cell, used by in-process HTTP clients."""
    if service not in _handlers:
        raise ValueError(f"serviço desconhecido: {service}")

    async def app(scope, receive, send):
        routed_scope = dict(scope)
        routed_scope["site_servico"] = service
        await application(routed_scope, receive, send)

    return app
