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

Copia-se o PADRÃO entre células, nunca o código: importar
`apps.gamificacao.validacao` daqui amarraria duas casas pelo banco de uma
terceira. E não se inventa um segundo desenho: um jeito novo de fazer a mesma
coisa custa uma segunda tela para a equipe aprender, uma segunda regra de prazo
para a escola manter e uma segunda chance de errar.

O SELO ENTROU AQUI NO DEGRAU 12, E O QUE ELE PROMETE É LIMITADO DE PROPÓSITO
-----------------------------------------------------------------------------
Aceitar deixou de só fechar o pedido: ele carimba o selo "conferido pela
escola" em `EstadoDoAluno` e emite `pages.portfolio.conferido.v1` na outbox, na
mesma transação (critério AC-12). O selo vale para o que o monitor VIU no dia
da conferência, e não para o que o portfólio for depois: a foto entra por link
colado e a escola não controla o que está do outro lado dele (plano §6.2). É
por isso que ele guarda a DATA, e é isso que o texto da tela do aluno diz com
todas as letras.

**Este módulo não paga XP, e não acende marco nenhum.** O marco real vale zero,
de propósito (plano §7, decisão 7 da Sessão A). Quem acende é a `gamificacao`,
no degrau 15, e ela só ESCUTA o evento.

O ACEITE AVISA O ALUNO, E A DEVOLUÇÃO NÃO
------------------------------------------
Desde 06/09/2026 o sim manda uma carta ao sininho dele
(`notificacao.devida.v1`, assunto `pages.portfolio-conferido`, acrescentado ao
enum no Rito de Contrato com o mantenedor). Quem pediu a conferência esperou um
prazo de cinco dias úteis, e antes disto só descobria a resposta reabrindo a
página por conta própria.

**A devolução continua muda de propósito.** O que a escola escreve ao devolver
é uma lista fechada de motivos que o aluno lê NA ESTANTE, ao lado das peças que
ele precisa arrumar, e é lá que a frase serve para alguma coisa. A mesma frase
num sininho, longe das obras, viraria só a notícia de que não foi.

O QUE ESTE MÓDULO AINDA NÃO FAZ
--------------------------------
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

from apps.portfolio import eventos
from apps.portfolio.models import (
    EstadoDoAluno,
    EstadoDoPedido,
    MotivoDaDevolucao,
    PedidoDeConferencia,
    Portfolio,
)
from apps.portfolio.tasks import relay_apos_commit

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


def pedir(
    portfolio: Portfolio | None, *, projeto=None, duvida_aluno: str = ""
) -> PedidoDeConferencia:
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
    from apps.portfolio import projetos

    if portfolio is None or (projeto is None and not portfolio.pecas.exists()):
        raise ConferenciaRecusada(
            "Adicione pelo menos um trabalho antes de pedir a avaliação. A escola "
            "olha os trabalhos do seu portfólio, e um portfólio vazio não tem o que "
            "ser olhado."
        )
    if pedido_em_analise(portfolio) is not None:
        raise ConferenciaRecusada(
            "O seu portfólio já está com a escola, esperando a conferência. "
            "Pedir de novo não faz a fila andar mais rápido, e a data da "
            "resposta continua sendo a que aparece aqui embaixo."
        )

    if projeto is not None and projeto.portfolio_id != portfolio.pk:
        raise ConferenciaRecusada("Este projeto não pertence ao portfólio do aluno.")
    duvida_aluno = projetos._texto("duvida_aluno", duvida_aluno, 3000)
    return PedidoDeConferencia.objects.create(
        portfolio=portfolio,
        projeto=projeto,
        duvida_aluno=duvida_aluno,
        contexto=projetos.capturar_contexto(portfolio, projeto),
        prazo_ate=prazo_de(),
    )


def dias_uteis_de_espera(desde, agora=None) -> int:
    """Quantos dias úteis inteiros o pedido já esperou, com a régua do prazo.

    Conta os mesmos passos de `prazo_de`, no mesmo fuso: um pedido que chega
    ao prazo esperou exatamente `DIAS_UTEIS_PARA_CONFERIR` dias úteis. Duas
    réguas diferentes fariam a fila dizer "no prazo" e "cinco dias de espera"
    sobre o mesmo pedido em dias diferentes.
    """
    agora = timezone.localtime(agora or timezone.now())
    passo = timezone.localtime(desde)
    dias = 0
    while (passo := _proximo_dia_util(passo)) <= agora:
        dias += 1
    return dias


