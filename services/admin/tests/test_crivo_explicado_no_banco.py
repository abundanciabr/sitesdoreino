"""O Crivo explicado do zero chega ao banco de produção, e o leigo o lê sem entrar.

Guarda de `0021_semear_o_crivo_explicado.py`. Mesmo desenho de
`test_guia_do_portfolio_no_banco.py`: no banco de teste a `0003` semeia a pasta
inteira, inclusive este documento, e a `0021` não encontraria o que inserir.
Cada teste apaga a linha antes, fabricando o banco que a migração vai encontrar
em produção (`armadilhas/253`, `347`).

Este documento é PÚBLICO: o pedido foi uma página para leigos e iniciantes
em criação deste tipo de sistema, e essa gente não passa pela porta do admin.
"""

import importlib
import re

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.figuras import FIGURAS
from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0021_semear_o_crivo_explicado"
)

NOME = "o-crivo-explicado-do-zero"
TITULO = "O Crivo explicado do zero"

#: Frases que, se caíssem da semente, deixariam a página abrindo com 200 e
#: ensinando o contrário do que a célula é. Não duplicam o documento: prendem
#: a semente de uma instalação nova.
AS_FRASES_DO_NUCLEO = (
    "O quiz não sabe o que é um cartão de crédito",
    "tela não é lugar de descobrir que o dado está pela metade",
    "um teste que passa nas duas situações não é um teste",
    "Subir não é abastecer",
)


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_o_crivo(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_do_documento(db):
    Documento.objects.filter(nome=NOME).delete()


def test_o_crivo_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == TITULO
    assert documento.publico is True


def test_o_leigo_le_o_crivo_sem_passar_por_porta_nenhuma(
    banco_de_producao_antes_do_documento,
):
    _semear()

    pagina = Client().get(f"/docs/{NOME}")
    assert pagina.status_code == 200
    html = pagina.content.decode()
    assert TITULO in Client().get("/docs/").content.decode()
    assert "<svg" in html
    assert "<table>" in html
    assert "recepcionista" in html.lower()


def test_o_crivo_carrega_as_frases_do_nucleo(
    banco_de_producao_antes_do_documento,
):
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    for frase in AS_FRASES_DO_NUCLEO:
        assert frase in corpo


def test_toda_figura_do_crivo_existe_na_casa(
    banco_de_producao_antes_do_documento,
):
    """Uma figura digitada no texto e ausente em figuras.py vira parágrafo
    cru na tela: a página abre, a ilustração some, e ninguém reclama."""
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    nomes = re.findall(r"\(figura:([a-z0-9-]+)\)", corpo)
    assert nomes, "o documento do Crivo nasceu sem nenhuma figura"
    html = documentos.para_html(corpo)
    assert html.count("<figure") == len(nomes)
    faltando = sorted(set(nomes) - set(FIGURAS))
    assert not faltando, f"figuras citadas e ausentes: {faltando}"


def test_a_pagina_publica_desenha_as_figuras_e_escapa_html(
    banco_de_producao_antes_do_documento,
):
    _semear()

    html = documentos.para_html(Documento.objects.get(nome=NOME).corpo)
    assert "<script>" not in html
    assert "<svg" in html
    assert "<table>" in html


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=False
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is False


def test_semeia_so_o_crivo_e_nao_a_pasta_inteira(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()
