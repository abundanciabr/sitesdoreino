"""Executa uma rodada supervisionada de pagamentos Appmax."""

import json

from django.core.management.base import BaseCommand

from pagamentos.supervisao import processar_rodada


class Command(BaseCommand):
    help = "Processa avisos, reconcilia cobranças e republica eventos pendentes."

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write(json.dumps(processar_rodada(), ensure_ascii=False))
