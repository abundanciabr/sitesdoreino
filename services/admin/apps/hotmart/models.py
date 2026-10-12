from django.db import models


class ConfiguracaoHotmart(models.Model):
    hottok_sha256 = models.CharField(max_length=64)
    atualizado_em = models.DateTimeField(auto_now=True)


class EventoHotmart(models.Model):
    evento_id = models.CharField(max_length=200, unique=True)
    evento = models.CharField(max_length=100)
    dados = models.JSONField()
    recebido_em = models.DateTimeField(auto_now_add=True)
    ultimo_recebimento = models.DateTimeField(auto_now_add=True)
    recebimentos = models.PositiveIntegerField(default=1)
