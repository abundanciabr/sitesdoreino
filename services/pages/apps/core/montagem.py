"""Prévia privada e recursos da montagem visual do portfólio."""
from pathlib import Path

from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.portfolio import vitrine, dossie, comercial
from apps.portfolio.models import Portfolio
from .jornada import dono
from .views import site_atual, _sem_rastro


@require_GET
def script_montagem(request):
    caminho = Path(__file__).parent / "static/pages/portfolio-montagem.js"
    return HttpResponse(caminho.read_text(encoding="utf-8"), content_type="application/javascript")


@require_GET
def script_endereco(request):
    caminho = Path(__file__).parent / "static/pages/portfolio-endereco.js"
    return HttpResponse(caminho.read_text(encoding="utf-8"), content_type="application/javascript")


@require_GET
def previa(request):
    portfolio = Portfolio.objects.do_aluno(**dono(request)).first()
    publico = vitrine.snapshot_rascunho(portfolio) if portfolio else {"conteudo": {"pagina": {}}, "obras": []}
    pagina = publico["conteudo"]["pagina"]
    destaque = pagina.get("trabalho_destaque")
    hero = next((obra for obra in publico["obras"] if str(obra["id"]) == destaque), None) or next(iter(publico["obras"]), None)
    resposta = render(request, "pages/portfolio-previa.html", {"publico": publico, "hero": hero,
        "apelido": (portfolio.apelido if portfolio else "") or request.aluno.get("nome", ""),
        "contato_url": comercial.url_publica(publico.get("oferta", {}).get("contato")), "pdf_url": reverse("dossie")})
    resposta["Cache-Control"] = "no-store"
    resposta["X-Frame-Options"] = "SAMEORIGIN"
    resposta["Content-Security-Policy"] = "frame-ancestors 'self'"
    return resposta


@require_GET
def pdf_publico(request, apelido):
    portfolio = vitrine.publicada(site_id=site_atual(), apelido=apelido)
    if portfolio is None:
        raise Http404
    contexto = vitrine.contexto_comercial(portfolio)
    publico = contexto.get("publico") or vitrine.snapshot_rascunho(portfolio)
    resposta = HttpResponse(dossie.montar_visual(apelido=portfolio.apelido, publico=publico,
        imagens=dossie.bytes_de_imagens_publicadas(portfolio, publico),
        endereco_publico=request.build_absolute_uri(vitrine.endereco(portfolio.apelido))), content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{dossie.nome_do_arquivo(portfolio.apelido)}"'
    return _sem_rastro(resposta)
