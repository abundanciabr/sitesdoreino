import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quiz", "0006_quizdraft")]

    operations = [
        migrations.CreateModel(
            name="PortfolioCatalog",
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
                ("version", models.PositiveIntegerField()),
                ("content", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_catalogs",
                        to="quiz.site",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PortfolioExploration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("aluno_id", models.CharField(db_index=True, max_length=64)),
                ("entrada", models.CharField(max_length=16)),
                ("etapa", models.CharField(default="interesses", max_length=32)),
                ("respostas", models.JSONField(default=dict)),
                ("versao", models.CharField(max_length=32)),
                ("catalogo_snapshot", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_explorations",
                        to="quiz.site",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="portfoliocatalog",
            constraint=models.UniqueConstraint(
                fields=("site", "version"), name="portfolio_catalog_site_version"
            ),
        ),
        migrations.AddIndex(
            model_name="portfolioexploration",
            index=models.Index(
                fields=["site", "aluno_id", "-created_at"], name="portfolio_aluno_atual"
            ),
        ),
    ]
