"""`/admin/escola/<curso>/aulas/<numero>/capitulo/` — colar um capítulo inteiro
e ele virar as 16 peças daquela encomenda.

Os textos das 34 aulas já estão escritos (o mantenedor, em 06/09/2026). O que
falta não é gerar nada: é o CAMINHO DE ENTRADA. Encher uma encomenda a mão é
digitar 16 caixas, e 34 encomendas são 544 colagens. Esta tela recebe o
capítulo de uma vez, mostra o que reconheceu, e grava.

## Por que uma TELA, e não um arquivo no repositório

O capítulo é obra NÃO LANÇADA e este repositório é PÚBLICO (`armadilhas/331`).
Ele não entra aqui: nem como arquivo, nem como semente, nem dentro de um teste.
Entra por esta área de colar (ou pelo arquivo `.md`/`.txt` do computador dele),
e o que fica guardado é o resultado, na `cursos`, nunca o capítulo. **Esta tela
não guarda nada**, nem entre o PREVER e o IMPORTAR: o texto volta para a caixa
dentro da própria página. O teste desta tela usa um capítulo de MENTIRA, com a
mesma forma e assunto inventado.

## A regra que não se negocia: peça escrita nunca é sobrescrita

Peça vazia o importador preenche; peça que já tem texto ele preserva, **e diz
na prévia que preservou**. É a mesma lei da tela do sumário, e pelo mesmo
motivo: um importador que apaga o que ele escreveu perde meses de trabalho que
só existem naquele banco.

## As peças se casam pelo NOME, e só os títulos `##` são peça

No sumário do livro a peça vinha numerada, e casar pelo número resolvia tudo.
No capitulo colado não há número nenhum: há títulos de Markdown. E aí o nível do
título é a decisão que vale a tela inteira. **`##` é peça; `###` é subseção
DENTRO da peça.** O "Eu faço" do capítulo medido tem nove `###` dentro dele (as
seções 8.1 a 8.8 e a solução do erro produtivo): quebrar em `###` picaria a
maior peça do capítulo em nove pedaços, e esse é o defeito mais fácil de
cometer aqui. O `#` sozinho é o título da encomenda.

Os nomes não batem letra por letra com os do contrato, e a normalização
(minúsculas, sem acento, sem a cauda depois do travessão, sem parênteses,
singular e plural iguais) resolve quase todos. O que ela não alcança tem
APELIDO explícito em `APELIDOS`, com o capítulo de onde saiu escrito ao lado.
Uma tabela que se lê é melhor que uma regra esperta que ninguém consegue
prever.

**Peça que não casar NÃO é adivinhada.** Ela aparece na prévia como não
reconhecida, com o trecho à vista, e o texto vai para "o que não coube".
Adivinhar em silêncio é o único jeito de perder obra dele.

## Três títulos, uma peça só

A 16ª peça do contrato (`dicionario_cartao_respostas`) chega no capítulo em
TRÊS títulos separados, e nem seguidos: "Dicionário da Encomenda 08", "Cartão
de 1 página" e "Respostas", com o Marco de carreira e o Boss no meio. Eles são
juntados numa peça só, na ordem em que aparecem, e cada trecho guarda o próprio
título. A prévia diz de quantos trechos a peça foi montada: é a única costura
que este importador faz, e ele precisa ver que ela aconteceu.

## Quatro títulos que são reconhecidos e NÃO são peça

O Marco de carreira, o Boss, o Guia de Produção e a abertura do capítulo têm
nome próprio e destino conhecido: nenhum deles é peça. Se caíssem em "o que não
coube", todo capítulo abriria com um alarme falso, e alarme que toca sempre é
alarme que ninguém lê. Eles são listados à parte, dizendo por que ficaram de
fora. O Guia de Produção é o caso mais perigoso dos quatro: ele é a instrução
de como escrever os OUTROS capítulos, e importá-lo encheria uma peça com o
manual do autor.

## O "Aceito quando" e o Quiz têm forma medida, e por isso são lidos

São campos próprios da encomenda, e no capítulo eles vivem dentro das peças 9 e
14. As duas formas foram medidas no capítulo de 06/09/2026: o "Aceito quando" é
uma linha só, com os critérios separados por `·`; o Quiz é a marca `**Quiz**`
seguida de perguntas numeradas, e as respostas moram lá embaixo, na peça 16, em
`**Quiz.** (1) ... (2) ...`, casadas pelo número.

Fora dessas formas, nada é adivinhado: o campo continua vazio, o texto segue
inteiro dentro da peça, e a prévia diz que aconteceu isso. O contrato exige
`resposta_modelo` de pelo menos uma letra em todo item do quiz, então um quiz
com pergunta sem resposta não viaja: viajaria como 422, ou pior, como resposta
inventada.

## O que a porta ainda não aceita, e a prévia mostra assim mesmo

O título da encomenda, o subtítulo e o título do Boss estão no capítulo e não
têm campo em `putLesson` hoje. A porta para eles está sendo aberta na `cursos`
(TAR-221, PR #1233) enquanto esta tela nasce. Gravá-los agora seria escrever na
célula de outro robô; escondê-los seria pior. Eles aparecem na prévia com a
frase que diz por que não entraram e quando entram.

## O número do capítulo confere a encomenda, e essa é a trava mais importante

São 34 capítulos parecidos, e importar o capítulo 8 dentro da encomenda 9 é o
pior acidente possível nesta tela: ele só descobriria semanas depois, lendo. O
título `# Encomenda 08` traz o número, e o IMPORTAR RECUSA quando ele não é o
da encomenda aberta. Capítulo sem essa linha não pode ser conferido: a prévia
diz isso com todas as letras, e a gravação segue.

Sem uma linha de script: a política de segurança desta área exige hash na CSP
para cada script embutido (`armadilhas/199`), e um POST por gesto deixa a tela
mostrando sempre o que está de fato gravado.
"""

