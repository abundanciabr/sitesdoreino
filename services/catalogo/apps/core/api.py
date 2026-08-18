# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/catalogo.openapi.yaml (somente-leitura).
# Handlers servem do banco (apps.sites/produtos/ofertas) — a FORMA da API (schemas,
# inline hacks abaixo) já era validada contra o contrato congelado na Fase 0 e
# permanece intocada aqui (make contrato-check verde).
from django.core.exceptions import ValidationError
from ninja import Field, Path, Router, Schema
from ninja.errors import HttpError

# Aliases: os nomes Site/Product/Offer são reusados abaixo pelos Schemas de
# resposta (mesmo nome do contrato) — sem alias o import do model seria
# sombreado pela classe Schema de mesmo nome definida no mesmo módulo.
from apps.ofertas.models import Offer as OfferModel
from apps.produtos.models import Product as ProductModel
from apps.sites.models import Site as SiteModel

router = Router()


class Site(Schema):
    id: str
    host: str = Field(..., description="Domínio canônico do site, minúsculas")
    name: str
    active: bool
    theme: dict = Field(
        default_factory=dict,
        description="Tokens de identidade visual (cores, logo) — opaco para quem consome",
    )
    default_offer_slug: str = Field(
        default_factory=str, description="Oferta que a raiz do funil exibe"
    )


class Product(Schema):
    id: str
    name: str
    price_cents: int = Field(
        ..., ge=0
    )  # dinheiro é centavos inteiros — lei da plataforma
    active: bool


def _inline_offer_product(schema: dict) -> None:
    """Produto embutido na oferta é objeto inline no contrato (não $ref para o
    componente Product) — sem isso o django-ninja extrai a submodel como schema
    nomeado separado, o que quebraria o freeze de contrato."""
    schema.clear()
    schema.update(
        {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
            },
        }
    )


def _inline_offer_bump_items(schema: dict) -> None:
    schema["items"] = {
        "type": "object",
        "required": ["id", "product_id", "name", "price_cents"],
        "properties": {
            "id": {"type": "string"},
            "product_id": {"type": "string"},
            "name": {"type": "string"},
            "price_cents": {"type": "integer", "minimum": 0},
            "headline": {"type": "string"},
        },
    }
    schema.pop("additionalProperties", None)


class Offer(Schema):
    site_id: str
    slug: str
    version: int = Field(
        ...,
        description="Ofertas publicadas não são editadas — mudanças criam nova versão",
    )
    product: dict = Field(..., json_schema_extra=_inline_offer_product)
    price_cents: int = Field(..., ge=1)
    bumps: list = Field(
        default_factory=list, json_schema_extra=_inline_offer_bump_items
    )


@router.get(
    "/sites/by-host/{host}",
    response=Site,
    operation_id="getSiteByHost",
    summary="Resolve um domínio para o Site correspondente (INV-P11)",
    description='Host desconhecido ⇒ 404. Nunca devolve um site "padrão".',
    openapi_extra={
        "responses": {
            200: {"description": "Site ativo deste domínio"},
            404: {"description": "Domínio não cadastrado ou site inativo"},
        }
    },
)
def get_site_by_host(
    request,
    host: str = Path(
        ..., description="Hostname em minúsculas, sem porta (ex. loja1.com.br)"
    ),
):
    site = SiteModel.objects.filter(host=host.lower(), active=True).first()
    if site is None:
        raise HttpError(404, "domínio não cadastrado ou site inativo")
    return {
        "id": str(site.id),
        "host": site.host,
        "name": site.name,
        "active": site.active,
        "theme": site.theme or {},
        "default_offer_slug": site.default_offer_slug or "",
    }


@router.get(
    "/sites/{site_id}/ofertas/{slug}",
    response=Offer,
    operation_id="getOffer",
    summary="Oferta publicada DE UM SITE, com produto, preço e bumps",
    description=(
        "Slugs são únicos por site; a mesma oferta pode existir com preços "
        "distintos em sites distintos."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "Oferta corrente (versão publicada) deste site"},
            404: {
                "description": (
                    "Oferta inexistente/despublicada NESTE site (mesmo que exista "
                    "em outro — INV-P11)"
                )
            },
        }
    },
)
def get_offer(request, site_id: str, slug: str):
    try:
        offer = (
            OfferModel.objects.select_related("product")
            .prefetch_related("bumps__product")
            .get(site_id=site_id, slug=slug, site__active=True)
        )
    except (OfferModel.DoesNotExist, ValidationError, ValueError):
        # [INV-P11] mesma slug pode existir noutro site — a query já filtra por
        # site_id, então "existe noutro site" cai aqui como 404 igual a "não existe".
        raise HttpError(404, "oferta inexistente/despublicada neste site")
    return {
        "site_id": str(offer.site_id),
        "slug": offer.slug,
        "version": offer.version,
        "product": {"id": str(offer.product_id), "name": offer.product.name},
        "price_cents": offer.price_cents,
        "bumps": [
            {
                "id": str(bump.id),
                "product_id": str(bump.product_id),
                "name": bump.name,
                "price_cents": bump.price_cents,
                "headline": bump.headline,
            }
            for bump in offer.bumps.all()
        ],
    }


@router.get(
    "/produtos/{product_id}",
    response=Product,
    operation_id="getProduct",
    summary="Produto por id (produtos são globais; ofertas é que são por site)",
    openapi_extra={
        "responses": {
            200: {"description": "Produto"},
            404: {"description": "Inexistente"},
        }
    },
)
def get_product(request, product_id: str):
    try:
        produto = ProductModel.objects.get(id=product_id)
    except (ProductModel.DoesNotExist, ValidationError, ValueError):
        raise HttpError(404, "produto inexistente")
    return {
        "id": str(produto.id),
        "name": produto.name,
        "price_cents": produto.price_cents,
        "active": produto.active,
    }
