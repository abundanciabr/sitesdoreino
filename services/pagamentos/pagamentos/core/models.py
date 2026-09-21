# pagamentos/core/models.py  # [RECEITA:R1 v1]
# core/ é dono do modelo (ver AGENTS.pagamentos: "core/ ... modelos, ledger, outbox,
# ... gateway p/ providers"). methods/pix e methods/card leem/escrevem Intent daqui —
# isso NÃO viola INV-P9 (a independência é só entre os dois métodos, e entre método
# e providers; método→core é permitido e é o padrão desta célula).
#
# Outbox (RECEITA:R3) mora aqui também — não em app Django separado. Decisão de
# orçamento (ver LICOES.md): core/models.py é o ÚNICO app com models.py/migrations
# desta célula; um app "eventos" à parte custaria outro migrations/__init__.py sem
# necessidade arquitetural real. A máquina de transição financeira, essa, mora em
# core/ledger.py: aqui ficam só os modelos e a tranca que obriga a passar por lá.
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Collection, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import redis
from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

STATUS_CHOICES = [
    ("created", "created"),
    ("pending", "pending"),
    ("approved", "approved"),
    ("rejected", "rejected"),
    ("expired", "expired"),
    ("refunded", "refunded"),
]
METHOD_CHOICES = [("pix", "pix"), ("card", "card")]
PROVIDER_CHOICES = [("appmax", "appmax"), ("mercadopago", "mercadopago")]

ATTEMPT_STATE_CHOICES = [
    ("sending", "sending"),
    ("approved", "approved"),
    ("rejected", "rejected"),
    ("failed", "failed"),
    ("reconciliation_required", "reconciliation_required"),
]
# Os tres estados que impedem um novo envio para o MESMO Intent, e o porque de
# cada um: `sending` porque a chamada ainda esta em voo (duplo clique),
# `reconciliation_required` porque o resultado e ambiguo e reenviar seria cobrar
# duas vezes, e `approved` porque ja foi pago. Os que faltam liberam de
# proposito: `rejected` (o comprador tem direito a tentar outro cartao) e
# `failed` (nada saiu da nossa maquina, entao nao ha cobranca possivel la fora).
ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO = ["sending", "reconciliation_required", "approved"]
ESTADOS_EM_ABERTO = ["sending", "reconciliation_required"]

# Os estados da Intent que SÃO um fato de dinheiro: a partir daqui existe algo a
# contar para as outras células (matrícula a criar, acesso a cortar, cobrança a
# reapresentar). Entrar num deles, ou sair dele, é o que esta célula chama de
# transição financeira, e nenhuma acontece fora de `core/ledger.py`.
ESTADOS_FINANCEIROS = frozenset({"approved", "rejected", "expired", "refunded"})


class TransicaoForaDoLedger(RuntimeError):
    """Alguém gravou um status financeiro direto na linha da Intent.

    É a falha que este módulo passou a tornar impossível: era assim que a
    confirmação de cartão aprovava o pagamento sem avisar ninguém. Quem pega
    esta exceção não deve "tentar de outro jeito": deve chamar
    `pagamentos.core.ledger.registrar_fato`, que grava o estado e o aviso na
    mesma transação.
    """


# A autorização da transição e a coleta dos avisos são a MESMA marca de
# contexto, de propósito: enquanto ela existe, o ledger está no meio de uma
# transição, e toda linha de outbox que nascer nesse intervalo fica registrada
# nela. É com essa lista que o ledger confere, antes de commitar, que a mudança
# de estado produziu exatamente um aviso. Ela é por contexto de execução
# (ContextVar), então duas requisições simultâneas nunca contam o aviso uma da
# outra.
_avisos_da_transicao: ContextVar[list[str] | None] = ContextVar(
    "pagamentos_avisos_da_transicao", default=None
)


@contextmanager
def transicao_do_ledger() -> Iterator[list[str]]:
    """Abre a ÚNICA janela em que um status financeiro pode ser gravado.

    Uso exclusivo de `pagamentos.core.ledger` (e o guarda
    `tests/test_ledger_transicao_financeira.py::test_so_o_ledger_abre_a_janela_de_transicao`
    varre o código de produção para que continue exclusivo). Devolve a lista dos
    avisos gravados enquanto a janela esteve aberta.
    """
    avisos: list[str] = []
    marca = _avisos_da_transicao.set(avisos)
    try:
        yield avisos
    finally:
        _avisos_da_transicao.reset(marca)


