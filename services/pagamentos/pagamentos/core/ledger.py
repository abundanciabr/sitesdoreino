# pagamentos/core/ledger.py
# O ÚNICO caminho por onde o dinheiro de uma Intent muda de estado. Mora em
# core/ porque é vocabulário de domínio (AGENTS.pagamentos: "core/ ... modelos,
# ledger, outbox"), e methods/pix e methods/card o usam sem enxergar
# providers.*.
#
# O ponto inteiro deste arquivo: transição de estado e aviso às outras
# células são o MESMO ato. Antes dele, a regra existia em prosa ("chame emitir()
# dentro da mesma transação") e era cumprida por disciplina; a confirmação
# síncrona do cartão não cumpria, e aprovava pagamento sem avisar ninguém. Aqui
# a regra é de construção, em três camadas:
#
#   1. `registrar_fato` monta a transição e o aviso juntos. Não há parâmetro
#      para pular o aviso: quem quer o estado leva o evento junto.
#   2. Antes de commitar, a transação confere que nasceu EXATAMENTE um aviso.
#      Zero (alguém apagou a emissão) ou dois (o fato mudou o ledger duas vezes)
#      derrubam a transação inteira: o estado também não fica.
#   3. `Intent.save()` recusa gravar status financeiro fora da janela que este
#      módulo abre (`models.transicao_do_ledger`). Não existe caminho paralelo.
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from pagamentos.core import models
from pagamentos.core.models import ESTADOS_FINANCEIROS, Intent, OutboxEvent, PaymentAttempt

logger = logging.getLogger(__name__)

# Monotonicidade em forma de dado: para cada fato financeiro, os estados de onde
# ele PODE vir. O que não está na tabela não acontece. É por isso que `approved`
# não volta para `pending` (pendente não é destino de fato nenhum) e que
# `refunded` só existe depois de `approved` (não se devolve dinheiro que não
# entrou). Estorno e contestação são o MESMO destino, `refunded`, porque o
# ledger registra que o dinheiro voltou; o que diferencia os dois é o `motivo`
# do evento, não o estado.
ORIGENS_ADMITIDAS: dict[str, frozenset[str]] = {
    "approved": frozenset({"created", "pending", "rejected", "expired"}),
    "rejected": frozenset({"created", "pending"}),
    "expired": frozenset({"created", "pending"}),
    "refunded": frozenset({"approved"}),
}


REFERENCIAS_DO_PEDIDO = ("oportunidade_ref", "oferta_ref", "ambiente")


def com_referencias_do_pedido(dados: dict[str, Any], intent: Intent) -> dict[str, Any]:
    """Ecoa no aviso as referências opacas que o checkout pôs no `metadata`
    (mesma técnica do `product_id`): a oportunidade do CRM, a oferta e, no
    pedido de teste, `ambiente: sandbox` (o CRM não conta compra de teste como
    venda). Assim quem acompanha a venda casa o pagamento sem consultar outra
    célula. Sem elas no `metadata`, o aviso sai exatamente como antes."""
    metadata = intent.metadata if isinstance(intent.metadata, dict) else {}
    extras = {
        campo: metadata[campo]
        for campo in REFERENCIAS_DO_PEDIDO
        if isinstance(metadata.get(campo), str) and metadata[campo] and campo not in dados
    }
    # A credencial de teste do Mercado Pago também pode começar com APP_USR.
    # A marca acompanha a aprovação até a matrícula, inclusive em intents
    # antigas que nasceram sem o ambiente no metadata.
    from django.conf import settings
    from pagamentos.core.ambiente_mp import mp_em_teste

    provider = dados.get("provider")
    if ((provider == "appmax" and "sandboxappmax.com.br" in settings.APPMAX_API_URL.lower())
            or (provider == "mercadopago" and mp_em_teste()
                and metadata.get("mp_ambiente") != "producao")):
        extras["ambiente"] = "sandbox"
    return {**dados, **extras} if extras else dados


class AvisoAusente(RuntimeError):
    """A transição de estado não produziu exatamente um aviso na outbox.

    Nunca chega a quem paga: a transação que a levanta volta atrás inteira, e a
    intent fica como estava. É o guarda que transforma "lembre de emitir o
    evento" em impossibilidade.
    """


