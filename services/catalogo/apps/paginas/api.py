# apps/paginas/api.py
# A superfície da estrutura de páginas, espelhando contracts/catalogo.openapi.yaml.
# Quatro rotas da página (ler o que está no ar, ler e gravar o rascunho, e
# publicar) e quatro do experimento que mora nela (criar, listar, ler e mudar
# de estado).
# Os operationId, os schemas e os textos abaixo são os do contrato, palavra por
# palavra: aqui o código é o espelho, e o contrato é a fonte.
import datetime as dt
import uuid
from typing import Literal, Optional

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from ninja import Field, Path, Router, Schema
from ninja.errors import HttpError

from apps.ofertas.models import Offer
from apps.paginas.models import (
    Experimento,
    Page,
    PageDraft,
    RascunhoVazio,
    Variante,
    amostra_por_braco,
)
from apps.paginas.vocabulario import VOCABULARIOS, normalizar_secoes
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


#: A forma da chave curta de uma variante (`a`, `b`, `titulo-curto`). É a que
#: viaja nos eventos do funil, então cabe numa coluna e numa URL sem escape.
PADRAO_DA_VARIANTE = r"^[a-z][a-z0-9-]{0,31}$"

#: O controle. Nasce com o texto publicado do slot, e é o que o funil mostra
#: quando não há experimento no ar.
CONTROLE = "a"

#: Pontos-base: 10000 é o todo, 5000 é metade.
TODO_EM_PONTOS_BASE = 10000


class VarianteDoExperimento(Schema):
    """Um braço do experimento: a chave curta, o peso no sorteio e o texto do slot."""

    variante_id: str = Field(
        ...,
        pattern=PADRAO_DA_VARIANTE,
        description=(
            "Chave curta da variante dentro do experimento. `a` é o controle, o texto "
            "que já estava publicado. É o valor que os eventos do funil carregam."
        ),
    )
    peso: int = Field(
        ...,
        ge=1,
        le=TODO_EM_PONTOS_BASE,
        description=(
            "Parte dos visitantes que cai nesta variante, em pontos-base. As "
            "variantes de um experimento somam 10000 (metade para cada = 5000 e 5000)."
        ),
    )
    valor: str = Field(
        ...,
        description=(
            "O texto do slot nesta variante, congelado quando o experimento sai do "
            "rascunho. Não muda nem se a página for publicada de novo."
        ),
    )


class ExperimentoAtivo(Schema):
    """O experimento que está no ar nesta página, para quem renderiza sortear o braço."""

    id: uuid.UUID
    secao: str = Field(..., description="Seção da página cujo slot está em teste.")
    slot: str = Field(
        ..., description="Slot da seção cujo texto muda de uma variante para outra."
    )
    variantes: list[VarianteDoExperimento] = Field(
        ..., description="As variantes em ordem de `variante_id`, que é a do sorteio."
    )


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
    tipo: Literal["oferta", "flp"] = Field(
        default_factory=lambda: "oferta",
        description="Escolhe o vocabulário de seções da página. Ausente: oferta.",
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
    # chave "default" no schema que o contrato não tem. O
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
    # Ausente, e não nulo, quando não há experimento no ar: é o que mantém a
    # resposta de uma página sem experimento idêntica à de antes (a rota usa
    # `exclude_unset`). Por isso o tipo é o objeto, e não `Optional`.
    experimento_ativo: ExperimentoAtivo = Field(
        default_factory=lambda: None,
        description=(
            "O experimento que está no ar nesta página. Ausente quando não há "
            "nenhum: aí a página se mostra como foi publicada. Só aparece o "
            "experimento no estado `ativo`."
        ),
    )


class RascunhoDaPagina(Schema):
    """O que está em edição, que é outra coisa do que está no ar. Só a tela do `admin`
    lê e grava isto; quem visita nunca o alcança."""

    site_id: uuid.UUID
    slug: str
    tipo: Literal["oferta", "flp"] = Field(
        default_factory=lambda: "oferta",
        description="Escolhe o vocabulário de seções da página. Ausente: oferta.",
    )
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

    tipo: Literal["oferta", "flp"] = Field(
        default_factory=lambda: "oferta",
        description="Escolhe o vocabulário de seções da página. Ausente: oferta.",
    )
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


def _criar_pagina(site: Site, slug: str, tipo: str) -> Page:
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
            site=site, slug=slug, defaults={"offer": oferta, "tipo": tipo}
        )
        PageDraft.objects.get_or_create(page=pagina)
    return pagina


