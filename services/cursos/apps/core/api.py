"""A porta de MÁQUINA da sala de aula: as dezessete operações do editor e da sala.

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

A SALA SERVE VÁRIOS CURSOS, E ELES NASCEM POR AQUI (TAR-266, 07/09/2026)
-------------------------------------------------------------------------
Decisão do mantenedor (`DECISAO-a-sala-serve-varios-cursos.md`): a sala serve
quantos cursos a escola vender, cada um com o seu produto, a sua regra de
avanço e a sua estrutura. Até essa data só o `semear_esqueleto` criava curso,
e só o do livro. Quatro operações nasceram: `listCourses`, `createCourse`,
`putCourse` e `putCourseStructure`.

`putCourseStructure` faz pela porta o que o semeador faz para o livro:
reconcilia ESTRUTURA (bloco, ordem, parte, Boss, Banca) e nunca toca OBRA
(pedido, cliente, peças, pausas, quiz, vídeo, estado, versão). O título da
aula só entra onde está VAZIO: obra escrita não se sobrescreve. O nome do
bloco e o título do Boss são ESTRUTURA (as letras são posicionais, e o nome
viaja com a posição): nulo não mexe, texto grava, vazio apaga. Aula que some
da estrutura só é apagada se nenhum aluno passou por ela, conferido dentro da
transação que apaga; se passou, é 422 com os números, e nada é gravado. O
texto das aulas continua entrando só por `putLesson` ([INV-CUR-C2] intacto).

O QUE FICA DE FORA, DE PROPÓSITO
--------------------------------
Não há sessão nem cookie: é máquina para máquina, e o Bearer do par
(`apps/core/auth.py`) é o único cadeado. Não há `getReviewQueue` (2.1) nem
`getStudentProgress` (1.8).

O REVISOR DE COERÊNCIA ENTROU AQUI (TAR-245, degrau 3.1)
---------------------------------------------------------
`checkLesson` confere uma aula e devolve a lista de defeitos, cada um já em
português, e não grava nada: é o agente de degrau A do §7, código e não IA.

E as duas operações de publicar passaram a RECUSAR com 422 a aula cuja peça
manda o aluno para uma encomenda que não existe no curso. É o [INV-CUR-C1], e
as outras cinco conferências continuam sendo aviso: o §7 pôs o veto na remissão,
e só nela. A regra mora em `apps/cursos/coerencia.py`; o ponto onde ela encaixa
na publicação é `_publicar`.

O GUARDIÃO DE FIDELIDADE ENTROU COMO PARÂMETRO (TAR-246, degrau 3.2)
---------------------------------------------------------------------
O segundo conferente é IA, e não ganhou operação nova: `checkLesson` ganhou o
parâmetro opcional `modo`. Ele responde a mesma pergunta, na mesma resposta e
para a mesma tela; o que muda é a régua. A razão por extenso está na seção da
operação. A regra mora em `apps/cursos/fidelidade.py`, e continuam sendo TREZE
operações.

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
Todo corpo de `PUT` e de `POST` recusa chave desconhecida com 422. É o que faz
"`nome_canonico` e `cartao` não mudam pela porta" ser mecânico, e é o que
impede um editor de mandar `estado: "publicada"` num `PUT` e acreditar que
publicou: o que esta porta ignora em silêncio, ela nunca ignora.

Guardas: `tests/test_porta_de_maquina.py` e `tests/test_porta_exige_bearer.py`.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify
from ninja import Field, Router, Schema
from ninja.errors import HttpError, ValidationError
from pydantic import ConfigDict, model_validator

from apps.cursos import coerencia, enderecos, fidelidade
from apps.cursos.models import PADRAO_DO_NUMERO_DE_AULA, PARTES_DO_CURSO
from apps.cursos.models import Aula as AulaModel
from apps.cursos.models import AulaAvulsa as AulaAvulsaModel
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


class AulaAvulsaSchema(Schema):
    """A aula avulsa que o Admin lista e que a pagina compartilhada mostra.

    `slug` e o endereco final salvo pelo servico. Ele nasce do titulo na criacao
    e pode mudar na edicao quando o Admin envia um slug valido. Se o endereco
    pedido estiver ocupado no mesmo site, o servico acrescenta um sufixo numerico
    e devolve aqui o endereco efetivamente salvo. `estado` sempre e `publicada`:
    esta porta nao oferece rascunho nem uma segunda publicacao."""

    titulo: str
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    video_url: str
    descricao: str
    estado: Literal["publicada"]
    publicada_em: datetime


class DefeitoSchema(Schema):
    """Um defeito de coerência apontado por `checkLesson` (degrau 3.1).

    Os campos são os do `apps.cursos.coerencia.Defeito`, e a tradução para
    português JÁ VEM PRONTA daqui: `frase` diz o que está errado e
    `o_que_fazer` diz o conserto, as duas escritas para a professora ler. A
    tela do Admin as mostra verbatim, e isso é de propósito: reescrevê-las lá
    amarraria a tela à redação desta célula, que é a dona da regra. É o mesmo
    desenho do `value_error` que `putInstrument` já devolve.

    `peca` é o tipo da peça onde está o defeito, ou texto VAZIO quando ele é da
    aula inteira: o mesmo arquivo escrito com dois nomes não mora em peça
    nenhuma, mora entre elas. `alvo` é o pedaço de texto em falta, para quem
    for consertar poder procurá-lo.

    `impede_publicar` é verdadeiro só na remissão quebrada, que é o
    [INV-CUR-C1]. Ele viaja dentro do defeito, e não numa segunda lista de
    códigos que vetam, porque uma segunda lista divergiria da recusa de
    `publishLesson` no primeiro dia em que alguém mexesse numa das duas.
    """

    codigo: str
    peca: str
    alvo: str
    frase: str
    o_que_fazer: str
    impede_publicar: bool


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


class CursoSchema(Schema):
    """O curso como a lista do Admin o mostra: a identidade (`slug`, `nome`),
    o estado, a regra de avanço, o produto do catálogo a que ele aponta (texto
    vazio enquanto ninguém apontar; curso sem produto fecha a sala) e as duas
    contagens que dizem se ele já tem o que mostrar a um aluno.

    `progressao` é o `TextChoices` do modelo, e o OpenAPI leva o `enum` com as
    duas palavras: nenhum nome escrito duas vezes.
    """

    slug: str
    nome: str
    estado: str
    progressao: CursoModel.Progressao
    produto_id: str
    total_de_aulas: int
    aulas_publicadas: int


class BlocoComAulasSchema(BlocoSchema):
    """Um bloco com as aulas dele, na ordem: é como `putCourseStructure`
    devolve a estrutura que acabou de gravar. Cada aula sai no formato da
    listagem (`AulaDaListaSchema`), e por isso carrega o bloco de novo dentro
    de si: é o preço de um formato só para a aula em toda a porta."""

    aulas: list[AulaDaListaSchema]


class EstruturaSchema(Schema):
    """A resposta de `putCourseStructure`: a estrutura como ficou e as quatro
    contagens do que a reconciliação fez. `aulas_preservadas` conta as aulas
    que já existiam e ficaram: a obra delas está intacta, e só bloco, ordem,
    Boss e Banca foram conferidos."""

    blocos: list[BlocoComAulasSchema]
    blocos_criados: int
    aulas_criadas: int
    aulas_preservadas: int
    aulas_apagadas: int


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


class AulaAvulsaParaCriarSchema(Schema):
    """O unico corpo que cria uma aula avulsa. O Admin oferece os tres
    campos ao mantenedor, mas so o servico gera o endereco pelo titulo.
    Descricao aceita texto vazio, para uma explicacao curta que so precisa
    do titulo e do video, mas o campo sempre viaja no corpo.
    """

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=1, max_length=CURTO)
    video_url: str = Field(min_length=1, max_length=URL)
    descricao: str = Field(max_length=5000)


class _SlugAusente(str):
    pass


_SLUG_AUSENTE = _SlugAusente()


class SlugDeAulaAvulsaInvalido(HttpError):
    def __init__(self):
        super().__init__(422, "o endereço da aula precisa usar o formato informado")


class AulaAvulsaParaEditarSchema(Schema):
    """O corpo que edita uma aula avulsa. Os tres campos de conteudo
    continuam obrigatorios. `slug` e opcional: ausente, conserva o endereco;
    presente, aceita o texto digitado para um novo endereco e o servico o
    normaliza para ASCII minusculo com hifens.
    Em colisao com outra aula, o servico reserva atomicamente o menor sufixo
    numerico livre e devolve o slug final salvo na resposta. O slug da propria
    aula nao conta como colisao."""

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=1, max_length=CURTO)
    video_url: str = Field(min_length=1, max_length=URL)
    descricao: str = Field(max_length=5000)
    slug: str = Field(default_factory=lambda: _SLUG_AUSENTE, max_length=140)


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
# OS CORPOS DO CURSO E DA ESTRUTURA (TAR-266)
# ---------------------------------------------------------------------------


class CursoParaCriarSchema(Schema):
    """O corpo de `createCourse`. `slug` é o apelido do endereço
    (`/cursos/<slug>/`), minúsculas, dígitos e hífen, e é o único campo que
    nunca muda depois: ele é a identidade do curso no par site+slug.
    `progressao` nasce `por_laudo` quando não vem; `produto_id` nasce vazio,
    que significa "ainda não apontado", e curso sem produto fecha a sala."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    nome: str = Field(min_length=1, max_length=CURTO)
    progressao: CursoModel.Progressao = CursoModel.Progressao.POR_LAUDO
    produto_id: str = Field("", max_length=64)


