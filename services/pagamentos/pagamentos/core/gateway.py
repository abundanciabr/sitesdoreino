# pagamentos/core/gateway.py  # [RECEITA:R1 v1]
# Única costura entre methods/* e providers/*. methods/pix e methods/card
# chamam SÓ estas funções — nunca importam providers.* direto (garantido em
# check-time por .importlinter, contrato "metodos-so-falam-com-core"). Os tipos de
# retorno (ResultadoPix/ResultadoCard) são vocabulário do domínio, definidos aqui —
# não vazam o formato de resposta do Mercado Pago para methods/*.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar

from pagamentos.providers.appmax.client import AppmaxClient, AppmaxError
from pagamentos.providers.mercadopago.client import MercadoPagoClient, MercadoPagoError


T = TypeVar("T")


class FalhaNoProvedor(Exception):
    """O provedor NÃO produziu um pagamento utilizável.

    Cobre os dois modos de falha com um nome só, porque para quem chama a
    consequência é idêntica (não há cobrança para apresentar):

    1. o provedor falhou — status não-2xx, rede, timeout, corpo ilegível;
    2. o provedor respondeu 2xx com um payload que não descreve um pagamento
       pagável (sem `id`, Pix sem copia-e-cola, cartão sem `status`).

    É vocabulário de DOMÍNIO e mora aqui pelo mesmo motivo que
    ResultadoPix/ResultadoCard: methods/* não pode importar providers.* (INV-P9,
    `.importlinter`, contrato "metodos-so-falam-com-core"). Sem esta tradução,
    quem chama o gateway não teria como capturar `MercadoPagoError` sem furar a
    arquitetura — e acabaria não capturando nada, que é como o bug original
    sobreviveu.
    """

    def __init__(
        self, message: str, *, ambiguo: bool = False, diagnostico: str = ""
    ) -> None:
        super().__init__(message)
        self.ambiguo = ambiguo
        self.diagnostico = diagnostico


class RecusaAntifraude(FalhaNoProvedor):
    def __init__(self, *, payment_id: str, status_detail: str) -> None:
        super().__init__("pagamento recusado por antifraude pelo Mercado Pago")
        self.payment_id = payment_id
        self.status_detail = status_detail
        self.reason_code = status_detail


class PixNaoPagavel(FalhaNoProvedor):
    """O MP criou o pagamento, mas recusado, cancelado ou vencido.

    Mesmo tratamento de `FalhaNoProvedor` para quem chama; carrega o id e o
    `status_detail` para que a criação os guarde como observação (AC11).
    """

    def __init__(
        self, message: str, *, payment_id: str, status: str, status_detail: str
    ) -> None:
        super().__init__(message)
        self.payment_id = payment_id
        self.status = status
        self.status_detail = status_detail


def recusa_antifraude_mp(status: str, status_detail: str) -> bool:
    return status == "rejected" and status_detail.endswith(("high_risk", "blacklist"))


@dataclass(frozen=True)
class ResultadoPix:
    payment_id: str
    qr_code: str
    qr_code_base64: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ResultadoCard:
    payment_id: str
    status: str
    reason_code: str
    external_reference: str = ""
    transaction_amount: Decimal | None = None
    installments: int | None = None
    currency_id: str = ""
    total_paid_amount: Decimal | None = None


@dataclass(frozen=True)
class StatusDoPagamento:
    """Resultado da CONSULTA a um pagamento existente (GET) — a fonte de
    verdade que os webhook handlers usam no lugar do corpo não assinado."""

    payment_id: str
    status: str  # status cru do provider (approved/rejected/cancelled/...)
    reason_code: str  # status_detail do provider ("" quando ausente)
    external_reference: str = ""
    transaction_amount: Decimal | None = None
    installments: int | None = None
    currency_id: str = ""
    total_paid_amount: Decimal | None = None


