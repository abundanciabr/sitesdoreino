from decimal import Decimal

from django.db import migrations


SLUGS = ['prop-espada', 'fuzil-assalto', 'pistola-estilizada', 'mascote-3d',
         'pet-fantasia', 'cabelo-curto', 'cabelo-longo', 'bone-estilizado',
         'chapeu-fantasia', 'personagem-conceito', 'personagem-robo']


def configurar(apps, schema_editor):
    projeto = apps.get_model('encomendas', 'ProjetoSandbox')
    projeto.objects.using(schema_editor.connection.alias).filter(slug__in=SLUGS).update(
        recompensa=Decimal('10000.00'))


class Migration(migrations.Migration):
    dependencies = [('encomendas', '0019_merge_pratica_carteira')]
    operations = [migrations.RunPython(configurar, migrations.RunPython.noop)]