def registrar_fato(
    intent: Intent,
    *,
    novo_status: str,
    evento: str,
    dados: dict[str, Any],
    version: int = 1,
) -> bool:
    """Grava um fato financeiro: o estado novo da intent e o aviso, juntos.

    Devolve True quando o ledger mudou, e False quando o fato não muda nada e
    ignorá-lo é o certo: a intent já está nesse estado (reentrega do mesmo
    webhook, INV-P3) ou o fato chegou fora de ordem (uma recusa depois da
    aprovação). Nos dois casos nada é gravado e nenhum aviso sai, que é o
    sentido de "cada fato muda o ledger UMA vez".

    Levanta `ValueError` quando o destino não é um fato financeiro (voltar para
    `pending` ou `created` não é transição, é bug de quem chamou) e
    `AvisoAusente` quando a transição não gerou exatamente um aviso.
    """
    _exigir_fato_financeiro(novo_status)
    with transaction.atomic():
        # select_for_update fecha a corrida de duas entregas simultâneas do
        # mesmo webhook: a segunda espera a primeira commitar e então enxerga o
        # estado novo, caindo na dedup logo abaixo.
        travada = Intent.objects.select_for_update().filter(pk=intent.pk).first()
        if travada is None:
            return False
        if travada.status == novo_status:
            return False  # o mesmo fato de novo: o ledger já o tem
        if travada.status not in ORIGENS_ADMITIDAS[novo_status]:
            logger.warning(
                "fato %s ignorado para a intent %s: ela esta em %s, e esse fato "
                "so acontece a partir de %s",
                evento,
                travada.pk,
                travada.status,
                sorted(ORIGENS_ADMITIDAS[novo_status]),
            )
            return False
        with models.transicao_do_ledger() as avisos:
            travada.status = novo_status
            travada.save(update_fields=["status", "updated_at"])
            models.emitir(evento, com_referencias_do_pedido(dados, travada), version=version)
        _exigir_um_aviso(avisos, evento=evento, novo_status=novo_status, intent=travada)
    transaction.on_commit(models.relay_apos_commit)
    intent.refresh_from_db()
    return True


def marcar_tentativa_pendente(intent: Intent) -> None:
    """Marca uma nova cobrança em análise sem inventar um fato financeiro.

    A tentativa e seus IDs externos já foram commitados antes desta chamada.
    Um `rejected` anterior deixa de representar o pedido atual enquanto o novo
    pagamento está em análise; a recusa histórica permanece no evento v2.
    """
    with transaction.atomic():
        travada = Intent.objects.select_for_update().get(pk=intent.pk)
        if travada.status not in {"created", "rejected", "pending"}:
            raise ValueError(
                f"tentativa de cartão não pode entrar em análise com intent em {travada.status!r}"
            )
        if travada.status == "pending" and not travada.provider_payment_id:
            return
        with models.transicao_do_ledger():
            travada.status = "pending"
            travada.provider_payment_id = ""
            travada.save(update_fields=["status", "provider_payment_id", "updated_at"])
    intent.refresh_from_db()


def transicionar_e_emitir(
    *, mp_payment_id: str, novo_status: str, evento: str, dados: dict[str, Any]
) -> bool:
    """A porta dos webhook handlers de methods/pix e
    methods/card: acha a intent pelo id do pagamento no provedor e entrega o
    fato ao ledger. Pagamento desconhecido é ignorado sem efeito (um webhook com
    assinatura válida para um id que não é nosso não pode criar nada)."""
    intent = Intent.objects.filter(provider_payment_id=mp_payment_id).first()
    if intent is None:
        return False
    return registrar_fato(intent, novo_status=novo_status, evento=evento, dados=dados)


def registrar_fato_da_tentativa(
    provider: str,
    provider_reference_id: str,
    *,
    novo_status: str,
    evento: str,
    dados: dict[str, Any],
    version: int = 2,
) -> str:
    """Aplica um fato da tentativa identificada pelo provedor.

    Retorna ``aplicado``, ``ignorado``, ``approved_duplicate`` ou
    ``desconhecido``. Uma tentativa anterior à mais recente nunca decide a
    intent; sua aprovação vira uma cobrança para estorno individual.
    """
    if not provider_reference_id:
        return "desconhecido"
    with transaction.atomic():
        tentativa = (PaymentAttempt.objects.filter(
            provider=provider, provider_reference_id=provider_reference_id
        ).order_by("-created_at", "-pk").first())
        if tentativa is None:
            return "desconhecido"
        intent = Intent.objects.select_for_update().get(pk=tentativa.intent_id)
        tentativa = PaymentAttempt.objects.select_for_update().get(pk=tentativa.pk)
        ultima = (PaymentAttempt.objects.filter(intent=intent)
                  .exclude(state="approved_duplicate")
                  .order_by("-created_at", "-pk").first())
        substituida = ultima is not None and ultima.pk != tentativa.pk
        aprovacoes_v2 = OutboxEvent.objects.filter(
            event="pagamento.aprovado", version=2,
            payload__payment_id=str(intent.pk),
        )
        aprovacao_desta_tentativa = aprovacoes_v2.filter(
            payload__provider=provider,
            payload__provider_reference_id=provider_reference_id,
        ).exists()
        if not aprovacao_desta_tentativa and not aprovacoes_v2.exists():
            # O livro antigo não identificava a empresa no evento. O ID que a
            # intent guardou e a referência da aprovação v1 identificam a
            # cobrança original sem tomar o state=approved como prova: _fechar
            # já põe esse state ANTES de chamar este método.
            aprovacao_desta_tentativa = (
                intent.status == "approved"
                and intent.provider_payment_id == provider_reference_id
                and OutboxEvent.objects.filter(
                    event="pagamento.aprovado", version=1,
                    payload__payment_id=str(intent.pk),
                    payload__mp_payment_id=provider_reference_id,
                ).exists()
            )
        if novo_status == "approved" and not aprovacao_desta_tentativa and (
            substituida or intent.status == "approved"
        ):
            if tentativa.state != "approved_duplicate":
                tentativa.state = "approved_duplicate"
                tentativa.save(update_fields=["state", "updated_at"])
                logger.error("cobranca_duplicada intent=%s tentativa=%s provider=%s", intent.pk, tentativa.pk, provider)
            agendar_estorno_duplicada(tentativa.pk)
            return "approved_duplicate"
        if tentativa.state == "approved_duplicate":
            if novo_status == "approved":
                agendar_estorno_duplicada(tentativa.pk)
            return "approved_duplicate"
        if tentativa.state == "approved" and novo_status != "approved":
            return "ignorado"
        if novo_status == "approved":
            tentativa.state = "approved"
        elif novo_status in {"rejected", "expired"} and tentativa.state in {"sending", "pending", "reconciliation_required"}:
            tentativa.state = "rejected"
            tentativa.reason = str(dados.get("reason_code") or "")[:120]
        tentativa.save(update_fields=["state", "reason", "updated_at"])
        if substituida:
            return "ignorado"
        if novo_status == "approved" and intent.status in {"rejected", "expired"}:
            logger.error("aprovacao_tardia intent=%s tentativa=%s provider=%s", intent.pk, tentativa.pk, provider)
        return "aplicado" if registrar_fato(
            intent, novo_status=novo_status, evento=evento, dados=dados, version=version
        ) else "ignorado"