def _corpo_publicada(versao) -> dict:
    return {
        "id": versao.id,
        "site_id": versao.page.site_id,
        "slug": versao.page.slug,
        "tipo": versao.page.tipo,
        "version": versao.version,
        "offer_slug": versao.page.offer.slug if versao.page.offer_id else "",
        "published_at": versao.published_at,
        "secoes": versao.secoes,
    }


def _corpo_rascunho(rascunho) -> dict:
    return {
        "site_id": rascunho.page.site_id,
        "slug": rascunho.page.slug,
        "tipo": rascunho.page.tipo,
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
    # Sem experimento no ar, a chave `experimento_ativo` não sai, e a resposta
    # continua a mesma de antes do experimento existir.
    exclude_unset=True,
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
    corpo = _corpo_publicada(versao)
    ativo = (
        Experimento.objects.filter(page=pagina, estado=Experimento.ATIVO)
        .prefetch_related("variantes")
        .first()
    )
    if ativo is not None:
        corpo["experimento_ativo"] = {
            "id": ativo.id,
            "secao": ativo.secao,
            "slot": ativo.slot,
            "variantes": _corpo_variantes(ativo),
        }
    return corpo


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
        secoes = normalizar_secoes(
            [secao.model_dump() for secao in payload.secoes], payload.tipo
        )
    except ValidationError as erro:
        # A mensagem do vocabulário é escrita para quem está montando a página
        # ler na tela, então ela atravessa a fronteira em vez de virar um 422 mudo.
        raise HttpError(422, "; ".join(erro.messages))

    if slug == SLUG_DA_OFERTA and payload.tipo != "oferta":
        raise HttpError(
            422, "a página 'oferta' deve ter tipo 'oferta'; use outro slug para a FLP"
        )

    pagina = Page.objects.filter(site=site, slug=slug).first()
    if pagina is None:
        pagina = _criar_pagina(site, slug, payload.tipo)
    if pagina.tipo != payload.tipo:
        raise HttpError(
            422,
            f"a página '{slug}' tem tipo '{pagina.tipo}'; envie esse tipo no rascunho ou use outro slug",
        )
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


class NovaVariante(Schema):
    """Uma variante como a tela do `admin` a manda ao criar o experimento."""

    variante_id: str = Field(
        ...,
        pattern=PADRAO_DA_VARIANTE,
        description="Chave curta da variante. O controle `a` é obrigatório.",
    )
    peso: int = Field(
        ...,
        ge=1,
        le=TODO_EM_PONTOS_BASE,
        description="Pontos-base; as variantes do experimento somam 10000.",
    )
    valor: str = Field(
        default_factory=str,
        description=(
            "O texto do slot nesta variante. No controle `a` pode ficar vazio: ele "
            "nasce com o texto publicado do slot, e um texto diferente é recusado."
        ),
    )


class NovoExperimento(Schema):
    """O que a tela do `admin` manda para criar um experimento, que nasce em rascunho.

    O horizonte vem decidido de antemão: `taxa_base`, `mde` e `dias_planejados`
    entram aqui, e a amostra por braço é calculada pelo `catalogo`."""

    secao: str = Field(..., description="Seção da página, do vocabulário do tipo dela.")
    slot: str = Field(..., description="Slot da seção cujo texto vai ser testado.")
    hipotese: str = Field(
        ..., min_length=1, description="O que se espera que aconteça, e por quê."
    )
    metrica_principal: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "O passo do funil que decide o experimento, com o nome que a leitura do "
            "funil usa (ex. cta_checkout: entrada no checkout por visitante)."
        ),
    )
    taxa_base: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Proporção atual da métrica principal, entre 0 e 1 (0,10 = 10%).",
    )
    mde: float = Field(
        ...,
        gt=0,
        lt=1,
        description=(
            "Menor efeito que vale detectar, ABSOLUTO, em pontos de proporção "
            "(0,02 = de 10% para 12%)."
        ),
    )
    dias_planejados: int = Field(
        ..., ge=1, description="Dias corridos de coleta, contados a partir do início."
    )
    variantes: list[NovaVariante] = Field(
        ..., min_length=2, description="Pelo menos duas, e o controle `a` entre elas."
    )


