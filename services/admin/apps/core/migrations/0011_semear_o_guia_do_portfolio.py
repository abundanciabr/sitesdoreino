"""O guia do portfólio entra no banco que JÁ EXISTE em produção.

`documentos/guia-do-portfolio.md` nasceu em 05/09/2026, no degrau 16 da escada
de `docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` (AC-18 do corredor
`docs/changespecs/CS-PAGES-0001.md`). O texto é o da professora da escola,
organizado com a voz da escola, e a partir daqui quem tem a caneta é o
mantenedor: ele edita o guia em `/admin/documentos/`, sem abrir PR.

A pasta `documentos/` é SEMENTE e a migração `0003` rodou uma vez, em
31/08/2026: um arquivo novo não vira página sozinho (`armadilhas/347`). Por isso
este documento entra pela mesma porta dos anteriores (`0007`, `0009`, `0010`):
`semear_documento`, que semeia SÓ ele, nunca sobrescreve o que o mantenedor já
tenha escrito pela tela, e sem a pasta na imagem não faz nada.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "guia-do-portfolio"


def semear_o_guia(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0010_semear_as_alavancas_10x_da_fabrica")]
    operations = [migrations.RunPython(semear_o_guia, nao_apaga)]