class Intent(models.Model):
    """Uma linha por intenção de cobrança. `idempotency_key` é o que torna
    POST /intents idempotente (INV-P4): a MESMA chave sempre resolve para a
    MESMA linha — nunca uma segunda chamada ao provider."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True)
    site_id = models.CharField(
        max_length=255
    )  # OPACO — armazenar e ecoar, nunca interpretar
    order_id = models.CharField(max_length=255)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="created")
    amount_cents = models.PositiveIntegerField()  # dinheiro é inteiro sempre
    currency = models.CharField(max_length=3, default="BRL")
    customer = models.JSONField()
    metadata = models.JSONField(default=dict, blank=True)

    provider_payment_id = models.CharField(max_length=255, blank=True, default="")
    pix_qr_code = models.TextField(blank=True, default="")
    pix_qr_code_base64 = models.TextField(blank=True, default="")
    pix_expires_at = models.DateTimeField(null=True, blank=True)
    card_reason_code = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # O status que esta linha tinha no banco quando foi lida. É o que permite
    # recusar também a transição para TRÁS (aprovado voltando a pendente) sem
    # gastar uma consulta a cada gravação.
    _status_no_banco: str | None = None

    class Meta:
        indexes = [models.Index(fields=["order_id"])]

    def __str__(self) -> str:
        return f"{self.method}:{self.id}:{self.status}"

    @classmethod
    def from_db(
        cls, db: str | None, field_names: Collection[str], values: Collection[Any]
    ) -> Intent:
        intent = super().from_db(db, field_names, values)
        if "status" in field_names:
            intent._status_no_banco = intent.status
        return intent

    def refresh_from_db(
        self,
        using: str | None = None,
        fields: Iterable[str] | None = None,
        from_queryset: Any = None,
    ) -> None:
        """Reler a linha reposiciona também a marca do status no banco. Sem
        isto, um objeto relido continuaria carregando o status anterior como se
        fosse o do banco, e a tranca de `save()` julgaria pelo passado."""
        campos = None if fields is None else list(fields)
        # `from_queryset` só existe no Django 5.1+; repassar sempre quebraria na
        # versão que esta célula roda. Repassado apenas quando quem chamou usou.
        extra = {} if from_queryset is None else {"from_queryset": from_queryset}
        super().refresh_from_db(using=using, fields=campos, **extra)
        if campos is None or "status" in campos:
            self._status_no_banco = self.status

    def save(self, *args: Any, **kwargs: Any) -> None:
        """[INV-P6] A tranca do dinheiro, no lugar onde ela não tem como ser
        esquecida: gravar `status` financeiro só passa dentro da janela que
        `core/ledger.py` abre, e lá o aviso da outbox nasce junto. Fora dela a
        gravação levanta `TransicaoForaDoLedger` em vez de aprovar em silêncio.

        Os dois lados são recusados: ENTRAR num estado financeiro (aprovar,
        recusar, expirar, estornar) e SAIR de um (aprovado voltando a pendente),
        porque transição financeira é de mão única. Gravar outros campos de uma
        linha já aprovada continua livre: a tranca só olha para `status`.
        """
        campos = kwargs.get("update_fields")
        grava_status = campos is None or "status" in campos
        self._recusar_status_fora_do_ledger(grava_status)
        super().save(*args, **kwargs)
        if grava_status:
            self._status_no_banco = self.status

    def _recusar_status_fora_do_ledger(self, grava_status: bool) -> None:
        if not grava_status or _avisos_da_transicao.get() is not None:
            return
        impedido = next(
            (
                status
                for status in (self.status, self._status_no_banco)
                if status in ESTADOS_FINANCEIROS
            ),
            None,
        )
        if impedido is None:
            return
        raise TransicaoForaDoLedger(
            f"gravar status={self.status!r} na intent {self.pk} fora do ledger "
            f"foi recusado ({impedido!r} e um estado de dinheiro). Estado "
            "financeiro e aviso as outras celulas nascem juntos: chame "
            "pagamentos.core.ledger.registrar_fato(), que grava a transicao e a "
            "linha da outbox na mesma transacao."
        )


class PaymentAttempt(models.Model):
    """Uma linha por TENTATIVA de cobrar o cartão. O Intent diz o que se quer
    cobrar; a tentativa diz o que de fato foi enviado ao provedor, quando, com
    que corpo e com que resultado.

    Ela nasce COMMITADA antes de qualquer chamada externa (ver
    `core/tentativas.py`): uma cobrança que existe lá fora sem linha aqui é uma
    cobrança órfã, e numa célula de dinheiro isso não se conserta depois.

    A regra que evita a cobrança dupla não está escrita em prosa, e sim no
    índice único parcial abaixo: enquanto existir uma tentativa em
    `sending`, `reconciliation_required` ou `approved`, o Postgres RECUSA a
    segunda linha para o mesmo Intent. Duplo clique simultâneo, portanto, não
    depende de o código lembrar de checar.

    [INV-P8] Nada de dado do portador aqui: do corpo enviado fica só
    `request_hash`, e o motivo do provedor entra sanitizado como código.
    """

    intent = models.ForeignKey(
        Intent, on_delete=models.PROTECT, related_name="tentativas"
    )
    # Copiado do Intent na abertura: a leitura isolada por site (Lei 9) não
    # pode depender de um join para acontecer.
    platform_site_id = models.CharField(max_length=255)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    # Nosso identificador da operação, gerado ANTES do envio: é o que liga o
    # que mandamos ao que o provedor responder depois.
    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_hash = models.CharField(max_length=64)

    provider_reference_id = models.CharField(max_length=255, blank=True, default="")
    external_order_id = models.CharField(max_length=255, blank=True, default="")
    installments = models.PositiveSmallIntegerField(default=1)
    amount_cents = models.PositiveIntegerField()  # dinheiro é inteiro sempre
    state = models.CharField(
        max_length=30, choices=ATTEMPT_STATE_CHOICES, default="sending"
    )
    reason = models.CharField(max_length=120, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["intent"],
                condition=models.Q(state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO),
                name="uma_tentativa_viva_por_intent",
            )
        ]
        # O webhook chega com a referência do provedor e precisa achar a
        # tentativa; sem índice isso é varredura na tabela de dinheiro.
        indexes = [models.Index(fields=["provider_reference_id"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.operation_id}:{self.state}"


class InstalacaoAppmax(models.Model):
    """Uma linha por instalação do nosso aplicativo numa conta Appmax.

    Durante `POST /app/client/generate` a Appmax chama a nossa URL de validação
    e só emite a credencial se a resposta for 200 com um `external_id` válido e
    inédito. Por isso `app_id` é único e `external_id` nasce UMA vez: a segunda
    chamada do mesmo `app_id` devolve o MESMO UUID, nunca um novo, que
    derrubaria a instalação já existente.

    [INV-P8] `client_secret`, `client_key` e `external_key` NUNCA são
    persistidos. Do segredo fica no máximo `client_secret_recebido`, a marca de
    que a credencial chegou a ser emitida para esta conta.
    """

    app_id = models.CharField(max_length=64, unique=True)  # ID NUMÉRICO, não UUID
    appmax_site_id = models.CharField(max_length=64, blank=True, default="")
    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alias = models.CharField(max_length=255)  # nome da loja, vem da configuração
    platform_site_ids = models.JSONField(
        default=list, blank=True
    )  # sites internos que esta instalação está autorizada a cobrar
    client_secret_recebido = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"appmax:{self.app_id}:{self.alias}"


class OutboxEvent(models.Model):
    """[RECEITA:R3 v1] Uma linha por evento emitido. `emitir()` grava SEMPRE na
    MESMA transação da mudança de estado que a justifica (INV-P6) — o relay
    (`relay_outbox`) publica no Redis Streams depois, marcando `published_at`."""

    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)  # ex.: "pagamento.aprovado"
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()  # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]

    def __str__(self) -> str:
        return f"{self.event}:{self.event_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Toda linha de outbox que nasce durante uma transição do ledger se
        anuncia para ela. É por esta anotação, e não por confiança no código de
        quem emite, que o ledger consegue exigir um aviso por transição antes de
        commitar: apagar a emissão deixa a lista vazia e a transação inteira
        volta atrás."""
        nova = self._state.adding
        super().save(*args, **kwargs)
        avisos = _avisos_da_transicao.get()
        if nova and avisos is not None:
            avisos.append(self.event)


