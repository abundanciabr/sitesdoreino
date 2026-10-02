"""Verifica que as telas da Caixa explicam as etapas e os estados das ideias."""

import pytest
from django.urls import reverse

from apps.core.participacao import (
    ETAPAS,
    EXPLICACAO_DAS_ETAPAS,
    VOTAR_NUNCA_FECHA,
    legenda_das_etapas,
)
from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db

def _corpo(pessoa, endereco: str) -> str:
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def test_nenhuma_situacao_da_ideia_nasce_muda():
    """Toda situação do model tem a frase dela — inclusive as duas saídas.

    Este é o degrau que impede o buraco de voltar: quem acrescentar um status
    novo em `Sugestao.Status` fica vermelho aqui, antes de um aluno topar com
    um selo que ninguém explica.
    """
    sem_texto = {s.value for s in Sugestao.Status} - set(EXPLICACAO_DAS_ETAPAS)
    assert not sem_texto, f"situação sem explicação para o aluno: {sorted(sem_texto)}"


def test_a_pagina_da_ideia_explica_as_quatro_etapas(dentro, sugestao):
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    for etapa in legenda_das_etapas():
        assert etapa["explicacao"] in corpo, etapa["chave"]
    assert VOTAR_NUNCA_FECHA in corpo


def test_o_quadro_explica_as_quatro_etapas(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    for etapa in legenda_das_etapas():
        assert etapa["explicacao"] in corpo, etapa["chave"]
    assert VOTAR_NUNCA_FECHA in corpo


@pytest.mark.parametrize("situacao", [s.value for s in Sugestao.Status])
def test_a_pagina_diz_o_que_a_situacao_desta_ideia_significa(
    dentro, sugestao, situacao
):
    """Inclusive `nao_planejado` e `mesclado`, que não têm bolinha na linha.

    São as duas situações em que a pessoa mais precisa de uma frase, e as duas
    que a legenda sozinha não cobriria: elas não são etapa do caminho, chegam
    pelo link direto e aparecem só como selo.

    `update()` e não `save()`: `Sugestao.save()` recusa
    `planejado → em_desenvolvimento` sem ChangeSpec aprovado (EVO-40), e esta
    prova é sobre o TEXTO da página, não sobre o corredor da moderação.
    """
    Sugestao.objects.filter(pk=sugestao.pk).update(status=situacao)
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    assert EXPLICACAO_DAS_ETAPAS[situacao] in corpo


def test_a_legenda_lista_as_quatro_etapas_do_caminho_e_so_elas():
    """As duas saídas têm texto, e de propósito NÃO entram na legenda.

    A legenda acompanha uma linha de quatro bolinhas; listar seis passos ali
    faria a explicação discordar do desenho que ela explica.
    """
    assert [etapa["chave"] for etapa in legenda_das_etapas()] == list(ETAPAS)
