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

import shutil
import subprocess
from pathlib import Path

import pytest

CELULA = Path(__file__).resolve().parents[1]
RAIZ_DO_REPO = CELULA.parents[1]


@pytest.fixture(scope="session", autouse=True)
def painel_materializado():
    """O painel é MONTADO antes da suíte que o mede (Onda 3 — escritor único).

    Desde 28/08/2026 `painel/painel.html` e `painel/livro-AAAAMM.js` não moram
    mais no Git: eles eram a colisão diária entre robôs (`armadilhas/156`), e
    quem os constrói é a integração. Num checkout novo eles simplesmente não
    existem — e esta célula SERVE o painel do dono, então metade da suíte
    mediria uma pasta vazia.

    Na imagem de produção nada acontece aqui: `painel_embutido/` já vem pronto,
    montado pelo `deploy-celula` antes do build.

    **Não silencia nada.** Se o Node faltar, o fixture volta sem montar e
    `test_a_pasta_do_painel_foi_encontrada` reprova alto, dizendo que a pasta
    não foi encontrada — que é a verdade. Montar em silêncio é o oposto disto:
    seria um verde sem medição.
    """
    if (CELULA / "painel_embutido" / "painel.html").is_file():
        return
    painel = RAIZ_DO_REPO / "painel"
    if (painel / "painel.html").is_file():
        return
    gerador = painel / "gerar_manifesto.js"
    node = shutil.which("node")
    if not gerador.is_file() or node is None:
        return
    subprocess.run(
        [node, str(gerador)], cwd=str(painel), check=True, capture_output=True, timeout=300
    )


@pytest.fixture(autouse=True)
def banco_disponivel(db):
    """`db` em tudo: a porta desta célula consulta o banco a cada requisição."""
    return db
