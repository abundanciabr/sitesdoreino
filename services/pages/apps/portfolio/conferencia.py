"""A conferência da escola: o pedido do aluno, o prazo, o aceite e a devolução.

ci:texto-publicado

A MARCA ACIMA LIGA O PORTÃO DO TRAVESSÃO neste arquivo inteiro
(`ci/travessao.py`, terceira regra de alcance no `CLAUDE.md`), pelo mesmo motivo
do `semaforo.py` ao lado: as recusas daqui são frases que o ALUNO lê na tela
dele, e elas não estão numa `templates/` nem num rótulo de `TextChoices`, que
são as duas regras que pegam sozinhas.

Lei: `docs/changespecs/CS-PAGES-0001.md`, critério AC-11, e
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §5 (degrau 11) e §7. Este módulo é
a regra do degrau 11 inteiro, tirando as telas.

O DESENHO É COPIADO, E ISSO É A PARTE MAIS IMPORTANTE DESTE ARQUIVO
--------------------------------------------------------------------
A fila humana desta escola já existe e já foi usada por gente de verdade: é a
dos marcos, em `/conquistas/interno`, na célula `gamificacao`. Três estados,
prazo em dias úteis, devolução com motivo de lista fechada, o mais urgente em
cima. Este módulo é esse MESMO desenho, reescrito para o portfólio.

Copia-se o PADRÃO entre células, nunca o código (Lei 3): importar
`apps.gamificacao.validacao` daqui amarraria duas casas pelo banco de uma
terceira. E não se inventa um segundo desenho: um jeito novo de fazer a mesma
coisa custa uma segunda tela para a equipe aprender, uma segunda regra de prazo
para a escola manter e uma segunda chance de errar.

O QUE ESTE MÓDULO NÃO FAZ
--------------------------
**Não põe o selo.** Aceitar fecha o pedido, e nada mais. O selo "conferido pela
escola", o evento `pages.portfolio.*` e a carta no sininho são o degrau 12
(critério AC-12), e a coluna que os guarda já espera vazia em `EstadoDoAluno`.
Escrever o selo aqui entregaria pela metade um critério que este PR não tem
como provar, e poria a mesma verdade em dois degraus.

**Não avisa o aluno.** Quem conta o que aconteceu é a TELA dele, que mostra o
estado do pedido e, quando ele volta, o motivo por extenso. Carta no sininho
depende do contrato de `notificacao.devida`, que é Rito e é o degrau 12.

**Não bloqueia quem ainda não cumpriu o roteiro.** A lista orienta, nunca
tranca (plano §7): um aluno com o semáforo amarelo pode pedir a conferência, e
é a equipe que diz o que falta. A única recusa é a do portfólio VAZIO, e ela
existe para não gastar o prazo da escola e a espera do aluno com uma estante
sem nenhuma obra dentro.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.portfolio.models import (
    EstadoDoPedido,
    MotivoDaDevolucao,
    PedidoDeConferencia,
    Portfolio,
)

# O prazo da escola para olhar um portfólio inteiro, em dias ÚTEIS. Cinco, o
# mesmo do marco real na fila de marcos, e pela mesma razão: alguém precisa
# abrir peça por peça e comparar com as quatro regras da professora.
#
# **Dias úteis, e não horas de relógio.** Um pedido feito na sexta à noite não
# vence no domingo, quando não há ninguém para atendê-lo. Prazo que vence
# enquanto a escola dorme não mede atraso: mede fim de semana.
DIAS_UTEIS_PARA_CONFERIR = 5


class ConferenciaRecusada(Exception):
    """O gesto não pode acontecer, e o motivo é regra, não erro de programa.

    Uma exceção, e não um `return None`: quem chama é uma tela, e uma tela que
    recebe `None` mostra "nada aconteceu", que é exatamente o que uma pessoa
    recusada NÃO pode ver. A mensagem é escrita para ser lida por gente.
    """


def _proximo_dia_util(momento):
    """O mesmo horário, no próximo dia que não é sábado nem domingo."""
    seguinte = momento + timedelta(days=1)
    while seguinte.weekday() >= 5:  # 5 = sábado, 6 = domingo
        seguinte += timedelta(days=1)
    return seguinte


def prazo_de(a_partir_de=None):
    """Quando este pedido passa a estar atrasado.

    **Contado no fuso da escola**, que é `America/Sao_Paulo` (o `TIME_ZONE`
    desta célula, com guarda em `tests/test_fuso_horario.py`). Contar em UTC
    daria um dia diferente para todo pedido feito depois das 21h, e a fila
    mostraria atraso onde não há (`armadilhas/099`).

    **Feriado não é considerado, e a ausência é declarada.** Uma tabela de
    feriados é dado que envelhece e que ninguém mantém; o custo de errar aqui é
    um pedido que aparece como atrasado um dia antes, numa fila que uma pessoa
    olha. Quando a escola tiver calendário próprio, este é o lugar de ligá-lo.
    """
    prazo = timezone.localtime(a_partir_de or timezone.now())
    for _ in range(DIAS_UTEIS_PARA_CONFERIR):
        prazo = _proximo_dia_util(prazo)
    return prazo


def pedido_em_analise(portfolio: Portfolio) -> PedidoDeConferencia | None:
    """O pedido que está esperando a escola, se houver um."""
    return portfolio.pedidos_de_conferencia.filter(
        estado=EstadoDoPedido.EM_ANALISE
    ).first()


def ultimo_pedido(portfolio: Portfolio) -> PedidoDeConferencia | None:
    """O pedido mais recente deste portfólio, em qualquer estado.

    É ele que a tela do aluno mostra: um pedido devolvido continua no banco
    (a história não se apaga), e é dele que sai o motivo que o aluno precisa
    ler para saber o que fazer.
    """
    return portfolio.pedidos_de_conferencia.order_by("-criado_em", "-id").first()


def pedir(portfolio: Portfolio | None) -> PedidoDeConferencia:
    """O aluno manda o portfólio para a escola olhar. O relógio começa a correr.

    **Pedir de novo depois de uma devolução é um pedido NOVO**, e não a edição
    do antigo. Aqui a prova é o portfólio, que o aluno arruma direto na estante,
    e um pedido reaproveitado apagaria o motivo que a escola escreveu na volta
    anterior. A linha velha fica, e é ela que guarda a história.

    **Duas recusas, e as duas dizem o que fazer.** Uma é a estante vazia; a
    outra é a fila dupla, e pedir de novo não a faz andar mais rápido.

    `portfolio` pode chegar `None`, e isso não é descuido de quem chama: o
    portfólio nasce na primeira escrita do aluno, então quem nunca guardou nada
    não tem linha nenhuma. É a MESMA recusa da estante vazia, e escrevê-la aqui
    uma vez só é o que impede a tela de ter a segunda cópia da frase.
    """
    if portfolio is None or not portfolio.pecas.exists():
        raise ConferenciaRecusada(
            "Guarde pelo menos uma peça antes de pedir a conferência. A escola "
            "olha as obras do seu portfólio, e uma estante vazia não tem o que "
            "ser olhado."
        )
    if pedido_em_analise(portfolio) is not None:
        raise ConferenciaRecusada(
            "O seu portfólio já está com a escola, esperando a conferência. "
            "Pedir de novo não faz a fila andar mais rápido, e a data da "
            "resposta continua sendo a que aparece aqui embaixo."
        )

    return PedidoDeConferencia.objects.create(portfolio=portfolio, prazo_ate=prazo_de())


def _conferir_quem_responde(pedido: PedidoDeConferencia, conferido_por: str) -> None:
    """As três recusas que restrição de banco nenhuma consegue fazer."""
    if pedido.estado != EstadoDoPedido.EM_ANALISE:
        raise ConferenciaRecusada(
            "Este pedido já foi respondido. Trocar a resposta de uma "
            "conferência fechada é outro gesto, com auditoria própria, e não "
            "passa por aqui."
        )
    if not conferido_por:
        raise ConferenciaRecusada(
            "Toda decisão humana tem nome. Sem o id de quem conferiu, a "
            "auditoria de uma conferência contestada não teria resposta meses "
            "depois."
        )
    if conferido_por == pedido.portfolio.aluno_id:
        raise ConferenciaRecusada(
            "Ninguém confere o próprio portfólio. Uma conferência em que a "
            "pessoa se aprova sozinha não confere nada."
        )


def aceitar(*, pedido: PedidoDeConferencia, conferido_por: str) -> PedidoDeConferencia:
    """Alguém da escola olhou o portfólio e disse sim.

    Fecha o pedido, com data e com nome. **O selo é o degrau 12**, e não sai
    daqui: o que este gesto grava é a decisão, e é dela que aquele degrau vai
    partir.
    """
    _conferir_quem_responde(pedido, conferido_por)

    with transaction.atomic():
        pedido.estado = EstadoDoPedido.ACEITO
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = conferido_por
        pedido.save(update_fields=["estado", "respondido_em", "respondido_por"])
    return pedido


def devolver(
    *, pedido: PedidoDeConferencia, conferido_por: str, motivo: str
) -> PedidoDeConferencia:
    """Ainda não. Com o que falta dito por escrito, e em português.

    **Esta função é metade do critério AC-11.** Devolver sem dizer por quê é o
    que faz um aluno desistir: ele fica sabendo que não foi, e não fica sabendo
    o que fazer. Por isso o motivo é obrigatório, e por isso ele sai de uma
    lista fechada que a escola escreveu: texto livre num campo de devolução
    vira crítica pessoal, e a lista existe para impedir exatamente isso.
    """
    _conferir_quem_responde(pedido, conferido_por)
    if motivo not in MotivoDaDevolucao.values:
        raise ConferenciaRecusada(
            f"{motivo!r} não é um dos motivos que esta escola aceita: "
            f"{MotivoDaDevolucao.values}. Devolver sem um deles deixaria o "
            "aluno sabendo que não foi, e sem saber o que fazer."
        )

    with transaction.atomic():
        pedido.estado = EstadoDoPedido.DEVOLVIDO
        pedido.motivo_da_devolucao = motivo
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = conferido_por
        pedido.save(
            update_fields=[
                "estado",
                "motivo_da_devolucao",
                "respondido_em",
                "respondido_por",
            ]
        )
    return pedido


def fila_da_equipe(site_id: str):
    """Os pedidos esperando nesta escola, o mais urgente em cima.

    **Não passa pelo `do_aluno`, e a diferença é o que a fila É.** Aquela porta
    é o isolamento entre ALUNOS (critério AC-07): ela responde "o que é meu?".
    Aqui quem pergunta é a equipe da escola, e a pergunta é outra: "o que está
    esperando por nós?". Passar a fila por uma porta feita para responder a
    primeira pergunta devolveria os pedidos do próprio monitor, e só eles.

    **A fronteira que continua de pé é a do SITE** (Lei 9): a equipe de uma
    escola nunca vê o pedido de outra, e é por isso que o `site_id` é
    obrigatório aqui em vez de opcional.

    **A ORDEM não se escreve nesta linha**, e sim no `ordering` do modelo: uma
    segunda expressão da mesma regra é a que diverge no dia em que alguém mudar
    só uma das duas.
    """
    return PedidoDeConferencia.objects.filter(
        portfolio__site_id=site_id, estado=EstadoDoPedido.EM_ANALISE
    ).select_related("portfolio")
