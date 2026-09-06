"""Guardas da porta de MÁQUINA (`/interno`) do portfólio.

Três coisas se provam aqui, e cada uma tem um modo de falha silencioso:

1. **O Bearer é o único cadeado.** Esta célula roda sob `SCRIPT_NAME=/pages` e o
   corte do prefixo é do Django, não do Traefik: `/interno` é alcançável pela
   borda pública em `meshcraft.top/pages/interno/...` (`armadilhas/186`). Se o
   401 sumir, nada quebra, nenhuma tela muda, e o portfólio de qualquer aluno
   passa a responder para a internet inteira. Por isso o guarda cobre o
   sem-token, o token errado E o conjunto de tokens vazio, que é o estado de uma
   VPS onde ninguém colou o env ainda.

2. **O isolamento por aluno atravessa a porta.** O critério AC-07 diz "em nenhuma
   tela e em nenhuma resposta de API", e API é aqui. O cenário monta dois alunos
   com portfólio em etapas diferentes, e um terceiro no MESMO site com o mesmo
   fim: cenário fraco (um aluno só) ficaria verde mesmo sem filtro nenhum.

3. **Só id opaco sai.** A resposta é conferida campo a campo, e não por
   "contém": um campo novo que vaze link, legenda ou apelido reprova aqui antes
   de virar contrato congelado.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

TOKEN = "token-de-teste-do-par"
SITE = "escola-a"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get(f"/interno{caminho}", **cabecalhos)


def corpo(resposta):
    return json.loads(resposta.content)


def caminho(aluno_id: str, site_id: str = SITE) -> str:
    return f"/portfolios/{site_id}/{aluno_id}"


# ---------------------------------------------------------------------------
# 1. O cadeado
# ---------------------------------------------------------------------------
def test_sem_token_e_401(criar_portfolio):
    criar_portfolio("aluno-1")
    assert pedir(caminho("aluno-1"), token=None).status_code == 401


def test_token_errado_e_401(criar_portfolio):
    criar_portfolio("aluno-1")
    assert pedir(caminho("aluno-1"), token="token-de-outra-pessoa").status_code == 401


def test_conjunto_de_tokens_vazio_recusa_todo_mundo(settings, criar_portfolio):
    """O estado de uma VPS onde o env ainda não foi colado: ninguém entra.

    É o caso que o desenho promete (fail-closed sem derrubar o boot) e o único
    em que um erro de digitação no nome da variável passaria despercebido: com o
    conjunto vazio, `token in set()` é falso para qualquer token.
    """
    criar_portfolio("aluno-1")
    settings.TOKENS_ACEITOS = set()
    assert pedir(caminho("aluno-1")).status_code == 401


# ---------------------------------------------------------------------------
# 2. O isolamento
# ---------------------------------------------------------------------------
def test_o_portfolio_de_um_aluno_nunca_sai_na_resposta_de_outro(
    criar_portfolio, criar_estado
):
    """Dois alunos no MESMO site, em etapas diferentes: a resposta é de quem foi pedido."""
    criar_estado(criar_portfolio("aluno-1"), etapa_atual=2)
    criar_estado(criar_portfolio("aluno-2"), etapa_atual=5)

    assert corpo(pedir(caminho("aluno-1")))["etapa_atual"] == 2
    assert corpo(pedir(caminho("aluno-2")))["etapa_atual"] == 5


def test_o_portfolio_de_outro_site_nao_responde(criar_portfolio):
    """A fronteira de site (Lei 9) vale na porta de máquina como vale na tela."""
    criar_portfolio("aluno-1", site_id="escola-b")
    assert pedir(caminho("aluno-1", site_id="escola-a")).status_code == 404


def test_o_cenario_do_teste_tem_dente(criar_portfolio, criar_estado):
    """Sem esta linha, os testes de isolamento passariam com um só aluno no banco.

    Cenário fraco é a forma mais comum de guarda que não guarda nada: com um
    aluno só, `do_aluno` trocado por `all()` continuaria devolvendo a resposta
    certa (`armadilhas/195` é a irmã disso do lado do vermelho).
    """
    from apps.portfolio.models import Portfolio

    criar_estado(criar_portfolio("aluno-1"), etapa_atual=2)
    criar_estado(criar_portfolio("aluno-2"), etapa_atual=5)
    criar_portfolio("aluno-1", site_id="escola-b")
    assert Portfolio.objects.count() == 3


# ---------------------------------------------------------------------------
# 3. O que sai, e o que nunca sai
# ---------------------------------------------------------------------------
def test_a_resposta_tem_exatamente_tres_campos_e_nenhum_e_conteudo(
    criar_portfolio, criar_peca, criar_estado
):
    """Campo a campo, e não "contém": conteúdo do aluno não atravessa a porta.

    A peça tem link e legenda, e o portfólio tem apelido e vitrine ligada, de
    propósito: se um campo novo vazasse qualquer um dos quatro, este teste
    reprovaria antes de o contrato congelar o vazamento.
    """
    portfolio = criar_portfolio("aluno-1", apelido="ana3d", publicada=True)
    criar_peca(portfolio, link="https://exemplo.test/render.png", legenda="Caneca")
    criar_estado(portfolio, etapa_atual=3)

    resposta = corpo(pedir(caminho("aluno-1")))
    assert set(resposta) == {"portfolio_id", "etapa_atual", "conferido_em"}
    assert resposta["portfolio_id"] == str(portfolio.pk)
    assert resposta["etapa_atual"] == 3
    assert resposta["conferido_em"] is None


def test_aluno_sem_estado_responde_a_primeira_etapa_sem_selo(criar_portfolio):
    """Quem abriu o portfólio e nunca andou não é erro: é a etapa 1, sem selo.

    `EstadoDoAluno` só nasce no degrau 07. Estourar aqui deixaria a porta em 500
    para o caso mais comum de todos, o do aluno que acabou de começar.
    """
    criar_portfolio("aluno-1")
    resposta = corpo(pedir(caminho("aluno-1")))
    assert resposta["etapa_atual"] == 1
    assert resposta["conferido_em"] is None


def test_o_selo_sai_com_a_data_em_que_o_monitor_conferiu(criar_portfolio, criar_estado):
    """O selo vale para o que o monitor VIU no dia (plano §6.2), e a data é o dia."""
    from tests.conftest import agora

    conferido = agora()
    criar_estado(
        criar_portfolio("aluno-1"),
        selo_conferido_em=conferido,
        selo_conferido_por="monitor-1",
    )
    assert corpo(pedir(caminho("aluno-1")))["conferido_em"] == conferido.isoformat()


def test_aluno_sem_portfolio_e_404_e_nao_um_200_vazio(criar_portfolio):
    """`Ele não começou` é um fato, e o 404 é como um fato desses se diz.

    200 com campos vazios obrigaria cada consumidor a inventar a própria regra
    para distinguir "não começou" de "começou e está no zero", e a primeira
    divergência entre duas dessas regras seria invisível.
    """
    criar_portfolio("outro-aluno")
    assert pedir(caminho("aluno-1")).status_code == 404


def test_a_porta_nao_escreve(criar_portfolio):
    """Nenhum verbo além de GET: quem muda o portfólio é o aluno, com sessão."""
    criar_portfolio("aluno-1")
    for verbo in (Client().post, Client().put, Client().delete):
        resposta = verbo(
            f"/interno{caminho('aluno-1')}", HTTP_AUTHORIZATION=f"Bearer {TOKEN}"
        )
        assert resposta.status_code == 405
