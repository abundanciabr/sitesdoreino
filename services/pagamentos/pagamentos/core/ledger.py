# pagamentos/core/ledger.py
# O ÚNICO caminho por onde o dinheiro de uma Intent muda de estado. Mora em
# core/ porque é vocabulário de domínio (AGENTS.pagamentos: "core/ ... modelos,
# ledger, outbox"), e methods/pix e methods/card o usam sem enxergar
# providers.* (INV-P9).
#
# [INV-P6] O ponto inteiro deste arquivo: transição de estado e aviso às outras
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
from pagamentos.core.models import ESTADOS_FINANCEIROS, Intent

logger = logging.getLogger(__name__)

# Monotonicidade em forma de dado: para cada fato financeiro, os estados de onde
# ele PODE vir. O que não está na tabela não acontece. É por isso que `approved`
# não volta para `pending` (pendente não é destino de fato nenhum) e que
# `refunded` só existe depois de `approved` (não se devolve dinheiro que não
# entrou). Estorno e contestação são o MESMO destino, `refunded`, porque o
# ledger registra que o dinheiro voltou; o que diferencia os dois é o `motivo`
# do evento (contracts/eventos/pagamento.estornado.v2.json), não o estado.
ORIGENS_ADMITIDAS: dict[str, frozenset[str]] = {
    "approved": frozenset({"created", "pending"}),
    "rejected": frozenset({"created", "pending"}),
    "expired": frozenset({"created", "pending"}),
    "refunded": frozenset({"approved"}),
}


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
            return False  # [INV-P3] o mesmo fato de novo: o ledger já o tem
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
            models.emitir(evento, dados, version=version)
        _exigir_um_aviso(avisos, evento=evento, novo_status=novo_status, intent=travada)
    transaction.on_commit(models.relay_apos_commit)
    intent.refresh_from_db()
    return True


def transicionar_e_emitir(
    *, mp_payment_id: str, novo_status: str, evento: str, dados: dict[str, Any]
) -> bool:
    """[INV-P3] [INV-P6] A porta dos webhook handlers de methods/pix e
    methods/card: acha a intent pelo id do pagamento no provedor e entrega o
    fato ao ledger. Pagamento desconhecido é ignorado sem efeito (um webhook com
    assinatura válida para um id que não é nosso não pode criar nada)."""
    intent = Intent.objects.filter(provider_payment_id=mp_payment_id).first()
    if intent is None:
        return False
    return registrar_fato(intent, novo_status=novo_status, evento=evento, dados=dados)


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
