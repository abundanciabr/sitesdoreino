import uuid

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import OutboxEvent, Quiz, Submission
from .tasks import relay_apos_commit


def _quiz_do_site(request, slug):
    return get_object_or_404(Quiz, site_id=request.site["id"], slug=slug, active=True)


def formulario(request, slug):
    quiz = _quiz_do_site(request, slug)
    questions = quiz.questions.prefetch_related("options")

    if request.method != "POST":
        return render(
            request, "quiz/formulario.html", {"quiz": quiz, "questions": questions}
        )

    email = request.POST.get("email", "").strip()
    if not email:
        return render(
            request,
            "quiz/formulario.html",
            {"quiz": quiz, "questions": questions, "erro": "e-mail é obrigatório"},
            status=422,
        )

    score = 0
    respostas: dict[int, int] = {}
    for question in questions:
        valor = request.POST.get(f"pergunta_{question.id}")
        if valor is None:
            return render(
                request,
                "quiz/formulario.html",
                {
                    "quiz": quiz,
                    "questions": questions,
                    "erro": "responda todas as perguntas",
                },
                status=422,
            )
        # [pontuação só no servidor] a opção é buscada no banco pela pergunta;
        # um id de opção que não pertence a esta pergunta é resposta adulterada.
        opcao = question.options.filter(id=valor).first()
        if opcao is None:
            raise Http404("opção inválida para esta pergunta")
        respostas[question.id] = opcao.id
        score += opcao.points

    banda = quiz.bands.filter(min_score__lte=score, max_score__gte=score).first()
    result_key = banda.key if banda is not None else "sem_faixa"
    utm = {k[4:]: v for k, v in request.GET.items() if k.startswith("utm_")}

    with transaction.atomic():
        submissao = Submission.objects.create(
            quiz=quiz,
            site_id=quiz.site_id,
            score=score,
            result_key=result_key,
            answers=respostas,
            lead_email=email,
            lead_name=request.POST.get("nome", "").strip(),
            lead_phone=request.POST.get("telefone", "").strip(),
            utm=utm,
        )
        lead = {"email": submissao.lead_email}
        if submissao.lead_name:
            lead["name"] = submissao.lead_name
        if submissao.lead_phone:
            lead["phone"] = submissao.lead_phone
        OutboxEvent.objects.create(  # [RECEITA:R3 v1] [INV-P6] mesma transação do resultado
            event="quiz.completado",
            payload={
                "site_id": submissao.site_id,
                "quiz_slug": quiz.slug,
                "result_key": submissao.result_key,
                "score": submissao.score,
                "lead": lead,
                "utm": submissao.utm,
            },
        )
        # [RECEITA:R3 v1] publica já (latência sub-segundo); a task periódica
        # do worker cobre qualquer falha aqui — o evento nunca se perde.
        transaction.on_commit(relay_apos_commit)

    destino = reverse("quiz-resultado", args=[slug])
    return redirect(f"{destino}?lead={submissao.id}")


def resultado(request, slug):
    quiz = _quiz_do_site(request, slug)
    try:
        submissao_id = uuid.UUID(request.GET.get("lead", ""))
    except ValueError:
        raise Http404("lead inválido")
    submissao = get_object_or_404(
        Submission, id=submissao_id, quiz=quiz, site_id=quiz.site_id
    )
    banda = quiz.bands.filter(key=submissao.result_key).first()
    return render(
        request,
        "quiz/resultado.html",
        {"quiz": quiz, "submissao": submissao, "banda": banda},
    )
