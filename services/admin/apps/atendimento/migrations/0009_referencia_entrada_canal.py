from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('atendimento', '0008_canais_e_passos')]
    operations = [migrations.AddField('conversa', 'origem_ultima_mensagem', models.CharField(max_length=100, blank=True))]
