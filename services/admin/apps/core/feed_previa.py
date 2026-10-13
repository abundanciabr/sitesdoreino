"""Prévia interativa privada do Feed; não altera alunos nem gamificação."""
from pathlib import Path

from django.http import FileResponse, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.http import require_GET

ASSETS = Path(__file__).resolve().parent / "feed_previa_assets"
TIPOS = {"feed.css": "text/css", "feed.js": "application/javascript", "hero.png": "image/png"}


def _permitido(request):
    admin = getattr(request, "admin", None)
    return bool(admin and not admin.get("equipe_apenas"))


@require_GET
def feed_previa(request):
    if not _permitido(request):
        return HttpResponseNotFound()
    resposta = render(request, "admin/feed_previa.html", {"admin": request.admin})
    resposta["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; media-src 'self' blob:; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
    )
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta


@require_GET
def feed_previa_asset(request, nome):
    if not _permitido(request) or nome not in TIPOS or not (ASSETS / nome).is_file():
        return HttpResponseNotFound()
    return FileResponse((ASSETS / nome).open("rb"), content_type=TIPOS[nome])
