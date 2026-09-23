# pagamentos/core/tentativas.py
# A máquina de estados de UMA tentativa de cobrar. Mora em core/ porque é
# vocabulário de domínio (AGENTS.pagamentos: core/ é dono de "modelos, ledger,
# outbox"), e methods/card a usa sem enxergar providers.* (INV-P9).
#
# O ponto inteiro deste arquivo é que `executar_tentativa` seja o ÚNICO caminho
# até o provedor. Quem chama entrega a função que fala com a rede; quem grava,
# bloqueia e fecha é daqui. Assim "nenhuma chamada externa sem tentativa
# persistida antes" deixa de ser combinado e vira a única forma de chamar.
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from pagamentos.core.models import (
    ESTADOS_EM_ABERTO,
    ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO,
    Intent,
    PaymentAttempt,
    PaymentOperation,
)

_MOTIVO_MAX = 120
_DIGITOS_LONGOS = re.compile(r"\d{6,}")
_NAO_CODIGO = re.compile(r"[^a-z0-9]+")
# Chaves cujo VALOR nunca entra no hash em claro. O valor não some: entra o
# digest dele, para que dois cartões diferentes continuem produzindo hashes
# diferentes (um hash que ignora o token não serve de evidência de nada).
_CAMPOS_SENSIVEIS = frozenset(
    {
        "token",
        "card_token",
        "number",
        "card_number",
        "cvv",
        "security_code",
        "holder_document_number",
        "document",
        "document_number",
        "cpf",
        "email",
        "phone",
        "first_name",
        "last_name",
        "holder_name",
        "ip",
        "client_secret",
        "access_token",
        "authorization",
    }
)


class TentativaBloqueada(Exception):
    """Existe uma tentativa que impede um novo envio para este Intent.

    Quem pega decide o que mostrar pelo `estado`: `approved` já foi pago,
    `sending` está em voo neste instante, `reconciliation_required` espera a
    consulta ao provedor. Nenhum deles é motivo para reenviar.
    """

    def __init__(self, tentativa: PaymentAttempt) -> None:
        super().__init__(
            f"tentativa {tentativa.operation_id} em {tentativa.state} bloqueia "
            "um novo envio para este intent; feche a tentativa aberta com uma "
            "consulta ao provedor antes de tentar de novo"
        )
        self.tentativa = tentativa
        self.estado = tentativa.state


class EnvioNaoChegou(Exception):
    """A função de envio levanta isto quando tem CERTEZA de que nada saiu da
    nossa máquina (DNS, conexão recusada, corpo inválido rejeitado antes de
    sair). Só nesse caso a tentativa fecha como `failed` e libera a próxima."""


class ResultadoAmbiguo(Exception):
    """A função de envio levanta isto quando a requisição partiu e o resultado
    não voltou (timeout depois do envio). A cobrança pode existir lá fora."""


@dataclass(frozen=True)
class ResultadoDoProvedor:
    """O que o provedor respondeu, traduzido para o vocabulário desta casa."""

    aprovada: bool | None
    provider_reference_id: str
    external_order_id: str = ""
    motivo: str = ""


