"""Retira o modelo ativo; a tabela e as mensagens históricas permanecem."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0022_midia")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="MensagemDoRadio")],
        ),
    ]
