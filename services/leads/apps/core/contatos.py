"""Contatos comerciais são os leads captados nos quizzes."""

from django.db.models import Q

from .models import Lead, TimelineEvent


ORIGEM_QUIZ = r"^quiz($|[:-])"


PALAVRA_DE_TESTE = r"(^|[^a-z0-9])(teste|test|sandbox)([^a-z0-9]|$)"
LEAD_DE_TESTE = (
    Q(name__iregex=PALAVRA_DE_TESTE)
    | Q(source__icontains="sandbox")
    | Q(email__iendswith="@example.com")
    | Q(email__iendswith="@exemplo.test")
)


def contatos_dos_quizzes():
    # O campo source pode mudar em um upsert posterior. O histórico preserva
    # a captura e evita transformar cadastro de aluno ou compra em contato.
    capturas = TimelineEvent.objects.filter(
        Q(event="quiz.completado")
        | Q(event="lead.upsert", payload__source__iregex=ORIGEM_QUIZ)
    ).values("lead_id")
    return Lead.objects.filter(
        Q(source__iregex=ORIGEM_QUIZ) | Q(pk__in=capturas)
    )
