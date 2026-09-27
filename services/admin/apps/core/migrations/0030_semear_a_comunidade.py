"""A página da Comunidade Meshcraft entra no banco que JÁ EXISTE em produção.

`documentos/comunidade.md` nasceu em 27/09/2026 como a primeira entrega da
Comunidade Meshcraft (`docs/comunidade/DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md`
§3, §16; handoff §6): a página que diz ao membro o propósito, o que fazer
agora, como pedir ajuda, quem avalia, as regras e o que acontece quando a
matrícula termina. Nasce pública, sem nome de membro e sem condição comercial
inventada: o acesso é o da matrícula vigente. A partir daqui quem tem a caneta é
o mantenedor, pela tela `/admin/documentos/`, sem PR.

A pasta `documentos/` é SEMENTE e a migração `0003` rodou uma vez, em
31/08/2026: um arquivo novo não vira página sozinho (`armadilhas/347`). Por isso
este documento entra pela mesma porta dos anteriores (`0007`, `0011`, `0028`):
`semear_documento`, que semeia SÓ ele, nunca sobrescreve o que o mantenedor já
tenha escrito pela tela, e sem a pasta na imagem não faz nada.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "comunidade"


def semear_a_comunidade(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento: o texto pode já ter edições dele pela tela."""


class Migration(migrations.Migration):
    dependencies = [("core", "0029_publicar_o_manual_de_experimentacao")]
    operations = [migrations.RunPython(semear_a_comunidade, nao_apaga)]
