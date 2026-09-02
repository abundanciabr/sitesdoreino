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

    **SÃO DUAS BIBLIOTECAS, e desde 02/09/2026 as duas são cortadas.** O `httpx`
    é por onde esta célula fala com `identidade`, `alunos`, `catalogo` e
    `gamificacao`. O `httpx2` é outro pacote, instalado junto com o SDK da
    Anthropic (`apps/core/agente.py`), e o corte antigo não o alcançava: a suíte
    dizia no próprio docstring que não falava com a rede e podia chamar a API
    paga da Anthropic de verdade, com a chave da máquina de quem rodasse os
    testes (`armadilhas/288`).

    O corte do `httpx2` é no TRANSPORTE, e não em `Client.post`, por dois
    motivos: o SDK chama `Client.send`, que `post` não intercepta, e cortar no
    transporte deixa o dublê dos testes do agente trocar essa mesma função por
    uma resposta de mentira — exercitando o SDK de verdade, com o request e a
    leitura da resposta que a produção usa (`armadilhas/061`).
    """
    import httpx
    import httpx2

    def recusa(*args, **kwargs):
        raise httpx.ConnectError("a suíte do fórum não fala com a rede")

    def recusa_httpx2(*args, **kwargs):
        raise httpx2.ConnectError("a suíte do fórum não fala com a rede")

    monkeypatch.setattr(httpx.Client, "get", recusa)
    monkeypatch.setattr(httpx.Client, "post", recusa)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", recusa_httpx2)
