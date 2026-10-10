"""Entrega a V4 aprovada da trilha, com progresso ilustrativo."""

from pathlib import Path

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

ARQUIVOS = Path(__file__).resolve().parents[2] / "static/funil/trilha-v4"
TIPOS = {
    "index.html": "text/html; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


@require_safe
def trilha_v4(request, arquivo="index.html"):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("página disponível apenas em meshcraft.top")
    if arquivo not in TIPOS:
        raise Http404("recurso inexistente")
    return HttpResponse((ARQUIVOS / arquivo).read_bytes(), content_type=TIPOS[arquivo])
