#!/usr/bin/env python3
"""O TRAVESSÃO NÃO ATRAVESSA — texto publicado sai sem travessão.

Decisão do mantenedor em 30/08/2026: **todo texto escrito para ser publicado
online sai sem travessão.** No lugar dele entram vírgula, parênteses,
dois-pontos ou aspas, conforme o papel que o travessão fazia na frase. A escolha
é de quem escreve; este portão não escolhe por ninguém — ele só recusa o
travessão e ensina as quatro trocas.

POR QUE ISTO É UM PORTÃO, E NÃO UM CONSELHO
-------------------------------------------
A doença-mãe deste projeto é regra escrita que ninguém impõe
(`ci/leis_sem_mecanismo.py`): ela não falha, não apita, e é obedecida enquanto
alguém lembrar. Uma regra de ESCRITA é o caso extremo dessa doença — quem
escreve o texto novo é uma sessão diferente a cada vez, e nenhuma delas leu o
que a anterior combinou. Só um portão atravessa sessões.

A SUPERFÍCIE PÚBLICA — o que ele olha, e por que assim
------------------------------------------------------
O mantenedor definiu a fronteira em 30/08/2026: **entra tudo que alguém que não
é ele lê.** A vitrine do site, o cadastro, o login, o checkout, o quiz, o
fórum, a área do aluno, a Caixa de Sugestões, os documentos publicados e as
traduções. Fica de fora o bastidor: o painel dele e as telas de administração,
que ninguém além dele abre.

A superfície é DERIVADA, não listada: toda pasta `templates/` de toda célula,
toda pasta `traducoes/`, e `documentos/`. Célula nova, ou tela nova numa célula
que já existe, entra sozinha — é fail-closed, e é de propósito. Um mapa de
caminhos mantido à mão envelheceria em silêncio, que é a Classe 8 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` e já cobrou caro aqui.

O bastidor sai por uma lista CURTA e declarada (`ci/texto-publico-bastidor.txt`),
uma linha por padrão, com o motivo escrito. A inversão importa: em dúvida, o
texto é público. Tirar algo da regra exige uma linha no diff que alguém vê.

O QUE CONTA COMO TRAVESSÃO
--------------------------
As três riscas longas (`—` travessão, `–` meia-risca, `―` barra horizontal) e
as formas escritas em HTML que viram risca na tela (`&mdash;`, `&ndash;`,
`&#8212;`, `&#x2014;`, ...). O HÍFEN (`-`) nunca entra: ele é letra de palavra
composta ("guarda-chuva"), não pontuação de frase. Um portão que caçasse hífen
seria um portão que recusa português correto, e viraria ruído até alguém o
desligar.

COMENTÁRIO NÃO É TEXTO PUBLICADO
--------------------------------
`{% comment %}`, `{# #}`, `<!-- -->` e `#` de YAML não chegam a leitor nenhum.
Eles são despidos antes da contagem — e sem essa poda a dívida medida aqui
seria quatro vezes maior e quase toda falsa, o que treinaria todo mundo a
ignorar o portão. Medir a coisa errada com precisão é como um portão morre.

O TEXTO DE TELA QUE MORA EM CÓDIGO (31/08/2026)
-----------------------------------------------
Até 31/08/2026 este parágrafo se chamava "o que ele NÃO mede" e prometia que a
superfície cresceria "se um dia a cópia do site passar a morar em `.py`". Esse
dia chegou, e o buraco era maior que o morador que o parágrafo citava: os
RÓTULOS de todo `TextChoices` sempre foram texto de tela morando em `models.py`.

    EM_ANALISE = "em_analise", "Em análise"
    #            ^ contrato       ^ o que o aluno lê no selo

O primeiro elemento viaja em contrato congelado, migration e banco; trocá-lo é
um Rito. O segundo sai em `{{ objeto.get_status_display }}` e nunca esteve sob
régua nenhuma. Entram agora DOIS conjuntos de `.py`, com regras diferentes de
propósito:

* **Quem declara `Choices` com rótulo escrito entra SOZINHO**, sem marca e sem
  lista, e só o RÓTULO é medido. É a classe que já mordeu, e não depende de
  ninguém lembrar de nada.
* **Quem se declara** com o comentário `ci:texto-publicado` entra INTEIRO, pela
  mesma peneira dos comandos de gestão. É para a cópia de site que não cabe em
  `Choices` — um dicionário de frases escrito para o aluno, como o
  `EXPLICACAO_DAS_ETAPAS` da Caixa de Sugestões.

`migrations/` fica fora das duas: o rótulo lá é fotografia do modelo naquele
dia, não a frase viva.

**Por que a segunda metade é opt-in, dito na cara:** para ela não existe forma
mecânica barata. Medido em 31/08/2026, varrer toda constante MAIÚSCULA de módulo
nas células públicas daria 2758 strings e 94 travessões, quase todos em mensagem
de erro e no próprio painel de travessões do Admin, que lista as riscas como
DADO. Medir a coisa errada com precisão é como um portão morre. Quem esquecer a
marca fica de fora, e essa é a fraqueza que sobra — mitigada por a primeira
metade, que é o caso comum, não depender de marca nenhuma.

O que continua fora, e por decisão e não por esquecimento: `painel/ia/`, servido
em `/mapa-ia/` sem porta, é mapa TÉCNICO escrito para uma IA de fora auditar o
sistema, e a régua do mantenedor é a leitura de PESSOAS. São 314 travessões que
nenhum aluno lê.

A CATRACA DA DÍVIDA HERDADA
---------------------------
O texto que já estava publicado quando a regra nasceu está em
`ci/travessoes-herdados.txt`, arquivo por arquivo, com a contagem exata. O
número declarado é um COMPROMISSO, não um teto frouxo:

    contagem real > declarada  ->  FAIL (a dívida cresceu)
    contagem real < declarada  ->  FAIL, com a linha nova pronta para colar
    arquivo fora da lista com travessão  ->  FAIL (texto novo não nasce devendo)

Baixar o número é sempre permitido, e é o objetivo. Exigir que o diff MOSTRE a
queda é o que impede a lista de virar ficção — a mesma forma de
`ci/guardas-nao-declarados.txt` e `ci/leis-sem-mecanismo.txt`, que já provaram
funcionar aqui.

Uso:

    python ci/travessao.py             # o portão (o que a CI roda)
    python ci/travessao.py --listar    # o censo, para leitura humana
    python ci/travessao.py --herdados  # a lista pronta para colar no arquivo

Exit codes: 0 PASS · 1 travessão em texto público · 2 ERROR (não mediu).
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)

LISTA_DE_HERDADOS = "ci/travessoes-herdados.txt"
LISTA_DE_BASTIDOR = "ci/texto-publico-bastidor.txt"

# A marca que um módulo `.py` põe em si mesmo para dizer "as minhas constantes
# de string saem na tela de alguém". É COMENTÁRIO, não código: não custa um
# import, não muda o comportamento em produção, e some do texto medido (o `.py`
# é despido de comentários antes da contagem).
#
# Ela existe porque a regra mecânica de baixo (`_arquivos_com_rotulos`) resolve
# a classe MAIS COMUM de cópia de site em código — o rótulo de um `TextChoices`
# — e não resolve a outra: um dicionário de frases escrito para o aluno ler,
# como o `EXPLICACAO_DAS_ETAPAS` da Caixa de Sugestões. Para essa não existe
# forma mecânica barata: medido em 31/08/2026, varrer toda constante MAIÚSCULA
# de módulo nas células públicas daria 2758 strings e 94 travessões, quase todos
# em mensagem de erro e no próprio painel de travessões do Admin, que lista as
# riscas como DADO. Medir a coisa errada com precisão é como um portão morre.
#
# É opt-in, e isso é uma fraqueza declarada, não escondida: quem esquecer a
# marca fica de fora. O que a torna honesta é ela não ser a única linha de
# defesa — o rótulo de `Choices`, que é o caso que já mordeu, entra sozinho.
MARCA_DE_TEXTO_PUBLICO = "ci:texto-publicado"

# Os dois modos de ler um `.py`. O sufixo do arquivo não basta para decidir:
# dois arquivos `.py` da superfície podem ser medidos de formas diferentes, e é
# `modo_de_leitura` quem escolhe.
MODO_PY_INTEIRO = ".py"
MODO_PY_ROTULOS = ".py:rotulos"

# ---------------------------------------------------------------------------
# O que é travessão. Cada forma tem nome, porque a recusa cita o nome.
# ---------------------------------------------------------------------------
FORMAS = (
    ("—", "travessão (—)"),
    ("–", "meia-risca (–)"),
    ("―", "barra horizontal (―)"),
    ("&mdash;", "travessão escrito em HTML (&mdash;)"),
    ("&ndash;", "meia-risca escrita em HTML (&ndash;)"),
    ("&horbar;", "barra horizontal em HTML (&horbar;)"),
    ("&#8212;", "travessão em código HTML (&#8212;)"),
    ("&#8211;", "meia-risca em código HTML (&#8211;)"),
    ("&#x2014;", "travessão em código HTML (&#x2014;)"),
    ("&#x2013;", "meia-risca em código HTML (&#x2013;)"),
)

# Pastas que nunca são texto publicado, em qualquer profundidade.
PASTAS_IGNORADAS = {"__pycache__", ".venv", "node_modules", ".git", "tests", "testes"}

# A lição que a recusa entrega, palavra por palavra do mantenedor. Ela viaja
# junto do erro de propósito: quem topa com o portão precisa saber como sair
# dele na mesma tela, sem abrir documento nenhum (a linha de precisão das
# muralhas desta casa — "a recusa entrega uma alternativa EXECUTÁVEL na hora").
COMO_TROCAR = """\
COMO TROCAR — escolha pelo papel que o travessão fazia na frase:

  VÍRGULA (troca neutra) — explicação comum, no meio da frase. Mantém a
  leitura fluida e natural.
      antes:  O motorista — que estava muito cansado — parou no posto.
      depois: O motorista, que estava muito cansado, parou no posto.

  PARÊNTESES (troca de menor destaque) — dado acessório, que pode ser
  ignorado sem perda.
      antes:  A inflação — principal vilã do orçamento — voltou a subir.
      depois: A inflação (principal vilã do orçamento) voltou a subir.

  DOIS-PONTOS (troca de fechamento) — quando o trecho isolado fica no FIM da
  frase e serve de esclarecimento ou conclusão.
      antes:  Ele só queria uma coisa — paz.
      depois: Ele só queria uma coisa: paz.

  ASPAS (troca de diálogo) — quando o travessão marcava fala de personagem.
      antes:  — Não quero ir hoje — disse Pedro.
      depois: "Não quero ir hoje", disse Pedro.