from __future__ import annotations

import re
import unicodedata

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .aulas import (
    NOME_DA_PECA,
    PECAS,
    SEQUENCIA,
    SOB_DEMANDA,
    CursosClient,
    _endereco,
    _falha,
    _sem_site,
    _site_desta_requisicao,
)
from .views import _auditar

TELA = "admin/escola_capitulo.html"

#: As extensões que o envio aceita, as mesmas da Biblioteca do Livro. `.docx` e
#: `.pdf` ficam de fora de propósito: os dois são pacotes, não texto.
EXTENSOES = (".md", ".markdown", ".txt")

#: O maior capítulo que passa por aqui. O capítulo medido em 06/09/2026 pesa
#: 25 KB; um megabyte é folga de quarenta vezes. O número existe para a recusa
#: ser uma FRASE em português, e não o erro cru do Django quando o corpo do
#: POST estoura o teto da célula.
LIMITE_DE_BYTES = 1_000_000


# ---------------------------------------------------------------------------
# AS PALAVRAS — como um título vira uma peça
# ---------------------------------------------------------------------------
def _palavras(titulo: str) -> tuple:
    """O título reduzido às palavras que decidem, para comparar sem sustos.

    Tira, nesta ordem: os acentos, as maiúsculas, o que está entre parênteses
    ("Erro produtivo (antes da aula)"), a cauda depois do travessão ou dos
    dois-pontos ("Drill D15 — Do .blend ao Studio"), e a pontuação. Por fim
    iguala singular e plural, que é o que separa "Drill D15" de "Drills".

    O corte do plural só vale para palavra de mais de três letras: "nós" e
    "erros" precisam de tratamentos opostos, e o tamanho os separa.
    """
    sem_acento = "".join(
        letra
        for letra in unicodedata.normalize("NFKD", titulo)
        if not unicodedata.combining(letra)
    ).casefold()
    sem_parenteses = re.sub(r"\([^)]*\)", " ", sem_acento)
    sem_cauda = re.split(r"\s[—–―-]\s|:", sem_parenteses)[0]
    limpo = re.sub(r"[^a-z0-9]+", " ", sem_cauda)
    return tuple(
        palavra[:-1] if len(palavra) > 3 and palavra.endswith("s") else palavra
        for palavra in limpo.split()
    )


#: Os nomes que a normalização sozinha não alcança. Cada linha diz de qual
#: capítulo o apelido saiu, porque os outros 33 vão trazer mais e quem os
#: acrescentar precisa saber o que já foi visto de verdade.
#:
#: As chaves são escritas em português, como ele as escreve, e passam pelo
#: MESMO `_palavras` dos nomes do contrato. Escrever a forma já normalizada à
#: mão foi tentado e deu errado na primeira medição: "Boss" normaliza para
#: "bos" (o corte do plural), e ninguém acerta isso de cabeça.
APELIDOS = {
    # Encomenda 08: "## Regra que entra no Padrão Meshcraft — §Pacote". O
    # contrato chama a peça de "Regra do Padrão", e o "que entra no" fica bem
    # no meio das duas palavras que casariam.
    "Regra que entra no Padrão": "regra_do_padrao",
    # Encomenda 08: "## Crítica de atelier". O contrato escreve "ateliê", com
    # ê; ele escreve "atelier", à francesa. É a mesma peça, e a única
    # diferença é uma letra no fim.
    "Crítica de atelier": "critica_de_atelier",
    # Encomenda 08: a 16ª peça chega em três títulos separados e não seguidos
    # ("Dicionário da Encomenda 08", "Cartão de 1 página — Encomenda 08" e
    # "Respostas"), com o Marco de carreira e o Boss entre eles.
    "Dicionário": "dicionario_cartao_respostas",
    "Cartão de 1 página": "dicionario_cartao_respostas",
    "Respostas": "dicionario_cartao_respostas",
}

