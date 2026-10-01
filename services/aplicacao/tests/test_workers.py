import types

import workers


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
    huey = object()
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
