# apps/paginas/api.py
# A superfície da estrutura de páginas, espelhando contracts/catalogo.openapi.yaml.
# Quatro rotas: ler o que está no ar, ler e gravar o rascunho, e publicar.
import datetime as dt

from django.core.exceptions import ValidationError
from ninja import Field, Router, Schema
from ninja.errors import HttpError

from apps.paginas.models import Page, RascunhoVazio
from apps.paginas.vocabulario import normalizar_secoes

router = Router()


class Secao(Schema):
    """Uma seção da página, com os slots que ela tem preenchidos."""

    nome: str = Field(
        ...,
        description=(
            "hero, problema, mecanismo, prova, oferta, garantia ou faq. Nome fora "
            "da lista é recusado com 422."
        ),
    )
    ordem: int = Field(
        ...,
        description=(
            "O lugar desta seção na ordem canônica da página, de hero a faq. É "
            "derivado do nome, e por isso o valor enviado numa gravação é "
            "ignorado: a ordem é propriedade da seção, e aceitar um número do "
            "chamador criaria duas fontes para o mesmo fato."
        ),
    )
    slots: dict[str, str] = Field(
        ...,
        description=(
            "Os textos desta seção, por nome de slot. Slot vazio não aparece "
            "aqui, e seção sem nenhum slot preenchido não aparece na página."
        ),
    )


class PaginaPublicada(Schema):
    """A versão da página que está no ar."""

    id: str
    site_id: str
    slug: str
    version: int = Field(
        ...,
        description="Páginas publicadas não são editadas: mudanças criam nova versão",
    )
    offer_slug: str = Field(
        ...,
        description="A oferta que esta página vende. Vazio quando ela não vende nenhuma.",
    )
    published_at: dt.datetime
    secoes: list[Secao]


class RascunhoDaPagina(Schema):
    """O que está sendo escrito nesta página, ainda fora do ar."""

    site_id: str
    slug: str
    base_version: int = Field(
        ...,
        description=(
            "A versão publicada de que este rascunho partiu. Zero enquanto a "
            "página nunca publicou."
        ),
    )
    secoes: list[Secao]
    atualizado_em: dt.datetime


class CorpoDoRascunho(Schema):
    """O que se grava num rascunho: as seções, inteiras."""

    secoes: list[Secao] = Field(
        ...,
        description=(
            "Substitui as seções inteiras, e não remendo campo a campo, porque a "
            "coerência é do conjunto: a ordem e a presença de cada seção só se "
            "decidem olhando a página toda."
        ),
    )


def _pagina(site_id: str, slug: str, publicada: bool = False) -> Page:
    """A página deste site, ou 404.

    `ValidationError`/`ValueError` cobrem o id que não tem nem forma de UUID:
    sem elas, um id torto viraria 500 em vez de 404. [INV-P11] o filtro por
    `site_id` é o que impede a página de um site de vazar para outro: existir
    noutro site não é existir aqui.
    """
    try:
        consulta = Page.objects.filter(site_id=site_id, slug=slug)
        if publicada:
            consulta = consulta.filter(site__active=True)
        pagina = consulta.first()
    except (ValidationError, ValueError):
        # O id torto estoura já na MONTAGEM da consulta, não na execução: o
        # `filter()` precisa ficar dentro do try, e não só o `first()`.
        pagina = None
    if pagina is None:
        raise HttpError(404, "página inexistente neste site")
    return pagina


def _corpo_publicada(versao) -> dict:
    return {
        "id": str(versao.id),
        "site_id": str(versao.page.site_id),
        "slug": versao.page.slug,
        "version": versao.version,
        "offer_slug": versao.page.offer.slug if versao.page.offer_id else "",
        "published_at": versao.published_at,
        "secoes": versao.secoes,
    }


def _corpo_rascunho(rascunho) -> dict:
    return {
        "site_id": str(rascunho.page.site_id),
        "slug": rascunho.page.slug,
        "base_version": rascunho.base_version,
        "secoes": rascunho.secoes,
        "atualizado_em": rascunho.atualizado_em,
    }


