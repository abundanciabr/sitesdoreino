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
- **A lista de avisos do aluno e o marcar-como-lido.** Moram em
  `apps/core/avisos.py` (EVO-21; leque aberto no EVO-42). O que ESTE arquivo faz
  é a metade que não podia morar em outro lugar: os avisos de todos os
  interessados nascem dentro do mesmo `transaction.atomic()` da mudança de
  status, logo abaixo do histórico — nunca de uma volta pelo Redis, que faria
  status e aviso poderem divergir.
- **Apagar sugestão.** Não existe: "remover" é status. A FK do histórico é
  `PROTECT` de propósito (EVO-11), e nenhuma rota daqui chama `delete()`.
"""

from functools import wraps

import logging

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.sugestoes import eventos
from apps.sugestoes.models import (
    AvaliacaoInterna,
    CorredorAusente,
    HistoricoStatus,
    Sugestao,
)
from apps.sugestoes.tasks import relay_apos_commit

from .avisos import avisar_os_interessados, ids_de_plataforma
from .participacao import exige_sessao, quadro_atual, sugestoes_ordenadas

logger = logging.getLogger(__name__)

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

# [INV-SUG10] A frase que a trava do ChangeSpec diz — uma só, usada na recusa
# do POST e no aviso que a página mostra ANTES de alguém tentar. Duas cópias
# divergiriam no primeiro ajuste, e a que ninguém testa é a que fica errada.
#
# Ela diz o CAMINHO, e não só o "não": erro que não ensina o que fazer custa
# uma rodada de investigação a quem o lê. O endereço da tela de registro não
# entra aqui — sai de `{% url %}` no template, como todo endereço desta casa
# (`armadilhas/102`).
SEM_CORREDOR = (
    "Esta ideia está em “Planejado” e ainda não tem ChangeSpec aprovado "
    "registrado — por isso ela não vai para “Em desenvolvimento”. O corredor "
    "existe para que uma ideia aprovada nunca vire um prompt aberto do tipo "
    "“implemente isso” (FORMATO-CHANGESPEC.md §5). O caminho: escreva o "
    "ChangeSpec em docs/changespecs/, colha a aprovação humana e registre-a "
    "no botão “Registrar ChangeSpec aprovado”, aqui embaixo."
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

    [INVARIANTE 4 — INV-SUG10, EVO-40] `planejado → em_desenvolvimento` só
    acontece com ChangeSpec aprovado registrado. A conferência aqui é a que
    produz a frase; a que produz a IMPOSSIBILIDADE está dois degraus abaixo
    (`Sugestao.save()` e o trigger `sugestoes_exige_changespec`). A corrida
    entre o `sugestao.status` lido pela view e o estado real do banco é
    resolvida pelo degrau 2, que relê o status DENTRO da transação, depois do
    `select_for_update`.

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

    # [INV-SUG10] A trava do ChangeSpec, degrau 1 de 3 — o ponto de
    # estrangulamento. Aqui ela não acrescenta poder nenhum ao que o
    # `Sugestao.save()` já impõe (degrau 2) e o trigger do Postgres impõe
    # abaixo dele (degrau 3): o que ela acrescenta é a FRASE. Sem esta linha, a
    # recusa chegaria à equipe como um erro de servidor no meio de um POST, e
    # não como uma página dizendo o que fazer em seguida.
    #
    # Conferida ANTES de abrir a transação, como a justificativa acima: recusa
    # não precisa de rollback. E lida pelo gerente relacionado
    # (`sugestao.changespecs`), não por um import de `apps/core/changespecs.py`
    # — que importa `exige_staff` DESTE arquivo, e o par viraria um ciclo.
    if (
        status_novo == Sugestao.Status.EM_DESENVOLVIMENTO
        and sugestao.status == Sugestao.Status.PLANEJADO
        and not sugestao.changespecs.exists()
    ):
        raise CorredorAusente(SEM_CORREDOR)

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
        # [EVO-21 → EVO-42] [INVARIANTE 1] E os avisos de TODOS os interessados
        # nascem na mesma transação — não de uma volta pelo Redis. O evento
        # acima existe para o mundo de fora; o aviso é da própria Caixa, e
        # fazê-lo depender do fio só acrescentaria um jeito de o status mudar
        # sem ninguém ficar sabendo. Rollback aqui leva tudo junto: status,
        # histórico e o leque inteiro de avisos (`apps/core/avisos.py`).
        #
        # É UMA chamada, com custo de consultas CONSTANTE — não um laço aqui
        # nem lá dentro. A trava `select_for_update` acima está aberta neste
        # ponto: alongá-la proporcionalmente ao número de votantes seria fazer a
        # moderação ficar mais lenta exatamente nas ideias mais populares.
        avisos = avisar_os_interessados(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
        )
        # [EVO-20] [INV-P6] O `sugestao.status-alterado` nasce AQUI DENTRO, na
        # outbox, antes do commit — é a letra da DoD do MVP (§11): "publicado
        # antes do commit da transação de status". Uma linha depois do `with`
        # já seria outro desenho: o status mudaria e o aviso do aluno poderia
        # nunca existir, sem nada indicando a falta.
        fato = eventos.emitir_status_alterado(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
            ator_id=por.id_da_plataforma,
        )
        # [Rito de Contrato de 26/08/2026] E as CARTAS ENDEREÇADAS, uma por
        # pessoa, no mesmo `atomic` e no mesmo insert único. Decisão dele contra
        # "uma lista com todos os nomes": a lista de quem votou nunca circula, e
        # o evento não cresce com a plateia (DECISAO-fase-2-do-sininho §1).
        #
        # Os destinatários saem dos avisos que ACABARAM de nascer, e não de uma
        # segunda chamada a `interessados_em()`: seriam duas consultas a mais
        # para reconstruir uma lista que já está na mão — e, pior, duas listas
        # que poderiam divergir se alguém votasse no meio da transação.
        #
        # Quem ainda não tem id de plataforma fica de fora da carta e continua
        # com o `Aviso` local (`ids_de_plataforma`). Quem MODEROU sem id é outra
        # história: aquilo é fail-closed e já parou a transação uma linha acima.
        na_plataforma = ids_de_plataforma(a.destinatario_id for a in avisos)
        # [Rito de Contrato de 27/08/2026] destinatario_id da PLATAFORMA →
        # vínculo, para a carta poder dizer POR QUE esta pessoa recebeu este
        # aviso (`contracts/eventos/notificacao.devida.v1.json`,
        # `parametros.vinculo`). O `vinculo` já está em mãos: cada `Aviso` que
        # `avisar_os_interessados()` acabou de gravar carrega o dele — não é
        # preciso perguntar de novo a `interessados_em()`, que seria uma
        # segunda leitura correndo o risco de divergir da primeira se alguém
        # votasse no meio desta mesma transação.
        vinculos_por_plataforma = {
            na_plataforma[a.destinatario_id]: a.vinculo
            for a in avisos
            if a.destinatario_id in na_plataforma
        }
        eventos.emitir_cartas_de_notificacao(
            sugestao=travada,
            destinatarios=list(vinculos_por_plataforma.keys()),
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
            ator_id=por.id_da_plataforma,
            origem_event_id=str(fato.event_id),
            vinculos=vinculos_por_plataforma,
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
            # [INV-SUG10] O corredor do EVO-40, nas duas metades que a página
            # precisa: o que JÁ está registrado (a lista, que é a prova de que
            # a ideia pode andar) e a frase do que está barrado agora — que a
            # página mostra ANTES de alguém tentar, e não só depois do 400.
            "changespecs": sugestao.changespecs.select_related("registrado_por"),
            "sem_corredor": (
                SEM_CORREDOR
                if sugestao.status == Sugestao.Status.PLANEJADO
                and not sugestao.changespecs.exists()
                else ""
            ),
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
    except (JustificativaObrigatoria, CorredorAusente) as erro:
        # As duas recusam ANTES de qualquer escrita e as duas voltam como
        # página, com o motivo em português — nunca como 500. A `CorredorAusente`
        # também pode subir de dentro do `save()` (degrau 2), e cair aqui é o
        # que garante que nem o caminho de corrida vire erro de servidor.
        return _pagina_de_moderacao(
            request, ator, sugestao, erros=[str(erro)], status=400
        )
    except eventos.AtorSemIdDaPlataforma:
        # Esta recusa é DIFERENTE das de cima: ela sobe de DENTRO do `atomic`, e
        # o rollback é o ponto — nada foi escrito, e é isso que a torna segura
        # (INV-P6: estado sem evento é impossível, então recusar os dois juntos é
        # a única saída correta quando o evento não pode ser afirmado).
        #
        # Cai aqui, e não em 500, porque a pessoa da equipe consegue resolver
        # sozinha: sair e entrar de novo pelo site faz a porta gravar o id
        # (INV-SUG11). Uma tela de erro do servidor não diria isso a ninguém.
        logger.warning(
            "moderacao recusada: identidade local %s sem id_da_plataforma "
            "(INV-SUG11); sugestao %s ficou intacta",
            ator.identidade.id,
            sugestao.id,
        )
        return _pagina_de_moderacao(
            request,
            ator,
            sugestao,
            erros=[
                "Não conseguimos confirmar sua identidade na plataforma, então "
                "nada foi alterado. Saia e entre de novo pelo site, e tente "
                "outra vez — se continuar, avise a equipe técnica."
            ],
            status=409,
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
