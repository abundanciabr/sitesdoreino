from django.db import migrations, models

PROJETOS = [('prop-espada',
  'Espada estilizada',
  'espadas_objetos',
  'Modele uma espada de fantasia para um jogo, com lâmina, guarda e cabo de silhuetas distintas. Prepare '
  'materiais e uma apresentação estática.',
  ['Espadas estilizadas low poly', 'Estudo de metal e detalhes do cabo'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia estática'],
  'Silhueta clara; topologia econômica; UV organizada; fonte editável.'),
 ('escudo-runico',
  'Escudo rúnico',
  'espadas_objetos',
  'Crie um escudo estilizado com emblema central e variação de materiais, mantendo leitura clara em tamanho '
  'pequeno.',
  ['Escudos medievais e símbolos geométricos', 'Referências de madeira e metal'],
  ['Fonte Blender', 'Modelo exportado', 'Prévia frontal e lateral'],
  'Emblema legível; espessura coerente; organização dos materiais.'),
 ('bau-aventura',
  'Baú de aventura',
  'espadas_objetos',
  'Construa um baú de tesouro fechado, com ferragens e detalhes que indiquem uso em um jogo de aventura.',
  ['Baús de madeira estilizados', 'Referências de fechaduras e ferragens'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia'],
  'Escala consistente; formas bem definidas; materiais distinguíveis.'),
 ('mascote-3d',
  'Mascote 3D da comunidade',
  'pets',
  'Modele um mascote animal simpático para a comunidade, com silhueta legível e expressão acolhedora.',
  ['Animais estilizados de formas simples', 'Paleta da escola'],
  ['Arquivo fonte 3D', 'Render frontal e lateral', 'Prévia estática'],
  'Silhueta clara; malha limpa; materiais consistentes; arquivos editáveis.'),
 ('pet-fantasia',
  'Pet de fantasia',
  'pets',
  'Crie um companheiro fantástico pequeno para jogo casual; expresse personalidade no rosto e em uma pose '
  'estática.',
  ['Pets de jogos casuais', 'Moodboard de criaturas fantásticas'],
  ['Modelo 3D', 'Texturas', 'Prévias estáticas'],
  'Personalidade reconhecível; proporções coerentes; texturas sem falhas.'),
 ('cabelo-curto',
  'Cabelo curto estilizado',
  'cabelos',
  'Modele um cabelo curto em mechas amplas para um avatar, com volume legível de frente, lado e costas.',
  ['Penteados curtos estilizados', 'Referência de proporções da cabeça'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias em três vistas'],
  'Mechas organizadas; silhueta consistente; encaixe demonstrado.'),
 ('cabelo-longo',
  'Cabelo longo em camadas',
  'cabelos',
  'Crie um penteado longo em camadas com mechas econômicas e desenho coerente em todas as vistas.',
  ['Penteados longos em camadas', 'Estudos de silhueta de cabelo'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias em três vistas'],
  'Volume equilibrado; camadas legíveis; malha sem interseções indevidas.'),
 ('bone-estilizado',
  'Boné estilizado',
  'chapeus',
  'Modele um boné com aba, costuras simplificadas e um emblema original. Apresente o encaixe em uma cabeça '
  'de referência.',
  ['Bonés de aba curva', 'Estudo de emblemas geométricos'],
  ['Fonte Blender', 'Modelo exportado', 'Texturas e prévia'],
  'Aba e copa proporcionais; emblema legível; encaixe demonstrado.'),
 ('chapeu-fantasia',
  'Chapéu de fantasia',
  'chapeus',
  'Construa um chapéu de mago com aba e copa expressivas, incluindo um detalhe ornamental original.',
  ['Chapéus de fantasia', 'Estudos de tecido estilizado'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias frontal e lateral'],
  'Silhueta original; ornamentação clara; materiais coerentes.'),
 ('personagem-conceito',
  'Conceito de personagem',
  'personagens',
  'Desenvolva um explorador original para um mundo de fantasia leve, em vistas estáticas consistentes.',
  ['Roupas de viagem', 'Estudos de silhueta'],
  ['Folha de silhuetas', 'Arte final', 'Paleta de cores'],
  'Design original; detalhes apoiam a história; vistas consistentes.'),
 ('personagem-robo',
  'Personagem robô explorador',
  'personagens',
  'Modele um robô explorador de formas simples com torso, membros e rosto expressivos. Entregue uma pose '
  'estática de apresentação.',
  ['Robôs estilizados', 'Estudos de proporção de personagens'],
  ['Fonte Blender', 'Modelo exportado', 'Prévias frontal e lateral'],
  'Proporções coerentes; peças organizadas; expressão e silhueta legíveis.')]

def organizar(apps, schema_editor):
    Projeto = apps.get_model('encomendas', 'ProjetoSandbox')
    db = schema_editor.connection.alias
    categorias = {p[0]: p[2] for p in PROJETOS}
    sites = set(Projeto.objects.using(db).values_list('site_id', flat=True))
    for projeto in Projeto.objects.using(db).all():
        if projeto.slug in categorias:
            projeto.categoria = categorias[projeto.slug]
            if projeto.slug == 'mascote-3d' and 'Prévia giratória' in projeto.entregaveis:
                projeto.entregaveis = ['Prévia estática' if x == 'Prévia giratória' else x for x in projeto.entregaveis]
            projeto.save(using=db, update_fields=['categoria', 'entregaveis'])
        else:
            Projeto.objects.using(db).filter(pk=projeto.pk).update(ativo=False)
    for site in sites:
        for slug, titulo, categoria, briefing, referencias, entregaveis, criterios in PROJETOS:
            Projeto.objects.using(db).get_or_create(site_id=site, slug=slug, defaults=dict(
                titulo=titulo, categoria=categoria, briefing=briefing, referencias=referencias,
                entregaveis=entregaveis, criterios=criterios))

class Migration(migrations.Migration):
    dependencies = [('encomendas', '0013_sandbox')]
    operations = [
        migrations.AddField(model_name='projetosandbox', name='categoria', field=models.CharField(
            max_length=24, blank=True, default='', choices=[('espadas_objetos','Espadas e objetos'),
            ('pets','Pets'),('cabelos','Cabelos'),('chapeus','Chapéus'),('personagens','Personagens')])),
        migrations.RunPython(organizar, migrations.RunPython.noop),
    ]
