"""Publica as duas ofertas Roblox solicitadas pelo mantenedor."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft
from apps.produtos.models import Product
from apps.sites.models import Site


OFERTAS = (
    {
        "slug": "desafio-como-ganhar-em-dolar-com-roblox",
        "produto": "desafio-como-ganhar-em-dolar-com-roblox",
        "nome": "Desafio Como Ganhar em Dólar com Roblox",
        "preco": 14700,
        "descricao": "Conheça caminhos para trabalhar com criação no universo Roblox.",
        "texto": "Um desafio para explorar as possibilidades de criação no Roblox e dar os primeiros passos nessa área.",
        "cta": "Quero participar do desafio",
    },
    {
        "slug": "primeiros-dolares-com-roblox",
        "produto": "primeiros-dolares",
        "nome": "Curso Primeiros Dólares com Roblox",
        "preco": 157900,
        "descricao": "Desenvolva sua habilidade de modelagem 3D para Roblox.",
        "texto": "Aprenda a criar itens 3D para Roblox e desenvolva trabalhos para seu portfólio, com a intenção de oferecer seu serviço e buscar renda.",
        "cta": "Quero entrar no curso",
    },
)


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        site = Site.objects.get(host="meshcraft.top")
        with transaction.atomic():
            for item in OFERTAS:
                produto, _ = Product.objects.get_or_create(
                    slug=item["produto"],
                    defaults={"name": item["nome"], "price_cents": item["preco"]},
                )
                if produto.price_cents != item["preco"]:
                    produto.price_cents = item["preco"]
                    produto.save(update_fields=["price_cents"])
                oferta, _ = Offer.objects.get_or_create(
                    site=site, slug=item["slug"],
                    defaults={"product": produto, "price_cents": item["preco"]},
                )
                if oferta.product_id != produto.id:
                    raise ValueError(f"Oferta {item['slug']} já pertence a outro produto")
                if oferta.price_cents != item["preco"]:
                    oferta.price_cents = item["preco"]
                    oferta.version += 1
                    oferta.save(update_fields=["price_cents", "version"])
                pagina, _ = Page.objects.get_or_create(
                    site=site, slug=item["slug"], defaults={"offer": oferta},
                )
                if pagina.tipo != "oferta":
                    raise ValueError(f"Página {item['slug']} já tem outro tipo")
                if pagina.offer_id != oferta.id:
                    pagina.offer = oferta
                    pagina.save(update_fields=["offer"])
                secoes = [
                    {"nome": "cubo", "ordem": 0, "slots": {
                        "headline": item["nome"], "subheadline": item["descricao"],
                        "cta_texto": "Ver a oferta", "cta_destino": "#a-oferta",
                    }},
                    {"nome": "metodo", "ordem": 2, "slots": {
                        "headline": "Sobre " + ("o desafio" if item["preco"] == 14700 else "o curso"),
                        "texto": item["texto"],
                    }},
                    {"nome": "oferta", "ordem": 8, "slots": {
                        "headline": "Sua inscrição", "o_que_recebe": "Acesso ao " + item["nome"] + ".",
                        "cta_texto": item["cta"],
                    }},
                ]
                ultima = pagina.ultima_versao
                if ultima is not None:
                    self.stdout.write(f"https://meshcraft.top/{pagina.slug}: oferta conferida; conteúdo existente preservado (v{ultima.version})")
                    continue
                PageDraft.objects.update_or_create(page=pagina, defaults={"secoes": secoes})
                versao = pagina.publicar()
                self.stdout.write(f"https://meshcraft.top/{pagina.slug}: publicado v{versao.version}; {oferta.price_cents} centavos")
