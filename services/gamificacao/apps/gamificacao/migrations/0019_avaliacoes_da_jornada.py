from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("gamificacao", "0018_reinicio_faixas_20261011")]

    operations = [
        migrations.AddField(
            model_name="recebimentodeclarado", name="referencia_trabalho",
            field=models.CharField(blank=True, default="", max_length=280),
        ),
        migrations.CreateModel(
            name="AvaliacaoDaJornada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("ordem", models.PositiveSmallIntegerField()),
                ("caminho", models.CharField(max_length=20)),
                ("resultado", models.CharField(max_length=12)),
                ("feedback", models.TextField()),
                ("evidencia", models.JSONField(default=dict)),
                ("chave", models.CharField(max_length=64)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("pessoa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="gamificacao.pessoa")),
            ],
            options={
                "indexes": [models.Index(fields=["pessoa", "site_id", "ordem", "resultado"], name="gam_avaliacao_pessoa_ordem_idx")],
                "constraints": [models.UniqueConstraint(fields=["pessoa", "site_id", "ordem", "chave"], name="uma_avaliacao_por_tentativa")],
            },
        ),
    ]
