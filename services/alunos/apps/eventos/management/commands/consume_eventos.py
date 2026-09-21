# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.eventos.models import EventoProcessado
from apps.matriculas.handlers import ao_pagamento_aprovado, ao_pagamento_estornado

logger = logging.getLogger(__name__)

GRUPO = "alunos"  # nome DESTA célula
CONSUMIDOR = "worker-1"
STREAMS = ["eventos.pagamento.aprovado", "eventos.pagamento.estornado"]
HANDLERS = {
    "pagamento.aprovado": ao_pagamento_aprovado,
    # [ESTORNO] 20/09/2026: o dinheiro que volta fecha o acesso na hora. Sem
    # este consumidor o corte dependeria de alguem olhar o painel do fornecedor
    # e mexer na matricula a mao, que foi exatamente o motivo de o contrato
    # `pagamento.estornado.v2` nascer.
    "pagamento.estornado": ao_pagamento_estornado,
}

# Convenção do lote de reentrega — MESMOS nomes e valores nas 4 células
# consumidoras (alunos, checkout, leads, mensageria). Guarda:
# tests/test_reentrega_pel.py::test_constantes_do_lote_nao_derivam.
IDLE_MS_REENTREGA = 60_000  # presa = pendente sem ACK há pelo menos isto
MAX_ENTREGAS = 5  # contagem do PEL em que a mensagem vai para a fila morta
LOTE_REENTREGA = 10  # quantas presas olhar por iteração (mesmo teto do xreadgroup)

# As versões do contrato que esta célula sabe ler. Fechada de propósito: uma
# versão nova pode renomear campo de novo, e tratá-la como se fosse a última
# conhecida produziria identidade errada — matrícula duplicada sem erro nenhum.
VERSOES_ACEITAS = (1, 2)

# A ponte entre as duas versões, COPIADA do campo `x-ponte-do-v1` dos contratos
# v2 (contracts/eventos/). Não é interpretação nossa: o contrato publica a regra
# como DADO justamente para que as células consumidoras derivem a MESMA chave em
# vez de cada uma inventar a sua. `chave_entre_versoes` são os campos de `data`
# que, juntos e só juntos, identificam o fato; `no_v1` diz de onde tirar cada um
# quando o evento chega na versão 1.
#
# A REGRA NÃO É A MESMA PARA TODOS OS AVISOS DA FAMÍLIA, e é por isso que ela
# mora numa tabela por evento e não numa função só: no `pagamento.aprovado` o
# fato é o par (`provider`, `provider_reference_id`), porque o `mp_payment_id`
# do v1 é o mesmo valor com `provider` implícito igual a `mercadopago`; no
# `pagamento.recusado` o v1 nunca carregou referência de provedor nenhuma, e
# quem atravessa as versões é o `payment_id`. Quem acrescentar um evento aqui
# copia a ponte DO CONTRATO daquele evento, nunca a da linha de cima.
#
# `no_v1: None` É UMA AFIRMAÇÃO, e não um campo que faltou preencher: aquele
# evento NASCEU na versão 2 e não tem v1 nenhum para atravessar, então o
# contrato dele não publica `x-ponte-do-v1` e não há o que copiar. Quem declara
# isso ganha a recusa de `dados_na_forma_do_v2`: um envelope que se diga v1
# daquele evento é aviso forjado, e traduzi-lo produziria uma identidade que não
# é a do fato. `chave_entre_versoes` continua obrigatório em todos, porque é ele
# que diz o que identifica o fato, exista v1 ou não.
# Guardas: tests/test_o_mesmo_pagamento_nas_duas_versoes.py.
PONTE_DO_V1 = {
    "pagamento.aprovado": {
        "chave_entre_versoes": ["provider", "provider_reference_id"],
        "no_v1": {
            "provider": "mercadopago",
            "provider_reference_id": "data.mp_payment_id",
        },
    },
    # [ESTORNO] O par do pagamento outra vez, e pela MESMA razão do aprovado: é
    # ele que o contrato aponta como "qual pagamento foi estornado". Coincidir
    # com a linha de cima é coincidência de contratos, não herança: o
    # `pagamento.recusado` da mesma família atravessa por outro campo.
    "pagamento.estornado": {
        "chave_entre_versoes": ["provider", "provider_reference_id"],
        "no_v1": None,  # nasceu na v2 (Rito de Contrato de 20/09/2026)
    },
}


