from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0038_o_que_o_objetivo_move")]

    operations = [
        migrations.CreateModel(
            name="RascunhoDeConfiguracao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(max_length=24)),
                ("site_id", models.CharField(blank=True, default="", max_length=64)),
                ("alvo", models.CharField(max_length=120)),
                ("conteudo", models.JSONField(default=dict)),
                ("base", models.JSONField(default=dict)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("tipo", "site_id", "alvo"), name="um_rascunho_por_configuracao")]
            },
        ),
    ]
