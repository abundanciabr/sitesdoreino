"""O que o admin fez com áudio: cada transcrição e cada síntese, com o custo.

O áudio e o texto moram na mensageria. Aqui fica o processamento pago: qual
modelo, quanto custou e em que conversa, para o custo aparecer no consumo da
conversa. `consumo_id` aponta o `agentes.Consumo` que entrou no teto de gasto.
"""
from django.db import models


class ProcessamentoDeVoz(models.Model):
    class Tipo(models.TextChoices):
        TRANSCRICAO = "transcricao", "Transcrição"
        SINTESE = "sintese", "Resposta em voz"

    class Situacao(models.TextChoices):
        FEITO = "feito", "Feito"
        ENTREGUE = "entregue", "Entregue à mensageria"
        FALHOU = "falhou", "Falhou"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    site_id = models.CharField(max_length=100)
    # Transcrição: id do áudio na mensageria. Síntese: a chave de idempotência.
    referencia = models.CharField(max_length=160)
    conversa_ref = models.CharField(max_length=160, blank=True, default="")
    consumo_id = models.BigIntegerField(null=True, blank=True)
    modelo = models.CharField(max_length=60, blank=True, default="")
    segundos = models.FloatField(null=True, blank=True)
    caracteres = models.PositiveIntegerField(default=0)
    custo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    # Texto da transcrição: se a devolução à mensageria falhar, reenvia sem
    # pagar de novo.
    texto = models.TextField(blank=True, default="")
    resultado = models.JSONField(default=dict, blank=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.FEITO)
    detalhe = models.CharField(max_length=300, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "site_id", "referencia"], name="uniq_voz_tipo_site_ref"),
        ]
