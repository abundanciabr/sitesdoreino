import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0004_contexto_do_quiz"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="oportunidade_ref",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="oferta_ref",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="order",
            name="pago_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["site_id", "oportunidade_ref"], name="pedidos_ord_site_op_idx"
            ),
        ),
        migrations.CreateModel(
            name="LinkDeCompra",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("site_id", models.CharField(max_length=64)),
                ("chave_idempotencia", models.CharField(max_length=200)),
                ("pedido_id", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("oferta_ref", models.CharField(max_length=200)),
                ("oportunidade_ref", models.CharField(max_length=100)),
                ("contato", models.JSONField(blank=True, default=dict)),
                ("condicao", models.JSONField(default=dict)),
                ("resposta", models.JSONField(default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="link_de_compra",
                        to="pedidos.session",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["site_id", "oportunidade_ref"], name="pedidos_lin_site_op_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("site_id", "chave_idempotencia"),
                        name="link_compra_chave_unica_por_site",
                    )
                ],
            },
        ),
    ]
