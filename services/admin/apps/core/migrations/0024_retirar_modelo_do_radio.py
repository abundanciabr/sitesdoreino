"""Retira o modelo da aplicação sem apagar a tabela e suas mensagens históricas."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0022_midia")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="MensagemDoRadio")],
        ),
    ]
