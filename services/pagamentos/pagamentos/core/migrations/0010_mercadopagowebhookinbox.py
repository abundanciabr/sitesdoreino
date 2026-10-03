from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0009_roteamento_pagamentos")]

    operations = [
        migrations.CreateModel(
            name="MercadoPagoWebhookInbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("topic", models.CharField(max_length=64)),
                ("resource_id_hash", models.CharField(max_length=64)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("topic", "resource_id_hash"), name="mp_aviso_futuro_unico"
                    )
                ]
            },
        )
    ]
