# apps/eventos/management/commands/eventos_mortos.py (TAR-456)
"""A fila morta desta célula deixa de ser um beco sem saída.

`consume_eventos` move para `<stream>.dlq` o evento que esgotou MAX_ENTREGAS e
loga "intervencao manual necessaria". Até aqui essa mão não tinha o que fazer:
a intervenção exigia abrir o Redis na unha, achar a entrada, reconstruir o
envelope e chamar o handler certo, com o risco de mandar duas vezes a mesma
mensagem para o mesmo aluno. Este comando é aquela mão.

São três gestos, e nenhum a mais:

    python manage.py eventos_mortos                          # o que está morto
    python manage.py eventos_mortos --reprocessar <event_id> # um, deliberado
    python manage.py eventos_mortos --reprocessar-tudo       # o incidente todo

`--reprocessar-tudo` existe porque um incidente mata dezenas de eventos pela
MESMA causa (o provedor caiu, o template sumiu), e recuperá-los um a um por
UUID é o que faria o operador desistir no meio.

## O que garante que reprocessar não manda a mensagem duas vezes

Nada novo: o reprocesso passa pelo MESMO `processar_envelope` do consumidor, e
a dedup por `event_id` continua sendo o mecanismo (INV desta célula: reentrega
implica UM envio). Um evento que morreu sem efeito nenhum roda o handler; um
que morreu depois de já ter efeito é reconhecido pela dedup e não reenvia nada.
As duas saídas são sucesso, e o texto diz qual foi.

## A ordem dos passos não é estética

O efeito final é CONFERIDO NO BANCO (`EventoProcessado`) antes de a entrada
sair da fila morta. Handler que volta sem estourar não é prova de efeito, e
apagar a entrada antes de conferir transformaria um verde falso em evento
perdido para sempre: a fila morta é a última cópia que existe daquele evento.
Por isso, quando o reprocesso falha, a entrada FICA, e o erro nomeia o
event_id, a causa real e o próximo passo.
"""

import json
import logging
import os
import uuid

import redis
from django.core.management.base import BaseCommand, CommandError

from apps.eventos.management.commands import consume_eventos
from apps.eventos.management.commands.consume_eventos import processar_envelope
from apps.eventos.models import EventoProcessado

log = logging.getLogger(__name__)

SUFIXO_DA_FILA_MORTA = ".dlq"

#: O que se escreve no lugar do dado que a entrada não tem como dar. A fila
#: morta copia o payload como veio, e a causa mais comum de um evento morrer é
#: justamente o corpo não ser legível.
ILEGIVEL = "ilegível"


def _texto(campos: dict, chave: bytes) -> str:
    valor = campos.get(chave, b"")
    return valor.decode(errors="replace") if isinstance(valor, bytes) else str(valor)


def _ler_entrada(stream: str, msg_id: bytes, campos: dict) -> dict:
    """Uma entrada da fila morta, aberta no que o operador precisa ler."""
    try:
        envelope = json.loads(campos[b"json"])
        event_id = str(envelope["event_id"])
        evento = str(envelope.get("event", ILEGIVEL))
    except (KeyError, TypeError, ValueError):
        envelope, event_id, evento = None, ILEGIVEL, ILEGIVEL
    return {
        "stream": stream,  # o stream ORIGINAL, sem o sufixo da fila morta
        "msg_id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
        "event_id": event_id,
        "evento": evento,
        "motivo": _texto(campos, b"motivo"),
        "entregas": _texto(campos, b"delivery_count"),
        "morta_desde": _texto(campos, b"movida_em"),
        "envelope": envelope,
    }


def listar_mortos(r) -> list[dict]:
    """Tudo o que está morto nos streams DESTA célula, na ordem em que morreu.

    A varredura é pelos streams declarados em `consume_eventos.STREAMS`: a fila
    morta de um stream que esta célula não consome não é assunto dela, e sair
    reprocessando stream alheio seria a célula entregando o evento de outra.
    """
    mortos = []
    for stream in consume_eventos.STREAMS:
        for msg_id, campos in r.xrange(f"{stream}{SUFIXO_DA_FILA_MORTA}"):
            mortos.append(_ler_entrada(stream, msg_id, campos))
    return mortos


