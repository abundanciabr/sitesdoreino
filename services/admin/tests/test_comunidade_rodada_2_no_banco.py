"""A pagina da Comunidade Meshcraft ganha a rodada 2 no banco de producao.

Guarda de `0031_atualizar_a_comunidade_na_rodada_2.py`. Mesmo desenho de
`test_comunidade_no_banco.py`: no banco de teste a `0030` semeia com o arquivo
de HOJE (ja com as secoes da rodada 2), entao a `0031` nunca encontraria o
texto da rodada 1 para atualizar. Cada teste abaixo reconstroi o estado que a
migracao encontra de verdade em producao (o texto que a `0030` semeou em
27/09/2026, antes desta rodada) e so entao chama a funcao dela.
"""

import importlib

import pytest

from apps.core.models import Documento, VersaoDoDocumento

_atualizacao = importlib.import_module(
    "apps.core.migrations.0031_atualizar_a_comunidade_na_rodada_2"
)

NOME = "comunidade"
TITULO_DA_RODADA_1 = (
    "A Comunidade Meshcraft: o que é, o que fazer agora e como pedir ajuda"
)
CORPO_DA_RODADA_1 = _atualizacao.CORPO_DA_RODADA_1

CONTRIBUICOES = "Como funcionam as contribuições"
QUADRO_DE_CONTRIBUICOES = "/conquistas/contribuicoes"
O_QUE_A_ESCOLA_REGISTRA = "O que a escola registra"
NINGUEM_APROVA_A_PROPRIA = "ninguém aprova a própria contribuição"


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com os modelos de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert app_label == "core"
        return {"Documento": Documento, "VersaoDoDocumento": VersaoDoDocumento}[
            model_name
        ]


def _atualizar():
    _atualizacao.atualizar_para_a_rodada_2(_AppsFalso, None)


@pytest.fixture
def documento_da_rodada_1(db):
    """O documento tal como a `0030` o deixou em produção, antes desta rodada."""
    Documento.objects.filter(nome=NOME).delete()
    return Documento.objects.create(
        nome=NOME,
        titulo=TITULO_DA_RODADA_1,
        publico=True,
        ordem=12,
        corpo=CORPO_DA_RODADA_1,
    )


def test_atualiza_o_texto_e_preserva_a_versao_anterior(documento_da_rodada_1):
    documento = documento_da_rodada_1

    _atualizar()

    documento.refresh_from_db()
    assert CONTRIBUICOES in documento.corpo
    assert QUADRO_DE_CONTRIBUICOES in documento.corpo
    assert O_QUE_A_ESCOLA_REGISTRA in documento.corpo
    assert NINGUEM_APROVA_A_PROPRIA in documento.corpo
    assert documento.publico is False
    assert documento.titulo == TITULO_DA_RODADA_1
    assert documento.ordem == 12

    versoes = list(documento.versoes.all())
    assert len(versoes) == 1
    versao = versoes[0]
    assert versao.corpo == CORPO_DA_RODADA_1
    assert versao.publico is True
    assert CONTRIBUICOES not in versao.corpo
    assert versao.gesto == (
        "preservou o texto da rodada 1 antes da atualizacao da rodada 2"
    )


def test_nao_sobrescreve_edicao_do_mantenedor(documento_da_rodada_1):
    """Se o texto publicado já não é mais o semeado pela rodada 1, a migração
    não troca nada: quem tem a caneta pela tela é o mantenedor."""
    documento = documento_da_rodada_1
    documento.titulo = "Editado pelo dono"
    documento.corpo = CORPO_DA_RODADA_1 + "\n\numa frase que o mantenedor escreveu"
    documento.save()

    _atualizar()

    documento.refresh_from_db()
    assert documento.titulo == "Editado pelo dono"
    assert "uma frase que o mantenedor escreveu" in documento.corpo
    assert CONTRIBUICOES not in documento.corpo
    assert documento.versoes.count() == 0


def test_sem_documento_nenhum_nao_estoura(db):
    Documento.objects.filter(nome=NOME).delete()

    _atualizar()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_atualizar_duas_vezes_e_seguro(documento_da_rodada_1):
    """A segunda chamada encontra o corpo já atualizado (diverge do congelado
    da rodada 1) e não cria uma segunda versão nem duplica o texto."""
    documento = documento_da_rodada_1

    _atualizar()
    _atualizar()

    documento.refresh_from_db()
    assert documento.versoes.count() == 1
    assert documento.corpo.count(CONTRIBUICOES) == 1
