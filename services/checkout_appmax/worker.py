"""Confirm sandbox payments in the clone's exclusive databases and Redis."""
from importlib import import_module
from threading import Event, Thread
from urllib.parse import urlparse
import json
import logging
import signal

import server
from config import settings as application_settings
from config.runtime import serving
from django.db import connections

# Existing handlers can log provider exceptions. The clone emits only error
# classes here so no customer or payment payload reaches this process's log.
logging.disable(logging.CRITICAL)
stop = Event()


def run_loop(name, service, function, interval):
    while not stop.is_set():
        try:
            with serving(service):
                function()
        except Exception as error:
            print(json.dumps({'worker': name, 'erro_tipo': type(error).__name__}), flush=True)
        finally:
            connections.close_all()
        stop.wait(interval)


def main():
    if server.environment != 'sandbox':
        raise RuntimeError('This worker belongs to the sandbox copy')
    for service in ('checkout', 'pagamentos'):
        url = urlparse(application_settings.SERVICE_ENV[service]['DATABASE_URL'])
        if url.hostname != 'postgres' or url.username != 'appmax_clone':
            raise RuntimeError('Exclusive sandbox database is absent')
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    consumer = import_module('modules.checkout.apps.pedidos.management.commands.consume_eventos')
    supervisor = import_module('modules.pagamentos.pagamentos.supervisao')
    relay = import_module('modules.checkout.apps.pedidos.tasks')
    threads = []
    for name, service, function, interval in (
        ('eventos-checkout', 'checkout', lambda: consumer.Command().handle(), 5),
        ('pagamentos-appmax', 'pagamentos', lambda: supervisor.processar_rodada(limite=25), 30),
        ('relay-checkout', 'checkout', relay.relay_outbox, 10),
    ):
        thread = Thread(target=run_loop, args=(name, service, function, interval), name=name, daemon=True)
        thread.start()
        threads.append(thread)
    print(json.dumps({'worker_sandbox': 'iniciado', 'consumidores': ['checkout'],
                      'supervisao': 'appmax', 'mensageria': False, 'robos_admin': False}), flush=True)
    while not stop.wait(1):
        pass
    for thread in threads:
        thread.join(timeout=1)


if __name__ == '__main__':
    main()
