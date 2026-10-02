"""Permite registrar a autoria sem documento ou aprovação declarada.

A remoção das duas checagens não altera linhas existentes. O vínculo obrigatório
com `Identidade`, a unicidade por ideia e CHANGE-ID e o trigger append-only
continuam no banco.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sugestoes", "0015_resposta_da_equipe")]

    operations = [
        migrations.RemoveConstraint(
            model_name="changespecaprovado",
            name="changespec_tem_quem_aprovou",
        ),
        migrations.RemoveConstraint(
            model_name="changespecaprovado",
            name="changespec_tem_documento",
        ),
        migrations.AlterField(
            model_name="changespecaprovado",
            name="documento",
            field=models.CharField(max_length=300, blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="changespecaprovado",
            name="aprovado_por",
            field=models.CharField(max_length=120, blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="changespecaprovado",
            name="aprovado_em",
            field=models.DateField(null=True, blank=True),
        ),
    ]
