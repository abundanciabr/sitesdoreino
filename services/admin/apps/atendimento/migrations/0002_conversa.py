from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('atendimento', '0001_initial')]
    operations = [
        migrations.AddField(model_name='conversa', name='solicitou_pessoa', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='assunto', name='modo', field=models.CharField(max_length=20, default='assistido', choices=[('assistido', 'Assistido'), ('base', 'Automático pela base'), ('encaminhamento', 'Automático com encaminhamento'), ('conversa', 'Assistente que conversa e resolve')])),
    ]
