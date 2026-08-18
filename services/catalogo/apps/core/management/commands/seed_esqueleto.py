# apps/core/management/commands/seed_esqueleto.py  # [RECEITA:R9 v1]
import os

from django.core.management.base import BaseCommand

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site

HOST_ESQUELETO_PADRAO = "esqueleto.exemplo.com.br"


class Command(BaseCommand):
    help = (
        "Dados do esqueleto — idempotente: rodar 2x não duplica nada. "
        "Cria o Site 'esqueleto' (host = domínio de operações, via env "
        "DOMINIO_OPERACOES) e a oferta 'curso-esqueleto' (990 cents) nesse site."
    )

    def handle(self, *args, **opts):
        host = os.environ.get("DOMINIO_OPERACOES", HOST_ESQUELETO_PADRAO).lower()

        site, site_criado = Site.objects.get_or_create(
            host=host,
            defaults={
                "name": "Esqueleto",
                "active": True,
                "default_offer_slug": "curso-esqueleto",
            },
        )

        produto, produto_criado = Product.objects.get_or_create(
            slug="curso-esqueleto",
            defaults={"name": "Curso Esqueleto", "price_cents": 990, "active": True},
        )

        oferta, oferta_criada = Offer.objects.get_or_create(
            site=site,
            slug="curso-esqueleto",
            defaults={"product": produto, "price_cents": 990, "version": 1},
        )

        def status(criado: bool) -> str:
            return "✅ criado" if criado else "ℹ já existia"

        self.stdout.write(
            self.style.SUCCESS(f"{status(site_criado)}: site {site.host} → {site.id}")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{status(produto_criado)}: produto {produto.slug} → {produto.id}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{status(oferta_criada)}: oferta {oferta.slug} em {site.host} → {oferta.price_cents} cents"
            )
        )
