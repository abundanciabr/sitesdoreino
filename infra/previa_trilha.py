"""Private ASGI entrance for the isolated Trilha candidate process.

Run ``infra.previa_trilha:application`` from a prepared unified bundle. The
regular application's ASGI module is unchanged; this wrapper never exposes its
other service routes. Identity and administrator checks happen again in the
Funil preview view, using the real session and admin service.
"""

from config.asgi import application as _application
from internal import instalar as _instalar_transporte_interno
from infra.previa_trilha_transporte import instalar as _instalar_filtro_privado

_instalar_transporte_interno()
_instalar_filtro_privado()

PREFIX = "/trilha/previa/"


async def _not_found(send):
    body = b"Not found"
    await send({"type": "http.response.start", "status": 404, "headers": [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"cache-control", b"private, no-store"),
        (b"x-robots-tag", b"noindex, nofollow"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]})
    await send({"type": "http.response.body", "body": body})


async def application(scope, receive, send):
    """Reject every route outside the private namespace before Django routes."""
    if scope.get("type") == "lifespan":
        from workers import Workers

        workers = None
        while True:
            mensagem = await receive()
            if mensagem["type"] == "lifespan.startup":
                try:
                    workers = Workers()
                    workers._thread("eventos-gamificacao", workers._consumir, "gamificacao", "eventos")
                    workers._thread("eventos-encomendas", workers._consumir, "encomendas", "core")
                    for servico in ("cursos", "encomendas", "gamificacao"):
                        workers._thread("huey-" + servico, workers._huey, servico)
                except Exception as erro:
                    if workers is not None:
                        workers.encerrar()
                    await send({"type": "lifespan.startup.failed", "message": str(erro)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif mensagem["type"] == "lifespan.shutdown":
                if workers is not None:
                    workers.encerrar()
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope.get("type") == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    if scope.get("type") != "http":
        return await _not_found(send)
    path = scope.get("path", "")
    host = next((value.decode("latin1").split(":", 1)[0].lower()
                 for key, value in scope.get("headers", []) if key.lower() == b"host"), "")
    if not (path.startswith(PREFIX) and host == "meshcraft.top"):
        return await _not_found(send)
    return await _application(scope, receive, send)
