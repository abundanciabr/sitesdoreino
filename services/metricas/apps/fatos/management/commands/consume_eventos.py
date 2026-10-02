"""O consumidor de eventos da `metricas`  # [RECEITA:R4 v1, adaptada]

Roda como processo supervisionado, ao lado do container web, e é a única boca
de entrada do livro de fatos. O molde é o das cinco células consumidoras
(`alunos`, `checkout`, `leads`, `mensageria`, `gamificacao`), com as mesmas
constantes de reentrega — copia-se o padrão, nunca o arquivo, e divergir nos números
tornaria impossível comparar o comportamento de duas células em incidente.

## As cinco adaptações desta célula, declaradas em vez de silenciosas

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

**4. Dois assuntos por vez sao exceção deliberada: proibem dado pessoal por
nome de campo, nao por contrato.** `recepcao.receber` nao valida o miolo.
Para os
assuntos em `ASSUNTOS_SEM_DADO_PESSOAL`, `processar` confere `data` contra
`CAMPOS_PESSOAIS_PROIBIDOS` ANTES de chamar `receber`: e um segundo guarda,
que nao depende de nenhum arquivo fora da celula, so de nomes de campo que a
casa ja proibe (customer, email, nome, telefone, documento). Assunto novo com
a mesma exigencia entra no MESMO conjunto.

**5. Um campo pessoal que o contrato declara e descartado na entrada.**
`quiz.completado` leva `data.lead` (e-mail, nome, telefone) por contrato, e o
livro nao o guarda: `processar` tira os campos de `DESCARTADOS_NA_ENTRADA`
antes de `receber`, e o resto do envelope segue como veio. A prova mora em
`tests/test_quiz_completado_sem_lead.py`.

## O que ele assina, e por que não assina mais

Os assuntos com contrato CONGELADO em `contracts/eventos/` que alguma célula
publica hoje. Assinar um stream que ninguém publica criaria um grupo de
consumo vazio e a impressão de que o caminho está pronto (a mesma razão pela
qual a `gamificacao` deixa `aula.concluida` de fora).

`matricula.situacao-alterada` era o assunto que esta célula mais queria, e
entrou em 05/09/2026, no degrau 8. Duas coisas precisavam ser verdade, e agora
sao: o contrato esta congelado e alguem o
publica de fato (a `alunos`, PR #1080, nos cinco caminhos que mexem no status).

Vale registrar o que se descobriu ao pagar essa divida, porque o comentario
anterior AQUI afirmava o contrario: a `alunos` **nao** publicava este assunto.
O que existia era a CARTA (`notificacao.devida`), que leva
"matricula.situacao-alterada" como um parametro dentro dela, e que so nasce
quando alguem GANHA acesso e tem identidade da plataforma. Recusa, suspensao,
encerramento e reembolso nao deixavam rastro nenhum.

Os quatro assuntos do funil (`pagina-vista`, `secao-vista`, `cta-clicado`,
`lead-capturado`) entram juntos em 26/09/2026, embora so `pagina-vista`
publique em producao neste minuto. Os outros tres saem da frente irma que mede
o funil (F3), em paralelo. Isso nao fere a regra do paragrafo acima porque
`xgroup_create(..., mkstream=True)` roda igual para todo item da lista: um
assunto sem publicador ainda vira grupo de consumo vazio, sem custo nem
travamento, ate a frente irma publicar de fato. Coordenar dois PRs no mesmo
minuto custaria mais do que esperar um grupo vazio por alguns commits.
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
    # A escada do funil de vendas (`funil`): visita, secao vista, clique e
    # lead. So `pagina-vista` publica hoje; os outros tres chegam da frente
    # irma (F3) que mede o funil, em paralelo (nota acima na docstring).
    "eventos.funil.pagina-vista",
    "eventos.funil.secao-vista",
    "eventos.funil.cta-clicado",
    "eventos.funil.lead-capturado",
    # Os dois fatos de compra do sistema de experimentos (`checkout`, contrato
    # F4a): quem foi atribuído a um pedido e quem pagou. É daqui que sai a
    # métrica principal do primeiro experimento (entrada no checkout) e as
    # conversões do funil de compra (DESENHO-COMUM.md, sessão de 26/09/2026).
    "eventos.checkout.pedido-atribuido",
    "eventos.checkout.pedido-pago",
]

#: Assuntos protegidos contra dado pessoal: nenhum deles pode levar customer,
#: e-mail, nome, telefone ou documento em `data`, por desenho da propria fonte
#: (o funil so tem `visitor_id`, opaco). E o SEGUNDO guarda: se um publicador
#: um dia divergir do contrato, o campo pessoal nao entra no livro por aqui,
#: mesmo com o envelope bem formado. Assunto novo com a mesma exigencia entra
#: NESTE conjunto, nunca cria um segundo.
ASSUNTOS_SEM_DADO_PESSOAL = frozenset(
    {
        "funil.pagina-vista",
        "funil.secao-vista",
        "funil.cta-clicado",
        "funil.lead-capturado",
        # DESENHO-COMUM.md, eventos de compra (F4a): "Sem customer, e-mail,
        # nome, telefone, documento."
        "checkout.pedido-atribuido",
        "checkout.pedido-pago",
    }
)

#: Campos de `data` que o livro descarta na entrada, por assunto. O contrato
#: os declara e continua declarando; o livro de fatos e que nao os guarda.
#: `quiz.completado` leva `lead` (e-mail, nome, telefone) e entra sem ele:
#: decisao 6 do mantenedor, sessao de 26/09/2026, "Limpar na entrada e
#: expurgar" (LGPD). Os fatos guardados antes dela perderam `lead` na migracao
#: `0004_quiz_completado_sem_lead`.
DESCARTADOS_NA_ENTRADA = {"quiz.completado": frozenset({"lead"})}

#: Comparado por chave, sem distinguir maiusculas.
CAMPOS_PESSOAIS_PROIBIDOS = frozenset(
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


def _campo_pessoal_proibido(tipo: str, dados: object) -> str | None:
    """A primeira chave proibida em `dados`, só para os assuntos protegidos.

    Os demais assuntos não têm validação de miolo por desenho desta célula
    (`recepcao.receber`: "quem valida o miolo é quem publica"). Os assuntos em
    `ASSUNTOS_SEM_DADO_PESSOAL` são a exceção deliberada, porque a fonte deles
    proíbe dado pessoal e o livro nunca pode guardar o que não pode expor.
    """
    if tipo not in ASSUNTOS_SEM_DADO_PESSOAL or not isinstance(dados, dict):
        return None
    for chave in dados:
        if isinstance(chave, str) and chave.lower() in CAMPOS_PESSOAIS_PROIBIDOS:
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
        dados = pre.get("data")
        descartar = DESCARTADOS_NA_ENTRADA.get(tipo, frozenset())
        if isinstance(dados, dict) and descartar & dados.keys():
            # Antes de `receber`: nem o fato nem um eventual EventoMorto guardam
            # o campo descartado.
            pre["data"] = {k: v for k, v in dados.items() if k not in descartar}
            texto = json.dumps(pre, ensure_ascii=False)
            cru = texto.encode("utf-8")
        campo = _campo_pessoal_proibido(tipo, pre.get("data"))
        if campo is not None:
            morto = EventoMorto.objects.create(
                corpo=texto[:100_000],
                motivo=(
                    f"campo pessoal proibido em assunto protegido: '{campo}' "
                    "(sem customer, e-mail, nome, telefone, documento)"
                ),
                tipo_declarado=tipo[:120],
                event_id_declarado=str(pre.get("event_id") or "")[:80],
            )
            logger.error(
                "EVENTO MORTO (id=%s): campo pessoal '%s' num assunto protegido "
                "contra dado pessoal. Inspecionar em /admin/, tentar de novo "
                "ou descartar com motivo.",
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