def criar_pagamento_pix(
    *, idempotency_key: str | None = None, amount_cents: int, order_id: str,
    payer_email: str, date_of_expiration: str | None = None,
    notification_url: str | None = None, payer_first_name: str = "",
    payer_last_name: str = "", payer_identification: dict[str, str] | None = None,
    envio_ambiguo_anterior: bool = False,
) -> ResultadoPix:
    try:
        resposta = MercadoPagoClient().criar_pagamento_pix(
            idempotency_key=idempotency_key,
            amount_cents=amount_cents,
            order_id=order_id,
            payer_email=payer_email,
            **({"date_of_expiration": date_of_expiration} if date_of_expiration else {}),
            **({"notification_url": notification_url} if notification_url else {}),
            **({"payer_first_name": payer_first_name} if payer_first_name else {}),
            **({"payer_last_name": payer_last_name} if payer_last_name else {}),
            **({"payer_identification": payer_identification} if payer_identification else {}),
            **({"envio_ambiguo_anterior": True} if envio_ambiguo_anterior else {}),
        )
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc), ambiguo=exc.ambiguo) from exc
    return _traduzir_resposta_pix(resposta)


def criar_pagamento_card(
    *, idempotency_key: str, amount_cents: int, order_id: str,
    card_token: str, installments: int, payment_method_id: str,
    payer_email: str, issuer_id: str | None = None, device_id: str = "",
    payer_first_name: str = "", payer_last_name: str = "",
    payer_identification: dict[str, str] | None = None,
    items: list[dict[str, Any]] | None = None,
    notification_url: str | None = None,
    envio_ambiguo_anterior: bool = False,
) -> ResultadoCard:
    try:
        resposta = MercadoPagoClient().criar_pagamento_cartao(
            idempotency_key=idempotency_key, amount_cents=amount_cents,
            order_id=order_id, card_token=card_token,
            installments=installments, payment_method_id=payment_method_id,
            payer_email=payer_email, issuer_id=issuer_id, device_id=device_id,
            payer_first_name=payer_first_name, payer_last_name=payer_last_name,
            payer_identification=payer_identification, items=items,
            notification_url=notification_url,
            envio_ambiguo_anterior=envio_ambiguo_anterior,
        )
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc), ambiguo=exc.ambiguo) from exc
    return traduzir_pagamento_card(resposta)


def traduzir_pagamento_card(resposta: dict[str, Any]) -> ResultadoCard:
    payment_id = _exigir_id(resposta, ambiguo=True)
    status = str(resposta.get("status") or "").strip()
    if not status:
        raise FalhaNoProvedor("resposta de cartao do Mercado Pago sem status", ambiguo=True)
    return ResultadoCard(
        payment_id=payment_id, status=status,
        reason_code=str(resposta.get("status_detail") or ""),
        **_dados_financeiros_mp(resposta),
    )


def buscar_por_referencia(*, external_reference: str) -> list[dict[str, Any]]:
    try:
        return MercadoPagoClient().buscar_por_referencia(external_reference)
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc), ambiguo=exc.ambiguo) from exc


def estornar_pagamento(*, payment_id: str, idempotency_key: str) -> dict[str, Any]:
    try:
        return MercadoPagoClient().estornar_pagamento(
            payment_id=payment_id, idempotency_key=idempotency_key
        )
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc), ambiguo=exc.ambiguo) from exc


