"""Moderação dos comentários; a porta administrativa autoriza a pessoa."""

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST
from apps.auditoria.models import Registro
from .aulas import _falha, _site_desta_requisicao
from .clients import CursosClient
from .views import _auditar


def _pagina(valor):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


@require_GET
def escola_comentarios_aulas(request):
    contexto = {"admin": request.admin}
    site = _site_desta_requisicao(request)
    if not site:
        contexto["sem_site"] = True
        return render(request, "admin/escola_comentarios.html", contexto, status=503)
    desfecho, dados = CursosClient().comentarios_das_aulas(
        site["id"], _pagina(request.GET.get("pagina"))
    )
    if desfecho != CursosClient.OK:
        contexto["falha"] = _falha(desfecho)
        return render(request, "admin/escola_comentarios.html", contexto, status=503)
    for comentario in dados["itens"]:
        comentario["criado_em"] = parse_datetime(comentario["criado_em"])
    contexto.update(dados)
    contexto["anterior"] = dados["pagina"] - 1 if dados["pagina"] > 1 else None
    contexto["proxima"] = (
        dados["pagina"] + 1 if dados["pagina"] < dados["paginas"] else None
    )
    contexto["recado"] = {
        "publico": "Comentário público para os alunos desta aula.",
        "privado": "Comentário privado: só o autor e os admins podem vê-lo.",
        "falha": "Não foi possível confirmar a alteração. Confira a visibilidade abaixo antes de tentar novamente.",
    }.get(request.GET.get("recado"))
    return render(request, "admin/escola_comentarios.html", contexto)


@require_POST
def escola_comentario_visibilidade(request, comentario_id: int):
    pagina = _pagina(request.POST.get("pagina"))
    destino = reverse("escola_comentarios_aulas")
    site = _site_desta_requisicao(request)
    valor = request.POST.get("visibilidade")
    recado = "falha"
    if site and valor in {"publico", "privado"}:
        desfecho, _ = CursosClient().visibilidade_do_comentario(
            site["id"],
            comentario_id,
            valor == "publico",
            request.admin.get("id") or "admin-local",
        )
        _auditar(
            request,
            Registro.EDITAR,
            f"comentario-aula:{comentario_id}",
            Registro.OK if desfecho == CursosClient.OK else Registro.NAO_RESPONDEU,
            f"visibilidade={valor}; resultado={desfecho}",
        )
        if desfecho == CursosClient.OK:
            recado = valor
    return HttpResponseRedirect(
        f"{destino}?pagina={pagina}&recado={recado}#comentario-{comentario_id}"
    )