def recuperar(r, entrada: dict) -> str:
    """Reprocessa UMA entrada e devolve o desfecho, ou levanta CommandError.

    Desfechos: "reprocessado" (o handler rodou agora) e "ja-processado" (o
    efeito já existia e a dedup o reconheceu). Nos dois a entrada sai da fila
    morta, porque nos dois o evento deixou de estar morto.
    """
    if entrada["envelope"] is None:
        raise CommandError(
            f"o corpo da entrada {entrada['msg_id']} em "
            f"{entrada['stream']}{SUFIXO_DA_FILA_MORTA} está {ILEGIVEL} e não há "
            "envelope para entregar a handler nenhum. Leia o corpo cru com "
            f"`XRANGE {entrada['stream']}{SUFIXO_DA_FILA_MORTA} {entrada['msg_id']} "
            f"{entrada['msg_id']}`, decida com o dono do evento se ele se "
            "reconstrói, e só então apague a entrada. Nada foi alterado."
        )
    handler = consume_eventos.STREAMS[entrada["stream"]]
    try:
        rodou = processar_envelope(entrada["envelope"], handler)
    except Exception as erro:
        raise CommandError(
            f"o reprocesso de event_id={entrada['event_id']} falhou de novo: "
            f"{type(erro).__name__}: {erro}. A causa NÃO foi corrigida, e o "
            f"evento continua na fila morta {entrada['stream']}"
            f"{SUFIXO_DA_FILA_MORTA}, intacto. Corrija a causa acima e repita "
            "este mesmo comando."
        ) from erro
    if not EventoProcessado.objects.filter(event_id=entrada["event_id"]).exists():
        raise CommandError(
            f"o reprocesso de event_id={entrada['event_id']} voltou sem erro e "
            "sem deixar efeito no banco: não há EventoProcessado para ele. A "
            "entrada continua na fila morta, e nada foi apagado. Investigue o "
            f"handler de {entrada['stream']} antes de tentar de novo."
        )
    r.xdel(f"{entrada['stream']}{SUFIXO_DA_FILA_MORTA}", entrada["msg_id"])
    log.info(
        "FILA MORTA RECUPERADA: event_id=%s saiu de %s%s e o efeito está "
        "gravado (%s)",
        entrada["event_id"],
        entrada["stream"],
        SUFIXO_DA_FILA_MORTA,
        "handler reprocessado agora" if rodou else "efeito já existia, sem reenvio",
    )
    return "reprocessado" if rodou else "ja-processado"


