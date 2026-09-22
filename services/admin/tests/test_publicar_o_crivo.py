"""Guarda a publicação do manual do quiz no site público."""

import importlib

from django.test import Client

from apps.core.models import Documento


_publicacao = importlib.import_module(
    "apps.core.migrations.0024_publicar_o_crivo_explicado"
)

NOME = "o-crivo-explicado-do-zero"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def test_o_manual_do_quiz_fica_publico_sem_trocar_o_texto(db):
    documento = Documento.objects.create(
        nome=NOME,
        titulo="O Crivo explicado do zero",
        publico=False,
        corpo="# Manual original\n",
    )

    _publicacao.publicar_o_crivo(_AppsFalso, None)

    documento.refresh_from_db()
    assert documento.publico is True
    assert documento.corpo == "# Manual original\n"
    assert Client().get(f"/docs/{NOME}").status_code == 200


def test_publicar_o_manual_duas_vezes_preserva_o_documento(db):
    documento = Documento.objects.create(
        nome=NOME,
        titulo="Título editado pelo mantenedor",
        publico=True,
        corpo="Texto editado pelo mantenedor",
    )

    _publicacao.publicar_o_crivo(_AppsFalso, None)
    _publicacao.publicar_o_crivo(_AppsFalso, None)

    documento.refresh_from_db()
    assert documento.publico is True
    assert documento.titulo == "Título editado pelo mantenedor"
    assert documento.corpo == "Texto editado pelo mantenedor"


def test_publicar_o_manual_ausente_nao_cria_documento(db):
    _publicacao.publicar_o_crivo(_AppsFalso, None)

    assert not Documento.objects.filter(nome=NOME).exists()