#: Os títulos que são RECONHECIDOS e não são peça. Sem esta lista eles cairiam
#: em "o que não coube" em todo capítulo, e um alarme que toca sempre é um
#: alarme que ninguém lê. Também em português, também pelo `_palavras`.
NAO_SAO_PECA = (
    (
        "Marco de carreira",
        "é da gamificação do curso, e não das 16 peças da encomenda.",
    ),
    (
        "Boss",
        "é o título do Boss do bloco, e ele aparece logo abaixo nesta prévia.",
    ),
    (
        "Guia de produção",
        "é a instrução de como escrever os capítulos, e nunca entra numa "
        "encomenda: importá-lo encheria uma peça com o manual do autor.",
    ),
)

#: As 16 da anatomia na ordem canônica do contrato, para a prévia numerar. São
#: as da categoria `SEQUENCIA`, e só elas.
PECAS_NUMERADAS = tuple(t for t, _, categoria in PECAS if categoria == SEQUENCIA)

#: Todo par (palavras, tipo) que o casamento tenta, com os apelidos por último.
#: As duas peças internas (`roteiro`, `guia_do_mentor`) entram: elas quase nunca
#: aparecem no capítulo, e quando aparecem pelo nome têm campo para onde ir.
#:
#: A VÍDEO-AULA EM TEXTO FICA DE FORA, e é o único tipo do contrato que fica.
#: Ela é um documento SEPARADO do capítulo (desenho do mantenedor, 06/09/2026):
#: o mesmo capítulo contado de outro jeito. Deixá-la entrar aqui faria o
#: importador de capítulo escrever a peça que ele não tem como conhecer, e um
#: título homônimo dentro do capítulo apagaria o texto da vídeo-aula que a
#: professora já tivesse escrito à mão.
_ALVOS = tuple(
    [
        (_palavras(nome), tipo)
        for tipo, nome, categoria in PECAS
        if categoria != SOB_DEMANDA
    ]
    + [(_palavras(apelido), tipo) for apelido, tipo in APELIDOS.items()]
)

#: O mesmo, para os títulos que não são peça.
_FORA_DA_ANATOMIA = tuple((_palavras(nome), motivo) for nome, motivo in NAO_SAO_PECA)


def _contem(agulha: tuple, palheiro: tuple) -> bool:
    """As palavras da agulha aparecem seguidas dentro do palheiro.

    Seguidas, e palavra inteira: é o que separa "Página do portfólio" de
    "Cartão de 1 página" sem precisar de uma lista de exceções.
    """
    return any(
        palheiro[i : i + len(agulha)] == agulha
        for i in range(len(palheiro) - len(agulha) + 1)
    )


def classificar(titulo: str) -> tuple:
    """O que este título `##` é. Devolve `(papel, tipo ou motivo)`.

    `("peca", tipo)` quando casa com uma das 18 do contrato; `("nao_e_peca",
    motivo)` para os títulos que têm nome e outro destino; `("desconhecida",
    "")` quando nada casa, que é o caso em que NADA é adivinhado.

    Quando mais de um nome casa, vence o mais específico (o de mais palavras).
    Empate entre tipos diferentes devolve desconhecida de propósito: é melhor
    ele decidir olhando o trecho do que a tela sortear uma peça.
    """
    palavras = _palavras(titulo)
    if not palavras:
        return "desconhecida", ""

    for nome, motivo in _FORA_DA_ANATOMIA:
        if _contem(nome, palavras):
            return "nao_e_peca", motivo

    casaram = [(len(nome), tipo) for nome, tipo in _ALVOS if _contem(nome, palavras)]
    if not casaram:
        return "desconhecida", ""
    maior = max(tamanho for tamanho, _ in casaram)
    tipos = {tipo for tamanho, tipo in casaram if tamanho == maior}
    if len(tipos) > 1:
        return "desconhecida", ""
    return "peca", tipos.pop()


def nomes_que_procuro() -> list:
    """Os 16 nomes de peça, em português, para a tela dizer o que ela procura.

    Ela só é chamada quando NADA foi reconhecido, e é a diferença entre "não
    achei nada" e uma tela que ensina o que era esperado.
    """
    return [NOME_DA_PECA[tipo] for tipo in PECAS_NUMERADAS]


# ---------------------------------------------------------------------------
# O INTERPRETADOR — capítulo para dentro, estrutura para fora
# ---------------------------------------------------------------------------
CABECALHO = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

