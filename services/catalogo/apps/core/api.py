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
from apps.sites.menu import normalizar_menu
from apps.ofertas.models import Offer as OfferModel
from apps.produtos.models import Product as ProductModel
from apps.sites.models import Site as SiteModel

router = Router()


def _inline_site_languages(schema: dict) -> None:
    """Mesmo motivo do `_inline_offer_bump_items`: o contrato declara o item de
    `languages` como objeto inline, não como componente nomeado."""
    schema["items"] = {
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {
                "type": "string",
                "description": "BCP 47 em minúsculas, exatamente como aparece na URL",
            },
            "indexable": {
                "type": "boolean",
                "default": True,
                "description": (
                    "false ⇒ as páginas desse idioma saem com noindex e ficam fora "
                    "do hreflang e do sitemap. Serve para lançar um idioma antes de "
                    "querer tráfego nele."
                ),
            },
        },
    }
    schema.pop("additionalProperties", None)


# ---------------------------------------------------------------------------
# O MENU DO TOPO: a forma do dado, escrita UMA vez
# ---------------------------------------------------------------------------
# Este dicionário é o schema JSON do menu, e ele aparece em três lugares do
# contrato: dentro do Site (para quem DESENHA a página), na resposta do
# getSiteMenu e no corpo do putSiteMenu (para quem CONFIGURA, no Admin). Uma
# constante em vez de três blocos copiados: três cópias divergiriam no primeiro
# campo novo, e o contrato congelado é justamente o lugar onde divergir custa
# um Rito inteiro.
#
# A REGRA de coerência não mora aqui, mora em `apps/sites/menu.py`, que é quem
# recusa endereço `javascript:`, apelido duplicado e página apontando para
# versão que não existe. Aqui é só a FORMA.
ESQUEMA_DO_MENU = {
    "type": "object",
    "description": (
        "O menu do topo deste site. Ausente: o site não tem menu configurado, "
        "e a resposta segue byte a byte igual à de antes desta fase."
    ),
    "properties": {
        "default_version": {
            "type": "string",
            "description": (
                "Apelido da versão usada por toda página sem regra própria. "
                "Vazio: página sem regra não mostra menu nenhum."
            ),
        },
        "versions": {
            "type": "array",
            "description": "As versões do menu deste site (ex.: completo, enxuto).",
            "items": {
                "type": "object",
                "required": ["slug", "name", "items"],
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Apelido único da versão; é o que as páginas apontam.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome que o mantenedor lê na tela de configuração.",
                    },
                    "items": {
                        "type": "array",
                        "description": "As opções do menu, na ordem em que aparecem.",
                        "items": {
                            "type": "object",
                            "required": ["url", "labels"],
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": (
                                        "Caminho deste site começando com uma barra, "
                                        "ou endereço completo de um site de fora."
                                    ),
                                },
                                "labels": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                    "description": (
                                        "Nome do item por idioma (BCP 47 minúsculo). "
                                        "Idioma sem rótulo cai no idioma padrão do site."
                                    ),
                                },
                                "localized": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": (
                                        "true: quem serve a página põe o prefixo do "
                                        "idioma no caminho. Só vale para rota da própria "
                                        "célula: link para outra célula segue cru (R12)."
                                    ),
                                },
                                "audience": {
                                    "type": "string",
                                    "enum": [
                                        "everyone",
                                        "logged_out",
                                        "logged_in",
                                        "staff",
                                    ],
                                    "default": "everyone",
                                    "description": (
                                        "Para quem este item aparece. `staff` sai do campo `papel` da "
                                        "sessão (contrato da `identidade`, schema Session), que é de "
                                        "EXIBIÇÃO e não autoriza nada: quem desenha o menu esconde o "
                                        "item, e quem barra a entrada continua sendo a porta "
                                        "fail-closed da célula dona do recurso. Plateia que um "
                                        "consumidor NÃO reconhecer deve ser ESCONDIDA, nunca mostrada "
                                        "a todos. Sem isso, um valor novo aqui vazaria um atalho "
                                        "durante a janela em que um consumidor ainda não subiu."
                                    ),
                                },
                                "new_tab": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "Abrir numa aba nova.",
                                },
                            },
                        },
                    },
                },
            },
        },
        "pages": {
            "type": "array",
            "description": (
                "Qual versão cada página usa. Página fora desta lista usa a "
                "default_version."
            ),
            "items": {
                "type": "object",
                "required": ["page", "version"],
                "properties": {
                    "page": {
                        "type": "string",
                        "description": (
                            "Chave da página na forma 'celula/rota', a mesma dupla de "
                            "painel/mapa-do-site.json (ex.: 'funil/' ou 'funil/login')."
                        ),
                    },
                    "version": {
                        "type": "string",
                        "description": (
                            "Apelido da versão. Vazio: esta página NÃO mostra menu."
                        ),
                    },
                },
            },
        },
    },
}


def _inline_menu(schema: dict) -> None:
    """Mesmo motivo do `_inline_site_languages`: o contrato declara o menu como
    objeto inline, e sem isto o pydantic emitiria um objeto nu, sem forma."""
    schema.clear()
    schema.update(ESQUEMA_DO_MENU)


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
    # `default_factory` (e não `default=`) nos dois campos abaixo pelo mesmo
    # motivo de `theme`/`default_offer_slug`: com `default=` o pydantic emitiria
    # uma chave "default" no schema que o contrato congelado não tem, e o
    # contrato-check reprovaria.
    default_language: str = Field(
        default_factory=str,
        description=(
            "Idioma padrão do site, BCP 47 em minúsculas, como aparece na URL "
            "(en, pt-br, es). AUSENTE ⇒ site monolíngue: nenhuma URL ganha "
            "prefixo de idioma e o comportamento herdado é preservado."
        ),
    )
    languages: list = Field(
        default_factory=list,
        json_schema_extra=_inline_site_languages,
        description=(
            "Idiomas que este site serve. Ausente ou vazio ⇒ monolíngue. Quando "
            "presente, DEVE conter default_language. A ordem não é significativa."
        ),
    )
    menu: dict = Field(
        default_factory=dict,
        json_schema_extra=_inline_menu,
        description=(
            "O menu do topo deste site. Ausente: o site não tem menu "
            "configurado, e a resposta segue byte a byte igual à de antes."
        ),
    )