class ExperimentoDaPagina(Schema):
    """Um experimento de uma página, do jeito que a tela do `admin` o lê."""

    id: uuid.UUID
    site_id: uuid.UUID
    slug: str = Field(..., description="Apelido da página onde o experimento mora.")
    secao: str
    slot: str
    hipotese: str
    metrica_principal: str
    taxa_base: float
    mde: float
    n_por_braco_planejado: int = Field(
        ...,
        ge=1,
        description=(
            "Expostos por braço calculados na criação: duas proporções, alfa 0,05 "
            "bicaudal, poder 0,8. Braço abaixo disto no horizonte é resultado "
            "inconclusivo."
        ),
    )
    dias_planejados: int
    estado: Literal["rascunho", "ativo", "encerrado"] = Field(
        ...,
        description=(
            "rascunho vai para ativo ou encerrado; ativo vai para encerrado; "
            "encerrado não sai mais. Não há pausa: retomar é criar outro."
        ),
    )
    decisao: Optional[Literal["promover", "reverter", "encerrar"]] = Field(
        ..., description="Guardada no encerramento. Nula antes dele."
    )
    vencedora: Optional[str] = Field(
        ..., description="`variante_id` da vencedora, quando o encerramento aponta uma."
    )
    criado_em: dt.datetime
    iniciado_em: Optional[dt.datetime] = Field(
        ..., description="Quando entrou no ar. Nulo enquanto é rascunho."
    )
    fim_planejado: Optional[dt.datetime] = Field(
        ...,
        description=(
            "iniciado_em mais dias_planejados: o fim da janela em que o resultado "
            "se calcula. Nulo enquanto é rascunho."
        ),
    )
    encerrado_em: Optional[dt.datetime]
    variantes: list[VarianteDoExperimento]


class MudancaDeEstado(Schema):
    """O estado para onde o experimento vai, e no encerramento a decisão tomada."""

    estado: Literal["ativo", "encerrado"]
    decisao: Optional[Literal["promover", "reverter", "encerrar"]] = Field(
        default=None,
        description="Obrigatória ao encerrar, e só ao encerrar.",
    )
    vencedora: Optional[str] = Field(
        default=None,
        description=(
            "`variante_id` da vencedora. Obrigatória para promover; só vale ao encerrar."
        ),
    )


def _corpo_variantes(experimento) -> list[dict]:
    return [
        {"variante_id": v.variante_id, "peso": v.peso, "valor": v.valor}
        for v in experimento.variantes.all()
    ]


def _corpo_experimento(experimento) -> dict:
    fim = None
    if experimento.iniciado_em is not None:
        fim = experimento.iniciado_em + dt.timedelta(days=experimento.dias_planejados)
    return {
        "id": experimento.id,
        "site_id": experimento.page.site_id,
        "slug": experimento.page.slug,
        "secao": experimento.secao,
        "slot": experimento.slot,
        "hipotese": experimento.hipotese,
        "metrica_principal": experimento.metrica_principal,
        "taxa_base": experimento.taxa_base,
        "mde": experimento.mde,
        "n_por_braco_planejado": experimento.n_por_braco_planejado,
        "dias_planejados": experimento.dias_planejados,
        "estado": experimento.estado,
        "decisao": experimento.decisao or None,
        "vencedora": experimento.vencedora or None,
        "criado_em": experimento.criado_em,
        "iniciado_em": experimento.iniciado_em,
        "fim_planejado": fim,
        "encerrado_em": experimento.encerrado_em,
        "variantes": _corpo_variantes(experimento),
    }


def _texto_publicado(pagina: Page, secao: str, slot: str) -> str:
    """O texto que está no ar neste slot, ou 409 que diz o que fazer.

    O controle de um experimento é o texto publicado: sem página publicada, ou
    com o slot vazio, não há controle, e testar contra o nada mediria outra
    coisa.
    """
    versao = pagina.ultima_versao
    if versao is None:
        raise HttpError(
            409,
            f"a página '{pagina.slug}' ainda não foi publicada, e o controle de um "
            "experimento é o texto publicado. Publique a página e crie o "
            "experimento de novo.",
        )
    for item in versao.secoes:
        if item["nome"] == secao and item["slots"].get(slot):
            return item["slots"][slot]
    raise HttpError(
        409,
        f"o slot {secao}.{slot} está vazio na versão {versao.version} publicada, "
        "e o controle de um experimento é o texto publicado. Escreva esse slot, "
        "publique a página e tente de novo.",
    )


def _experimento(pagina: Page, experimento_id: str) -> Experimento:
    """O experimento desta página, ou 404. Id sem forma de UUID também é 404."""
    try:
        experimento = (
            Experimento.objects.select_related("page")
            .filter(page=pagina, id=experimento_id)
            .first()
        )
    except (ValidationError, ValueError):
        experimento = None
    if experimento is None:
        raise HttpError(404, "experimento inexistente nesta página")
    return experimento


