"""Testes da semeadura privada da Comunidade Meshcraft.

**Por que este arquivo fabrica o estado de produção.** No banco de teste a
`0003` semeia a pasta inteira, inclusive a Comunidade, e a `0030` não encontraria
o que inserir. Verde de banco novo é cego para banco antigo (`armadilhas/253`),
e banco antigo é o único que existe em produção: lá a `0003` rodou em 31/08 sem
este arquivo. Cada teste abaixo começa reconstruindo o estado que a migração vai
encontrar de verdade, e só então chama a função dela.

"""

import importlib

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_semeadura = importlib.import_module("apps.core.migrations.0030_semear_a_comunidade")

NOME = "comunidade"
TITULO = "A Comunidade Meshcraft: o que é, o que fazer agora e como pedir ajuda"


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com o modelo de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semear():
    _semeadura.semear_a_comunidade(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_da_comunidade(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


def test_a_comunidade_entra_privada_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_da_comunidade,
):
    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.titulo == TITULO


def test_visitante_nao_le_a_comunidade_nem_a_encontra_na_lista_publica(
    banco_de_producao_antes_da_comunidade,
):
    _semear()

    pagina = Client().get(f"/docs/{NOME}")
    assert pagina.status_code == 404
    assert TITULO not in Client().get("/docs/").content.decode()


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_da_comunidade,
):
    """Se ele criou ou editou o documento pela tela, a semeadura não encosta."""
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=False
    )

    _semear()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is False


def test_semeia_so_a_comunidade_e_nao_a_pasta_inteira(
    banco_de_producao_antes_da_comunidade,
):
    """A pasta inteira é da `0003`, que roda uma vez por desenho. Esta migração
    não pode virar uma segunda passagem por ela."""
    Documento.objects.filter(nome="jornada-do-aluno").delete()

    _semear()

    assert Documento.objects.filter(nome=NOME).exists()
    assert not Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_da_comunidade, monkeypatch, tmp_path
):
    """Falhar aqui deixaria a célula em crashloop no `migrate` por um passo de
    conteúdo. A página ausente é visível; a célula fora do ar leva o site junto."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _semear()

    assert not Documento.objects.filter(nome=NOME).exists()


def test_semear_duas_vezes_e_igual_a_semear_uma(banco_de_producao_antes_da_comunidade):
    _semear()
    _semear()

    assert Documento.objects.filter(nome=NOME).count() == 1