#: A linha de régua do Markdown (`---`). Ela separa o fim do capítulo do Guia
#: de Produção e não é texto de peça nenhuma.
REGUA = re.compile(r"^\s*([-*_])\1{2,}\s*$")

#: `# Encomenda 08 — "Me manda pronto pra colocar no jogo."`
NUMERO_DA_ENCOMENDA = re.compile(r"encomenda\s+(\d{1,3})\b", re.IGNORECASE)
ENTRE_ASPAS = re.compile('["\u201c](.+?)["\u201d]')

#: `## Boss C — "O Kit do Aventureiro no jogo"`
LETRA_DO_BOSS = re.compile(r"\bboss\s+([a-z])\b", re.IGNORECASE)

#: `**Aceito quando:** zero avisos · Size correto · Pacote completo.`
ACEITO_QUANDO = re.compile(
    r"^\s*\*\*\s*aceito quando\s*:?\s*\*\*\s*:?\s*(.+?)\s*$", re.IGNORECASE
)
SEPARADOR_DE_CRITERIO = "·"

#: `**Quiz** (respostas no fim)` e, logo abaixo, `1. ...` até `5. ...`.
MARCA_DO_QUIZ = re.compile(r"^\s*\*\*\s*quiz\s*\*\*", re.IGNORECASE)
PERGUNTA_NUMERADA = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")

#: `**Quiz.** (1) Chega com o dobro... (2) Ele vira as faces...`
MARCA_DAS_RESPOSTAS = re.compile(
    r"^\s*\*\*\s*quiz\s*\.?\s*\*\*\s*(.+?)\s*$", re.IGNORECASE
)
RESPOSTA_NUMERADA = re.compile(r"\((\d{1,2})\)\s*")

#: O travessão em todas as formas que ele escreve, para cortar a cauda de um
#: título e para achar o que vem depois dele numa linha de Boss.
TRAVESSAO = r"\s[—–―-]\s"


def _sem_acento(texto: str) -> str:
    return "".join(
        letra
        for letra in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(letra)
    )


def _titulo_entre_aspas(linha: str) -> str:
    """O que está entre aspas, ou a frase depois do travessão, ou nada."""
    casou = ENTRE_ASPAS.search(linha)
    if casou:
        return casou.group(1).strip()
    depois = re.split(TRAVESSAO, linha, maxsplit=1)
    return depois[1].strip() if len(depois) > 1 else ""


def _juntar(linhas: list) -> str:
    return "\n".join(linhas).strip()


def interpretar(texto: str) -> dict:
    """O capítulo colado, em estrutura. Sem rede, sem banco, sem Django.

    Corta o texto nos títulos `##` e só neles: `###` e o que vier abaixo ficam
    dentro da peça aberta, as marcações de figura (`[FIGURA 8.1 ...]`) ficam
    intactas onde estão, e a régua `---` é descartada.
    """
    fragmentos: dict = {}
    nao_e_peca: list = []
    desconhecidas: list = []
    cabeca: dict = {"numero": "", "titulo": "", "subtitulo": "", "boss": None}
    abertura: list = []
    aberta: dict | None = None

    for linha in texto.replace("\r\n", "\n").split("\n"):
        casou = CABECALHO.match(linha)
        nivel = len(casou.group(1)) if casou else 0
        titulo = casou.group(2) if casou else ""

        if nivel == 1 and aberta is None and not cabeca["numero"]:
            numero = NUMERO_DA_ENCOMENDA.search(titulo)
            cabeca["numero"] = numero.group(1) if numero else ""
            cabeca["titulo"] = _titulo_entre_aspas(titulo)
            continue

        if nivel == 3 and aberta is None and not cabeca["subtitulo"]:
            cabeca["subtitulo"] = titulo
            continue

        if nivel == 2:
            aberta = {"titulo": titulo, "bruto": linha.rstrip(), "linhas": []}
            papel, o_que = classificar(titulo)
            if papel == "peca":
                fragmentos.setdefault(o_que, []).append(aberta)
            elif papel == "nao_e_peca":
                nao_e_peca.append(aberta | {"motivo": o_que})
                letra = LETRA_DO_BOSS.search(_sem_acento(titulo))
                if letra and cabeca["boss"] is None:
                    cabeca["boss"] = {
                        "letra": letra.group(1).upper(),
                        "titulo": _titulo_entre_aspas(titulo),
                    }
            else:
                desconhecidas.append(aberta)
            continue

        if REGUA.match(linha):
            continue

        (aberta["linhas"] if aberta is not None else abertura).append(linha)

    pecas = {
        tipo: {
            "texto": _montar(lista),
            "titulos": [f["titulo"] for f in lista],
            "trechos": len(lista),
        }
        for tipo, lista in fragmentos.items()
    }
    lido = {
        "numero": cabeca["numero"],
        "titulo": cabeca["titulo"],
        "subtitulo": cabeca["subtitulo"],
        "boss": cabeca["boss"],
        "abertura": _juntar(abertura),
        "pecas": pecas,
        "nao_e_peca": [
            {"titulo": f["titulo"], "motivo": f["motivo"]} for f in nao_e_peca
        ],
        "nao_reconhecidos": [
            {"titulo": f["titulo"], "trecho": _juntar(f["linhas"])}
            for f in desconhecidas
        ],
    }
    lido["aceito_quando"] = _criterios((pecas.get("voce_faz") or {}).get("texto", ""))
    lido["quiz"], lido["quiz_incompleto"] = _quiz(
        (pecas.get("checkpoint") or {}).get("texto", ""),
        (pecas.get("dicionario_cartao_respostas") or {}).get("texto", ""),
    )
    return lido


