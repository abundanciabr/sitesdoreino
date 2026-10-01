"""Private editor for quizzes. Published rows remain untouched while editing."""

import json
import secrets
import uuid

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Option, Question, Quiz, QuizDraft, QuizVersion, ResultBand, Site


def _authorized(request):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return (
        scheme.lower() == "bearer"
        and bool(token)
        and any(
            secrets.compare_digest(token, accepted)
            for accepted in settings.TOKENS_ACEITOS
        )
    )


def _error(message, status):
    return JsonResponse({"detail": message}, status=status)


def _site(request):
    site_id = request.GET.get("site_id", "")
    return Site.objects.filter(pk=site_id, active=True).first() if site_id else None


def _published(quiz):
    version = quiz.versions.filter(active=True).order_by("-id").first()
    if version is None:
        return {"title": quiz.title, "questions": [], "bands": []}
    return {
        "title": quiz.title,
        "questions": [
            {
                "text": question.text,
                "options": [
                    {"text": option.text, "points": option.points}
                    for option in question.options.all()
                ],
            }
            for question in version.questions.prefetch_related("options")
        ],
        "bands": [
            {
                "key": band.key,
                "title": band.title,
                "description": band.description,
                "min_score": band.min_score,
                "max_score": band.max_score,
                "botao_destino": band.botao_destino,
                "botao_rotulo": band.botao_rotulo,
            }
            for band in version.bands.all()
        ],
    }


def _validate(payload):
    if not isinstance(payload, dict) or set(payload) != {"title", "questions", "bands"}:
        raise ValueError("Use title, questions e bands.")
    if (
        not isinstance(payload["title"], str)
        or not 1 <= len(payload["title"].strip()) <= 200
    ):
        raise ValueError("title deve ter de 1 a 200 caracteres.")
    questions = payload["questions"]
    bands = payload["bands"]
    if not isinstance(questions, list) or not 1 <= len(questions) <= 255:
        raise ValueError("Informe de 1 a 255 perguntas.")
    if not isinstance(bands, list) or not 1 <= len(bands) <= 255:
        raise ValueError("Informe de 1 a 255 faixas.")
    for question in questions:
        if not isinstance(question, dict) or set(question) != {"text", "options"}:
            raise ValueError("Cada pergunta precisa de text e options.")
        if (
            not isinstance(question["text"], str)
            or not 1 <= len(question["text"].strip()) <= 500
        ):
            raise ValueError("Texto de pergunta inválido.")
        options = question["options"]
        if not isinstance(options, list) or not 2 <= len(options) <= 255:
            raise ValueError("Cada pergunta precisa de 2 a 255 opções.")
        for option in options:
            if not isinstance(option, dict) or set(option) != {"text", "points"}:
                raise ValueError("Cada opção precisa de text e points.")
            if (
                not isinstance(option["text"], str)
                or not 1 <= len(option["text"].strip()) <= 300
            ):
                raise ValueError("Texto de opção inválido.")
            if (
                type(option["points"]) is not int
                or not -(2**31) <= option["points"] < 2**31
            ):
                raise ValueError("Pontuação inválida.")
    keys = set()
    for band in bands:
        required = {"key", "title", "min_score", "max_score"}
        optional = {"description", "botao_destino", "botao_rotulo"}
        if (
            not isinstance(band, dict)
            or not required <= set(band)
            or set(band) - required - optional
        ):
            raise ValueError("Campos de faixa inválidos.")
        if (
            not isinstance(band["key"], str)
            or not 1 <= len(band["key"]) <= 100
            or band["key"] in keys
        ):
            raise ValueError("Chave de faixa inválida ou repetida.")
        keys.add(band["key"])
        if (
            not isinstance(band["title"], str)
            or not 1 <= len(band["title"].strip()) <= 200
        ):
            raise ValueError("Título de faixa inválido.")
        if (
            type(band["min_score"]) is not int
            or type(band["max_score"]) is not int
            or band["min_score"] > band["max_score"]
        ):
            raise ValueError("Intervalo de pontuação inválido.")
        for key, length in (
            ("description", 10000),
            ("botao_destino", 500),
            ("botao_rotulo", 80),
        ):
            if key in band and (
                not isinstance(band[key], str) or len(band[key]) > length
            ):
                raise ValueError(f"{key} inválido.")
        if bool(band.get("botao_destino")) != bool(band.get("botao_rotulo")):
            raise ValueError("Destino e rótulo do botão devem ser preenchidos juntos.")
    ranges = sorted((b["min_score"], b["max_score"]) for b in bands)
    if any(right[0] <= left[1] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("Faixas de pontuação não podem se sobrepor.")


@csrf_exempt
def quizzes(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    site = _site(request)
    if site is None:
        return _error("Site não encontrado.", 404)
    return JsonResponse(
        {
            "items": [
                {
                    "slug": quiz.slug,
                    "title": quiz.title,
                    "published": quiz.active,
                    "has_draft": hasattr(quiz, "draft"),
                }
                for quiz in Quiz.objects.filter(site=site)
                .select_related("draft")
                .order_by("slug")
            ]
        }
    )


@csrf_exempt
def quiz_draft(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method not in ("GET", "PUT"):
        return _error("Método não permitido.", 405)
    site = _site(request)
    if site is None:
        return _error("Site não encontrado.", 404)
    quiz = Quiz.objects.filter(site=site, slug=slug).first()
    if request.method == "GET":
        if quiz is None:
            return _error("Quiz não encontrado.", 404)
        content = quiz.draft.content if hasattr(quiz, "draft") else _published(quiz)
        return JsonResponse(
            {
                "slug": slug,
                "published": quiz.active,
                "has_draft": hasattr(quiz, "draft"),
                "content": content,
            }
        )
    try:
        payload = json.loads(request.body)
        _validate(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        return _error(str(exc), 422)
    with transaction.atomic():
        if quiz is None:
            quiz = Quiz.objects.create(
                site=site, slug=slug, title=payload["title"], active=False
            )
        QuizDraft.objects.update_or_create(quiz=quiz, defaults={"content": payload})
    return JsonResponse(
        {"slug": slug, "published": quiz.active, "has_draft": True, "content": payload}
    )


@csrf_exempt
def publish_quiz(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método não permitido.", 405)
    site = _site(request)
    if site is None:
        return _error("Site não encontrado.", 404)
    with transaction.atomic():
        quiz = Quiz.objects.select_for_update().filter(site=site, slug=slug).first()
        if quiz is None or not hasattr(quiz, "draft"):
            return _error("Rascunho não encontrado.", 404)
        content = quiz.draft.content
        try:
            _validate(content)
        except ValueError as exc:
            return _error(str(exc), 422)
        version = QuizVersion.objects.create(
            quiz=quiz, key=f"editor-{uuid.uuid4().hex[:12]}", weight=100, active=False
        )
        for order, item in enumerate(content["questions"], 1):
            question = Question.objects.create(
                version=version, order=order, text=item["text"].strip()
            )
            for option_order, option in enumerate(item["options"], 1):
                Option.objects.create(
                    question=question,
                    order=option_order,
                    text=option["text"].strip(),
                    points=option["points"],
                )
        for band in content["bands"]:
            ResultBand.objects.create(
                version=version,
                key=band["key"],
                title=band["title"].strip(),
                description=band.get("description", ""),
                min_score=band["min_score"],
                max_score=band["max_score"],
                botao_destino=band.get("botao_destino", ""),
                botao_rotulo=band.get("botao_rotulo", ""),
            )
        quiz.versions.filter(active=True).update(active=False)
        version.active = True
        version.save(update_fields=["active"])
        quiz.title = content["title"].strip()
        quiz.active = True
        quiz.save(update_fields=["title", "active"])
        quiz.draft.delete()
    return JsonResponse(
        {
            "slug": slug,
            "published": True,
            "has_draft": False,
            "version": version.key,
            "content": content,
        }
    )
