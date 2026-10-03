from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_appmaxwebhookinbox_redeliveries")]

    operations = [
        migrations.AddField(
            model_name="intent",
            name="segunda_opcao_ate",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="estorno_estado",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="paymentattempt",
            name="estorno_solicitado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="paymentattempt",
            name="state",
            field=models.CharField(
                choices=[
                    ("sending", "sending"),
                    ("pending", "pending"),
                    ("approved", "approved"),
                    ("rejected", "rejected"),
                    ("failed", "failed"),
                    ("reconciliation_required", "reconciliation_required"),
                    ("approved_duplicate", "approved_duplicate"),
                ],
                default="sending",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="paymentoperation",
            name="operation_type",
            field=models.CharField(
                choices=[
                    ("customer", "customer"),
                    ("order", "order"),
                    ("payment", "payment"),
                    ("refund", "refund"),
                ],
                max_length=16,
            ),
        ),
    ]
