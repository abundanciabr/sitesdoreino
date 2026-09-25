# pagamentos/core/gateway.py  # [RECEITA:R1 v1]
# [INV-P9] Única costura entre methods/* e providers/*. methods/pix e methods/card
# chamam SÓ estas funções — nunca importam providers.* direto (garantido em
# check-time por .importlinter, contrato "metodos-so-falam-com-core"). Os tipos de
# retorno (ResultadoPix/ResultadoCard) são vocabulário do domínio, definidos aqui —
# não vazam o formato de resposta do Mercado Pago para methods/*.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable
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


@dataclass(frozen=True)
class ResultadoPix:
    payment_id: str
    qr_code: str
    qr_code_base64: str
    expires_at: datetime | None


@dataclass(frozen=True)
class StatusDoPagamento:
    """Resultado da CONSULTA a um pagamento existente (GET) — a fonte de
    verdade que os webhook handlers usam no lugar do corpo não assinado."""

    payment_id: str
    status: str  # status cru do provider (approved/rejected/cancelled/...)
    reason_code: str  # status_detail do provider ("" quando ausente)


def criar_pagamento_pix(
    *, idempotency_key: str, amount_cents: int, order_id: str, payer_email: str
) -> ResultadoPix:
    try:
        resposta = MercadoPagoClient().criar_pagamento_pix(
            idempotency_key=idempotency_key,
            amount_cents=amount_cents,
            order_id=order_id,
            payer_email=payer_email,
        )
    except MercadoPagoError as exc:
        raise FalhaNoProvedor(str(exc)) from exc
    return _traduzir_resposta_pix(resposta)


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
        raise FalhaNoProvedor(str(exc)) from exc
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
    )


# ---------------------------------------------------------------------------
# Tradução — um 2xx do provedor NÃO é, sozinho, um pagamento
# ---------------------------------------------------------------------------
# Estas funções são a segunda metade do fail-closed: mesmo com status 200, o
# corpo precisa descrever algo pagável. Traduzir campo ausente para string vazia
# (`str(resposta.get("id", ""))`) era o que transformava um corpo de ERRO num
# ResultadoPix de aparência normal, que seguia adiante como sucesso.


def _exigir_id(resposta: dict[str, Any]) -> str:
    try:
        payment_id = str(resposta["id"] or "").strip()
    except KeyError as exc:
        raise FalhaNoProvedor(
            "resposta do Mercado Pago sem id; confira a resposta antes de reconciliar"
        ) from exc
    if not payment_id:
        # Só as CHAVES do corpo entram na mensagem — nunca os valores, que podem
        # carregar dado do pagador para o log.
        raise FalhaNoProvedor(
            "resposta 2xx do Mercado Pago sem `id` de pagamento (campos "
            f"recebidos: {sorted(resposta)}). Sem id nao ha como reconciliar o "
            "webhook depois — a cobranca ficaria orfa."
        )
    return payment_id


def _traduzir_resposta_pix(resposta: dict[str, Any]) -> ResultadoPix:
    payment_id = _exigir_id(resposta)
    interacao = resposta.get("point_of_interaction") or {}
    dados = interacao.get("transaction_data") or {}
    qr_code = str(dados.get("qr_code") or "")
    if not qr_code:
        raise FalhaNoProvedor(
            f"resposta de Pix do Mercado Pago sem qr_code (payment_id={payment_id}). "
            "O copia-e-cola e a unica coisa que o cliente precisa para pagar; sem "
            "ele a tela de Pix nasce em branco."
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