@router.get(
    "/sites/{site_id}/paginas/{slug}",
    response=PaginaPublicada,
    operation_id="getPaginaPublicada",
    summary="A página publicada DE UM SITE, na versão que está no ar",
    description=(
        "Serve a última versão publicada. Slugs são únicas por site; a mesma "
        "slug pode existir com conteúdo distinto em sites distintos. Site "
        "desativado não serve página, pela mesma regra da oferta."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "A versão publicada corrente desta página"},
            404: {
                "description": (
                    "Página inexistente NESTE site, ou que nunca publicou "
                    "(mesmo que exista em outro, INV-P11)"
                )
            },
        }
    },
)
def get_pagina_publicada(request, site_id: str, slug: str):
    pagina = _pagina(site_id, slug, publicada=True)
    versao = pagina.ultima_versao
    if versao is None:
        raise HttpError(404, "esta página ainda não foi publicada")
    return _corpo_publicada(versao)


@router.get(
    "/sites/{site_id}/paginas/{slug}/rascunho",
    response=RascunhoDaPagina,
    operation_id="getRascunhoDaPagina",
    summary="O rascunho de uma página, para a tela que a escreve",
    description=(
        "Toda página tem um rascunho desde que nasce. A página em que ainda "
        "não se escreveu nada responde 200 com a lista de seções vazia, e não "
        "404: para quem vai escrever, isso é estado normal, não erro."
    ),
    openapi_extra={
        "responses": {
            200: {
                "description": "O rascunho desta página (vazio enquanto nada foi escrito)"
            },
            404: {"description": "Página inexistente neste site"},
        }
    },
)
def get_rascunho(request, site_id: str, slug: str):
    return _corpo_rascunho(_pagina(site_id, slug).rascunho)


@router.put(
    "/sites/{site_id}/paginas/{slug}/rascunho",
    response=RascunhoDaPagina,
    operation_id="putRascunhoDaPagina",
    summary="Grava o rascunho de uma página, inteiro",
    description=(
        "Substitui as seções inteiras. Seção fora do vocabulário, ou slot fora "
        "da seção, respondem 422 dizendo o nome errado e a lista válida, e NADA "
        "é gravado. Slot vazio não é erro: ele simplesmente não aparece na "
        "página, e seção sem nenhum slot preenchido também não."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O rascunho como ficou gravado, na forma canônica"},
            404: {"description": "Página inexistente neste site"},
            422: {"description": "Seção ou slot fora do vocabulário; nada foi gravado"},
        }
    },
)
def put_rascunho(request, site_id: str, slug: str, payload: CorpoDoRascunho):
    pagina = _pagina(site_id, slug)
    try:
        secoes = normalizar_secoes([secao.model_dump() for secao in payload.secoes])
    except ValidationError as erro:
        # A mensagem do vocabulário é escrita para quem está montando a página
        # ler na tela, então ela atravessa a fronteira em vez de virar um 422 mudo.
        raise HttpError(422, "; ".join(erro.messages))

    versao = pagina.ultima_versao
    rascunho = pagina.rascunho
    rascunho.secoes = secoes
    rascunho.base_version = versao.version if versao else 0
    rascunho.save()
    return _corpo_rascunho(rascunho)


@router.post(
    "/sites/{site_id}/paginas/{slug}/publicar",
    response=PaginaPublicada,
    operation_id="publicarPagina",
    summary="Congela o rascunho numa versão nova e põe no ar",
    description=(
        "A versão nova nasce com o número seguinte, e as anteriores continuam "
        "intactas: publicar nunca reescreve o passado. Rascunho vazio responde "
        "409, porque publicar página em branco poria no ar um endereço público "
        "sem nada dentro."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "A versão recém-publicada"},
            404: {"description": "Página inexistente neste site"},
            409: {"description": "Rascunho vazio; nada foi publicado"},
        }
    },
)
def publicar_pagina(request, site_id: str, slug: str):
    pagina = _pagina(site_id, slug)
    try:
        versao = pagina.publicar()
    except RascunhoVazio as erro:
        raise HttpError(409, str(erro))
    return _corpo_publicada(versao)
