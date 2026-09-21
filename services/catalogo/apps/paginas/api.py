# apps/paginas/api.py
# A superfície da estrutura de páginas, espelhando contracts/catalogo.openapi.yaml.
# Quatro rotas: ler o que está no ar, ler e gravar o rascunho, e publicar.
# Os operationId, os schemas e os textos abaixo são os do contrato, palavra por
# palavra: aqui o código é o espelho, e o contrato é a fonte.
import datetime as dt
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from ninja import Field, Path, Router, Schema
from ninja.errors import HttpError

from apps.ofertas.models import Offer
from apps.paginas.models import Page, PageDraft, RascunhoVazio
from apps.paginas.vocabulario import normalizar_secoes
from apps.sites.models import Site

#: O slug da página que vende. É o único que nasce amarrado a uma oferta, porque
#: é o único cujo preço e botão saem do catálogo em vez do texto escrito à mão.
SLUG_DA_OFERTA = "oferta"

# A descrição do mapa de slots é a do contrato, palavra por palavra: ela é a
# única lista do vocabulário que quem consome a API enxerga, e duas cópias
# divergiriam no primeiro slot novo.
DESCRICAO_DOS_SLOTS = """Os textos da seção, um por slot. O mapa é LIVRE aqui e o vocabulário é
FECHADO dentro do `catalogo`, que recusa slot desconhecido na gravação.
Enumerar os slots no contrato faria cada frase nova de copy custar um Rito
de Contrato; não validar em lugar nenhum faria nascer `div_47_text`. Por
isso a validação mora no provedor.

O vocabulário que o `catalogo` valida hoje, na ordem da ferramenta 73:

   1 cubo                 headline, subheadline, cta_texto, cta_destino, imagem
   2 viloes               headline, vilao_1, vilao_2, vilao_3, prova
   3 metodo               headline, texto, imagem, prova
   4 instrumentos         headline, texto, indice_de_estudios, prova
   5 percurso             headline, texto, prova
   6 tempo                headline, texto, prova
   7 para_quem_nao_serve  headline, recusa_1, recusa_2, recusa_3, recusa_4, recusa_5, recusa_6
   8 se_eu_parar          headline, texto
   9 oferta               headline, o_que_recebe, preco_texto, parcelamento, cta_texto
  10 carta                headline, texto, assinatura
  11 perguntas            headline, perguntas

O slot `prova` existe em cinco seções porque a ferramenta 73 pede prova ao
lado de cada afirmação. O PREÇO APARECE UMA VEZ, em `oferta.preco_texto`, e
SEM ANCORAGEM: não há slot de valor riscado, e não haverá. Os padrões que a
ferramenta 74 proíbe nesta página são contagem regressiva, "últimas vagas",
valor riscado, promessa de renda ou de prazo e superlativo. Isto é
documentação do contrato, não validação: quem recusa continua sendo o
provedor, e a sentinela da ferramenta 74 mede a peça.

O nome do slot é o que os eventos `funil.cta-clicado` carregam no campo
`slot`. O texto muda a cada versão; o nome do slot não muda, e é por isso
que ele serve de identificador e a copy não serve."""


router = Router()


class Secao(Schema):
    """Um bloco da página: um nome, um lugar na ordem e os textos que o preenchem."""

    nome: str = Field(
        ...,
        description=(
            "Nome da seção. A ordem canônica da página de vendas é a das onze seções\n"
            "da ferramenta 73 de `documentos/ferramentas-do-projeto-meshcraft.md`:\n"
            "cubo, viloes, metodo, instrumentos, percurso, tempo, para_quem_nao_serve,\n"
            "se_eu_parar, oferta, carta e perguntas. É essa sequência que os eventos\n"
            "`funil.secao-vista` transformam numa escada de retenção."
        ),
    )
    ordem: int = Field(
        ..., ge=0, description="Posição desta seção na página, de cima para baixo."
    )
    slots: dict[str, str] = Field(..., description=DESCRICAO_DOS_SLOTS)


class PaginaPublicada(Schema):
    """Uma versão publicada de uma página, que é o que quem visita vê e o que a
    telemetria do funil mede. Publicada não se edita: cada publicação nasce com
    `version` maior, e a anterior fica de pé porque os eventos já a citaram."""

    id: uuid.UUID
    site_id: uuid.UUID
    slug: str = Field(
        ...,
        description="Apelido da página dentro do site (ex. oferta); único por site",
    )
    version: int = Field(
        ...,
        ge=1,
        description=(
            "Cresce a cada publicação e nunca é reescrita. É o número que os eventos "
            "do funil carregam para amarrar cada fato ao conteúdo exato que esteve "
            "na tela."
        ),
    )
    # `default_factory` e não `default=`: com `default=` o pydantic emitiria uma
    # chave "default" no schema que o contrato não tem (`armadilhas/075`). O
    # contrato não exige este campo, e o handler sempre o preenche.
    offer_slug: str = Field(
        default_factory=str,
        description=(
            "Apelido da oferta que esta página vende, para ligar a visita ao pedido. "
            "Vazio quando a página não vende nada."
        ),
    )
    published_at: dt.datetime
    secoes: list[Secao]