def _montar(lista: list) -> str:
    """O texto da peça: o corpo do trecho, ou os trechos com os títulos deles.

    Trecho único perde o título, porque o título vira a identidade da peça.
    Vários trechos guardam cada um o seu, exatamente como ele escreveu: sem
    eles ninguém saberia onde o Dicionário acaba e o Cartão começa.
    """
    if len(lista) == 1:
        return _juntar(lista[0]["linhas"])
    return "\n\n".join(
        f"{f['bruto']}\n\n{_juntar(f['linhas'])}".strip() for f in lista
    ).strip()


def _paragrafo(linhas: list, i: int) -> str:
    """A linha `i` mais as que vêm coladas nela, até a primeira linha em branco.

    O editor de texto dele quebra a linha para caber na largura da página, e
    uma linha quebrada continua sendo UMA frase. Ler só a primeira metade
    perderia o fim do "Aceito quando" e as últimas respostas do quiz, calado,
    que é o defeito que este importador existe para não cometer.
    """
    pedaco = [linhas[i].strip()]
    for adiante in linhas[i + 1 :]:
        if not adiante.strip():
            break
        pedaco.append(adiante.strip())
    return " ".join(pedaco)


def _criterios(texto_do_voce_faz: str) -> list:
    """Os critérios do parágrafo que abre com `**Aceito quando:**`, ou vazio.

    Fora desse parágrafo nada é lido: o "Aceito quando" segue dentro do texto
    da peça de qualquer jeito, então não há nada a perder por não adivinhar.
    """
    linhas = texto_do_voce_faz.split("\n")
    for i, linha in enumerate(linhas):
        if not ACEITO_QUANDO.match(linha):
            continue
        casou = ACEITO_QUANDO.match(_paragrafo(linhas, i))
        if not casou:
            continue
        itens = [
            item.strip()
            for item in casou.group(1).split(SEPARADOR_DE_CRITERIO)
            if item.strip()
        ]
        if itens:
            return itens
    return []


def _perguntas(texto_do_checkpoint: str) -> list:
    """As perguntas numeradas logo abaixo da marca `**Quiz**`.

    A numeração precisa vir de 1 em diante, sem buraco: é o que separa um quiz
    de qualquer outra lista numerada do capítulo (os "Erros clássicos" também
    são uma). Linha sem número COLADA numa pergunta é a continuação dela;
    depois de uma linha em branco, só um número na sequência continua o quiz,
    e é isso que impede o parágrafo seguinte de virar rabo da última pergunta.
    """
    linhas = texto_do_checkpoint.split("\n")
    for i, linha in enumerate(linhas):
        if not MARCA_DO_QUIZ.match(linha):
            continue
        perguntas: list = []
        colada = False
        for adiante in linhas[i + 1 :]:
            if not adiante.strip():
                colada = False
                continue
            casou = PERGUNTA_NUMERADA.match(adiante)
            if casou and int(casou.group(1)) == len(perguntas) + 1:
                perguntas.append(casou.group(2).strip())
                colada = True
                continue
            if colada:
                perguntas[-1] = f"{perguntas[-1]} {adiante.strip()}"
                continue
            if perguntas:
                break
        return perguntas
    return []


def _respostas(texto_da_16: str) -> dict:
    """As respostas do quiz por número, do parágrafo `**Quiz.** (1) ... (2) ...`."""
    linhas = texto_da_16.split("\n")
    for i, linha in enumerate(linhas):
        if not MARCA_DAS_RESPOSTAS.match(linha):
            continue
        casou = MARCA_DAS_RESPOSTAS.match(_paragrafo(linhas, i))
        if not casou:
            continue
        pedacos = RESPOSTA_NUMERADA.split(casou.group(1))
        respostas = {}
        for i in range(1, len(pedacos) - 1, 2):
            texto = pedacos[i + 1].strip()
            if texto:
                respostas[int(pedacos[i])] = texto
        if respostas:
            return respostas
    return {}


