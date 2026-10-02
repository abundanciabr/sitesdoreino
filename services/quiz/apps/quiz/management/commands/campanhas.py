import json

from django.core.management.base import BaseCommand, CommandError

from apps.quiz.campanhas import relatorio_campanhas
from apps.quiz.models import Quiz


class Command(BaseCommand):
    help = "Imprime coortes de chegada, conclusões e saídas do quiz em JSON."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--site-id", default="")
        parser.add_argument("--inicio")
        parser.add_argument("--fim")

    def handle(self, *, slug, site_id, inicio, fim, **opts):
        quizzes = Quiz.objects.filter(slug=slug)
        if site_id:
            quizzes = quizzes.filter(site_id=site_id)
        quantidade = quizzes.count()
        if quantidade == 0:
            raise CommandError("Não existe quiz com esse slug e site.")
        if quantidade > 1:
            raise CommandError("Há mais de um quiz com esse slug. Passe --site-id.")
        try:
            relatorio = relatorio_campanhas(quizzes.get(), inicio=inicio, fim=fim)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True))
