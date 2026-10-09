from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jornadas", "0005_jornada_da_oportunidade")]

    operations = [
        migrations.AddField("jornada", "central_nome", models.CharField(max_length=160, blank=True, default="")),
        migrations.AddField("jornada", "central_objetivo", models.TextField(blank=True, default="")),
        migrations.AddField("jornada", "central_entrada_aberta", models.BooleanField(default=False)),
        migrations.AddField("jornada", "central_pausada", models.BooleanField(default=False)),
        migrations.AddField("jornadaversao", "central_config", models.JSONField(default=dict, blank=True)),
        migrations.AddField("passo", "central_interacao", models.CharField(max_length=16, blank=True, default="")),
        migrations.AddField("passo", "central_modelo_whatsapp", models.JSONField(default=dict, blank=True)),
        migrations.AddField("inscricao", "central_suspensa", models.BooleanField(default=False)),
        migrations.AddField("inscricao", "central_conversa_id", models.UUIDField(null=True, blank=True, db_index=True)),
        migrations.AddField("inscricao", "central_contexto", models.JSONField(default=dict, blank=True)),
    ]
