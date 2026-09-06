"""A porta de MÁQUINA da sala de aula: as doze operações do editor e da sala.

POR QUE ELA EXISTE
------------------
O conteúdo do curso mora no banco desta célula, e só nele (a lei
anti-duplicação). O editor do Admin (degrau 1.5) lê e grava por aqui, nunca no
banco e nunca guardando cópia. Este arquivo é o degrau 1.3 da escada
(`PLANO-CELULA-CURSOS.md` §10, TAR-150): `listLessons`, `getLesson`,
`putLesson`, `putInstrument` e `publishLesson`; o degrau 1.3b (TAR-161)
acrescentou `listInstruments` e `getInstrument`, porque o editor gravava a
escala de um instrumento sem poder lê-la de volta. O contrato congela A PARTIR
do que `manage.py export_openapi` imprime daqui, nunca de cabeça
(`armadilhas/243`), e a PROSA daqui congela junto (`armadilhas/324`).

O CURSO E A PARTE ENTRARAM NO ENDEREÇO (TAR-203, 05/09/2026)
-------------------------------------------------------------
Decisão do mantenedor: o link de uma aula tem de dizer ao aluno em que parte do
curso ele está. Por isso nasceram quatro operações em `/cursos/{curso}/aulas`,
que resolvem o curso pelo par site+slug e conferem a parte contra o bloco da
aula. Elas não substituíram as quatro antigas: `listSiteLessons`,
`getSiteLesson`, `putSiteLesson` e `publishSiteLesson` continuam respondendo
como sempre, porque o editor do Admin que está no ar as chama, e trocar o
endereço dele é outro PR.

O defeito que as novas curam não tinha sintoma: a porta antiga resolve a aula
pelo SITE, e a sala de aula resolvia o curso com "o primeiro do site". No dia
em que nascesse um segundo curso, o site inteiro continuaria servindo o
primeiro, sem erro, sem aviso e sem tela quebrada.

O TÍTULO E O BLOCO PASSARAM A TER POR ONDE ENTRAR (TAR-221, 06/09/2026)
-----------------------------------------------------------------------
A tela que cola o sumário do livro gravava as 16 peças de cada encomenda e
esbarrava em duas frases que não tinham porta: o título da encomenda e o
título do Boss de cada bloco.

O título saiu da lista dos proibidos, e é o único dos sete que sai. Número,
ordem, bloco, estado, versão e data de publicação são ESTRUTURA, fatos
públicos do livro, e a fonte deles é o semeador; o título é OBRA do
mantenedor, a frase que o cliente diz na encomenda, e a primeira coisa que o
aluno lê. Estar na mesma lista era o engano: ele parecia estrutura por ser
curto e por nascer com o esqueleto.

O bloco ganhou operação própria (`putBlock`) em vez de virar campo da aula,
porque doze blocos servem trinta e quatro encomendas e nenhum deles pertence a
uma aula em particular. O motivo por extenso está na seção da operação, lá
embaixo.

A VÍDEO-AULA EM TEXTO É A DÉCIMA NONA PEÇA, E NÃO A DÉCIMA SÉTIMA (TAR-233)
---------------------------------------------------------------------------
Cada encomenda passou a ter um segundo texto, a mesma aula contada como numa
vídeo-aula, e o aluno chega nele por um botão embaixo do capítulo. Ele entra e
sai por aqui como peça (`videoaula_em_texto`), e não como campo nem como tabela
nova, porque assim herda de graça o editor, o histórico de versões, a restrição
de uma por aula e o renderizador de Markdown que as outras já têm.

Ele NÃO entra em `ORDEM_CANONICA`: as 16 são a anatomia que a lei da célula
declara, e esta peça vive fora da sequência (`Peca.TIPOS_SOB_DEMANDA`).

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
com as 19 e as 3 palavras, e nenhum nome é escrito duas vezes. É por isso que a
`videoaula_em_texto` (TAR-233) passou a entrar e a sair pela porta sem nenhuma
segunda lista: bastou nascer no `TextChoices`.

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
from typing import Annotated, Any, Literal

from django.db import transaction
from django.utils import timezone
from ninja import Field, Router, Schema
from ninja.errors import HttpError, ValidationError
from pydantic import ConfigDict, model_validator

from apps.cursos import enderecos
from apps.cursos.models import PARTES_DO_CURSO
from apps.cursos.models import Aula as AulaModel
from apps.cursos.models import Bloco as BlocoModel
from apps.cursos.models import Curso as CursoModel
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

# As 3 partes em que os 12 blocos se dividem, DERIVADAS de `PARTES_DO_CURSO`
# (a mesma tupla da restrição `parte_de_bloco_e_1_2_ou_3` do banco): o OpenAPI
# exportado leva `enum: [1, 2, 3]` no parâmetro, e parte fora do vocabulário é
# 422 antes de tocar o banco. Não é segunda lista; é o vocabulário do modelo.
ParteDoCurso = enum.Enum(
    "ParteDoCurso", {f"PARTE_{parte}": parte for parte in PARTES_DO_CURSO}, type=int
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
    """O bloco como ele viaja dentro de toda aula: a estrutura do livro
    (`letra`, `ordem`, `parte`) e o que o mantenedor escreve nele (`nome` e
    `boss_titulo`, vazios até alguém os escrever por `putBlock`).

    Os dois de obra entraram aqui em 06/09/2026, e é isto que faz `putBlock`
    dispensar uma operação de leitura própria: quem grava um bloco o lê de
    volta na primeira aula dele. Gravar sem poder ler de volta foi o defeito
    que o degrau 1.3b teve de curar nos instrumentos, com um PR a mais.

    OS DOIS NOVOS CARREGAM DEFAULT, E ISSO NÃO É DESCUIDO NEM ENFEITE: sem
    ele o campo nasce em `required` no documento congelado, e
    `ci/contrato_aditivo.py` reprova o PR do Rito, porque campo obrigatório
    novo quebra quem consome pelo contrato antigo (`armadilhas/202`, medida
    aqui em 06/09/2026). O valor emitido NÃO muda: o modelo sempre tem os
    dois, com `default=""` no banco. Muda só o que o contrato EXIGE de quem
    valida. Não tire os defaults para "deixar igual aos outros três": os
    outros três nasceram com o contrato, estes chegaram depois.
    """

    letra: str
    ordem: int
    parte: int
    nome: str = ""
    boss_titulo: str = ""


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
    """O corpo de `putLesson`: o que se edita, e o título.

    O TÍTULO MUDOU DE LADO EM 06/09/2026 (TAR-221), e é o único dos sete que
    muda. Número, ordem, bloco, estado, versão e data de publicação continuam
    fora, e mandá-los é 422: são ESTRUTURA, fatos do livro, e quem os escreve é
    o semeador. O `titulo_exibido` estava nessa lista por parecer estrutura, e
    não é: ele é a frase que o cliente diz na encomenda, obra do mantenedor, e
    a primeira coisa que o aluno lê. Sem porta para ele, a encomenda ficava
    "Encomenda 22" onde o livro na mão do aluno diz outra coisa.

    ELE É OPCIONAL, E AUSENTE SIGNIFICA NÃO MEXER. O editor do Admin que já
    está no ar não manda este campo, e um `PUT` dele não pode apagar o título
    que a outra tela escreveu. Nulo diz o mesmo que ausente, de propósito:
    apagar título não é gesto que esta porta ofereça, e por isso título vazio
    é 422.
    """

    model_config = ConfigDict(extra="forbid")

    titulo_exibido: Annotated[str, Field(min_length=1, max_length=CURTO)] | None = None
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


class BlocoParaGravarSchema(Schema):
    """O corpo de `putBlock`: o nome do bloco e o título do Boss dele.

    Letra, ordem e parte NÃO entram, pelo mesmo motivo que `cartao` não entra
    em `putInstrument`: são a estrutura do livro, o semeador é a fonte delas, e
    mandá-las é 422.

    Os dois campos vêm SEMPRE, e vazio é valor válido: é com ele que os doze
    blocos nascem, e quem digitou um nome errado precisa poder apagá-lo. É a
    diferença para o título da aula, onde ausente significa não mexer, porque
    lá existe uma segunda tela gravando o mesmo campo.
    """

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(max_length=CURTO)
    boss_titulo: str = Field(max_length=CURTO)


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


def _curso(site_id: str, slug: str) -> CursoModel:
    """O curso pelo PAR site+slug, que é a unicidade do banco
    (`um_curso_por_slug_por_site`), e NUNCA "o primeiro curso do site".

    A resolução por "o primeiro" é a que esta porta tinha até 05/09/2026: no dia
    em que nascesse um segundo curso, o site inteiro continuaria servindo o
    primeiro, sem erro, sem aviso e sem tela quebrada. Slug que não existe é
    404 com os slugs que existem, nunca o primeiro curso como consolo.

    A conta mora em `apps/cursos/enderecos.py` desde 06/09/2026, porque a sala
    do aluno passou a precisar dela também (TAR-212). Uma regra, um lugar: um
    endereço que esta porta recusasse e a sala aceitasse mostraria ao aluno a
    aula errada com o número certo na barra do navegador.
    """
    curso = enderecos.curso_do_site(site_id, slug)
    if curso is None:
        raise HttpError(404, enderecos.recado_de_curso_desconhecido(site_id, slug))
    return curso


def _aula_do_curso(
    curso: CursoModel, numero: str, parte: ParteDoCurso | None
) -> AulaModel:
    """A aula daquele curso, e só se a parte pedida CASAR com a do bloco dela.

    O endereço da sala de aula carrega a parte para que o aluno saiba onde está
    (decisão do mantenedor, 05/09/2026). Um endereço que aponta certo para a
    aula ERRADA é pior do que um endereço quebrado: se a parte não casa, a
    resposta é recusa, e a frase diz em que parte a aula realmente está.

    A guarda mora em `apps/cursos/enderecos.py` desde 06/09/2026: a sala do
    aluno (TAR-212) confere a MESMA parte, e duas cópias da regra divergiriam
    justamente onde ninguém olha.
    """
    try:
        aula = AulaModel.objects.select_related("bloco", "instrumento").get(
            curso=curso, numero=numero
        )
    except AulaModel.DoesNotExist:
        raise HttpError(404, f"a aula {numero} não existe no curso '{curso.slug}'")
    recusa = enderecos.parte_errada(curso, aula, parte)
    if recusa is not None:
        raise HttpError(404, recusa)
    return aula


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


def _bloco(bloco: BlocoModel) -> dict[str, Any]:
    return {
        "letra": bloco.letra,
        "ordem": bloco.ordem,
        "parte": bloco.parte,
        "nome": bloco.nome,
        "boss_titulo": bloco.boss_titulo,
    }


def _linha(aula: AulaModel) -> dict[str, Any]:
    return {
        "numero": aula.numero,
        "ordem": aula.ordem,
        "titulo_exibido": aula.titulo_exibido,
        "bloco": _bloco(aula.bloco),
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
        # As 16 da anatomia na ordem canônica, depois as duas internas, depois a
        # sob demanda: SEMPRE as 19. A peça que ainda não foi escrita sai com
        # texto vazio, e o editor desenha o formulário inteiro desde o primeiro
        # dia. A vídeo-aula em texto entra no FIM, e fora da ordem canônica, pelo
        # motivo escrito em `Peca.TIPOS_SOB_DEMANDA`.
        "pecas": [
            {"tipo": tipo, "texto": textos.get(tipo, "")}
            for tipo in PecaModel.ORDEM_CANONICA
            + PecaModel.TIPOS_INTERNOS
            + PecaModel.TIPOS_SOB_DEMANDA
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


def _gravar(aula: AulaModel, payload: AulaParaGravarSchema) -> dict[str, Any]:
    """O que `putLesson` grava, para os DOIS caminhos: o do site e o do curso.

    Mora aqui, e não dentro de um dos dois, porque "o caminho antigo responde
    exatamente como o novo" precisa ser mecânico e não uma promessa: é o mesmo
    código, chamado com a aula que cada caminho resolveu.
    """
    instrumento = _instrumento_do_slug(payload.instrumento)
    with transaction.atomic():
        # O título só entra na lista de campos gravados quando VEIO no corpo.
        # É isto que faz "ausente não apaga" ser mecânico e não uma promessa: o
        # editor do Admin que está no ar não manda o campo, e o `update_fields`
        # dele continua sem `titulo_exibido`.
        campos = []
        if payload.titulo_exibido is not None:
            aula.titulo_exibido = payload.titulo_exibido
            campos.append("titulo_exibido")
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
            update_fields=campos
            + [
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


def _publicar(aula: AulaModel) -> dict[str, Any]:
    """O que `publishLesson` faz, para os dois caminhos. Idempotente: publicar o
    que já está publicado devolve a aula como está, sem mexer na data."""
    # O invariante C1 ("remissão quebrada não publica") NÃO se valida aqui, e a
    # ausência é o desenho deste degrau: a conferência é `checkLesson`, degrau
    # 3.1, e é ali que ela encaixa, ANTES deste `if`, recusando com 422 a aula
    # cujos desvios o verificador listar.
    if aula.estado != AulaModel.Estado.PUBLICADA:
        aula.estado = AulaModel.Estado.PUBLICADA
        aula.publicada_em = timezone.now()
        aula.save(update_fields=["estado", "publicada_em"])
    return _linha(aula)


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
    operation_id="listSiteLessons",
    summary="As aulas do curso de um site, na ordem em que o aluno as encontra",
    description=(
        "A lista que o editor mostra como indice: numero, ordem, titulo\n"
        "exibido, o bloco (letra, ordem, parte, nome e titulo do Boss), estado,\n"
        "versao, data de publicacao, se e Boss e o nivel de Banca. NENHUM texto\n"
        "de peca sai aqui: e listagem, e o texto vem em `getLesson`.\n"
        "\n"
        "`site_id` e obrigatorio. Site sem curso responde lista vazia, nao\n"
        "erro: nao ter curso ainda e um estado, nao uma falha.\n"
        "\n"
        "ESTE CAMINHO NAO SABE DE CURSO: ele lista as aulas de TODOS os cursos\n"
        "do site, e existe porque o editor que ja esta no ar o chama. Quem sabe\n"
        "de curso e de parte e `listLessons`, em /cursos/{curso}/aulas."
    ),
)
def list_site_lessons(request, site_id: str):
    aulas = (
        AulaModel.objects.filter(curso__site_id=site_id)
        .select_related("bloco")
        .order_by("ordem")
    )
    return [_linha(aula) for aula in aulas]


@router.get(
    "/aulas/{numero}",
    response=AulaSchema,
    operation_id="getSiteLesson",
    summary="Uma aula inteira: os campos, o instrumento, as pecas e as pausas",
    description=(
        "Tudo o que o editor precisa para desenhar o formulario de uma\n"
        "encomenda. As pecas vem SEMPRE as 19, na ordem canonica das 16 da\n"
        "anatomia, depois as duas internas (`roteiro`, `guia_do_mentor`) e por\n"
        "ultimo `videoaula_em_texto`, com texto vazio na que ainda nao foi\n"
        "escrita. As pausas vem na ordem. `instrumento` e o slug do cartao, ou\n"
        "null.\n"
        "\n"
        "`videoaula_em_texto` NAO E A DECIMA SETIMA PECA DA ANATOMIA: e a mesma\n"
        "encomenda contada como numa video-aula, e o aluno chega nela por um\n"
        "botao embaixo do capitulo, num modal, fora da sequencia das 16. Quem a\n"
        "recebe vazia nao deve desenhar botao nenhum.\n"
        "\n"
        "404 se a aula nao existe nesse site.\n"
        "\n"
        "ESTE CAMINHO NAO SABE DE CURSO: procura a aula pelo numero dentro do\n"
        "site inteiro. Quem sabe de curso e de parte e `getLesson`, em\n"
        "/cursos/{curso}/aulas/{numero}."
    ),
)
def get_site_lesson(request, numero: str, site_id: str):
    return _aula_inteira(_aula(site_id, numero))


@router.put(
    "/aulas/{numero}",
    response=AulaSchema,
    operation_id="putSiteLesson",
    summary="Grava uma aula inteira: substitui as pecas e as pausas, sobe a versao",
    description=(
        "O corpo e a aula completa, e so o que se edita: pedido, cliente,\n"
        "instrumento (slug ou null), minimo, aceito_quando (lista de frases),\n"
        "quiz (lista de {pergunta, resposta_modelo}), video_url, e_boss,\n"
        "banca_nivel (1, 2, 3 ou null), pecas [{tipo, texto}] e pausas\n"
        "[{ordem, segundo, tipo, pede, campos}]. Mais o titulo_exibido, que e\n"
        "OPCIONAL, e a regra dele esta em `putLesson`, palavra por palavra.\n"
        "\n"
        "As pecas e as pausas da aula sao SUBSTITUIDAS pelas do corpo, numa\n"
        "transacao unica: ou entra tudo, ou nao entra nada. A versao sobe 1.\n"
        "O estado e a data de publicacao NAO mudam: publicar e outro gesto\n"
        "(`publishLesson`), e editar uma aula publicada a mantem publicada.\n"
        "\n"
        "422 se: tipo de peca fora do vocabulario, peca repetida, pausa com\n"
        "ordem repetida, item do quiz sem pergunta ou sem resposta_modelo,\n"
        "aceito_quando que nao seja lista de textos, instrumento inexistente,\n"
        "banca_nivel fora de 1..3, titulo_exibido vazio ou com mais de 120\n"
        "letras, ou qualquer chave que este corpo nao conheca (numero, estado,\n"
        "versao...). 404 se a aula nao existe.\n"
        "\n"
        "Devolve a aula como ficou, no mesmo formato de `getSiteLesson`.\n"
        "\n"
        "ESTE CAMINHO NAO SABE DE CURSO: procura a aula pelo numero dentro do\n"
        "site inteiro. Quem sabe de curso e de parte e `putLesson`, em\n"
        "/cursos/{curso}/aulas/{numero}."
    ),
)
def put_site_lesson(request, numero: str, site_id: str, payload: AulaParaGravarSchema):
    return _gravar(_aula(site_id, numero), payload)


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
    operation_id="publishSiteLesson",
    summary="Publica uma aula: estado publicada, data de agora, versao inalterada",
    description=(
        "O gesto que abre a aula para a sala de aula (degrau 1.8). Muda o\n"
        "estado para `publicada` e carimba `publicada_em` com o instante de\n"
        "agora; a versao NAO muda, porque publicar nao edita.\n"
        "\n"
        "Idempotente: publicar o que ja esta publicado devolve a aula como\n"
        "esta, sem mexer na data. 404 se a aula nao existe.\n"
        "\n"
        "ESTE CAMINHO NAO SABE DE CURSO: procura a aula pelo numero dentro do\n"
        "site inteiro. Quem sabe de curso e de parte e `publishLesson`, em\n"
        "/cursos/{curso}/aulas/{numero}/publicar."
    ),
)
def publish_site_lesson(request, numero: str, site_id: str):
    return _publicar(_aula(site_id, numero))


# ---------------------------------------------------------------------------
# AS QUATRO OPERAÇÕES QUE SABEM DE CURSO E DE PARTE (05/09/2026)
# ---------------------------------------------------------------------------
# O endereço da sala de aula passou a carregar o curso e a parte, para que o
# link de uma aula diga ao aluno exatamente onde ele está (decisão do
# mantenedor). Estas quatro são as mesmas quatro de cima, com duas diferenças
# que são o motivo delas existirem: o curso vem pelo SLUG, e a parte, quando
# vem, é conferida contra o bloco da aula.


@router.get(
    "/cursos/{curso}/aulas",
    response=list[AulaDaListaSchema],
    operation_id="listLessons",
    summary="As aulas de um curso, pelo slug, na ordem em que o aluno as encontra",
    description=(
        "A lista que o editor mostra como indice e que a sala de aula percorre:\n"
        "numero, ordem, titulo exibido, o bloco (letra, ordem, parte, nome e\n"
        "titulo do Boss), estado, versao, data de publicacao, se e Boss e o\n"
        "nivel de Banca. NENHUM texto de peca sai aqui: e listagem, e o texto\n"
        "vem em `getLesson`.\n"
        "\n"
        "`curso` e o SLUG, resolvido pelo par site+slug, que e a unicidade do\n"
        "banco. `site_id` continua obrigatorio (uma fabrica, N lojas). Slug que\n"
        "nao existe naquele site e 404 dizendo quais existem, nunca o primeiro\n"
        "curso do site como consolo.\n"
        "\n"
        "`parte` (1, 2 ou 3) e opcional e filtra pelos blocos daquela parte: e\n"
        "o mesmo numero que viaja no endereco da sala de aula. Sem `parte`, vem\n"
        "o curso inteiro. Curso sem aula responde lista vazia, nao erro."
    ),
)
def list_lessons(request, curso: str, site_id: str, parte: ParteDoCurso | None = None):
    aulas = (
        AulaModel.objects.filter(curso=_curso(site_id, curso))
        .select_related("bloco")
        .order_by("ordem")
    )
    if parte is not None:
        aulas = aulas.filter(bloco__parte=parte)
    return [_linha(aula) for aula in aulas]


@router.get(
    "/cursos/{curso}/aulas/{numero}",
    response=AulaSchema,
    operation_id="getLesson",
    summary="Uma aula de um curso, inteira, conferida contra a parte do endereco",
    description=(
        "Tudo o que o editor e a sala de aula precisam de uma encomenda. As\n"
        "pecas vem SEMPRE as 19, na ordem canonica das 16 da anatomia, depois\n"
        "as duas internas (`roteiro`, `guia_do_mentor`) e por ultimo\n"
        "`videoaula_em_texto`, com texto vazio na que ainda nao foi escrita. As\n"
        "pausas vem na ordem. `instrumento` e o slug do cartao, ou null.\n"
        "\n"
        "`videoaula_em_texto` NAO E A DECIMA SETIMA PECA DA ANATOMIA: e a mesma\n"
        "encomenda contada como numa video-aula, e o aluno chega nela por um\n"
        "botao embaixo do capitulo, num modal, fora da sequencia das 16. Quem a\n"
        "recebe vazia nao deve desenhar botao nenhum.\n"
        "\n"
        "`parte` e opcional e NAO e filtro: e GUARDA. Quando ela vem e nao casa\n"
        "com a parte do bloco desta aula, a resposta e 404 dizendo em que parte\n"
        "a aula realmente esta, e nunca a aula. Um endereco que aponta certo\n"
        "para a aula errada e pior do que um endereco quebrado, e o endereco da\n"
        "sala de aula carrega a parte justamente para o aluno se localizar.\n"
        "\n"
        "404 tambem se o curso nao existe naquele site, ou se a aula nao existe\n"
        "naquele curso."
    ),
)
def get_lesson(
    request, curso: str, numero: str, site_id: str, parte: ParteDoCurso | None = None
):
    return _aula_inteira(_aula_do_curso(_curso(site_id, curso), numero, parte))


@router.put(
    "/cursos/{curso}/aulas/{numero}",
    response=AulaSchema,
    operation_id="putLesson",
    summary="Grava uma aula de um curso: substitui as pecas e as pausas, sobe a versao",
    description=(
        "O corpo, o que ele recusa e o que ele NAO toca sao exatamente os de\n"
        "`putSiteLesson`: pedido, cliente, instrumento (slug ou null), minimo,\n"
        "aceito_quando, quiz, video_url, e_boss, banca_nivel, pecas e pausas;\n"
        "as pecas e as pausas sao SUBSTITUIDAS numa transacao unica; a versao\n"
        "sobe 1; estado e data de publicacao nao mudam. E o mesmo codigo, com a\n"
        "aula resolvida pelo curso.\n"
        "\n"
        "O TITULO DA ENCOMENDA ENTRA POR AQUI, e ele e o unico dos sete campos\n"
        "de fora que passou a entrar. Numero, ordem, bloco, estado, versao e\n"
        "data de publicacao continuam sendo 422: sao ESTRUTURA, fatos publicos\n"
        "do livro, e quem os escreve e a instalacao do curso. O titulo e OBRA:\n"
        "e a frase que o cliente diz na encomenda e a primeira coisa que o\n"
        "aluno le, e sem porta para ele a aula ficava com o nome de esqueleto\n"
        "(`Encomenda 22`) enquanto o livro na mao do aluno dizia outra coisa.\n"
        "\n"
        "`titulo_exibido` e OPCIONAL, e ausente significa NAO MEXER, nunca\n"
        "esvaziar: ha mais de uma tela gravando esta aula, e a que nao conhece\n"
        "o campo nao pode apagar o que a outra escreveu. Nulo diz o mesmo que\n"
        "ausente. Titulo vazio e 422, porque apagar o titulo nao e gesto que\n"
        "esta porta ofereca: encomenda sem nome nao e um estado do sistema.\n"
        "O NOME DO BLOCO e o TITULO DO BOSS nao entram aqui; sao `putBlock`.\n"
        "\n"
        "`parte` e o mesmo GUARDA de `getLesson`: parte que nao casa com o\n"
        "bloco da aula recusa com 404 ANTES de gravar qualquer coisa, e nada e\n"
        "escrito. 404 tambem se o curso ou a aula nao existem.\n"
        "\n"
        "Devolve a aula como ficou, no mesmo formato de `getLesson`."
    ),
)
def put_lesson(
    request,
    curso: str,
    numero: str,
    site_id: str,
    payload: AulaParaGravarSchema,
    parte: ParteDoCurso | None = None,
):
    return _gravar(_aula_do_curso(_curso(site_id, curso), numero, parte), payload)


@router.post(
    "/cursos/{curso}/aulas/{numero}/publicar",
    response=AulaDaListaSchema,
    operation_id="publishLesson",
    summary="Publica uma aula de um curso: estado publicada, data de agora, versao inalterada",
    description=(
        "O gesto que abre a aula para a sala de aula. Muda o estado para\n"
        "`publicada` e carimba `publicada_em` com o instante de agora; a versao\n"
        "NAO muda, porque publicar nao edita. Idempotente: publicar o que ja\n"
        "esta publicado devolve a aula como esta, sem mexer na data.\n"
        "\n"
        "`parte` e o mesmo GUARDA de `getLesson`: parte que nao casa com o\n"
        "bloco da aula recusa com 404 e a aula continua como estava. 404\n"
        "tambem se o curso ou a aula nao existem."
    ),
)
def publish_lesson(
    request, curso: str, numero: str, site_id: str, parte: ParteDoCurso | None = None
):
    return _publicar(_aula_do_curso(_curso(site_id, curso), numero, parte))


# ---------------------------------------------------------------------------
# O BLOCO, QUE NÃO É DE NENHUMA AULA EM PARTICULAR (TAR-221, 06/09/2026)
# ---------------------------------------------------------------------------
# São doze linhas por curso, e o bloco A é o mesmo para a E00, a E01 e a E02.
# Por isso `nome` e `boss_titulo` não entraram em `putLesson`: se entrassem,
# gravar a E00 e depois a E01 escreveria o nome do bloco duas vezes, a última
# ganharia, e um formulário aberto com o nome antigo apagaria em silêncio o que
# a outra tela acabara de escrever. E um bloco cujas aulas ninguém tivesse
# aberto não teria como ser nomeado.
#
# Só há a forma que sabe de CURSO: as quatro operações por site existem porque
# o editor no ar as chama, e nada no ar chama bloco. Um endereço por site ainda
# teria de escolher entre os cursos do site, que é justamente o defeito que a
# TAR-203 curou.


@router.put(
    "/cursos/{curso}/blocos/{letra}",
    response=BlocoSchema,
    operation_id="putBlock",
    summary="Grava o nome de um bloco e o titulo do Boss dele",
    description=(
        "O bloco tem NOME e TITULO DO BOSS, e os dois sao obra do mantenedor:\n"
        "nascem vazios e so entram por aqui. O corpo leva os dois SEMPRE, e\n"
        "texto vazio e valor valido, porque quem digitou errado precisa poder\n"
        "apagar. Nao ha versao a subir: o bloco nao e versionado.\n"
        "\n"
        "E OPERACAO PROPRIA, e nao campo de `putLesson`, porque o bloco nao\n"
        "pertence a nenhuma aula: sao doze blocos para trinta e quatro\n"
        "encomendas, e tres aulas dividem o bloco A. Se o nome viajasse no\n"
        "corpo da aula, gravar duas aulas do mesmo bloco escreveria o nome duas\n"
        "vezes, a ultima ganharia, e um formulario aberto com o nome antigo\n"
        "apagaria o que a outra tela escreveu. Um bloco cujas aulas ninguem\n"
        "abriu tambem nao teria como ser nomeado.\n"
        "\n"
        "`letra` e a do bloco, de A a L, e `curso` e o SLUG, resolvido pelo par\n"
        "site+slug como nas quatro operacoes de aula. Letra, ordem e parte NAO\n"
        "entram no corpo: sao a estrutura do livro, o semeador e a fonte delas,\n"
        "e manda-las e 422, do mesmo jeito que `cartao` em `putInstrument`.\n"
        "\n"
        "404 se o curso nao existe naquele site, ou se aquela letra nao existe\n"
        "naquele curso. Devolve o bloco como ficou, no mesmo formato em que ele\n"
        "ja viaja dentro de cada aula: e por ai que quem grava le de volta o\n"
        "que gravou, sem uma operacao de leitura so para isso."
    ),
)
def put_block(
    request, curso: str, letra: str, site_id: str, payload: BlocoParaGravarSchema
):
    encontrado = _curso(site_id, curso)
    try:
        bloco = BlocoModel.objects.get(curso=encontrado, letra=letra)
    except BlocoModel.DoesNotExist:
        letras = ", ".join(
            BlocoModel.objects.filter(curso=encontrado)
            .order_by("ordem")
            .values_list("letra", flat=True)
        )
        raise HttpError(
            404,
            f"o curso '{encontrado.slug}' não tem o bloco '{letra}'; "
            f"as letras dele são: {letras}",
        )
    bloco.nome = payload.nome
    bloco.boss_titulo = payload.boss_titulo
    bloco.save(update_fields=["nome", "boss_titulo"])
    return _bloco(bloco)
