"""Aulas avulsas: criar e reencontrar respostas em vídeo, fora de cursos."""

from __future__ import annotations

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .aulas import _falha, _site_desta_requisicao
from .clients import CursosClient
from .views import _auditar

TELA = "admin/escola_aulas_avulsas.html"


def _rascunho(request) -> dict:
    return {
        "titulo": (request.POST.get("titulo") or "").strip(),
        "video_url": (request.POST.get("video_url") or "").strip(),
        "descricao": (request.POST.get("descricao") or "").strip(),
    }


def _linha(aula: dict) -> dict:
    slug = str(aula.get("slug") or "")
    return {
        "titulo": str(aula.get("titulo") or ""),
        "descricao": str(aula.get("descricao") or ""),
        "video_url": str(aula.get("video_url") or ""),
        "slug": slug,
        "endereco": f"/aulas/{slug}/",
        "publicada_em": str(aula.get("publicada_em") or ""),
    }


def _desenhar(request, site: dict, contexto: dict, status: int = 200):
    desfecho, aulas = CursosClient().aulas_avulsas(site["id"])
    if desfecho != CursosClient.OK:
        return render(
            request,
            TELA,
            {"admin": request.admin, "falha_da_sala": _falha(desfecho)} | contexto,
            status=200 if contexto.get("criada") else 503,
        )
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "aulas": [_linha(aula) for aula in (aulas or []) if isinstance(aula, dict)],
            "url_criar": reverse("escola_aula_avulsa_criar"),
        }
        | contexto,
        status=status,
    )


def _sem_site(request):
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "sem_site": True,
            "url_criar": reverse("escola_aula_avulsa_criar"),
        },
        status=503,
    )


@require_GET
def aulas_avulsas(request):
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)
    return _desenhar(request, site, {})


@require_POST
def aula_avulsa_criar(request):
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)

    rascunho = _rascunho(request)
    if not rascunho["titulo"]:
        return _desenhar(
            request,
            site,
            {"rascunho": rascunho, "erro": "Escreva o nome da aula. Nada foi criado."},
            status=400,
        )
    if not rascunho["video_url"]:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "Cole a URL do vídeo do YouTube. Nada foi criado.",
            },
            status=400,
        )

    desfecho, aula = CursosClient().criar_aula_avulsa(site["id"], rascunho)
    if desfecho == CursosClient.OK:
        slug = str((aula or {}).get("slug") or "")
        _auditar(
            request,
            Registro.CRIAR_AULA_AVULSA,
            slug,
            Registro.OK,
            "campos: titulo, video_url, descricao",
        )
        return _desenhar(
            request,
            site,
            {"criada": _linha(aula or {})},
        )

    _auditar(
        request,
        Registro.CRIAR_AULA_AVULSA,
        rascunho["titulo"],
        (
            Registro.RECUSADO_PELA_CELULA
            if desfecho in (CursosClient.RECUSADO, CursosClient.JA_EXISTE)
            else Registro.NAO_RESPONDEU
        ),
        f"campos: titulo, video_url, descricao; desfecho: {desfecho}",
    )
    if desfecho == CursosClient.RECUSADO:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "A sala de aula não aceitou esta aula: corrija o nome, a URL do YouTube ou a descrição e envie de novo.",
            },
            status=400,
        )
    if desfecho == CursosClient.JA_EXISTE:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "A sala de aula encontrou uma colisão de endereço. Não envie de novo agora: recarregue a lista para conferir se a aula já apareceu.",
            },
            status=409,
        )
    if desfecho == CursosClient.RECUSOU:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "A sala de aula recusou a admin: confira a senha do par entre as duas áreas no servidor. Nada foi criado.",
            },
            status=503,
        )
    return _desenhar(
        request,
        site,
        {
            "rascunho": rascunho,
            "erro": "A sala de aula não respondeu, e não sei se a aula foi criada. Recarregue a lista em um minuto antes de enviar novamente.",
        },
        status=503,
    )
