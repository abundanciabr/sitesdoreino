from django.db import migrations
from django.db.models import F


def liberar_reservas(apps, schema_editor):
    Pedido = apps.get_model('encomendas', 'PedidoMarketplace')
    Pedido.objects.using(schema_editor.connection.alias).filter(
        status='aguardando_pagamento', ambiente='production',
        producao_iniciada_em__isnull=True, aluno__isnull=True,
        fila_cliente__cliente__ativo=True,
        fila_cliente__cliente__site_id=F('site_id'),
        fila_cliente__reservado_cents=F('valor_cents'), valor_cents__gt=0,
    ).update(status='na_fila')


class Migration(migrations.Migration):
    dependencies = [('encomendas', '0023_saque_manual_fila')]
    operations = [migrations.RunPython(liberar_reservas, migrations.RunPython.noop)]