@router.post(
    "/sites/{site_id}/paginas/{slug}/experimentos",
    # Um só status declarado, com Schema nomeado: sai como referência no
    # contrato, sem o Schema dinâmico que `armadilhas/021` teme de 200 e 201.
    response={201: ExperimentoDaPagina},
    operation_id="createExperiment",
    summary="Cria um experimento num slot da página, em rascunho",
    description=(
        "O experimento nasce em rascunho, com o controle `a` carregando o texto "
        "publicado do slot e a amostra por braço já calculada. Nada vai ao ar "
        "até a mudança de estado para ativo."
    ),
    openapi_extra={
        "responses": {
            201: {
                "description": "O experimento criado, em rascunho",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ExperimentoDaPagina"}
                    }
                },
            },
            404: {"description": "Site ou página inexistente"},
            409: {"description": "Página sem versão publicada, ou slot vazio nela"},
            422: {
                "description": (
                    "Seção ou slot fora do vocabulário, variantes incoerentes ou "
                    "horizonte impossível; nada foi gravado"
                )
            },
        }
    },
)
def create_experiment(request, site_id: str, slug: str, payload: NovoExperimento):
    pagina = _pagina(site_id, slug)
    vocabulario = VOCABULARIOS[pagina.tipo]
    if payload.secao not in vocabulario:
        raise HttpError(
            422,
            f"seção desconhecida: {payload.secao!r}. As seções válidas são: "
            f"{', '.join(vocabulario)}.",
        )
    if payload.slot not in vocabulario[payload.secao]:
        raise HttpError(
            422,
            f"slot desconhecido na seção {payload.secao!r}: {payload.slot!r}. Os "
            f"slots de {payload.secao!r} são: {', '.join(vocabulario[payload.secao])}.",
        )
    if payload.taxa_base + payload.mde >= 1:
        raise HttpError(
            422,
            "taxa_base mais mde passa de 100%, e nenhuma proporção chega lá. "
            "Diminua o mde.",
        )

    chaves = [v.variante_id for v in payload.variantes]
    if len(set(chaves)) != len(chaves):
        raise HttpError(422, "cada variante_id aparece uma vez só no experimento.")
    if CONTROLE not in chaves:
        raise HttpError(
            422, "falta a variante 'a', o controle com o texto publicado. Inclua-a."
        )
    soma = sum(v.peso for v in payload.variantes)
    if soma != TODO_EM_PONTOS_BASE:
        raise HttpError(
            422,
            f"os pesos somam {soma}, e precisam somar 10000 pontos-base "
            "(metade para cada = 5000 e 5000).",
        )

    controle = _texto_publicado(pagina, payload.secao, payload.slot)
    valores = {}
    for variante in payload.variantes:
        valor = variante.valor.strip()
        if variante.variante_id == CONTROLE:
            if valor and valor != controle:
                raise HttpError(
                    422,
                    "a variante 'a' é o texto publicado do slot e não recebe outro. "
                    "Deixe o valor dela vazio.",
                )
            valor = controle
        elif not valor:
            raise HttpError(
                422,
                f"a variante {variante.variante_id!r} está sem texto. Escreva o "
                "texto que ela mostra no slot.",
            )
        valores[variante.variante_id] = valor

    with transaction.atomic():
        experimento = Experimento.objects.create(
            page=pagina,
            secao=payload.secao,
            slot=payload.slot,
            hipotese=payload.hipotese.strip(),
            metrica_principal=payload.metrica_principal.strip(),
            taxa_base=payload.taxa_base,
            mde=payload.mde,
            n_por_braco_planejado=amostra_por_braco(payload.taxa_base, payload.mde),
            dias_planejados=payload.dias_planejados,
        )
        for variante in payload.variantes:
            Variante.objects.create(
                experimento=experimento,
                variante_id=variante.variante_id,
                peso=variante.peso,
                valor=valores[variante.variante_id],
            )
    return 201, _corpo_experimento(experimento)


@router.get(
    "/sites/{site_id}/paginas/{slug}/experimentos",
    response=list[ExperimentoDaPagina],
    operation_id="listExperiments",
    summary="Os experimentos de uma página, do mais novo para o mais antigo",
    openapi_extra={
        "responses": {
            200: {"description": "Os experimentos da página, em qualquer estado"},
            404: {"description": "Site ou página inexistente"},
        }
    },
)
def list_experiments(request, site_id: str, slug: str):
    pagina = _pagina(site_id, slug)
    return [
        _corpo_experimento(experimento)
        for experimento in pagina.experimentos.select_related("page").prefetch_related(
            "variantes"
        )
    ]


