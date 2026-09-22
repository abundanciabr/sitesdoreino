"""Guarda o manual do quiz fora da área pública."""

import importlib

from django.test import Client

from apps.core.models import Documento


_privacidade = importlib.import_module(
    "apps.core.migrations.0026_o_crivo_explicado_so_para_administradores"
)

NOME = "o-crivo-explicado-do-zero"


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def test_o_manual_fica_privado_sem_trocar_o_texto(db):
    documento = Documento.objects.get(nome=NOME)
    corpo_original = documento.corpo
    documento.publico = True
    documento.save(update_fields=["publico"])

    _privacidade.fechar_o_crivo(_AppsFalso, None)

    documento.refresh_from_db()
    assert documento.publico is False
    assert documento.corpo == corpo_original
    assert Client().get(f"/docs/{NOME}").status_code == 404


def test_fechar_o_manual_duas_vezes_preserva_o_documento(db):
    documento = Documento.objects.get(nome=NOME)
    documento.titulo = "Título editado pelo mantenedor"
    documento.corpo = "Texto editado pelo mantenedor"
    documento.publico = True
    documento.save(update_fields=["titulo", "corpo", "publico"])

    _privacidade.fechar_o_crivo(_AppsFalso, None)
    _privacidade.fechar_o_crivo(_AppsFalso, None)

    documento.refresh_from_db()
    assert documento.publico is False
    assert documento.titulo == "Título editado pelo mantenedor"
    assert documento.corpo == "Texto editado pelo mantenedor"


def test_fechar_o_manual_ausente_nao_cria_documento(db):
    Documento.objects.filter(nome=NOME).delete()

    _privacidade.fechar_o_crivo(_AppsFalso, None)

    assert not Documento.objects.filter(nome=NOME).exists()
