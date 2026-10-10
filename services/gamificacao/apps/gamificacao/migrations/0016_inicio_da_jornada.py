from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gamificacao', '0015_anexo_da_jornada')]
    operations = [
        migrations.AddField(model_name='jornadapessoal', name='inicio', field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name='anexodajornada', name='aprendi', field=models.CharField(max_length=500, blank=True, default='')),
        migrations.AddField(model_name='anexodajornada', name='duvida', field=models.CharField(max_length=500, blank=True, default='')),
    ]