class VersaoDesconhecida(ValueError):
    """Envelope numa versão que esta célula não sabe ler.

    Sobe e mata o processamento do evento, que é o certo: a mensagem fica no
    PEL, a reentrega tenta de novo e a fila morta a recolhe depois de
    MAX_ENTREGAS. O contrário seria adivinhar o formato e matricular errado.
    """


class EventoSemPonte(LookupError):
    """Evento consumido sem a ponte entre versões declarada em PONTE_DO_V1."""


def ponte_do_evento(evento: str) -> dict:
    """A linha de PONTE_DO_V1 daquele evento, ou a recusa em nome dele.

    As duas funções abaixo precisam da mesma linha, e por razões diferentes: uma
    para saber se existe v1 a traduzir, outra para saber o que identifica o
    fato. Buscar em dois lugares deixaria uma delas esquecer o `KeyError`, e o
    evento consumido sem ponte voltaria a ser um `KeyError` cru no meio do laço.
    """
    ponte = PONTE_DO_V1.get(evento)
    if ponte is None:
        raise EventoSemPonte(
            f"{evento} é consumido sem ponte entre versões declarada. Copie o "
            "`x-ponte-do-v1` do contrato v2 desse evento para PONTE_DO_V1, e "
            "não reaproveite a chave de outro evento: elas são diferentes. "
            "Evento que nasceu na v2 declara `no_v1: None`."
        )
    return ponte


def dados_na_forma_do_v2(envelope: dict) -> dict:
    """O `data` do evento na forma do v2, a única que esta célula lê.

    A tradução mora AQUI, na borda, e não dentro do handler, porque é aqui que
    o número da versão existe. Um handler que decidisse a versão pela presença
    de um campo estaria adivinhando o que o envelope já diz. Quando o v1 parar
    de ser emitido (RITOS.md §3), some esta função e nada mais muda.

    O que o v2 renomeou, e por quê, está na descrição de
    `contracts/eventos/pagamento.aprovado.v2.json`: `site_id` virou
    `platform_site_id` para não se confundir com o `site_id` do fornecedor, e
    `mp_payment_id` virou o par neutro `provider` mais `provider_reference_id`.

    **Nem todo evento desta célula tem v1.** `VERSOES_ACEITAS` é do CONSUMIDOR,
    não de cada aviso: ele diz quais números esta célula sabe ler, e não que
    todos os avisos existam nos dois. `pagamento.estornado` nasceu na versão 2
    (Rito de Contrato de 20/09/2026), e um envelope que se diga v1 dele é aviso
    forjado ou emissor com defeito. Traduzir esse envelope pelas regras do
    `pagamento.aprovado` daria um `platform_site_id` e um par de pagamento
    plausíveis, tirados dos campos errados, e o consumidor cortaria o acesso de
    quem aquela identidade calhasse de apontar. Recusar é a única resposta
    honesta, e a mensagem fica no PEL como qualquer versão desconhecida.
    """
    versao = envelope["version"]
    if versao not in VERSOES_ACEITAS:
        raise VersaoDesconhecida(
            f"{envelope['event']} chegou na versão {versao!r}, e esta célula lê "
            f"as versões {VERSOES_ACEITAS}. Leia o contrato dessa versão em "
            "contracts/eventos/ e traduza aqui antes de consumi-la."
        )
    dados = envelope["data"]
    if versao == 2:
        return dados
    if ponte_do_evento(envelope["event"])["no_v1"] is None:
        raise VersaoDesconhecida(
            f"{envelope['event']} chegou na versão 1, e esse aviso nasceu na "
            "versão 2: não existe v1 dele para traduzir. Confira quem publicou "
            "este envelope, porque o contrato em contracts/eventos/ não tem "
            "versão 1 nenhuma."
        )
    traduzido = {
        chave: valor
        for chave, valor in dados.items()
        if chave not in ("site_id", "mp_payment_id")
    }
    traduzido["platform_site_id"] = dados["site_id"]
    traduzido["provider"] = "mercadopago"
    traduzido["provider_reference_id"] = dados["mp_payment_id"]
    return traduzido


