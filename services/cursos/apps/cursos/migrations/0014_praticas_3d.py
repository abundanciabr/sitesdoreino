import uuid
from django.db import migrations, models
import django.db.models.deletion

def fk(to):
    return models.ForeignKey(to=to,on_delete=django.db.models.deletion.PROTECT)

class Migration(migrations.Migration):
    dependencies=[('cursos','0013_item_de_plano_de_producao')]
    operations=[
      migrations.CreateModel(name='Base3D',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('chave',models.SlugField(max_length=100)),('versao',models.PositiveIntegerField(default=1)),('dados',models.JSONField(default=dict))],options={'constraints':[models.UniqueConstraint(fields=['chave','versao'],name='base3d_versao_unica')]}),
      migrations.CreateModel(name='Atividade3D',fields=[('id',models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),('aula',models.OneToOneField(to='cursos.aula',on_delete=django.db.models.deletion.PROTECT,related_name='atividade3d')),('grupo',models.SlugField(max_length=100)),('dia',models.PositiveSmallIntegerField(default=1)),('configuracao',models.JSONField(default=dict)),('ativa',models.BooleanField(default=True))]),
      migrations.CreateModel(name='Projeto3D',fields=[('id',models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),('pessoa',fk('cursos.Pessoa')),('curso',fk('cursos.Curso')),('base',fk('cursos.Base3D')),('grupo',models.SlugField(max_length=100)),('titulo',models.CharField(max_length=120,default='Meu item')),('receita',models.JSONField(default=dict)),('revisao',models.PositiveIntegerField(default=1)),('imagem',models.BinaryField()),('tamanho_imagem',models.PositiveIntegerField(default=0)),('atualizado_em',models.DateTimeField(auto_now=True))]),
      migrations.CreateModel(name='Tentativa3D',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('pessoa',fk('cursos.Pessoa')),('atividade',fk('cursos.Atividade3D')),('projeto',fk('cursos.Projeto3D')),('estado',models.JSONField(default=dict))],options={'constraints':[models.UniqueConstraint(fields=['pessoa','atividade'],name='tentativa3d_por_atividade')]}),
      migrations.CreateModel(name='Jornada3D',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('pessoa',fk('cursos.Pessoa')),('curso',fk('cursos.Curso')),('inicio',models.DateTimeField(null=True)),('legado',models.BooleanField(default=False))],options={'constraints':[models.UniqueConstraint(fields=['pessoa','curso'],name='jornada3d_por_curso')]}),
      migrations.CreateModel(name='Evento3D',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('pessoa',fk('cursos.Pessoa')),('atividade',fk('cursos.Atividade3D')),('tipo',models.CharField(max_length=40)),('etapa',models.PositiveSmallIntegerField(default=0)),('criado_em',models.DateTimeField(auto_now_add=True))]),
    ]
