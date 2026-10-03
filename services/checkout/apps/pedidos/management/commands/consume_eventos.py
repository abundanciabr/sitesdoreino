# apps/pedidos/management/commands/consume_eventos.py  # [RECEITA:R4 v1] adaptado
# Consome pagamento.aprovado/pagamento.recusado/pix.expirado e move o status do
# pedido; pix.codigo_trocado atualiza apenas o código Pix do pedido pendente.
#
# DUAS VERSÕES AO MESMO TEMPO: pagamento.aprovado.v2 e pagamento.recusado.v2
# tiraram o nome do fornecedor do contrato (saiu `mp_payment_id`, entrou o par
# `provider` mais `provider_reference_id`; `site_id` virou `platform_site_id`).
# O v1 continua sendo emitido até o último consumidor migrar,
# então o MESMO pagamento chega aqui nas duas versões, com `event_id`
# diferente em cada uma.
#
# Dedup: pela IDENTIDADE LÓGICA do fato, não pelo `event_id` — que muda entre
# as versões e por isso não deduplicaria nada. Quem define a identidade é o
# contrato, no campo `x-ponte-do-v1` de cada schema v2, e a tabela AVISOS
# abaixo é a transcrição literal dele, conferida contra o schema em disco por
# tests/test_aviso_de_pagamento_v1_e_v2.py. As duas cartas têm pontes
# DIFERENTES: a aprovação atravessa pelo par do fornecedor, a recusa pelo
# `payment_id`, porque a recusa v1 nunca carregou referência do fornecedor sob
# nome nenhum.
#
# O UPDATE condicional de status (WHERE status=aguardando_pagamento) continua
# aqui: ele é o que impede um evento atrasado de fazer um pedido já decidido
# voltar para outro estado. O que ele nunca soube fazer é distinguir dois fatos
# do mesmo pedido de um fato só que chegou duas vezes — isso é FatoAplicado.
#
# Reentrega do PEL: mensagem cujo handler estourou ficava em
# XPENDING do grupo para sempre — xreadgroup ">" só entrega mensagem NOVA, e
# ninguém chamava XAUTOCLAIM. Agora, a cada iteração do loop e ANTES do ">",
# reivindicamos as presas (idle >= IDLE_MS_REENTREGA) e as reprocessamos pelo
# MESMO caminho do handler das novas. Quem chega à MAX_ENTREGAS-ésima entrega
# NÃO é reprocessado: vai para a fila morta `<stream>.dlq` (payload original +
# motivo/delivery_count/movida_em), é ACKado no stream original e deixa um log
# ERROR com o event_id. Desenho e nomes são convenção do lote — as 4 células
# consumidoras implementam exatamente isto.
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q

from django.utils import timezone as django_timezone

from apps.pedidos.emitir import emitir
from apps.pedidos.models import FatoAplicado
from apps.pedidos.models import Order as OrderModel

logger = logging.getLogger(__name__)

GRUPO = "checkout"
CONSUMIDOR = "worker-1"
IDLE_MS_REENTREGA = 60000  # presa = parada há >= 60 s no PEL do grupo
MAX_ENTREGAS = 5  # na 5ª entrega não se reprocessa: fila morta

# O vocabulário desta célula, uma linha por aviso escutado.
#
# `chave_entre_versoes` e `no_v1` são transcrição literal de `x-ponte-do-v1`
# nos schemas v2: `chave_entre_versoes` são os campos de
# `data` que, juntos e só juntos, identificam o fato; `no_v1` diz de onde tirar
# cada um quando o aviso chega na versão 1, como um caminho dentro do evento
# (`data.<campo>`) ou como o valor literal que o v1 não carregava.
#
# A tabela relaciona as versões aceitas de cada aviso. O que não estiver nela
# estoura em vez de ser engolido.
AVISOS = {
    "pagamento.aprovado": {
        "versoes": (1, 2),
        "status": "pago",
        "chave_entre_versoes": ("provider", "provider_reference_id"),
        "no_v1": {
            "provider": "mercadopago",
            "provider_reference_id": "data.mp_payment_id",
        },
    },
    "pagamento.recusado": {
        "versoes": (1, 2),
        "status": "recusado",
        "chave_entre_versoes": ("payment_id",),
        "no_v1": {"payment_id": "data.payment_id"},
    },
    "pagamento.reversao_confirmada": {
        # Estorno ou contestação confirmados pelo fornecedor. Só tira do
        # "pago": um pedido que nunca foi pago não tem o que devolver.
        "versoes": (2,),
        "status": "reembolsado",
        "chave_entre_versoes": ("provider", "provider_reference_id"),
        "no_v1": {},
    },
    "pix.expirado": {
        # Sem v2 e sem ponte a transcrever: o Rito de Contrato de 20/09/2026
        # não tocou nesta carta. A identidade é o id local do pagamento.
        "versoes": (1,),
        "status": "expirado",
        "chave_entre_versoes": ("payment_id",),
        "no_v1": {"payment_id": "data.payment_id"},
    },
    "pix.codigo_trocado": {
        "versoes": (1,),
        "status": "aguardando_pagamento",
        "chave_entre_versoes": ("payment_id",),
        "no_v1": {"payment_id": "data.payment_id"},
    },
}

