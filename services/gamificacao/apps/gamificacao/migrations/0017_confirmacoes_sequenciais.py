from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gamificacao', '0016_inicio_da_jornada')]

    operations = [
        migrations.AddField(
            model_name='jornadapessoal',
            name='confirmacoes_sequenciais',
            field=models.JSONField(default=dict, db_default={}, blank=True),
        ),
    ]