class CursoParaAlterarSchema(Schema):
    """O corpo de `putCourse`: os três campos que mudam, todos opcionais, e
    AUSENTE OU NULO SIGNIFICA NÃO MEXER, a mesma regra do `titulo_exibido` em
    `putLesson`. `produto_id` vazio é valor válido e desaponta o produto (a
    sala fecha); é o mesmo gesto do comando `apontar_o_produto_do_curso`, pela
    porta. Nome vazio é 422: curso sem nome não é um estado do sistema."""

    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, Field(min_length=1, max_length=CURTO)] | None = None
    progressao: CursoModel.Progressao | None = None
    produto_id: Annotated[str, Field(max_length=64)] | None = None


class AulaDaEstruturaSchema(Schema):
    """Uma aula como a estrutura a declara: só o que é ESTRUTURA. `titulo` é a
    exceção aparente: ele só preenche o título de uma aula que ainda não tem
    um, e nunca sobrescreve o que a tela escreveu."""

    model_config = ConfigDict(extra="forbid")

    numero: str = Field(pattern=PADRAO_DO_NUMERO_DE_AULA)
    titulo: str = Field(min_length=1, max_length=CURTO)
    e_boss: bool = False
    banca_nivel: Literal[1, 2, 3] | None = None


class BlocoDaEstruturaSchema(Schema):
    """Um bloco como a estrutura o declara: a letra, a parte (o enum do
    contrato), as aulas na ordem, e os dois textos do bloco. A estrutura e a
    fonte do nome do bloco e do titulo do Boss, porque as letras sao
    posicionais: o bloco que hoje e o A pode virar o B na estrutura nova, e
    o nome tem de viajar com ele. Por isso os dois campos tem tres estados:
    ausente ou nulo NAO MEXE no que esta gravado; texto GRAVA aquele valor;
    texto vazio APAGA."""

    model_config = ConfigDict(extra="forbid")

    letra: str = Field(pattern=r"^[A-Z]$")
    parte: ParteDoCurso
    nome: str | None = Field(
        None,
        max_length=CURTO,
        description=(
            "O nome do bloco. Ausente ou nulo: o nome gravado fica como esta. "
            "Texto: passa a ser este, mesmo que o bloco ja tivesse outro. "
            "Texto vazio: apaga o nome."
        ),
    )
    boss_titulo: str | None = Field(
        None,
        max_length=CURTO,
        description=(
            "O titulo do Boss do bloco. Ausente ou nulo: o titulo gravado fica "
            "como esta. Texto: passa a ser este, mesmo que o bloco ja tivesse "
            "outro. Texto vazio: apaga o titulo."
        ),
    )
    aulas: list[AulaDaEstruturaSchema]


