"""O plano da Central de Pendências entra no banco que JÁ EXISTE em produção.

`documentos/pendencias-e-conferencia-por-pares.md` nasceu em 06/09/2026, a
pedido do mantenedor, depois de ele abrir `meshcraft.top/conquistas/interno` e
descobrir uma fila que já era dele desde 01/09 (registro `20260901-009`).

Mesma porta de `0007`, `0010` e `0015`: `semear_documento` semeia SÓ ele, nunca
sobrescreve o que o mantenedor já tenha escrito pela tela, e sem a pasta na
imagem não faz nada (`armadilhas/347`).

Nasce PRIVADO, por ausência de `publico` no cabeçalho: é plano de bastidor, e a
pasta é fail-closed por desenho (`documentos/LEIA-ME.md`).
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "pendencias-e-conferencia-por-pares"


def semear_o_plano_das_pendencias(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0016_o_extrator_existe_e_o_gerador_foi_dissolvido")]
    operations = [migrations.RunPython(semear_o_plano_das_pendencias, nao_apaga)]
