"""Aulas avulsas: criar e reencontrar respostas em vídeo, fora de cursos."""

from __future__ import annotations

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.auditoria.models import Registro

from .aulas import _falha, _site_desta_requisicao
from .clients import CursosClient
from .views import _auditar

TELA = "admin/escola_aulas_avulsas.html"
TELA_DE_EDICAO = "admin/escola_aula_avulsa_editar.html"


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
        "endereco": f"/cursos/aulas/{slug}",
        "publicada_em": str(aula.get("publicada_em") or ""),
    }


def _desenhar_edicao(request, aula: dict, contexto: dict, status: int = 200):
    linha = _linha(aula)
    return render(
        request,
        TELA_DE_EDICAO,
        {
            "admin": request.admin,
            "aula": linha,
            "url_editar": reverse(
                "escola_aula_avulsa_editar", kwargs={"slug": linha["slug"]}
            ),
        }
        | contexto,
        status=status,
    )


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


def _sem_site_edicao(request, slug: str):
    return _desenhar_edicao(request, {"slug": slug}, {"sem_site": True}, status=503)


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


@require_http_methods(["GET", "POST"])
def aula_avulsa_editar(request, slug: str):
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site_edicao(request, slug)

    if request.method == "GET":
        desfecho, aulas = CursosClient().aulas_avulsas(site["id"])
        if desfecho != CursosClient.OK:
            return _desenhar_edicao(
                request,
                {"slug": slug},
                {"falha_da_sala": _falha(desfecho)},
                status=503,
            )
        aula = next(
            (
                item
                for item in (aulas or [])
                if isinstance(item, dict) and item.get("slug") == slug
            ),
            None,
        )
        if aula is None:
            return _desenhar_edicao(
                request,
                {"slug": slug},
                {
                    "erro": "Esta aula não está mais publicada. Volte à lista para conferir as aulas disponíveis.",
                    "aula_inexistente": True,
                },
                status=404,
            )
        return _desenhar_edicao(request, aula, {})

    rascunho = _rascunho(request)
    aula_atual = {"slug": slug} | rascunho
    if not rascunho["titulo"]:
        return _desenhar_edicao(
            request,
            aula_atual,
            {"erro": "Escreva o nome da aula antes de salvar. Nada foi alterado."},
            status=400,
        )
    if not rascunho["video_url"]:
        return _desenhar_edicao(
            request,
            aula_atual,
            {
                "erro": "Cole a URL do vídeo do YouTube antes de salvar. Nada foi alterado."
            },
            status=400,
        )

    desfecho, aula = CursosClient().editar_aula_avulsa(site["id"], slug, rascunho)
    if desfecho == CursosClient.OK:
        _auditar(
            request,
            Registro.EDITAR_AULA_AVULSA,
            slug,
            Registro.OK,
            "campos: titulo, video_url, descricao",
        )
        return _desenhar_edicao(request, aula or aula_atual, {"salva": True})

    _auditar(
        request,
        Registro.EDITAR_AULA_AVULSA,
        slug,
        (
            Registro.RECUSADO_PELA_CELULA
            if desfecho in (CursosClient.RECUSADO, CursosClient.NAO_EXISTE)
            else Registro.NAO_RESPONDEU
        ),
        f"campos: titulo, video_url, descricao; desfecho: {desfecho}",
    )
    if desfecho == CursosClient.RECUSADO:
        return _desenhar_edicao(
            request,
            aula_atual,
            {
                "erro": "A sala de aula não aceitou as alterações: corrija o nome, a URL do YouTube ou a descrição e salve de novo."
            },
            status=400,
        )
    if desfecho == CursosClient.NAO_EXISTE:
        return _desenhar_edicao(
            request,
            aula_atual,
            {
                "erro": "Esta aula não está mais publicada. Volte à lista para conferir as aulas disponíveis.",
                "aula_inexistente": True,
            },
            status=404,
        )
    if desfecho == CursosClient.RECUSOU:
        return _desenhar_edicao(
            request,
            aula_atual,
            {
                "erro": "A sala de aula recusou a admin: confira a senha do par entre as duas áreas no servidor. Nada foi alterado."
            },
            status=503,
        )
    if desfecho == CursosClient.SEM_CONFIGURACAO:
        return _desenhar_edicao(
            request,
            aula_atual,
            {
                "erro": "A sala de aula não está configurada para esta área. Confira o par entre as duas áreas no servidor. As alterações não foram enviadas."
            },
            status=503,
        )
    return _desenhar_edicao(
        request,
        aula_atual,
        {
            "erro": "A sala de aula não respondeu, e não sei se as alterações foram salvas. Recarregue a lista em um minuto antes de enviar novamente."
        },
        status=503,
    )
