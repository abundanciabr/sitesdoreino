# apps/paginas/management/commands/criar_pagina_da_oferta.py
from django.core.management.base import BaseCommand, CommandError

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft
from apps.paginas.vocabulario import SECOES
from apps.sites.models import Site


def em_reais(centavos: int) -> str:
    """O preço como a pessoa lê na tela, a partir dos centavos que estão no banco."""
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


class Command(BaseCommand):
    """Semeia a página de oferta de um site, só com o que os dados provam.

    O rascunho nasce preenchido apenas pelos slots que se pode escrever com
    verdade a partir do que já existe no catálogo: o nome do produto e o preço
    da oferta. Os vilões, o método, os instrumentos, o percurso, o tempo, as
    seis recusas e a carta nascem VAZIOS, e isso não é falta de capricho: são
    afirmações que esta casa não tem como provar, e o destino delas é uma
    página pública. Slot vazio não aparece na tela, e página sem o índice de
    estúdios é página sem a seção de instrumentos, o que é honesto.

    Idempotente, e pela mesma regra do `criar_site` e do `criar_curso`: rodar
    de novo não duplica nada e não sobrescreve o que o dono escreveu. A partir
    do primeiro uso o dono deste texto é ele, e um semeador que sobrescrevesse
    apagaria o trabalho dele na próxima vez que alguém rodasse o comando.
    """

    help = (
        "Semeia a página 'oferta' de um site, ligada à oferta padrão dele, com o "
        "rascunho preenchido só pelo nome do produto e pelo preço (idempotente)."
    )

    def add_arguments(self, parser):
        parser.add_argument("host", help="o domínio do site, como está cadastrado")

    def handle(self, host: str, **opts):
        host = host.strip().lower()
        site = Site.objects.filter(host=host).first()
        if site is None:
            raise CommandError(
                f"não há site cadastrado no domínio '{host}'.\n"
                f"Cadastre primeiro: manage.py criar_site {host} '<nome do site>'"
            )
        if not site.default_offer_slug:
            raise CommandError(
                f"o site '{host}' não tem default_offer_slug, e é dele que sai a "
                "oferta desta página.\n"
                "Defina a oferta padrão do site antes de semear a página."
            )

        oferta = (
            Offer.objects.select_related("product")
            .filter(site=site, slug=site.default_offer_slug)
            .first()
        )
        if oferta is None:
            raise CommandError(
                f"o site '{host}' aponta para a oferta '{site.default_offer_slug}', "
                "que não existe neste site.\n"
                "Crie a oferta, ou corrija o default_offer_slug do site."
            )

        pagina, criada = Page.objects.get_or_create(
            site=site, slug="oferta", defaults={"offer": oferta}
        )
        rascunho, _ = PageDraft.objects.get_or_create(page=pagina)

        semeadas = {
            "cubo": {"headline": oferta.product.name},
            "oferta": {
                "headline": oferta.product.name,
                "preco_texto": em_reais(oferta.price_cents),
            },
        }
        if rascunho.secoes:
            self.stdout.write(
                f"ℹ o rascunho já tem texto e NÃO foi tocado: {site.host}/oferta"
            )
        else:
            rascunho.secoes = [
                {"nome": nome, "slots": slots} for nome, slots in semeadas.items()
            ]
            rascunho.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"{'✅ criada' if criada else 'ℹ já existia'}: página "
                f"{site.host}/{pagina.slug} → {pagina.id}"
            )
        )
        self.stdout.write(f"   oferta:  {oferta.slug} ({em_reais(oferta.price_cents)})")
        for secao in rascunho.secoes:
            preenchidos = ", ".join(sorted(secao["slots"]))
            self.stdout.write(f"   {secao['nome']}: {preenchidos}")

        escritas = {secao["nome"] for secao in rascunho.secoes}
        vazias = [nome for nome in SECOES if nome not in escritas]
        self.stdout.write(
            "   sem texto (não aparecem na página, e escrevê-las é decisão de "
            f"quem vende): {', '.join(vazias)}"
        )
