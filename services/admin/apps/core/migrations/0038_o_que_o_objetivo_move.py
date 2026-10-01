"""O objetivo diz o que move no placar (01/10/2026).

Um campo opcional, vazio por padrão: nenhum objetivo existente passa a mover
nada sem que alguém escolha. Sem RunPython, sem linha semeada.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_acesso_da_equipe_por_aparelho"),
    ]

    operations = [
        migrations.AddField(
            model_name="objetivo",
            name="move",
            field=models.CharField(
                blank=True,
                choices=[
                    ("compras-no-ciclo", "A MCI nº 1, a meta grande do placar"),
                    (
                        "pedidos-de-entrada-por-semana",
                        "Medida de direção: chegadas à sala de espera",
                    ),
                    (
                        "liberacoes-em-48h",
                        "Medida de direção: confirmações em até 48 horas",
                    ),
                ],
                default="",
                max_length=80,
            ),
        ),
    ]
