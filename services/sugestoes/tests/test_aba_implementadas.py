"""A aba "IMPLEMENTADAS" do quadro, pedida pelo mantenedor em 29/09/2026.

A quarta aba ao lado de "Em alta", "Mais votadas" e "Novas": mostra só as ideias
que a equipe já entregou, e a entregue por último vem primeiro. É a vitrine do
"a Caixa funciona", então a ordem é a da entrega, não a dos votos.
"""

import re

import pytest
from django.urls import reverse

from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db

TITULO_DE_PECA = re.compile(r'<h3 class="peca-titulo"><a href="[^"]*">([^<]+)</a>')


def _corpo(pessoa, **query) -> str:
    endereco = reverse("quadro") + "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _implementar(caixa, sugestao: Sugestao) -> None:
    resposta = caixa.mudar_status(
        sugestao, Sugestao.Status.IMPLEMENTADO, nota="Entregue na plataforma."
    )
    assert resposta.status_code == 200, resposta.content


def test_a_aba_mostra_so_as_implementadas_e_a_entregue_por_ultimo_primeiro(caixa):
    entregue_antes = caixa.publicar("Tutorial de chapéu")
    entregue_agora = caixa.publicar("Guia de portfólio")
    em_analise = caixa.publicar("Ideia ainda em votação")
    caixa.votar(entregue_antes)
    caixa.votar(em_analise)
    _implementar(caixa, entregue_antes)
    _implementar(caixa, entregue_agora)

    assert TITULO_DE_PECA.findall(_corpo(caixa.aluno, ordem="implementadas")) == [
        "Guia de portfólio",
        "Tutorial de chapéu",
    ]


def test_a_aba_aparece_ao_lado_das_outras_e_carrega_a_categoria(caixa):
    corpo = _corpo(caixa.aluno, ordem="novas", categoria="curso")

    assert (
        f'href="{reverse("quadro")}?ordem=implementadas&amp;categoria=curso"' in corpo
    )
    assert ">Implementadas</a>" in corpo


def test_a_aba_vazia_diz_o_que_vai_aparecer_nela(caixa):
    caixa.publicar("Ideia ainda em votação")

    corpo = _corpo(caixa.aluno, ordem="implementadas")

    assert TITULO_DE_PECA.findall(corpo) == []
    assert "Nenhuma ideia implementada aqui ainda" in corpo


@pytest.mark.parametrize("ordem", ["em-alta", "mais-votadas", "novas"])
def test_a_implementada_sai_das_outras_abas(caixa, ordem):
    """Pedido do mantenedor, 29/09/2026: a ideia entregue só aparece quando
    alguém clica em Implementadas."""
    entregue = caixa.publicar("Tutorial de chapéu")
    caixa.publicar("Ideia ainda em votação")
    caixa.votar(entregue)
    _implementar(caixa, entregue)

    assert TITULO_DE_PECA.findall(_corpo(caixa.aluno, ordem=ordem)) == [
        "Ideia ainda em votação"
    ]
