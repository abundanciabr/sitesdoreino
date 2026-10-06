from django.db import migrations, models

PROJETOS = [('pistola-estilizada',
  'Pistola estilizada',
  'espadas_objetos',
  'Modele uma pistola estilizada como objeto digital para um jogo. Trabalhe a silhueta, as '
  'proporções visuais e os materiais, apresentando o modelo em vistas estáticas.',
  ['Pistolas estilizadas de jogos', 'Estudos de silhueta e materiais low poly'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévias frontal e lateral'],
  'Silhueta reconhecível; topologia econômica; UV organizada; materiais legíveis; fonte editável.'),
 ('fuzil-assalto',
  'Fuzil de assalto estilizado',
  'espadas_objetos',
  'Crie um fuzil de assalto estilizado como objeto digital para um jogo. Mantenha leitura clara da '
  'silhueta e contraste entre materiais, com apresentação estática.',
  ['Fuzis estilizados de jogos', 'Estudos de proporções visuais e materiais'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévias frontal e lateral'],
  'Proporções visuais coerentes; silhueta clara; malha organizada; UV sem falhas; materiais '
  'distinguíveis.')]

def substituir(apps, schema_editor):
    Projeto = apps.get_model('encomendas', 'ProjetoSandbox')
    db = schema_editor.connection.alias
    sites = set(Projeto.objects.using(db).values_list('site_id', flat=True))
    Projeto.objects.using(db).filter(slug__in=['bau-aventura', 'escudo-runico']).update(ativo=False)
    for site in sites:
        for slug, titulo, categoria, briefing, referencias, entregaveis, criterios in PROJETOS:
            Projeto.objects.using(db).get_or_create(site_id=site, slug=slug, defaults=dict(
                titulo=titulo, categoria=categoria, briefing=briefing, referencias=referencias,
                entregaveis=entregaveis, criterios=criterios))

class Migration(migrations.Migration):
    dependencies = [('encomendas', '0014_categorias_sandbox')]
    operations = [
        migrations.AlterField(model_name='projetosandbox', name='categoria', field=models.CharField(
            max_length=24, blank=True, default='', choices=[('espadas_objetos','Espadas e armas'),
            ('pets','Pets'),('cabelos','Cabelos'),('chapeus','Chapéus'),('personagens','Personagens')])),
        migrations.RunPython(substituir, migrations.RunPython.noop),
    ]