def executar_tentativa(
    *,
    intent: Intent,
    provider: str,
    corpo: Mapping[str, Any],
    enviar: Callable[[PaymentAttempt], ResultadoDoProvedor],
    installments: int = 1,
    external_order_id: str = "",
    effective_amount_cents: int | None = None,
    registrar_resultado: (
        Callable[[PaymentAttempt, ResultadoDoProvedor], None] | None
    ) = None,
) -> PaymentAttempt:
    """Abre a tentativa, manda, e fecha com o que voltou.

    `enviar` recebe a tentativa JÁ gravada e devolve `ResultadoDoProvedor`, ou
    levanta `EnvioNaoChegou` (nada saiu) ou `ResultadoAmbiguo` (saiu e não
    sabemos). Qualquer outra exceção é tratada como ambígua de propósito: não
    saber o que aconteceu tem o mesmo risco de saber que houve timeout, e o
    padrão seguro é bloquear.

    Levanta `TentativaBloqueada` quando o Intent já tem tentativa viva. Uma
    tentativa recusada NÃO bloqueia: é ela que devolve ao comprador o direito
    de pagar com outro cartão.
    """
    tentativa, nova = _abrir(
        intent=intent,
        provider=provider,
        corpo=corpo,
        installments=installments,
        external_order_id=external_order_id,
        effective_amount_cents=effective_amount_cents,
    )
    if not nova:
        return tentativa
    try:
        resultado = enviar(tentativa)
    except EnvioNaoChegou as exc:
        _fechar(tentativa, state="failed", motivo=str(exc))
        raise
    except Exception as exc:
        _fechar(tentativa, state="reconciliation_required", motivo=str(exc))
        raise
    estado = (
        "approved"
        if resultado.aprovada
        else "rejected" if resultado.aprovada is False else "pending"
    )
    with transaction.atomic():
        finalizada = _fechar(
            tentativa,
            state=estado,
            motivo=resultado.motivo,
            resultado=resultado,
        )
        if registrar_resultado is not None:
            registrar_resultado(finalizada, resultado)
    return finalizada


def fechar_reconciliacao(
    tentativa: PaymentAttempt,
    *,
    resultado: ResultadoDoProvedor,
    registrar_resultado: (
        Callable[[PaymentAttempt, ResultadoDoProvedor], None] | None
    ) = None,
) -> PaymentAttempt:
    """Fecha uma tentativa em aberto com o que uma CONSULTA ao provedor disse.

    É a única saída de `reconciliation_required` (e também de um `sending` que
    ficou órfão porque o processo morreu no meio). O resultado tem de vir de
    uma consulta de verdade: nunca se fecha por suposição, porque fechar como
    recusada uma cobrança que existe libera a segunda cobrança.
    """
    estado = (
        "approved"
        if resultado.aprovada
        else "rejected" if resultado.aprovada is False else "pending"
    )
    with transaction.atomic():
        travada = PaymentAttempt.objects.select_for_update().get(pk=tentativa.pk)
        if travada.state not in ESTADOS_EM_ABERTO:
            tentativa.refresh_from_db()
            return travada
        finalizada = _fechar(
            travada,
            state=estado,
            motivo=resultado.motivo,
            resultado=resultado,
        )
        if registrar_resultado is not None:
            registrar_resultado(finalizada, resultado)
        return finalizada


def tentativas_do_site(platform_site_id: str) -> QuerySet[PaymentAttempt]:
    """O caminho de leitura desta tabela. Toda consulta nasce presa a um site:
    uma loja não enxerga a tentativa de pagamento da loja vizinha (Lei 9)."""
    return PaymentAttempt.objects.filter(platform_site_id=platform_site_id)


def hash_da_tentativa(corpo: Mapping[str, Any]) -> str:
    return _hash_do_corpo(corpo)


def _abrir(
    *,
    intent: Intent,
    provider: str,
    corpo: Mapping[str, Any],
    installments: int,
    external_order_id: str,
    effective_amount_cents: int | None,
) -> tuple[PaymentAttempt, bool]:
    """`durable=True` é o guarda de "persistida ANTES do envio": ele recusa
    rodar dentro de uma transação já aberta, e é isso que garante que, ao sair
    daqui, a linha está COMMITADA de verdade. Sem ele, um chamador que
    envolvesse tudo num `atomic()` faria a chamada externa com a linha ainda
    invisível, e um crash apagaria o rastro da cobrança."""
    request_hash = _hash_do_corpo(corpo)
    try:
        with transaction.atomic(durable=True):
            Intent.objects.select_for_update().get(pk=intent.pk)
            bloqueadora = _tentativa_viva(intent)
            if bloqueadora is not None:
                raise TentativaBloqueada(bloqueadora)
            anterior = PaymentAttempt.objects.filter(
                intent=intent, request_hash=request_hash
            ).first()
            if anterior is not None:
                return anterior, False
            return (
                PaymentAttempt.objects.create(
                    intent=intent,
                    platform_site_id=intent.site_id,
                    provider=provider,
                    amount_cents=intent.amount_cents,
                    effective_amount_cents=(
                        effective_amount_cents or intent.amount_cents
                    ),
                    previous_intent_status=intent.status,
                    installments=installments,
                    external_order_id=external_order_id,
                    request_hash=request_hash,
                    state="sending",
                ),
                True,
            )
    except IntegrityError:
        # A checagem acima perde a corrida do duplo clique; o índice único
        # parcial não perde. Quem chegou depois recebe a mesma recusa clara.
        anterior = PaymentAttempt.objects.filter(
            intent=intent, request_hash=request_hash
        ).first()
        if anterior is not None:
            return anterior, False
        bloqueadora = _tentativa_viva(intent)
        if bloqueadora is None:
            raise
        raise TentativaBloqueada(bloqueadora) from None


