"""O dossiê em PDF do portfólio, montado NO SERVIDOR (degrau 14, AC-16).

ci:texto-publicado

A MARCA ACIMA LIGA O PORTÃO DO TRAVESSÃO neste arquivo inteiro
(`ci/travessao.py`), pelo mesmo motivo do `vitrine.py` e do `semaforo.py` ao
lado: as frases daqui saem impressas num arquivo que o aluno anexa a um e-mail
para um cliente pagante, e elas não moram numa `templates/` nem num rótulo de
`TextChoices`, que são as duas regras que pegam sozinhas.

Lei: `docs/changespecs/CS-PAGES-0001.md`, critério AC-16, e
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §5 (degrau 14) e §7.

POR QUE UM ARQUIVO, E NÃO SÓ A VITRINE
----------------------------------------
A vitrine do degrau 13 é o LINK que o aluno manda no chat. Alguns clientes não
querem link: querem o anexo que dá para guardar, encaminhar, imprimir e levar a
uma reunião. É a mesma obra, na mesma ordem, em outro formato.

**E é a MESMA consulta.** Quem escolhe as obras é `vitrine.obras`, e este
módulo nunca escreve uma segunda: o cliente do aluno recebe o link e o anexo, e
duas listas livres para divergir seriam a escola desmentindo o próprio aluno na
frente de quem paga. O guarda disso vive em `tests/test_o_dossie_em_pdf.py`, e
compara a página pública com o arquivo, obra por obra.

POR QUE O ARQUIVO SE ESCREVE AQUI, EM VEZ DE VIR DE UMA BIBLIOTECA
--------------------------------------------------------------------
Medido em 06/09/2026, antes de decidir: nenhuma das treze células desta
plataforma gera PDF, e não há biblioteca de PDF em nenhum `requirements.txt`.
Então a escolha era entre trazer um motor de diagramação para compor duas
folhas de TEXTO, ou escrever as duas folhas.

O dossiê é texto: título, selo, e uma linha numerada por obra com o endereço
dela. As imagens continuam do outro lado do link, porque a foto entra por link
colado e esta casa nunca guarda arquivo (plano §6.2, e a constituição da
célula); baixar o render de cada aluno para dentro do nosso servidor a cada
dossiê seria uma decisão nova, de segurança e de disco, que ninguém pediu neste
degrau. Sem imagem, o que sobra é posicionar linhas de texto numa folha, e é
isso que este módulo faz abaixo: sem dependência nova, sem uma versão a mais
para acompanhar, e sem uma segunda ideia de "como se desenha uma página" dentro
da célula.

**Em troca, o arquivo é o mesmo em toda máquina**, e é isso que faz o AC-16
(montado no servidor) valer alguma coisa: não há data de criação, não há
identificador sorteado e não há compressão. O mesmo portfólio produz os mesmos
bytes em qualquer lugar, e o guarda disso é
`test_baixar_duas_vezes_da_o_mesmo_arquivo_byte_a_byte`. De quebra, o texto
fica legível dentro do arquivo, e é assim que os guardas o leem de FORA, sem
perguntar nada a este módulo.

A MONTAGEM NÃO É TRABALHO PESADO, E ISSO FOI MEDIDO
-----------------------------------------------------
O despacho deste degrau lembra que trabalho pesado não roda dentro do ciclo da
requisição. Aqui não há rede, não há disco e não há imagem: montar o dossiê de
trinta e nove obras leva menos de dois milésimos de segundo, contra os cinco
SEGUNDOS de teto que uma única batida em endereço de terceiro custaria
(`conferencia_do_link.TIMEOUT`). O que tornaria esta montagem pesada seria
justamente puxar as imagens, e é o que ela não faz.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable, Sequence

from django.utils import timezone

# ---------------------------------------------------------------------------
# AS FRASES QUE O CLIENTE DO ALUNO LÊ
# ---------------------------------------------------------------------------
# Nenhuma delas identifica a pessoa (critério AC-14, plano §7): o arquivo vai
# para as mesmas mãos que a página pública, e cala exatamente as mesmas coisas.

SEM_APELIDO = "Portfólio de modelagem 3D"

SUBTITULO = "Portfólio de modelagem 3D."

OBRA_SEM_LEGENDA = "Obra sem legenda"

EM_DESTAQUE = "Em destaque"

ASSINATURA = "Meshcraft Academy, a escola de modelagem 3D para Roblox."

#: O segundo parágrafo do selo, e ele é obrigação escrita, não enfeite: a foto
#: mora num site que a escola não controla (plano §6.2), então o selo vale para
#: o que o monitor viu no dia. Prometer mais seria uma promessa que a escola
#: não pode cumprir, levada por um aluno a um cliente pagante.
ALCANCE_DO_SELO = (
    "Uma pessoa da equipe da Meshcraft Academy abriu estas obras e conferiu o "
    "portfólio nessa data. O selo vale para o que ela viu no dia."
)


#: A recusa que a estante mostra quando não há o que pôr no arquivo. Um dossiê
#: com o título e nenhuma obra, anexado a um e-mail para um cliente pagante,
#: seria pior do que não existir botão nenhum.
SEM_OBRAS = (
    "O dossiê é o arquivo com as suas obras, e você ainda não tem nenhuma obra "
    "pronta para entrar nele. Guarde uma peça com um endereço que abre, aqui "
    "em cima, e o arquivo fica pronto na hora."
)


def frase_do_selo(dia: str) -> str:
    return f"Conferido pela escola em {dia}."


# ---------------------------------------------------------------------------
# A FOLHA
# ---------------------------------------------------------------------------
# A4 em pontos, que é a unidade do PDF. Os números estão por extenso, e não
# saem de uma conta a partir de milímetros: a folha não muda, e a conta só
# esconderia o valor de quem lê.

LARGURA_DA_FOLHA = 595.28
ALTURA_DA_FOLHA = 841.89
MARGEM = 56.7  # dois centímetros
COLUNA = LARGURA_DA_FOLHA - 2 * MARGEM
TOPO = ALTURA_DA_FOLHA - MARGEM

#: Onde o corpo do texto para. Abaixo daqui é a faixa do rodapé, e uma linha de
#: obra invadindo essa faixa sairia colada na assinatura da escola.
PISO = MARGEM + 26

ENTRELINHA = 1.35

TAMANHO_DO_TITULO = 24.0
TAMANHO_DO_SUBTITULO = 10.0
TAMANHO_DO_SELO = 11.0
TAMANHO_DA_OBRA = 13.0
TAMANHO_MIUDO = 9.0
TAMANHO_DO_RODAPE = 8.0


@dataclass(frozen=True)
class Linha:
    """Uma linha de texto na folha, e o endereço que ela abre quando é clicada."""

    texto: str
    tamanho: float
    antes: float = 0.0
    link: str = ""

    @property
    def altura(self) -> float:
        return self.antes + self.tamanho * ENTRELINHA


# ---------------------------------------------------------------------------
# A LARGURA DE CADA LETRA
# ---------------------------------------------------------------------------
# A Helvetica é uma das catorze fontes que todo leitor de PDF já tem, então o
# arquivo não carrega fonte nenhuma dentro dele. O preço é este: quem quebra a
# linha somos nós, e para isso é preciso saber quanto cada letra ocupa.
#
# Os números são os da tabela da Adobe, em milésimos do tamanho da fonte.
# **Letra com acento tem a largura da letra sem acento**, o que é verdade nessa
# tabela e é o que dispensa aqui uma segunda tabela só para o português.

_LARGURAS = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667,
    "'": 191, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278, "0": 556, "1": 556, "2": 556, "3": 556, "4": 556,
    "5": 556, "6": 556, "7": 556, "8": 556, "9": 556, ":": 278, ";": 278,
    "<": 584, "=": 584, ">": 584, "?": 556, "@": 1015, "A": 667, "B": 667,
    "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278,
    "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667,
    "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944,
    "X": 667, "Y": 667, "Z": 611, "[": 278, "\\": 278, "]": 278, "^": 469,
    "_": 556, "`": 333, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556,
    "f": 278, "g": 556, "h": 556, "i": 222, "j": 222, "k": 500, "l": 222,
    "m": 833, "n": 556, "o": 556, "p": 556, "q": 556, "r": 333, "s": 500,
    "t": 278, "u": 556, "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
    "{": 334, "|": 260, "}": 334, "~": 584,
}  # fmt: skip

#: A largura de quem não está na tabela. É a da letra minúscula mais comum, e
#: não zero: uma letra desconhecida contada como zero encolheria a conta da
#: linha inteira e a faria estourar a margem em silêncio.
_LARGURA_DESCONHECIDA = 556


def largura(texto: str, tamanho: float) -> float:
    """Quanto este texto ocupa na folha, em pontos."""
    total = 0
    for letra in texto:
        sem_acento = unicodedata.normalize("NFD", letra)[0]
        total += _LARGURAS.get(sem_acento, _LARGURA_DESCONHECIDA)
    return total * tamanho / 1000


def legivel(texto: str) -> str:
    """O que a fonte do arquivo sabe desenhar, e nada além disso.

    A legenda é escrita pelo aluno, e ele pode digitar o que quiser. O que a
    Helvetica não tem sai FORA, em vez de virar um losango preto no meio da
    frase: num arquivo que vai para um cliente pagante, esse losango pareceria
    defeito da obra dele. Acento e cedilha ficam, que é o que importa em
    português.
    """
    return (texto or "").encode("cp1252", "ignore").decode("cp1252")


def quebrar(texto: str, tamanho: float, *, limite: float = COLUNA) -> list[str]:
    """O texto em linhas que cabem na coluna, sem cortar palavra pelo meio.

    **A palavra que sozinha não cabe é partida na letra**, e essa é a exceção
    que existe por causa dos endereços: um link de duzentas letras sem espaço
    nenhum, deixado inteiro, sairia por cima da margem e ninguém veria o fim
    dele.
    """
    linhas: list[str] = []
    atual = ""
    for palavra in (texto or "").split():
        tentativa = f"{atual} {palavra}".strip()
        if atual and largura(tentativa, tamanho) > limite:
            linhas.append(atual)
            atual = ""
            tentativa = palavra
        while largura(tentativa, tamanho) > limite and len(tentativa) > 1:
            cabem = len(tentativa) - 1
            while cabem > 1 and largura(tentativa[:cabem], tamanho) > limite:
                cabem -= 1
            linhas.append(tentativa[:cabem])
            tentativa = tentativa[cabem:]
        atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas or [""]


# ---------------------------------------------------------------------------
# O QUE O DOSSIÊ DIZ
# ---------------------------------------------------------------------------


def _bloco(
    texto: str, tamanho: float, *, antes: float = 0.0, link: str = ""
) -> list[Linha]:
    partes = quebrar(legivel(texto), tamanho)
    return [
        Linha(parte, tamanho, antes if numero == 0 else 0.0, link)
        for numero, parte in enumerate(partes)
    ]


def _blocos(*, apelido: str, selo_em, obras: Sequence) -> list[list[Linha]]:
    """O documento inteiro, em blocos que não se partem entre duas folhas.

    Cada obra é UM bloco de propósito: o número, a legenda e o endereço dela
    separados por uma quebra de página fariam o cliente ler um endereço sem
    saber de que peça ele é.
    """
    abertura = _bloco(apelido or SEM_APELIDO, TAMANHO_DO_TITULO)
    if apelido:
        abertura += _bloco(SUBTITULO, TAMANHO_DO_SUBTITULO, antes=6)

    blocos = [abertura]

    if selo_em is not None:
        dia = timezone.localtime(selo_em).strftime("%d/%m/%Y")
        blocos.append(
            _bloco(frase_do_selo(dia), TAMANHO_DO_SELO, antes=22)
            + _bloco(ALCANCE_DO_SELO, TAMANHO_MIUDO, antes=4)
        )

    for numero, obra in enumerate(obras, start=1):
        titulo = f"{numero}. {obra.legenda or OBRA_SEM_LEGENDA}"
        bloco = _bloco(titulo, TAMANHO_DA_OBRA, antes=26)
        if obra.destaque:
            bloco += _bloco(EM_DESTAQUE, TAMANHO_MIUDO, antes=2)
        bloco += _bloco(obra.link, TAMANHO_MIUDO, antes=2, link=obra.link)
        blocos.append(bloco)

    return blocos


def _paginar(blocos: Iterable[list[Linha]]) -> list[list[tuple[float, Linha]]]:
    """Os blocos distribuídos pelas folhas, cada linha com a altura em que cai."""
    paginas: list[list[tuple[float, Linha]]] = []
    atual: list[tuple[float, Linha]] = []
    y = TOPO

    for bloco in blocos:
        altura = sum(linha.altura for linha in bloco)
        if atual and y - altura < PISO and altura <= TOPO - PISO:
            paginas.append(atual)
            atual, y = [], TOPO
        for linha in bloco:
            y -= linha.altura
            if y < PISO:
                paginas.append(atual)
                atual, y = [], TOPO - linha.altura
            atual.append((y, linha))

    paginas.append(atual)
    return paginas


# ---------------------------------------------------------------------------
# O ARQUIVO
# ---------------------------------------------------------------------------
# Um PDF é uma lista de objetos numerados, uma tabela dizendo em que byte cada
# um começa, e um fecho apontando para essa tabela. Nada aqui é comprimido, e
# essa é a escolha que deixa o texto legível dentro do arquivo, para quem o
# audita de fora.


def _texto_do_pdf(texto: str) -> bytes:
    escapado = texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return escapado.encode("cp1252", "ignore")


def _numero(valor: float) -> bytes:
    return f"{valor:.2f}".encode()


def _desenhar(texto: str, tamanho: float, x: float, y: float) -> bytes:
    return b"/F1 %s Tf 1 0 0 1 %s %s Tm (%s) Tj" % (
        _numero(tamanho),
        _numero(x),
        _numero(y),
        _texto_do_pdf(texto),
    )


def _fluxo(pagina: list[tuple[float, Linha]], numero: int, de: int) -> bytes:
    """O desenho de uma folha: as linhas do corpo, e o rodapé da escola."""
    partes = [b"BT"]
    for y, linha in pagina:
        partes.append(_desenhar(linha.texto, linha.tamanho, MARGEM, y))

    contagem = f"página {numero} de {de}"
    partes.append(_desenhar(ASSINATURA, TAMANHO_DO_RODAPE, MARGEM, MARGEM))
    partes.append(
        _desenhar(
            contagem,
            TAMANHO_DO_RODAPE,
            MARGEM + COLUNA - largura(contagem, TAMANHO_DO_RODAPE),
            MARGEM,
        )
    )
    partes.append(b"ET")
    return b"\n".join(partes)


def _ancoras(pagina: list[tuple[float, Linha]]) -> list[bytes]:
    """As âncoras clicáveis desta folha, uma por linha que carrega endereço.

    Num anexo, o endereço só impresso obriga o cliente do aluno a digitá-lo à
    mão. A área que responde ao clique é a da própria linha, medida com a mesma
    tabela de larguras que quebrou o texto.
    """
    ancoras = []
    for y, linha in pagina:
        if not linha.link:
            continue
        ancoras.append(
            b"<< /Type /Annot /Subtype /Link /Border [0 0 0] "
            b"/Rect [%s %s %s %s] /A << /S /URI /URI (%s) >> >>"
            % (
                _numero(MARGEM),
                _numero(y - linha.tamanho * 0.25),
                _numero(MARGEM + largura(linha.texto, linha.tamanho)),
                _numero(y + linha.tamanho * 0.9),
                _texto_do_pdf(linha.link),
            )
        )
    return ancoras


def _arquivo(paginas: list[list[tuple[float, Linha]]]) -> bytes:
    """Os objetos, a tabela de posições e o fecho que aponta para ela."""
    quantas = len(paginas)
    filhas = b" ".join(b"%d 0 R" % (4 + 2 * i) for i in range(quantas))

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R /Lang (pt-BR) >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (filhas, quantas),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    for i, pagina in enumerate(paginas):
        fluxo = _fluxo(pagina, i + 1, quantas)
        objetos.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %s %s] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R "
            b"/Annots [%s] >>"
            % (
                _numero(LARGURA_DA_FOLHA),
                _numero(ALTURA_DA_FOLHA),
                5 + 2 * i,
                b" ".join(_ancoras(pagina)),
            )
        )
        objetos.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(fluxo), fluxo))

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posicoes = []
    for numero, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += b"%d 0 obj\n" % numero + corpo + b"\nendobj\n"

    tabela = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for posicao in posicoes:
        saida += b"%010d 00000 n \n" % posicao
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        tabela,
    )
    return bytes(saida)


def montar(*, apelido: str, selo_em, obras: Sequence) -> bytes:
    """O dossiê pronto para anexar, em bytes.

    `obras` chega de FORA, e sempre de `vitrine.obras`: é ela que decide o que
    entra e em que ordem, e este módulo não escolhe nada disso.
    """
    return _arquivo(_paginar(_blocos(apelido=apelido, selo_em=selo_em, obras=obras)))


def nome_do_arquivo(apelido: str) -> str:
    """Como o anexo se chama na caixa de entrada de quem o recebe.

    O apelido é o que o aluno escolheu mostrar, e é a única coisa desta casa que
    pode ir no nome do arquivo: e-mail, nome completo e o id dele estão fora
    (critério AC-14).
    """
    return f"portfolio-{apelido}.pdf" if apelido else "portfolio.pdf"