class AppmaxGateway:
    """Uma sessão por tentativa reaproveita o OAuth sem expor providers a methods."""

    def __init__(self) -> None:
        self._client = AppmaxClient()

    def preparar(self) -> None:
        self._chamar(self._client.preparar)

    def consultar_parcelas(self, *, total_value: int) -> dict[str, Any]:
        return self._chamar(self._client.consultar_parcelas, total_value)

    def criar_cliente(self, *, body: dict[str, Any]) -> dict[str, Any]:
        return self._chamar(self._client.criar_cliente, body)

    def criar_pedido(self, *, body: dict[str, Any]) -> dict[str, Any]:
        return self._chamar(self._client.criar_pedido, body)

    def criar_pagamento_cartao(self, *, body: dict[str, Any]) -> dict[str, Any]:
        return self._chamar(self._client.criar_pagamento_cartao, body)

    def criar_pagamento_pix(self, *, body: dict[str, Any]) -> dict[str, str]:
        return self._chamar(self._client.criar_pagamento_pix, body)

    def consultar_pedido(self, *, order_id: int) -> dict[str, Any]:
        return self._chamar(self._client.consultar_pedido, order_id)

    def registrar_resposta_pix(self, operation_id: str) -> AbstractContextManager[None]:
        from pagamentos.providers.appmax.client import registrar_resposta_pix

        return registrar_resposta_pix(operation_id)

    def solicitar_estorno(self, *, order_id: int, tipo: str = "total") -> dict[str, Any]:
        return self._chamar(self._client.solicitar_estorno, order_id, tipo)

    @staticmethod
    def _chamar(funcao: Callable[..., T], *args: Any) -> T:
        try:
            return funcao(*args)
        except AppmaxError as exc:
            raise FalhaNoProvedor(
                str(exc), ambiguo=exc.ambiguo, diagnostico=exc.diagnostico
            ) from None


def nova_sessao_appmax() -> AppmaxGateway:
    return AppmaxGateway()


def consultar_status_do_pagamento(*, payment_id: str) -> StatusDoPagamento:
    """Usada pelos webhook handlers: o `data.id` assinado entra, o status QUE A
    API RESPONDEU sai. Fail-closed como as criações — provedor fora do ar,
    corpo ilegível ou resposta sem `status` levantam FalhaNoProvedor (o webhook
    responde 5xx e o MP reentrega; nunca se decide sem a fonte de verdade)."""
    try:
        resposta = MercadoPagoClient().obter_pagamento(payment_id)
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc), ambiguo=exc.ambiguo) from exc
    payment_id_confirmado = _exigir_id(resposta)
    try:
        status = str(resposta["status"] or "").strip()
    except KeyError as exc:
        raise FalhaNoProvedor(
            "consulta ao Mercado Pago sem status; confira a resposta do provedor"
        ) from exc
    if not status:
        raise FalhaNoProvedor(
            "consulta ao Mercado Pago sem `status` no corpo "
            f"(payment_id={payment_id_confirmado}) — sem ele nao ha decisao "
            "possivel para o webhook."
        )
    return StatusDoPagamento(
        payment_id=payment_id_confirmado,
        status=status,
        reason_code=str(resposta.get("status_detail") or ""),
        **_dados_financeiros_mp(resposta),
    )


def _dados_financeiros_mp(resposta: dict[str, Any]) -> dict[str, Any]:
    """A tradução retém apenas o necessário para conferir a cobrança."""
    def valor_decimal(chave: str, origem: dict[str, Any]) -> Decimal | None:
        bruto = origem.get(chave)
        if isinstance(bruto, bool) or not isinstance(bruto, (str, int, float, Decimal)):
            return None
        try:
            valor = Decimal(str(bruto))
        except InvalidOperation:
            return None
        return valor if valor.is_finite() else None

    referencia = resposta.get("external_reference")
    moeda = resposta.get("currency_id")
    parcelas = resposta.get("installments")
    detalhes = resposta.get("transaction_details")
    if not isinstance(detalhes, dict):
        detalhes = {}
    return {
        "external_reference": referencia if isinstance(referencia, str) else "",
        "transaction_amount": valor_decimal("transaction_amount", resposta),
        "installments": parcelas if type(parcelas) is int and parcelas > 0 else None,
        "currency_id": moeda if isinstance(moeda, str) else "",
        "total_paid_amount": valor_decimal("total_paid_amount", detalhes),
    }


