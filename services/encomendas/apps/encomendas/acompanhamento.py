"""O pedido visto da cadeira do cliente: o que aconteceu, o que fazer, e os gestos.

Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §5.3 (a jornada de quatro
passos) e §5.5 (aprovar, ou pedir um ajuste). Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §3.4 e §7.2.

CADA ESTADO DA MÁQUINA TEM UMA FRASE, E O TESTE CONTA
------------------------------------------------------
`RECADO` cobre os DEZENOVE estados de `ESTADOS_DE_ENCOMENDA`, e
`tests/test_jornada_do_cliente.py` compara as duas listas. Não é zelo: a
máquina de estado desta célula cresceu três vezes em duas semanas, e um estado
novo sem frase é uma tela em branco para o cliente justamente no dia em que
alguma coisa incomum aconteceu com o pedido dele.

Cada frase é um par: **o que aconteceu** e **o que fazer**. O segundo é vazio
quando não há nada a fazer, e o vazio é a resposta certa: inventar uma tarefa
para quem só precisa esperar é o jeito mais barato de treinar alguém a ignorar
a tela.

OS TRÊS GESTOS QUE MORAM AQUI, E OS DOIS QUE NÃO
-------------------------------------------------
Aqui moram `aprovar`, `pedir_correcao` e `cancelar`, porque são os gestos do
fim da jornada e não tinham dono. Aceitar a proposta e contrapor NÃO moram
aqui: são `negociacao.aceitar_a_proposta` e `negociacao.propor`, escritos no
degrau 2.12, e chamá-los é o que a tela faz. Uma segunda escada de negociação
ao lado da primeira divergiria na primeira regra que mudasse.

NENHUMA LINHA DE COBRANÇA, DE NOVO
-----------------------------------
A pausa financeira de 22/08/2026 continua. Não há gesto de pagar neste arquivo,
não há rota de pagar na tela, e o estado `acordada` diz ao cliente que quem
confirma o pagamento é a escola. Quem grava essa confirmação é o plantão, por
`negociacao.confirmar_pagamento_pela_escola`, com autor e data.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction

from apps.encomendas import cardapio
from apps.encomendas.gestos import Desfecho
from apps.encomendas.models import Encomenda, MudancaDeStatus

NAO_E_ESTA_HORA = "nao_e_esta_hora"
SEM_AUTOR = "sem_autor"
SEM_O_QUE_AJUSTAR = "sem_o_que_ajustar"
AJUSTE_LONGO_DEMAIS = "ajuste_longo_demais"
CONTATO_NO_AJUSTE = "contato_no_ajuste"
ACABARAM_AS_CORRECOES = "acabaram_as_correcoes"
CANCELAMENTO_DEPOIS_DO_PAGAMENTO = "cancelamento_depois_do_pagamento"

MOTIVO_DA_APROVACAO = "o cliente aprovou a entrega"
MOTIVO_DA_CORRECAO = "o cliente pediu um ajuste"
MOTIVO_DA_MEDIACAO = (
    "o cliente pediu mais ajustes do que o acordo incluiu: vai ao plantao"
)
MOTIVO_DO_CANCELAMENTO = "o cliente cancelou o pedido"

# De onde o cliente cancela sozinho. É a interseção de duas listas: os estados
# de onde o banco aceita a seta para `cancelada`, e aqueles em que ninguém
# perdeu trabalho ainda. `aguardando_pagamento` fica de fora de propósito, e a
# ausência é a pausa financeira: cancelar depois que a escola confirmou o
# pagamento é reembolso, e reembolso é da célula `pagamentos`, que não existe.
ESTADOS_QUE_O_CLIENTE_CANCELA = frozenset(
    {
        Encomenda.Status.NA_FILA,
        Encomenda.Status.NO_MURAL,
        Encomenda.Status.ACORDADA,
        Encomenda.Status.PARA_RECLASSIFICAR,
    }
)

# O que aconteceu, e o que fazer, em cada um dos dezenove estados.
RECADO: dict[str, tuple[str, str]] = {
    Encomenda.Status.NA_FILA: (
        "Estou procurando um modelador para o seu pedido na Fila.",
        "",
    ),
    Encomenda.Status.NO_MURAL: (
        "O seu pedido esta no Mural, a vista dos modeladores do nivel dele.",
        "",
    ),
    Encomenda.Status.OFERECIDA: (
        "Um modelador recebeu o seu pedido e esta decidindo se aceita.",
        "",
    ),
    Encomenda.Status.RESERVADA: (
        "Um modelador pegou o seu pedido no Mural e esta montando a proposta.",
        "",
    ),
    Encomenda.Status.ABERTA: (
        "O seu pedido esta aberto para o primeiro modelador que aceitar.",
        "",
    ),
    Encomenda.Status.EM_NEGOCIACAO: (
        "O modelador enviou uma proposta de valor, prazo e entregaveis.",
        "Aceite a proposta, ou responda com uma contraproposta.",
    ),
    Encomenda.Status.ACORDADA: (
        "O acordo fechou. Valor, prazo, entregaveis e correcoes estao "
        "congelados e ninguem muda mais.",
        "Aguarde a escola confirmar o pagamento. O pagamento nao passa por "
        "este site.",
    ),
    Encomenda.Status.AGUARDANDO_PAGAMENTO: (
        "A escola confirmou o pagamento. A producao comeca na proxima passada "
        "do relogio.",
        "",
    ),
    Encomenda.Status.EM_PRODUCAO: (
        "O modelador esta trabalhando na sua peca.",
        "",
    ),
    Encomenda.Status.ENTREGUE: (
        "A peca chegou e esta passando pela conferencia da escola.",
        "",
    ),
    Encomenda.Status.EM_REVISAO: (
        "Um revisor da escola esta conferindo a entrega antes de ela chegar "
        "ate voce.",
        "",
    ),
    Encomenda.Status.AGUARDANDO_CLIENTE: (
        "A entrega passou pela revisao da escola e esta pronta para voce olhar.",
        "Aprove a entrega, ou peca um ajuste dizendo o que precisa mudar.",
    ),
    Encomenda.Status.EM_CORRECAO: (
        "O modelador esta fazendo o ajuste que voce pediu.",
        "",
    ),
    Encomenda.Status.PARA_RECLASSIFICAR: (
        "O seu pedido esta com o plantao da escola, que vai decidir o proximo "
        "passo dele.",
        "",
    ),
    Encomenda.Status.ABANDONADA: (
        "O modelador nao concluiu o trabalho. O seu pedido volta a procurar "
        "outro, sem custo para voce.",
        "",
    ),
    Encomenda.Status.EM_MEDIACAO: (
        "O plantao da escola esta mediando este pedido.",
        "",
    ),
    Encomenda.Status.APROVADA: (
        "Voce aprovou a entrega. Obrigado.",
        "",
    ),
    Encomenda.Status.CONCLUIDA: (
        "Este pedido esta concluido.",
        "",
    ),
    Encomenda.Status.CANCELADA: (
        "Este pedido foi cancelado.",
        "",
    ),
}


def correcoes_pedidas(projeto: Encomenda) -> int:
    """Quantos ajustes o cliente já pediu neste pedido.

    A conta sai do histórico de status, e não de uma coluna nova: cada entrada
    em `em_correcao` é um ajuste pedido, o histórico é append-only por gatilho, e
    um contador em coluna separada seria uma segunda verdade que um `update()`
    poderia desmentir.
    """
    return MudancaDeStatus.objects.filter(
        encomenda=projeto, para=Encomenda.Status.EM_CORRECAO
    ).count()


def correcoes_restantes(projeto: Encomenda) -> int:
    """Quantos ajustes ainda cabem no acordo. Nunca negativo.

    O número vem do ACORDO, e não do parâmetro `correcoes_incluidas`: o
    parâmetro é a régua com que o aluno monta a proposta, e o que vale depois é
    o que os dois combinaram e o banco congelou ([INV-ENC-N3]).
    """
    inclusas = projeto.acordo_correcoes_inclusas or 0
    return max(0, inclusas - correcoes_pedidas(projeto))


def o_que_o_cliente_pode_fazer(projeto: Encomenda) -> tuple[str, ...]:
    """Os gestos que a tela desenha como botão, neste estado, agora.

    Uma função só para a tela e para o teste, porque duas listas de botões (uma
    no template, outra no teste) concordam até o dia em que alguém muda uma
    delas.
    """
    gestos = []
    if projeto.status == Encomenda.Status.EM_NEGOCIACAO:
        gestos += ["aceitar", "contrapor", "desistir"]
    if projeto.status == Encomenda.Status.AGUARDANDO_CLIENTE:
        gestos += ["aprovar", "pedir_correcao"]
    if projeto.status in ESTADOS_QUE_O_CLIENTE_CANCELA:
        gestos.append("cancelar")
    return tuple(gestos)


@transaction.atomic
def aprovar(encomenda_id, agora: datetime, *, site_id: str, quem: str) -> Desfecho:
    """O cliente aprova a entrega, e o trabalho do aluno conta.

    Só de `aguardando_cliente`, que é o único estado em que a entrega já passou
    pela revisão humana: aprovar antes dela seria furar o [INV-ENC-S2], que
    existe para nenhuma primeira entrega chegar ao cliente sem revisão.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.status != Encomenda.Status.AGUARDANDO_CLIENTE:
        return Desfecho(
            feito=False,
            razao=NAO_E_ESTA_HORA,
            encomenda_em=projeto.status if projeto else "",
        )
    projeto.mudar_status(
        Encomenda.Status.APROVADA, ator_id=quem, motivo=MOTIVO_DA_APROVACAO
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)


