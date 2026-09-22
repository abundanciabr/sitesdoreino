"""O Crivo explicado do zero entra no banco que JÁ EXISTE em produção.

`documentos/o-crivo-explicado-do-zero.md` nasceu em 21/09/2026, a pedido do
mantenedor: uma página de documento para leigos e iniciantes, com figuras,
tabelas e histórias, ensinando o quiz da casa. A pasta `documentos/` é SEMENTE
e a migração `0003` rodou uma vez, em 31/08/2026: um arquivo novo não vira
página sozinho (`armadilhas/347`). Por isso este documento entra pela mesma
porta dos anteriores: `semear_documento`, que semeia SÓ ele, nunca sobrescreve
o que o mantenedor já tenha escrito pela tela, e sem a pasta na imagem não
faz nada.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "o-crivo-explicado-do-zero"


def semear_o_crivo(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0020_tipos_de_mensagem_do_radio")]
    operations = [migrations.RunPython(semear_o_crivo, nao_apaga)]