# ---------------------------------------------------------------------------
# Tradução — um 2xx do provedor NÃO é, sozinho, um pagamento
# ---------------------------------------------------------------------------
# Estas funções são a segunda metade do fail-closed: mesmo com status 200, o
# corpo precisa descrever algo pagável. Traduzir campo ausente para string vazia
# (`str(resposta.get("id", ""))`) era o que transformava um corpo de ERRO num
# ResultadoPix de aparência normal, que seguia adiante como sucesso.


def _exigir_id(resposta: dict[str, Any], *, ambiguo: bool = False) -> str:
    try:
        payment_id = str(resposta["id"] or "").strip()
    except KeyError as exc:
        raise FalhaNoProvedor(
            "resposta do Mercado Pago sem id; confira a resposta antes de reconciliar",
            ambiguo=ambiguo,
        ) from exc
    if not payment_id:
        # Só as CHAVES do corpo entram na mensagem — nunca os valores, que podem
        # carregar dado do pagador para o log.
        raise FalhaNoProvedor(
            "resposta 2xx do Mercado Pago sem `id` de pagamento (campos "
            f"recebidos: {sorted(resposta)}). Sem id nao ha como reconciliar o "
            "webhook depois — a cobranca ficaria orfa.", ambiguo=ambiguo
        )
    return payment_id


def _traduzir_resposta_pix(resposta: dict[str, Any]) -> ResultadoPix:
    status = str(resposta.get("status") or "").strip()
    status_detail = str(resposta.get("status_detail") or "").strip()
    payment_id = _exigir_id(resposta, ambiguo=True)
    if not status:
        raise FalhaNoProvedor("resposta de Pix do Mercado Pago sem status", ambiguo=True)
    if status == "rejected":
        if recusa_antifraude_mp(status, status_detail):
            raise RecusaAntifraude(payment_id=payment_id, status_detail=status_detail)
        raise PixNaoPagavel(
            f"Pix recusado pelo Mercado Pago (payment_id={payment_id}, "
            f"status_detail={status_detail})",
            payment_id=payment_id, status=status, status_detail=status_detail,
        )
    if status in ("cancelled", "expired"):
        raise PixNaoPagavel(
            f"Pix indisponivel no Mercado Pago: {status}",
            payment_id=payment_id, status=status, status_detail=status_detail,
        )
    interacao = resposta.get("point_of_interaction") or {}
    dados = interacao.get("transaction_data") or {}
    qr_code = str(dados.get("qr_code") or "")
    if not qr_code:
        raise FalhaNoProvedor(
            f"resposta de Pix do Mercado Pago sem qr_code (payment_id={payment_id}). "
            "O copia-e-cola e a unica coisa que o cliente precisa para pagar; sem "
            "ele a tela de Pix nasce em branco.", ambiguo=True
        )
    return ResultadoPix(
        payment_id=payment_id,
        qr_code=qr_code,
        # `qr_code_base64` é a IMAGEM do QR — cosmética. O copia-e-cola acima já
        # basta para pagar (e o front consegue desenhar o QR a partir dele), então
        # a ausência dele NÃO derruba a cobrança. A fronteira do fail-closed aqui
        # é "o cliente consegue pagar?", não "a resposta veio perfeita?".
        qr_code_base64=str(dados.get("qr_code_base64") or ""),
        expires_at=_traduzir_expiracao(resposta.get("date_of_expiration")),
    )


def _traduzir_expiracao(bruto: Any) -> datetime | None:
    """Ausente é legítimo (o contrato permite `expires_at: null`). Presente e
    ilegível, não: significa que a forma da resposta mudou sob nossos pés. Antes
    isso era um `ValueError` cru vazando de `datetime.fromisoformat` — 500 sem
    nome; agora é falha nomeada, igual aos outros campos."""
    if not isinstance(bruto, str) or not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto)
    except ValueError as exc:
        raise FalhaNoProvedor(
            f"date_of_expiration ilegivel na resposta do Mercado Pago: {bruto!r}"
        ) from exc