class RascunhoDaPagina(Schema):
    """O que está em edição, que é outra coisa do que está no ar. Só a tela do `admin`
    lê e grava isto; quem visita nunca o alcança."""

    site_id: uuid.UUID
    slug: str
    base_version: int = Field(
        ...,
        ge=0,
        description=(
            "A versão publicada de onde este rascunho saiu. ZERO quando ainda não há "
            "nenhuma publicação, e é assim que a tela sabe que a página nunca esteve "
            "no ar."
        ),
    )
    secoes: list[Secao]
    atualizado_em: dt.datetime


class CorpoDoRascunho(Schema):
    """O que a tela do `admin` manda ao gravar: as seções inteiras, de uma vez.
    Existe como componente nomeado, e não solto dentro da operação, porque é
    assim que o provedor consegue emitir uma referência só em vez de referência
    e objeto ao mesmo tempo."""

    secoes: list[Secao]


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


def _site(site_id: str) -> Site:
    """O site desta rota, ou 404.

    Gravar rascunho pode CRIAR a página, então "não existe" deixou de ser uma
    resposta só: site que não existe continua 404, e página que não existe
    passa a nascer. Quem separa as duas coisas é esta consulta, e é por isso
    que ela vem ANTES de qualquer escrita.

    O `try` cobre o id sem forma de UUID pela mesma razão de `_pagina`.
    """
    try:
        site = Site.objects.filter(id=site_id).first()
    except (ValidationError, ValueError):
        site = None
    if site is None:
        raise HttpError(404, "site inexistente")
    return site


def _oferta_padrao(site: Site) -> Offer:
    """A oferta que a página de venda deste site anuncia, ou 422 que ensina.

    Recusar aqui, antes de qualquer escrita, é o que impede a página de venda
    de nascer sem nada para vender. As duas mensagens dizem o campo exato a
    corrigir, porque quem lê está numa tela de administração, não num log.
    """
    if not site.default_offer_slug:
        raise HttpError(
            422,
            f"o site '{site.host}' não tem default_offer_slug, e é dele que sai a "
            "oferta da página de venda. Preencha o default_offer_slug do site com "
            "o slug de uma oferta existente e grave de novo.",
        )
    oferta = (
        Offer.objects.select_related("product")
        .filter(site=site, slug=site.default_offer_slug)
        .first()
    )
    if oferta is None:
        raise HttpError(
            422,
            f"o site '{site.host}' aponta para a oferta '{site.default_offer_slug}', "
            "que não existe neste site. Crie a oferta, ou corrija o "
            "default_offer_slug do site, e grave de novo.",
        )
    return oferta


def _criar_pagina(site: Site, slug: str) -> Page:
    """Cria a página deste site, com o vínculo que o slug pede, uma vez só.

    **A unicidade é do banco, nunca de uma checagem em Python:** entre um
    `exists()` e um `create()` cabe a requisição inteira da outra thread, e o
    resultado seriam duas páginas para o mesmo site e slug. `get_or_create`
    apanha o `IntegrityError` da restrição e refaz a leitura, então a corrida
    termina com uma página e dois 200.

    A oferta é resolvida ANTES do `atomic`: um 422 no meio da transação não
    deixaria página órfã, mas deixaria a mensagem dependente de rollback para
    ser verdadeira, e o mantenedor merece a recusa antes de qualquer escrita.
    """
    oferta = _oferta_padrao(site) if slug == SLUG_DA_OFERTA else None
    with transaction.atomic():
        pagina, _ = Page.objects.get_or_create(
            site=site, slug=slug, defaults={"offer": oferta}
        )
        PageDraft.objects.get_or_create(page=pagina)
    return pagina


def _corpo_publicada(versao) -> dict:
    return {
        "id": versao.id,
        "site_id": versao.page.site_id,
        "slug": versao.page.slug,
        "version": versao.version,
        "offer_slug": versao.page.offer.slug if versao.page.offer_id else "",
        "published_at": versao.published_at,
        "secoes": versao.secoes,
    }


def _corpo_rascunho(rascunho) -> dict:
    return {
        "site_id": rascunho.page.site_id,
        "slug": rascunho.page.slug,
        "base_version": rascunho.base_version,
        "secoes": rascunho.secoes,
        "atualizado_em": rascunho.atualizado_em,
    }


