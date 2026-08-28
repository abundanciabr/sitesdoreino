"""O dublê de rede da suíte do fórum.

**Nenhum teste desta célula fala com a `identidade` ou com a `alunos` de
verdade.** Suíte que depende de outra célula estar no ar fica vermelha por
motivo alheio — e uma suíte que fica vermelha sozinha deixa de ser lida.

O padrão é o de `services/sugestoes/tests/conftest.py`.
"""

import pytest


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