def identidade_do_fato(evento: str, dados: dict) -> str:
    """A chave que diz "isto já aconteceu", igual nas duas versões do contrato.

    Recebe o `data` JÁ traduzido para o v2, então os campos da chave têm o mesmo
    nome venha o aviso de onde vier.

    [INV-P11] A chave nasce ESCOPADA PELO SITE, e isso não é zelo: o
    `provider_reference_id` é o id da cobrança na conta do fornecedor, e cada
    escola tem a sua. Duas escolas podem receber a referência `12345` no mesmo
    dia, de pagamentos que nada têm a ver um com o outro. Sem o site na chave, a
    segunda compra seria lida como reentrega da primeira e descartada: a pessoa
    pagou, e a matrícula nunca acontece. O mesmo vale para um aviso que chegue
    com o site errado, que consumiria a identidade do fato verdadeiro.

    A ordem das partes (site, evento, campos da chave) é a mesma das outras
    células consumidoras deste lote, para que a chave de um fato seja legível do
    mesmo jeito em qualquer uma.
    """
    ponte = ponte_do_evento(evento)
    return "|".join(
        [
            str(dados["platform_site_id"]),
            evento,
            *(str(dados[campo]) for campo in ponte["chave_entre_versoes"]),
        ]
    )


def processar_envelope(envelope: dict, handlers: dict) -> None:
    """Dedup pelo FATO: nem a mesma mensagem nem a outra versão dela rodam duas vezes.
    handlers mapeia envelope["event"] (ex.: "pagamento.aprovado") -> callable(data).

    São DUAS unicidades no create, e elas medem coisas diferentes. O `event_id`
    barra a MESMA mensagem chegando de novo (entrega at-least-once). A
    `identidade_logica` barra o MESMO FATO chegando pela OUTRA versão do
    contrato: desde 20/09/2026 o v1 e o v2 do aviso de pagamento convivem, cada
    um com seu `event_id`, e para o dedup por envelope eles seriam dois eventos.
    A pessoa viraria aluna duas vezes, sem erro, sem log e sem chamado.

    São DUAS transações aninhadas. Parecem redundantes; não são — cada uma fecha
    um modo de falha diferente, e remover qualquer uma reabre um bug silencioso.
    Guarda das duas: tests/test_inv_p5_dedup_atomico.py.

    (1) A EXTERNA envolve o registro E o efeito, para que falhem juntos. Se o
        handler estourar (deadlock, conexão caída, timeout), o EventoProcessado
        é desfeito junto e a reentrega volta a funcionar. Com o create()
        commitando sozinho — como era antes —, um hiccup de 2s do Postgres no
        meio da matrícula deixava o evento marcado como visto: toda reentrega
        futura caía no `except IntegrityError` abaixo e era descartada em
        silêncio. O cliente pagou e nunca foi matriculado, sem nada no sistema
        para descobrir isso (não há reconciliação).

    (2) A INTERNA é savepoint SÓ em volta do create(), por dois motivos.
        Primeiro, ARMADILHAS.md §4.8: sem savepoint próprio, o IntegrityError
        do event_id duplicado marca a transação inteira como abortada e a query
        seguinte estoura TransactionManagementError em vez de o evento ser
        simplesmente ignorado. Segundo — e é por isso que o handler está FORA
        do try, não só fora do savepoint —, o `except` precisa enxergar
        exclusivamente o IntegrityError DESTE create. Com o handler dentro do
        try, um IntegrityError vindo de dentro dele (qualquer constraint que
        nada tem a ver com event_id) seria lido como "já processado" e o evento
        seria descartado em silêncio: o mesmo bug de antes, só que mais difícil
        de enxergar.

    A tradução e a identidade são calculadas ANTES da transação, de propósito:
    envelope de versão desconhecida estoura sem abrir transação nenhuma e sem
    gravar nada, e a mensagem segue no PEL para a fila morta.
    """
    dados = dados_na_forma_do_v2(envelope)
    identidade = identidade_do_fato(envelope["event"], dados)
    with transaction.atomic():  # (1) registro e efeito: vivem ou morrem juntos
        try:
            with transaction.atomic():  # (2) savepoint: SÓ o create
                EventoProcessado.objects.create(
                    event_id=envelope["event_id"], identidade_logica=identidade
                )
        except IntegrityError:
            return  # já processado: nada foi gravado, o handler não roda de novo
        handlers[envelope["event"]](dados)