@router.get(
    "/sites/{site_id}/paginas/{slug}",
    response=PaginaPublicada,
    operation_id="getPage",
    summary="A página publicada de um site, que é o que quem visita vê",
    description=(
        "É esta operação que a célula `funil` lê para renderizar. Devolve a versão\n"
        "PUBLICADA, nunca o rascunho: o que está em edição não chega a quem visita.\n"
        "\n"
        "Página sem nenhuma versão publicada responde 404, e não 200 com seções "
        "vazias.\n"
        'Para quem renderiza, "ainda não existe" precisa levar a outro lugar, nunca '
        "a\numa tela em branco servida como se fosse a oferta."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "A versão publicada corrente desta página"},
            404: {
                "description": (
                    "Site inexistente, ou página sem nenhuma versão publicada"
                )
            },
        }
    },
)
def get_page(
    request,
    site_id: str,
    slug: str = Path(..., description="Apelido da página dentro do site (ex. oferta)"),
):
    pagina = _pagina(site_id, slug, publicada=True)
    versao = pagina.ultima_versao
    if versao is None:
        raise HttpError(404, "esta página ainda não foi publicada")
    return _corpo_publicada(versao)


@router.get(
    "/sites/{site_id}/paginas/{slug}/rascunho",
    response=RascunhoDaPagina,
    operation_id="getPageDraft",
    summary="O rascunho em edição de uma página, para a tela que escreve",
    description=(
        "Serve o que está em edição, que é outra coisa do que está no ar. Página que\n"
        "nunca foi editada responde 404: quem abre a tela precisa saber se começa de\n"
        "uma folha em branco ou de um texto que alguém já deixou pela metade."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O rascunho corrente desta página"},
            404: {"description": "Site inexistente, ou página sem rascunho nenhum"},
        }
    },
)
def get_page_draft(request, site_id: str, slug: str):
    pagina = _pagina(site_id, slug)
    rascunho = PageDraft.objects.filter(page=pagina).first()
    if rascunho is None:
        # 404, e não 200 com a lista vazia: quem abre a tela precisa distinguir
        # "folha em branco" de "alguém deixou um texto pela metade".
        raise HttpError(404, "esta página ainda não tem rascunho")
    return _corpo_rascunho(rascunho)


@router.put(
    "/sites/{site_id}/paginas/{slug}/rascunho",
    response=RascunhoDaPagina,
    operation_id="putPageDraft",
    summary="Grava o rascunho de uma página, inteiro",
    description=(
        "Substitui as seções do rascunho de uma vez, e não remenda slot a slot, "
        "porque a\ncoerência é do CONJUNTO: a ordem das seções e os slots de cada uma "
        "só fazem\nsentido juntos. É por aqui que a tela do `admin` salva o que o "
        "mantenedor\nescreve, e gravar rascunho não publica nada."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O rascunho como ficou gravado, na forma canônica"},
            404: {"description": "Site inexistente"},
            422: {"description": "Rascunho incoerente; nada foi gravado"},
        }
    },
)
def put_page_draft(request, site_id: str, slug: str, payload: CorpoDoRascunho):
    # A ordem destas quatro linhas é a entrega inteira, e nenhuma delas troca de
    # lugar: o site existe, o texto é válido, e SÓ ENTÃO alguma coisa é escrita.
    # Validar depois de criar deixaria `Page` órfã atrás de cada texto torto.
    site = _site(site_id)
    try:
        secoes = normalizar_secoes([secao.model_dump() for secao in payload.secoes])
    except ValidationError as erro:
        # A mensagem do vocabulário é escrita para quem está montando a página
        # ler na tela, então ela atravessa a fronteira em vez de virar um 422 mudo.
        raise HttpError(422, "; ".join(erro.messages))

    pagina = Page.objects.filter(site=site, slug=slug).first()
    if pagina is None:
        pagina = _criar_pagina(site, slug)
    # Página que já existe não tem a oferta trocada: o vínculo é decisão de quem
    # criou a página, e regravar texto não é motivo para mudar o que ela vende.

    versao = pagina.ultima_versao
    rascunho, _ = PageDraft.objects.get_or_create(page=pagina)
    rascunho.secoes = secoes
    rascunho.base_version = versao.version if versao else 0
    rascunho.save()
    return _corpo_rascunho(rascunho)


@router.post(
    "/sites/{site_id}/paginas/{slug}/publicar",
    response=PaginaPublicada,
    operation_id="publishPage",
    summary="Publica o rascunho, criando a versão seguinte da página",
    description=(
        "O rascunho vira uma versão publicada nova. Versão publicada não é editada:\n"
        "`version` cresce e a anterior continua existindo, porque é ela que a "
        "telemetria\ndo funil já mediu. Sem isso, medir a página seria medir alvo "
        "móvel.\n"
        "\n"
        "Rascunho vazio responde 409 e nada é publicado. Publicar página sem nada "
        "seria\npôr uma tela em branco no ar com a aparência de sucesso, e o caminho "
        "certo é\nescrever antes."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "A versão que acabou de ser publicada"},
            404: {"description": "Site inexistente"},
            409: {"description": "Rascunho vazio; nada foi publicado"},
        }
    },
)
def publish_page(request, site_id: str, slug: str):
    pagina = _pagina(site_id, slug)
    try:
        versao = pagina.publicar()
    except RascunhoVazio as erro:
        raise HttpError(409, str(erro))
    return _corpo_publicada(versao)
