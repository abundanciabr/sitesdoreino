from django.db import migrations

from apps.encomendas.faixas_carga import carregar


def frente(apps, schema_editor):
    m = apps.get_model
    carregar(m("encomendas", "ParticipacaoSandbox"), m("encomendas", "AcordoMarketplace"),
             m("encomendas", "RecebivelMarketplace"), m("encomendas", "EventoMarketplace"),
             m("encomendas", "OutboxMarketplace"))


class Migration(migrations.Migration):
    dependencies = [("encomendas", "0025_analise_e_cliente_sandbox")]
    operations = [migrations.RunPython(frente, migrations.RunPython.noop)]
