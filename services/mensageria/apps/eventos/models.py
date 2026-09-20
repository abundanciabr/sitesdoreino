# apps/eventos/models.py  # [RECEITA:R4 v1]
from django.db import models


class EventoProcessado(models.Model):
    """Guarda de idempotência na entrega do stream — a unicidade de event_id É
    o mecanismo: reentrega do mesmo evento nunca chega ao handler duas vezes."""

    event_id = models.UUIDField(unique=True)
    event = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)


class FatoDeProvedorVisto(models.Model):
    """Dedup ENTRE VERSÕES do mesmo fato de pagamento (TAR-549).

    `EventoProcessado` só pega a reentrega do MESMO `event_id`. Quando o mesmo
    pagamento chega uma vez como v1 e outra como v2, os dois envelopes têm
    `event_id` diferente — a unicidade acima não enxerga a repetição, e o
    handler rodaria duas vezes.

    A chave aqui não é `order_id`: é a identidade lógica que os contratos
    `contracts/eventos/pagamento.*.v2.json` declaram em `x-ponte-do-v1`, e as
    duas versões do mesmo fato sempre derivam o MESMO valor de `chave`, em
    qualquer ordem de chegada. Para `pagamento.aprovado` é o par
    `provider`+`provider_reference_id` (no v1 o par implícito é sempre
    `mercadopago`+`mp_payment_id`); para `pagamento.recusado` é só
    `payment_id`, porque o v1 da recusa nunca carregou referência de
    provedor. As duas SEMPRE nascem escopadas pelo site (`platform_site_id`
    no v2, `site_id` no v1) — [INV-P11] — para que um fato de um site nunca
    consuma, por coincidência de referência opaca, a identidade de outro. Ver
    `identidade_do_fato()` em `management/commands/consume_eventos.py`.
    """

    evento = models.CharField(max_length=100)
    chave = models.CharField(max_length=255)
    event_id = models.UUIDField()
    visto_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "chave"], name="uniq_fato_por_evento_e_chave"
            ),
        ]


class EnvioRegistrado(models.Model):
    """Auditoria + segunda camada de idempotência, por chave de negócio
    (order_id), já que o handler recebe só `envelope["data"]` — sem event_id."""

    STATUS_CHOICES = [
        ("pendente", "pendente"),
        ("enviado", "enviado"),
        ("falhou", "falhou"),
    ]
    CANAL_CHOICES = [("email", "email"), ("whatsapp", "whatsapp")]

    event = models.CharField(max_length=100)
    site_id = models.CharField(max_length=100)
    order_id = models.CharField(max_length=100)
    tipo = models.CharField(max_length=40)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
    destinatario = models.CharField(max_length=255)
    assunto = models.CharField(max_length=255, blank=True, default="")
    corpo = models.TextField()
    template_versao = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    tentativas = models.PositiveSmallIntegerField(default=0)
    resultado = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order_id", "tipo", "canal"],
                name="uniq_envio_por_order_tipo_canal",
            ),
        ]


class EnderecoDeEmail(models.Model):
    """Endereço que o provedor declarou inválido ou que reclamou.

    O bloqueio é global para e-mail: uma reclamação não pode ser contornada
    por outra jornada ou pelo caminho transacional.
    """

    MOTIVOS = [("devolucao", "devolução"), ("reclamacao", "reclamação")]

    email = models.EmailField(unique=True)
    motivo = models.CharField(max_length=20, choices=MOTIVOS)
    bloqueado_em = models.DateTimeField(auto_now=True)


class JanelaDeCapacidade(models.Model):
    """Contadores e disjuntor do único provedor de e-mail da célula."""

    chave = models.CharField(max_length=32, unique=True, default="email")
    minuto_em = models.DateTimeField()
    envios_no_minuto = models.PositiveIntegerField(default=0)
    hora_em = models.DateTimeField()
    envios_na_hora = models.PositiveIntegerField(default=0)
    disjuntor_ate = models.DateTimeField(null=True, blank=True)
    falhas_consecutivas = models.PositiveSmallIntegerField(default=0)
    atualizado_em = models.DateTimeField(auto_now=True)
