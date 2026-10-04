"""Caixa de entrada conversacional: WhatsApp e e-mail nos dois sentidos.

Uma conversa por (site, canal, endereço do contato). O endereço é o telefone
normalizado (só dígitos, com DDI) ou o e-mail em minúsculas. A ligação com o
lead do quiz vem da célula `leads` por API; esta célula guarda só o id opaco.
"""

import uuid

from django.db import models

CANAIS = ("whatsapp", "email")
ESTADOS = ("agente", "pessoa", "encerrada")
LIGACOES = ("ligada", "ambigua", "desconhecida", "pendente")
DIRECOES = ("entrada", "saida")
AUTORES = ("lead", "agente", "pessoa", "sistema")
# Entrada é sempre "recebida". Saída por e-mail: pendente/enviado/falhou/
# desconhecido. Saída por WhatsApp espelha a MensagemWhatsApp ligada.
ESTADOS_DE_ENVIO = (
    "recebida", "pendente", "desconhecido", "aceito", "enviado",
    "entregue", "lido", "falhou",
)


def _escolhas(valores):
    return [(v, v) for v in valores]


class Conversa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100, db_index=True)
    canal = models.CharField(max_length=20, choices=_escolhas(CANAIS))
    endereco = models.CharField(max_length=254)
    # Instância do WhatsApp ou caixa de e-mail que recebeu a conversa.
    caixa = models.CharField(max_length=254, blank=True, default="")
    lead_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    ligacao = models.CharField(max_length=20, choices=_escolhas(LIGACOES), default="pendente")
    estado = models.CharField(max_length=20, choices=_escolhas(ESTADOS), default="agente")
    assumida_por = models.CharField(max_length=100, blank=True, default="")
    assumida_em = models.DateTimeField(null=True, blank=True)
    janela_aberta_ate = models.DateTimeField(null=True, blank=True)
    ultima_entrada_em = models.DateTimeField(null=True, blank=True)
    ultima_mensagem_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "canal", "endereco"], name="uniq_conversa_site_canal_endereco"),
            models.CheckConstraint(condition=models.Q(canal__in=CANAIS), name="conversa_canal_conhecido"),
            models.CheckConstraint(condition=models.Q(estado__in=ESTADOS), name="conversa_estado_conhecido"),
            models.CheckConstraint(condition=models.Q(ligacao__in=LIGACOES), name="conversa_ligacao_conhecida"),
        ]
        indexes = [models.Index(fields=["site_id", "estado", "ultima_mensagem_em"], name="conv_site_estado_ultima")]

    @property
    def ambigua(self) -> bool:
        return self.ligacao == "ambigua"


class MensagemDaConversa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name="mensagens")
    direcao = models.CharField(max_length=10, choices=_escolhas(DIRECOES))
    autor = models.CharField(max_length=10, choices=_escolhas(AUTORES))
    autor_id = models.CharField(max_length=100, blank=True, default="")
    texto = models.TextField(blank=True, default="")
    assunto = models.CharField(max_length=300, blank=True, default="")
    midia_tipo = models.CharField(max_length=20, blank=True, default="")
    midia_referencia = models.CharField(max_length=300, blank=True, default="")
    midia_mime = models.CharField(max_length=120, blank=True, default="")
    transcricao = models.TextField(blank=True, default="")
    estado_envio = models.CharField(max_length=20, choices=_escolhas(ESTADOS_DE_ENVIO))
    erro = models.CharField(max_length=300, blank=True, default="")
    # wamid / id da Evolution / Message-ID do e-mail.
    id_externo = models.CharField(max_length=300, blank=True, default="")
    em_resposta_a = models.CharField(max_length=300, blank=True, default="")
    chave_idempotencia = models.CharField(max_length=100, blank=True, default="")
    mensagem_whatsapp = models.ForeignKey(
        "whatsapp.MensagemWhatsApp", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    descadastro = models.BooleanField(default=False)
    ocorrida_em = models.DateTimeField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversa", "direcao", "id_externo"], condition=~models.Q(id_externo=""),
                name="uniq_msg_conversa_direcao_externo",
            ),
            models.UniqueConstraint(
                fields=["conversa", "chave_idempotencia"], condition=~models.Q(chave_idempotencia=""),
                name="uniq_msg_conversa_chave",
            ),
            models.CheckConstraint(condition=models.Q(direcao__in=DIRECOES), name="msg_direcao_conhecida"),
            models.CheckConstraint(condition=models.Q(estado_envio__in=ESTADOS_DE_ENVIO), name="msg_estado_conhecido"),
        ]
        indexes = [models.Index(fields=["conversa", "ocorrida_em"], name="msg_conversa_ocorrida")]


class Descadastro(models.Model):
    """O contato pediu para parar naquele canal (PARAR, SAIR, STOP...)."""

    site_id = models.CharField(max_length=100)
    canal = models.CharField(max_length=20, choices=_escolhas(CANAIS))
    endereco = models.CharField(max_length=254)
    conversa = models.ForeignKey(Conversa, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    registrado_em = models.DateTimeField()
    # Preferência gravada nas jornadas (precisa do id de plataforma da pessoa).
    preferencia_registrada = models.BooleanField(default=False)
    preferencia_motivo = models.CharField(max_length=200, blank=True, default="")
    tentativas = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "canal", "endereco"], name="uniq_descadastro_site_canal_endereco"),
        ]