O hífen (-) continua livre: ele é letra de palavra composta, não pontuação.

A TROCA É UMA REESCRITA, NÃO UM CARACTERE TROCADO. Este erro já foi cometido, em
30/08/2026, numa dúzia de frases publicadas: dois-pontos NÃO separa o verbo do
seu complemento, nem abre uma oração que continua direto o pensamento anterior.
Se o trecho depois do travessão começa por "é", "são", "não" ou um imperativo,
dois-pontos quebra a frase.

      travessão:  Modelo pela metade também conta — é vendo o meio do caminho...
      ERRADO:     Modelo pela metade também conta: é vendo o meio do caminho...
      certo:      Modelo pela metade também conta, pois é vendo o meio...
      certo:      Nada foi criado. Tente de novo.        (ponto final)

Leia a frase em voz alta. Se você tropeçar, a troca está errada, ainda que o
travessão tenha sumido.
"""


@dataclass(frozen=True)
class Achado:
    """Um travessão vivo num texto que alguém vai ler."""

    caminho: str
    linha: int
    forma: str
    trecho: str


# ---------------------------------------------------------------------------
# Despir o texto: o que é comentário não chega a leitor nenhum.
#
# Toda poda troca o comentário por ESPAÇOS do mesmo tamanho, nunca por vazio.
# Assim o número da linha e a coluna continuam batendo com o arquivo real, e a
# recusa aponta para o lugar certo. Um portão que erra a linha manda o leitor
# procurar, e procurar é onde a paciência acaba.
# ---------------------------------------------------------------------------
def _apagar(texto: str, inicio: int, fim: int) -> str:
    miolo = texto[inicio:fim]
    return (
        texto[:inicio]
        + "".join("\n" if c == "\n" else " " for c in miolo)
        + texto[fim:]
    )


def _podar_par(texto: str, abre: str, fecha: str) -> str:
    """Apaga todo trecho entre `abre` e `fecha`, inclusive os delimitadores.

    Abertura sem fechamento apaga até o fim do arquivo: um comentário que
    ninguém fechou também não é publicado, e tratar o resto como texto vivo
    inventaria achados que não existem na tela.
    """
    saida = texto
    procura = 0
    while True:
        i = saida.find(abre, procura)
        if i < 0:
            return saida
        j = saida.find(fecha, i + len(abre))
        fim = len(saida) if j < 0 else j + len(fecha)
        saida = _apagar(saida, i, fim)
        procura = fim


RE_COMENTARIO_DJANGO = re.compile(r"\{%-?\s*comment\b.*?%\}", re.DOTALL)


def _podar_comentario_django(texto: str) -> str:
    """`{% comment %} … {% endcomment %}`, inclusive com rótulo e com `{%- -%}`."""
    saida = texto
    procura = 0
    while True:
        abre = RE_COMENTARIO_DJANGO.search(saida, procura)
        if abre is None:
            return saida
        fecha = saida.find("endcomment", abre.end())
        if fecha < 0:
            fim = len(saida)
        else:
            marca = saida.find("%}", fecha)
            fim = len(saida) if marca < 0 else marca + 2
        saida = _apagar(saida, abre.start(), fim)
        procura = fim


def _podar_comentario_de_linha(texto: str, marca: str, exigir_folga: bool) -> str:
    """`marca` até o fim da linha, mas só FORA de aspas.

    `titulo: "Promoção # 2"` publica a cerquilha; tratá-la como comentário
    cegaria o portão para o resto da linha, que é justamente onde o texto do
    site mora. Em JS a mesma regra vale para `//`, com o cuidado extra de não
    confundir com o `//` de uma URL (`https://…`).

    `exigir_folga` pede espaço antes da marca — é o que separa o `#` de
    comentário do `#` colado numa palavra.
    """
    saida = []
    for linha in texto.split("\n"):
        aspas: str | None = None
        corte = None
        pos = 0
        while pos < len(linha):
            c = linha[pos]
            if aspas:
                if c == aspas and linha[pos - 1] != "\\":
                    aspas = None
            elif c in "'\"`":
                aspas = c
            elif linha.startswith(marca, pos):
                anterior = linha[pos - 1] if pos else " "
                folga_ok = (not exigir_folga) or anterior in " \t" or pos == 0
                if folga_ok and anterior != ":":
                    corte = pos
                    break
            pos += 1
        saida.append(
            linha if corte is None else linha[:corte] + " " * (len(linha) - corte)
        )
    return "\n".join(saida)


def _podar_comentario_de_yaml(texto: str) -> str:
    return _podar_comentario_de_linha(texto, "#", exigir_folga=True)


RE_BLOCO_DE_CODIGO = re.compile(
    r"<(script|style)\b[^>]*>(.*?)</\1\s*>", re.DOTALL | re.IGNORECASE
)


def _podar_comentario_de_codigo(texto: str) -> str:
    """Comentário de JS e de CSS dentro de `<script>`/`<style>` também não é lido.

    Sem esta poda o portão reprovava a nota de um programador dentro de um
    `/* … */` — texto que nenhum visitante recebe. Reprovar comentário de código
    é a definição de portão chato, e portão chato é desligado por quem trabalha:
    a lição está na `docs/decisoes/RETROSPECTIVA-FASE-D.md`.

    A poda é DELIBERADAMENTE estreita. Só o miolo de `<script>` e `<style>`
    entra, para um `/*` solto no meio do HTML nunca comer texto de verdade; e o
    `//` só corta fora de aspas, porque `x_text="\\`${a} — ${b}\\`"` é rótulo na
    tela, não comentário.
    """
    saida = texto
    for casa in RE_BLOCO_DE_CODIGO.finditer(texto):
        inicio, fim = casa.span(2)
        miolo = saida[inicio:fim]
        limpo = _podar_par(miolo, "/*", "*/")
        limpo = _podar_comentario_de_linha(limpo, "//", exigir_folga=False)
        saida = saida[:inicio] + limpo + saida[fim:]
    return saida


def _so_as_strings_de_codigo(texto: str) -> str:
    """Só as constantes de string que NÃO são docstring, no lugar exato delas.

    Num `.py` a maior parte do texto é para quem programa: docstring, comentário,
    mensagem de log, texto de validação. Varrer o arquivo inteiro seria ruído —
    medido em 30/08/2026, 160 achados nas células públicas e quase nenhum na
    tela de alguém. O que sobra depois desta peneira é o que o código realmente
    ESCREVE: o nome de uma área, a descrição que o aluno lê.

    A tela em branco preserva linha e coluna, então a recusa aponta para o lugar
    certo do arquivo original. Arquivo que nem parseia devolve vazio: quem cobra
    sintaxe é o CI da célula, e um `SyntaxError` aqui não é travessão nenhum.
    """
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return ""

    docstrings: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(
            no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if no.body and isinstance(no.body[0], ast.Expr):
                primeiro = no.body[0].value
                if isinstance(primeiro, ast.Constant) and isinstance(
                    primeiro.value, str
                ):
                    docstrings.add(id(primeiro))

    linhas = texto.split("\n")
    tela = [[" "] * len(linha) for linha in linhas]
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
            continue
        if id(no) in docstrings or no.end_lineno is None:
            continue
        for numero in range(no.lineno, no.end_lineno + 1):
            original = linhas[numero - 1]
            comeco = no.col_offset if numero == no.lineno else 0
            fim = no.end_col_offset if numero == no.end_lineno else len(original)
            for coluna in range(comeco, min(fim, len(original))):
                tela[numero - 1][coluna] = original[coluna]
    return "\n".join("".join(linha) for linha in tela)


def _so_os_rotulos_de_choices(texto: str) -> str:
    """Só o RÓTULO de cada membro de um `TextChoices`, no lugar exato dele.

    Um `TextChoices` tem duas metades por linha, e só a segunda é interface:

        EM_ANALISE = "em_analise", "Em análise"
        #            ^ contrato       ^ o que a pessoa lê na tela

    A primeira viaja em contrato congelado, migration e banco; trocá-la é um
    Rito. A segunda sai em `{{ objeto.get_status_display }}`, no selo, na linha
    do tempo e no aviso — e nunca esteve sob portão de texto nenhum, porque
    mora num arquivo de MODELO.

    Só o segundo elemento em diante da tupla entra. O primeiro é deixado de
    fora de propósito: ele é identificador, não frase, e um travessão ali seria
    um problema de outra natureza (e outro portão).

    Mesma tela em branco de `_so_as_strings_de_codigo`: linha e coluna
    preservadas, para a recusa apontar o lugar certo do arquivo original.
    """
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return ""

    linhas = texto.split("\n")
    tela = [[" "] * len(linha) for linha in linhas]
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ClassDef) or not _eh_classe_de_choices(no):
            continue
        for membro in no.body:
            if not isinstance(membro, ast.Assign) or not isinstance(
                membro.value, ast.Tuple
            ):
                continue
            for elemento in membro.value.elts[1:]:
                if not (
                    isinstance(elemento, ast.Constant)
                    and isinstance(elemento.value, str)
                ):
                    continue
                if elemento.end_lineno is None:
                    continue
                for numero in range(elemento.lineno, elemento.end_lineno + 1):
                    original = linhas[numero - 1]
                    comeco = elemento.col_offset if numero == elemento.lineno else 0
                    fim = (
                        elemento.end_col_offset
                        if numero == elemento.end_lineno
                        else len(original)
                    )
                    for coluna in range(comeco, min(fim, len(original))):
                        tela[numero - 1][coluna] = original[coluna]
    return "\n".join("".join(linha) for linha in tela)


def _eh_classe_de_choices(no: ast.ClassDef) -> bool:
    """A classe herda de algo terminado em `Choices`.

    Casa `models.TextChoices`, `TextChoices`, `models.IntegerChoices` e o
    `Choices` cru, sem importar o Django aqui — o portão roda sem as células
    instaladas. O sufixo, e não a lista fechada de nomes, porque uma base
    própria (`class MinhasChoices(models.TextChoices)`) continua sendo choices.
    """
    for base in no.bases:
        nome = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        if nome.endswith("Choices"):
            return True
    return False


def despir(texto: str, sufixo: str) -> str:
    """O texto como o leitor o recebe: sem os comentários de quem escreveu."""
    if sufixo in (".html", ".htm"):
        texto = _podar_comentario_django(texto)
        texto = _podar_par(texto, "{#", "#}")
        texto = _podar_par(texto, "<!--", "-->")
        return _podar_comentario_de_codigo(texto)
    if sufixo in (".yaml", ".yml"):
        return _podar_comentario_de_yaml(texto)
    if sufixo == ".md":
        return _podar_par(texto, "<!--", "-->")
    if sufixo == MODO_PY_ROTULOS:
        return _so_os_rotulos_de_choices(texto)
    if sufixo == MODO_PY_INTEIRO:
        return _so_as_strings_de_codigo(texto)
    return texto


# ---------------------------------------------------------------------------
# A superfície pública, derivada do repositório (nunca listada à mão).
# ---------------------------------------------------------------------------
def _padroes_de_bastidor(raiz: Path) -> list[str]:
    arquivo = raiz / LISTA_DE_BASTIDOR
    if not arquivo.is_file():
        raise ErroDeInstrumentacao(
            "a lista do bastidor não existe",
            f"Esperada em:\n  {arquivo}\n\n"
            "Sem ela o portão não sabe o que é tela de administração e o que é\n"
            "texto público. Lista ausente não é lista vazia: medir a superfície\n"
            "errada é pior que não medir.",
        )
    padroes = []
    for bruta in arquivo.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        padrao, _, motivo = linha.partition("::")
        if len(motivo.strip()) < 15:
            raise ErroDeInstrumentacao(
                "linha do bastidor sem motivo escrito",
                f"Em {LISTA_DE_BASTIDOR}:\n  {linha}\n\n"
                "Toda linha tira um texto da regra: `<padrão> :: <por que ninguém\n"
                "de fora lê isto>`. Carimbo de menos de 15 caracteres não é motivo.",
            )
        padroes.append(padrao.strip())
    return padroes


def _define_choices(fonte: str) -> bool:
    r"""O arquivo declara ao menos uma classe de `Choices` com rótulo escrito.

    Rótulo ESCRITO é a metade que importa: `PUBLICA = "publica"` sozinho não
    tem frase nenhuma (o Django deriva o rótulo do nome), e um arquivo assim não
    tem o que medir. Só a forma de tupla entra.

    O silêncio em volta do `ast.parse` não é preguiça: esta função agora lê TODO
    `.py` de célula à procura de `Choices`, e um `SyntaxWarning` de sequência de
    escape mal escrita num arquivo qualquer (`"\g"` numa regex sem `r`) sairia
    no meio da saída do portão, parecendo achado dele. O aviso é legítimo e
    continua aparecendo para quem roda aquele arquivo; aqui ele é ruído de
    instrumento.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            arvore = ast.parse(fonte)
    except SyntaxError:
        return False
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ClassDef) or not _eh_classe_de_choices(no):
            continue
        for membro in no.body:
            if isinstance(membro, ast.Assign) and isinstance(membro.value, ast.Tuple):
                if len(membro.value.elts) > 1:
                    return True
    return False


