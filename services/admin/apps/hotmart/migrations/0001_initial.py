from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='ConfiguracaoHotmart', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('hottok_sha256', models.CharField(max_length=64)),
            ('atualizado_em', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='EventoHotmart', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('evento_id', models.CharField(max_length=200, unique=True)),
            ('evento', models.CharField(max_length=100)),
            ('dados', models.JSONField()),
            ('recebido_em', models.DateTimeField(auto_now_add=True)),
            ('ultimo_recebimento', models.DateTimeField(auto_now_add=True)),
            ('recebimentos', models.PositiveIntegerField(default=1)),
        ]),
    ]
