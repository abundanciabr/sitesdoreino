from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jornadas", "0003_silencio_da_devolucao")]

    operations = [
        migrations.AddField(
            model_name="entrega",
            name="whatsapp_intencao",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="entrega",
            name="whatsapp_verificado_em",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RemoveConstraint(
            model_name="entrega",
            name="entrega_com_resultado_conhecido",
        ),
        migrations.AlterField(
            model_name="entrega",
            name="resultado",
            field=models.CharField(
                max_length=48,
                choices=[
                    ("enviada", "enviada"),
                    ("pulada", "pulada"),
                    ("barrada_pela_regua", "barrada_pela_regua"),
                    ("barrada_por_preferencia", "barrada_por_preferencia"),
                    ("pendente", "pendente"),
                    ("aceita_pelo_gateway", "aceita_pelo_gateway"),
                    ("resultado_desconhecido", "resultado_desconhecido"),
                    ("falhou", "falhou"),
                    ("entregue", "entregue"),
                    ("lida", "lida"),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="entrega",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    resultado__in=(
                        "enviada",
                        "pulada",
                        "barrada_pela_regua",
                        "barrada_por_preferencia",
                        "pendente",
                        "aceita_pelo_gateway",
                        "resultado_desconhecido",
                        "falhou",
                        "entregue",
                        "lida",
                    )
                ),
                name="entrega_com_resultado_conhecido",
            ),
        ),
    ]
