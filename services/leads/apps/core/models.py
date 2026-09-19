# apps/core/models.py  # [RECEITA:R4 v1]
import uuid

from django.db import models


class Lead(models.Model):
    """Uma pessoa, dentro de UM site. A mesma pessoa (mesmo e-mail) em sites
    diferentes é registrada como leads distintos — upsert é por (site_id, email)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    source = models.CharField(max_length=100, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    consent = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "email"], name="uniq_lead_site_email"
            ),
        ]


class TimelineEvent(models.Model):
    """Histórico da pessoa, por site. Nunca é apagado — upsert e reprocessamento
    de evento só acrescentam entrada, nunca removem as existentes."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="timeline")
    event = models.CharField(max_length=100)  # ex.: "quiz.completado", "lead.upsert"
    event_id = models.UUIDField(null=True, blank=True)  # ausente para upsert via API
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["lead", "occurred_at"])]


class EventoProcessado(models.Model):
    """[INV-leads-idempotencia] a unicidade É o guarda: reentrega do mesmo
    event_id não roda o handler pela segunda vez."""

    event_id = models.UUIDField(unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)


class Oportunidade(models.Model):
    """O acompanhamento comercial humano de UMA pessoa já conhecida da casa.

    A situação não é coluna: é derivada de `desfecho_encerrada_em`. Duas colunas
    dizendo a mesma coisa é uma que pode mentir — o contrato declara `aberta` e
    `encerrada` como variantes disjuntas, e aqui só existe um fato para consultar.
    """

    ETAPAS_ABERTAS = ("nova", "qualificada", "proposta", "negociacao")
    ETAPAS_ENCERRADAS = ("ganha", "perdida", "desqualificada")
    TIPOS_DE_FONTE = ("captura", "quiz", "pedido", "pagamento", "timeline_lead")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead, on_delete=models.PROTECT, related_name="oportunidades"
    )
    etapa = models.CharField(max_length=20)
    titular_id = models.CharField(max_length=100)
    fonte_tipo = models.CharField(max_length=20)
    fonte_referencia_id = models.CharField(max_length=200)
    passo_descricao = models.TextField()
    passo_executar_ate = models.DateTimeField()
    passo_evidencia_esperada = models.TextField()
    desfecho_resultado = models.CharField(max_length=20, blank=True, default="")
    desfecho_motivo = models.TextField(blank=True, default="")
    desfecho_evidencia = models.TextField(blank=True, default="")
    desfecho_encerrada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["titular_id", "-criada_em"]),
            models.Index(fields=["lead", "-criada_em"]),
        ]

    @property
    def encerrada(self) -> bool:
        return self.desfecho_encerrada_em is not None


class RegistroHistoricoOportunidade(models.Model):
    """Histórico humano da oportunidade. Nasce imutável e morre imutável.

    A garantia não é combinada: `save()` recusa o segundo save da mesma linha e
    `delete()` recusa sempre. O contrato promete que a API não expõe alteração
    nem remoção; sem estas duas recusas, a promessa valeria só enquanto ninguém
    escrevesse a linha de código que a quebra.
    """

    TIPOS = (
        "nota",
        "contato",
        "etapa_alterada",
        "transferencia_solicitada",
        "transferencia_aceita",
        "transferencia_recusada",
        "encerramento",
        "reabertura",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oportunidade = models.ForeignKey(
        Oportunidade, on_delete=models.PROTECT, related_name="historico"
    )
    registrado_em = models.DateTimeField(auto_now_add=True)
    autor_id = models.CharField(max_length=100)
    tipo = models.CharField(max_length=30)
    descricao = models.TextField()
    evidencia = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["oportunidade", "registrado_em"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(
                "registro de histórico é imutável: crie um registro novo em vez "
                "de alterar este"
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            "registro de histórico não é removível: o histórico da oportunidade "
            "é a memória do acompanhamento"
        )


class TransferenciaResponsabilidade(models.Model):
    """Passagem de bastão entre comerciais, com aceite do novo titular.

    A unicidade parcial É o guarda do 409: enquanto houver uma pendente, o banco
    recusa a segunda. Sem ela, duas chamadas simultâneas abririam duas pendências
    e a segunda aceita trocaria o titular de novo, sem ninguém ter pedido.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oportunidade = models.ForeignKey(
        Oportunidade, on_delete=models.PROTECT, related_name="transferencias"
    )
    de_titular_id = models.CharField(max_length=100)
    para_titular_id = models.CharField(max_length=100)
    motivo = models.TextField()
    estado = models.CharField(max_length=10, default="pendente")
    solicitada_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    motivo_recusa = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["oportunidade"],
                condition=models.Q(estado="pendente"),
                name="uniq_transferencia_pendente_por_oportunidade",
            ),
        ]
