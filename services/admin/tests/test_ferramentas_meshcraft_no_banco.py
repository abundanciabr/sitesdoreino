"""As ferramentas do projeto Meshcraft chegam ao banco que JÁ EXISTE em produção.

Guarda de `0009_semear_as_ferramentas_do_projeto_meshcraft.py` e de
`documentos.semear_documento` (o mesmo mecanismo de
`test_relatorio_da_fundacao_no_banco.py`, e a mesma razão: no banco de teste a
`0003` semeia a pasta inteira, inclusive este arquivo, e a `0009` não
encontraria o que inserir. Em produção a `0003` rodou muito antes de este
documento existir, e é o cenário que este teste fabrica.
"""

import importlib

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0009_semear_as_ferramentas_do_projeto_meshcraft"
)

NOME = "ferramentas-do-projeto-meshcraft"


class _AppsFalso:
    """O `apps` que a migração recebe do Django, com o modelo de hoje."""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _correr():
    _migracao.semear_as_ferramentas(_AppsFalso, None)


@pytest.fixture
def banco_de_producao_antes_do_documento(db):
    """O banco em que a `0003` rodou antes de o arquivo existir: sem a linha."""
    Documento.objects.filter(nome=NOME).delete()


def test_o_documento_entra_no_banco_que_ja_foi_semeado(
    banco_de_producao_antes_do_documento,
):
    _correr()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.titulo == "As ferramentas do projeto Meshcraft"
    assert "78 ferramentas" in documento.corpo


def test_a_pagina_publica_da_404_e_a_porta_le(banco_de_producao_antes_do_documento):
    """Nasce fechado, como a parte 1: de fora é 404, quem passa pela porta lê."""
    _correr()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    assert NOME not in Client().get("/docs/").content.decode()


def test_nao_sobrescreve_o_que_o_mantenedor_ja_escreveu(
    banco_de_producao_antes_do_documento,
):
    Documento.objects.create(
        nome=NOME, titulo="Editado pelo dono", corpo="texto dele", publico=True
    )

    _correr()

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Editado pelo dono"
    assert documento.corpo == "texto dele"
    assert documento.publico is True


def test_semear_duas_vezes_nao_duplica(banco_de_producao_antes_do_documento):
    _correr()
    _correr()

    assert Documento.objects.filter(nome=NOME).count() == 1


def test_sem_a_pasta_na_imagem_nao_estoura(
    banco_de_producao_antes_do_documento, monkeypatch, tmp_path
):
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))

    _correr()

    assert not Documento.objects.filter(nome=NOME).exists()
