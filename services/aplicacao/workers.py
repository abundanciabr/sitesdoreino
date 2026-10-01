"""Consumidores de eventos e Huey dentro do processo único da aplicação.

Chame ``iniciar()`` depois de ``django.setup()``. Cada consumidor mantém seu
próprio grupo Redis e suas funções existentes de ACK, reentrega e fila morta.
Uma falha reinicia somente aquela thread, como fazia o supervisor do container.
"""

from __future__ import annotations

from importlib import import_module, util
import logging
from threading import Event, Thread

from huey.consumer import Consumer


log = logging.getLogger(__name__)

# App que abriga o comando em cada serviço. Um comando Django homônimo não
# pode ser resolvido por call_command quando todos os apps estão registrados.
CONSUMIDORES = {
    "alunos": "eventos",
    "checkout": "pedidos",
    "gamificacao": "eventos",
    "leads": "core",
    "mensageria": "eventos",
    "metricas": "fatos",
    "notificacoes": "eventos",
}

HUEYS = (
    "alunos",
    "checkout",
    "cursos",
    "encomendas",
    "forum",
    "gamificacao",
    "identidade",
    "mensageria",
    "pages",
    "quiz",
    "sugestoes",
)


class HueyIncorporado(Consumer):
    """Huey usa threads próprias; sinais pertencem ao servidor ASGI principal."""

    def _set_signal_handlers(self) -> None:
        pass


class Workers:
    def __init__(self, *, consumidores=CONSUMIDORES, hueys=HUEYS):
        self.consumidores = dict(consumidores)
        self.hueys = tuple(hueys)
        self.parar = Event()
        self.threads: list[Thread] = []
        self._huey_ativos: dict[str, HueyIncorporado] = {}

    def iniciar(self) -> "Workers":
        if self.threads:
            return self
        for servico, app in self.consumidores.items():
            self._thread(f"eventos-{servico}", self._consumir, servico, app)
        for servico in self.hueys:
            self._thread(f"huey-{servico}", self._huey, servico)
        return self

    def _thread(self, nome: str, funcao, *args) -> None:
        thread = Thread(
            target=self._supervisionar,
            args=(nome, funcao, args),
            name=nome,
            daemon=True,
        )
        thread.start()
        self.threads.append(thread)

    def _supervisionar(self, nome: str, funcao, args: tuple) -> None:
        while not self.parar.is_set():
            try:
                funcao(*args)
            except Exception:
                log.exception("Worker %s falhou; reiniciando", nome)
            else:
                if not self.parar.is_set():
                    log.error("Worker %s terminou inesperadamente; reiniciando", nome)
            self.parar.wait(5)

    @staticmethod
    def _consumir(servico: str, app: str) -> None:
        modulo = import_module(
            f"modules.{servico}.apps.{app}.management.commands.consume_eventos"
        )
        modulo.Command().handle()

    def _huey(self, servico: str) -> None:
        from django.apps import apps

        # djhuey fazia autodiscover dos tasks.py ao subir cada célula. No
        # processo único registramos cada task na instância Huey de sua célula.
        for config in apps.get_app_configs():
            if not config.name.startswith(f"modules.{servico}.apps."):
                continue
            nome = f"{config.name}.tasks"
            if util.find_spec(nome) is not None:
                import_module(nome)

        huey = import_module(f"modules.{servico}.config.huey").huey
        consumer = HueyIncorporado(huey, workers=1, worker_type="thread")
        self._huey_ativos[servico] = consumer
        try:
            consumer.run()
        finally:
            self._huey_ativos.pop(servico, None)

    def encerrar(self) -> None:
        self.parar.set()
        for consumer in tuple(self._huey_ativos.values()):
            consumer.stop()
        # O xreadgroup das células bloqueia por até 5s. Threads daemon permitem
        # ao ASGI encerrar sem esperar comandos legados com laço infinito.
        for thread in self.threads:
            thread.join(timeout=1)


def iniciar() -> Workers:
    """Entrada pequena para o lifespan ASGI do servidor unificado."""
    return Workers().iniciar()