def emitir(event: str, data: dict[str, Any], *, version: int = 1) -> OutboxEvent:
    """[RECEITA:R3 v1] [INV-P6] Chame SEMPRE dentro da MESMA transaction.atomic()
    da mudança de estado que o justifica — estado sem evento e evento sem estado
    são ambos impossíveis."""
    return OutboxEvent.objects.create(event=event, version=version, payload=data)


def relay_outbox() -> int:
    """[RECEITA:R3 v1] Publica os eventos pendentes em `eventos.<nome>` no Redis
    Streams e marca `published_at`. Chamada via `transaction.on_commit` logo após
    a transação que gravou o evento (latência sub-segundo). Nesta fase do
    esqueleto não há worker/periodic task de "rede de segurança" (Huey) — ver
    LICOES.md; a função é idempotente e segura de chamar de novo manualmente
    (um evento com `published_at` preenchido é ignorado pelo filtro abaixo)."""
    pendentes = list(
        OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:200]
    )
    if not pendentes:
        return 0
    cliente = redis.from_url(settings.REDIS_STREAMS_URL)  # type: ignore[no-untyped-call]
    publicados = 0
    for evento in pendentes:
        envelope = {
            "event": evento.event,
            "version": evento.version,
            "event_id": str(evento.event_id),
            "occurred_at": evento.occurred_at.isoformat(),
            "data": evento.payload,
        }
        cliente.xadd(
            f"eventos.{evento.event}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
        evento.published_at = timezone.now()
        evento.save(update_fields=["published_at"])
        publicados += 1
    return publicados


def relay_apos_commit() -> None:
    """Publica imediatamente após o commit. Uma falha aqui (ex.: Redis fora do
    ar) NUNCA perde o evento — ele já está persistido na outbox com
    `published_at=None` e será republicado na próxima chamada de
    `relay_outbox()` (manual, ou de um próximo webhook)."""
    try:
        relay_outbox()
    except Exception:  # noqa: BLE001 - defensivo por design, ver docstring
        logger.exception("relay_outbox falhou apos commit; evento fica pendente")