def modo_de_leitura(caminho: Path, texto: str) -> str:
    """Como este arquivo deve ser despido antes da contagem.

    Para tudo que não é `.py`, o modo É o sufixo. Para um `.py` a pergunta é
    outra: o arquivo INTEIRO é cópia de site (um comando de gestão, ou um
    módulo que se declarou com a marca), ou só os rótulos de `Choices` dele?

    A marca vence o `Choices` de propósito. Um `models.py` que se declarou
    inteiro público está dizendo que tem mais texto de tela do que os rótulos, e
    medir só os rótulos ali seria obedecer à metade mais fraca da declaração.
    """
    if caminho.suffix.lower() != ".py":
        return caminho.suffix.lower()
    if caminho.parent.name == "commands" or MARCA_DE_TEXTO_PUBLICO in texto:
        return MODO_PY_INTEIRO
    return MODO_PY_ROTULOS


def _dentro_de_pasta_ignorada(relativo: Path) -> bool:
    return any(parte in PASTAS_IGNORADAS for parte in relativo.parts)


def superficie(raiz: Path) -> list[Path]:
    """Todo arquivo cujo texto alguém que não é o mantenedor pode ler."""
    achados: set[Path] = set()

    documentos = raiz / "documentos"
    if documentos.is_dir():
        achados |= {p for p in documentos.rglob("*.md") if p.is_file()}

    servicos = raiz / "services"
    if not servicos.is_dir():
        raise ErroDeInstrumentacao(
            "não encontrei services/ para derivar a superfície pública",
            f"Procurei em:\n  {servicos}\n\nSem as células não há o que medir.",
        )
    for celula in sorted(p for p in servicos.iterdir() if p.is_dir()):
        for pasta in celula.rglob("templates"):
            if not pasta.is_dir():
                continue
            for sufixo in (".html", ".htm", ".txt", ".md"):
                achados |= {p for p in pasta.rglob(f"*{sufixo}") if p.is_file()}
        for pasta in celula.rglob("traducoes"):
            if not pasta.is_dir():
                continue
            for sufixo in (".yaml", ".yml"):
                achados |= {p for p in pasta.rglob(f"*{sufixo}") if p.is_file()}
        # OS COMANDOS DE GESTÃO: os únicos `.py` da superfície, e a fronteira
        # aqui já foi estreita DEMAIS uma vez. Ela era `semear_*.py`, pelo
        # motivo certo (o nome e a descrição de uma área do fórum saem daqui
        # para `meshcraft.top/forum`) e com a régua errada: o NOME do arquivo.
        # `seed_sugestoes.py` cria as categorias e o quadro que o aluno lê, e
        # escapava por começar com `seed` em vez de `semear`. Quem achou o
        # buraco foi o mantenedor, olhando o site.
        #
        # Hoje entra a pasta inteira. O custo é pequeno e foi medido em
        # 30/08/2026: 12 travessões em 10 comandos, a maioria texto de terminal
        # que só o operador lê. Pagar 12 uma vez vale mais que uma régua que
        # depende de alguém escolher o prefixo certo do nome do arquivo.
        for pasta in celula.rglob("commands"):
            if not pasta.is_dir():
                continue
            achados |= {
                p for p in pasta.glob("*.py") if p.is_file() and p.name != "__init__.py"
            }

        # O CÓDIGO QUE ESCREVE TEXTO DE TELA. O buraco que o parágrafo "o que
        # ele NÃO mede" desta docstring anunciava desde 30/08/2026, fechado em
        # 31/08/2026 (TAR-087, `armadilhas/254`), com mandato do mantenedor
        # porque `ci/` é caminho CODEOWNERS.
        #
        # Entram DOIS conjuntos, e a diferença entre eles é o ponto:
        #
        # 1. **Quem tem `Choices` entra sozinho** — sem marca, sem lista, sem
        #    ninguém lembrar. É a classe que já mordeu: os seis rótulos de
        #    `Sugestao.Status` ("Em análise" e companhia) sempre foram texto que
        #    o aluno lê, morando em `models.py`, fora de qualquer portão. Aqui
        #    só o RÓTULO é medido (ver `_so_os_rotulos_de_choices`): o valor
        #    viaja em contrato congelado e não é frase.
        # 2. **Quem se declara** com a marca `ci:texto-publicado`, para a cópia
        #    de site que não cabe em `Choices` — um dicionário de frases para o
        #    aluno, como o `EXPLICACAO_DAS_ETAPAS` da Caixa. Aí o arquivo INTEIRO
        #    é medido pela mesma peneira dos comandos de gestão.
        #
        # `migrations/` fica FORA das duas. O rótulo lá é uma fotografia do que
        # o modelo era no dia, não a frase viva: corrigir a fotografia não muda
        # uma tela, e um portão que exigisse isso mandaria reescrever história.
        for arquivo in celula.rglob("*.py"):
            if not arquivo.is_file() or arquivo.name == "__init__.py":
                continue
            if "migrations" in arquivo.relative_to(celula).parts:
                continue
            if arquivo in achados:
                continue
            try:
                fonte = arquivo.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if MARCA_DE_TEXTO_PUBLICO in fonte or _define_choices(fonte):
                achados.add(arquivo)

    bastidor = _padroes_de_bastidor(raiz)
    publicos = []
    for caminho in achados:
        relativo = caminho.relative_to(raiz)
        if _dentro_de_pasta_ignorada(relativo):
            continue
        texto = relativo.as_posix()
        if any(fnmatch.fnmatch(texto, padrao) for padrao in bastidor):
            continue
        publicos.append(caminho)
    return sorted(publicos)


