from pathlib import Path
from django.http import FileResponse, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.http import require_GET


def permitido(request):
    admin = getattr(request, "admin", None)
    return bool(admin and not admin.get("equipe_apenas"))


@require_GET
def previa(request):
    if not permitido(request):
        return HttpResponseNotFound()
    resposta = render(request, "admin/saude_icone.html", {"admin": request.admin})
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_GET
def imagem(request):
    if not permitido(request):
        return HttpResponseNotFound()
    alvo = Path(__file__).parent / "assets" / "icone-site-proposto.png"
    resposta = FileResponse(alvo.open("rb"), content_type="image/png")
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta
