"""O consumidor de eventos da `metricas`  # [RECEITA:R4 v1, adaptada]

Roda como processo supervisionado, ao lado do container web, e é a única boca
de entrada do livro de fatos. O molde é o das cinco células consumidoras
(`alunos`, `checkout`, `leads`, `mensageria`, `gamificacao`), com as mesmas
constantes de reentrega — copiar o padrão é Lei 3, e divergir nos números
tornaria impossível comparar o comportamento de duas células em incidente.

## As três adaptações desta célula, declaradas em vez de silenciosas

**1. Não há tabela `EventoProcessado`.** Nas outras células ela existe porque o
efeito do evento (creditar XP, matricular) não deixa rastro do `event_id`; aqui
o efeito É gravar o evento, e `Evento.event_id` já é único. Uma segunda tabela
com a mesma chave seria o mesmo fato em dois lugares, e as duas poderiam
discordar.

**2. Não há mapa de handlers.** Tudo que chega com envelope bom é guardado.
Assunto novo entra sozinho no livro, sem PR nenhum — que é a diferença entre
um livro e um contador.

**3. Envelope inválido não estoura: vira EventoMorto e é ACKado.** Nas outras
células, um envelope quebrado explode o handler, a mensagem fica presa no PEL
e, cinco entregas depois, cai na fila morta do Redis, onde ninguém olha. Aqui
ela cai numa TABELA, que o painel mostra e sobre a qual há três ações
(inspecionar, tentar de novo, descartar com motivo). Reentregar um corpo
quebrado não o conserta; o que conserta é alguém ver.

## O que ele assina, e por que não assina mais

Os assuntos com contrato CONGELADO em `contracts/eventos/` que alguma célula
publica hoje. Assinar um stream que ninguém publica criaria um grupo de
consumo vazio e a impressão de que o caminho está pronto (a mesma razão pela
qual a `gamificacao` deixa `aula.concluida` de fora).

`matricula.situacao-alterada` era o assunto que esta célula mais queria, e
entrou em 05/09/2026, no degrau 8. Duas coisas precisavam ser verdade, e agora
sao: o contrato esta congelado (`contracts/eventos/`, PR #1076) e alguem o
publica de fato (a `alunos`, PR #1080, nos cinco caminhos que mexem no status).

Vale registrar o que se descobriu ao pagar essa divida, porque o comentario
anterior AQUI afirmava o contrario: a `alunos` **nao** publicava este assunto.
O que existia era a CARTA (`notificacao.devida`), que leva
"matricula.situacao-alterada" como um parametro dentro dela, e que so nasce
quando alguem GANHA acesso e tem identidade da plataforma. Recusa, suspensao,
encerramento e reembolso nao deixavam rastro nenhum.
"""

import json
import logging
import os
from datetime import datetime, timezone

import redis
from django.core.management.base import BaseCommand

from apps.fatos.models import EventoMorto
from apps.fatos.recepcao import MORTO, receber

logger = logging.getLogger(__name__)

GRUPO = "metricas"  # nome DESTA célula
CONSUMIDOR = "worker-1"

#: Os assuntos com contrato congelado que alguém publica hoje.
STREAMS = [
    # Quem entrou no site (`identidade`, desde 31/08/2026).
    "eventos.identidade.pessoa-cadastrada",
    # A jornada de aprendizado (`quiz`).
    "eventos.quiz.completado",
    # A vida do fórum (`forum`, desde 30/08/2026).
    "eventos.forum.topico-criado",
    "eventos.forum.mensagem-criada",
    "eventos.forum.resposta-aceita",
    "eventos.forum.mensagem-removida",
    # A vida de uma matricula (`alunos`, desde 05/09/2026): quem pediu
    # entrada, quem foi liberado, recusado, suspenso, encerrado, reembolsado.
    # E dele que sai "quem virou aluna", e o campo `origem` separa a VENDA
    # (`comprou`) do aluno das turmas anteriores (`liberado`).
    "eventos.matricula.situacao-alterada",
    # A Caixa de Sugestões (`sugestoes`).
    "eventos.sugestao.criada",
    "eventos.sugestao.status-alterado",
    "eventos.sugestao.voto-adicionado",
    "eventos.sugestao.voto-removido",
    # Os dois fatos de compra do sistema de experimentos (`checkout`, contrato
    # F4a): quem foi atribuído a um pedido e quem pagou. É daqui que sai a
    # métrica principal do primeiro experimento (entrada no checkout) e as
    # conversões do funil de compra (DESENHO-COMUM.md, sessão de 26/09/2026).
    "eventos.checkout.pedido-atribuido",
    "eventos.checkout.pedido-pago",
]

#: Os dois assuntos de compra do checkout: DESENHO-COMUM.md é taxativo — eles
#: NUNCA levam dado pessoal. `_campo_pessoal_do_checkout` é o segundo guarda:
#: se algum publicador um dia divergir do contrato F4a, o campo pessoal não
#: entra no livro por aqui, mesmo que o envelope esteja bem formado.
EVENTOS_DE_COMPRA_DO_CHECKOUT = frozenset(
    {"checkout.pedido-atribuido", "checkout.pedido-pago"}
)

#: DESENHO-COMUM.md, eventos de compra (F4a): "Sem customer, e-mail, nome,
#: telefone, documento." Comparação por chave, sem distinguir maiúsculas.
CAMPOS_PESSOAIS_PROIBIDOS_NO_CHECKOUT = frozenset(
    {"customer", "email", "nome", "telefone", "documento"}
)

# Convenção do lote de reentrega — MESMOS nomes e valores das outras células.
IDLE_MS_REENTREGA = 60_000  # presa = pendente sem ACK há pelo menos isto
MAX_ENTREGAS = 5  # contagem do PEL em que a mensagem vai para a fila morta
LOTE_REENTREGA = 10  # quantas presas olhar por iteração


def _corpo(campos: dict) -> bytes:
    """O texto cru da mensagem, sem supor que a chave existe."""
    return campos.get(b"json") or campos.get("json") or b""


def _texto_do_corpo(cru: bytes | str) -> str:
    """`cru` decodificado, ou vazio quando não é UTF-8 (mesma régua de `recepcao`)."""
    if isinstance(cru, bytes):
        try:
            return cru.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    return cru


def _campo_pessoal_do_checkout(tipo: str, dados: object) -> str | None:
    """A primeira chave proibida em `dados`, só para os dois eventos de compra.

    Os demais assuntos não têm validação de miolo por desenho desta célula
    (`recepcao.receber`: "quem valida o miolo é quem publica"). Os dois
    eventos de compra do checkout são a exceção deliberada, porque
    DESENHO-COMUM.md proíbe dado pessoal neles e o livro nunca pode guardar o
    que não pode expor.
    """
    if tipo not in EVENTOS_DE_COMPRA_DO_CHECKOUT or not isinstance(dados, dict):
        return None
    for chave in dados:
        if (
            isinstance(chave, str)
            and chave.lower() in CAMPOS_PESSOAIS_PROIBIDOS_NO_CHECKOUT
        ):
            return chave
    return None


def processar(cru: bytes) -> str:
    """Guarda o fato e devolve o desfecho, registrando o que merece log."""
    texto = _texto_do_corpo(cru)
    try:
        pre = json.loads(texto) if texto else None
    except (TypeError, ValueError):
        pre = None
    if isinstance(pre, dict):
        tipo = pre.get("event") if isinstance(pre.get("event"), str) else ""
        campo = _campo_pessoal_do_checkout(tipo, pre.get("data"))
        if campo is not None:
            morto = EventoMorto.objects.create(
                corpo=texto[:100_000],
                motivo=(
                    f"campo pessoal proibido em evento de compra do checkout: "
                    f"'{campo}' (DESENHO-COMUM.md: sem customer, e-mail, nome, "
                    "telefone, documento)"
                ),
                tipo_declarado=tipo[:120],
                event_id_declarado=str(pre.get("event_id") or "")[:80],
            )
            logger.error(
                "EVENTO MORTO (id=%s): campo pessoal '%s' num evento de compra "
                "do checkout. Inspecionar em /admin/, tentar de novo ou "
                "descartar com motivo.",
                morto.pk,
                campo,
            )
            return MORTO
    desfecho, objeto = receber(cru)
    if desfecho == MORTO:
        # ERROR e não WARNING: um evento que a plataforma afirmou e o livro não
        # pôde guardar é um buraco na contagem, e alguém precisa olhar.
        logger.error(
            "EVENTO MORTO (id=%s): %s. Inspecionar em /admin/, tentar de novo "
            "ou descartar com motivo.",
            getattr(objeto, "pk", "?"),
            getattr(objeto, "motivo", "?"),
        )
    return desfecho


def _mover_para_fila_morta(
    r: "redis.Redis", stream: str, msg_id: bytes, delivery_count: int
) -> None:
    """Esgotou MAX_ENTREGAS: preserva a mensagem em <stream>.dlq e tira do PEL.

    Nesta célula este caminho quase não deveria acontecer, porque `receber`
    não levanta — uma mensagem só chega aqui se o processo morreu no meio
    (banco fora do ar, contêiner reiniciado). XADD antes do XACK, de propósito:
    duplicata na `.dlq` é melhor que mensagem perdida.
    """
    entradas = r.xrange(stream, min=msg_id, max=msg_id)
    campos = dict(entradas[0][1]) if entradas else {}
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
    logger.error(
        "FILA MORTA DO REDIS: stream=%s msg_id=%s delivery_count=%s. O livro "
        "NAO guardou este fato; investigar e reprocessar manualmente.",
        stream,
        msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
        delivery_count,
    )


def reentregar_presas(r: "redis.Redis", stream: str) -> None:
    """`xreadgroup(">")` só entrega mensagem NOVA; o que ficou preso volta aqui."""
    presas = r.xpending_range(
        stream, GRUPO, min="-", max="+", count=LOTE_REENTREGA, idle=IDLE_MS_REENTREGA
    )
    for presa in presas:
        if presa["times_delivered"] >= MAX_ENTREGAS:
            _mover_para_fila_morta(
                r, stream, presa["message_id"], presa["times_delivered"]
            )
    resultado = r.xautoclaim(
        stream, GRUPO, CONSUMIDOR, min_idle_time=IDLE_MS_REENTREGA, count=LOTE_REENTREGA
    )
    for msg_id, campos in resultado[1]:
        processar(_corpo(dict(campos)))
        r.xack(stream, GRUPO, msg_id)


class Command(BaseCommand):
    help = "Recebe os eventos da plataforma e os guarda no livro de fatos"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            for stream in STREAMS:
                reentregar_presas(r, stream)
            resp = r.xreadgroup(
                GRUPO, CONSUMIDOR, {s: ">" for s in STREAMS}, count=10, block=5000
            )
            for stream, msgs in resp or []:
                for msg_id, campos in msgs:
                    processar(_corpo(dict(campos)))
                    r.xack(stream, GRUPO, msg_id)