def pertence_a_superficie(raiz: Path, relativo: Path, texto: str) -> bool:
    """Este arquivo, com ESTE conteúdo, seria texto público para `superficie`?

    O espelho por-arquivo de `superficie`, para quem precisa decidir ANTES de o
    arquivo existir no disco: a muralha da escrita
    (`ci/muralha_do_travessao_na_escrita.py`) recusa o Write/Edit no momento em
    que o robô tenta gravar, e nesse momento um arquivo novo ainda não está em
    lugar nenhum para uma varredura de disco encontrar.

    As duas réguas são obrigadas a bater: o teste de equivalência
    (`ci/tests/test_muralha_do_travessao_na_escrita.py`) compara esta função com
    `superficie` sobre TODO arquivo do repositório real. Quem mudar uma sem a
    outra reprova lá, com o caminho divergente na tela.
    """
    if _dentro_de_pasta_ignorada(relativo):
        return False
    sufixo = relativo.suffix.lower()
    partes = relativo.parts
    publico = False
    if partes[0] == "documentos":
        publico = sufixo == ".md"
    elif partes[0] == "services" and len(partes) >= 3:
        pastas_da_celula = partes[2:-1]
        if sufixo in (".html", ".htm", ".txt", ".md"):
            publico = "templates" in pastas_da_celula
        elif sufixo in (".yaml", ".yml"):
            publico = "traducoes" in pastas_da_celula
        elif sufixo == ".py" and relativo.name != "__init__.py":
            if relativo.parent.name == "commands":
                publico = True
            elif "migrations" not in partes[2:]:
                publico = MARCA_DE_TEXTO_PUBLICO in texto or _define_choices(texto)
    if not publico:
        return False
    caminho_posix = relativo.as_posix()
    return not any(
        fnmatch.fnmatch(caminho_posix, padrao) for padrao in _padroes_de_bastidor(raiz)
    )


