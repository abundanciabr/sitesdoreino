"""O manual do quiz volta a ficar disponível no site público.

O mantenedor pediu acesso ao manual em 22/09/2026. O texto continua sendo o
mesmo documento do banco; esta migração só reabre a publicação que a `0022`
fechou para administradores.
"""

from django.db import migrations


NOME = "o-crivo-explicado-do-zero"


def publicar_o_crivo(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    if not documento.publico:
        documento.publico = True
        documento.save(update_fields=["publico"])


def despublicar_o_crivo(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=NOME).first()
    if documento is None:
        return
    if documento.publico:
        documento.publico = False
        documento.save(update_fields=["publico"])


class Migration(migrations.Migration):
    dependencies = [("core", "0022_midia")]
    operations = [migrations.RunPython(publicar_o_crivo, despublicar_o_crivo)]
