from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0007_sessao_reaberta_e_pedido_de_teste'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='encerrado_motivo',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
    ]
