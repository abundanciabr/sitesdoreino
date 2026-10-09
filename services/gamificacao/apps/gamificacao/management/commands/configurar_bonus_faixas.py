from django.core.management.base import BaseCommand
from apps.gamificacao.bonus_faixas import configurar


class Command(BaseCommand):
    help = "Configura os bônus por conquista definidos pelo mantenedor em 09/10/2026."

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True)

    def handle(self, *args, **options):
        configurar(options["site"])
        self.stdout.write("Tabela de bônus preparada na economia do site.")
