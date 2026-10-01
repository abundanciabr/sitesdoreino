import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi = get_asgi_application()


async def application(scope, receive, send):
    """O Django, e o `lifespan` que liga o executor dos robôs.

    Na célula sozinha, o uvicorn manda `lifespan.startup` ao subir: é a hora
    de ligar a thread que pega as execuções dos robôs (`apps/agentes/
    executor.py`). Na aplicação unificada este arquivo não é usado; lá quem
    liga é `services/aplicacao/workers.py`."""
    if scope["type"] == "lifespan":
        while True:
            mensagem = await receive()
            if mensagem["type"] == "lifespan.startup":
                from apps.agentes.executor import ligar_em_segundo_plano

                ligar_em_segundo_plano()
                await send({"type": "lifespan.startup.complete"})
            elif mensagem["type"] == "lifespan.shutdown":
                from apps.agentes.executor import desligar

                desligar()
                await send({"type": "lifespan.shutdown.complete"})
                return
    await django_asgi(scope, receive, send)
