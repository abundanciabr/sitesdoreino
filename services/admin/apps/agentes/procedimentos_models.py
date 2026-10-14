from django.db import models
from django.utils import timezone


class RotinaProcedimentos(models.Model):
    host = models.CharField(max_length=100, unique=True)
    site_id = models.CharField(max_length=100, blank=True)
    idiomas = models.JSONField(default=list, blank=True)
    proxima_em = models.DateTimeField(default=timezone.now)
    coletada_em = models.DateTimeField(null=True)
    posse = models.CharField(max_length=36, blank=True)
    ocupada_ate = models.DateTimeField(null=True)
    executor_em = models.DateTimeField(null=True)
    fontes = models.JSONField(default=dict)
    erro = models.CharField(max_length=300, blank=True)


class AgrupamentoProcedimento(models.Model):
    rotina = models.ForeignKey(RotinaProcedimentos, on_delete=models.PROTECT)
    publico = models.CharField(max_length=20, choices=[('alunos', 'Alunos'), ('interno', 'Técnico interno')])
    titulo = models.CharField(max_length=300)
    termos = models.JSONField(default=list)
    contexto = models.CharField(max_length=300, blank=True)
    casos_independentes = models.PositiveIntegerField(default=0)
    elegivel = models.BooleanField(default=False)
    rascunho = models.TextField(blank=True)
    respostas = models.JSONField(default=dict)
    revisao = models.PositiveIntegerField(default=0)
    assinatura_redigida = models.CharField(max_length=64, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)


class CasoProcedimento(models.Model):
    rotina = models.ForeignKey(RotinaProcedimentos, on_delete=models.PROTECT)
    grupo = models.ForeignKey(AgrupamentoProcedimento, on_delete=models.PROTECT, null=True, related_name='casos')
    fonte = models.CharField(max_length=20)
    chave = models.CharField(max_length=150)
    independente = models.CharField(max_length=64)
    publico = models.CharField(max_length=20)
    contexto = models.CharField(max_length=300, blank=True)
    titulo = models.CharField(max_length=300)
    sintoma = models.TextField()
    solucao = models.TextField(blank=True)
    confirmada = models.BooleanField(default=False)
    ocorrida_em = models.DateTimeField()
    referencia = models.URLField(max_length=500)
    ativa = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['rotina', 'fonte', 'chave'], name='procedimento_caso_unico')]


class RedacaoProcedimento(models.Model):
    grupo = models.ForeignKey(AgrupamentoProcedimento, on_delete=models.PROTECT, related_name='redacoes')
    execucao = models.OneToOneField('agentes.Execucao', on_delete=models.PROTECT)
    assinatura = models.CharField(max_length=64)
    evidencias = models.JSONField(default=list)
    idiomas = models.JSONField(default=list)
    texto = models.TextField(blank=True)
    respostas = models.JSONField(default=dict)
    criada_em = models.DateTimeField(auto_now_add=True)
