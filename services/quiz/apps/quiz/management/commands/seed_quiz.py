# apps/quiz/management/commands/seed_quiz.py  # [RECEITA:R9 v1]
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.quiz.models import Option, Question, Quiz, ResultBand, Site

PERGUNTAS = [
    (
        "Qual é o seu maior desafio hoje?",
        [
            ("Não sei por onde começar", 0),
            ("Já comecei mas travei no meio", 5),
            ("Quero acelerar o que já funciona", 10),
        ],
    ),
    (
        "Quanto tempo você tem disponível por semana?",
        [
            ("Menos de 2 horas", 0),
            ("Entre 2 e 5 horas", 5),
            ("Mais de 5 horas", 10),
        ],
    ),
    (
        "Como você descreveria sua experiência atual?",
        [
            ("Iniciante", 0),
            ("Intermediário", 5),
            ("Avançado", 10),
        ],
    ),
]

FAIXAS = [
    ("iniciante", "Você está começando", "Foco em fundamentos primeiro.", 0, 9),
    ("intermediario", "Você já tem base", "Hora de acelerar o que funciona.", 10, 19),
    ("avancado", "Você está pronto para escalar", "Bora para o próximo nível.", 20, 30),
]


class Command(BaseCommand):
    help = "Dados fixos do Crivo (perguntas, opções, faixas de resultado): idempotente"

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True)
        parser.add_argument("--site-id", required=True)
        parser.add_argument("--site-name", required=True)
        parser.add_argument("--slug", default="crivo")

    def handle(self, *, host: str, site_id: str, site_name: str, slug: str, **opts):
        with transaction.atomic():
            site, _ = Site.objects.get_or_create(
                id=site_id, defaults={"host": host.lower(), "name": site_name}
            )
            quiz, _ = Quiz.objects.get_or_create(
                site=site, slug=slug, defaults={"title": "Crivo"}
            )
            for ordem, (texto, opcoes) in enumerate(PERGUNTAS, start=1):
                pergunta, _ = Question.objects.get_or_create(
                    quiz=quiz, order=ordem, defaults={"text": texto}
                )
                for ordem_opt, (texto_opt, pontos) in enumerate(opcoes, start=1):
                    Option.objects.get_or_create(
                        question=pergunta,
                        order=ordem_opt,
                        defaults={"text": texto_opt, "points": pontos},
                    )
            for key, title, descricao, minimo, maximo in FAIXAS:
                ResultBand.objects.get_or_create(
                    quiz=quiz,
                    key=key,
                    defaults={
                        "title": title,
                        "description": descricao,
                        "min_score": minimo,
                        "max_score": maximo,
                    },
                )
        self.stdout.write(
            self.style.SUCCESS(f"✅ seed do Crivo: {quiz.slug} @ {site.host}")
        )
