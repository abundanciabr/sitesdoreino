"""The unchanged approved engine, using only the production copy's databases."""
import json
import logging
import os
import threading
from importlib import import_module
from pathlib import Path
from urllib.parse import urlparse

os.environ["APPMAX_PRODUCTION_CHILD"] = "1"
logging.disable(logging.CRITICAL)
import server
from config import settings as application_settings
from config.runtime import serving
from django.db import connections

if server.environment != "production":
    raise RuntimeError("Production copy requires production endpoints")
for name in ("checkout", "pagamentos"):
    url = urlparse(application_settings.SERVICE_ENV[name]["DATABASE_URL"])
    if url.hostname != "postgres" or url.username != "appmax_clone" or not url.path.endswith("_producao"):
        raise RuntimeError("Production copy database is not isolated")

state = json.loads(Path("/appmax-producao/instalacao.json").read_text())
with serving("pagamentos"):
    from modules.pagamentos.pagamentos.core.models import InstalacaoAppmax
    InstalacaoAppmax.objects.update_or_create(app_id=state["app_id"], defaults={
        "external_id": state["external_id"], "alias": "Meshcraft",
        "platform_site_ids": ["cc06b8c3-043b-4c06-92c5-5ea624e00586"], "client_secret_recebido": True})


def loop(service, function, interval):
    while True:
        try:
            with serving(service):
                function()
        except Exception as error:
            print(json.dumps({"servico": service, "erro_tipo": type(error).__name__}), flush=True)
        finally:
            connections.close_all()
        threading.Event().wait(interval)


consumer = import_module("modules.checkout.apps.pedidos.management.commands.consume_eventos")
supervisor = import_module("modules.pagamentos.pagamentos.supervisao")
relay = import_module("modules.checkout.apps.pedidos.tasks")
for name, service, function, interval in (
    ("eventos-checkout-producao", "checkout", lambda: consumer.Command().handle(), 5),
    ("confirmacoes-appmax-producao", "pagamentos", lambda: supervisor.processar_rodada(limite=25), 30),
    ("relay-checkout-producao", "checkout", relay.relay_outbox, 10),
):
    threading.Thread(target=loop, args=(service, function, interval), name=name, daemon=True).start()


async def application(scope, receive, send):
    if scope.get("type") == "http" and scope.get("path") == "/estado":
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"producao_isolada":true}'})
        return
    if scope.get("type") == "http" and scope.get("path") == "/api/pagamentos/appmax/webhooks":
        forwarded = dict(scope)
        forwarded["site_servico"] = "pagamentos"
        return await server.approved_application(forwarded, receive, send)
    return await server.application(scope, receive, send)