class Command(BaseCommand):
    help = "Lista e reprocessa os eventos mortos desta célula (fila <stream>.dlq)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reprocessar",
            metavar="EVENT_ID",
            help="reprocessa o evento morto com este event_id",
        )
        parser.add_argument(
            "--reprocessar-tudo",
            action="store_true",
            help="reprocessa TODOS os eventos mortos (um incidente mata vários pela mesma causa)",
        )

    def handle(self, *args, **opts):
        # `alvo is not None` em todo este método, e não a verdade do valor:
        # `--reprocessar ""` (a variável de shell que veio vazia) É um pedido de
        # recuperação, e cair na listagem com saída zero mandaria o operador
        # embora achando que recuperou. Vazio vira erro nomeado logo abaixo.
        alvo, tudo = opts["reprocessar"], opts["reprocessar_tudo"]
        if alvo is not None and tudo:
            raise CommandError(
                "escolha um dos dois: `--reprocessar <event_id>` para um evento "
                "ou `--reprocessar-tudo` para a fila inteira."
            )
        if alvo is not None:
            # `event_id` é UUID no banco, e consultar com um texto que não é
            # UUID estoura um ValueError cru do ORM na cara do operador. Quem
            # digitou errado (ou passou uma variável de shell vazia) merece
            # ouvir isso em português, antes de qualquer consulta.
            try:
                uuid.UUID(alvo)
            except (ValueError, AttributeError, TypeError):
                raise CommandError(
                    f"`{alvo}` não é um event_id: esta célula identifica evento "
                    "por UUID. Copie o event_id da lista: `python manage.py "
                    "eventos_mortos`."
                )
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        mortos = listar_mortos(r)
        if alvo is None and not tudo:
            return self._listar(mortos)
        escolhidos = mortos if tudo else [m for m in mortos if m["event_id"] == alvo]
        if not escolhidos:
            return self._nada_a_recuperar(alvo, tudo)
        self._recuperar(r, escolhidos, len(mortos))

    def _listar(self, mortos: list[dict]) -> None:
        streams = sorted({morto["stream"] for morto in mortos})
        if not mortos:
            self.stdout.write(
                "FILA MORTA VAZIA: nenhum evento parado nos "
                f"{len(consume_eventos.STREAMS)} streams desta célula."
            )
        else:
            self.stdout.write(
                f"FILA MORTA: {len(mortos)} evento(s) parado(s) em "
                f"{len(streams)} stream(s) desta célula.\n"
            )
            for stream in streams:
                self.stdout.write(stream)
                for morto in [m for m in mortos if m["stream"] == stream]:
                    self.stdout.write(
                        f"  event_id={morto['event_id']} evento={morto['evento']} "
                        f"entregas={morto['entregas']} morto_desde={morto['morta_desde']} "
                        f"motivo={morto['motivo']}"
                    )
            self.stdout.write(
                "\nCorrija a causa e recupere com:\n"
                "  python manage.py eventos_mortos --reprocessar <event_id>\n"
                "  python manage.py eventos_mortos --reprocessar-tudo"
            )
        self.stdout.write(
            f"INDICADOR eventos_mortos={len(mortos)} streams_afetados={len(streams)}"
        )

    def _nada_a_recuperar(self, alvo: str | None, tudo: bool) -> None:
        if tudo:
            self.stdout.write("FILA MORTA VAZIA: não há o que recuperar.")
            self.stdout.write(
                "INDICADOR eventos_mortos_recuperados=0 eventos_mortos_restantes=0"
            )
            return
        if EventoProcessado.objects.filter(event_id=alvo).exists():
            # Rodar o mesmo comando duas vezes é o gesto mais provável de quem
            # não sabe se o primeiro pegou. A resposta é a verdade medida no
            # banco, nunca um segundo envio.
            self.stdout.write(
                f"JÁ RECUPERADO event_id={alvo}: não está na fila morta e o "
                "efeito está gravado (EventoProcessado). Nada a fazer."
            )
            return
        raise CommandError(
            f"event_id={alvo} não está na fila morta e nunca foi processado por "
            "esta célula. Confira o event_id na lista: `python manage.py "
            "eventos_mortos`."
        )

    def _recuperar(self, r, escolhidos: list[dict], mortos_antes: int) -> None:
        recuperados, falhas = 0, []
        for entrada in escolhidos:
            try:
                desfecho = recuperar(r, entrada)
            except CommandError as erro:
                # Um evento que ainda falha não pode calar os outros do mesmo
                # incidente: o laço segue, e o resumo no fim reprova o comando.
                if len(escolhidos) == 1:
                    raise
                falhas.append(str(erro))
                continue
            recuperados += 1
            self.stdout.write(
                f"RECUPERADO event_id={entrada['event_id']} em {entrada['stream']}: "
                + (
                    "o handler rodou e o efeito está gravado (EventoProcessado)."
                    if desfecho == "reprocessado"
                    else "o efeito já estava gravado, nada foi reenviado "
                    "(idempotência por event_id)."
                )
            )
        self.stdout.write(
            f"INDICADOR eventos_mortos_recuperados={recuperados} "
            f"eventos_mortos_restantes={mortos_antes - recuperados}"
        )
        if falhas:
            raise CommandError(
                f"{len(falhas)} de {len(escolhidos)} evento(s) continuam na fila "
                "morta. A primeira falha foi: " + falhas[0]
            )
