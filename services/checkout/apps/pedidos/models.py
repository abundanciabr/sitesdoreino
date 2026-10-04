import uuid

from django.db import models


class SnapshotCongelado(Exception):
    """Tentativa de reescrever um snapshot já criado."""


# O que o pedido congela na criação. Correção de pedido = pedido novo +
# cancelamento do antigo, nunca UPDATE nestes campos.
CAMPOS_CONGELADOS = ("site_id", "items", "total_cents", "customer")


class Session(models.Model):
    """Sessão de checkout: a oferta lida do catálogo NA ABERTURA, por site."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64)  # vem do Host, nunca do payload
    offer_slug = models.CharField(max_length=200)
    offer = models.JSONField()
    lead_id = models.CharField(max_length=64, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    # Atribuição vinda do quiz (v, fmt, seg, src, med, cpg, ctv, qa, qz) e do
    # link de compra do atendimento (op, est): valores curtos, opacos, sem dado
    # pessoal. Preserva o que chegou na abertura.
    contexto = models.JSONField(default=dict, blank=True)
    # [DESENHO-COMUM.md F10] o UUID4 do cookie `meshcraft_visitante` (funil),
    # lido na abertura da sessão. Nulo quando o navegador chegou sem o cookie
    # ou com um valor que não é um UUID4 canônico — esta célula não é dona do
    # cookie, só lê; nunca sorteia nem corrige o que recebeu.
    visitor_id = models.CharField(max_length=36, null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["site_id", "offer_slug"])]


class OrderQuerySet(models.QuerySet):
    def update(self, **kwargs):
        # QuerySet.update() não passa por Model.save() — o guarda precisa
        # existir nos dois caminhos, senão a lei vale só pela metade.
        congelados = sorted(set(kwargs) & set(CAMPOS_CONGELADOS))
        if congelados:
            raise SnapshotCongelado(
                f"snapshot é create-only; campos recusados: {', '.join(congelados)}"
            )
        return super().update(**kwargs)


class Order(models.Model):
    AGUARDANDO = "aguardando_pagamento"
    STATUS = [
        (AGUARDANDO, AGUARDANDO),
        ("pago", "pago"),
        ("recusado", "recusado"),
        ("expirado", "expirado"),
        ("reembolsado", "reembolsado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session, on_delete=models.PROTECT, related_name="order"
    )
    site_id = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=STATUS, default=AGUARDANDO)
    items = models.JSONField()
    total_cents = models.PositiveIntegerField()
    customer = models.JSONField()
    method = models.CharField(max_length=8)
    intent_id = models.CharField(max_length=64)
    pix = models.JSONField(default=dict, blank=True)
    # Cópia de Session.contexto no fechamento do pedido.
    contexto = models.JSONField(default=dict, blank=True)
    # Referências opacas para o CRM casar a venda: a oportunidade (vinda do
    # link de compra do atendimento) e a oferta (a slug do catálogo).
    oportunidade_ref = models.CharField(max_length=100, blank=True, default="")
    oferta_ref = models.CharField(max_length=200, blank=True, default="")
    # Quando o aviso do provedor confirmou o pagamento (pagamento.aprovado).
    pago_em = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_cents__gte=1), name="order_total_cents_min_1"
            )
        ]
        indexes = [
            models.Index(
                fields=["site_id", "oportunidade_ref"], name="pedidos_ord_site_op_idx"
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            anterior = (
                Order.objects.filter(pk=self.pk).values(*CAMPOS_CONGELADOS).first()
            )
            if anterior is not None:
                divergentes = sorted(
                    campo
                    for campo in CAMPOS_CONGELADOS
                    if getattr(self, campo) != anterior[campo]
                )
                if divergentes:
                    raise SnapshotCongelado(
                        "snapshot é create-only; campos recusados: "
                        f"{', '.join(divergentes)}"
                    )
        return super().save(*args, **kwargs)


class LinkDeCompra(models.Model):
    """Link de compra preparado pelo atendimento para uma oportunidade.

    Abre o checkout pelo caminho normal: uma `Session` da oferta, com o id do
    pedido já reservado. O pedido nasce quando a pessoa confirma os dados na
    página (o CPF é dela e só ela digita). A mesma chave de idempotência no
    mesmo site devolve sempre este link, nunca um segundo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64)
    chave_idempotencia = models.CharField(max_length=200)
    session = models.OneToOneField(
        Session, on_delete=models.PROTECT, related_name="link_de_compra"
    )
    pedido_id = models.UUIDField(unique=True, default=uuid.uuid4)
    oferta_ref = models.CharField(max_length=200)
    oportunidade_ref = models.CharField(max_length=100)
    contato = models.JSONField(default=dict, blank=True)
    condicao = models.JSONField(default=dict)
    resposta = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True)

    def id_da_tentativa(self, numero: int) -> uuid.UUID:
        """O link serve um pedido por vez. A 1ª tentativa leva o id que o CRM
        já recebeu (`pedido_id`); quando ela expira ou é recusada e a pessoa
        reabre o link, a tentativa seguinte ganha um id derivado dele. Assim o
        CRM segue com um id só e a cadeia se acha sem guardar nada a mais."""
        return self.pedido_id if numero == 1 else uuid.uuid5(self.pedido_id, str(numero))

    def tentativas(self) -> list:
        """Os pedidos deste link, do primeiro ao último."""
        achados = []
        while True:
            pedido = Order.objects.filter(
                pk=self.id_da_tentativa(len(achados) + 1), site_id=self.site_id
            ).first()
            if pedido is None:
                return achados
            achados.append(pedido)

    def proximo_id_de_pedido(self) -> uuid.UUID:
        return self.id_da_tentativa(len(self.tentativas()) + 1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "chave_idempotencia"],
                name="link_compra_chave_unica_por_site",
            )
        ]
        indexes = [
            models.Index(
                fields=["site_id", "oportunidade_ref"], name="pedidos_lin_site_op_idx"
            )
        ]


class CondicaoDoAgente(models.Model):
    """Uma condição de compra que o mantenedor deixou o agente oferecer.

    Existir a linha é estar liberada. A condição em si (Pix, parcela do cartão,
    cupom) continua sendo a que o checkout calcula agora; aqui só se guarda a
    escolha. Nada aqui cria preço, desconto ou prazo.
    """

    site_id = models.CharField(max_length=64)
    oferta_slug = models.CharField(max_length=200)
    condicao_id = models.CharField(max_length=80)
    liberada_por = models.CharField(max_length=200, blank=True, default="")
    liberada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "oferta_slug", "condicao_id"],
                name="condicao_agente_unica_por_oferta",
            )
        ]


class OutboxEvent(models.Model):  # [RECEITA:R3 v1]
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]


class FatoAplicado(models.Model):
    """Um fato de pagamento que esta célula já aplicou, guardado pela
    identidade lógica que o contrato publica no campo `x-ponte-do-v1` dos
    schemas v2.

    A chave NÃO é o `event_id`: o mesmo pagamento chega como `pagamento.*.v1` e
    como `pagamento.*.v2` enquanto o v1 não sai do ar, e cada versão traz o seu
    próprio `event_id`. Deduplicar por ele deixaria o mesmo fato passar duas
    vezes. O índice único desta chave é o que faz v1 e v2, a reentrega do
    transporte e dois consumidores ao mesmo tempo renderem um efeito só.
    """

    chave = models.CharField(max_length=300, primary_key=True)
    aplicado_em = models.DateTimeField(auto_now_add=True)
