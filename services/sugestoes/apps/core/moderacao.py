"""O lado da equipe: a fila, o status com histórico e a avaliação interna.

Escopo do EVO-13, e só ele. O que a `ESPECIFICACAO-CELULA.md` §10 chama de MVP
**do lado de quem modera**: ver a fila do quadro com votos e status, mudar o
status (gravando histórico), recusar `nao_planejado` sem justificativa e
registrar a avaliação interna de produto.

**A fronteira deste arquivo é o crachá, e ela é mecânica.** Toda rota daqui
carrega `@exige_staff`, que é `@exige_sessao` mais uma pergunta: o papel desta
requisição é `staff`? Não sendo, a resposta é **403** — não um redirecionamento
para a porta, como faz a participação. A diferença é deliberada e é a Definição
de Pronto do MVP em pessoa (§11: *"endpoint de avaliação de produto retorna 403
para qualquer ator sem role de staff"*): quem chega aqui sem crachá não é
alguém que esqueceu de entrar, é alguém que já entrou e não tem o papel. Mandar
essa pessoa para a tela de login seria dizer "tente de novo" a quem não tem o
que tentar.

O papel continua **derivado a cada requisição** da `SUGESTOES_STAFF_EMAILS`
(`apps/core/sessao.py`, `DECISAO-EVO-01` §4). Consequência que vale conhecer:
tirar alguém da variável e reiniciar a célula tira o crachá **no ato**, mesmo de
quem já está com a sessão aberta. Há guarda para isso.

**O que NÃO mora aqui, e por quê:**

- **Mesclar sugestão.** A §10 põe merge em **V1.1**, não no MVP. O status
  `mesclado` existe no model e continua sem ninguém escrevendo nele — e a lista
  `STATUS_QUE_A_EQUIPE_ESCOLHE` abaixo o exclui de propósito, para que ele não
  entre pela porta dos fundos de um `<select>`.
- **Consumir o evento e avisar o aluno (o sininho).** É o EVO-21. Este arquivo
  AFIRMA o fato; quem escuta e notifica é outro despacho, na mesma célula.
- **Apagar sugestão.** Não existe: "remover" é status. A FK do histórico é
  `PROTECT` de propósito (EVO-11), e nenhuma rota daqui chama `delete()`.
"""

from functools import wraps

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.sugestoes import eventos
from apps.sugestoes.models import AvaliacaoInterna, HistoricoStatus, Sugestao
from apps.sugestoes.tasks import relay_apos_commit

from .participacao import exige_sessao, quadro_atual, sugestoes_ordenadas

PAGINA_FILA = "sugestoes/fila.html"
PAGINA_MODERAR = "sugestoes/moderar.html"

# Os cinco estados que a equipe escolhe. `MESCLADO` fica FORA: mesclar é V1.1
# (spec §10) e é uma operação transacional inteira — mover votos sem duplicar
# ator, preservar comentários, manter a URL antiga resolvendo. Deixá-lo no
# `<select>` daria à equipe um jeito de marcar "mesclado" sem que nada tivesse
# sido mesclado, e a lista de mescladas nasceria mentindo.
STATUS_QUE_A_EQUIPE_ESCOLHE = (
    Sugestao.Status.EM_ANALISE,
    Sugestao.Status.PLANEJADO,
    Sugestao.Status.EM_DESENVOLVIMENTO,
    Sugestao.Status.IMPLEMENTADO,
    Sugestao.Status.NAO_PLANEJADO,
)

# Spec §10: *"'não planejado' com justificativa obrigatória"*. É o único status
# que exige nota, e o motivo é o mesmo que fez a §5 da DECISAO-EVO-01 proibir o
# "acesso negado" seco: um "não vamos fazer" sem uma linha de explicação é a
# forma mais rápida de a Caixa ensinar aos alunos que sugerir não adianta.
EXIGEM_JUSTIFICATIVA = frozenset({Sugestao.Status.NAO_PLANEJADO})

# A escala das três notas da avaliação interna. A spec §6 só diz
# `PositiveSmallIntegerField`; o teto é decisão desta implementação, e existe
# para que a recusa venha como uma frase em português em vez de um
# `IntegrityError` do check constraint do Postgres.
NOTA_MINIMA = 0
NOTA_MAXIMA = 5
CAMPOS_DE_NOTA = ("impacto_educacional", "impacto_comercial", "esforco_tecnico")

SEM_CRACHA = (
    "Esta parte da Caixa é da equipe. Sua sessão está aberta, mas o seu e-mail "
    "não está na lista de quem modera."
)


