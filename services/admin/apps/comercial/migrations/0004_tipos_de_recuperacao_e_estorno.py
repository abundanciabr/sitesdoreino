from django.db import migrations, models


class Migration(migrations.Migration):
    """Dois tipos de trabalho novos: recuperar a compra (recusa, Pix vencido)
    e registrar o estorno confirmado. Só muda a lista de escolhas."""

    dependencies = [("comercial", "0003_tabela_do_experimento")]

    operations = [
        migrations.AlterField(
            model_name="trabalhocomercial",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("analisar_lead", "Analisar o lead"),
                    ("abordar", "Abordar o lead"),
                    ("atender_mensagem", "Atender mensagem"),
                    ("acompanhar_pagamento", "Acompanhar pagamento"),
                    ("analisar_resultados", "Analisar resultados"),
                    ("recuperar_compra", "Recuperar compra"),
                    ("registrar_estorno", "Registrar estorno"),
                ],
                max_length=30,
            ),
        ),
    ]