# O v2 renomeou o tenant desta plataforma para não confundi-lo com o `site_id`
# que vem no envelope do webhook do fornecedor.
CAMPO_DO_SITE = {1: "site_id", 2: "platform_site_id"}

STREAMS = tuple(f"eventos.{evento}" for evento in AVISOS)
VOCABULARIO = ", ".join(
    f"{evento} v{versao}"
    for evento, aviso in AVISOS.items()
    for versao in aviso["versoes"]
)


class AvisoDesconhecido(LookupError):
    """Evento ou versão de evento que esta célula não sabe ler."""


@dataclass(frozen=True)
class Aviso:
    """O aviso já normalizado: o que o consumer precisa saber, igual para
    qualquer versão do contrato que o tenha trazido."""

    evento: str
    chave: str  # a identidade lógica do fato, igual nas duas versões
    site_id: str
    order_id: str
    status: str
    pix: dict | None = None
    payment_id: str | None = None


def _valor_no_v1(data: dict, origem: str):
    """`no_v1` do contrato: um caminho dentro do evento v1, ou o valor literal
    que o v1 não carregava por ser de um fornecedor só."""
    if origem.startswith("data."):
        return data[origem[len("data.") :]]
    return origem


def normalizar(envelope: dict) -> Aviso:
    evento = envelope["event"]
    versao = envelope["version"]
    aviso = AVISOS.get(evento)
    if aviso is None or versao not in aviso["versoes"]:
        raise AvisoDesconhecido(
            f"{evento} v{versao} não está no vocabulário desta célula "
            f"(versões disponíveis: {VOCABULARIO}). Confira o schema do evento "
            "e as versões listadas em AVISOS neste consumer."
        )
    data = envelope["data"]
    if versao == 1:
        partes = [
            _valor_no_v1(data, aviso["no_v1"][campo])
            for campo in aviso["chave_entre_versoes"]
        ]
    else:
        partes = [data[campo] for campo in aviso["chave_entre_versoes"]]
    site_id = data[CAMPO_DO_SITE[versao]]
    return Aviso(
        evento=evento,
        # a identidade nasce escopada pelo site, como tudo nesta
        # célula. Sem isso, um aviso com o site errado (bug do publicador, ou
        # mensagem injetada no stream) gravaria a identidade do fato VERDADEIRO
        # sem mover pedido nenhum, e o aviso legítimo que chegasse depois seria
        # descartado como duplicado: a compra ficaria paga e o pedido preso.
        chave="|".join([site_id, evento, *(str(parte) for parte in partes)]),
        site_id=site_id,
        order_id=data["order_id"],
        status=aviso["status"],
        pix=data["pix"] if evento == "pix.codigo_trocado" else None,
        payment_id=str(data["payment_id"]) if evento == "pix.codigo_trocado" else None,
    )


def _emitir_pedido_pago(aviso: Aviso) -> None:
    """[DESENHO-COMUM.md F10] Só emite com visitante, e sem dado pessoal —
    nem `customer`. Chamada DENTRO da mesma `transaction.atomic()` de
    `aplicar`, então roda uma vez por fato aplicado: a reentrega do
    `pagamento.aprovado` (mesma identidade lógica, v1 ou v2) esbarra no índice
    único de `FatoAplicado` antes de chegar aqui de novo (§ IntegrityError).
    Contrato ainda em voo na frente irmã F4a; construído contra os campos
    publicados em DESENHO-COMUM.md."""
    pedido = (
        OrderModel.objects.select_related("session")
        .filter(pk=aviso.order_id, site_id=aviso.site_id)
        .first()
    )
    if pedido is None or not pedido.session.visitor_id:
        return
    emitir(
        "checkout.pedido-pago",
        {
            "site_id": pedido.site_id,
            "order_id": str(pedido.id),
            "visitor_id": pedido.session.visitor_id,
            "valor_centavos": pedido.total_cents,
            "moeda": "BRL",
            "pago_em": django_timezone.now().isoformat(),
        },
    )