class JustificativaObrigatoria(Exception):
    """`nao_planejado` sem nota. Recusado ANTES de qualquer escrita."""


def exige_staff(view):
    """Sessão de aluno não basta: aqui é preciso o papel `staff`.

    Empilha-se sobre `exige_sessao` (e não ao lado dele) de propósito: o
    anônimo continua sendo mandado para a porta, como em toda a célula, e só
    quem já está dentro chega a receber o 403. Isso mantém verde — e verdadeiro
    — o guarda que varre o urlconf exigindo o porteiro de sessão em toda rota
    não pública (`tests/test_inv_sem_sessao_nada.py`).

    O atributo `exige_staff` fica no objeto pelo mesmo motivo que o
    `exige_sessao`: é por ele que `tests/test_inv_so_staff_modera.py` deriva do
    urlconf a lista de rotas de moderação. Rota nova nasce dentro do guarda sem
    ninguém lembrar de cadastrá-la — e `functools.wraps` copia o `__dict__`, de
    modo que o atributo sobrevive ao `require_GET`/`require_POST` de fora.
    """

    @wraps(view)
    def cracha(request, ator, *args, **kwargs):
        if not ator.e_staff:
            return HttpResponseForbidden(SEM_CRACHA, content_type="text/plain")
        return view(request, ator, *args, **kwargs)

    cracha.exige_staff = True
    return exige_sessao(cracha)


def opcoes_de_status():
    """Os pares (valor, rótulo) que o `<select>` mostra — só os cinco de cima."""
    return [(status.value, status.label) for status in STATUS_QUE_A_EQUIPE_ESCOLHE]


def registrar_mudanca_de_status(*, sugestao, status_novo, nota, por):
    """Muda o status e grava o histórico **na mesma transação**.

    [INVARIANTE 2] As duas escritas são uma só: um status alterado sem rastro é
    pior que uma mudança que não aconteceu, porque ninguém consegue nem
    descobrir que aconteceu. O `atomic` garante o par; o `select_for_update`
    garante que duas pessoas da equipe mexendo na mesma sugestão ao mesmo tempo
    produzam duas linhas de histórico em ordem, e não uma sobrescrevendo a
    outra com um `status_anterior` que nunca existiu.

    [INVARIANTE 3] A justificativa é conferida **antes** de abrir a transação:
    recusa não precisa de rollback.

    Repare no que NÃO está aqui: nenhum caminho de correção. `HistoricoStatus`
    é append-only nos três degraus do EVO-11 (instância, queryset e trigger no
    Postgres) — corrigir é registrar de novo, e é isso que uma segunda chamada
    desta função faz.

    Registrar a mudança quando o status escolhido é o MESMO de agora é
    permitido, e de propósito: a nota é metade do valor deste formulário
    ("seguimos analisando, e o motivo é este"). Recusar o caso levaria a equipe
    a agir sem nada ficar escrito, que é exatamente o que o histórico existe
    para impedir.
    """
    nota = (nota or "").strip()
    if status_novo in EXIGEM_JUSTIFICATIVA and not nota:
        raise JustificativaObrigatoria(
            "Para marcar como “Não planejado” é preciso escrever o porquê — "
            "quem sugeriu vai ler essa justificativa (spec §10)."
        )

    with transaction.atomic():
        travada = (
            Sugestao.objects.select_for_update()
            .select_related("quadro")
            .get(pk=sugestao.pk)
        )
        status_anterior = travada.status
        travada.status = status_novo
        travada.save(update_fields=["status"])
        HistoricoStatus.objects.create(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
            alterado_por=por,
        )
        # [EVO-20] [INV-P6] O `sugestao.status-alterado` nasce AQUI DENTRO, na
        # outbox, antes do commit — é a letra da DoD do MVP (§11): "publicado
        # antes do commit da transação de status". Uma linha depois do `with`
        # já seria outro desenho: o status mudaria e o aviso do aluno poderia
        # nunca existir, sem nada indicando a falta.
        eventos.emitir_status_alterado(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
        )
    # E o publish, esse sim, é DEPOIS do commit: no fio nunca aparece um fato
    # que a transação ainda pode desfazer.
    transaction.on_commit(relay_apos_commit)
    return status_anterior


# ---------------------------------------------------------------------------
# As rotas
# ---------------------------------------------------------------------------


