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
from django.http import HttpResponseForbidden

from apps.sugestoes import eventos
from apps.sugestoes.models import (
    CorredorAusente,
    HistoricoStatus,
    Sugestao,
)
from apps.sugestoes.tasks import relay_apos_commit

from .avisos import avisar_os_interessados, ids_de_plataforma
from .participacao import exige_sessao

logger = logging.getLogger(__name__)

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

# A escala das três notas da avaliação interna saiu daqui em 30/08/2026, junto
# com a tela que a impunha: quem conversa com a pessoa agora é o Admin
# (`services/admin/apps/core/caixa.py`, `NOTA_MINIMA`/`NOTA_MAXIMA`), e é lá que
# a recusa em português tem de nascer, porque é lá que existe um formulário. Do
# lado de cá o teto continua sendo do banco (o check constraint de
# `AvaliacaoInterna`) — e ele é a única trava que ninguém contorna.

SEM_CRACHA = (
    "Esta parte da Caixa é da equipe. Sua sessão está aberta, mas o seu e-mail "
    "não está na lista de quem modera."
)

# [INV-SUG10] A frase que a trava do ChangeSpec diz — uma só, e agora ela
# atravessa a fronteira: a recusa do contrato a devolve inteira ao Admin
# (`Recusa`), que a mostra à pessoa. Duas cópias divergiriam no primeiro ajuste,
# e a que ninguém testa é a que fica errada.
#
# Ela diz o CAMINHO, e não só o "não": erro que não ensina o que fazer custa uma
# rodada de investigação a quem o lê. **Ela não aponta para nenhuma tela** — nem
# por endereço, nem por "aqui embaixo": até 30/08/2026 apontava para o botão da
# tela de `/moderacao` desta célula, que foi aposentada (TAR-023), e uma frase
# que descreve a tela de OUTRA célula envelhece no dia em que ela mudar de
# layout. Ela descreve o FATO que falta; onde clicar é de quem desenha a tela.
SEM_CORREDOR = (
    "Esta ideia está em “Planejado” e ainda não tem ChangeSpec aprovado "
    "registrado — por isso ela não vai para “Em desenvolvimento”. O corredor "
    "existe para que uma ideia aprovada nunca vire um prompt aberto do tipo "
    "“implemente isso” (FORMATO-CHANGESPEC.md §5). O caminho: escreva o "
    "ChangeSpec em docs/changespecs/, colha a aprovação humana e registre a "
    "assinatura de obra desta ideia — é ela que destrava a passagem."
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