@transaction.atomic
def pedir_correcao(
    encomenda_id,
    agora: datetime,
    *,
    site_id: str,
    quem: str,
    o_que_ajustar: str,
) -> Desfecho:
    """O cliente pede um ajuste. Acabaram as correções do acordo, vai à mediação.

    O §5.5 diz *"pedir um ajuste (uma vez, com texto estruturado); segundo
    pedido, mediação pelo plantão"*. O "uma vez" não é um literal neste arquivo:
    quantas correções cabem é o que o acordo congelou, e ler o número do acordo
    em vez de escrever `1` aqui é o que permite um pedido combinar duas sem
    ninguém mudar código.

    **A segunda recusa MEXE NO MUNDO**, e é de propósito: um cliente que pede
    mais do que foi combinado não pode ficar sem resposta nem receber um "não" e
    acabou. O pedido vai ao plantão, que é quem decide se aquilo é um ajuste
    justo ou um pedido novo, e o `encomenda_em` da resposta diz para onde ele
    foi.

    O texto do ajuste passa pela MESMA peneira de contato e pelo MESMO teto do
    briefing: é o segundo e último campo livre que o cliente escreve, e deixar
    qualquer um dos dois de fora teria tornado o guarda do briefing um teatro.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    pedido = (o_que_ajustar or "").strip()
    if not pedido:
        return Desfecho(feito=False, razao=SEM_O_QUE_AJUSTAR)
    if len(pedido) > cardapio.teto_do_texto(agora, site_id=site_id):
        return Desfecho(feito=False, razao=AJUSTE_LONGO_DEMAIS)
    if not cardapio.sem_contato(pedido):
        return Desfecho(feito=False, razao=CONTATO_NO_AJUSTE)

    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None or projeto.status != Encomenda.Status.AGUARDANDO_CLIENTE:
        return Desfecho(
            feito=False,
            razao=NAO_E_ESTA_HORA,
            encomenda_em=projeto.status if projeto else "",
        )
    if correcoes_restantes(projeto) <= 0:
        projeto.mudar_status(
            Encomenda.Status.EM_MEDIACAO, ator_id=quem, motivo=MOTIVO_DA_MEDIACAO
        )
        return Desfecho(
            feito=False, razao=ACABARAM_AS_CORRECOES, encomenda_em=projeto.status
        )

    projeto.mudar_status(
        Encomenda.Status.EM_CORRECAO,
        ator_id=quem,
        motivo=f"{MOTIVO_DA_CORRECAO}: {pedido}"[:200],
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)


@transaction.atomic
def cancelar(encomenda_id, agora: datetime, *, site_id: str, quem: str) -> Desfecho:
    """O cliente desiste do pedido antes de alguém pagar ou produzir.

    Depois da confirmação do pagamento a resposta é uma recusa NOMEADA, e não a
    recusa genérica: "não é esta hora" mandaria o cliente esperar, quando o que
    ele precisa é falar com a escola. Devolver dinheiro é da célula
    `pagamentos`, e ela não existe (lei §9).

    Dentro da negociação quem cancela é `negociacao.desistir`, porque lá sair
    tem consequência para o aluno do outro lado, e aquela função já sabe qual.
    """
    if not quem:
        return Desfecho(feito=False, razao=SEM_AUTOR)
    projeto = (
        Encomenda.objects.select_for_update()
        .filter(pk=encomenda_id, site_id=site_id)
        .first()
    )
    if projeto is None:
        return Desfecho(feito=False, razao=NAO_E_ESTA_HORA)
    if projeto.status == Encomenda.Status.AGUARDANDO_PAGAMENTO:
        return Desfecho(
            feito=False,
            razao=CANCELAMENTO_DEPOIS_DO_PAGAMENTO,
            encomenda_em=projeto.status,
        )
    if projeto.status not in ESTADOS_QUE_O_CLIENTE_CANCELA:
        return Desfecho(feito=False, razao=NAO_E_ESTA_HORA, encomenda_em=projeto.status)
    projeto.mudar_status(
        Encomenda.Status.CANCELADA, ator_id=quem, motivo=MOTIVO_DO_CANCELAMENTO
    )
    return Desfecho(feito=True, encomenda_em=projeto.status)
