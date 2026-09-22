"""O manual do quiz volta a ficar disponível apenas para administradores.

O mantenedor decidiu em 22/09/2026 que documentos criados no site devem nascer
privados. O texto permanece no banco; esta migração só fecha a publicação.
"""

from django.db import migrations


NOME = "o-crivo-explicado-do-zero"


def fechar_o_crivo(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    if documento.publico:
        documento.publico = False
        documento.save(update_fields=["publico"])


def nao_reabre(apps, schema_editor):
    """Um rollback não desfaz a decisão de privacidade do mantenedor."""


class Migration(migrations.Migration):
    dependencies = [("core", "0025_publicar_o_crivo_explicado")]
    operations = [migrations.RunPython(fechar_o_crivo, nao_reabre)]
