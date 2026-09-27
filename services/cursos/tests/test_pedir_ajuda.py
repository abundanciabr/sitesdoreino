"""COM-03: a aula e o laudo dizem onde pedir ajuda no grupo da Comunidade.

O dossiê da Comunidade (documentos/comunidade.md, "Como pedir ajuda") exige que
todo desafio explique como pedir ajuda. Esta célula não sabe nada de fórum ou
gamificação (constituicoes/AGENTS.cursos.md): o link é um caminho absoluto
fixo para outra célula (`/forum/comunidade`), nunca `reverse()`.

O que este arquivo protege:

1. Na aula, o bloco fica dentro do checkpoint, perto do "aceito quando" e do
   envio (o mesmo lugar onde os dois já vivem).
2. No laudo, o bloco vem depois da data de retorno e da mudança pedida.
3. As duas telas linkam para `/forum/comunidade` e trazem as três linhas do
   bom pedido (o que entrega, onde travou, o que já tentou).
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import COOKIE, forcas_validas, mudanca_valida, notas_validas

pytestmark = pytest.mark.django_db

LINK_DA_COMUNIDADE = "/forum/comunidade"
AS_TRES_LINHAS = (
    "o que você está tentando entregar",
    "onde você travou",
    "o que você já tentou",
)


def corpo_de(resposta) -> str:
    return resposta.content.decode()


def test_a_aula_mostra_onde_pedir_ajuda_perto_do_aceito_quando_e_do_envio(
    aluna, envio_na_fila, client
):
    corpo = corpo_de(
        client.get(
            reverse("aula-do-curso", args=["profissional", 1, "E00"]),
            HTTP_COOKIE=COOKIE,
        )
    )
    inicio = corpo.index('id="checkpoint"')
    checkpoint = corpo[inicio : corpo.index("</section>", inicio)]

    assert f'href="{LINK_DA_COMUNIDADE}"' in checkpoint
    for linha in AS_TRES_LINHAS:
        assert linha in checkpoint.lower()

    posicao_aceito_quando = checkpoint.index("aceito-quando")
    posicao_envio = checkpoint.index('class="envio"')
    posicao_ajuda = checkpoint.index(LINK_DA_COMUNIDADE)
    assert posicao_aceito_quando < posicao_ajuda < posicao_envio


def test_a_aula_sem_envio_ainda_mostra_o_bloco_perto_do_aceito_quando(
    aluna, ana_pronta, client
):
    """Antes de qualquer entrega o "envio" não existe, mas o "aceito quando"
    sim: o bloco continua ali, porque é aceito quando que o aluno lê primeiro."""
    corpo = corpo_de(
        client.get(
            reverse("aula-do-curso", args=["profissional", 1, "E00"]),
            HTTP_COOKIE=COOKIE,
        )
    )
    inicio = corpo.index('id="checkpoint"')
    checkpoint = corpo[inicio : corpo.index("</section>", inicio)]
    assert f'href="{LINK_DA_COMUNIDADE}"' in checkpoint
    assert checkpoint.index("aceito-quando") < checkpoint.index(LINK_DA_COMUNIDADE)


def test_o_laudo_mostra_onde_pedir_ajuda_depois_da_data_e_da_mudanca(
    aluna, envio_na_fila, professora, client
):
    amanha = dt.date.today() + dt.timedelta(days=3)
    parecer.emitir(
        envio_na_fila,
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio_na_fila.aula),
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=amanha,
        sabe_o_que_fazer_amanha=True,
    )
    corpo = corpo_de(
        client.get(reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE)
    )

    assert f'href="{LINK_DA_COMUNIDADE}"' in corpo

    data_formatada = amanha.strftime("%d/%m/%Y")
    posicao_data = corpo.find(data_formatada)
    posicao_mudanca = corpo.find("Praticar UV na próxima entrega.")
    posicao_ajuda = corpo.find(f'href="{LINK_DA_COMUNIDADE}"')

    assert posicao_data != -1 and posicao_mudanca != -1 and posicao_ajuda != -1
    assert posicao_data < posicao_ajuda
    assert posicao_mudanca < posicao_ajuda
    for linha in AS_TRES_LINHAS:
        assert linha in corpo.lower()
