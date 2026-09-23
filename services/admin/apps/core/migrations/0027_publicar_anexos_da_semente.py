"""Publica anexos semeados antes de a tabela de mídia existir."""

from django.db import migrations


def publicar_anexos(apps, schema_editor):
    from apps.core import midia

    Documento = apps.get_model("core", "Documento")
    for documento in Documento.objects.filter(corpo__contains="anexo:").iterator():
        midia.aplicar_anexos_ao_documento(documento)


class Migration(migrations.Migration):
    dependencies = [("core", "0026_o_crivo_explicado_so_para_administradores")]
    operations = [migrations.RunPython(publicar_anexos, migrations.RunPython.noop)]
