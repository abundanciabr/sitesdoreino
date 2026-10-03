from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_fato_pagamento_escopado_por_site")]

    operations = [
        migrations.CreateModel(
            name="ReversaoDePagamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=100)),
                ("order_id", models.CharField(max_length=200)),
                ("event_id", models.UUIDField()),
                ("payload", models.JSONField()),
                ("registrada_na_timeline", models.BooleanField(default=False)),
            ],
        ),
        migrations.AddConstraint(
            model_name="reversaodepagamento",
            constraint=models.UniqueConstraint(
                fields=["site_id", "order_id"], name="uniq_reversao_site_pedido"
            ),
        ),
    ]
