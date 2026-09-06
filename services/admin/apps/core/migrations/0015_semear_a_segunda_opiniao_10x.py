"""A segunda opinião de 10x entra no banco que JÁ EXISTE em produção.

`documentos/segunda-opiniao-10x-da-fabrica.md` nasceu em 06/09/2026, a pedido
do mantenedor ("quero uma segunda opinião de uma equipe de especialistas para
mais melhorias e otimizações de 10x"), no mesmo dia em que ele viu 47% da cota
semanal consumida em 36 horas. É a continuação de `0010` (as alavancas de
tempo) pela ótica do custo: cinco especialistas, cada um num ângulo que as duas
análises anteriores não mediram.

Mesma porta de `0007` e `0010`: `semear_documento` semeia SÓ ele, nunca
sobrescreve o que o mantenedor já tenha escrito pela tela, e sem a pasta na
imagem não faz nada (`armadilhas/347`).
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "segunda-opiniao-10x-da-fabrica"


def semear_a_segunda_opiniao(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0014_as_tres_leituras_dos_documentos")]
    operations = [migrations.RunPython(semear_a_segunda_opiniao, nao_apaga)]
