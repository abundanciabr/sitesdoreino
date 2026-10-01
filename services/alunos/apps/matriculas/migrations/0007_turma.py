from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("matriculas", "0006_pagamento_and_more")]
    operations = [
        migrations.CreateModel(
            name="Turma",
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
                ("site_id", models.CharField(max_length=64)),
                ("slug", models.SlugField(max_length=120)),
                ("nome", models.CharField(blank=True, default="", max_length=120)),
                ("descricao", models.TextField(blank=True, default="")),
                ("published", models.BooleanField(default=False)),
                ("draft", models.JSONField(blank=True, null=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("site_id", "slug"), name="turma_site_slug_unico"
                    )
                ]
            },
        ),
    ]