class EstruturaParaGravarSchema(Schema):
    """O corpo de `putCourseStructure`: os blocos na ordem, cada um com as
    aulas na ordem. A ordem dos blocos é a posição na lista, de um; a das
    aulas é a posição no curso inteiro, do zero: exatamente a conta do
    semeador do livro."""

    model_config = ConfigDict(extra="forbid")

    blocos: list[BlocoDaEstruturaSchema]

    @model_validator(mode="after")
    def sem_repeticao_e_sem_vazio(self):
        """Letra repetida e número repetido são as duas unicidades do banco
        (`uma_letra_por_bloco_por_curso`, `um_numero_por_aula_por_curso`);
        recusadas aqui viram 422 dizendo a linha, não IntegrityError. Estrutura
        sem bloco e bloco sem aula também são 422: apagar um curso inteiro não
        é gesto que esta porta ofereça, e um bloco vazio é um título que
        nenhum aluno alcança."""
        if not self.blocos:
            raise ValueError("a estrutura precisa ter pelo menos um bloco")
        letras: dict[str, int] = {}
        numeros: dict[str, str] = {}
        for posicao, bloco in enumerate(self.blocos, start=1):
            if bloco.letra in letras:
                raise ValueError(
                    f"bloco {posicao}: a letra '{bloco.letra}' repete a do "
                    f"bloco {letras[bloco.letra]}"
                )
            letras[bloco.letra] = posicao
            if not bloco.aulas:
                raise ValueError(
                    f"bloco {posicao} ('{bloco.letra}'): não tem aula nenhuma"
                )
            for linha, aula in enumerate(bloco.aulas, start=1):
                if aula.numero in numeros:
                    raise ValueError(
                        f"bloco {posicao} ('{bloco.letra}'), aula {linha}: o "
                        f"número '{aula.numero}' repete o de {numeros[aula.numero]}"
                    )
                numeros[aula.numero] = f"bloco {letras[bloco.letra]} ('{bloco.letra}')"
        return self


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
    que já está publicado devolve a aula como está, sem mexer na data.

    A CONFERÊNCIA VEM ANTES DO `if`, e não depois, de propósito: a aula que já
    está publicada e ganhou uma remissão quebrada numa edição posterior tem de
    ser recusada também. Se a checagem viesse depois, a idempotência viraria a
    porta dos fundos do [INV-CUR-C1], e a aula quebrada passaria calada, com
    200, só por já estar publicada.
    """
    quebradas = coerencia.impedem_publicar(aula)
    if quebradas:
        numeros = ", ".join(sorted({defeito.alvo for defeito in quebradas}))
        raise HttpError(
            422,
            f"esta encomenda manda o aluno para {numeros}, que não existe neste "
            "curso. Troque pelo número da encomenda certa, ou tire a remissão do "
            "texto. Enquanto ela estiver lá, a encomenda não abre para os alunos; "
            "o botão Conferir coerência mostra em qual peça ela está.",
        )
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
# AS OPERAÇÕES
# ---------------------------------------------------------------------------

_ID_DO_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _youtube_incorporavel(url: str) -> bool:
    """Só URL HTTPS do YouTube que a página pública pode incorporar."""
    partes = urlsplit(url)
    if partes.scheme != "https":
        return False
    host = partes.netloc.lower().removeprefix("www.").removeprefix("m.")
    segmentos = [segmento for segmento in partes.path.split("/") if segmento]
    if host == "youtu.be" and segmentos:
        video_id = segmentos[0]
    elif host == "youtube.com" and segmentos:
        if segmentos[0] == "watch":
            video_id = dict(
                par.split("=", 1) for par in partes.query.split("&") if "=" in par
            ).get("v", "")
        elif segmentos[0] in ("embed", "shorts") and len(segmentos) > 1:
            video_id = segmentos[1]
        else:
            return False
    else:
        return False
    return bool(_ID_DO_YOUTUBE.fullmatch(video_id))


def _aula_avulsa(aula: AulaAvulsaModel) -> dict[str, Any]:
    return {
        "titulo": aula.titulo,
        "slug": aula.slug,
        "video_url": aula.video_url,
        "descricao": aula.descricao,
        "estado": aula.estado,
        "publicada_em": aula.publicada_em,
    }


def _proximo_slug(titulo: str, sufixo: int) -> str:
    base = slugify(titulo) or "aula"
    cauda = "" if sufixo == 1 else f"-{sufixo}"
    return f"{base[: 140 - len(cauda)].rstrip('-') or 'aula'}{cauda}"


def _slug_normalizado(valor: str) -> str:
    slug = slugify(valor)[:140].rstrip("-")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SlugDeAulaAvulsaInvalido()
    return slug


def _proximo_slug_livre(site_id: str, base: str, aula_id: int) -> str:
    ocupados = set(
        AulaAvulsaModel.objects.filter(site_id=site_id)
        .exclude(pk=aula_id)
        .values_list("slug", flat=True)
    )
    for sufixo in range(1, 10_000):
        candidato = _proximo_slug(base, sufixo)
        if candidato not in ocupados:
            return candidato
    raise HttpError(409, "não foi possível encontrar um endereço livre para esta aula")


def _campos_da_aula_avulsa(
    payload: AulaAvulsaParaCriarSchema | AulaAvulsaParaEditarSchema,
) -> tuple[str, str]:
    titulo = payload.titulo.strip()
    if not titulo:
        raise HttpError(422, "o título da aula avulsa não pode ficar vazio")
    video_url = payload.video_url.strip()
    if not _youtube_incorporavel(video_url):
        raise HttpError(
            422,
            "a URL do vídeo precisa ser um link HTTPS incorporável do YouTube. "
            "Use um link de assistir, curto, incorporar ou Shorts.",
        )
    return titulo, video_url


@router.get(
    "/aulas-avulsas",
    response=list[AulaAvulsaSchema],
    operation_id="listStandaloneLessons",
    summary="As aulas avulsas publicadas de um site, da mais recente para a mais antiga",
    description=(
        "A lista que o Admin consulta para reencontrar e compartilhar uma\n"
        "aula avulsa. Ela so devolve aulas publicadas do mesmo `site_id`, da mais\n"
        "recente para a mais antiga. Site sem aula avulsa responde lista vazia,\n"
        "porque esse e o primeiro uso normal.\n"
        "\n"
        "Aula avulsa nao pertence a curso, bloco, parte, progresso ou avaliacao.\n"
        "Ela existe para responder uma duvida em grupo com um endereco proprio."
    ),
)
def list_standalone_lessons(request, site_id: str):
    return [
        _aula_avulsa(aula) for aula in AulaAvulsaModel.objects.filter(site_id=site_id)
    ]


@router.post(
    "/aulas-avulsas",
    response={201: AulaAvulsaSchema},
    operation_id="createStandaloneLesson",
    summary="Cria e publica uma aula avulsa com endereço próprio",
    description="O gesto Criar aula avulsa do Admin. O corpo recebe somente titulo,\nvideo_url e descricao. O servico gera o slug pelo titulo e o estabiliza\nna criacao: se um titulo igual ja tiver ocupado o endereco naquele site,\nele acrescenta um sufixo numerico sem pedir que o Admin escolha outro.\n\nA aula nasce publicada, com estado `publicada`, e pode ser lida na hora\npelo endereco devolvido. Nao existe rascunho nem gesto posterior de\npublicacao nesta porta. A edicao usa `updateStandaloneLesson`: preserva\no endereco original somente quando o corpo do PUT omite `slug`.\n\n422 se titulo ou video_url estiverem vazios, a URL nao for um link HTTPS\ndo YouTube incorporavel, a descricao passar de 5.000 caracteres ou o\ncorpo tiver uma chave desconhecida.",
)
def create_standalone_lesson(request, site_id: str, payload: AulaAvulsaParaCriarSchema):
    titulo, video_url = _campos_da_aula_avulsa(payload)
    for sufixo in range(1, 10_000):
        try:
            with transaction.atomic():
                aula = AulaAvulsaModel.objects.create(
                    site_id=site_id,
                    titulo=titulo,
                    slug=_proximo_slug(titulo, sufixo),
                    video_url=video_url,
                    descricao=payload.descricao,
                )
            return 201, _aula_avulsa(aula)
        except IntegrityError:
            continue
    raise HttpError(409, "não foi possível criar um endereço único para esta aula")


@router.put(
    "/aulas-avulsas/{slug}",
    response=AulaAvulsaSchema,
    operation_id="updateStandaloneLesson",
    summary="Edita uma aula avulsa e pode trocar seu endereço",
    description="O gesto Editar aula avulsa do Admin. O `slug` do caminho identifica\na aula existente. O corpo recebe titulo, video_url, descricao e, opcionalmente,\num slug novo. Esse slug pode conter o texto digitado pela pessoa. Quando ele\nvier, o servico normaliza acentos, simbolos e espacos para letras ASCII\nminusculas, numeros e hifens; depois grava o endereco pedido ou,\nse ele ja estiver ocupado por outra aula no mesmo site, acrescenta o menor\nsufixo numerico livre, como `-2` e `-3`. O slug igual ao da propria aula\nnao e colisao e permanece igual. Antes de gravar, o servico reserva o\nendereco por unicidade atomica de site e slug. Se outra gravacao ocupar\no sufixo no mesmo instante, ele tenta o proximo menor sufixo livre antes\nde responder. Nao ha conflito para o Admin resolver: a resposta 200 sempre\ndevolve o slug final salvo.\n\nSem slug no corpo, o endereco atual permanece. Site ou slug do caminho\ninexistente responde 404. Corpo invalido responde 422, inclusive campo\ndesconhecido, slug que nao gera letras ou numeros, titulo ou video_url vazios, URL que\nnao seja HTTPS incorporavel do YouTube e descricao acima de 5.000 caracteres.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "preservar_endereco": {
                            "summary": "Sem "
                            "slug, "
                            "a "
                            "aula "
                            "conserva "
                            "o "
                            "endereço "
                            "atual",
                            "value": {
                                "descricao": "Primeira " "aula " "de " "testes",
                                "titulo": "Aula " "de " "testes",
                                "video_url": "https://www.youtube.com/embed/abcdefghijk",
                            },
                        },
                        "slug_normalizado": {
                            "summary": "Texto "
                            "digitado "
                            "vira "
                            "um "
                            "endereço "
                            "simples",
                            "value": {
                                "descricao": "Primeira " "aula " "de " "testes",
                                "slug": "Ação " "& " "Testes",
                                "titulo": "Aula " "de " "testes",
                                "video_url": "https://www.youtube.com/embed/abcdefghijk",
                            },
                        },
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "OK",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AulaAvulsaSchema"},
                        "examples": {
                            "menor_sufixo_livre": {
                                "summary": "O "
                                "sufixo "
                                "dois "
                                "esta "
                                "ocupado "
                                "e "
                                "o "
                                "tres "
                                "e "
                                "o "
                                "primeiro "
                                "livre",
                                "value": {
                                    "descricao": "Primeira " "aula " "de " "testes",
                                    "estado": "publicada",
                                    "publicada_em": "2026-09-11T10:58:49.598Z",
                                    "slug": "aula-de-testes-3",
                                    "titulo": "Aula " "de " "testes",
                                    "video_url": "https://www.youtube.com/embed/abcdefghijk",
                                },
                            },
                            "slug_identico": {
                                "summary": "O "
                                "slug "
                                "pedido "
                                "ja "
                                "e "
                                "o "
                                "da "
                                "propria "
                                "aula",
                                "value": {
                                    "descricao": "Primeira " "aula " "de " "testes",
                                    "estado": "publicada",
                                    "publicada_em": "2026-09-11T10:58:49.598Z",
                                    "slug": "aula-de-testes",
                                    "titulo": "Aula " "de " "testes",
                                    "video_url": "https://www.youtube.com/embed/abcdefghijk",
                                },
                            },
                            "slug_normalizado": {
                                "summary": "O "
                                "serviço "
                                "devolve "
                                "o "
                                "endereço "
                                "que "
                                "normalizou",
                                "value": {
                                    "descricao": "Primeira " "aula " "de " "testes",
                                    "estado": "publicada",
                                    "publicada_em": "2026-09-11T10:58:49.598Z",
                                    "slug": "acao-testes",
                                    "titulo": "Aula " "de " "testes",
                                    "video_url": "https://www.youtube.com/embed/abcdefghijk",
                                },
                            },
                            "slug_ocupado": {
                                "summary": "Outra "
                                "aula "
                                "ja "
                                "usa "
                                "o "
                                "slug "
                                "pedido",
                                "value": {
                                    "descricao": "Primeira " "aula " "de " "testes",
                                    "estado": "publicada",
                                    "publicada_em": "2026-09-11T10:58:49.598Z",
                                    "slug": "aula-de-testes-2",
                                    "titulo": "Aula " "de " "testes",
                                    "video_url": "https://www.youtube.com/embed/abcdefghijk",
                                },
                            },
                        },
                    }
                },
            },
            "404": {
                "content": {
                    "application/json": {
                        "examples": {
                            "aula_nao_encontrada": {
                                "value": {
                                    "erro": "aula_avulsa_nao_encontrada",
                                    "o_que_fazer": "Confira "
                                    "o "
                                    "endereço "
                                    "da "
                                    "aula "
                                    "ou "
                                    "escolha "
                                    "outra "
                                    "aula "
                                    "publicada.",
                                }
                            }
                        },
                        "schema": {
                            "additionalProperties": False,
                            "properties": {
                                "erro": {
                                    "const": "aula_avulsa_nao_encontrada",
                                    "type": "string",
                                },
                                "o_que_fazer": {"minLength": 1, "type": "string"},
                            },
                            "required": ["erro", "o_que_fazer"],
                            "type": "object",
                        },
                    }
                },
                "description": "Aula avulsa inexistente para este site e slug do caminho",
            },
            "422": {
                "content": {
                    "application/json": {
                        "examples": {
                            "slug_invalido": {
                                "value": {
                                    "erro": "slug_invalido",
                                    "o_que_fazer": "Informe "
                                    "um "
                                    "endereço "
                                    "com "
                                    "ao "
                                    "menos "
                                    "uma "
                                    "letra "
                                    "ou "
                                    "número.",
                                }
                            }
                        },
                        "schema": {
                            "additionalProperties": False,
                            "properties": {
                                "erro": {
                                    "enum": ["corpo_invalido", "slug_invalido"],
                                    "type": "string",
                                },
                                "o_que_fazer": {"minLength": 1, "type": "string"},
                            },
                            "required": ["erro", "o_que_fazer"],
                            "type": "object",
                        },
                    }
                },
                "description": "Corpo invalido, inclusive slug que nao gera letras ou "
                "numeros",
            },
        },
        "x-normalizacao-de-slug": {
            "algoritmo": "unicode_para_ascii_minusculo_com_hifens",
            "campo": "slug",
            "exemplo": {"entrada": "Ação & Testes", "saida": "acao-testes"},
        },
        "x-reserva-de-slug": {
            "atomica": True,
            "chave": ["site_id", "slug"],
            "em_colisao": "menor_sufixo_numerico_livre",
            "exclui_aula_editada": True,
            "repete_ate_reservar": True,
        },
    },
)
def update_standalone_lesson(
    request,
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")],
    site_id: str,
    payload: AulaAvulsaParaEditarSchema,
):
    titulo, video_url = _campos_da_aula_avulsa(payload)
    slug_pedido = (
        None if payload.slug is _SLUG_AUSENTE else _slug_normalizado(payload.slug)
    )
    for _ in range(10_000):
        try:
            with transaction.atomic():
                aula = (
                    AulaAvulsaModel.objects.select_for_update()
                    .filter(site_id=site_id, slug=slug)
                    .first()
                )
                if aula is None:
                    raise HttpError(
                        404, "aula avulsa inexistente para este site e slug"
                    )
                slug_final = (
                    aula.slug
                    if slug_pedido is None or slug_pedido == aula.slug
                    else _proximo_slug_livre(site_id, slug_pedido, aula.pk)
                )
                aula.titulo = titulo
                aula.slug = slug_final
                aula.video_url = video_url
                aula.descricao = payload.descricao
                aula.save(update_fields=["titulo", "slug", "video_url", "descricao"])
            return _aula_avulsa(aula)
        except IntegrityError:
            continue
    raise HttpError(409, "não foi possível encontrar um endereço livre para esta aula")


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
        "422 QUANDO A ENCOMENDA TEM REMISSAO QUEBRADA: uma peca que manda o\n"
        "aluno para uma encomenda `E[NN]` que nao existe neste curso impede\n"
        "publicar, e o `detail` diz quais numeros sao. E o invariante\n"
        "[INV-CUR-C1], e ele vale tambem para a aula JA publicada que ganhou\n"
        "a remissao numa edicao posterior. As outras cinco conferencias de\n"
        "`checkLesson` sao aviso, e nao impedem publicar.\n"
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
        "422 QUANDO A ENCOMENDA TEM REMISSAO QUEBRADA: uma peca que manda o\n"
        "aluno para uma encomenda `E[NN]` que nao existe neste curso impede\n"
        "publicar, e o `detail` diz quais numeros sao. E o invariante\n"
        "[INV-CUR-C1], e ele vale tambem para a aula JA publicada que ganhou\n"
        "a remissao numa edicao posterior. As outras cinco conferencias de\n"
        "`checkLesson` sao aviso, e nao impedem publicar.\n"
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
# OS DOIS CONFERENTES DA ENCOMENDA (TAR-245, degrau 3.1; TAR-246, degrau 3.2)
# ---------------------------------------------------------------------------
# Ele é de LEITURA e não grava nada: confere a aula como ela está gravada e
# devolve a lista de defeitos. É por isso que é `GET`, e não um `POST` que
# "roda a conferência": não há nada para rodar nem nada para guardar, e um
# `POST` faria a tela do Admin precisar de CSRF para fazer uma pergunta.
#
# Ele mora só no caminho que sabe de curso. As quatro irmãs sem curso existem
# porque o editor que está no ar as chama desde antes da TAR-203; esta nasceu
# depois, e nascer com o defeito que aquelas carregam seria escolhê-lo.
#
# O `modo` É PARÂMETRO, E NÃO OPERAÇÃO NOVA (degrau 3.2, TAR-246)
# ---------------------------------------------------------------------
# O Guardião de fidelidade responde a MESMA pergunta que o Revisor de
# coerência ("o que está errado nesta encomenda?"), com a mesma resposta
# (`list[DefeitoSchema]`) e para a mesma tela. O que muda é a régua: o Revisor
# compara a encomenda com ela mesma, por código; o Guardião compara cada peça
# derivada com a fonte dela, por IA.
#
# Uma segunda operação teria de repetir o endereço, a resolução do curso, o
# guarda da parte e o formato da resposta, e o dia em que uma das quatro coisas
# mudasse, mudaria em um lugar só. `modo` é opcional e o padrão é `coerencia`:
# quem chamava antes deste degrau continua recebendo, byte a byte, o que
# recebia. Modo fora dos dois é 422 do ninja, antes de tocar o banco.
class ModoDeConferencia(str, enum.Enum):
    COERENCIA = "coerencia"
    FIDELIDADE = "fidelidade"


@router.get(
    "/cursos/{curso}/aulas/{numero}/conferir",
    response=list[DefeitoSchema],
    operation_id="checkLesson",
    summary="Confere a coerencia de uma aula e devolve os defeitos, sem gravar nada",
    description=(
        "O Revisor de coerencia: CODIGO, e nao inteligencia artificial. Ele\n"
        "aponta e nunca corrige, nao grava nada e nao sobe versao.\n"
        "\n"
        "As SEIS conferencias sao as do plano da celula: remissao `E[NN]` para\n"
        "aula que existe no curso; instrumento e defeito citados pelo nome\n"
        "canonico; o mesmo arquivo escrito igual em todas as pecas; a mesma\n"
        "contagem com o mesmo numero; o `Aceito quando` da peca `Voce faz`\n"
        "igual a lista do checkpoint; e nenhum numero de plataforma no que o\n"
        "aluno le.\n"
        "\n"
        "Cada defeito traz `codigo` (o vocabulario fechado das seis),\n"
        "`peca` (o tipo da peca, ou vazio quando o defeito e da aula inteira),\n"
        "`alvo` (o pedaco de texto em falta), `frase` e `o_que_fazer`, as duas\n"
        "ja em portugues, escritas para quem edita a aula ler direto na tela.\n"
        "\n"
        "`impede_publicar` e verdadeiro SO na remissao quebrada, que e o\n"
        "[INV-CUR-C1]: e o unico defeito que `publishLesson` recusa com 422.\n"
        "Os outros cinco sao aviso.\n"
        "\n"
        "Aula sem defeito responde lista vazia, e nao erro. `parte` e o mesmo\n"
        "GUARDA de `getLesson`. 404 se o curso ou a aula nao existem.\n"
        "\n"
        "O `modo` ESCOLHE A REGUA, e o padrao e `coerencia`, identico ao que\n"
        "esta operacao respondia antes do degrau 3.2.\n"
        "\n"
        "Em `modo=fidelidade` responde o GUARDIAO DE FIDELIDADE, que e IA, e\n"
        "nao codigo. Ele compara cada peca DERIVADA com a FONTE de que ela\n"
        "deriva e aponta onde o sentido mudou: o `roteiro` e a\n"
        "`videoaula_em_texto` contra as 16 pecas canonicas, o `guia_do_mentor`\n"
        "contra o `Aceito quando` mais as pecas `voce_faz` e `checkpoint`, e a\n"
        "peca `dicionario_cartao_respostas` (onde mora o Cartao de 1 pagina)\n"
        "contra as outras 15. Peca derivada sem texto nao e comparada.\n"
        "\n"
        "O `codigo` de cada defeito de fidelidade vem de OUTRO vocabulario\n"
        "fechado, o dos sete desvios da ficha: `invencao`,\n"
        "`regra_virou_sugestao`, `nome_trocado`, `omissao`,\n"
        "`sentido_alterado`, `decisao_simplificada` e\n"
        "`comparacao_entre_pessoas`. `peca` e a peca DERIVADA, `alvo` e o\n"
        "trecho dela, e `frase` traz o trecho da fonte ao lado do trecho da\n"
        "saida. `impede_publicar` e SEMPRE falso neste modo: o Guardiao\n"
        "aponta, e nunca veta.\n"
        "\n"
        "422 em `modo=fidelidade` quando a encomenda nao tem nenhuma peca\n"
        "derivada escrita, e quando um dos textos passa do teto desta\n"
        "conferencia; o `detail` diz o que fazer, em portugues. 503 quando a\n"
        "IA nao produziu resposta (chave ausente, chave recusada, limite,\n"
        "queda, formato ilegivel), tambem com a frase em portugues. Nada e\n"
        "gravado em nenhum dos dois casos."
    ),
)
def check_lesson(
    request,
    curso: str,
    numero: str,
    site_id: str,
    parte: ParteDoCurso | None = None,
    modo: ModoDeConferencia = ModoDeConferencia.COERENCIA,
):
    aula = _aula_do_curso(_curso(site_id, curso), numero, parte)
    if modo is ModoDeConferencia.FIDELIDADE:
        defeitos = _conferir_a_fidelidade(aula)
    else:
        defeitos = coerencia.conferir(aula)
    return [
        {
            "codigo": defeito.codigo,
            "peca": defeito.peca,
            "alvo": defeito.alvo,
            "frase": defeito.frase,
            "o_que_fazer": defeito.o_que_fazer,
            "impede_publicar": defeito.impede_publicar,
        }
        for defeito in defeitos
    ]


def _conferir_a_fidelidade(aula: AulaModel) -> list:
    """O Guardião, com as duas recusas dele traduzidas em HTTP.

    A separação é de responsabilidade, e não de gosto: o domínio sabe o que
    houve e diz isso em português; só aqui se sabe que "a encomenda não tem o
    que conferir" é 422 (o pedido está bem formado, o dado é que não dá) e que
    "a IA não respondeu" é 503 (tente de novo mais tarde). A frase viaja
    intacta nos dois casos, porque quem a lê é a professora, na tela do editor.
    """
    try:
        return fidelidade.conferir(aula)
    except fidelidade.ConferenciaImpossivel as motivo:
        raise HttpError(422, str(motivo)) from motivo
    except fidelidade.AgenteIndisponivel as motivo:
        raise HttpError(503, str(motivo)) from motivo


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
        "`letra` e a do bloco, de A a Z, e `curso` e o SLUG, resolvido pelo par\n"
        "site+slug como nas quatro operacoes de aula. Letra, ordem e parte NAO\n"
        "entram no corpo: sao estrutura, a fonte delas e o semeador (no curso\n"
        "do livro) ou `putCourseStructure` (em qualquer curso), e manda-las e\n"
        "422, do mesmo jeito que `cartao` em `putInstrument`.\n"
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


# ---------------------------------------------------------------------------
# O CURSO E A ESTRUTURA DELE (TAR-266, 07/09/2026)
# ---------------------------------------------------------------------------
# A sala serve vários cursos, e cada um nasce na tela do Admin, com o seu
# produto, a sua regra de avanço e a sua estrutura. Estas quatro operações são
# a porta por onde isso entra. A estrutura do curso do livro continua vindo do
# semeador; a de qualquer outro curso vem por `putCourseStructure`, que faz a
# MESMA reconciliação: escreve estrutura, nunca toca obra.


def _curso_inteiro(curso: CursoModel) -> dict[str, Any]:
    aulas = AulaModel.objects.filter(curso=curso)
    return {
        "slug": curso.slug,
        "nome": curso.nome,
        "estado": curso.estado,
        "progressao": curso.progressao,
        "produto_id": curso.produto_id,
        "total_de_aulas": aulas.count(),
        "aulas_publicadas": aulas.filter(estado=AulaModel.Estado.PUBLICADA).count(),
    }


def _estrutura(curso: CursoModel) -> list[dict[str, Any]]:
    aulas_por_bloco: dict[int, list[dict[str, Any]]] = {}
    for aula in (
        AulaModel.objects.filter(curso=curso).select_related("bloco").order_by("ordem")
    ):
        aulas_por_bloco.setdefault(aula.bloco_id, []).append(_linha(aula))
    return [
        {**_bloco(bloco), "aulas": aulas_por_bloco.get(bloco.id, [])}
        for bloco in BlocoModel.objects.filter(curso=curso).order_by("ordem")
    ]


def _reconciliar_estrutura(
    curso: CursoModel, payload: EstruturaParaGravarSchema
) -> dict[str, Any]:
    """A mesma fronteira do `semear_esqueleto`: cria o que falta, corrige
    bloco, ordem, parte, `e_boss` e `banca_nivel` do que existe, e não toca em
    obra. Uma transação só: ou a estrutura inteira entra, ou nada entra, e a
    conferência do rastro de aluno mora dentro dela.

    O NOME DO BLOCO É ESTRUTURA, O TÍTULO DA AULA É OBRA. As aulas casam pelo
    número, que é estável, e o título só preenche a que ainda não tem um. Os
    blocos casam pela letra, que é posicional: o bloco que era o B vira o C
    quando nasce um na frente, e o nome tem de vir na estrutura nova para
    acompanhá-lo. Por isso `nome` e `boss_titulo` do bloco são gravados como
    vieram (nulo não mexe, texto grava, vazio apaga), e a regra antiga, "só
    onde está vazio", apagava em silêncio o nome de todo bloco que mudava de
    letra.

    A ORDEM DAS AULAS É ESTACIONADA ANTES DE SER REESCRITA. `uma_ordem_por_aula_
    por_curso` é conferida linha a linha, e trocar duas aulas de lugar colide
    na primeira gravação. Todas as aulas do curso sobem para acima do maior
    valor que a estrutura nova vai usar, e cada uma desce para a posição
    final: nenhuma gravação encontra outra linha na posição. O bloco não tem
    essa faixa livre (a ordem é 1..26), e por isso a unicidade dele é adiada
    para o `COMMIT` (`apps/cursos/models.py`, `Bloco`).
    """
    letras_novas = [bloco.letra for bloco in payload.blocos]
    numeros_novos = [aula.numero for bloco in payload.blocos for aula in bloco.aulas]

    with transaction.atomic():
        existentes = {
            aula.numero: aula for aula in AulaModel.objects.filter(curso=curso)
        }
        somem = [numero for numero in existentes if numero not in numeros_novos]
        # O rastro de aluno é o que impede apagar: progresso, envio ou registro
        # de pausa. A conferência mora DENTRO da transação que apaga, com as
        # aulas candidatas trancadas: a chave estrangeira do rastro precisa da
        # linha da aula no COMMIT do aluno, então quem estiver gravando rastro
        # numa candidata espera a transação acabar, e rastro nenhum fica
        # apontando para aula apagada. Fora da transação havia uma janela
        # entre a conferência e o apagar, e a porta morria em 500 dentro dela.
        candidatas = list(
            AulaModel.objects.select_for_update().filter(curso=curso, numero__in=somem)
        )
        com_aluno = sorted(
            AulaModel.objects.filter(pk__in=[aula.pk for aula in candidatas])
            .filter(
                Q(progressos__isnull=False)
                | Q(envios__isnull=False)
                | Q(pausas__registros__isnull=False)
            )
            .values_list("numero", flat=True)
            .distinct()
        )
        if com_aluno:
            raise HttpError(
                422,
                f"as aulas {', '.join(com_aluno)} sumiram da estrutura nova, mas "
                "algum aluno já passou por elas (progresso, envio ou registro de "
                "pausa) e elas não podem ser apagadas. Devolva-as à estrutura, em "
                "qualquer bloco e posição, e mande de novo. Nada foi gravado.",
            )

        maior_ordem = max((aula.ordem for aula in existentes.values()), default=-1)
        deslocamento = max(maior_ordem, len(numeros_novos)) + 1
        AulaModel.objects.filter(curso=curso).update(ordem=F("ordem") + deslocamento)

        blocos_por_letra = {
            bloco.letra: bloco for bloco in BlocoModel.objects.filter(curso=curso)
        }
        blocos_criados = 0
        for posicao, bloco_novo in enumerate(payload.blocos, start=1):
            bloco = blocos_por_letra.get(bloco_novo.letra)
            if bloco is None:
                blocos_por_letra[bloco_novo.letra] = BlocoModel.objects.create(
                    curso=curso,
                    ordem=posicao,
                    letra=bloco_novo.letra,
                    parte=int(bloco_novo.parte),
                    nome=bloco_novo.nome or "",
                    boss_titulo=bloco_novo.boss_titulo or "",
                )
                blocos_criados += 1
                continue
            bloco.ordem = posicao
            bloco.parte = int(bloco_novo.parte)
            campos = ["ordem", "parte"]
            # A estrutura é a fonte dos dois textos do bloco (as letras são
            # posicionais, e o nome viaja com a posição): nulo não mexe, texto
            # grava, e texto vazio apaga.
            if bloco_novo.nome is not None:
                bloco.nome = bloco_novo.nome
                campos.append("nome")
            if bloco_novo.boss_titulo is not None:
                bloco.boss_titulo = bloco_novo.boss_titulo
                campos.append("boss_titulo")
            bloco.save(update_fields=campos)

        aulas_criadas = aulas_preservadas = 0
        ordem = 0
        for bloco_novo in payload.blocos:
            bloco = blocos_por_letra[bloco_novo.letra]
            for aula_nova in bloco_novo.aulas:
                aula = existentes.get(aula_nova.numero)
                if aula is None:
                    AulaModel.objects.create(
                        curso=curso,
                        bloco=bloco,
                        ordem=ordem,
                        numero=aula_nova.numero,
                        titulo_exibido=aula_nova.titulo,
                        e_boss=aula_nova.e_boss,
                        banca_nivel=aula_nova.banca_nivel,
                    )
                    aulas_criadas += 1
                else:
                    aula.bloco = bloco
                    aula.ordem = ordem
                    aula.e_boss = aula_nova.e_boss
                    aula.banca_nivel = aula_nova.banca_nivel
                    campos = ["bloco", "ordem", "e_boss", "banca_nivel"]
                    if not aula.titulo_exibido:
                        aula.titulo_exibido = aula_nova.titulo
                        campos.append("titulo_exibido")
                    aula.save(update_fields=campos)
                    aulas_preservadas += 1
                ordem += 1

        apagar = AulaModel.objects.filter(curso=curso, numero__in=somem)
        PecaModel.objects.filter(aula__in=apagar).delete()
        PausaModel.objects.filter(aula__in=apagar).delete()
        apagar.delete()
        BlocoModel.objects.filter(curso=curso).exclude(letra__in=letras_novas).delete()

    return {
        "blocos": _estrutura(curso),
        "blocos_criados": blocos_criados,
        "aulas_criadas": aulas_criadas,
        "aulas_preservadas": aulas_preservadas,
        "aulas_apagadas": len(somem),
    }


@router.get(
    "/cursos",
    response=list[CursoSchema],
    operation_id="listCourses",
    summary="Os cursos de um site, em ordem de apelido",
    description=(
        "A lista que a tela de cursos do Admin mostra: apelido, nome, estado,\n"
        "regra de avanco, o produto do catalogo a que cada curso aponta (texto\n"
        "vazio enquanto ninguem apontar) e duas contagens, o total de aulas e\n"
        "quantas estao publicadas. Em ordem de apelido, que e a ordem em que o\n"
        "aluno le. Site sem curso responde lista vazia, nao erro.\n"
        "\n"
        "`site_id` e obrigatorio (uma fabrica, N lojas): esta celula nao tem\n"
        "middleware de site, e a porta nao adivinha de qual escola e o curso."
    ),
)
def list_courses(request, site_id: str):
    return [_curso_inteiro(curso) for curso in enderecos.cursos_do_site(site_id)]


@router.post(
    "/cursos",
    response={201: CursoSchema},
    operation_id="createCourse",
    summary="Cria um curso: apelido, nome, regra de avanco e, se ja houver, o produto",
    description=(
        "O gesto Novo curso da tela do Admin. O curso nasce em rascunho, sem\n"
        "bloco e sem aula: a estrutura entra depois por `putCourseStructure`,\n"
        "e o texto de cada aula por `putLesson`. Nunca por arquivo, nunca por\n"
        "migracao ([INV-CUR-C2]).\n"
        "\n"
        "`slug` e o apelido do endereco (`/cursos/<slug>/`): minusculas,\n"
        "digitos e hifen, de 1 a 64 letras, e fora disso e 422. E o unico\n"
        "campo que nao muda depois, porque e a identidade do curso no par\n"
        "site+slug. Apelido que ja existe naquele site e 409 com a frase em\n"
        "portugues; o mesmo apelido em outro site e outro curso.\n"
        "\n"
        "`nome` vazio e 422. `progressao` e `por_laudo` (a regra do livro: a\n"
        "proxima aula abre com o laudo da professora) ou `livre` (a proxima\n"
        "abre quando o aluno conclui a anterior), e nasce `por_laudo` quando\n"
        "nao vem. `produto_id` e o id do produto no catalogo, o mesmo que a\n"
        "matricula guarda; vazio significa ainda nao apontado, e curso sem\n"
        "produto fecha a sala para todo mundo, de proposito. Chave que a\n"
        "porta nao conhece e 422.\n"
        "\n"
        "Responde 201 com o curso como ficou, no formato de `listCourses`."
    ),
)
def create_course(request, site_id: str, payload: CursoParaCriarSchema):
    try:
        with transaction.atomic():
            curso = CursoModel.objects.create(
                site_id=site_id,
                slug=payload.slug,
                nome=payload.nome,
                progressao=payload.progressao.value,
                produto_id=payload.produto_id,
            )
    except IntegrityError:
        # `um_curso_por_slug_por_site`: a unicidade e do banco, e a recusa e
        # mecanica mesmo com dois pedidos ao mesmo tempo.
        raise HttpError(
            409,
            f"já existe um curso com o apelido '{payload.slug}' no site "
            f"'{site_id}'. Escolha outro apelido, ou altere aquele curso por "
            "putCourse.",
        )
    return 201, _curso_inteiro(curso)


@router.put(
    "/cursos/{curso}",
    response=CursoSchema,
    operation_id="putCourse",
    summary="Altera o nome, a regra de avanco ou o produto de um curso",
    description=(
        "Os tres campos que mudam depois de o curso nascer, todos opcionais:\n"
        "AUSENTE OU NULO SIGNIFICA NAO MEXER, a mesma regra do `titulo_exibido`\n"
        "em `putLesson`. Corpo vazio devolve o curso como esta, sem gravar.\n"
        "\n"
        "`nome` vazio e 422. `progressao` e `por_laudo` ou `livre`, e trocar a\n"
        "regra de um curso muda como a proxima aula abre para TODOS os alunos\n"
        "dele. `produto_id` e o elo com a matricula: troca-lo troca QUEM ENTRA\n"
        "no curso, e texto vazio desaponta o produto e fecha a sala. E o mesmo\n"
        "gesto do comando `apontar_o_produto_do_curso`, pela porta; o comando\n"
        "continua existindo.\n"
        "\n"
        "O apelido, o estado e a versao NAO entram, e manda-los e 422: o apelido\n"
        "e a identidade do curso, e o estado e a versao sao da publicacao.\n"
        "404 se o curso nao existe naquele site. Devolve o curso como ficou."
    ),
)
def put_course(request, curso: str, site_id: str, payload: CursoParaAlterarSchema):
    encontrado = _curso(site_id, curso)
    campos = []
    if payload.nome is not None:
        encontrado.nome = payload.nome
        campos.append("nome")
    if payload.progressao is not None:
        encontrado.progressao = payload.progressao.value
        campos.append("progressao")
    if payload.produto_id is not None:
        encontrado.produto_id = payload.produto_id
        campos.append("produto_id")
    if campos:
        encontrado.save(update_fields=campos)
    return _curso_inteiro(encontrado)


@router.put(
    "/cursos/{curso}/estrutura",
    response=EstruturaSchema,
    operation_id="putCourseStructure",
    summary="Grava a estrutura de um curso: os blocos e as aulas, reconciliando com o que existe",
    description=(
        "O gesto Importar da tela de estrutura do Admin. O corpo e a lista de\n"
        "blocos na ordem, cada um com letra (A a Z), parte (1, 2 ou 3), as\n"
        "aulas na ordem e, se quiser, o nome do bloco e o titulo do Boss; cada\n"
        "aula leva numero (de 1 a 3 letras maiusculas ou digitos), titulo, se e\n"
        "Boss e o nivel de Banca. A ordem dos blocos e a posicao na lista, de\n"
        "um; a das aulas e a posicao no curso inteiro, do zero.\n"
        "\n"
        "RECONCILIA COMO O SEMEADOR DO LIVRO, e a fronteira e a mesma. Cria o\n"
        "bloco e a aula que faltam; corrige bloco, ordem, parte, Boss e Banca\n"
        "do que ja existe; e NUNCA toca obra: pedido, cliente, pecas, pausas,\n"
        "quiz, video, estado e versao ficam como estao. As aulas casam pelo\n"
        "NUMERO, que e estavel: o titulo da aula so entra onde esta VAZIO, o\n"
        "que a tela ja escreveu nao se sobrescreve, e `aulas_preservadas` diz\n"
        "quantas aulas ja existiam e ficaram com a obra intacta.\n"
        "\n"
        "OS BLOCOS CASAM PELA LETRA, QUE E POSICIONAL, e por isso a estrutura\n"
        "e a fonte do nome do bloco e do titulo do Boss: quando nasce um bloco\n"
        "na frente, o que era o B vira o C, e o nome tem de vir na estrutura\n"
        "nova para acompanha-lo. Cada um dos dois campos tem tres estados.\n"
        "Ausente ou nulo: o que esta gravado fica como esta. Texto: passa a\n"
        "ser este, mesmo que o bloco ja tivesse outro. Texto vazio: apaga.\n"
        "Mande sempre o nome que a tela mostra, e nenhum bloco perde o nome\n"
        "quando muda de letra.\n"
        "\n"
        "Aula que sumiu da estrutura nova e APAGADA so se nenhum aluno passou\n"
        "por ela (sem progresso, sem envio, sem registro de pausa). A\n"
        "conferencia acontece DENTRO da transacao que apaga, com essas aulas\n"
        "trancadas: um aluno gravando rastro nelas no mesmo instante e visto,\n"
        "e nenhuma aula por onde alguem passou e apagada. Se algum passou, e\n"
        "422 nomeando as aulas, e NADA e gravado: a transacao e uma so. Bloco\n"
        "que sumiu e apagado depois que as aulas dele mudaram de bloco ou\n"
        "foram apagadas.\n"
        "\n"
        "422 tambem, dizendo a linha do problema: letra de bloco repetida,\n"
        "numero de aula repetido, estrutura sem bloco, bloco sem aula, parte\n"
        "fora de 1..3, numero fora do padrao, titulo vazio, chave desconhecida.\n"
        "404 se o curso nao existe naquele site.\n"
        "\n"
        "Devolve a estrutura como ficou (os blocos com as aulas, cada aula no\n"
        "formato da listagem) e as contagens: blocos_criados, aulas_criadas,\n"
        "aulas_preservadas e aulas_apagadas."
    ),
)
def put_course_structure(
    request, curso: str, site_id: str, payload: EstruturaParaGravarSchema
):
    return _reconciliar_estrutura(_curso(site_id, curso), payload)
