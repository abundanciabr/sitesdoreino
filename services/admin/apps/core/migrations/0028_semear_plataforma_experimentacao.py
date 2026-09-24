"""O manual da plataforma de experimentação entra no banco existente.

`documentos/plataforma-experimentacao-e-aprendizado-de-conversao.md` nasceu
como manual publicado. A pasta `documentos/` é semente: arquivo novo não vira
documento no site sem migração própria. Esta migração semeia só este manual e
preserva qualquer edição feita pela tela.
"""

from django.db import migrations

from apps.core.documentos import semear_documento


NOME = "plataforma-experimentacao-e-aprendizado-de-conversao"


def semear_manual(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer não apaga texto que pode ter sido editado no site."""


class Migration(migrations.Migration):
    dependencies = [("core", "0027_publicar_anexos_da_semente")]
    operations = [migrations.RunPython(semear_manual, nao_apaga)]
