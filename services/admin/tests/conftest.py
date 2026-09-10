"""O que vale para TODA a suíte desta célula: o banco, e o corte da API paga.

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

**O segundo assunto deste arquivo, desde 07/09/2026:** nenhum teste desta célula
sai para a API paga da Anthropic, e a garantia não depende de o próximo autor
copiar o corte à mão para o arquivo dele (`sem_a_rede_do_sdk`, abaixo).
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
        yield
        return
    painel = RAIZ_DO_REPO / "painel"
    if (painel / "painel.html").is_file():
        yield
        return
    gerador = painel / "gerar_manifesto.js"
    node = shutil.which("node")
    if not gerador.is_file() or node is None:
        yield
        return
    subprocess.run(
        [node, str(gerador)],
        cwd=str(painel),
        check=True,
        capture_output=True,
        timeout=300,
    )
    try:
        yield
    finally:
        for arquivo in (painel / "painel.html", *painel.glob("livro-*.js")):
            arquivo.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def banco_disponivel(db):
    """`db` em tudo: a porta desta célula consulta o banco a cada requisição."""
    return db


@pytest.fixture(autouse=True)
def sem_a_rede_do_sdk(monkeypatch):
    """Nenhum teste desta célula fala com a API paga da Anthropic.

    O corte mora AQUI, e não dentro de `tests/test_analista.py`, porque proteção
    que depende de o próximo autor lembrar de copiar doze linhas não é proteção:
    o primeiro teste de tela que fizer `client.post(reverse("reuniao"),
    {"acao": "analista"})` sem repetir o corte faz uma chamada paga de verdade,
    com a chave da máquina de quem rodou. E a chave está na máquina do
    mantenedor desde 02/09/2026 (`armadilhas/288`). O molde é o
    `sem_rede` de `services/forum/tests/conftest.py`.

    **É o `httpx2`, e não o `httpx`.** O SDK da Anthropic roda sobre `httpx2`,
    um pacote separado que entra junto na instalação. O `httpx` desta célula
    fica de fora deste corte de propósito: é por ele que a `admin` fala com
    `identidade` e `alunos`, e quem o dubla é o `respx` dos testes de tela.
    Trocar `httpx.Client.get` aqui cegaria o `respx`, que intercepta mais abaixo,
    no transporte.

    O corte é no TRANSPORTE porque o SDK chama `Client.send`, que `post` não
    intercepta, e porque é ali que o teste que QUER uma resposta de mentira troca
    a mesma função, deixando o SDK montar o request e ler a resposta como faz em
    produção.

    **Os DOIS transportes.** O síncrono é o que o analista usa hoje; o
    assíncrono fica cortado desde já porque o dia em que esta célula ganhar
    streaming ou `AsyncAnthropic`, como o fórum já tem em `rascunhar_ao_vivo`, é
    um dia em que ninguém vai lembrar de voltar aqui, e a suíte voltaria a se
    declarar sem rede chamando a API paga pelo outro lado.
    """
    import httpx2

    def recusa(*args, **kwargs):
        raise httpx2.ConnectError("a suíte da admin não fala com a rede")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", recusa)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", recusa)


@pytest.fixture(autouse=True)
def sem_a_chave_da_anthropic(monkeypatch):
    """A suíte inteira começa com o robô DESLIGADO, e cada teste liga o dele.

    O contrário (herdar a chave do ambiente de quem roda) faz um teste passar na
    máquina do mantenedor por um motivo que não existe na CI, e faz um caminho
    que deveria ser exercitado sem chave sair para a rede.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
