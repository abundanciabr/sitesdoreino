from django.db import migrations

from apps.encomendas.faixas_carga import carregar


def frente(apps, schema_editor):
    # `apps.get_model("encomendas", ...)` por extenso: a aplicação única só troca o
    # rótulo do app nessa forma (um apelido como `m = apps.get_model` escapa).
    carregar(apps.get_model("encomendas", "ParticipacaoSandbox"),
             apps.get_model("encomendas", "AcordoMarketplace"),
             apps.get_model("encomendas", "RecebivelMarketplace"),
             apps.get_model("encomendas", "EventoMarketplace"),
             apps.get_model("encomendas", "OutboxMarketplace"))


class Migration(migrations.Migration):
    dependencies = [("encomendas", "0025_analise_e_cliente_sandbox")]
    operations = [migrations.RunPython(frente, migrations.RunPython.noop)]