def abrir_operacao(
    tentativa: PaymentAttempt, *, tipo: str, corpo: Mapping[str, Any]
) -> PaymentOperation:
    if tipo not in {"customer", "order", "payment"}:
        raise ValueError(f"tipo de operação Appmax inválido: {tipo}")
    with transaction.atomic(durable=True):
        return PaymentOperation.objects.create(
            attempt=tentativa,
            platform_site_id=tentativa.platform_site_id,
            operation_type=tipo,
            request_hash=_hash_do_corpo(corpo),
        )


def finalizar_operacao(
    operacao: PaymentOperation,
    *,
    state: str,
    provider_resource_id: str = "",
    customer_id: str = "",
    external_order_id: str = "",
) -> PaymentOperation:
    if state not in {"completed", "failed", "reconciliation_required"}:
        raise ValueError(f"estado de operação Appmax inválido: {state}")
    with transaction.atomic():
        tentativa = PaymentAttempt.objects.select_for_update().get(
            pk=operacao.attempt_id
        )
        operacao.state = state
        operacao.provider_resource_id = provider_resource_id
        operacao.save(update_fields=["state", "provider_resource_id", "updated_at"])
        if customer_id:
            tentativa.customer_id = customer_id
        if external_order_id:
            tentativa.external_order_id = external_order_id
        if customer_id or external_order_id:
            campos = ["updated_at"]
            if customer_id:
                campos.append("customer_id")
            if external_order_id:
                campos.append("external_order_id")
            tentativa.save(update_fields=campos)
    return operacao


def _tentativa_viva(intent: Intent) -> PaymentAttempt | None:
    return PaymentAttempt.objects.filter(
        intent=intent, state__in=ESTADOS_QUE_BLOQUEIAM_NOVO_ENVIO
    ).first()


def _fechar(
    tentativa: PaymentAttempt,
    *,
    state: str,
    motivo: str,
    resultado: ResultadoDoProvedor | None = None,
) -> PaymentAttempt:
    tentativa.state = state
    tentativa.reason = _sanitizar_motivo(motivo)
    campos = ["state", "reason", "updated_at"]
    if resultado is not None:
        tentativa.provider_reference_id = resultado.provider_reference_id
        campos.append("provider_reference_id")
        if resultado.external_order_id:
            tentativa.external_order_id = resultado.external_order_id
            campos.append("external_order_id")
    tentativa.save(update_fields=campos)
    return tentativa


def _sanitizar_motivo(bruto: str) -> str:
    """O motivo vem de fora e termina em tela e em log. Entra como código:
    minúsculas, sem pontuação e sem sequência longa de dígitos, que é a forma
    de um cartão, de um CPF ou de um telefone vazarem por descuido."""
    sem_numeros_longos = _DIGITOS_LONGOS.sub("", bruto.lower())
    return _NAO_CODIGO.sub("_", sem_numeros_longos).strip("_")[:_MOTIVO_MAX].strip("_")


def _hash_do_corpo(corpo: Mapping[str, Any]) -> str:
    canonico = json.dumps(
        _sanitizar(corpo), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _sanitizar(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {
            str(chave): (
                _digerir(item)
                if str(chave).lower() in _CAMPOS_SENSIVEIS
                else _sanitizar(item)
            )
            for chave, item in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_sanitizar(item) for item in valor]
    return valor


def _digerir(valor: Any) -> str:
    return hashlib.sha256(str(valor).encode("utf-8")).hexdigest()
