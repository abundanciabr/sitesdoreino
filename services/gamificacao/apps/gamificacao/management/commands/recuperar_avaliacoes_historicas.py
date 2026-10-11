"""Reaproveita avaliações já concluídas, sem publicar conteúdo."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.gamificacao.jornada import recuperar_avaliacoes_anteriores


class Command(BaseCommand):
    help = "Recupera avaliações antigas equivalentes, sem publicar conteúdo."

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True)
        parser.add_argument("--pessoa", required=True)
        parser.add_argument("--fatos", help="JSON local com fatos já evidenciados por Encomendas")

    def handle(self, *args, **options):
        fatos = None
        if options["fatos"]:
            fatos = json.loads(Path(options["fatos"]).read_text(encoding="utf-8"))
            if not isinstance(fatos, list):
                raise ValueError("O arquivo de fatos precisa conter uma lista JSON.")
        quantidade = recuperar_avaliacoes_anteriores(options["pessoa"], options["site"], fatos=fatos)
        self.stdout.write(f"{quantidade} avaliação(ões) histórica(s) registrada(s).")
