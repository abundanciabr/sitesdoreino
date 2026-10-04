from django.db import migrations


class Migration(migrations.Migration):
    """O nome da tabela vem escrito no modelo, igual ao que o banco já tem."""

    dependencies = [("comercial", "0002_experimento_de_estrategia")]

    operations = [
        migrations.AlterModelTable(
            name="experimentoestrategia",
            table="comercial_experimentoestrategia",
        ),
    ]
