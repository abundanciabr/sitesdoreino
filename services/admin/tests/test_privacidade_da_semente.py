from importlib import import_module

import pytest
from django.apps import apps

from apps.auditoria.models import Registro
from apps.core.models import Documento, VersaoDoDocumento

MIGRACAO = import_module(
    "apps.core.migrations.0032_manter_o_manual_de_experimentacao_privado"
)
NOME = "plataforma-experimentacao-e-aprendizado-de-conversao"


@pytest.fixture
def documentos_vazios():
    Documento.objects.all().delete()


@pytest.mark.parametrize("arquivado", [False, True])
def test_compensacao_preserva_todos_os_campos_e_o_historico(
    documentos_vazios, arquivado
):
    documento = Documento.objects.create(
        nome=NOME,
        titulo="Título preservado",
        publico=True,
        arquivado=arquivado,
        ordem=17,
        corpo="Texto preservado pelo mantenedor.",
    )
    anterior = VersaoDoDocumento.objects.create(
        documento=documento,
        titulo=documento.titulo,
        publico=True,
        ordem=documento.ordem,
        corpo=documento.corpo,
        salvo_por="dono@exemplo.com",
        gesto="criou o documento",
    )
    antes = {
        campo.attname: getattr(documento, campo.attname)
        for campo in documento._meta.concrete_fields
        if campo.name != "publico"
    }
    registros = Registro.objects.count()

    MIGRACAO.fechar_semente(apps, None)
    MIGRACAO.fechar_semente(apps, None)
    MIGRACAO.nao_reabre(apps, None)

    documento.refresh_from_db()
    assert documento.publico is False
    assert all(getattr(documento, campo) == valor for campo, valor in antes.items())
    anterior.refresh_from_db()
    assert anterior.publico is True
    assert anterior.gesto == "criou o documento"
    assert documento.versoes.count() == 1
    assert Registro.objects.count() == registros


def test_compensacao_nao_muda_outros_documentos_nem_inventa_gesto(documentos_vazios):
    entrada = Documento.objects.create(nome="como-funciona-a-entrada", publico=True)
    outro = Documento.objects.create(nome="publicacao-autorizada", publico=True)
    privado = Documento.objects.create(nome=NOME, publico=False)

    MIGRACAO.fechar_semente(apps, None)

    entrada.refresh_from_db()
    outro.refresh_from_db()
    privado.refresh_from_db()
    assert entrada.publico is True
    assert outro.publico is True
    assert privado.publico is False
    assert not VersaoDoDocumento.objects.exists()
    assert not Registro.objects.exists()


def test_compensacao_nao_cria_documento_ausente(documentos_vazios):
    MIGRACAO.fechar_semente(apps, None)
    assert not Documento.objects.exists()


def test_todas_as_migracoes_de_instalacao_deixam_so_a_entrada_publica():
    assert list(
        Documento.objects.filter(publico=True).values_list("nome", flat=True)
    ) == ["como-funciona-a-entrada"]
    assert not VersaoDoDocumento.objects.exists()
    assert not Registro.objects.exists()