def _quiz(texto_do_checkpoint: str, texto_da_16: str) -> tuple:
    """`(quiz, incompleto)`. Pergunta sem resposta derruba o quiz inteiro.

    O contrato exige `resposta_modelo` de pelo menos uma letra em CADA item, e
    inventar resposta é o pior desfecho possível numa tela cuja única promessa
    é não mexer no texto dele. Sem o par completo o campo fica vazio, o texto
    continua dentro das peças 9 e 14, e a prévia diz exatamente isso.
    """
    perguntas = _perguntas(texto_do_checkpoint)
    if not perguntas:
        return [], False
    respostas = _respostas(texto_da_16)
    if not all(respostas.get(n + 1) for n in range(len(perguntas))):
        return [], True
    return [
        {"pergunta": pergunta, "resposta_modelo": respostas[n + 1]}
        for n, pergunta in enumerate(perguntas)
    ], False


# ---------------------------------------------------------------------------
# O CASAMENTO — o que seria preenchido, e o que ficaria como está
# ---------------------------------------------------------------------------
def _escrito(valor) -> bool:
    """Um campo conta como ESCRITO quando tem qualquer coisa além de espaço."""
    return bool(str(valor or "").strip())


def _rotulo(tipo: str, lido: dict) -> str:
    """ "Peça 7: Eu faço", e o nome que o capítulo usou quando ele difere."""
    do_contrato = NOME_DA_PECA.get(tipo, tipo)
    lidos = (lido["pecas"].get(tipo) or {}).get("titulos") or []
    diferentes = [nome for nome in lidos if nome.casefold() != do_contrato.casefold()]
    if diferentes:
        do_contrato = f"{do_contrato} (no capítulo: {', '.join(diferentes)})"
    if tipo in PECAS_NUMERADAS:
        return f"Peça {PECAS_NUMERADAS.index(tipo) + 1}: {do_contrato}"
    return do_contrato


def casar(lido: dict, aula: dict) -> dict:
    """O que o importador FARIA nesta encomenda, sem fazer nada.

    Devolve `preencher` (o que entra), `preservar` (o que já tem texto e fica
    intacto) e `corpo` (o corpo de `putLesson`, montado do que está gravado com
    só os vazios trocados). `corpo` é `None` quando nada mudaria, e é assim que
    importar duas vezes não sobe a versão sem trocar uma letra.
    """
    preencher: list = []
    preservar: list = []

    pecas = []
    for peca in aula.get("pecas") or []:
        if not isinstance(peca, dict):
            continue
        tipo = str(peca.get("tipo") or "")
        texto = str(peca.get("texto") or "")
        do_capitulo = (lido["pecas"].get(tipo) or {}).get("texto", "")
        if do_capitulo:
            rotulo = _rotulo(tipo, lido)
            if _escrito(texto):
                preservar.append({"campo": rotulo, "atual": texto})
            else:
                preencher.append(
                    {
                        "campo": rotulo,
                        "novo": do_capitulo,
                        "trechos": lido["pecas"][tipo]["trechos"],
                    }
                )
                texto = do_capitulo
        pecas.append({"tipo": tipo, "texto": texto})

    aceito = [str(c) for c in (aula.get("aceito_quando") or [])]
    if lido["aceito_quando"]:
        junta = f" {SEPARADOR_DE_CRITERIO} "
        if aceito:
            preservar.append({"campo": "Aceito quando", "atual": junta.join(aceito)})
        else:
            preencher.append(
                {
                    "campo": "Aceito quando",
                    "novo": junta.join(lido["aceito_quando"]),
                    "trechos": 1,
                }
            )
            aceito = lido["aceito_quando"]

    quiz = [q for q in (aula.get("quiz") or []) if isinstance(q, dict)]
    if lido["quiz"]:
        if quiz:
            preservar.append(
                {"campo": "Quiz", "atual": f"{len(quiz)} pergunta(s) já escritas."}
            )
        else:
            preencher.append(
                {
                    "campo": "Quiz",
                    "novo": "\n".join(
                        f"{n + 1}. {item['pergunta']}"
                        for n, item in enumerate(lido["quiz"])
                    ),
                    "trechos": 1,
                }
            )
            quiz = lido["quiz"]

    if not preencher:
        return {"preencher": [], "preservar": preservar, "corpo": None}

    return {
        "preencher": preencher,
        "preservar": preservar,
        # O corpo INTEIRO de `putLesson`, montado do que está gravado: a porta
        # substitui a encomenda toda, então o que não vem no corpo se perde.
        "corpo": {
            "pedido": str(aula.get("pedido") or ""),
            "cliente": str(aula.get("cliente") or ""),
            "instrumento": aula.get("instrumento") or None,
            "minimo": str(aula.get("minimo") or ""),
            "aceito_quando": aceito,
            "quiz": quiz,
            "video_url": str(aula.get("video_url") or ""),
            "e_boss": bool(aula.get("e_boss")),
            "banca_nivel": aula.get("banca_nivel"),
            "pecas": pecas,
            "pausas": [p for p in (aula.get("pausas") or []) if isinstance(p, dict)],
        },
    }


