from django.db import migrations

from apps.cursos.faixas_carga import carregar


def frente(apps, schema_editor):
    carregar(apps.get_model("cursos", "Projeto3D"), apps.get_model("cursos", "OutboxEvent"))


class Migration(migrations.Migration):
    dependencies = [("cursos", "0014_praticas_3d")]
    operations = [migrations.RunPython(frente, migrations.RunPython.noop)]
