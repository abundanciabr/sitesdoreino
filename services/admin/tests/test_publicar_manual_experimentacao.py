"""Guarda a publicação do manual de experimentação no site."""

import importlib

from django.test import Client

from apps.core.models import Documento


_semeadura = importlib.import_module(
    "apps.core.migrations.0028_semear_plataforma_experimentacao"
)

NOME = "plataforma-experimentacao-e-aprendizado-de-conversao"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def test_o_manual_entra_publico_no_banco_existente(db):
    Documento.objects.filter(nome=NOME).delete()

    _semeadura.semear_manual(_AppsFalso, None)

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is True
    assert documento.titulo == "Plataforma de Experimentação e Aprendizado de Conversão"
    assert "Assignment:" in documento.corpo
    assert Client().get(f"/docs/{NOME}").status_code == 200


def test_semear_duas_vezes_preserva_edicao_do_mantenedor(db):
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME,
        titulo="Título editado",
        corpo="Texto editado",
        publico=False,
    )

    _semeadura.semear_manual(_AppsFalso, None)
    _semeadura.semear_manual(_AppsFalso, None)

    documento = Documento.objects.get(nome=NOME)
    assert documento.titulo == "Título editado"
    assert documento.corpo == "Texto editado"
    assert documento.publico is False
