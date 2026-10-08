from django.db import migrations


def restaurar(apps, schema_editor):
    Participacao = apps.get_model("quiz", "NPSParticipacao")
    Participacao.objects.using(schema_editor.connection.alias).filter(
        segmento__in=("neutro", "promotor"),
        conquistas_privadas_ate__isnull=False,
    ).update(conquistas_privadas_ate=None)


class Migration(migrations.Migration):
    dependencies = [("quiz", "0018_nps_participacao")]
    operations = [migrations.RunPython(restaurar, migrations.RunPython.noop)]
