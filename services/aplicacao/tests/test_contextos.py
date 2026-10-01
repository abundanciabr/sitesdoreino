from concurrent.futures import ThreadPoolExecutor
from threading import Thread

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