_MOTIVOS_REVERSAO = {
    "appmax_estornado": "estorno",
    "appmax_chargeback_em_tratativa": "contestacao",
    "appmax_chargeback_em_disputa": "contestacao",
    "appmax_chargeback_perdido": "contestacao",
    "refunded": "estorno",
    "charged_back": "contestacao",
}


def emitir_reversao_confirmada(tentativa: PaymentAttempt, codigo: str) -> bool:
    """Emite uma reversão v2 uma única vez para a cobrança desta tentativa."""
    motivo = _MOTIVOS_REVERSAO[codigo]
    with transaction.atomic():
        travada = PaymentAttempt.objects.select_for_update().get(pk=tentativa.pk)
        if travada.state != "approved" or not travada.provider_reference_id:
            return False
        payload = {
            "platform_site_id": travada.platform_site_id,
            "provider": travada.provider,
            "provider_reference_id": travada.provider_reference_id,
            "motivo": motivo,
            # O checkout acha o pedido por aqui e o marca como reembolsado.
            "order_id": travada.intent.order_id,
        }
        if OutboxEvent.objects.filter(
            event="pagamento.reversao_confirmada", version=2,
            payload__platform_site_id=travada.platform_site_id,
            payload__provider=travada.provider,
            payload__provider_reference_id=travada.provider_reference_id,
        ).exists():
            return False
        models.emitir(
            "pagamento.reversao_confirmada",
            com_referencias_do_pedido(payload, travada.intent),
            version=2,
        )
    transaction.on_commit(models.relay_apos_commit)
    return True


def agendar_estorno_duplicada(tentativa_id: int) -> None:
    transaction.on_commit(lambda: _estornar_duplicada(tentativa_id))


def _estornar_duplicada(tentativa_id: int) -> None:
    """O callback corre após o commit externo, exigido pelo registro durável."""
    from pagamentos.core.estorno import estornar

    try:
        estornar(PaymentAttempt.objects.get(pk=tentativa_id), "cobranca_duplicada")
    except Exception as exc:
        # A aprovação duplicada já foi gravada. A entrega do webhook não deve
        # voltar ao início e gerar um segundo fato por falha do provedor.
        logger.error("estorno_automatico_pendente tentativa=%s erro=%s", tentativa_id, type(exc).__name__)


def _exigir_fato_financeiro(novo_status: str) -> None:
    if novo_status in ORIGENS_ADMITIDAS:
        return
    raise ValueError(
        f"{novo_status!r} nao e um fato financeiro desta celula; o ledger "
        f"registra apenas {sorted(ORIGENS_ADMITIDAS)}. Transicao financeira e de "
        "mao unica: nenhum fato leva a intent de volta para pending ou created."
    )


def _exigir_um_aviso(
    avisos: list[str], *, evento: str, novo_status: str, intent: Intent
) -> None:
    if avisos == [evento]:
        return
    raise AvisoAusente(
        f"a transicao da intent {intent.pk} para {novo_status!r} gravou "
        f"{avisos} na outbox, e o esperado era exatamente um {evento!r}. Nada "
        "foi gravado: a transacao inteira volta atras, porque estado de dinheiro "
        "sem aviso deixa a compra paga aqui e invisivel para as outras celulas. "
        "Emita o evento dentro de core.ledger.registrar_fato."
    )
