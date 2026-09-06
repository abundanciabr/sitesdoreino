"""O guia do portfólio chega ao banco de produção, e o aluno o lê sem entrar.

Guarda de `0011_semear_o_guia_do_portfolio.py`. Mesmo desenho de
`test_alavancas_10x_no_banco.py`: no banco de teste a `0003` semeia a pasta
inteira, inclusive este documento, e a `0011` não encontraria o que inserir.
Cada teste apaga a linha antes, fabricando o banco que a migração vai encontrar
em produção (`armadilhas/253`, `347`).

A diferença para os guardas dos outros documentos novos é o público: este é
PÚBLICO, porque quem o lê é o aluno, e ele precisa abrir sem porta nenhuma.
"""

import importlib

import pytest
from django.test import Client

from apps.core.models import Documento

_semeadura = importlib.import_module(
    "apps.core.migrations.0011_semear_o_guia_do_portfolio"
)

NOME = "guia-do-portfolio"
TITULO = "Como montar o seu portfólio"

#: As quatro regras objetivas da professora, uma frase de cada. Elas são o
#: motivo de a semente existir: um guia que perdesse uma delas continuaria
#: abrindo com 200, e ninguém veria a falta.
#:
#: Isto NÃO duplica o guia. O texto que vale é o do banco, que o mantenedor
#: edita pela tela, e nenhum teste manda nele. O que estas frases prendem é a
#: SEMENTE de uma instalação nova: quem editar `documentos/guia-do-portfolio.md`
#: e derrubar uma das quatro é avisado aqui.
AS_QUATRO_REGRAS = (
    "escolha pelo menos 3 desses tipos",
    "pelo menos 3 peças de cada um",
    "a maioria seja mesmo high poly",
    "não se pareçam com a aula",
)


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_o_guia(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_do_documento(db):
    Documento.objects.filter(nome=NOME).delete()


def test_o_guia_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == TITULO
    assert documento.publico is True


def test_o_aluno_le_o_guia_sem_passar_por_porta_nenhuma(
    banco_de_producao_antes_do_documento,
):
    _semear()

    pagina = Client().get(f"/docs/{NOME}")
    assert pagina.status_code == 200
    assert TITULO in Client().get("/docs/").content.decode()


def test_o_guia_carrega_as_quatro_regras_da_professora(
    banco_de_producao_antes_do_documento,
):
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    for regra in AS_QUATRO_REGRAS:
        assert regra in corpo


def test_o_guia_diz_ao_aluno_que_ainda_e_rascunho(
    banco_de_producao_antes_do_documento,
):
    """A professora marcou o texto como rascunho, e o aluno tem de saber disso.

    Sem esta frase o guia promete regra fechada onde ainda não há uma, e a
    escola passa a dever ao aluno um critério que pode mudar amanhã.
    """
    _semear()

    assert "rascunho" in Documento.objects.get(nome=NOME).corpo.lower()


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=True
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
