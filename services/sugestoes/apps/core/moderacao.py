"""Lado da equipe: muda o status com histórico, avisos e evento na mesma transação.
As rotas exigem o papel `staff`; sem ele a resposta é 403."""

from functools import wraps

import logging

from django.db import transaction
from django.http import HttpResponseForbidden

from apps.sugestoes import eventos
from apps.sugestoes.models import HistoricoStatus, Sugestao
from apps.sugestoes.tasks import relay_apos_commit

from .avisos import avisar_os_interessados, ids_de_plataforma
from .participacao import exige_sessao
from .resposta_rica import resposta_em_html_seguro

logger = logging.getLogger(__name__)

# `MESCLADO` fica fora: mesclar é uma operação inteira que ainda não existe.
STATUS_QUE_A_EQUIPE_ESCOLHE = (
    Sugestao.Status.EM_ANALISE,
    Sugestao.Status.PLANEJADO,
    Sugestao.Status.EM_DESENVOLVIMENTO,
    Sugestao.Status.IMPLEMENTADO,
    Sugestao.Status.NAO_PLANEJADO,
)

# A escala das notas da avaliação interna mora no Admin; aqui o teto é o do banco.

SEM_CRACHA = (
    "Esta parte da Caixa é da equipe. Sua sessão está aberta, mas o seu e-mail "
    "não está na lista de quem modera."
)


class RespostaForaDeImplementado(Exception):
    """Resposta escrita para uma fase que não é Implementado. Recusada ANTES."""


def exige_staff(view):
    """Exige o papel `staff` além da sessão: anônimo vai à porta, sem crachá leva 403.
    O atributo `exige_staff` fica no objeto para o urlconf poder ser varrido."""

    @wraps(view)
    def cracha(request, ator, *args, **kwargs):
        if not ator.e_staff:
            return HttpResponseForbidden(SEM_CRACHA, content_type="text/plain")
        return view(request, ator, *args, **kwargs)

    cracha.exige_staff = True
    return exige_sessao(cracha)


def registrar_mudanca_de_status(*, sugestao, status_novo, nota, por, resposta=None):
    """Muda o status e grava histórico, avisos e cartas na mesma transação.
    Implementado para Implementado sem nota só grava a `resposta` da equipe."""
    nota = (nota or "").strip()
    entrega = status_novo == Sugestao.Status.IMPLEMENTADO
    if resposta is not None:
        resposta = resposta_em_html_seguro(resposta)
        if resposta and not entrega:
            raise RespostaForaDeImplementado(
                "A resposta publicada na ideia só vale para a fase Implementado."
            )
    grava_resposta = entrega and resposta is not None

    with transaction.atomic():
        travada = (
            Sugestao.objects.select_for_update()
            .select_related("quadro")
            .get(pk=sugestao.pk)
        )
        status_anterior = travada.status
        campos = ["status"]
        if grava_resposta:
            travada.resposta_da_equipe = resposta
            campos.append("resposta_da_equipe")
        if entrega and status_anterior == status_novo and not nota:
            travada.save(update_fields=campos)
            return status_anterior
        travada.status = status_novo
        travada.save(update_fields=campos)
        HistoricoStatus.objects.create(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
            alterado_por=por,
        )
        # Os avisos de todos os interessados nascem na mesma transação, numa
        # chamada só, com consultas em número constante (a trava está aberta).
        avisos = avisar_os_interessados(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
        )
        # O evento de status vai para a outbox aqui dentro, antes do commit.
        fato = eventos.emitir_status_alterado(
            sugestao=travada,
            status_anterior=status_anterior,
            status_novo=status_novo,
            nota=nota,
            ator_id=por.id_da_plataforma,
        )
        # As cartas, uma por pessoa, saem no mesmo `atomic` e no mesmo insert.
        # Os destinatários vêm dos avisos recém-criados; sem id, só o `Aviso`.
        na_plataforma = ids_de_plataforma(a.destinatario_id for a in avisos)
        # Vínculo de cada destinatário da plataforma, tirado dos avisos recém-gravados,
        # para a carta dizer por que a pessoa recebeu o aviso.
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
