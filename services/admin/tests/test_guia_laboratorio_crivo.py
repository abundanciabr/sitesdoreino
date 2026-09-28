import importlib

import pytest
from django.apps import apps

from apps.core.models import Documento

pytestmark = pytest.mark.django_db


def test_o_guia_novo_chega_ao_banco_e_a_pagina_publica(client):
    Documento.objects.filter(nome="laboratorio-crivo").delete()
    migracao = importlib.import_module(
        "apps.core.migrations.0033_semear_laboratorio_crivo"
    )
    migracao.semear(apps, None)
    migracao.semear(apps, None)
    guia = Documento.objects.get(nome="laboratorio-crivo")
    assert guia.publico and not guia.arquivado
    assert "Experimento 10" in guia.corpo
    assert "Vínculo individual" in guia.corpo
    resposta = client.get("/docs/laboratorio-crivo", follow=True)
    assert resposta.status_code == 200
    assert "laboratorio-crivo/observacao/" in resposta.content.decode()
    guia.corpo = "Texto editado pelo mantenedor"
    guia.save()
    migracao.semear(apps, None)
    guia.refresh_from_db()
    assert guia.corpo == "Texto editado pelo mantenedor"