# ---------------------------------------------------------------------------
# A TELA
# ---------------------------------------------------------------------------
def _so_digitos(numero: str) -> str:
    """`E08`, `08` e `8` viram `8`: o número confere sem depender da forma."""
    digitos = re.sub(r"\D", "", numero or "")
    if not digitos:
        return ""
    return digitos.lstrip("0") or "0"


def _parte(parte) -> "int | None":
    return int(parte) if parte else None


def _desenhar(request, curso, parte, numero, colado, contexto, status=200):
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "curso": curso,
            "numero": numero,
            "colado": colado,
            "extensoes": ", ".join(EXTENSOES),
            "url_da_encomenda": _endereco("escola_aula", curso, parte, numero),
            "url_de_prever": _endereco("escola_capitulo_prever", curso, parte, numero),
            "url_de_importar": _endereco(
                "escola_capitulo_importar", curso, parte, numero
            ),
        }
        | contexto,
        status=status,
    )


def _texto_enviado(request) -> tuple:
    """`(texto, erro)`. O arquivo tem preferência sobre a caixa quando vem.

    Cada recusa NOMEIA o arquivo e diz o que fazer com ele. A codificação
    antiga do Windows é recusada em vez de adivinhada: adivinhar erra em
    silêncio, e o erro só aparece semanas depois num acento trocado no meio do
    capítulo.
    """
    arquivo = request.FILES.get("arquivo")
    if arquivo is not None:
        nome = arquivo.name or "sem-nome"
        if not nome.lower().endswith(EXTENSOES):
            return "", (
                f'O arquivo "{nome}" não é um arquivo de texto. Esta tela lê '
                f"{', '.join(EXTENSOES)}. Se o capítulo está no Word, salve como "
                "texto simples ou cole o conteúdo na caixa abaixo. Nada foi gravado."
            )
        if arquivo.size > LIMITE_DE_BYTES:
            return "", (
                f'O arquivo "{nome}" passa de um megabyte, e um capítulo não pesa '
                "isso. Confira se você escolheu o arquivo certo. Nada foi gravado."
            )
        try:
            conteudo = arquivo.read().decode("utf-8-sig").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return "", (
                f'Não consegui ler o arquivo "{nome}": ele está numa codificação '
                "antiga. Abra o arquivo, salve de novo escolhendo UTF-8, e mande "
                "outra vez. Nada foi gravado."
            )
        if not conteudo.strip():
            return "", (
                f'O arquivo "{nome}" está vazio. Escolha o arquivo do capítulo ou '
                "cole o texto na caixa abaixo. Nada foi gravado."
            )
        return conteudo, ""

    colado = (request.POST.get("capitulo") or "").replace("\r\n", "\n")
    if not colado.strip():
        return "", (
            "Cole o capítulo na caixa ou escolha um arquivo do seu computador "
            "antes de apertar o botão. Nada foi lido e nada foi gravado."
        )
    return colado, ""


