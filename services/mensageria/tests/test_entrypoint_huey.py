# Teste-guarda do entrypoint oficial do worker (ARMADILHAS §1/H10.2 e §4.11):
# `python manage.py run_huey` só existe com `huey.contrib.djhuey` em INSTALLED_APPS,
# e só serve as tasks certas se `settings.HUEY` for a MESMA instância de
# config/huey.py. Sem estas garantias, o worker de produção volta a depender do
# bootstrap de 6 linhas embutido no compose.
from django.conf import settings
from django.core.management import get_commands


def test_djhuey_instalado_e_run_huey_disponivel():
    assert "huey.contrib.djhuey" in settings.INSTALLED_APPS
    assert get_commands().get("run_huey") == "huey.contrib.djhuey"


def test_djhuey_serve_a_mesma_instancia_das_tasks():
    # Instância diferente = duas filas: o handler enfileira numa, o worker escuta
    # a outra, e nenhum e-mail sai — o modo de falha silencioso do §4.11.
    import huey.contrib.djhuey as djhuey
    from config.huey import huey as instancia_das_tasks

    assert djhuey.HUEY is instancia_das_tasks


def test_registry_da_instancia_servida_contem_a_task_de_envio():
    # O autodiscover do run_huey importa apps/eventos/tasks.py (sinal vivo no log:
    # `+ apps.eventos.tasks.enviar_notificacao`). Aqui, o guarda estático: o mesmo
    # import registra a task NA INSTÂNCIA que o run_huey serve.
    import huey.contrib.djhuey as djhuey

    import apps.eventos.tasks  # noqa: F401  (o mesmo import que o autodiscover faz)

    nomes = list(djhuey.HUEY._registry._registry)
    assert any(n.endswith("enviar_notificacao") for n in nomes), nomes