@router.get(
    "/sites/{site_id}/paginas/{slug}/experimentos/{experimento_id}",
    response=ExperimentoDaPagina,
    operation_id="getExperiment",
    summary="Um experimento de uma página",
    openapi_extra={
        "responses": {
            200: {"description": "O experimento, com as variantes"},
            404: {"description": "Site, página ou experimento inexistente"},
        }
    },
)
def get_experiment(request, site_id: str, slug: str, experimento_id: str):
    return _corpo_experimento(_experimento(_pagina(site_id, slug), experimento_id))


@router.post(
    "/sites/{site_id}/paginas/{slug}/experimentos/{experimento_id}/estado",
    response=ExperimentoDaPagina,
    operation_id="changeExperimentState",
    summary="Põe o experimento no ar ou o encerra",
    description=(
        "rascunho vai para ativo ou encerrado; ativo vai para encerrado. Pedir o "
        "estado em que o experimento já está responde 200 sem mudar nada. Ao "
        "entrar no ar, o controle `a` é conferido com o texto publicado de agora, "
        "e as variantes congelam. Ao encerrar, a decisão é obrigatória."
    ),
    openapi_extra={
        "responses": {
            200: {"description": "O experimento no estado pedido"},
            404: {"description": "Site, página ou experimento inexistente"},
            409: {
                "description": (
                    "Transição inválida, outro experimento já ativo nesta página, "
                    "ou encerramento repetido com outra decisão; nada mudou"
                )
            },
            422: {"description": "Decisão ausente, ou vencedora que não é variante"},
        }
    },
)
def change_experiment_state(
    request, site_id: str, slug: str, experimento_id: str, payload: MudancaDeEstado
):
    pagina = _pagina(site_id, slug)
    _experimento(pagina, experimento_id)
    encerrar = payload.estado == Experimento.ENCERRADO
    if not encerrar and (payload.decisao or payload.vencedora):
        raise HttpError(422, "decisão e vencedora só se mandam ao encerrar.")
    if encerrar and not payload.decisao:
        raise HttpError(
            422, "ao encerrar, diga a decisão: promover, reverter ou encerrar."
        )
    if payload.decisao == "promover" and not payload.vencedora:
        raise HttpError(422, "para promover, diga qual variante venceu.")

    with transaction.atomic():
        experimento = (
            Experimento.objects.select_for_update()
            .select_related("page")
            .get(pk=experimento_id)
        )
        if payload.estado == experimento.estado:
            if encerrar and (
                payload.decisao != experimento.decisao
                or (payload.vencedora or "") != experimento.vencedora
            ):
                raise HttpError(
                    409,
                    "este experimento já foi encerrado com a decisão "
                    f"'{experimento.decisao}', e ela não muda. Nada foi alterado.",
                )
            return _corpo_experimento(experimento)
        if payload.estado not in Experimento.TRANSICOES[experimento.estado]:
            raise HttpError(
                409,
                f"um experimento {experimento.estado} não vai para {payload.estado}. "
                "Para testar de novo, crie um experimento novo.",
            )
        if encerrar:
            chaves = set(experimento.variantes.values_list("variante_id", flat=True))
            if payload.vencedora and payload.vencedora not in chaves:
                raise HttpError(
                    422,
                    f"a vencedora {payload.vencedora!r} não é variante deste "
                    f"experimento. As variantes são: {', '.join(sorted(chaves))}.",
                )
            experimento.estado = Experimento.ENCERRADO
            experimento.decisao = payload.decisao
            experimento.vencedora = payload.vencedora or ""
            experimento.encerrado_em = timezone.now()
            experimento.save()
            return _corpo_experimento(experimento)

        # Entrar no ar: o controle é o texto publicado AGORA, e não o do dia da
        # criação, porque a página pode ter sido publicada de novo no meio. A
        # atualização vem antes da troca de estado: depois dela, a variante já
        # está congelada.
        controle = _texto_publicado(
            experimento.page, experimento.secao, experimento.slot
        )
        experimento.variantes.filter(variante_id=CONTROLE).update(valor=controle)
        experimento.estado = Experimento.ATIVO
        experimento.iniciado_em = timezone.now()
        try:
            with transaction.atomic():
                experimento.save()
        except IntegrityError:
            raise HttpError(
                409,
                "já há um experimento no ar nesta página. Encerre-o antes de pôr "
                "este no ar. Nada foi alterado.",
            )
        return _corpo_experimento(experimento)
