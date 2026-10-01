"""Rascunhos privados de conversas assinadas pela escola no fórum."""

import os
from uuid import UUID

import httpx
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST


def _pedir(metodo, caminho, corpo=None):
    base = (os.environ.get("FORUM_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("TOKEN_FORUM") or "").strip()
    if not base or not token:
        return 503, None
    if not base.endswith("/interno"):
        base += "/interno"
    try:
        r = httpx.request(
            metodo,
            base + "/editor/" + caminho,
            json=corpo,
            headers={"Authorization": f"Bearer {token}"},
            timeout=4.0,
        )
        return r.status_code, r.json() if r.content else {}
    except (httpx.HTTPError, ValueError):
        return 503, None


def _pagina(request, *, erro="", draft=None, status=200, areas=None):
    if areas is None:
        codigo, dados = _pedir("GET", "areas")
        areas = (
            dados.get("areas", []) if codigo == 200 and isinstance(dados, dict) else []
        )
    return render(
        request,
        "admin/forum_topico.html",
        {
            "admin": request.admin,
            "erro": erro,
            "rascunho": draft,
            "areas": areas,
            "recado": request.GET.get("recado", ""),
        },
        status=status,
    )


@require_GET
def forum_topicos(request):
    status, dados = _pedir("GET", "topicos")
    if status != 200 or not isinstance(dados, (dict, list)):
        return _pagina(
            request, erro="Não consegui ler as conversas do fórum.", status=503
        )
    itens = (
        dados.get("items", dados.get("topicos", []))
        if isinstance(dados, dict)
        else dados
    )
    return render(
        request,
        "admin/forum_topicos.html",
        {
            "admin": request.admin,
            "itens": itens,
        },
    )


@require_GET
def forum_topico_novo(request):
    return _pagina(request)


@require_POST
def forum_topico_criar(request):
    corpo = {
        "area_slug": (request.POST.get("area_slug") or "").strip(),
        "titulo": (request.POST.get("titulo") or "").strip(),
        "texto": (request.POST.get("texto") or "").strip(),
    }
    status, dados = _pedir("POST", "topicos/rascunho", corpo)
    if (
        status not in (200, 201)
        or not isinstance(dados, dict)
        or not dados.get("rascunho_id")
    ):
        return _pagina(
            request,
            erro="Não consegui salvar o rascunho da conversa.",
            draft=corpo,
            status=422 if status in (400, 422) else 503,
        )
    return HttpResponseRedirect(
        reverse("forum_topico_editar", kwargs={"rascunho_id": dados["rascunho_id"]})
    )


@require_POST
def forum_topico_abrir_edicao(request, topico_id: int):
    status, dados = _pedir("POST", f"topicos/{topico_id}/rascunho")
    if (
        status not in (200, 201)
        or not isinstance(dados, dict)
        or not dados.get("rascunho_id")
    ):
        return _pagina(
            request,
            erro="Não consegui abrir a edição desta conversa.",
            status=422 if status in (400, 409, 422) else 503,
        )
    return HttpResponseRedirect(
        reverse("forum_topico_editar", kwargs={"rascunho_id": dados["rascunho_id"]})
    )


@require_GET
def forum_topico_editar(request, rascunho_id: UUID):
    status, dados = _pedir("GET", f"topicos/rascunho/{rascunho_id}")
    if status == 404:
        raise Http404
    if status != 200 or not isinstance(dados, dict):
        return _pagina(
            request, erro="Não consegui abrir o rascunho da conversa.", status=503
        )
    return _pagina(request, draft=dados)


@require_POST
def forum_topico_salvar(request, rascunho_id: UUID):
    corpo = {
        "area_slug": (request.POST.get("area_slug") or "").strip(),
        "titulo": (request.POST.get("titulo") or "").strip(),
        "texto": (request.POST.get("texto") or "").strip(),
    }
    status, _ = _pedir("PUT", f"topicos/rascunho/{rascunho_id}", corpo)
    if status not in (200, 201):
        return _pagina(
            request,
            erro="Não consegui salvar o rascunho da conversa.",
            draft={**corpo, "rascunho_id": str(rascunho_id)},
            status=422 if status in (400, 422) else 503,
        )
    return HttpResponseRedirect(
        reverse("forum_topico_editar", kwargs={"rascunho_id": rascunho_id})
        + "?recado=salvo"
    )


@require_POST
def forum_topico_publicar(request, rascunho_id: UUID):
    status, _ = _pedir("POST", f"topicos/rascunho/{rascunho_id}/publicar")
    if status not in (200, 201):
        _, rascunho = _pedir("GET", f"topicos/rascunho/{rascunho_id}")
        return _pagina(
            request,
            erro="Não consegui publicar a conversa; o rascunho continua guardado.",
            draft=rascunho,
            status=422 if status in (400, 409, 422) else 503,
        )
    return HttpResponseRedirect(reverse("forum_topicos"))