def _preparar(request, curso, parte, numero):
    """A leitura que PREVER e IMPORTAR fazem igual.

    Devolve `(preparado, resposta)`: exatamente um dos dois é `None`. A
    resposta pronta é a própria tela, e existe quando não há o que fazer: sem
    site, sem texto, arquivo que não serve, capítulo em que nada foi
    reconhecido, ou a sala de aula fora do ar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return None, _sem_site(request)

    colado, erro = _texto_enviado(request)
    if erro:
        return None, _desenhar(
            request, curso, parte, numero, "", {"erro": erro}, status=400
        )

    lido = interpretar(colado)
    if not lido["pecas"]:
        return None, _desenhar(
            request,
            curso,
            parte,
            numero,
            colado,
            {
                "erro": (
                    "Não reconheci nenhuma peça neste texto. Cada peça começa com "
                    "um título de dois sustenidos, assim: ## O pedido. Confira se "
                    "você mandou o capítulo inteiro, e não um pedaço. Nada foi "
                    "gravado."
                ),
                "nomes_que_procuro": nomes_que_procuro(),
            },
            status=400,
        )

    desfecho, aula = CursosClient().aula(site["id"], curso, numero)
    if desfecho != CursosClient.OK:
        return None, _desenhar(
            request,
            curso,
            parte,
            numero,
            colado,
            {"falha_da_sala": _falha(desfecho)},
            status=503,
        )

    do_capitulo = _so_digitos(lido["numero"])
    return (
        site,
        colado,
        lido,
        casar(lido, aula or {}),
        {
            "capitulo": lido["numero"],
            "diferente": bool(do_capitulo) and do_capitulo != _so_digitos(numero),
            "sem_numero": not do_capitulo,
        },
    ), None


def _resumo(lido: dict, casamento: dict, conferencia: dict) -> dict:
    """O que a tela mostra. Contado na hora, nunca guardado.

    `montadas` é a única costura que este importador faz, e por isso ela é
    dita em voz alta: peça montada de mais de um trecho do capítulo, com os
    títulos na ordem em que foram juntados. `faltando` é o contrário, e serve
    ao mesmo olho: das 16, quais o capítulo não trouxe.
    """
    return {
        "lido": lido,
        "conferencia": conferencia,
        "preencher": casamento["preencher"],
        "preservar": casamento["preservar"],
        "reconhecidas": len(lido["pecas"]),
        "montadas": [
            {
                "campo": _rotulo(tipo, lido),
                "trechos": peca["trechos"],
                "titulos": peca["titulos"],
            }
            for tipo, peca in lido["pecas"].items()
            if peca["trechos"] > 1
        ],
        "faltando": [
            NOME_DA_PECA[tipo] for tipo in PECAS_NUMERADAS if tipo not in lido["pecas"]
        ],
    }


@require_GET
def capitulo(request, curso: str, numero: str, parte: "str | None" = None):
    """A área de colar, vazia. Nenhuma ida à porta: aqui ainda não há texto."""
    return _desenhar(request, curso, _parte(parte), numero, "", {})


@require_POST
def capitulo_prever(request, curso: str, numero: str, parte: "str | None" = None):
    """Lê o capítulo e mostra o que aconteceria. NÃO grava nada."""
    em = _parte(parte)
    preparado, resposta = _preparar(request, curso, em, numero)
    if resposta is not None:
        return resposta
    _, colado, lido, casamento, conferencia = preparado
    return _desenhar(
        request,
        curso,
        em,
        numero,
        colado,
        _resumo(lido, casamento, conferencia) | {"previu": True},
    )


@require_POST
def capitulo_importar(request, curso: str, numero: str, parte: "str | None" = None):
    """Grava, pela porta, só as peças que estão vazias hoje.

    RECUSA quando o número do capítulo não é o da encomenda aberta: são 34
    capítulos parecidos, e gravar o 8 dentro do 9 é o acidente que ele só
    descobriria semanas depois, lendo.
    """
    em = _parte(parte)
    preparado, resposta = _preparar(request, curso, em, numero)
    if resposta is not None:
        return resposta
    site, colado, lido, casamento, conferencia = preparado

    if conferencia["diferente"]:
        return _desenhar(
            request,
            curso,
            em,
            numero,
            colado,
            _resumo(lido, casamento, conferencia) | {"recusei_pelo_numero": True},
            status=400,
        )

    if not casamento["corpo"]:
        return _desenhar(
            request,
            curso,
            em,
            numero,
            colado,
            _resumo(lido, casamento, conferencia) | {"importou": True, "gravou": False},
        )

    desfecho, corpo = CursosClient().gravar_aula(
        site["id"], curso, numero, casamento["corpo"]
    )
    if desfecho != CursosClient.OK:
        _auditar(
            request,
            Registro.EDITAR_AULA,
            numero,
            (
                Registro.RECUSADO_PELA_CELULA
                if desfecho == CursosClient.RECUSADO
                else Registro.NAO_RESPONDEU
            ),
            f"capitulo: {desfecho}",
        )
        return _desenhar(
            request,
            curso,
            em,
            numero,
            colado,
            _resumo(lido, casamento, conferencia)
            | {
                "recusada": (
                    "A sala de aula não aceitou o texto deste capítulo."
                    if desfecho == CursosClient.RECUSADO
                    else _falha(desfecho)["titulo"]
                )
            },
            status=503,
        )

    _auditar(
        request,
        Registro.EDITAR_AULA,
        numero,
        Registro.OK,
        f"capitulo: {len(casamento['preencher'])} campo(s) vazio(s) preenchido(s)",
    )
    return _desenhar(
        request,
        curso,
        em,
        numero,
        colado,
        _resumo(lido, casamento, conferencia)
        | {
            "importou": True,
            "gravou": True,
            "versao": int((corpo or {}).get("versao") or 0),
        },
    )
