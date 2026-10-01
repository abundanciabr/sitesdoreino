"""A segunda camada do painel da equipe: objetivos, compromissos da semana e
comentários. Só tabelas e um campo opcional; nenhuma linha semeada, porque
objetivo e compromisso são decisão da equipe, não da migração.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_o_painel_da_equipe"),
    ]

    operations = [
        migrations.CreateModel(
            name="Objetivo",
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
                ("titulo", models.CharField(max_length=200)),
                ("descricao", models.TextField(blank=True, default="")),
                ("prazo", models.DateField(blank=True, null=True)),
                ("ativo", models.BooleanField(default=True)),
                (
                    "criado_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-ativo", "prazo", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="Comentario",
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
                ("texto", models.CharField(max_length=500)),
                ("autor", models.CharField(blank=True, default="", max_length=200)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "tarefa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comentarios",
                        to="core.tarefa",
                    ),
                ),
            ],
            options={
                "ordering": ["criado_em", "id"],
            },
        ),
        migrations.AddField(
            model_name="tarefa",
            name="objetivo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tarefas",
                to="core.objetivo",
            ),
        ),
        migrations.CreateModel(
            name="Compromisso",
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
                ("semana", models.DateField()),
                (
                    "marcado_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("marcado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "tarefa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compromissos",
                        to="core.tarefa",
                    ),
                ),
            ],
            options={
                "ordering": ["semana", "marcado_em"],
                "indexes": [
                    models.Index(
                        fields=["semana"], name="core_compro_semana_2537f1_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tarefa", "semana"), name="um_compromisso_por_semana"
                    )
                ],
            },
        ),
    ]
