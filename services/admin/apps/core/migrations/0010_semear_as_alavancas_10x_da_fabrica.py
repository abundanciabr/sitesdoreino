"""As alavancas de 10x da fábrica entram no banco que JÁ EXISTE em produção.

`documentos/alavancas-10x-da-fabrica.md` nasceu em 05/09/2026, a pedido do
mantenedor ("o que pode ser feito nesse projeto que aumentaria em 10x ou mais a
velocidade de execução das tarefas"). Pela lei de 05/09/2026
(`DECISAO-onde-mora-o-que-eu-entrego.md`), análise que ele vai reler mora no
site, e como não se apoia em fatos vivos do sistema, mora no editor de
documentos, só para administradores.

A pasta `documentos/` é SEMENTE e a migração `0003` rodou uma vez, em
31/08/2026: um arquivo novo não vira página sozinho (`armadilhas/347`). Por isso
este documento entra pela mesma porta do relatório da fundação (`0007`):
`semear_documento`, que semeia SÓ ele, nunca sobrescreve o que o mantenedor já
tenha escrito pela tela, e sem a pasta na imagem não faz nada.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "alavancas-10x-da-fabrica"


def semear_as_alavancas(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0009_semear_as_ferramentas_do_projeto_meshcraft")]
    operations = [migrations.RunPython(semear_as_alavancas, nao_apaga)]
