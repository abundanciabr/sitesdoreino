"""A resposta da equipe numa ideia implementada (pedido do mantenedor, 29/09/2026).

Uma coluna nova em `Sugestao`, com `""` como "a equipe não escreveu resposta":
nenhuma linha existente muda de significado com esta migração.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("sugestoes", "0014_a_fase_anda_sem_assinatura")]

    operations = [
        migrations.AddField(
            model_name="sugestao",
            name="resposta_da_equipe",
            field=models.TextField(blank=True, default=""),
        ),
    ]
