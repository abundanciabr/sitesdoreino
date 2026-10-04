"""Modelos de mensagem aprovados pela Meta e os envios feitos com eles.

O primeiro contato com um lead no WhatsApp oficial (Cloud API) só pode sair
por um modelo aprovado: a resposta livre depende da janela de 24 horas que o
próprio contato abre ao escrever. Aqui ficam o espelho dos modelos da conta
(sincronizado da Cloud API) e cada envio, com chave de idempotência.
"""
from django.db import models


class ModeloWhatsApp(models.Model):
    ESTADOS = [(x, x) for x in ("aprovado", "pendente", "rejeitado", "pausado", "desativado", "outro")]

    conta = models.CharField(max_length=64)  # WABA id: o modelo é da conta, não do site
    modelo_id = models.CharField(max_length=64, blank=True)
    nome = models.CharField(max_length=512)
    idioma = models.CharField(max_length=20)
    categoria = models.CharField(max_length=30, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="outro")
    estado_no_provedor = models.CharField(max_length=40, blank=True)
    formato_parametros = models.CharField(max_length=12, default="positional")
    corpo = models.TextField(blank=True)
    componentes = models.JSONField(default=list, blank=True)
    # [{"chave": "body:1", "componente": "body", "parametro": "1", "exemplo": ""}]
    variaveis = models.JSONField(default=list, blank=True)
    # {"body:1": "nome", "body:2": "quiz"}: que dado do lead vai em cada lugar
    mapeamento = models.JSONField(default=dict, blank=True)
    suportado = models.BooleanField(default=True)
    motivo = models.CharField(max_length=300, blank=True)
    presente_no_provedor = models.BooleanField(default=True)
    sincronizado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conta", "nome", "idioma"], name="uniq_wa_modelo_conta_nome_idioma"),
        ]


class EnvioDeModelo(models.Model):
    ESTADOS = [(x, x) for x in ("reservado", "aceito", "enviado", "entregue", "lido", "falhou", "desconhecido")]

    site_id = models.CharField(max_length=100)
    chave_idempotencia = models.CharField(max_length=200)
    origem = models.CharField(max_length=40)  # abordagem | jornada | manual
    referencia = models.CharField(max_length=200, blank=True)  # ex.: oportunidade_ref
    modelo_nome = models.CharField(max_length=512)
    idioma = models.CharField(max_length=20)
    destinatario = models.CharField(max_length=20, blank=True)
    variaveis = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="reservado")
    provider_id = models.CharField(max_length=200, blank=True)
    erro = models.CharField(max_length=300, blank=True)
    erro_codigo = models.CharField(max_length=20, blank=True)
    # True quando a falha é comprovadamente anterior à criação da mensagem na
    # Meta (recusa 4xx, falta de credencial, dado ausente): repetir é seguro.
    retomavel = models.BooleanField(default=False)
    tentativas = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "chave_idempotencia"], name="uniq_wa_envio_modelo_chave"),
            models.UniqueConstraint(fields=["provider_id"], condition=~models.Q(provider_id=""),
                                    name="uniq_wa_envio_modelo_provider"),
        ]
        indexes = [models.Index(fields=["site_id", "-id"], name="wa_envio_modelo_site_idx")]


class RetornoDeModelo(models.Model):
    """Estado informado pela Meta que pode chegar antes da resposta do envio."""
    provider_id = models.CharField(max_length=200, unique=True)
    estado = models.CharField(max_length=20)
    erro_codigo = models.CharField(max_length=20, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
