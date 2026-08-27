# Generated for the Fase 2 do sininho — Rito de Contrato de 26/08/2026.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sugestoes", "0006_id_da_plataforma")]

    operations = [
        migrations.AddField(
            model_name="outboxevent",
            name="envelope_extra",
            # `default=dict` e NOT NULL: as linhas que já existem passam a ter
            # `{}`, que o relay traduz em "envelope como sempre foi". Nenhuma
            # linha antiga muda de significado, e nenhum evento já publicado é
            # republicado por causa disto.
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