def aplicar(envelope: dict) -> bool:
    """Aplica o aviso exatamente uma vez, venha ele na versão que vier.

    Devolve True quando o efeito aconteceu agora, e False quando este MESMO
    fato já tinha sido aplicado antes: pela outra versão do contrato, por
    reentrega do transporte ou por outro consumidor do grupo.

    O registro do fato e o efeito acontecem na MESMA transação, nesta ordem.
    Marcar o fato antes e aplicar o efeito depois, fora da transação, é o erro
    que já saiu caro em três células: o efeito estourava, a reentrega chegava,
    encontrava o fato marcado e descartava o evento em silêncio
    (RETROSPECTIVA-FASE-D §4). Aqui, efeito que falha derruba o registro junto,
    e a reentrega volta a encontrar trabalho a fazer.

    A corrida entre dois consumidores é decidida pelo índice único da chave: o
    segundo bate no índice, a transação inteira cai e nenhum efeito acontece
    duas vezes.
    """
    aviso = normalizar(envelope)
    try:
        with transaction.atomic():
            if aviso.evento == "pix.codigo_trocado":
                pedido = (
                    OrderModel.objects.select_for_update()
                    .filter(
                        pk=aviso.order_id,
                        site_id=aviso.site_id,
                        intent_id=aviso.payment_id,
                        method="pix",
                        status=OrderModel.AGUARDANDO,
                    )
                    .first()
                )
                if pedido is None:
                    return False
                FatoAplicado.objects.create(chave=aviso.chave)
                pedido.pix = {
                    "qr_code": aviso.pix["qr_code"],
                    "qr_code_base64": aviso.pix["qr_code_base64"],
                    "expires_at": aviso.pix["expires_at"],
                    "trocado_em": django_timezone.now().isoformat(),
                }
                pedido.save(update_fields=["pix"])
                return True
            FatoAplicado.objects.create(chave=aviso.chave)
            estados_elegiveis = Q(status=OrderModel.AGUARDANDO)
            if aviso.status == "pago":
                estados_elegiveis |= Q(status="recusado", method__in=("card", "pix"))
            if aviso.status == "reembolsado":
                estados_elegiveis = Q(status="pago")
            atualizados = (
                OrderModel.objects.filter(
                    pk=aviso.order_id,
                    site_id=aviso.site_id,  # o site do evento tem de bater
                )
                .filter(estados_elegiveis)
                .update(status=aviso.status)
            )
            if aviso.status == "pago" and atualizados:
                _emitir_pedido_pago(aviso)
    except IntegrityError:
        return False
    return True


def _processar(r, stream: str, msg_id, campos) -> None:
    """Caminho ÚNICO de processamento — mensagens novas e reivindicadas passam
    por aqui. Se o handler estourar, a mensagem fica no PEL (sem ACK) e a
    reentrega a reclama depois de IDLE_MS_REENTREGA."""
    aplicar(json.loads(campos[b"json"]))
    r.xack(stream, GRUPO, msg_id)


def _mover_para_fila_morta(r, stream: str, msg_id, campos, entregas: int) -> None:
    # Defensivo de propósito: uma mensagem cujo b"json" nem parseia é
    # exatamente o tipo de veneno que acaba aqui — a fila morta não pode
    # estourar no mesmo lugar em que o handler estourou.
    try:
        event_id = json.loads(campos[b"json"]).get("event_id", "desconhecido")
    except (ValueError, KeyError, AttributeError):
        event_id = "desconhecido"
    campos_dlq = dict(campos)  # payload original, intacto
    campos_dlq.update(
        {
            "motivo": "max_entregas_esgotado",
            "delivery_count": str(entregas),
            "movida_em": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Publica na .dlq ANTES do ACK — pior caso duplica na fila morta, nunca
    # perde.
    r.xadd(f"{stream}.dlq", campos_dlq)
    r.xack(stream, GRUPO, msg_id)
    logger.error(
        "FILA MORTA: evento %s (stream %s, msg %s) esgotou %d entregas e foi "
        "movido para %s.dlq: investigue o payload antes de reinjetar.",
        event_id,
        stream,
        msg_id,
        entregas,
        stream,
    )


def reivindicar_e_reprocessar_presas(r) -> None:
    """Uma passada de reentrega, chamada a cada iteração do loop ANTES do
    xreadgroup ">". XAUTOCLAIM devolve as mensagens paradas há mais de
    IDLE_MS_REENTREGA no PEL do grupo (e incrementa o delivery_count delas);
    o delivery_count real vem do próprio PEL (XPENDING). Quem já está em
    MAX_ENTREGAS vai para a fila morta; o resto volta pelo MESMO caminho do
    handler das mensagens novas."""
    for stream in STREAMS:
        resultado = r.xautoclaim(
            stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA
        )
        # resultado = [cursor, [(id, campos), ...], ids-deletados]; entradas já
        # removidas do stream podem vir com campos None — não há o que fazer
        # com elas além de ignorar (o próprio Redis as tira do PEL).
        reivindicadas = [(m, c) for m, c in resultado[1] if c is not None]
        if not reivindicadas:
            continue
        entregas_por_msg = {
            p["message_id"]: p["times_delivered"]
            for p in r.xpending_range(
                stream,
                GRUPO,
                min=reivindicadas[0][0],
                max=reivindicadas[-1][0],
                count=len(reivindicadas),
            )
        }
        for msg_id, campos in reivindicadas:
            entregas = entregas_por_msg.get(msg_id, 1)
            if entregas >= MAX_ENTREGAS:
                _mover_para_fila_morta(r, stream, msg_id, campos, entregas)
            else:
                _processar(r, stream, msg_id, campos)


class Command(BaseCommand):
    help = "Consumer de eventos da célula (roda como processo supervisionado)"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            # ANTES das novas: sem isto, mensagem cujo handler estourou ficava
            # pendente para sempre.
            reivindicar_e_reprocessar_presas(r)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    _processar(r, stream.decode(), msg_id, campos)
