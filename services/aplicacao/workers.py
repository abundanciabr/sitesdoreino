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


def registrar_nomes_legados(huey, servico: str) -> int:
    """Read queued jobs created by the previous per-service Python package.

    Huey serializes the task class' module path. The bundle prefixes that
    path with ``modules.<service>.``; the existing Redis queue still contains
    the original ``apps.*`` identifiers until it drains.
    """
    prefixo = f"modules.{servico}."
    registro = huey._registry._registry
    adicionados = 0
    for nome, classe in tuple(registro.items()):
        if nome.startswith(prefixo):
            antigo = nome[len(prefixo):]
            if antigo not in registro:
                registro[antigo] = classe
                adicionados += 1
    return adicionados


class HueyIncorporado(Consumer):
    """Huey usa threads próprias; sinais pertencem ao servidor ASGI principal."""

    def __init__(self, huey, *, servico: str, **kwargs):
        self.servico = servico
        super().__init__(huey, **kwargs)

    def _set_signal_handlers(self) -> None:
        pass

    def _create_process(self, process, name):
        # Huey cria outras threads depois da nossa. ContextVar não atravessa
        # Thread automaticamente; cada passo do worker/scheduler recebe o
        # contexto do serviço dono da fila.
        from config.runtime import serving

        for nome in ("initialize", "loop", "shutdown"):
            original = getattr(process, nome)

            def contextual(*args, _original=original, **kwargs):
                with serving(self.servico):
                    return _original(*args, **kwargs)

            setattr(process, nome, contextual)
        return super()._create_process(process, name)


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
        self._thread("pagamentos-appmax", self._processar_appmax)
        self._thread("robos-admin", self._robos_admin)
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
        from config.runtime import serving

        servico = nome.split("-", 1)[-1] if nome != "pagamentos-appmax" else "pagamentos"
        while not self.parar.is_set():
            try:
                with serving(servico):
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
        registrar_nomes_legados(huey, servico)
        consumer = HueyIncorporado(huey, servico=servico, workers=1,
                                   worker_type="thread")
        self._huey_ativos[servico] = consumer
        try:
            consumer.run()
        finally:
            self._huey_ativos.pop(servico, None)

    def _processar_appmax(self) -> None:
        modulo = import_module(
            "modules.pagamentos.pagamentos.api.management.commands.processar_appmax"
        )
        while not self.parar.is_set():
            modulo.Command().handle()
            self.parar.wait(30)

    def _robos_admin(self) -> None:
        # O executor dos robôs pessoais da equipe (apps/agentes do admin):
        # pega da fila no banco as conversas e os trabalhos delegados.
        modulo = import_module("modules.admin.apps.agentes.executor")
        modulo.rodar_para_sempre(self.parar)

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
