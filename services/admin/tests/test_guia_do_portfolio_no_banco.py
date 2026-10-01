"""O guia do portfólio chega privado ao banco de produção.

Guarda de `0011_semear_o_guia_do_portfolio.py`. Mesmo desenho de
`test_alavancas_10x_no_banco.py`: no banco de teste a `0003` semeia a pasta
inteira, inclusive este documento, e a `0011` não encontraria o que inserir.
Cada teste apaga a linha antes, fabricando o banco que a migração vai encontrar
em produção (`armadilhas/253`, `347`).

O guia fica somente para administradores por decisão de 27/09/2026.
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

# A semente acompanha as escolhas do aluno e o apoio da escola.
PASSOS_DA_JORNADA = (
    "explorar sugestões no quiz",
    "Criar meu projeto sem quiz",
    "pedir feedback sobre um projeto em desenvolvimento",
    "obras selecionadas quando você decidir publicá-la",
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


def test_o_guia_entra_privado_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == TITULO
    assert documento.publico is False


def test_visitante_nao_le_o_guia_nem_o_encontra_na_lista_publica(
    banco_de_producao_antes_do_documento,
):
    _semear()

    pagina = Client().get(f"/docs/{NOME}")
    assert pagina.status_code == 404
    assert TITULO not in Client().get("/docs/").content.decode()


def test_o_guia_carrega_a_jornada_autoral(
    banco_de_producao_antes_do_documento,
):
    _semear()

    corpo = Documento.objects.get(nome=NOME).corpo
    for passo in PASSOS_DA_JORNADA:
        assert passo in corpo
    assert "escolha pelo menos 3 desses tipos" not in corpo
    assert "a maioria seja mesmo high poly" not in corpo


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
