"""Clientes e orçamento interno da fila, separados de dinheiro recebido."""

import uuid
from django.db import models


class ClienteFila(models.Model):
    site_id = models.CharField(max_length=64, db_index=True)
    slug = models.SlugField(max_length=40)
    nome = models.CharField(max_length=120)
    pessoa_id = models.CharField(max_length=64, blank=True)
    ativo = models.BooleanField(default=True)
    creditos_cents = models.BigIntegerField(default=500000)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'encomendas_clientefila'
        constraints = [
            models.UniqueConstraint(fields=['site_id', 'slug'], name='fila_cliente_site_slug'),
            models.UniqueConstraint(fields=['site_id', 'pessoa_id'], condition=~models.Q(pessoa_id=''), name='fila_cliente_conta_unica'),
            models.CheckConstraint(condition=models.Q(creditos_cents__gte=0), name='fila_creditos_nao_negativos'),
        ]


class PedidoClienteFila(models.Model):
    pedido = models.OneToOneField('encomendas.PedidoMarketplace', on_delete=models.PROTECT, related_name='fila_cliente')
    cliente = models.ForeignKey(ClienteFila, on_delete=models.PROTECT, related_name='pedidos')
    reservado_cents = models.PositiveIntegerField(default=0)
    consumido_em = models.DateTimeField(null=True, blank=True)
    charge_id = models.CharField(max_length=160, blank=True)
    pagamento_real_confirmado_em = models.DateTimeField(null=True, blank=True)
    referencia_provedor = models.CharField(max_length=160, blank=True)
    termos_aceitos = models.JSONField(default=dict)

    class Meta:
        db_table = 'encomendas_pedidoclientefila'


class MovimentoOrcamentoFila(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cliente = models.ForeignKey(ClienteFila, on_delete=models.PROTECT, related_name='movimentos')
    pedido = models.ForeignKey('encomendas.PedidoMarketplace', on_delete=models.PROTECT, null=True, blank=True)
    chave = models.CharField(max_length=200, unique=True)
    tipo = models.CharField(max_length=24)
    valor_cents = models.BigIntegerField()
    saldo_apos_cents = models.BigIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'encomendas_movimentoorcamentofila'


class OrientacaoPrivadaFila(models.Model):
    pedido = models.ForeignKey('encomendas.PedidoMarketplace', on_delete=models.PROTECT, related_name='orientacoes_privadas')
    pessoa_id = models.CharField(max_length=64, db_index=True)
    pergunta = models.TextField()
    resposta = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'encomendas_orientacaoprivadafila'


class CasoConversaFila(models.Model):
    """Resolução humana preservada para preparar o robô futuro, sem envio automático."""
    pedido = models.ForeignKey('encomendas.PedidoMarketplace', on_delete=models.PROTECT)
    pergunta = models.OneToOneField('encomendas.MensagemMarketplace', on_delete=models.PROTECT, related_name='caso_fila')
    resposta = models.ForeignKey('encomendas.MensagemMarketplace', on_delete=models.PROTECT, null=True, blank=True, related_name='casos_resolvidos')
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'encomendas_casoconversafila'
