"""`/robos/conhecimento/comercial` — o conhecimento comercial deste site.

Só do administrador (mora sob `robos/`). O site é o do domínio pelo qual a
requisição chegou, como nas telas do catálogo. Aqui ele:

* vê quantas fontes o índice tem e quando foi conferido;
* manda atualizar agora (a mesma atualização da volta automática);
* marca um documento como material comercial ou depoimento deste site;
* procura como o agente procura, vendo fonte e vigência de cada trecho.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.clients import CatalogoClient
from apps.core.equipe import _quem
from apps.core.models import Documento

from . import conhecimento_comercial
from .models import MaterialComercial

RESULTADOS = {
    "atualizado": "Conhecimento comercial atualizado.",
    "marcado": "Marca salva e conhecimento comercial atualizado.",
    "desmarcado": "Marca tirada; o documento saiu do conhecimento comercial.",
    "sem_documento": "Escolha um documento do site.",
}


def _site(request) -> dict | None:
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


def _volta(resultado: str, relatorio: dict | None = None) -> HttpResponseRedirect:
    """De volta à tela; o que não respondeu na atualização vai junto, para a tela dizer."""
    faltou = "; ".join((relatorio or {}).get("faltou") or [])[:300]
    extra = f"&{urlencode({'faltou': faltou})}" if faltou else ""
    return HttpResponseRedirect(f"{reverse('conhecimento_comercial')}?resultado={resultado}{extra}")


@require_http_methods(["GET", "POST"])
def conhecimento_comercial_tela(request):
    site = _site(request)
    if site is None:
        return render(request, "agentes/comercial.html", {"admin": request.admin, "sem_site": True}, status=503)
    site_id = str(site.get("id"))
    if request.method == "POST":
        return _post(request, site)
    termo = (request.GET.get("q") or "").strip()[:200]
    produto = (request.GET.get("produto") or "").strip()[:200]
    resultado = conhecimento_comercial.consultar(site_id, termo, produto) if termo else None
    marcas = {m.documento_nome: m for m in MaterialComercial.objects.filter(site_id=site_id)}
    documentos = list(Documento.objects.filter(arquivado=False).order_by("ordem", "nome"))
    for d in documentos:
        d.marca = marcas.get(d.nome)
    return render(
        request,
        "agentes/comercial.html",
        {
            "admin": request.admin,
            "site": site,
            "numeros": conhecimento_comercial.numeros(site_id),
            "documentos": documentos,
            "marcados": [d for d in documentos if d.marca],
            "termo": termo,
            "produto": produto,
            "resultado": resultado,
            "mensagem": RESULTADOS.get(request.GET.get("resultado") or ""),
            "faltou": (request.GET.get("faltou") or "")[:300],
        },
    )


def _post(request, site: dict):
    acao = request.POST.get("acao") or ""
    if acao == "marcar":
        nome = (request.POST.get("documento") or "").strip()[:80]
        if not Documento.objects.filter(nome=nome).exists():
            return _volta("sem_documento")
        tipo = request.POST.get("tipo") or ""
        site_id = str(site.get("id"))
        if tipo not in MaterialComercial.Tipo.values:
            MaterialComercial.objects.filter(documento_nome=nome, site_id=site_id).delete()
            return _volta("desmarcado", conhecimento_comercial.atualizar(site))
        MaterialComercial.objects.update_or_create(
            documento_nome=nome,
            site_id=site_id,
            defaults={
                "site_host": str(site.get("host") or "")[:200],
                "tipo": tipo,
                "produto": (request.POST.get("produto") or "").strip()[:255],
                "oferta": (request.POST.get("oferta") or "").strip()[:255],
                "utilizavel": request.POST.get("utilizavel") == "1",
                "marcado_por": _quem(request)[:200],
            },
        )
        return _volta("marcado", conhecimento_comercial.atualizar(site))
    return _volta("atualizado", conhecimento_comercial.atualizar(site))
