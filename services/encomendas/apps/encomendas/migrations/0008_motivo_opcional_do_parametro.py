from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("encomendas", "0007_remover_pista"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="parametro",
            name="mudanca_de_parametro_tem_motivo_escrito",
        ),
        migrations.AlterField(
            model_name="parametro",
            name="motivo",
            field=models.TextField(blank=True),
        ),
    ]
