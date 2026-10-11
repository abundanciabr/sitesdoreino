from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agentes", "0010_super_equipe_automatica")]
    operations = [
        migrations.AddField("rotinasuperequipe", "executor_consultado_em", models.DateTimeField(null=True)),
        migrations.AddField("rotinasuperequipe", "executor_local", models.CharField(max_length=30, blank=True, default="")),
        migrations.AddField("rotinasuperequipe", "operacao", models.JSONField(default=dict)),
        migrations.AddField("rotinasuperequipe", "fotografia", models.JSONField(default=dict)),
        migrations.AddField("melhoriasuperequipe", "desenvolvimento", models.JSONField(default=dict)),
    ]
