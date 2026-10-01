import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_application = get_asgi_application()


async def application(scope, receive, send):
    """Redireciona links antigos antes de o Django aplicar o prefixo atual."""
    from apps.core.enderecos import destino_antigo

    destino = destino_antigo(scope.get("path", "")) if scope["type"] == "http" else None
    if destino is not None:
        consulta = scope.get("query_string", b"")
        local = destino.encode("utf-8") + (b"?" + consulta if consulta else b"")
        await send(
            {
                "type": "http.response.start",
                "status": 308,
                "headers": [(b"location", local), (b"cache-control", b"no-store")],
            }
        )
        await send({"type": "http.response.body", "body": b""})
        return
    await django_application(scope, receive, send)
