import uuid
from django.db import migrations, models


def identificar_testes(apps, schema_editor):
    Entrega = apps.get_model('encomendas', 'EntregaSandbox')
    # Identificação expressa do mantenedor. Não deduz a autoria pelo nome do arquivo.
    Entrega.objects.using(schema_editor.connection.alias).filter(
        participacao_id='64a163d4-23aa-483d-a4c5-155f254225aa',
        versao__in=[2, 3, 4, 5, 6],
    ).update(teste_mantenedor=True)


def registrar_envio_original(apps, schema_editor):
    # Recupera o fato faltante com a data verdadeira, sem reabrir o reinício das faixas.
    db = schema_editor.connection.alias
    Entrega = apps.get_model('encomendas', 'EntregaSandbox')
    entrega = Entrega.objects.using(db).filter(
        participacao_id='64a163d4-23aa-483d-a4c5-155f254225aa', versao=1,
        teste_mantenedor=False).select_related('participacao').first()
    if entrega is None:
        return
    p = entrega.participacao
    evento = 'encomendas.sandbox-trabalho-concluido'
    Evento = apps.get_model('encomendas', 'EventoMarketplace')
    Outbox = apps.get_model('encomendas', 'OutboxMarketplace')
    fato, criado = Evento.objects.using(db).get_or_create(
        chave=f'faixas:{evento}:{p.pk}',
        defaults={'site_id': p.site_id, 'tipo': f'{evento}.v1', 'dados': {}})
    if criado:
        Outbox.objects.using(db).create(site_id=p.site_id, evento=fato, event=evento,
            version=1, event_id=uuid.uuid5(uuid.NAMESPACE_URL, f'meshcraft-faixas:{evento}:{p.pk}'),
            payload={'site_id': p.site_id, 'pessoa_id': str(p.pessoa_id),
                     'trabalho_id': str(p.pk), 'ocorrido_em': entrega.criada_em.isoformat()})


class Migration(migrations.Migration):
    dependencies = [('encomendas', '0029_devolutiva_trabalho_64a163d4')]
    operations = [
        migrations.AddField(model_name='entregasandbox', name='teste_mantenedor',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='analiseentregasandbox', name='historico',
                            field=models.JSONField(default=list)),
        migrations.RunPython(identificar_testes, migrations.RunPython.noop),
        migrations.RunPython(registrar_envio_original, migrations.RunPython.noop),
    ]
