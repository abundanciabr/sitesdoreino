import types

import workers


def test_consumidor_marketplace_roda_na_celula_encomendas(monkeypatch):
    chamados = []
    class Command:
        def handle(self):
            chamados.append("executado")
    def importar(nome):
        assert nome == "modules.encomendas.apps.core.management.commands.consume_marketplace"
        return types.SimpleNamespace(Command=Command)
    monkeypatch.setattr(workers, "import_module", importar)
    assert workers.CONSUMIDORES["encomendas"] == "core"
    workers.Workers._consumir("encomendas", "core")
    assert chamados == ["executado"]


def test_huey_decodifica_mensagem_enfileirada_antes_do_bundle():
    from huey.registry import Message, Registry

    class Tarefa:
        def __init__(self, args, kwargs, *resto):
            self.args, self.kwargs = args, kwargs

    Tarefa.__module__ = "modules.alunos.apps.matriculas.tasks"
    registro = Registry()
    registro.register(Tarefa)
    huey = types.SimpleNamespace(_registry=registro)
    assert workers.registrar_nomes_legados(huey, "alunos") == 1
    mensagem = Message(id="legado", name="apps.matriculas.tasks.Tarefa",
                       args=(17,), kwargs={"status": "pendente"})
    tarefa = registro.create_task(mensagem)
    assert isinstance(tarefa, Tarefa)
    assert tarefa.args == (17,)
    assert tarefa.kwargs == {"status": "pendente"}


def test_comando_consumidor_e_escolhido_por_modulo(monkeypatch):
    chamados = []

    class Command:
        def handle(self):
            chamados.append("checkout")

    original = workers.import_module

    def importar(nome):
        if nome == "modules.checkout.apps.pedidos.management.commands.consume_eventos":
            return types.SimpleNamespace(Command=Command)
        return original(nome)

    monkeypatch.setattr(workers, "import_module", importar)
    workers.Workers._consumir("checkout", "pedidos")
    assert chamados == ["checkout"]


def test_huey_descobre_tasks_do_servico_e_preserva_sua_instancia(monkeypatch):
    import django.apps

    configs = [
        types.SimpleNamespace(name="modules.alunos.apps.matriculas"),
        types.SimpleNamespace(name="modules.checkout.apps.pedidos"),
    ]
    monkeypatch.setattr(django.apps.apps, "get_app_configs", lambda: configs)
    monkeypatch.setattr(
        workers.util, "find_spec", lambda nome: nome.endswith("matriculas.tasks")
    )
    importados = []
    tarefa = object()
    registro = {"modules.alunos.apps.matriculas.tasks.Tarefa": tarefa}
    huey = types.SimpleNamespace(_registry=types.SimpleNamespace(_registry=registro))
    monkeypatch.setattr(
        workers,
        "import_module",
        lambda nome: importados.append(nome) or types.SimpleNamespace(huey=huey),
    )
    recebidos = []

    class Consumer:
        def __init__(self, instancia, **kwargs):
            recebidos.append((instancia, kwargs))

        def run(self):
            pass

    monkeypatch.setattr(workers, "HueyIncorporado", Consumer)
    grupo = workers.Workers(consumidores={}, hueys=("alunos",))
    grupo._huey("alunos")
    assert importados == [
        "modules.alunos.apps.matriculas.tasks",
        "modules.alunos.config.huey",
    ]
    assert recebidos[0][0] is huey
    assert recebidos[0][1]["worker_type"] == "thread"
    assert registro["apps.matriculas.tasks.Tarefa"] is tarefa