def _mover_para_fila_morta(
    r: "redis.Redis", stream: str, msg_id: bytes, delivery_count: int
) -> None:
    """Esgotou MAX_ENTREGAS: preserva a mensagem em <stream>.dlq e tira do PEL.

    O handler NÃO roda. XADD na fila morta ANTES do XACK, de propósito: se o
    processo morrer entre os dois, a mensagem continua presa e o próximo ciclo
    a move de novo — duplicata na .dlq é melhor que mensagem perdida.

    O ERROR abaixo é o alarme possível hoje; alerta de verdade é dívida
    registrada (§9), não deste despacho.
    """
    entradas = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(entradas[0][1]) if entradas else {}
    try:
        event_id = json.loads(campos[b"json"])["event_id"]
    except (KeyError, ValueError):
        # Payload ilegível ou mensagem apagada do stream — vai para a .dlq do
        # mesmo jeito: o motivo de o handler estourar pode ser exatamente este.
        event_id = "desconhecido"
    r.xadd(
        f"{stream}.dlq",
        {
            **campos,
            "motivo": f"esgotou MAX_ENTREGAS={MAX_ENTREGAS} sem ACK",
            "delivery_count": str(delivery_count),
            "movida_em": datetime.now(timezone.utc).isoformat(),
        },
    )
    r.xack(stream, GRUPO, msg_id)
    msg_id_txt = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
    logger.error(
        "FILA MORTA: evento %s (stream=%s, msg_id=%s, delivery_count=%s) movido "
        "para %s.dlq: o handler NAO rodou; investigar e reprocessar manualmente.",
        event_id,
        stream,
        msg_id_txt,
        delivery_count,
        stream,
    )


def reentregar_presas(r: "redis.Redis", stream: str, handlers: dict) -> None:
    """A peça que faltava (ARMADILHAS-OPERACAO.md §9): `xreadgroup(">")` só entrega
    mensagem NOVA — quem estourava o handler ficava em XPENDING para sempre.
    Roda a cada iteração do loop, ANTES da leitura de mensagens novas:

    1) quem já chegou a MAX_ENTREGAS no PEL vai para a fila morta, sem rodar o
       handler (XPENDING traz a contagem; XAUTOCLAIM não traz — daí as duas
       chamadas);
    2) o resto preso há IDLE_MS_REENTREGA+ é reivindicado (XAUTOCLAIM) e
       reprocessado pelo MESMO caminho das mensagens novas — idempotência
       segura pós-#43: registro e efeito na mesma transação.

    Se o reprocesso estourar de novo, a exceção propaga como no caminho normal
    (o processo morre e o supervisor o traz de volta); a mensagem segue no PEL
    com delivery_count incrementado pelo próprio XAUTOCLAIM — o teto de
    MAX_ENTREGAS é o que impede o ciclo de ser eterno.
    """
    presas = r.xpending_range(
        stream, GRUPO, min="-", max="+", count=LOTE_REENTREGA, idle=IDLE_MS_REENTREGA
    )
    for presa in presas:
        if presa["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(
                r, stream, presa["message_id"], presa["times_delivered"]
            )
    # As movidas para a .dlq acima já foram ACKadas — o XAUTOCLAIM não as vê.
    resultado = r.xautoclaim(
        stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA, count=LOTE_REENTREGA
    )
    for msg_id, campos in resultado[1]:
        envelope = json.loads(campos[b"json"])
        processar_envelope(envelope, handlers)
        r.xack(stream, GRUPO, msg_id)


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
            for stream in STREAMS:
                reentregar_presas(r, stream, HANDLERS)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    processar_envelope(envelope, HANDLERS)
                    r.xack(stream, GRUPO, msg_id)
