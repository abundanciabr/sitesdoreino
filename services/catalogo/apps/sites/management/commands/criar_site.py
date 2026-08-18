# apps/sites/management/commands/criar_site.py  # [RECEITA:R11 v1]
from django.core.management.base import BaseCommand

from apps.sites.models import Site


class Command(BaseCommand):
    help = "Cadastra um site novo (idempotente por host)"

    def add_arguments(self, parser):
        parser.add_argument("host")
        parser.add_argument("name")

    def handle(self, host: str, name: str, **opts):
        site, criado = Site.objects.get_or_create(
            host=host.lower(), defaults={"name": name, "active": True}
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'✅ criado' if criado else 'ℹ já existia'}: {site.host} → {site.id}"
            )
        )
