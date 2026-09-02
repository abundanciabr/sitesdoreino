"""O REVISOR DE POUSO — um par de olhos com contexto fresco, no instante do merge.

Recomendação **B11** do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`
("revisor-robô no pouso é o substituto mais próximo do revisor humano
ausente"), tarefa TAR-006, despachada pelo mantenedor em 02/09/2026.

    python ci/revisor_de_pouso.py 123              # revisa e imprime
    python ci/revisor_de_pouso.py 123 --comentar   # revisa e comenta no PR
    python ci/revisor_de_pouso.py 0 --diff-de x.patch   # sem tocar no GitHub

O BURACO QUE ISTO FECHA, e ele é MEDIDO
=======================================
Nos lotes de 01/09/2026, **seis falsos-verdes** foram encontrados em código que
já estava verde. Nenhum deles pelo CI: todos por mutação deliberada feita pelo
próprio autor, depois do verde (`armadilhas/264` a `269` e `272`). Todos da
mesma família:

    a asserção tinha mais de uma causa suficiente,
    então o teste passava pelo motivo errado.

Nenhum guarda deste repositório pega essa classe, e não é descuido: ela é
**invisível a quem só olha "passou ou não passou"**. O teste existe, tem nome
descritivo, tem docstring, cobre a linha e fica verde — e continua verde com a
regra que ele deveria proteger arrancada do código. A cobertura de linhas é
idêntica nas duas versões, porque as duas *executam* o mesmo trecho
(`armadilhas/267`).

O que falta não é mais um portão binário: é alguém LENDO o diff com contexto
fresco e perguntando "quantos caminhos independentes produzem esse vazio?".
Este programa é esse alguém.

TRÊS DECISÕES DE DESENHO, E O PORQUÊ DE CADA UMA
================================================

1. ELE OPINA, NÃO REPROVA — e por isso o exit code é SEMPRE 0.
   Um revisor que barra vira portão sem apelação num fluxo onde não há humano
   para desempatar, e esta casa já mediu o custo disso: *"portão que reprova
   quem está certo ensina a ser contornado"* (lição 7 do Lote 9). As heurísticas
   aqui são bem-intencionadas e vão errar; errar custando um comentário é
   barato, errar travando a esteira da casa inteira não é. Se um dia ele passar
   a barrar, isso é decisão do mantenedor, com data — não de quem escreve
   código.

2. FAIL-OPEN, E ISTO É OBRIGATÓRIO.
   Revisor que não conseguiu rodar **não segura o pouso** e **não fabrica
   veredito**: ele diz `NAO-REVISADO` e sai de cena. A distinção FAIL contra
   ERROR vale aqui como em todo lugar desta casa ([INV-CI01]) — só que, como
   ele não tem poder de recusa, os dois desaguam em exit 0. O que NUNCA pode
   acontecer é "não consegui medir" chegar disfarçado de "está limpo": por isso
   `NAO-REVISADO` é um veredito escrito, não um silêncio.

3. ELE NUNCA EXECUTA O CÓDIGO DO PR — só LÊ o texto do diff.
   A pista roda com a `PISTA_TOKEN`, que tem poder de merge. Rodar código vindo
   de um PR ali dentro seria entregar esse poder a qualquer um que abra um PR —
   e o repositório é público. Este programa só chama `gh pr diff` e olha o
   texto. Sem `import`, sem `exec`, sem checkout do ramo. É a mesma razão pela
   qual a pista faz `checkout ref: main` (decisão 2 do cabeçalho do
   `pouso.yml`).

O QUE ELE PROCURA, EM ORDEM DE VALOR
====================================
Só coisas que NENHUMA máquina desta casa já diz. Estilo, formatação, travessão,
orçamento de arquivos, catraca de testes e contrato já têm portão próprio —
revisor que repete o que a máquina já disse ensina a ser ignorado.

    D1  asserção de ausência com mais de uma causa suficiente  (armadilhas/266)
    D2  filtro provado por um lado só do filtro                (armadilhas/267)
    D3  a asserção mede o dublê, não o código
    D4  guarda novo que nunca foi visto reprovando  (RETROSPECTIVA-FASE-D §1)

A LINHA QUE QUEM AGE SOBRE O VEREDITO LÊ
========================================
Última linha da saída, sempre ASCII, no mesmo molde do `MOTIVO-DA-RECUSA:` do
`ci/mergear.py` e pelo mesmo motivo (roteador não pode depender de prosa
acentuada atravessando YAML, shell e locale de executor):

    REVISOR-DE-POUSO: LIMPO
    REVISOR-DE-POUSO: ACHADOS 3
    REVISOR-DE-POUSO: NAO-REVISADO
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)

# A linha de código estável. Ver o fim do docstring.
MARCA = "REVISOR-DE-POUSO:"
LIMPO = "LIMPO"
ACHADOS = "ACHADOS"
NAO_REVISADO = "NAO-REVISADO"

# Teto de achados no comentário. Um revisor que despeja quarenta apontamentos
# não é lido — e o valor dele é justamente ser lido.
TETO_DE_ACHADOS = 6

# Segundos para cada conversa com o GitHub. A pista atende um PR por vez: um
# revisor lento vira fila, e fila é o problema que a pista existe para resolver.
TIMEOUT_PADRAO = 40

# A escapatória, e ela é deliberada. Um arquivo (ou um bloco) que fale SOBRE
# testes ruins — este próprio programa, os testes dele, um corpus de exemplo —
# dispara as heurísticas de propósito. Como o revisor OPINA e não reprova,
# silenciá-lo não afrouxa portão nenhum: não há nada aqui para contornar.
DISPENSA = "revisor-de-pouso: ignorar"


# =============================================================================
# 1. LER O DIFF — o lado NOVO das linhas, e nada além disso
# =============================================================================


@dataclass
class Linha:
    """Uma linha do lado NOVO do arquivo, com o número que ela terá lá."""

    numero: int
    texto: str
    adicionada: bool


@dataclass
class Bloco:
    """Um pedaço contíguo de arquivo com nome — quase sempre uma função."""

    arquivo: str
    nome: str
    linhas: list[Linha] = field(default_factory=list)

    @property
    def tem_linha_nova(self) -> bool:
        return any(linha.adicionada for linha in self.linhas)

    @property
    def texto(self) -> str:
        return "\n".join(linha.texto for linha in self.linhas)

    @property
    def dispensado(self) -> bool:
        return DISPENSA in self.texto


CABECALHO_DE_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@ ?(.*)$")
# `re.M` não é enfeite: sem ele o `^` só casa no início do patch INTEIRO, e o
# `finditer` de `arquivos_do_diff` devolvia sempre lista vazia — o D4 nunca
# disparava, em silêncio. Pego no primeiro ensaio; é a razão de
# `test_d4_*` existir com um caso que o vê disparando.
CAMINHO_NOVO = re.compile(r"^\+\+\+ b/(.*)$", re.M)
NOME_DE_FUNCAO = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)")


def blocos_do_diff(patch: str) -> list[Bloco]:
    """Fatia o patch unificado em blocos nomeados do lado NOVO.

    Só o lado novo interessa: o revisor julga o código que vai entrar, não o que
    sai. Linhas removidas são descartadas de propósito.

    O nome do bloco vem, nesta ordem: (1) de um `def` que apareça dentro do
    próprio hunk; (2) do contexto de função que o git escreve no cabeçalho do
    hunk (`@@ ... @@ def test_alguma_coisa`), que é o que salva o caso comum de
    um diff pequeno no meio de uma função grande; (3) do próprio arquivo.
    """
    blocos: list[Bloco] = []
    arquivo = ""
    corrente: Bloco | None = None
    numero = 0
    contexto_do_hunk = ""

    for bruta in patch.splitlines():
        casa_caminho = CAMINHO_NOVO.match(bruta)
        if casa_caminho:
            arquivo = casa_caminho.group(1).strip()
            corrente = None
            continue
        if bruta.startswith(("--- ", "diff --git ", "index ", "similarity ")):
            continue

        casa_hunk = CABECALHO_DE_HUNK.match(bruta)
        if casa_hunk:
            numero = int(casa_hunk.group(1))
            contexto_do_hunk = casa_hunk.group(2).strip()
            # Hunk novo = descontinuidade. Fechar o bloco aqui evita costurar
            # duas partes distantes do arquivo numa "função" que não existe.
            corrente = None
            continue

        if not arquivo:
            continue
        if bruta.startswith("-") or bruta.startswith("\\"):
            continue  # linha removida, ou "No newline at end of file"

        if bruta.startswith("+"):
            texto, adicionada = bruta[1:], True
        elif bruta.startswith(" ") or bruta == "":
            texto, adicionada = bruta[1:] if bruta else "", False
        else:
            continue

        casa_def = NOME_DE_FUNCAO.match(texto)
        if casa_def or corrente is None:
            nome = casa_def.group(1) if casa_def else _nome_do_contexto(
                contexto_do_hunk, arquivo
            )
            corrente = Bloco(arquivo=arquivo, nome=nome)
            blocos.append(corrente)

        corrente.linhas.append(Linha(numero=numero, texto=texto, adicionada=adicionada))
        numero += 1

    # A dispensa vale para o ARQUIVO inteiro, não para o bloco onde a marca
    # calhou de cair. É o uso real dela: um arquivo que fala SOBRE testes ruins
    # (este programa, os testes dele, um corpus de exemplo) dispara as
    # heurísticas de propósito, e escondê-la num bloco só faria os vizinhos
    # continuarem gritando. Como o revisor OPINA e não reprova, a marca não
    # afrouxa portão nenhum — não há nada aqui para contornar.
    dispensados = {bloco.arquivo for bloco in blocos if bloco.dispensado}
    return [
        bloco
        for bloco in blocos
        if bloco.tem_linha_nova and bloco.arquivo not in dispensados
    ]


def _nome_do_contexto(contexto: str, arquivo: str) -> str:
    casa = NOME_DE_FUNCAO.match(contexto)
    if casa:
        return casa.group(1)
    return f"(fora de função em {arquivo})"


def arquivos_do_diff(patch: str) -> list[str]:
    return [casa.group(1).strip() for casa in CAMINHO_NOVO.finditer(patch)]


def linhas_novas_de(patch: str, filtro) -> list[tuple[str, Linha]]:
    """Todas as linhas ADICIONADAS dos arquivos que passam pelo filtro."""
    saida: list[tuple[str, Linha]] = []
    for bloco in blocos_do_diff(patch):
        if not filtro(bloco.arquivo):
            continue
        saida.extend(
            (bloco.arquivo, linha) for linha in bloco.linhas if linha.adicionada
        )
    return saida


# =============================================================================
# 2. O VOCABULÁRIO — o que conta como asserção, e de que tipo
# =============================================================================

# Ausência: a asserção afirma que algo NÃO aconteceu, ou que veio vazio. É a
# forma que a família inteira dos seis falsos-verdes assumiu.
AUSENCIA = (
    re.compile(r"==\s*(?:\[\]|\{\}|\(\)|set\(\)|''|\"\")"),
    re.compile(r"==\s*0\b"),
    re.compile(r"\bis\s+None\b"),
    re.compile(r"^\s*assert\s+not\s+\S"),
    re.compile(r"\bnot\s+in\b"),
)

# Presença forte: prova que ALGO aconteceu. Um bloco que tenha uma destas não
# está apoiado só em ausência.
PRESENCA_FORTE = (
    re.compile(r"\bpytest\.raises\b"),
    re.compile(r"\.assert_called"),
    re.compile(r"\bassert_awaited"),
)

DISTINCAO = (
    "filtr",
    "exceto",
    "exclu",
    "apenas",
    "somente",
    "ignor",
    "descart",
    "pula",
    "so_tem",
    "ficaram de fora",
)

# Montagem de dublê: onde o autor DECIDE a resposta que o código vai receber.
DUBLE = (
    "return_value",
    "side_effect",
    "Mock(",
    "MagicMock(",
    "AsyncMock(",
    "monkeypatch.setattr",
    ".setattr(",
    "mock.patch",
    "patch.object",
)

# Sinais de que um teste viu o guarda REPROVANDO. Sem um destes, o guarda só
# foi visto aceitando — e portão que ninguém viu reprovar é indistinguível de
# portão desligado (RETROSPECTIVA-FASE-D §1).
VIU_REPROVAR = (
    "pytest.raises",
    "Estado.FAIL",
    "Estado.ERROR",
    "exit_code == 1",
    "exit_code == 2",
    "returncode == 1",
    "returncode == 2",
    "!= 0",
    "reprov",
    "recus",
    "FAIL",
    "ERROR",
    "assert not ",
    "vermelh",
)

STATUS_HTTP = {"200", "201", "202", "204", "301", "302", "400", "401", "403", "404", "409", "422", "500", "502", "503"}

LITERAL_TEXTO = re.compile(r"[\"']([^\"'\\\n]{4,})[\"']")
LITERAL_NUMERO = re.compile(r"\b(\d{3,})\b")


def _e_teste(arquivo: str) -> bool:
    nome = arquivo.rsplit("/", 1)[-1]
    return (
        nome.startswith("test_")
        or nome.endswith("_test.py")
        or "/tests/" in arquivo
        or "/testes/" in arquivo
    ) and arquivo.endswith(".py")


def _e_guarda_do_ci(arquivo: str) -> bool:
    """Um portão do repositório: mora em `ci/`, e não é o teste dele."""
    return (
        arquivo.startswith("ci/")
        and not arquivo.startswith("ci/tests/")
        and arquivo.endswith((".py", ".sh"))
    )


def _asserts(bloco: Bloco) -> list[Linha]:
    return [
        linha
        for linha in bloco.linhas
        if re.match(r"^\s*assert\b", linha.texto) or "pytest.raises" in linha.texto
    ]


def _e_ausencia(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in AUSENCIA)


def _tem_presenca_forte(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in PRESENCA_FORTE)


def _literais(texto: str) -> set[str]:
    achados = set(LITERAL_TEXTO.findall(texto))
    achados |= {n for n in LITERAL_NUMERO.findall(texto) if n not in STATUS_HTTP}
    return achados


# =============================================================================
# 3. OS DETECTORES — cada um é uma PERGUNTA, nunca um veredito
# =============================================================================


@dataclass
class Achado:
    detector: str
    titulo: str
    arquivo: str
    linha: int
    trecho: str
    pergunta: str
    referencia: str


def d1_ausencia_com_mais_de_uma_causa(bloco: Bloco) -> Achado | None:
    """A família inteira dos seis falsos-verdes de 01/09/2026.

    Régua da `armadilhas/266`: *um teste do tipo "X não aconteceu" só vale se o
    mundo do teste tiver EXATAMENTE UMA razão para X não acontecer.* O sinal
    barato e preciso é um teste cujas asserções são **todas** de ausência: ele
    não tem, em lugar nenhum, a prova de que o cenário conseguiria produzir X
    se a regra não existisse.
    """
    if not _e_teste(bloco.arquivo):
        return None
    asserts = _asserts(bloco)
    if not asserts:
        return None
    # A presença forte se procura no BLOCO INTEIRO, não entre os `assert`. Um
    # `rota.assert_called_once()` não começa com a palavra `assert` e nunca
    # entraria em `_asserts` — a saída ficava inalcançável, e uma regra que
    # nunca roda é enfeite com cara de proteção. Achado pela prova por mutação
    # deste próprio PR: as mutações M6 e M7 saíam VERDES.
    if any(_tem_presenca_forte(linha.texto) for linha in bloco.linhas):
        return None
    if not all(_e_ausencia(linha.texto) for linha in asserts):
        return None
    alvo = next((linha for linha in asserts if linha.adicionada), asserts[0])
    return Achado(
        detector="D1",
        titulo="asserção de ausência com mais de uma causa suficiente",
        arquivo=bloco.arquivo,
        linha=alvo.numero,
        trecho=alvo.texto.strip(),
        pergunta=(
            "Todas as asserções deste teste afirmam que algo **não** aconteceu, e "
            "nenhuma prova que o cenário conseguiria fazer acontecer. Quantos "
            "caminhos independentes deixam esse vazio? Se o mundo do teste já "
            "garantia o vazio por outro motivo (uma variável de ambiente ausente, "
            "um cliente que desiste antes, um dublê que nunca chega a ser "
            "chamado), ele fica verde do mesmo jeito com a regra arrancada do "
            "código."
        ),
        referencia="armadilhas/266",
    )


def d2_filtro_com_um_lado_so(bloco: Bloco) -> Achado | None:
    """`armadilhas/267` — um filtro tem duas saídas; um cenário com uma só não
    prova qual delas você implementou.

    O sinal: o teste anuncia uma distinção (no nome ou no corpo) e afirma que o
    grupo cortado está VAZIO. É exatamente o ponto onde as duas implementações
    concordam.
    """
    if not _e_teste(bloco.arquivo):
        return None
    texto = bloco.texto.lower()
    if not any(palavra in texto or palavra in bloco.nome.lower() for palavra in DISTINCAO):
        return None
    for linha in bloco.linhas:
        if not re.match(r"^\s*assert\b", linha.texto):
            continue
        if not re.search(r"\(0\)|==\s*0\b|==\s*\[\]", linha.texto):
            continue
        return Achado(
            detector="D2",
            titulo="filtro provado por um lado só do filtro",
            arquivo=bloco.arquivo,
            linha=linha.numero,
            trecho=linha.texto.strip(),
            pergunta=(
                "Este teste anuncia uma distinção (incluir uns, cortar outros) e "
                "afirma que o grupo cortado está **vazio**. Nesse ponto as duas "
                "implementações concordam: a certa e a errada produzem a mesma "
                "lista vazia. Ponha na MESMA cena alguém que o filtro corta de "
                "verdade e confira o grupo dos cortados por número **e** por nome."
            ),
            referencia="armadilhas/267",
        )
    return None


def d3_a_assercao_mede_o_duble(bloco: Bloco) -> Achado | None:
    """O valor afirmado é o mesmo que o autor mandou o dublê devolver.

    Nem sempre é defeito — às vezes o caminho de ida e volta é justamente o que
    se quer provar. Mas é sempre uma pergunta que vale ser feita em voz alta: se
    o código sob teste sumisse, esta asserção mudaria?
    """
    if not _e_teste(bloco.arquivo):
        return None
    do_duble: set[str] = set()
    for linha in bloco.linhas:
        if any(marca in linha.texto for marca in DUBLE):
            do_duble |= _literais(linha.texto)
    if not do_duble:
        return None
    for linha in bloco.linhas:
        if not re.match(r"^\s*assert\b", linha.texto):
            continue
        # O mais LONGO primeiro: `"1499 reais"` diz mais a quem lê do que o
        # `1499` que mora dentro dele, e um recado que obriga a procurar o que
        # ele quis dizer não é lido.
        repetidos = sorted(do_duble & _literais(linha.texto), key=len, reverse=True)
        if not repetidos:
            continue
        return Achado(
            detector="D3",
            titulo="a asserção mede o dublê, não o código",
            arquivo=bloco.arquivo,
            linha=linha.numero,
            trecho=linha.texto.strip(),
            pergunta=(
                f"O valor `{repetidos[0]}` foi decidido pelo próprio teste, num "
                "dublê deste mesmo bloco, e é ele que a asserção confere. Se o "
                "código sob teste devolvesse a resposta sem passar por lugar "
                "nenhum, esta linha mudaria? Se não mudaria, ela está medindo o "
                "que você mesmo escreveu."
            ),
            referencia="RETROSPECTIVA-FASE-D §1",
        )
    return None


def d4_guarda_nunca_visto_reprovando(patch: str) -> Achado | None:
    """Portão novo em `ci/` sem nenhum teste que o veja RECUSAR.

    *"Um portão que nunca foi visto reprovando é um portão que ninguém sabe se
    reprova"* — RETROSPECTIVA-FASE-D §1, que exige os três casos: aceita o
    certo · recusa o errado **e diz o quê** · erro de instrumento vira ERROR.
    A catraca de testes já cobra que o teste EXISTA; ninguém cobra que ele tenha
    visto o vermelho.
    """
    guardas = sorted({arq for arq in arquivos_do_diff(patch) if _e_guarda_do_ci(arq)})
    if not guardas:
        return None
    linhas_de_teste = linhas_novas_de(patch, _e_teste)
    if any(
        marca in linha.texto for _, linha in linhas_de_teste for marca in VIU_REPROVAR
    ):
        return None
    primeira = linhas_de_teste[0] if linhas_de_teste else None
    return Achado(
        detector="D4",
        titulo="guarda novo que ninguém viu reprovando",
        arquivo=primeira[0] if primeira else guardas[0],
        linha=primeira[1].numero if primeira else 1,
        trecho=(
            primeira[1].texto.strip()
            if primeira
            else f"(nenhuma linha nova de teste para {guardas[0]})"
        ),
        pergunta=(
            "Este PR mexe em portão do repositório ("
            + ", ".join(f"`{g}`" for g in guardas[:3])
            + ") e nenhuma linha nova de teste mostra o portão **recusando** algo. "
            "Um portão que ninguém viu reprovar é indistinguível de um portão "
            "desligado. Os três casos que a casa pede: aceita o certo · recusa o "
            "errado **e diz o quê** · erro de instrumento vira ERROR."
        ),
        referencia="RETROSPECTIVA-FASE-D §1",
    )


DETECTORES_DE_BLOCO = (
    d1_ausencia_com_mais_de_uma_causa,
    d2_filtro_com_um_lado_so,
    d3_a_assercao_mede_o_duble,
)


def revisar(patch: str) -> list[Achado]:
    """Um achado por bloco, no máximo — o primeiro detector que casar.

    O teto por bloco é de propósito: três apontamentos sobre a mesma função de
    teste não são três informações, são uma informação repetida três vezes, e é
    assim que um revisor deixa de ser lido.
    """
    achados: list[Achado] = []
    for bloco in blocos_do_diff(patch):
        for detector in DETECTORES_DE_BLOCO:
            achado = detector(bloco)
            if achado is not None:
                achados.append(achado)
                break
    do_pr = d4_guarda_nunca_visto_reprovando(patch)
    if do_pr is not None:
        achados.append(do_pr)
    return achados


# =============================================================================
# 4. O VEREDITO — escrito para quem vai ler depois, não despejo de log
# =============================================================================

ABERTURA = (
    "🔍 **revisor de pouso** — li o diff deste PR com contexto fresco, no "
    "instante do merge, procurando a família que os portões desta casa não "
    "pegam: **asserção com mais de uma causa suficiente**, o falso-verde que "
    "aparece seis vezes nas `armadilhas/264` a `272`."
)

RODAPE = (
    "*Isto é opinião, não reprovação: o pouso segue normalmente. A prova de "
    "verdade continua sendo a sua — arranque a regra que cada guarda protege e "
    "confira que o vermelho diz o NOME do teste que caiu, senão foi outro guarda "
    "que respondeu (`armadilhas/268`).*"
)

O_QUE_FOI_OLHADO = (
    "O que eu olhei: asserção de ausência sem contraprova (`armadilhas/266`) · "
    "filtro provado por um lado só (`armadilhas/267`) · asserção que confere o "
    "dublê em vez do código · portão novo que nenhum teste viu recusar."
)


def comentario(numero: int, achados: list[Achado]) -> str:
    if not achados:
        return (
            f"{ABERTURA}\n\n"
            "**Nada a apontar.** " + O_QUE_FOI_OLHADO + "\n\n"
            "*Este recado existe para que \"revisei e não achei nada\" não se "
            "pareça com \"não rodei\": ausência de evidência nunca é evidência "
            "de sucesso ([INV-CI01]).*"
        )

    mostrados = achados[:TETO_DE_ACHADOS]
    partes = [
        ABERTURA,
        "",
        f"**{len(achados)} ponto(s) para olhar** — opinião, não reprovação: o "
        "pouso segue.",
        "",
    ]
    for indice, achado in enumerate(mostrados, start=1):
        partes.append(
            f"### {indice}. {achado.titulo}\n"
            f"`{achado.arquivo}:{achado.linha}` ({achado.detector})\n\n"
            f"```python\n{achado.trecho}\n```\n\n"
            f"{achado.pergunta}\n\n"
            f"Referência: `{achado.referencia}`."
        )
        partes.append("")
    if len(achados) > len(mostrados):
        partes.append(
            f"*(e mais {len(achados) - len(mostrados)}; mostro os "
            f"{TETO_DE_ACHADOS} primeiros para este recado continuar sendo "
            "lido)*"
        )
        partes.append("")
    partes.append(RODAPE)
    return "\n".join(partes)


# =============================================================================
# 5. AS BORDAS — e todas elas são fail-open
# =============================================================================


def ler_diff(numero: int, raiz: Path, timeout: int) -> str:
    """O diff do PR, pelo `gh`. Levanta ErroDeInstrumentacao se não der."""
    execucao = executar(
        ["gh", "pr", "diff", str(numero)],
        cwd=raiz,
        descricao=f"ler o diff do PR #{numero}",
        timeout=timeout,
    )
    return execucao.stdout


def comentar(numero: int, raiz: Path, texto: str, timeout: int) -> None:
    """Publica o veredito no PR, por arquivo e FORA da árvore do repositório.

    Por `--body-file`: o corpo tem markdown, quebras de linha e acentos, e
    passá-lo como argumento de linha de comando é onde escape se perde.

    Fora da árvore porque este processo pode ser MORTO pelo `timeout` da pista
    no meio do caminho. Um temporário na raiz sobreviveria ao revisor e sujaria
    a árvore de quem o chamou — e quem o chama é a máquina que faz todo PR
    desta casa pousar.
    """
    with tempfile.TemporaryDirectory(prefix="revisor-de-pouso-") as pasta:
        alvo = Path(pasta) / f"veredito-{numero}.md"
        alvo.write_text(texto, encoding="utf-8")
        executar(
            ["gh", "pr", "comment", str(numero), "--body-file", str(alvo)],
            cwd=raiz,
            descricao=f"comentar o veredito no PR #{numero}",
            timeout=timeout,
        )


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Revisor de pouso — opina sobre o diff, nunca reprova (B11)"
    )
    parser.add_argument("pr", type=int, help="número do PR")
    parser.add_argument(
        "--comentar",
        action="store_true",
        help="publica o veredito como comentário no PR (o que a pista faz)",
    )
    parser.add_argument(
        "--diff-de",
        metavar="ARQUIVO",
        help="lê o patch deste arquivo em vez de perguntar ao GitHub "
        "(para teste e para revisar um diff que você já tem em mãos)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_PADRAO,
        help=f"segundos por conversa com o GitHub (padrão: {TIMEOUT_PADRAO})",
    )
    args = parser.parse_args(argv)

    try:
        if args.diff_de:
            patch = Path(args.diff_de).read_text(encoding="utf-8", errors="replace")
            raiz = Path.cwd()
        else:
            raiz = raiz_do_repo()
            patch = ler_diff(args.pr, raiz, args.timeout)
    except (ErroDeInstrumentacao, OSError) as erro:
        return _desistir(f"não consegui ler o diff do PR #{args.pr}: {erro}")

    # Diff vazio é NAO-REVISADO, nunca LIMPO — e a checagem mora AQUI, no
    # caminho comum aos dois modos, porque quando ela morava só dentro do
    # `ler_diff` o `--diff-de` com arquivo vazio saía dizendo "nada a apontar".
    # Ausência de evidência tratada como evidência de sucesso ([INV-CI01]) é o
    # modo de falha nº 1 desta casa, e ele acabara de nascer aqui dentro.
    if not patch.strip():
        return _desistir(
            f"o diff do PR #{args.pr} veio vazio. Um PR sem diff é "
            "indistinguível de uma consulta que falhou em silêncio: não reviso "
            "o nada e não chamo isso de limpo"
        )

    achados = revisar(patch)
    texto = comentario(args.pr, achados)
    print(texto)
    print("")

    if args.comentar:
        try:
            comentar(args.pr, raiz, texto, args.timeout)
            print(f"Veredito publicado no PR #{args.pr}.")
        except (ErroDeInstrumentacao, OSError) as erro:
            return _desistir(f"revisei, mas não consegui comentar no PR: {erro}")

    print(f"{MARCA} {ACHADOS} {len(achados)}" if achados else f"{MARCA} {LIMPO}")
    return 0


def _desistir(motivo: str) -> int:
    """A saída fail-open: diz o que não deu, NÃO fabrica veredito, e sai limpo.

    O exit 0 aqui é a decisão de desenho 2 do cabeçalho, e ela é o oposto de
    esconder o erro: o motivo é impresso e a última linha diz `NAO-REVISADO`,
    que é um veredito escrito. O que não pode existir é "não consegui medir"
    chegando disfarçado de "está limpo".
    """
    print("")
    print(f"NÃO REVISEI ESTE PR — {motivo}")
    print(
        "O pouso segue normalmente: este revisor OPINA, não reprova. "
        "Ninguém fica esperando por ele."
    )
    print(f"{MARCA} {NAO_REVISADO}")
    return 0


def _blindar(funcao):
    """Última linha de defesa: nem uma exceção nossa pode segurar um pouso.

    O `ci/mergear.py` tem a mesma peça, com o desfecho oposto (lá, exceção
    inesperada vira ERROR e recusa o merge). Aqui recusar não é opção: um bug
    NESTE arquivo não pode travar a esteira da casa inteira.
    """

    def blindada(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print("Exceção não tratada dentro do próprio revisor:")
            print(traceback.format_exc())
            return _desistir("o revisor quebrou (o rastro está acima)")

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar(main)())
