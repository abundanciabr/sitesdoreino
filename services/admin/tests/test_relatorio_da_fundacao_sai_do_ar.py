"""O relatório da fundação sai do ar no banco que JÁ EXISTE em produção.

Guarda de `apps/core/migrations/0008_o_relatorio_da_fundacao_sai_do_ar.py`.

**Por que este arquivo fabrica o estado de produção.** Consertar a semente
(`documentos/relatorio-da-fundacao.md`, que voltou a `publico: false`) resolve
o banco NOVO e não encosta no que está no ar: semear é `get_or_create` e de
propósito não altera o que existe. Em produção a linha já está lá, com
`publico=True`, e a página respondia HTTP 200 com 42 KB para qualquer pessoa —
foi assim que o mantenedor a encontrou em 05/09/2026. É a `armadilhas/253`, e
por isso a migração existe: quem vira a chave no banco antigo é ela.

Cada teste começa PONDO a linha pública, que é o estado de produção, e só
então chama a função da migração de verdade.
"""

import importlib

import pytest
from django.test import Client

from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0008_o_relatorio_da_fundacao_sai_do_ar"
)

NOME = "relatorio-da-fundacao"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _correr():
    _migracao.tirar_do_ar(_AppsFalso, None)


@pytest.fixture
def o_banco_de_producao(db):
    """O estado real em 05/09/2026: a página no ar para o mundo."""
    Documento.objects.filter(nome=NOME).delete()
    return Documento.objects.create(
        nome=NOME,
        titulo="Relatório da fundação (setembro de 2026)",
        corpo="Os números, medidos em 5 de setembro de 2026.",
        publico=True,
    )


def test_a_pagina_sai_do_ar_no_banco_que_ja_estava_publicando(o_banco_de_producao):
    assert Client().get(f"/docs/{NOME}").status_code == 200, (
        "o cenário nasceu fraco: se a página já estivesse fora do ar antes da "
        "migração, este teste ficaria verde sem ela ter feito nada"
    )

    _correr()

    assert Client().get(f"/docs/{NOME}").status_code == 404
    o_banco_de_producao.refresh_from_db()
    assert o_banco_de_producao.publico is False


def test_o_texto_nao_e_destruido(o_banco_de_producao):
    """Ele pediu para tirar do mundo, não para apagar. O texto pode ter edições
    dele pela tela, e destruí-las para desfazer uma exposição seria trocar um
    problema por outro pior."""
    _correr()

    documento = Documento.objects.get(nome=NOME)
    assert documento.corpo == "Os números, medidos em 5 de setembro de 2026."
    assert documento.titulo == "Relatório da fundação (setembro de 2026)"


def test_rodar_duas_vezes_nao_muda_nada(o_banco_de_producao):
    _correr()
    _correr()

    assert Documento.objects.filter(nome=NOME, publico=False).count() == 1


def test_descer_NAO_republica(o_banco_de_producao):
    """Fail-closed. Uma reversão que devolvesse `publico=True` transformaria um
    `migrate` para trás numa reexposição silenciosa do documento."""
    _correr()

    _migracao.nao_republica(_AppsFalso, None)

    assert Documento.objects.get(nome=NOME).publico is False
    assert Client().get(f"/docs/{NOME}").status_code == 404


def test_nao_encosta_nos_outros_documentos(o_banco_de_producao):
    """A migração vira UMA chave. Um `update()` sem filtro despublicaria a área
    de documentos inteira, e ninguém notaria até faltar uma página."""
    outro, _ = Documento.objects.update_or_create(
        nome="um-documento-que-fica-no-ar",
        defaults={"titulo": "Fica", "corpo": "x", "publico": True},
    )

    _correr()

    outro.refresh_from_db()
    assert outro.publico is True


def test_sem_a_linha_no_banco_nao_estoura(db):
    """Banco onde o documento nunca existiu: a migração passa sem fazer nada.
    Falhar aqui deixaria a célula em crashloop no `migrate` (a lição H18)."""
    Documento.objects.filter(nome=NOME).delete()

    _correr()

    assert not Documento.objects.filter(nome=NOME).exists()