def pedido_da_escola(site_id: str, numero: str) -> PedidoDeConferencia | None:
    """O pedido que a equipe desta escola apontou na fila, em QUALQUER estado.

    Em qualquer estado, e não só em análise, de propósito: quem clica num
    pedido que outra pessoa acabou de responder precisa ouvir quem respondeu e
    quando, e não um "não encontrado" que o faria procurar o pedido sumido. A
    fronteira que continua de pé é a do SITE (multissítio: site é dado).
    """
    if not numero.isdigit():
        return None
    return (
        PedidoDeConferencia.objects.filter(portfolio__site_id=site_id, pk=numero)
        .select_related("portfolio")
        .first()
    )


def _travar(pedido: PedidoDeConferencia) -> None:
    """Relê o pedido do banco e segura a linha até o fim da transação.

    **É isto que impede a decisão dupla.** O objeto que chega aqui foi lido
    quando a tela abriu, e outra pessoa da equipe pode ter respondido depois.
    Conferir o estado nele seria conferir uma foto velha. Com a linha travada,
    a segunda decisão espera a primeira terminar e relê o pedido já
    respondido, em vez de gravar por cima dela e publicar um segundo selo.
    """
    pedido.refresh_from_db(
        from_queryset=PedidoDeConferencia.objects.select_for_update(of=("self",))
    )


# O rótulo do estado é a frase que o ALUNO lê ("A escola conferiu o seu
# portfólio"); a equipe, que recebe esta recusa, precisa do gesto que foi feito.
_RESPOSTA_DITA_A_EQUIPE = {
    EstadoDoPedido.ACEITO: "aceitou a conferência",
    EstadoDoPedido.DEVOLVIDO: "devolveu com o que falta",
}


def _quando(momento) -> str:
    return timezone.localtime(momento).strftime("%d/%m/%Y às %H:%M")


def _quem(id_da_pessoa: str, quem_pergunta: str) -> str:
    return "você" if id_da_pessoa == quem_pergunta else id_da_pessoa


