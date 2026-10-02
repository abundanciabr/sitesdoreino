import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quiz", "0009_integracoes")]

    operations = [
        migrations.CreateModel(
            name="PropostaDeVersao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("versao_base", models.SlugField(max_length=100)),
                ("gargalo", models.CharField(blank=True, default="", max_length=200)),
                ("hipotese", models.TextField()),
                (
                    "prioridade",
                    models.CharField(
                        choices=[("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")],
                        default="media",
                        max_length=8,
                    ),
                ),
                ("mudanca", models.TextField()),
                ("key_sugerida", models.SlugField(max_length=100)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("proposta", "Proposta"),
                            ("aceita", "Aceita"),
                            ("descartada", "Descartada"),
                            ("publicada", "Publicada"),
                            ("medida", "Medida"),
                        ],
                        default="proposta",
                        max_length=12,
                    ),
                ),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                ("aceita_em", models.DateTimeField(blank=True, null=True)),
                ("descartada_em", models.DateTimeField(blank=True, null=True)),
                ("publicada_em", models.DateTimeField(blank=True, null=True)),
                ("medida_em", models.DateTimeField(blank=True, null=True)),
                ("resultado_texto", models.TextField(blank=True, default="")),
                ("resultado_json", models.JSONField(blank=True, default=dict)),
                ("decisao_seguinte", models.TextField(blank=True, default="")),
                (
                    "quiz",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="propostas",
                        to="quiz.quiz",
                    ),
                ),
            ],
            options={
                "ordering": ["-criada_em", "-id"],
                "indexes": [
                    models.Index(fields=["quiz", "estado"], name="proposta_quiz_estado")
                ],
            },
        ),
    ]
