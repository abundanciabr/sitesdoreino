"""O dublê de rede da suíte do fórum, e o banco de teste com a cura da busca.

**Nenhum teste desta célula fala com a `identidade` ou com a `alunos` de
verdade.** Suíte que depende de outra célula estar no ar fica vermelha por
motivo alheio — e uma suíte que fica vermelha sozinha deixa de ser lida.

O padrão é o de `services/sugestoes/tests/conftest.py`.
"""

import pytest
from django.db import connection

from apps.forum.config_de_busca import SQL_DA_CURA


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """O banco de teste nasce com a configuração de busca sem acento.

    **Por que aqui, e não numa migração** (`armadilhas/154`): criar extensão
    exige superusuário do PostgreSQL. Na CI o usuário do banco é superusuário e
    a migração passaria; em produção a célula roda com um papel restrito e o
    `migrate` do boot **morreria na VPS**, com o container em crashloop. Verde
    na CI, vermelho só em produção: a combinação que este projeto mais paga
    caro para evitar.

    Em produção quem cria é `infra/provisionar-forum.sh`, que já roda com esse
    poder. Aqui é a preparação do banco de TESTE, e o SQL é o MESMO — importado
    de `config_de_busca.py`, não copiado: duas versões da cura divergiriam, e a
    suíte passaria a provar uma configuração que a produção não tem.
    """
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(SQL_DA_CURA)


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Corta a rede para TODO teste, e o corte é fail-closed.

    Se algum caminho tentar perguntar quem é a pessoa sem que o teste tenha
    montado o dublê, a chamada levanta — e o código de produção trata isso
    fechando a porta, que é exatamente o comportamento que se quer provar.
    """
    import httpx

    def recusa(*args, **kwargs):
        raise httpx.ConnectError("a suíte do fórum não fala com a rede")

    monkeypatch.setattr(httpx.Client, "get", recusa)
    monkeypatch.setattr(httpx.Client, "post", recusa)
