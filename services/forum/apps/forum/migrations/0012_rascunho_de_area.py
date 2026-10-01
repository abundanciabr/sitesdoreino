from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forum", "0011_rastro_da_area")]

    operations = [
        migrations.CreateModel(
            name="RascunhoDeArea",
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
                ("slug", models.SlugField(max_length=60, unique=True)),
                ("dados", models.JSONField()),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("publicado_em", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
