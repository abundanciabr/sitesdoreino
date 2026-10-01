import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0007_quem_assumiu_o_pedido")]

    operations = [
        migrations.CreateModel(
            name="ImagemDoPortfolio",
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
                ("bytes", models.BinaryField()),
                ("tamanho", models.PositiveIntegerField()),
                ("largura", models.PositiveIntegerField()),
                ("altura", models.PositiveIntegerField()),
                (
                    "peca",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imagem_enviada",
                        to="portfolio.peca",
                    ),
                ),
            ],
            options={
                "verbose_name": "imagem do portfólio",
                "verbose_name_plural": "imagens do portfólio",
            },
        ),
        migrations.AddConstraint(
            model_name="imagemdoportfolio",
            constraint=models.CheckConstraint(
                condition=models.Q(tamanho__gte=1), name="imagem_tem_bytes"
            ),
        ),
        migrations.AddConstraint(
            model_name="imagemdoportfolio",
            constraint=models.CheckConstraint(
                condition=models.Q(largura__gte=1), name="imagem_tem_largura"
            ),
        ),
        migrations.AddConstraint(
            model_name="imagemdoportfolio",
            constraint=models.CheckConstraint(
                condition=models.Q(altura__gte=1), name="imagem_tem_altura"
            ),
        ),
    ]
