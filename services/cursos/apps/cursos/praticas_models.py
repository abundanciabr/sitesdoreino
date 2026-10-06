"""Bases imutáveis, atividades configuráveis e personalizações privadas."""
import uuid
from django.db import models

class Base3D(models.Model):
    chave = models.SlugField(max_length=100)
    versao = models.PositiveIntegerField(default=1)
    dados = models.JSONField(default=dict)
    class Meta:
        db_table = 'cursos_base3d'
        constraints = [models.UniqueConstraint(fields=['chave','versao'], name='base3d_versao_unica')]

class Atividade3D(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aula = models.OneToOneField('cursos.Aula', on_delete=models.PROTECT, related_name='atividade3d')
    grupo = models.SlugField(max_length=100)
    dia = models.PositiveSmallIntegerField(default=1)
    configuracao = models.JSONField(default=dict)
    ativa = models.BooleanField(default=True)
    class Meta:
        db_table = 'cursos_atividade3d'

class Projeto3D(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pessoa = models.ForeignKey('cursos.Pessoa', on_delete=models.PROTECT)
    curso = models.ForeignKey('cursos.Curso', on_delete=models.PROTECT)
    base = models.ForeignKey(Base3D, on_delete=models.PROTECT)
    grupo = models.SlugField(max_length=100)
    titulo = models.CharField(max_length=120, default='Meu item')
    receita = models.JSONField(default=dict)
    revisao = models.PositiveIntegerField(default=1)
    imagem = models.BinaryField()
    tamanho_imagem = models.PositiveIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'cursos_projeto3d'

class Tentativa3D(models.Model):
    pessoa = models.ForeignKey('cursos.Pessoa', on_delete=models.PROTECT)
    atividade = models.ForeignKey(Atividade3D, on_delete=models.PROTECT)
    projeto = models.ForeignKey(Projeto3D, on_delete=models.PROTECT)
    estado = models.JSONField(default=dict)
    class Meta:
        db_table = 'cursos_tentativa3d'
        constraints = [models.UniqueConstraint(fields=['pessoa','atividade'],name='tentativa3d_por_atividade')]

class Jornada3D(models.Model):
    pessoa = models.ForeignKey('cursos.Pessoa', on_delete=models.PROTECT)
    curso = models.ForeignKey('cursos.Curso', on_delete=models.PROTECT)
    inicio = models.DateTimeField(null=True)
    legado = models.BooleanField(default=False)
    class Meta:
        db_table = 'cursos_jornada3d'
        constraints = [models.UniqueConstraint(fields=['pessoa','curso'], name='jornada3d_por_curso')]

class Evento3D(models.Model):
    pessoa = models.ForeignKey('cursos.Pessoa', on_delete=models.PROTECT)
    atividade = models.ForeignKey(Atividade3D, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=40)
    etapa = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'cursos_evento3d'
