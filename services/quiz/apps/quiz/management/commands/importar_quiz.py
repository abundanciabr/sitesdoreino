import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.quiz.conteudo import importar_documento
from apps.quiz.models import Site


class Command(BaseCommand):
    help = "Importa campanha direcionada no formato quiz-low-ticket/2"

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", required=True)
        parser.add_argument("--host", required=True)
        parser.add_argument("--site-id", required=True)
        parser.add_argument("--site-name", required=True)

    def handle(self, *, arquivo, host, site_id, site_name, **options):
        try:
            dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as erro:
            raise CommandError(
                f"não foi possível ler JSON de {arquivo}: {erro}"
            ) from erro
        host = host.strip().lower()
        if not host or "/" in host or ":" in host or len(host) > 255:
            raise CommandError("--host precisa ser nome de host sem protocolo ou porta")
        if (
            not site_id.strip()
            or len(site_id) > 64
            or not site_name.strip()
            or len(site_name) > 200
        ):
            raise CommandError(
                "--site-id e --site-name precisam ser preenchidos dentro do limite"
            )
        try:
            with transaction.atomic():
                site = Site.objects.filter(id=site_id).first()
                por_host = Site.objects.filter(host=host).first()
                if site is not None and site.host != host:
                    raise ValueError("site_id já pertence a outro host")
                if por_host is not None and por_host.id != site_id:
                    raise ValueError("host já pertence a outro site_id")
                if site is None:
                    site = Site.objects.create(id=site_id, host=host, name=site_name)
                quiz = importar_documento(dados, site)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(
            self.style.SUCCESS(f"quiz {quiz.slug} importado em {site.host}")
        )
