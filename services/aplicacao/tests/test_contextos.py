from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from types import SimpleNamespace

from django.core.signals import request_finished, request_started
import django.db
from huey.consumer import Consumer

from config import runtime
from workers import HueyIncorporado


def test_env_isolado_em_requisicoes_concorrentes(monkeypatch):
    monkeypatch.setitem(runtime._service_environments, "forum", {"TOKEN": "forum"})
    monkeypatch.setitem(runtime._service_environments, "admin", {"TOKEN": "admin"})
    env = runtime.ContextualEnvironment({"GLOBAL": "base"})

    def ler(servico):
        with runtime.serving(servico):
            return env["TOKEN"], env.copy()["TOKEN"], env["GLOBAL"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(ler, ("forum", "admin")))
    assert resultados == [("forum", "forum", "base"),
                          ("admin", "admin", "base")]


def test_thread_interna_do_huey_recebe_contexto(monkeypatch):
    observado = []

    class Processo:
        def initialize(self):
            observado.append(("initialize", runtime.current_service()))

        def loop(self):
            observado.append(("loop", runtime.current_service()))

        def shutdown(self):
            observado.append(("shutdown", runtime.current_service()))

    def executar(_self, processo, _name):
        thread = Thread(target=lambda: (processo.initialize(), processo.loop(),
                                        processo.shutdown()))
        thread.start()
        thread.join()

    monkeypatch.setattr(Consumer, "_create_process", executar)
    consumer = HueyIncorporado.__new__(HueyIncorporado)
    consumer.servico = "forum"
    consumer._create_process(Processo(), "Worker-1")
    assert observado == [("initialize", "forum"), ("loop", "forum"),
                         ("shutdown", "forum")]


def test_limpeza_da_requisicao_interna_preserva_transacao_externa(monkeypatch):
    class Connection:
        def __init__(self, alias):
            self.alias = alias
            self.queries_log = []
            self.cleanup_calls = 0
            self.closed_in_transaction = False

        def close_if_unusable_or_obsolete(self):
            self.cleanup_calls += 1
            if self.alias == "admin":
                self.closed_in_transaction = True

    class Connections:
        settings = {"admin": {}, "catalogo": {}}

        def __init__(self, admin, catalogo):
            self._connections = SimpleNamespace(admin=admin, catalogo=catalogo)

        def __getitem__(self, alias):
            return getattr(self._connections, alias)

        def all(self, initialized_only=False):
            return [self._connections.admin, self._connections.catalogo]

    admin, catalogo = Connection("admin"), Connection("catalogo")
    monkeypatch.setattr(django.db, "connections", Connections(admin, catalogo))
    runtime.install_default_database_alias()

    with runtime.serving("admin"):
        with runtime.serving("catalogo"):
            request_started.send(sender=object())
            request_finished.send(sender=object())
        assert not admin.closed_in_transaction
        assert admin.cleanup_calls == 0
        assert catalogo.cleanup_calls == 2

    request_finished.send(sender=object())
    assert admin.cleanup_calls == 1
