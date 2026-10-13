from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agentes', '0011_operacao_super_equipe')]
    operations = [migrations.AddField(model_name='rotinasuperequipe', name='entregas_operacionais',
                                     field=models.JSONField(default=dict))]
