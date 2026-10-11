from django.db import migrations, models
import django.db.models.deletion



class Migration(migrations.Migration):
    dependencies = [("gamificacao", "0018_reinicio_faixas_20261011")]

    operations = [
        migrations.CreateModel(
            name="AvaliacaoSandboxProjetada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("trabalho_id", models.CharField(max_length=64)),
                ("entrega_id", models.CharField(blank=True, default="", max_length=64)),
                ("analise_id", models.CharField(blank=True, default="", max_length=64)),
                ("event_id", models.CharField(max_length=64)),
                ("versao", models.PositiveIntegerField()),
                ("entrega_criada_em", models.DateTimeField()),
                ("origem_atualizada_em", models.DateTimeField()),
                ("ocorrido_em", models.DateTimeField()),
                ("atual", models.BooleanField(default=False)),
                ("estado", models.CharField(max_length=20)),
                ("resultado", models.CharField(blank=True, default="", max_length=24)),
                ("explicacao", models.TextField(blank=True, default="")),
                ("justificativa", models.TextField(blank=True, default="")),
                ("proxima_acao", models.TextField(blank=True, default="")),
                ("url", models.CharField(blank=True, default="", max_length=500)),
                ("historico", models.BooleanField(default=False)),
                ("anterior_reinicio", models.BooleanField(default=False)),
                ("reconhecida_em", models.DateTimeField(blank=True, null=True)),
                ("reconhecida_versao", models.PositiveIntegerField(blank=True, null=True)),
                ("reconhecida_entrega_id", models.CharField(blank=True, default="", max_length=64)),
                ("reconhecida_analise_id", models.CharField(blank=True, default="", max_length=64)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                ("pessoa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="gamificacao.pessoa")),
            ],
            options={
                "indexes": [models.Index(fields=["pessoa", "site_id"], name="gamificacao_pessoa__4a020e_idx")],
                "constraints": [models.UniqueConstraint(fields=("pessoa", "site_id", "trabalho_id"), name="uma_avaliacao_sandbox_por_trabalho")],
            },
        ),
    ]
