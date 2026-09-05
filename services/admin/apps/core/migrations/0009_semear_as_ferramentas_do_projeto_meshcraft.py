"""As ferramentas do projeto Meshcraft entram no banco que JÁ EXISTE em produção.

`documentos/ferramentas-do-projeto-meshcraft.md` nasceu em 05/09/2026, a pedido
do mantenedor: a parte 2 do painel que ele está montando para quem o contratou
(a parte 1 é o relatório da fundação) — o catálogo das 78 ferramentas que o
projeto Meshcraft vai construir para os alunos do próximo curso. A pasta
`documentos/` é SEMENTE (`DECISAO-o-editor-de-documentos.md`), e a semeadura de
toda a pasta é a migração `0003`, que já rodou em produção antes de este
arquivo existir: sem migração própria, o documento nasceria só no repositório e
`meshcraft.top/docs/…` (ou a tela do admin) nunca o encontraria
(`armadilhas/347`).

Nasce PRIVADO (`publico: false` no cabeçalho do arquivo), pelo mesmo motivo da
parte 1: o mantenedor decidiu manter o controle de quem vê o material antes de
distribuí-lo. Fecha sozinho a mesma dúvida que a `armadilhas/347` já resolveu
para o relatório da fundação: documento novo em `documentos/` pede migração
própria, sempre, pública ou não.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "ferramentas-do-projeto-meshcraft"


def semear_as_ferramentas(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento, e a omissão é a decisão (molde da `0007`)."""


class Migration(migrations.Migration):
    dependencies = [("core", "0008_o_relatorio_da_fundacao_so_para_administradores")]
    operations = [migrations.RunPython(semear_as_ferramentas, nao_apaga)]
