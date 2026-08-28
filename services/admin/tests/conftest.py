"""Acesso ao banco liberado para toda a suíte desta célula.

**Por que isto passou a ser necessário em 28/08/2026:** a porta
(`apps/core/porta.py`) deixou de ler a lista de administradores só do env e
passou a somá-la com a tabela `Administrador`
(`DECISAO-administradores-e-apagar` §3.1). Ou seja, **toda requisição
autorizada desta célula toca o banco** — que é exatamente o que acontece em
produção.

Sem este `autouse`, 60 testes que nunca precisaram de banco passariam a
reprovar com `RuntimeError: Database access not allowed` — e a leitura errada
seria "a mudança quebrou a porta", quando o que mudou foi de quanto a porta
precisa para responder.

O `/healthz` continua sem tocar no banco: ele é caminho ISENTO, e a porta
devolve antes de chegar à lista. `tests/test_inv_porta_fail_closed.py` mede
isso, e continua verde sem depender deste fixture.
"""

import pytest


@pytest.fixture(autouse=True)
def banco_disponivel(db):
    """`db` em tudo: a porta desta célula consulta o banco a cada requisição."""
    return db
