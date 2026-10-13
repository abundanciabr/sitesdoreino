from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('atendimento', '0006_merge_escala_expediente')]
    operations = [migrations.AddField(
        model_name='conversa', name='arquivada_em',
        field=models.DateTimeField(null=True, blank=True, db_index=True),
    )]
