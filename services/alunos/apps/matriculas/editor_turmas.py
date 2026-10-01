"""Admin editor for cohorts without changing existing enrollment records."""

import json
import secrets

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Matricula, Turma
from .turmas_publicadas import legacy_slug


def _authorized(request):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return (
        scheme.lower() == "bearer"
        and bool(token)
        and bool(settings.TOKEN_EDITOR_ADMIN)
        and secrets.compare_digest(token, settings.TOKEN_EDITOR_ADMIN)
    )


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _site(request):
    value = request.GET.get("site_id", "")
    return value if 0 < len(value) <= 64 else None


def _legacy(site_id):
    names = (
        Matricula.objects.filter(site_id=site_id)
        .exclude(turma="")
        .values_list("turma", flat=True)
        .distinct()
    )
    return {legacy_slug(name): name for name in names}


def _content(turma):
    return {"nome": turma.nome, "descricao": turma.descricao}


def _validate(content):
    if not isinstance(content, dict) or set(content) != {"nome", "descricao"}:
        raise ValueError("Use nome e descricao.")
    if (
        not isinstance(content["nome"], str)
        or not 1 <= len(content["nome"].strip()) <= 120
    ):
        raise ValueError("nome deve ter de 1 a 120 caracteres.")
    if not isinstance(content["descricao"], str) or len(content["descricao"]) > 10000:
        raise ValueError("descricao inválida.")


@csrf_exempt
def turmas(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    site_id = _site(request)
    if site_id is None:
        return _error("site_id obrigatório.", 422)
    items = [
        {
            "slug": row.slug,
            "nome": row.nome or (row.draft or {}).get("nome", ""),
            "published": row.published,
            "has_draft": row.draft is not None,
        }
        for row in Turma.objects.filter(site_id=site_id).order_by("slug")
    ]
    saved = {row["slug"] for row in items}
    items.extend(
        {"slug": slug, "nome": name, "published": True, "has_draft": False}
        for slug, name in _legacy(site_id).items()
        if slug not in saved
    )
    return JsonResponse(
        {"items": sorted(items, key=lambda row: row["nome"].casefold())}
    )


@csrf_exempt
def turma_publicada(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    site_id = _site(request)
    if site_id is None:
        return _error("site_id obrigatório.", 422)
    turma = Turma.objects.filter(site_id=site_id, slug=slug, published=True).first()
    if turma is None:
        return _error("Turma publicada não encontrada.", 404)
    return JsonResponse({"slug": turma.slug, "content": _content(turma)})


@csrf_exempt
def turma_draft(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method not in ("GET", "PUT"):
        return _error("Método não permitido.", 405)
    site_id = _site(request)
    if site_id is None:
        return _error("site_id obrigatório.", 422)
    turma = Turma.objects.filter(site_id=site_id, slug=slug).first()
    legacy = _legacy(site_id).get(slug)
    if request.method == "GET":
        if turma is None and legacy is None:
            return _error("Turma não encontrada.", 404)
        content = (
            turma.draft
            if turma and turma.draft is not None
            else _content(turma) if turma else {"nome": legacy, "descricao": ""}
        )
        return JsonResponse(
            {
                "slug": slug,
                "published": turma.published if turma else True,
                "has_draft": turma.draft is not None if turma else False,
                "content": content,
            }
        )
    try:
        content = json.loads(request.body)
        _validate(content)
    except (ValueError, UnicodeDecodeError) as exc:
        return _error(str(exc), 422)
    with transaction.atomic():
        if turma is None:
            turma = Turma.objects.create(
                site_id=site_id,
                slug=slug,
                nome=legacy or "",
                published=legacy is not None,
            )
        turma.draft = content
        turma.save(update_fields=["draft"])
    return JsonResponse(
        {
            "slug": slug,
            "published": turma.published,
            "has_draft": True,
            "content": content,
        }
    )


@csrf_exempt
def publish_turma(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método não permitido.", 405)
    site_id = _site(request)
    if site_id is None:
        return _error("site_id obrigatório.", 422)
    with transaction.atomic():
        turma = (
            Turma.objects.select_for_update().filter(site_id=site_id, slug=slug).first()
        )
        if turma is None or turma.draft is None:
            return _error("Rascunho não encontrado.", 404)
        try:
            _validate(turma.draft)
        except ValueError as exc:
            return _error(str(exc), 422)
        turma.nome = turma.draft["nome"].strip()
        if not turma.chave_matricula:
            turma.chave_matricula = _legacy(site_id).get(slug) or turma.nome
        turma.descricao = turma.draft["descricao"]
        turma.published = True
        turma.draft = None
        turma.save(
            update_fields=["nome", "chave_matricula", "descricao", "published", "draft"]
        )
    return JsonResponse(
        {
            "slug": slug,
            "published": True,
            "has_draft": False,
            "content": _content(turma),
        }
    )
