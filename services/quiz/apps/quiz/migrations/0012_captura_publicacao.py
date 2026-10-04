from django.db import migrations, models


def marcar_ja_publicadas(apps, schema_editor):
    """As capturas que já existem saíram na hora, pelo código anterior.

    Sem isto a tarefa as publicaria uma segunda vez com o mesmo `captura_id`.
    """
    CapturaParcial = apps.get_model("quiz", "CapturaParcial")
    CapturaParcial.objects.filter(publicada_em__isnull=True).update(
        publicada_em=models.F("criada_em"), publicacoes=1
    )


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0011_captura_parcial'),
    ]

    operations = [
        migrations.AddField(
            model_name='capturaparcial',
            name='publicada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='capturaparcial',
            name='publicacoes',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name='capturaparcial',
            index=models.Index(condition=models.Q(('publicada_em__isnull', True), ('submissao__isnull', True)), fields=['atualizada_em'], name='captura_a_publicar'),
        ),
        migrations.RunPython(marcar_ja_publicadas, migrations.RunPython.noop),
    ]
