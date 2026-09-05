"""A porta de MÁQUINA da sala de aula: as sete operações do editor.

POR QUE ELA EXISTE
------------------
O conteúdo do curso mora no banco desta célula, e só nele (a lei
anti-duplicação). O editor do Admin (degrau 1.5) lê e grava por aqui, nunca no
banco e nunca guardando cópia. Este arquivo é o degrau 1.3 da escada
(`PLANO-CELULA-CURSOS.md` §10, TAR-150): `listLessons`, `getLesson`,
`putLesson`, `putInstrument` e `publishLesson`; o degrau 1.3b (TAR-161)
acrescentou `listInstruments` e `getInstrument`, porque o editor gravava a
escala de um instrumento sem poder lê-la de volta. O contrato congela no degrau
1.4 A PARTIR do que `manage.py export_openapi` imprime daqui, nunca de cabeça
(`armadilhas/243`).

O QUE FICA DE FORA, DE PROPÓSITO
--------------------------------
Não há sessão nem cookie: é máquina para máquina, e o Bearer do par
(`apps/core/auth.py`) é o único cadeado. Não há `checkLesson` (degrau 3.1),
`getReviewQueue` (2.1) nem `getStudentProgress` (1.8). E `publishLesson` NÃO
valida remissão: o invariante C1 ("remissão quebrada não publica") é do 3.1,
e o ponto onde ele encaixa está marcado lá embaixo.

O SOMBREAMENTO QUE ESTA PORTA NÃO PODE COMER (`armadilhas/020`)
-----------------------------------------------------------------
Um `ninja.Schema` com o MESMO nome de um model Django, no mesmo arquivo,
sombreia o model em silêncio: o import não falha, o lint não vê, e o primeiro
`.objects` estoura `AttributeError` vindo de dentro do pydantic. Por isso todo
model entra aqui com alias `...Model`, e todo schema leva o sufixo `Schema`.

O VOCABULÁRIO É O DO MODELO, E NÃO UMA SEGUNDA LISTA
----------------------------------------------------
`tipo` de peça e `tipo` de pausa são tipados com o `TextChoices` do próprio
modelo: o pydantic valida a pertinência, o OpenAPI exportado carrega o `enum`
com as 18 e as 3 palavras, e nenhum nome é escrito duas vezes.

O CORPO QUE A PORTA NÃO CONHECE É RECUSADO (`extra="forbid"`)
-------------------------------------------------------------
Os dois corpos de `PUT` recusam chave desconhecida com 422. É o que faz
"`nome_canonico` e `cartao` não mudam pela porta" ser mecânico, e é o que
impede um editor de mandar `estado: "publicada"` num `PUT` e acreditar que
publicou: o que esta porta ignora em silêncio, ela nunca ignora.

Guardas: `tests/test_porta_de_maquina.py` e `tests/test_porta_exige_bearer.py`.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal

from django.db import transaction
from django.utils import timezone
from ninja import Field, Router, Schema
from ninja.errors import HttpError, ValidationError
from pydantic import ConfigDict, model_validator

from apps.cursos.models import Aula as AulaModel
from apps.cursos.models import Instrumento as InstrumentoModel
from apps.cursos.models import Pausa as PausaModel
from apps.cursos.models import Peca as PecaModel
from apps.cursos.models import TipoDePeca

router = Router()

# O nome do componente no contrato é o nome da classe, e o enum de pausa mora
# aninhado no modelo como `Pausa.Tipo`: sairia como "Tipo", ambíguo ao lado de
# `TipoDePeca`. Este é DERIVADO do modelo, membro a membro; não é segunda lista.
TipoDePausa = enum.Enum(
    "TipoDePausa", {membro.name: membro.value for membro in PausaModel.Tipo}, type=str
)

# Os limites das colunas do modelo, repetidos aqui para que o pydantic recuse
# com 422 o que o banco recusaria com erro 500: um texto de 201 letras num
# `CharField(max_length=200)` é entrada inválida, não incidente.
CURTO = 120
MEDIO = 200
URL = 500
MAIOR_INTEIRO_PEQUENO = 32_767
MAIOR_INTEIRO = 2_147_483_647


# ---------------------------------------------------------------------------
# OS SCHEMAS DE RESPOSTA
# ---------------------------------------------------------------------------


class BlocoSchema(Schema):
    letra: str
    ordem: int
    parte: int


class AulaDaListaSchema(Schema):
    """A linha da listagem: o que o editor mostra no índice, sem texto de peça."""

    numero: str
    ordem: int
    titulo_exibido: str
    bloco: BlocoSchema
    estado: str
    versao: int
    publicada_em: datetime | None
    e_boss: bool
    banca_nivel: int | None


class PecaSchema(Schema):
    tipo: TipoDePeca
    texto: str


class PausaSchema(Schema):
    ordem: int = Field(ge=0, le=MAIOR_INTEIRO_PEQUENO)
    segundo: int = Field(ge=0, le=MAIOR_INTEIRO)
    tipo: TipoDePausa
    pede: str
    campos: list[str]


class ItemDoQuizSchema(Schema):
    pergunta: str = Field(min_length=1)
    resposta_modelo: str = Field(min_length=1)


class AulaSchema(AulaDaListaSchema):
    """A aula inteira: a linha da listagem mais o que se edita."""

    pedido: str
    cliente: str
    instrumento: str | None
    minimo: str
    aceito_quando: list[str]
    quiz: list[ItemDoQuizSchema]
    video_url: str
    pecas: list[PecaSchema]
    pausas: list[PausaSchema]


class InstrumentoSchema(Schema):
    slug: str
    nome_canonico: str
    cartao: int
    escala: dict[str, Any]
    minimo_exercicio: str
    minimo_contrato: str
    secao_do_padrao: str
    descritores: dict[str, Any]
    versao: int


# ---------------------------------------------------------------------------
# OS CORPOS DE `PUT`
# ---------------------------------------------------------------------------


class AulaParaGravarSchema(Schema):
    """O corpo de `putLesson`: só o que se edita. Número, ordem, título, bloco,
    estado, versão e data de publicação não entram, e mandá-los é 422."""

    model_config = ConfigDict(extra="forbid")

    pedido: str
    cliente: str = Field(max_length=CURTO)
    instrumento: str | None
    minimo: str = Field(max_length=MEDIO)
    aceito_quando: list[str]
    quiz: list[ItemDoQuizSchema]
    video_url: str = Field(max_length=URL)
    e_boss: bool
    banca_nivel: Literal[1, 2, 3] | None
    pecas: list[PecaSchema]
    pausas: list[PausaSchema]

    @model_validator(mode="after")
    def sem_repeticao(self):
        """Peça repetida e pausa com a mesma ordem são as duas unicidades do
        banco (`uma_peca_por_tipo_por_aula`, `uma_ordem_por_pausa_por_aula`);
        recusadas aqui viram 422 com o nome do repetido, não IntegrityError."""
        tipos = [peca.tipo for peca in self.pecas]
        repetidos = sorted({tipo for tipo in tipos if tipos.count(tipo) > 1})
        if repetidos:
            raise ValueError(f"peça repetida: {', '.join(repetidos)}")
        ordens = [pausa.ordem for pausa in self.pausas]
        repetidas = sorted({ordem for ordem in ordens if ordens.count(ordem) > 1})
        if repetidas:
            raise ValueError(
                f"pausa com ordem repetida: {', '.join(map(str, repetidas))}"
            )
        return self


class InstrumentoParaGravarSchema(Schema):
    """O corpo de `putInstrument`: a escala, os mínimos, a seção e os
    descritores. `nome_canonico` e `cartao` são da lei, não do editor: vêm no
    corpo, é 422."""

    model_config = ConfigDict(extra="forbid")

    escala: dict[str, Any]
    minimo_exercicio: str = Field(max_length=MEDIO)
    minimo_contrato: str = Field(max_length=MEDIO)
    secao_do_padrao: str = Field(max_length=CURTO)
    descritores: dict[str, Any]


# ---------------------------------------------------------------------------
# AS CONSULTAS E AS FORMAS DE RESPOSTA
# ---------------------------------------------------------------------------


def _aula(site_id: str, numero: str) -> AulaModel:
    try:
        return AulaModel.objects.select_related("bloco", "instrumento").get(
            curso__site_id=site_id, numero=numero
        )
    except AulaModel.DoesNotExist:
        raise HttpError(404, f"a aula {numero} não existe no site {site_id}")


def _instrumento_do_slug(slug: str | None) -> InstrumentoModel | None:
    if slug is None:
        return None
    try:
        return InstrumentoModel.objects.get(slug=slug)
    except InstrumentoModel.DoesNotExist:
        conhecidos = ", ".join(
            InstrumentoModel.objects.order_by("cartao").values_list("slug", flat=True)
        )
        raise ValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ["body", "payload", "instrumento"],
                    "msg": f"o instrumento '{slug}' não existe; os slugs são: {conhecidos}",
                }
            ]
        )


def _linha(aula: AulaModel) -> dict[str, Any]:
    return {
        "numero": aula.numero,
        "ordem": aula.ordem,
        "titulo_exibido": aula.titulo_exibido,
        "bloco": {
            "letra": aula.bloco.letra,
            "ordem": aula.bloco.ordem,
            "parte": aula.bloco.parte,
        },
        "estado": aula.estado,
        "versao": aula.versao,
        "publicada_em": aula.publicada_em,
        "e_boss": aula.e_boss,
        "banca_nivel": aula.banca_nivel,
    }


def _aula_inteira(aula: AulaModel) -> dict[str, Any]:
    textos = dict(aula.pecas.values_list("tipo", "texto"))
    return {
        **_linha(aula),
        "pedido": aula.pedido,
        "cliente": aula.cliente,
        "instrumento": aula.instrumento.slug if aula.instrumento_id else None,
        "minimo": aula.minimo,
        "aceito_quando": aula.aceito_quando,
        "quiz": aula.quiz,
        "video_url": aula.video_url,
        # As 16 da anatomia na ordem canônica e depois as duas internas, SEMPRE
        # as 18: a peça que ainda não foi escrita sai com texto vazio, e o
        # editor desenha o formulário inteiro desde o primeiro dia.
        "pecas": [
            {"tipo": tipo, "texto": textos.get(tipo, "")}
            for tipo in PecaModel.ORDEM_CANONICA + PecaModel.TIPOS_INTERNOS
        ],
        "pausas": [
            {
                "ordem": pausa.ordem,
                "segundo": pausa.segundo,
                "tipo": pausa.tipo,
                "pede": pausa.pede,
                "campos": pausa.campos,
            }
            for pausa in aula.pausas.order_by("ordem")
        ],
    }


def _instrumento(instrumento: InstrumentoModel) -> dict[str, Any]:
    return {
        "slug": instrumento.slug,
        "nome_canonico": instrumento.nome_canonico,
        "cartao": instrumento.cartao,
        "escala": instrumento.escala,
        "minimo_exercicio": instrumento.minimo_exercicio,
        "minimo_contrato": instrumento.minimo_contrato,
        "secao_do_padrao": instrumento.secao_do_padrao,
        "descritores": instrumento.descritores,
        "versao": instrumento.versao,
    }


# ---------------------------------------------------------------------------
# AS SETE OPERAÇÕES
# ---------------------------------------------------------------------------


@router.get(
    "/aulas",
    response=list[AulaDaListaSchema],
    operation_id="listLessons",
    summary="As aulas do curso de um site, na ordem em que o aluno as encontra",
    description=(
        "A lista que o editor mostra como indice: numero, ordem, titulo\n"
        "exibido, o bloco (letra, ordem, parte), estado, versao, data de\n"
        "publicacao, se e Boss e o nivel de Banca. NENHUM texto de peca sai\n"
        "aqui: e listagem, e o texto vem em `getLesson`.\n"
        "\n"
        "`site_id` e obrigatorio. Site sem curso responde lista vazia, nao\n"
        "erro: nao ter curso ainda e um estado, nao uma falha."
    ),
)
def list_lessons(request, site_id: str):
    aulas = (
        AulaModel.objects.filter(curso__site_id=site_id)
        .select_related("bloco")
        .order_by("ordem")
    )
    return [_linha(aula) for aula in aulas]


@router.get(
    "/aulas/{numero}",
    response=AulaSchema,
    operation_id="getLesson",
    summary="Uma aula inteira: os campos, o instrumento, as pecas e as pausas",
    description=(
        "Tudo o que o editor precisa para desenhar o formulario de uma\n"
        "encomenda. As pecas vem SEMPRE as 18, na ordem canonica das 16 da\n"
        "anatomia e depois as duas internas (`roteiro`, `guia_do_mentor`),\n"
        "com texto vazio na que ainda nao foi escrita. As pausas vem na ordem.\n"
        "`instrumento` e o slug do cartao, ou null.\n"
        "\n"
        "404 se a aula nao existe nesse site."
    ),
)
def get_lesson(request, numero: str, site_id: str):
    return _aula_inteira(_aula(site_id, numero))


@router.put(
    "/aulas/{numero}",
    response=AulaSchema,
    operation_id="putLesson",
    summary="Grava uma aula inteira: substitui as pecas e as pausas, sobe a versao",
    description=(
        "O corpo e a aula completa, e so o que se edita: pedido, cliente,\n"
        "instrumento (slug ou null), minimo, aceito_quando (lista de frases),\n"
        "quiz (lista de {pergunta, resposta_modelo}), video_url, e_boss,\n"
        "banca_nivel (1, 2, 3 ou null), pecas [{tipo, texto}] e pausas\n"
        "[{ordem, segundo, tipo, pede, campos}].\n"
        "\n"
        "As pecas e as pausas da aula sao SUBSTITUIDAS pelas do corpo, numa\n"
        "transacao unica: ou entra tudo, ou nao entra nada. A versao sobe 1.\n"
        "O estado e a data de publicacao NAO mudam: publicar e outro gesto\n"
        "(`publishLesson`), e editar uma aula publicada a mantem publicada.\n"
        "\n"
        "422 se: tipo de peca fora do vocabulario, peca repetida, pausa com\n"
        "ordem repetida, item do quiz sem pergunta ou sem resposta_modelo,\n"
        "aceito_quando que nao seja lista de textos, instrumento inexistente,\n"
        "banca_nivel fora de 1..3, ou qualquer chave que este corpo nao\n"
        "conheca (numero, estado, versao...). 404 se a aula nao existe.\n"
        "\n"
        "Devolve a aula como ficou, no mesmo formato de `getLesson`."
    ),
)
def put_lesson(request, numero: str, site_id: str, payload: AulaParaGravarSchema):
    aula = _aula(site_id, numero)
    instrumento = _instrumento_do_slug(payload.instrumento)
    with transaction.atomic():
        aula.pedido = payload.pedido
        aula.cliente = payload.cliente
        aula.instrumento = instrumento
        aula.minimo = payload.minimo
        aula.aceito_quando = payload.aceito_quando
        aula.quiz = [item.model_dump() for item in payload.quiz]
        aula.video_url = payload.video_url
        aula.e_boss = payload.e_boss
        aula.banca_nivel = payload.banca_nivel
        aula.versao += 1
        # `estado` e `publicada_em` ficam FORA da lista de propósito: é isto que
        # faz "o PUT não publica nem despublica" ser mecânico.
        aula.save(
            update_fields=[
                "pedido",
                "cliente",
                "instrumento",
                "minimo",
                "aceito_quando",
                "quiz",
                "video_url",
                "e_boss",
                "banca_nivel",
                "versao",
            ]
        )
        aula.pecas.all().delete()
        PecaModel.objects.bulk_create(
            PecaModel(aula=aula, tipo=peca.tipo.value, texto=peca.texto)
            for peca in payload.pecas
        )
        aula.pausas.all().delete()
        PausaModel.objects.bulk_create(
            PausaModel(
                aula=aula,
                ordem=pausa.ordem,
                segundo=pausa.segundo,
                tipo=pausa.tipo.value,
                pede=pausa.pede,
                campos=pausa.campos,
            )
            for pausa in payload.pausas
        )
    return _aula_inteira(aula)


@router.get(
    "/instrumentos",
    response=list[InstrumentoSchema],
    operation_id="listInstruments",
    summary="Os 13 instrumentos, na ordem dos cartoes, com escala e descritores",
    description=(
        "A lista que o editor usa para escolher o instrumento cabivel de uma\n"
        "aula e para abrir a tela de cada cartao. Os instrumentos sao de\n"
        "plataforma inteira, por isso nao ha `site_id`. Vem na ordem do cartao\n"
        "(1 a 13), inteiros: slug, nome canonico, cartao, escala, minimos,\n"
        "secao do Padrao, descritores e versao."
    ),
)
def list_instruments(request):
    return [
        _instrumento(instrumento)
        for instrumento in InstrumentoModel.objects.order_by("cartao")
    ]


@router.get(
    "/instrumentos/{slug}",
    response=InstrumentoSchema,
    operation_id="getInstrument",
    summary="Um instrumento inteiro, pelo slug",
    description=(
        "O que `putInstrument` grava, lido de volta: escala, minimos, secao do\n"
        "Padrao, descritores e a versao vigente. 404 se o slug nao existe."
    ),
)
def get_instrument(request, slug: str):
    try:
        instrumento = InstrumentoModel.objects.get(slug=slug)
    except InstrumentoModel.DoesNotExist:
        raise HttpError(404, f"o instrumento '{slug}' não existe")
    return _instrumento(instrumento)


@router.put(
    "/instrumentos/{slug}",
    response=InstrumentoSchema,
    operation_id="putInstrument",
    summary="Grava a escala, os minimos, a secao do padrao e os descritores de um instrumento",
    description=(
        "Os instrumentos sao de plataforma inteira (os 13 cartoes sao os mesmos\n"
        "em toda escola), por isso nao ha `site_id` aqui. O corpo leva escala\n"
        "(criterios, minimo e maximo por criterio), minimo_exercicio,\n"
        "minimo_contrato, secao_do_padrao e descritores (o 5/3/1). A versao\n"
        "sobe 1: avaliacao em andamento guarda a versao em que comecou.\n"
        "\n"
        "`nome_canonico` e `cartao` sao da lei e NAO mudam pela porta: vem no\n"
        "corpo, e 422. 404 se o slug nao existe."
    ),
)
def put_instrument(request, slug: str, payload: InstrumentoParaGravarSchema):
    try:
        instrumento = InstrumentoModel.objects.get(slug=slug)
    except InstrumentoModel.DoesNotExist:
        raise HttpError(404, f"o instrumento '{slug}' não existe")
    instrumento.escala = payload.escala
    instrumento.minimo_exercicio = payload.minimo_exercicio
    instrumento.minimo_contrato = payload.minimo_contrato
    instrumento.secao_do_padrao = payload.secao_do_padrao
    instrumento.descritores = payload.descritores
    instrumento.versao += 1
    instrumento.save(
        update_fields=[
            "escala",
            "minimo_exercicio",
            "minimo_contrato",
            "secao_do_padrao",
            "descritores",
            "versao",
        ]
    )
    return _instrumento(instrumento)


@router.post(
    "/aulas/{numero}/publicar",
    response=AulaDaListaSchema,
    operation_id="publishLesson",
    summary="Publica uma aula: estado publicada, data de agora, versao inalterada",
    description=(
        "O gesto que abre a aula para a sala de aula (degrau 1.8). Muda o\n"
        "estado para `publicada` e carimba `publicada_em` com o instante de\n"
        "agora; a versao NAO muda, porque publicar nao edita.\n"
        "\n"
        "Idempotente: publicar o que ja esta publicado devolve a aula como\n"
        "esta, sem mexer na data. 404 se a aula nao existe."
    ),
)
def publish_lesson(request, numero: str, site_id: str):
    aula = _aula(site_id, numero)
    # O invariante C1 ("remissão quebrada não publica") NÃO se valida aqui, e a
    # ausência é o desenho deste degrau: a conferência é `checkLesson`, degrau
    # 3.1, e é ali que ela encaixa, ANTES deste `if`, recusando com 422 a aula
    # cujos desvios o verificador listar.
    if aula.estado != AulaModel.Estado.PUBLICADA:
        aula.estado = AulaModel.Estado.PUBLICADA
        aula.publicada_em = timezone.now()
        aula.save(update_fields=["estado", "publicada_em"])
    return _linha(aula)