@require_GET
@exige_staff
def ver_fila(request, ator):
    """A fila de trabalho da equipe: o quadro inteiro, com votos e status.

    É a mesma consulta ordenada do quadro do aluno (`sugestoes_ordenadas`), e
    de propósito: duas ordenações para a mesma lista seriam duas verdades sobre
    o que está mais pedido, e a que a equipe vê seria a que ninguém testa. O
    que muda é o filtro — aqui se filtra por status, que é o eixo de quem
    trabalha a fila, e não por categoria, que é o eixo de quem procura.
    """
    quadro = quadro_atual()
    escolhido = (request.GET.get("status") or "").strip()
    valores = {valor for valor, _ in opcoes_de_status()}
    if escolhido and escolhido not in valores:
        escolhido = ""

    sugestoes = sugestoes_ordenadas(quadro).annotate(
        tem_avaliacao=Exists(
            AvaliacaoInterna.objects.filter(sugestao_id=OuterRef("pk"))
        )
    )
    if escolhido:
        sugestoes = sugestoes.filter(status=escolhido)

    return render(
        request,
        PAGINA_FILA,
        {
            "ator": ator,
            "quadro": quadro,
            "sugestoes": sugestoes,
            "status_disponiveis": opcoes_de_status(),
            "status_escolhido": escolhido,
        },
    )


def _pagina_de_moderacao(request, ator, sugestao, *, erros=(), status=200):
    return render(
        request,
        PAGINA_MODERAR,
        {
            "ator": ator,
            "sugestao": sugestao,
            "total_votos": sugestao.votos.count(),
            "historico": sugestao.historico.select_related("alterado_por"),
            "avaliacao": AvaliacaoInterna.objects.filter(sugestao=sugestao).first(),
            "status_disponiveis": opcoes_de_status(),
            "nota_rascunho": (request.POST.get("nota") or "").strip(),
            "erros": list(erros),
        },
        status=status,
    )


@require_GET
@exige_staff
def moderar(request, ator, sugestao_id):
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("categoria", "autor", "quadro"), pk=sugestao_id
    )
    return _pagina_de_moderacao(request, ator, sugestao)


@require_POST
@exige_staff
def mudar_status(request, ator, sugestao_id):
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("categoria", "autor", "quadro"), pk=sugestao_id
    )
    escolhido = (request.POST.get("status") or "").strip()

    if escolhido not in {valor for valor, _ in opcoes_de_status()}:
        # Vale também para `mesclado`: ele é status legítimo do model e mesmo
        # assim não passa por aqui, porque mesclar é V1.1 e é uma operação, não
        # um rótulo.
        return _pagina_de_moderacao(
            request,
            ator,
            sugestao,
            erros=["Escolha um dos status da lista."],
            status=400,
        )

    try:
        registrar_mudanca_de_status(
            sugestao=sugestao,
            status_novo=escolhido,
            nota=request.POST.get("nota"),
            por=ator.identidade,
        )
    except JustificativaObrigatoria as erro:
        return _pagina_de_moderacao(
            request, ator, sugestao, erros=[str(erro)], status=400
        )

    return HttpResponseRedirect(reverse("moderar", args=[sugestao.id]))


@require_POST
@exige_staff
def avaliar(request, ator, sugestao_id):
    """A avaliação interna: impacto, esforço, notas e a decisão de produto.

    `update_or_create` porque a avaliação é UMA por sugestão (`OneToOneField`)
    e é revisitada: a equipe volta, muda a nota de esforço, reescreve a
    decisão. Não é histórico — quem guarda a linha do tempo é o
    `HistoricoStatus`, e ele é de status, não de opinião interna.

    `avaliado_por` é sempre reescrito com quem salvou por último: a pergunta que
    essa coluna responde é "quem responde por este texto agora", e não "quem
    escreveu primeiro".
    """
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("categoria", "autor", "quadro"), pk=sugestao_id
    )

    erros = []
    notas = {}
    for campo in CAMPOS_DE_NOTA:
        cru = (request.POST.get(campo) or "").strip()
        try:
            valor = int(cru or 0)
        except ValueError:
            valor = -1
        if not NOTA_MINIMA <= valor <= NOTA_MAXIMA:
            erros.append(
                f"A nota de “{campo.replace('_', ' ')}” vai de "
                f"{NOTA_MINIMA} a {NOTA_MAXIMA}."
            )
        notas[campo] = valor

    if erros:
        return _pagina_de_moderacao(request, ator, sugestao, erros=erros, status=400)

    AvaliacaoInterna.objects.update_or_create(
        sugestao=sugestao,
        defaults={
            **notas,
            "notas": (request.POST.get("notas") or "").strip(),
            "decisao_produto": (request.POST.get("decisao_produto") or "").strip(),
            "avaliado_por": ator.identidade,
        },
    )
    return HttpResponseRedirect(reverse("moderar", args=[sugestao.id]))
