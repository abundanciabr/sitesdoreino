from django.db import models


class ConfiguracaoWhatsApp(models.Model):
    site_id = models.CharField(max_length=100, unique=True)
    instancia = models.CharField(max_length=100, unique=True)
    transporte = models.CharField(max_length=30, default="WHATSAPP-BAILEYS")
    ativo = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)


class MensagemWhatsApp(models.Model):
    ESTADOS = [(x, x) for x in ("desconhecido", "aceito", "enviado", "entregue", "lido", "falhou")]
    site_id = models.CharField(max_length=100)
    instancia = models.CharField(max_length=100, blank=True)
    origem = models.CharField(max_length=40)
    referencia = models.CharField(max_length=160)
    destinatario = models.CharField(max_length=20)
    corpo = models.TextField()
    status = models.CharField(max_length=20, choices=ESTADOS, default="desconhecido")
    provider_id = models.CharField(max_length=160, blank=True)
    erro = models.CharField(max_length=300, blank=True)
    tentativas = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "origem", "referencia"], name="uniq_wa_origem_site_ref"),
            models.UniqueConstraint(fields=["instancia", "provider_id"], condition=~models.Q(provider_id=""), name="uniq_wa_instancia_provider"),
        ]


class EstadoDeProvedor(models.Model):
    """Retorno que pode chegar antes da resposta HTTP do envio."""
    instancia = models.CharField(max_length=100)
    provider_id = models.CharField(max_length=160)
    status = models.CharField(max_length=20)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["instancia", "provider_id"], name="uniq_wa_retorno_instancia_id")]
