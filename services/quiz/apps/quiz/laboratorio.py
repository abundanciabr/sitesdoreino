import re

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .management.commands.funil import montar_funil
from .management.commands.seed_laboratorio_crivo import EMAIL, GUIA, ORIGENS, SLUG
from .models import OutboxEvent, Submission, TelemetryEvent
from .views import _entrada_usavel, _ler_quizzes, _quiz_do_site


@require_GET
def observacao(request, slug):
    if slug != SLUG:
        raise Http404
    quiz = _quiz_do_site(request, slug)
    entrada = _ler_quizzes(request).get(slug)
    contexto = {"quiz": quiz, "guia": GUIA, "rodada": None}
    if _entrada_usavel(entrada) and entrada["site_id"] == quiz.site_id:
        versao = quiz.versions.filter(pk=entrada["version_id"]).first()
        if versao is not None:
            sessao = entrada["session_id"]
            eventos = TelemetryEvent.objects.filter(
                site_id=quiz.site_id, quiz_slug=slug, session_id=sessao
            )
            submissao = Submission.objects.filter(quiz=quiz, session_id=sessao).first()
            origem = ORIGENS.get(
                (entrada.get("utm") or {}).get("content"),
                "Sem origem de demonstração reconhecida",
            )
            linhas = montar_funil(quiz, session_id=sessao).splitlines()
            perguntas = list(versao.questions.prefetch_related("options"))
            relatorio = []
            for linha in linhas[1:]:
                if " | utm=" in linha:
                    linha = f"Versão {versao.key} | origem: {origem}"
                elif re.fullmatch(r"  conversao: \d+ de \d+", linha):
                    pass
                elif re.fullmatch(
                    r"  pergunta \d+: viram \d+, sairam \d+, hesitaram \d+, "
                    r"tempo medio (?:\d+\.\d+s|sem amostra)",
                    linha,
                ) and any(linha.startswith(f"  pergunta {p.id}:") for p in perguntas):
                    pass
                else:
                    continue
                for pergunta in perguntas:
                    linha = linha.replace(
                        f"pergunta {pergunta.id}:", f"pergunta {pergunta.order}:"
                    )
                relatorio.append(linha)
            respostas = []
            if submissao:
                for pergunta in perguntas:
                    escolhida = submissao.answers.get(str(pergunta.id))
                    opcao = next(
                        (o for o in pergunta.options.all() if o.id == escolhida), None
                    )
                    respostas.append(
                        {
                            "pergunta": pergunta.text,
                            "escolha": (
                                opcao.text
                                if opcao
                                else "Escolha indisponível no cadastro atual"
                            ),
                        }
                    )
            contexto["rodada"] = {
                "versao": versao.key,
                "origem": origem,
                "visitas": eventos.filter(event_type="view_quiz").count(),
                "submissao": submissao,
                "respostas": respostas,
                "relatorio": "\n".join(relatorio),
            }
    eventos_sinteticos = OutboxEvent.objects.filter(
        event="quiz.completado",
        payload__site_id=quiz.site_id,
        payload__quiz_slug=SLUG,
        payload__lead__email=EMAIL,
        payload__utm__campaign=SLUG,
        payload__utm__source="laboratorio",
        payload__utm__content__in=list(ORIGENS),
    )
    contexto["pendentes"] = eventos_sinteticos.filter(published_at__isnull=True).count()
    contexto["entregues"] = eventos_sinteticos.filter(
        published_at__isnull=False
    ).count()
    return render(request, "quiz/observacao.html", contexto)
