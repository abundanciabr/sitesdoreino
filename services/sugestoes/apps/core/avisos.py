"""Escreve o `Aviso` local de quem interagiu com a ideia quando o status muda.
A leitura é a página `/notificacoes` do `funil`; `/avisos` só redireciona."""

from django.db import transaction
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_safe

from apps.sugestoes.models import Aviso, Comentario, Identidade, Voto

PAGINA_UNICA_DE_AVISOS = "/notificacoes"


class AvisoForaDaTransacao(Exception):
    """`avisar_os_interessados()` foi chamada sem transação aberta."""


def interessados_em(sugestao) -> dict[str, str]:
    """Quem interagiu com a ideia e por qual vínculo, sem repetir pessoa.
    Quem acumula papéis fica com o primeiro: autor, depois comentário, depois voto."""
    vinculos: dict[str, str] = {sugestao.autor_id: Aviso.Vinculo.AUTOR}
    for identidade_id in (
        Comentario.objects.filter(sugestao=sugestao)
        .order_by()
        .values_list("autor_id", flat=True)
        .distinct()
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.COMENTARIO)
    for identidade_id in Voto.objects.filter(sugestao=sugestao).values_list(
        "autor_id", flat=True
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.VOTO)
    return vinculos


def ids_de_plataforma(locais) -> dict[str, str]:
    """Id local → id da plataforma, só de quem já tem, em uma consulta."""
    return {
        local: plataforma
        for local, plataforma in Identidade.objects.filter(
            pk__in=list(locais), id_da_plataforma__isnull=False
        ).values_list("pk", "id_da_plataforma")
    }


def avisar_os_interessados(
    *, sugestao, status_anterior: str, status_novo: str, nota: str = ""
) -> list[Aviso]:
    """Grava um `Aviso` por interessado, em lote, na transação da mudança de status.
    Recusa a escrita se não houver transação aberta."""
    if not transaction.get_connection().in_atomic_block:
        raise AvisoForaDaTransacao(
            "avisar_os_interessados() foi chamada fora de transaction.atomic(). "
            "Os avisos têm de nascer na MESMA transação da mudança de status: sem "
            "isso, um rollback deixa gente avisada de algo que não aconteceu — e o "
            "aviso e o status passam a poder divergir."
        )
    return Aviso.objects.bulk_create(
        [
            Aviso(
                destinatario_id=destinatario_id,
                sugestao=sugestao,
                status_anterior=status_anterior,
                status_novo=status_novo,
                nota=nota,
                vinculo=vinculo,
            )
            for destinatario_id, vinculo in interessados_em(sugestao).items()
        ]
    )


@require_safe
def ver_avisos(request):
    """Redireciona `/avisos` para a página única `/notificacoes`.
    O caminho é absoluto, fora do prefixo da célula."""
    return HttpResponseRedirect(PAGINA_UNICA_DE_AVISOS)