# Envelope, e não o objeto nu: um corpo de topo que É o próprio dado não tem
# onde crescer. No dia em que a tela precisar devolver junto "quando isto
# mudou" ou "quem mudou", o campo entra ao lado de `menu` sem quebrar
# ninguém. A docstring é curta de propósito — o django-ninja a exporta como a
# `description` do componente, e o contrato congelado não é lugar de ensaio.
class SiteMenu(Schema):
    """O menu do topo de um site, no envelope que o contrato declara."""

    menu: dict = Field(
        default_factory=dict,
        json_schema_extra=_inline_menu,
        description="O menu do topo deste site. Objeto vazio = site sem menu.",
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


def _site_por_id(site_id: str) -> SiteModel:
    """O site, ou 404. `ValidationError`/`ValueError` cobrem o id que não tem
    nem forma de UUID: sem elas, um id torto viraria 500 em vez de 404."""
    try:
        return SiteModel.objects.get(id=site_id)
    except (SiteModel.DoesNotExist, ValidationError, ValueError):
        raise HttpError(404, "site inexistente")


@router.get(
    "/sites/by-host/{host}",
    response=Site,
    # Site monolíngue OMITE default_language/languages em vez de mandar ""/[]:
    # o contrato define AUSÊNCIA como o sinal de monolíngue, `null` não é
    # permitido ali (type: string, sem nullable) e a omissão deixa a resposta do
    # site monolíngue BYTE-IDÊNTICA à de antes desta fase — a garantia mais
    # forte possível de que nenhum consumidor atual quebra. `exclude_unset`
    # serializa só as chaves que o handler realmente pôs no dict.
    exclude_unset=True,
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
    payload = {
        "id": str(site.id),
        "host": site.host,
        "name": site.name,
        "active": site.active,
        "theme": site.theme or {},
        "default_offer_slug": site.default_offer_slug or "",
    }
    if site.menu:
        # Omitido quando não há menu, pelo MESMO motivo dos idiomas: a
        # ausência é o sinal de "este site não tem menu", e ela deixa a
        # resposta do site sem menu byte-idêntica à de antes desta fase, que
        # é a garantia mais forte possível de que nenhum consumidor quebra.
        payload["menu"] = site.menu
    if site.languages:
        payload["default_language"] = site.default_language
        payload["languages"] = [
            # `.get` com o default do contrato: linha gravada por um caminho que
            # fure o guarda (bulk_create) ainda sai na forma do contrato.
            {"code": idioma["code"], "indexable": idioma.get("indexable", True)}
            for idioma in site.languages
        ]
    return payload


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
    "/produtos",
    response=list[Product],
    operation_id="listProducts",
    summary="Os produtos ativos, para quem precisa ESCOLHER um",
    openapi_extra={
        "responses": {
            200: {"description": "Os produtos ativos, em ordem de nome"},
        }
    },
)
def list_products(request):
    """Quem chama isto precisa MOSTRAR uma lista para alguém escolher.

    Só os ativos, porque a escolha existe para liberar acesso e ninguém deve
    ser liberado num produto aposentado. Quem já tem uma matrícula apontando
    para um produto aposentado continua vendo o nome dele por `getProduct`.
    """
    return [
        {
            "id": str(produto.id),
            "name": produto.name,
            "price_cents": produto.price_cents,
            "active": produto.active,
        }
        for produto in ProductModel.objects.filter(active=True).order_by("name")
    ]


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


@router.get(
    "/sites/{site_id}/menu",
    response=SiteMenu,
    operation_id="getSiteMenu",
    summary="O menu do topo de um site, para a tela que o configura",
    description=(
        "Serve a configuração inteira do menu. Site sem menu responde 200 com "
        "um objeto vazio, e não 404: para quem vai configurar, 'ainda não tem "
        "menu' é um estado normal, não um erro."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O menu deste site (vazio quando não há)"},
            404: {"description": "Site inexistente"},
        }
    },
)
def get_site_menu(request, site_id: str):
    site = _site_por_id(site_id)
    return {"menu": site.menu or {}}


@router.put(
    "/sites/{site_id}/menu",
    response=SiteMenu,
    operation_id="putSiteMenu",
    summary="Grava o menu do topo de um site, inteiro",
    description=(
        "Substitui a configuração inteira do menu: versões, itens e regras por "
        "página de uma vez. Documento inteiro, e não remendo campo a campo, "
        "porque a coerência é do CONJUNTO: uma versão só pode sumir junto com "
        "as páginas que apontavam para ela. Configuração incoerente responde "
        "422 com o motivo em português, e NADA é gravado."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O menu como ficou gravado, na forma canônica"},
            404: {"description": "Site inexistente"},
            422: {"description": "Configuração incoerente; nada foi gravado"},
        }
    },
)
def put_site_menu(request, site_id: str, payload: SiteMenu):
    site = _site_por_id(site_id)
    try:
        site.menu = normalizar_menu(payload.menu)
    except ValidationError as erro:
        # A mensagem do validador é escrita para o mantenedor ler na tela do
        # Admin, então ela ATRAVESSA a fronteira em vez de virar um 422 mudo.
        raise HttpError(422, "; ".join(erro.messages))
    site.save()
    return {"menu": site.menu}
