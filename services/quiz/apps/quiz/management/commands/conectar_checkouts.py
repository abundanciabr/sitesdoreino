import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.quiz.destinos import conectar_checkouts
from apps.quiz.models import Quiz


class Command(BaseCommand):
    help = "Conecta os dois checkouts a uma campanha direcionada já importada"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--arquivo", required=True, help="JSON {oferta_id: URL_HTTPS}"
        )

    def handle(self, *, slug, site_id, arquivo, **options):
        try:
            destinos = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as erro:
            raise CommandError(
                f"não foi possível ler JSON de {arquivo}: {erro}"
            ) from erro
        quiz = Quiz.objects.filter(site_id=site_id, slug=slug).first()
        if quiz is None:
            raise CommandError("quiz não encontrado neste site_id")
        try:
            conectar_checkouts(quiz, destinos)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(
            self.style.SUCCESS(f"checkouts conectados: {quiz.slug} @ {quiz.site_id}")
        )
