from datetime import time
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('atendimento', '0004_interesse_e_agenda')]
    operations = [
        migrations.AddField(model_name='configuracao', name='expediente_ativo',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='configuracao', name='expediente_inicio',
                            field=models.TimeField(default=time(14))),
        migrations.AddField(model_name='configuracao', name='expediente_fim',
                            field=models.TimeField(default=time(18))),
    ]
