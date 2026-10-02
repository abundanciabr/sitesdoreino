from django.db import models


class IntegracaoEnvio(models.Model):
    """Registro idempotente: um envio por (serviço, evento)."""

    STATUS = [
        ("pendente", "pendente"),
        ("aceito", "aceito"),
        ("falhou", "falhou"),
        ("nao_configurado", "nao_configurado"),
        ("sem_consentimento", "sem_consentimento"),
    ]

    servico = models.CharField(max_length=32)
    chave_evento = models.CharField(max_length=120)
    status = models.CharField(max_length=24, choices=STATUS, default="pendente")
    tentativas = models.PositiveSmallIntegerField(default=0)
    ultimo_erro = models.TextField(blank=True, default="")  # nunca com segredo
    enviado_em = models.DateTimeField(null=True, blank=True)
    resposta = models.JSONField(default=dict, blank=True)  # resumo, sem segredo
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quiz"
        constraints = [
            models.UniqueConstraint(
                fields=["servico", "chave_evento"], name="integracao_envio_unico"
            )
        ]