# ---------------------------------------------------------------------------
# A contagem.
# ---------------------------------------------------------------------------
def achar(texto: str, sufixo: str, caminho: str) -> list[Achado]:
    """Os travessões vivos de um texto, já despido dos comentários."""
    limpo = despir(texto, sufixo)
    achados: list[Achado] = []
    for numero, linha in enumerate(limpo.split("\n"), start=1):
        for marca, nome in FORMAS:
            posicao = linha.find(marca)
            while posicao >= 0:
                achados.append(
                    Achado(caminho, numero, nome, _recorte(linha, posicao, len(marca)))
                )
                posicao = linha.find(marca, posicao + len(marca))
    return sorted(achados, key=lambda a: (a.linha, a.forma))


def _recorte(linha: str, posicao: int, tamanho: int, folga: int = 32) -> str:
    inicio = max(0, posicao - folga)
    fim = min(len(linha), posicao + tamanho + folga)
    trecho = linha[inicio:fim].strip()
    return ("…" if inicio > 0 else "") + trecho + ("…" if fim < len(linha) else "")


def censo(raiz: Path) -> dict[str, list[Achado]]:
    """Arquivo público -> travessões vivos nele. Só entra quem tem algum."""
    resultado: dict[str, list[Achado]] = {}
    for caminho in superficie(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as erro:
            raise ErroDeInstrumentacao(
                f"não consegui ler {relativo}",
                f"{erro}\n\nUm arquivo público ilegível não é um arquivo limpo.",
            ) from erro
        achados = achar(texto, modo_de_leitura(caminho, texto), relativo)
        if achados:
            resultado[relativo] = achados
    return resultado


# ---------------------------------------------------------------------------
# A catraca da dívida herdada.
# ---------------------------------------------------------------------------
def herdados(raiz: Path) -> dict[str, int]:
    arquivo = raiz / LISTA_DE_HERDADOS
    if not arquivo.is_file():
        raise ErroDeInstrumentacao(
            "a lista da dívida herdada não existe",
            f"Esperada em:\n  {arquivo}\n\n"
            "Lista ausente faria todo texto antigo virar violação de uma vez.\n"
            "Isso não é rigor: é um portão que ninguém consegue atender, e um\n"
            "portão assim é desligado na primeira semana.",
        )
    declarados: dict[str, int] = {}
    for bruta in arquivo.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        caminho, _, quantia = linha.partition("::")
        try:
            numero = int(quantia.strip())
        except ValueError:
            raise ErroDeInstrumentacao(
                "linha da dívida sem contagem",
                f"Em {LISTA_DE_HERDADOS}:\n  {linha}\n\n"
                "O molde é `<caminho> :: <quantos travessões ainda vivos>`.",
            ) from None
        declarados[caminho.strip()] = numero
    return declarados


def rodar(raiz: Path | None = None) -> Relatorio:
    relatorio = Relatorio("TRAVESSÃO EM TEXTO PÚBLICO")
    try:
        raiz = raiz or raiz_do_repo()
        vivos = censo(raiz)
        declarados = herdados(raiz)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("superficie", erro))
        return relatorio

    novos = {c: a for c, a in vivos.items() if c not in declarados}
    cresceu = {
        c: (len(a), declarados[c])
        for c, a in vivos.items()
        if c in declarados and len(a) > declarados[c]
    }
    encolheu = {
        c: (len(vivos.get(c, [])), n)
        for c, n in declarados.items()
        if len(vivos.get(c, [])) < n
    }

    total_publicos = len(superficie(raiz))
    relatorio.registrar(
        Resultado(
            "superficie",
            Estado.PASS,
            f"{total_publicos} arquivos de texto público inspecionados",
        )
    )

    if novos:
        linhas = [
            "Travessão em texto que alguém vai ler, e que não está na dívida herdada.",
            "",
        ]
        for caminho, achados in sorted(novos.items()):
            linhas.append(f"  {caminho}  ({len(achados)})")
            for achado in achados[:6]:
                linhas.append(f"      linha {achado.linha}: {achado.trecho}")
            if len(achados) > 6:
                linhas.append(f"      … e mais {len(achados) - 6}")
        linhas += ["", COMO_TROCAR]
        relatorio.registrar(
            Resultado(
                "texto-novo",
                Estado.FAIL,
                f"{sum(len(a) for a in novos.values())} travessões em {len(novos)} arquivo(s)",
                "\n".join(linhas),
            )
        )
    else:
        relatorio.registrar(
            Resultado(
                "texto-novo", Estado.PASS, "nenhum travessão fora da dívida herdada"
            )
        )

    if cresceu:
        linhas = ["A dívida herdada CRESCEU. Ela só pode encolher.", ""]
        for caminho, (real, declarado) in sorted(cresceu.items()):
            linhas.append(f"  {caminho}: {declarado} declarados, {real} encontrados")
            for achado in vivos[caminho][:6]:
                linhas.append(f"      linha {achado.linha}: {achado.trecho}")
        linhas += ["", COMO_TROCAR]
        relatorio.registrar(
            Resultado(
                "divida-cresceu",
                Estado.FAIL,
                f"{len(cresceu)} arquivo(s)",
                "\n".join(linhas),
            )
        )
    elif encolheu:
        linhas = [
            "A dívida encolheu — é exatamente o objetivo. Falta baixar o número",
            f"em {LISTA_DE_HERDADOS}, no MESMO PR, para a queda aparecer no diff:",
            "",
        ]
        for caminho, (real, declarado) in sorted(encolheu.items()):
            linhas.append(
                f"  {caminho} :: {real}"
                + (f"      (era {declarado}; apague a linha se chegou a zero)")
            )
        relatorio.registrar(
            Resultado(
                "divida-encolheu",
                Estado.FAIL,
                f"{len(encolheu)} arquivo(s) já limpos e ainda declarados",
                "\n".join(linhas),
            )
        )
    else:
        restante = sum(declarados.values())
        relatorio.registrar(
            Resultado(
                "divida-herdada",
                Estado.PASS,
                f"{restante} travessões herdados em {len(declarados)} arquivo(s), estáveis",
            )
        )

    orfaos = [
        c
        for c in declarados
        if c not in {p.relative_to(raiz).as_posix() for p in superficie(raiz)}
    ]
    if orfaos:
        relatorio.registrar(
            Resultado(
                "divida-orfa",
                Estado.FAIL,
                f"{len(orfaos)} linha(s) apontam para arquivo que saiu da superfície",
                "Estes caminhos estão na dívida mas não são mais texto público\n"
                "(sumiram, mudaram de nome, ou entraram no bastidor). Apague as\n"
                "linhas — dívida que aponta para o nada parece garantia e não é:\n\n"
                + "\n".join(f"  {c}" for c in sorted(orfaos)),
            )
        )

    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Nenhum texto publicado online sai com travessão.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=COMO_TROCAR,
    )
    parser.add_argument(
        "--listar", action="store_true", help="o censo, para leitura humana"
    )
    parser.add_argument(
        "--herdados",
        action="store_true",
        help=f"a lista pronta para colar em {LISTA_DE_HERDADOS}",
    )
    args = parser.parse_args(argv)

    if args.listar or args.herdados:
        try:
            vivos = censo(raiz_do_repo())
        except ErroDeInstrumentacao as erro:
            print(f"ERROR: {erro.resumo}\n{erro.detalhe}", file=sys.stderr)
            return 2
        if args.herdados:
            for caminho, achados in sorted(vivos.items()):
                print(f"{caminho} :: {len(achados)}")
            print(f"# TOTAL: {sum(len(a) for a in vivos.values())}")
            return 0
        for caminho, achados in sorted(vivos.items()):
            print(f"\n{caminho}  ({len(achados)})")
            for achado in achados:
                print(f"  linha {achado.linha}  {achado.forma}: {achado.trecho}")
        print(
            f"\nTOTAL: {sum(len(a) for a in vivos.values())} em {len(vivos)} arquivo(s)"
        )
        return 0

    relatorio = rodar()
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
