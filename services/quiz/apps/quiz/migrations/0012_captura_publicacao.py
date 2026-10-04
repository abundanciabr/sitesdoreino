from django.db import migrations, models


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
    ]
