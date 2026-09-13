from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("cursos", "0008_varios_cursos")]

    operations = [
        migrations.CreateModel(
            name="AulaAvulsa",
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
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("titulo", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140)),
                ("video_url", models.URLField(max_length=500)),
                ("descricao", models.TextField(blank=True, default="")),
                (
                    "estado",
                    models.CharField(
                        choices=[("publicada", "Publicada")],
                        default="publicada",
                        max_length=10,
                    ),
                ),
                (
                    "publicada_em",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
            ],
            options={"ordering": ["-publicada_em", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="aulaavulsa",
            constraint=models.UniqueConstraint(
                fields=("site_id", "slug"), name="uma_aula_avulsa_por_slug_por_site"
            ),
        ),
        migrations.AddConstraint(
            model_name="aulaavulsa",
            constraint=models.CheckConstraint(
                condition=models.Q(("estado", "publicada")),
                name="aula_avulsa_nasce_publicada",
            ),
        ),
    ]
