"""Reconcilia o nome legado da escola com o ID já usado pelos seus cursos."""
from django.db import migrations
from django.db.models import Q

SITE_LEGADO = 'Meshcraft'
SITE_CANONICO = 'cc06b8c3-043b-4c06-92c5-5ea624e00586'
PRODUTO_DA_PESQUISA = 'a88d13e0-2393-4fee-a1f7-0417634d9888'


def corrigir_identificador(apps, schema_editor):
    Matricula = apps.get_model('matriculas', 'Matricula')
    alias = schema_editor.connection.alias
    antigas = Matricula.objects.using(alias).filter(site_id=SITE_LEGADO, status='ativa')
    # A conferência do caso encontrou uma única conta neste cadastro legado,
    # com matrícula neste Desafio. Sem esse vínculo único, não corrige dados
    # de outra pessoa. O e-mail é lido no banco, nunca exposto no código/log.
    contas = list(antigas.filter(product_id=PRODUTO_DA_PESQUISA).values_list('email', flat=True).distinct()[:2])
    if not contas:
        return
    if len(contas) != 1:
        raise RuntimeError('Vínculo legado da pesquisa ambíguo: correção não aplicada.')
    legadas = antigas.filter(email=contas[0])
    ids = list(legadas.select_for_update().values_list('id', flat=True))
    if not ids:
        return
    # Uma referência financeira tem o site como parte de sua chave. Este
    # reparo de cadastros legados não desloca esse vínculo nem o seu estorno.
    if legadas.filter(~Q(provider='') | ~Q(provider_reference_id='')).exists():
        raise RuntimeError('Matrícula legada com vínculo financeiro: correção de escola não aplicada.')
    # Não cria matrícula, não libera curso e não altera status ou histórico.
    Matricula.objects.using(alias).filter(id__in=ids).update(site_id=SITE_CANONICO)


class Migration(migrations.Migration):
    dependencies = [('matriculas', '0009_origem_da_nova_venda')]
    # A volta do código não desfaz uma correção de dados. O publicador mantém
    # o backup anterior; o banco nunca é restaurado automaticamente.
    operations = [migrations.RunPython(corrigir_identificador, migrations.RunPython.noop)]
