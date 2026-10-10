"""A entrada da trilha leva à página protegida pela porta administrativa."""

from urllib.parse import urlencode

from django.http import Http404, HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@require_safe
def trilha_v4(request, arquivo="index.html"):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404
    if arquivo != "index.html":
        raise Http404
    destino = "/admin/trilha/"
    aluno = request.GET.get("aluno", "")
    if aluno:
        destino += "?" + urlencode({"aluno": aluno[:200]})
    resposta = HttpResponseRedirect(destino)
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta
