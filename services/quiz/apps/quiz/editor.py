"""Private editor for quizzes. Published rows remain untouched while editing."""

import json
import secrets
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Option, Question, Quiz, QuizDraft, QuizVersion, ResultBand, Site


FORMATO_DIRECIONADO = "quiz-low-ticket/2"


def _authorized(request):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return (
        scheme.lower() == "bearer"
        and bool(token)
        and bool(settings.TOKEN_EDITOR_ADMIN)
        and secrets.compare_digest(token, settings.TOKEN_EDITOR_ADMIN)
    )


def _error(message, status):
    return JsonResponse({"detail": message}, status=status)


def _site(request):
    site_id = request.GET.get("site_id", "")
    return Site.objects.filter(pk=site_id, active=True).first() if site_id else None


def _published(quiz):
    if quiz.directed:
        versions = list(quiz.versions.order_by("id"))
        if not versions:
            return {
                "formato": FORMATO_DIRECIONADO,
                "quiz": {"slug": quiz.slug, "title": quiz.title},
                "ofertas": [],
                "versoes": [],
            }
        documents = [version.experience.get("documento") for version in versions]
        if not all(isinstance(document, dict) for document in documents):
            raise ValueError("Campanha publicada sem documento de origem.")
        return {
            "formato": FORMATO_DIRECIONADO,
            "quiz": documents[0]["quiz"],
            "ofertas": documents[0]["ofertas"],
            "versoes": [document["versao"] for document in documents],
        }
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


def _directed(payload, slug):
    if not isinstance(payload, dict) or payload.get("formato") != FORMATO_DIRECIONADO:
        return False
    from .conteudo import conferir_documento

    conferir_documento(payload)
    if payload["quiz"]["slug"] != slug:
        raise ValueError("O slug do documento difere do endereço do quiz.")
    return True


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
    possible_scores = {0}
    minimum_score = maximum_score = 0
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
        points = {option["points"] for option in options}
        minimum_score += min(points)
        maximum_score += max(points)
        if possible_scores is not None:
            if len(possible_scores) * len(points) > 50000:
                possible_scores = None
            else:
                possible_scores = {
                    score + point for score in possible_scores for point in points
                }
    if not -(2**31) <= minimum_score <= maximum_score < 2**31:
        raise ValueError("Pontuação total fora do intervalo permitido.")
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
            or not -(2**31) <= band["min_score"] < 2**31
            or not -(2**31) <= band["max_score"] < 2**31
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
        destination = band.get("botao_destino", "")
        if destination:
            parsed = urlsplit(destination)
            safe_relative = destination.startswith("/") and not destination.startswith(
                "//"
            )
            safe_absolute = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            if (
                destination != destination.strip()
                or "\\" in destination
                or any(ord(char) < 32 for char in destination)
                or not (safe_relative or safe_absolute)
            ):
                raise ValueError(
                    "Destino do botão deve ser caminho local ou URL HTTP(S)."
                )
    ranges = sorted((b["min_score"], b["max_score"]) for b in bands)
    if any(right[0] <= left[1] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("Faixas de pontuação não podem se sobrepor.")
    if possible_scores is None:
        covered_until = minimum_score - 1
        for low, high in ranges:
            if low > covered_until + 1 and covered_until < maximum_score:
                raise ValueError("Há pontuações possíveis sem faixa de resultado.")
            covered_until = max(covered_until, high)
        if covered_until < maximum_score:
            raise ValueError("Há pontuações possíveis sem faixa de resultado.")
    elif any(
        not any(low <= score <= high for low, high in ranges)
        for score in possible_scores
    ):
        raise ValueError("Há pontuações possíveis sem faixa de resultado.")


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
                    "directed": quiz.directed,
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
        try:
            content = quiz.draft.content if hasattr(quiz, "draft") else _published(quiz)
        except ValueError as exc:
            return _error(str(exc), 422)
        return JsonResponse(
            {
                "slug": slug,
                "published": quiz.active,
                "has_draft": hasattr(quiz, "draft"),
                "content": content,
                "directed": quiz.directed,
                "publicadas": list(
                    quiz.versions.order_by("id").values_list("key", flat=True)
                )
                if quiz.directed
                else [],
            }
        )
    try:
        payload = json.loads(request.body)
        directed = _directed(payload, slug)
        if not directed:
            _validate(payload)
        if quiz is not None and quiz.directed != directed:
            raise ValueError("Este slug pertence a outro tipo de quiz.")
    except (ValueError, UnicodeDecodeError) as exc:
        return _error(str(exc), 422)
    with transaction.atomic():
        if quiz is None:
            quiz = Quiz.objects.create(
                site=site,
                slug=slug,
                title=payload["quiz"]["title"] if directed else payload["title"],
                active=False,
                directed=directed,
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
            directed = _directed(content, slug)
            if directed != quiz.directed:
                raise ValueError("Tipo de rascunho incompatível com o quiz.")
            if not directed:
                _validate(content)
        except ValueError as exc:
            return _error(str(exc), 422)
        if directed:
            from .conteudo import importar_documento
            from .destinos import conectar_checkouts

            connected = None
            previous = quiz.versions.order_by("id").first()
            if previous is not None:
                offers = previous.experience.get("ofertas", {})
                if isinstance(offers, dict) and len(offers) == 2:
                    urls = {
                        key: value.get("checkout_url") for key, value in offers.items()
                    }
                    if all(urls.values()):
                        connected = urls
            try:
                importar_documento(content, site)
                if connected is not None:
                    conectar_checkouts(quiz, connected)
            except ValueError as exc:
                transaction.set_rollback(True)
                return _error(str(exc), 422)
            quiz.active = True
            quiz.save(update_fields=["active"])
            quiz.draft.delete()
            return JsonResponse(
                {
                    "slug": slug,
                    "published": True,
                    "has_draft": False,
                    "versions": [version["key"] for version in content["versoes"]],
                    "content": content,
                    "directed": True,
                }
            )
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
