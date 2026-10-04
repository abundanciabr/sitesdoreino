from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0005_link_de_compra"),
    ]

    operations = [
        migrations.CreateModel(
            name="CondicaoDoAgente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=64)),
                ("oferta_slug", models.CharField(max_length=200)),
                ("condicao_id", models.CharField(max_length=80)),
                ("liberada_por", models.CharField(blank=True, default="", max_length=200)),
                ("liberada_em", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="condicaodoagente",
            constraint=models.UniqueConstraint(
                fields=("site_id", "oferta_slug", "condicao_id"),
                name="condicao_agente_unica_por_oferta",
            ),
        ),
    ]
