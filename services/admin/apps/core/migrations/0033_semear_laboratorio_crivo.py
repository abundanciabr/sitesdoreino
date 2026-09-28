from django.db import migrations

from apps.core.documentos import semear_documento


def semear(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), "laboratorio-crivo")


class Migration(migrations.Migration):
    dependencies = [("core", "0032_semear_roadmap_da_comunidade")]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
