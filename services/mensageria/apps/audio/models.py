"""Áudio do WhatsApp: o que o lead mandou em voz e o que a equipe respondeu em voz.

A mensageria guarda o áudio original e o texto que corresponde a ele. A
transcrição e a síntese rodam no admin (é lá que mora a chave da OpenAI e o
teto de gasto); o admin pega o áudio por esta API e devolve o texto.
"""
from django.db import models


class AudioRecebido(models.Model):
    class Situacao(models.TextChoices):
        RECEBIDO = "recebido", "Recebido, esperando transcrição"
        TRANSCRITO = "transcrito", "Transcrito"
        FALHOU = "falhou", "Não foi possível transcrever"

    site_id = models.CharField(max_length=100)
    instancia = models.CharField(max_length=100)
    provider_id = models.CharField(max_length=160)
    telefone = models.CharField(max_length=20)
    conversa_ref = models.CharField(max_length=160, blank=True, default="")
    mime = models.CharField(max_length=80, blank=True, default="")
    segundos = models.PositiveIntegerField(null=True, blank=True)
    tamanho_bytes = models.PositiveIntegerField(default=0)
    # O áudio original. Nota de voz do WhatsApp é pequena (opus, ~1,5 KB/s).
    conteudo = models.BinaryField(null=True, blank=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.RECEBIDO)
    tentativas = models.PositiveIntegerField(default=0)
    erro = models.CharField(max_length=300, blank=True, default="")
    transcricao = models.TextField(blank=True, default="")
    idioma = models.CharField(max_length=20, blank=True, default="")
    modelo = models.CharField(max_length=60, blank=True, default="")
    ambiguidades = models.JSONField(default=list, blank=True)
    pedir_esclarecimento = models.BooleanField(default=False)
    pergunta_de_esclarecimento = models.TextField(blank=True, default="")
    custo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    recebido_em = models.DateTimeField(auto_now_add=True)
    transcrito_em = models.DateTimeField(null=True, blank=True)
    entregue_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["instancia", "provider_id"], name="uniq_audio_instancia_provider"),
        ]
        indexes = [models.Index(fields=["site_id", "telefone"], name="audio_site_telefone")]


class PreferenciaDeResposta(models.Model):
    class Modo(models.TextChoices):
        TEXTO = "texto", "Sempre em texto"
        AUDIO = "audio", "Em áudio quando o canal aceitar"
        ESPELHAR = "espelhar", "Em áudio quando o lead mandou áudio"

    site_id = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    modo = models.CharField(max_length=20, choices=Modo.choices, default=Modo.ESPELHAR)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "telefone"], name="uniq_preferencia_site_telefone"),
        ]


class RespostaEmVoz(models.Model):
    """Uma resposta da equipe em áudio, sempre com o texto que foi falado."""

    ESTADOS = [(x, x) for x in ("desconhecido", "aceito", "enviado", "entregue", "lido", "falhou")]

    site_id = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    conversa_ref = models.CharField(max_length=160, blank=True, default="")
    chave_idempotencia = models.CharField(max_length=160)
    texto = models.TextField()
    mime = models.CharField(max_length=80, blank=True, default="")
    tamanho_bytes = models.PositiveIntegerField(default=0)
    conteudo = models.BinaryField(null=True, blank=True)
    modelo = models.CharField(max_length=60, blank=True, default="")
    voz = models.CharField(max_length=40, blank=True, default="")
    custo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    instancia = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=ESTADOS, default="desconhecido")
    provider_id = models.CharField(max_length=160, blank=True, default="")
    erro = models.CharField(max_length=300, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "chave_idempotencia"], name="uniq_voz_site_chave"),
        ]
        indexes = [models.Index(fields=["site_id", "telefone"], name="voz_site_telefone")]