def _conferir_quem_responde(pedido: PedidoDeConferencia, conferido_por: str) -> None:
    """As três recusas que restrição de banco nenhuma consegue fazer.

    Quem chama já travou o pedido com `_travar`: o estado conferido aqui é o
    do banco, e não o da tela que abriu minutos antes.
    """
    if pedido.estado != EstadoDoPedido.EM_ANALISE:
        raise ConferenciaRecusada(
            f"Este pedido já foi respondido em {_quando(pedido.respondido_em)}, "
            f"por {_quem(pedido.respondido_por, conferido_por)}, que "
            f"{_RESPOSTA_DITA_A_EQUIPE[pedido.estado]}. Nada foi gravado "
            "de novo. Trocar a resposta de uma conferência fechada é outro "
            "gesto, com auditoria própria, e não passa por aqui."
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


def aceitar(
    *,
    pedido: PedidoDeConferencia,
    conferido_por: str,
    feedback_pontos_fortes: str = "",
    feedback_melhorar: str = "",
    feedback_proximo_passo: str = "",
) -> PedidoDeConferencia:
    """Alguém da escola olhou o portfólio e disse sim, e o SELO sai (AC-12).

    Quatro escritas, e as quatro na MESMA transação: o pedido fecha, o selo é
    carimbado no estado do aluno, o fato entra na outbox e a carta do sininho
    entra atrás dele. Ou as quatro acontecem, ou nenhuma. Um selo sem evento
    deixaria a trilha do aluno parada para sempre com o portfólio já conferido;
    um evento sem selo faria a plataforma acreditar num carimbo que a tela dele
    não mostra; e uma carta fora da transação avisaria o aluno de um sim que um
    erro seguinte tivesse desfeito.

    **A carta cita o fato, então o fato nasce primeiro.** O `origem_event_id`
    dela é o `event_id` dele, e é assim que de um aviso na tela se chega ao
    acontecimento que o causou. A ordem das duas linhas é a única coisa que
    garante isso.

    **A data do selo é a da conferência, e é a mesma do `respondido_em`**, lida
    uma vez só. Dois relógios lidos em linhas diferentes dariam ao selo e ao
    pedido instantes separados por microssegundos, e na virada da meia-noite a
    tela do aluno mostraria dois dias para a mesma decisão.

    **O selo é do PORTFÓLIO, não do pedido.** Ele mora em `EstadoDoAluno`
    porque quem o mostra é a estante do aluno e quem o lê é a porta de máquina,
    e nenhum dos dois pergunta qual foi o último pedido. Uma conferência nova,
    depois de peças novas, recarimba a mesma coluna com a data nova: o selo vale
    para o que o monitor viu no dia, e o dia que vale é sempre o último.

    **O estado do aluno nasce aqui, se ainda não existir.** Ele é criado quando
    o aluno marca o primeiro item do roteiro (degrau 07), e nada obriga quem
    montou uma estante inteira a ter marcado alguma coisa. Sem o
    `get_or_create`, justamente esse aluno receberia o sim da escola e nenhum
    selo.

    **Um sim por pedido, nunca dois** (§12 do dossiê da Comunidade). O pedido é
    relido com a linha travada ANTES de conferir o estado, e é por isso que a
    conferência mora dentro da transação: duas abas abertas na mesma fila não
    carimbam dois selos nem mandam duas cartas ao aluno.
    """
    with transaction.atomic():
        _travar(pedido)
        _conferir_quem_responde(pedido, conferido_por)

        from apps.portfolio import projetos

        feedback = {
            "feedback_pontos_fortes": projetos._texto(
                "feedback_pontos_fortes", feedback_pontos_fortes, 3000
            ),
            "feedback_melhorar": projetos._texto(
                "feedback_melhorar", feedback_melhorar, 3000
            ),
            "feedback_proximo_passo": projetos._texto(
                "feedback_proximo_passo", feedback_proximo_passo, 3000
            ),
        }

        agora = timezone.now()
        pedido.estado = EstadoDoPedido.ACEITO
        pedido.respondido_em = agora
        pedido.respondido_por = conferido_por
        for nome, valor in feedback.items():
            setattr(pedido, nome, valor)
        pedido.save(
            update_fields=["estado", "respondido_em", "respondido_por", *feedback]
        )

        # Um feedback de projeto confere apenas esta versão da escolha. O selo
        # global continua reservado à conferência do portfólio completo.
        if pedido.projeto_id is not None or not projetos.contexto_atual(pedido):
            return pedido

        estado, _ = EstadoDoAluno.objects.get_or_create(portfolio=pedido.portfolio)
        estado.selo_conferido_em = agora
        estado.selo_conferido_por = conferido_por
        estado.save(update_fields=["selo_conferido_em", "selo_conferido_por"])

        fato = eventos.fato_do_selo(pedido.portfolio, conferido_por=conferido_por)
        eventos.carta_do_selo(
            pedido.portfolio,
            conferido_por=conferido_por,
            origem_event_id=fato.event_id,
        )

    # DEPOIS do commit, e nunca dentro dele: publicar antes poria um evento no
    # fio para um sim que um erro seguinte tivesse revertido. Falhar aqui não
    # custa o fato, que fica pendente na outbox, nem a tela da equipe.
    transaction.on_commit(relay_apos_commit)
    return pedido


def devolver(
    *,
    pedido: PedidoDeConferencia,
    conferido_por: str,
    motivo: str,
    feedback_pontos_fortes: str = "",
    feedback_melhorar: str = "",
    feedback_proximo_passo: str = "",
) -> PedidoDeConferencia:
    """Ainda não. Com o que falta dito por escrito, e em português.

    **Esta função é metade do critério AC-11.** Devolver sem dizer por quê é o
    que faz um aluno desistir: ele fica sabendo que não foi, e não fica sabendo
    o que fazer. Por isso o motivo é obrigatório, e por isso ele sai de uma
    lista fechada que a escola escreveu: texto livre num campo de devolução
    vira crítica pessoal, e a lista existe para impedir exatamente isso.

    Relê e trava o pedido antes de conferir, pelo mesmo motivo do `aceitar`:
    uma devolução atrasada não troca por "ainda não" o sim que outra pessoa
    da equipe acabou de dar.
    """
    if motivo not in MotivoDaDevolucao.values:
        raise ConferenciaRecusada(
            f"{motivo!r} não é um dos motivos que esta escola aceita: "
            f"{MotivoDaDevolucao.values}. Devolver sem um deles deixaria o "
            "aluno sabendo que não foi, e sem saber o que fazer."
        )

    with transaction.atomic():
        _travar(pedido)
        _conferir_quem_responde(pedido, conferido_por)

        from apps.portfolio import projetos

        feedback = {
            "feedback_pontos_fortes": projetos._texto(
                "feedback_pontos_fortes", feedback_pontos_fortes, 3000
            ),
            "feedback_melhorar": projetos._texto(
                "feedback_melhorar", feedback_melhorar, 3000
            ),
            "feedback_proximo_passo": projetos._texto(
                "feedback_proximo_passo", feedback_proximo_passo, 3000
            ),
        }
        if motivo == MotivoDaDevolucao.ORIENTACAO and not any(feedback.values()):
            raise ConferenciaRecusada(
                "Escreva a orientação para o aluno antes de devolver."
            )

        pedido.estado = EstadoDoPedido.DEVOLVIDO
        pedido.motivo_da_devolucao = motivo
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = conferido_por
        for nome, valor in feedback.items():
            setattr(pedido, nome, valor)
        pedido.save(
            update_fields=[
                "estado",
                "motivo_da_devolucao",
                "respondido_em",
                "respondido_por",
                *feedback,
            ]
        )
    return pedido


def assumir(*, pedido: PedidoDeConferencia, assumido_por: str) -> PedidoDeConferencia:
    """Alguém da equipe diz "este é comigo", e a fila passa a mostrar o nome.

    COM-06 do dossiê da Comunidade: nenhuma espera fica sem responsável. A
    fila mostra quem assumiu cada pedido, e quem abre a tela sabe o que já tem
    dono e o que ninguém pegou.

    **Assumir não tranca a decisão.** Qualquer pessoa da equipe continua
    podendo aceitar ou devolver, e quem respondeu fica em `respondido_por`.
    Trancar faria um pedido esperar por alguém de férias.

    **Quem chega depois não tira o pedido de quem assumiu.** Trocar o dono em
    silêncio deixaria duas pessoas achando que o pedido é delas. Assumir de
    novo o próprio pedido não muda nada, e a data continua sendo a primeira.
    """
    with transaction.atomic():
        _travar(pedido)
        _conferir_quem_responde(pedido, assumido_por)
        if pedido.assumido_por == assumido_por:
            return pedido
        if pedido.assumido_por:
            raise ConferenciaRecusada(
                f"Este pedido já está com {pedido.assumido_por} desde "
                f"{_quando(pedido.assumido_em)}. Você ainda pode decidir o "
                "pedido, e a decisão fica gravada no seu nome."
            )
        pedido.assumido_por = assumido_por
        pedido.assumido_em = timezone.now()
        pedido.save(update_fields=["assumido_por", "assumido_em"])
    return pedido


def fila_da_equipe(site_id: str):
    """Os pedidos esperando nesta escola, o mais urgente em cima.

    **Não passa pelo `do_aluno`, e a diferença é o que a fila É.** Aquela porta
    é o isolamento entre ALUNOS (critério AC-07): ela responde "o que é meu?".
    Aqui quem pergunta é a equipe da escola, e a pergunta é outra: "o que está
    esperando por nós?". Passar a fila por uma porta feita para responder a
    primeira pergunta devolveria os pedidos do próprio monitor, e só eles.

    **A fronteira que continua de pé é a do SITE** (multissítio: site é dado): a equipe de uma
    escola nunca vê o pedido de outra, e é por isso que o `site_id` é
    obrigatório aqui em vez de opcional.

    **A ORDEM não se escreve nesta linha**, e sim no `ordering` do modelo: uma
    segunda expressão da mesma regra é a que diverge no dia em que alguém mudar
    só uma das duas.
    """
    return PedidoDeConferencia.objects.filter(
        portfolio__site_id=site_id, estado=EstadoDoPedido.EM_ANALISE
    ).select_related("portfolio")
