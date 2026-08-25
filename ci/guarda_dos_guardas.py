"""GUARDA DOS GUARDAS — o portão que prova que os outros guardas ainda mordem.

    INVARIANTES.md  ──(parse)──►  guarda_dos_guardas  ──(git ls-files)──►  disco
         ▲                                 │
         └────────── FAIL/ERROR ◄──────────┘

O buraco que este portão fecha, medido em 25/08/2026 contra a `main`:

  - `RITOS.md` §2.3 e `INVARIANTES.md` regra 2 dizem "teste-guarda é intocável:
    nunca deletar, desativar ou afrouxar". Isso era **só prosa** — nada media.
  - `INVARIANTES.md` declarava 12 linhas `Teste-Guarda:` (14 caminhos). Nada
    conferia que esses 14 arquivos ainda existiam.
  - 10 células têm `@if [ -f .importlinter ]; then lint-imports; fi` no
    `Makefile`. Só `services/pagamentos/` tem de fato um `.importlinter`.
    Apagar esse arquivo deixava o `make ci` **VERDE** — o `if` some junto com o
    arquivo — e o guarda do INV-P9 evaporava em silêncio, com o step do CI
    ainda se chamando "lint + import-linter + type + testes".

Escada da Imposição (CONSTITUICAO Lei 1): a regra sobe de *documento* para
*portão mecânico*.

AS CINCO REGRAS
---------------
1. **Declaração resolve.** Todo caminho citado numa linha `Teste-Guarda:`
   existe em disco. Uma linha pode citar mais de um.
2. **Guarda `.py` tem teste.** Ao menos um `def test_`.
3. **Guarda `.py` morde.** Nenhum `@pytest.mark.skip/skipif/xfail` (nem
   `pytestmark` de módulo) e nenhum corpo de teste que seja só
   `pass` / `return` / `...` / docstring.
4. **Guarda que não é `.py` existe e tem conteúdo** — e, no caso do
   `.importlinter`, o `Makefile` da célula realmente invoca `lint-imports`.
5. **INVERSO, com catraca.** Todo `services/*/tests/test_inv_*.py` em disco ou
   está declarado no `INVARIANTES.md`, ou está na dívida versionada
   `ci/guardas-nao-declarados.txt`. Guarda novo fora dos dois ⇒ FAIL.

As regras 2 e 3 valem para **todos** os guardas em disco, declarados ou não.
A dívida do item 5 isenta de DECLARAÇÃO, nunca de MORDER — é isso que impede a
lista de virar um interruptor de desligar guarda.

FAIL vs ERROR (INV-CI01)
------------------------
FAIL (1) = medi e encontrei violação. ERROR (2) = não consegui medir: git que
não responde, `INVARIANTES.md` ausente, zero linhas `Teste-Guarda:` parseadas,
zero guardas em disco, arquivo de dívida ausente/malformado, `.py` que não
parseia. Nunca existe caminho "não consegui medir ⇒ PASS".

ONDE ELE RODA
-------------
`ci/tests/test_guarda_dos_guardas.py` chama `rodar()` contra o repositório
real. Os workflows `muralhas` e `alarme-main` já rodam
`python ci/ci.py --apenas testador` (= `pytest ci/tests`), então este portão
roda nos dois **sem editar YAML nenhum**. Ele também está registrado como
portão próprio do runner (`python ci/ci.py --apenas guardas`) para uso local.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

DOCUMENTO = "INVARIANTES.md"
DIVIDA = "ci/guardas-nao-declarados.txt"

# `### [INV-P1] Snapshot ...` — o código do invariante a que o bloco pertence.
RE_CODIGO = re.compile(r"^#{2,4}\s*\[([A-Z0-9\-]+)\]")
# O bloco `- **Teste-Guarda:** ...` vai até o próximo item de lista em negrito,
# até o próximo heading ou até a régua `---`.
RE_BLOCO_GUARDA = re.compile(
    r"^- \*\*Teste-Guarda:\*\*(.*?)(?=^- \*\*|^#{1,6} |^---\s*$)",
    re.MULTILINE | re.DOTALL,
)
# Só conta como CAMINHO o que tem barra e não tem espaço. É o que separa
# `services/pagamentos/.importlinter` de `make ci`, `lint-imports`, `FAIL` e
# de `pix.js`/`cartao.js` (dois tokens de uma barra literal FORA das crases).
RE_TOKEN = re.compile(r"`([^`]+)`")

# O que conta como guarda de célula para o INVERSO (regra 5). Deliberadamente
# mais largo que o disco de hoje (aceita subpasta) — errar para o lado de
# exigir declaração demais é o lado certo.
RE_GUARDA_DE_CELULA = re.compile(r"services/[^/]+/tests/(?:.+/)?test_inv_[^/]+\.py")

# Marcas que desligam um teste. `skipif` entra junto de propósito: um guarda de
# invariante que não roda em algum ambiente é um invariante sem guarda NAQUELE
# ambiente — e o INV-CI01 já diz que SKIP só existe quando alguém o declarou
# por escrito. Hoje a linha de base tem ZERO ocorrências das três; travá-la
# agora custa nada e impede a primeira.
MARCAS_QUE_DESLIGAM = frozenset({"skip", "skipif", "xfail"})

# Motivo abaixo disso é carimbo, não motivo.
MOTIVO_MINIMO = 15
SEPARADOR_DA_DIVIDA = "::"
RE_TOTAL = re.compile(r"^#\s*TOTAL:\s*(\d+)\s*$", re.MULTILINE)


# --------------------------------------------------------------- o varredor


def arquivos_versionados(raiz: Path) -> list[str]:
    """Os arquivos que o GIT rastreia, em caminho posix relativo à raiz.

    Por que perguntar ao git em vez de andar no disco: `Path.rglob("*")` entra
    em `.claude/worktrees/`, onde o harness do agente guarda worktrees de
    OUTRAS sessões. Isso já produziu um vermelho real e invisível — o
    `test_toda_referencia_a_uma_armadilha_resolve` acusava três vezes a
    sentinela `§99.99` do próprio fixture, copiada dentro de worktrees velhos.
    No runner do GitHub essas pastas não existem, então o furo era mudo na CI e
    barulhento na máquina do agente: a receita para um guarda que todo mundo
    aprende a ignorar.

    Uma lista de pastas a pular resolveria o caso e não a classe (a próxima
    ferramenta inventa outra pasta). O git já sabe a resposta certa: o que ele
    rastreia é o repositório; o resto é lixo de máquina.

    Consequência aceita e documentada: arquivo criado e ainda NÃO adicionado ao
    índice é invisível para este varredor. O rito da casa manda `git add` por
    arquivo antes de qualquer coisa, e na CI tudo está commitado — mas se você
    está rodando o portão local com arquivo novo, `git add` primeiro.

    Falha do git é ERROR, nunca lista vazia: `executar` levanta
    `ErroDeInstrumentacao` em exit != 0, comando ausente ou stdout vazio.
    """
    execucao = executar(
        ["git", "ls-files", "-z", "--cached"],
        cwd=raiz,
        descricao="listar os arquivos versionados (git ls-files)",
        exigir_stdout=True,
    )
    return sorted(p for p in execucao.stdout.split("\0") if p.strip())


# --------------------------------------------------------- parse do documento


@dataclass
class Invariante:
    codigo: str
    guardas: list[str] = field(default_factory=list)


def invariantes_declarados(texto: str) -> list[Invariante]:
    """Os blocos `Teste-Guarda:` do documento, com os caminhos que cada um cita.

    Zero blocos ⇒ `ErroDeInstrumentacao`. Um documento que perdeu a seção (ou
    um regex que parou de casar) não pode virar "nenhuma violação encontrada" —
    seria o falso-verde exato que o INV-CI01 descreve.
    """
    linhas = texto.splitlines()
    codigo_por_posicao: list[str] = []
    atual = "?"
    for linha in linhas:
        achado = RE_CODIGO.match(linha)
        if achado:
            atual = achado.group(1)
        codigo_por_posicao.append(atual)

    # offset de cada linha, para saber a que invariante um bloco pertence
    offsets: list[int] = []
    corrido = 0
    for linha in linhas:
        offsets.append(corrido)
        corrido += len(linha) + 1

    encontrados: list[Invariante] = []
    for bloco in RE_BLOCO_GUARDA.finditer(texto):
        indice = 0
        for numero, offset in enumerate(offsets):
            if offset <= bloco.start():
                indice = numero
            else:
                break
        caminhos = [
            token
            for token in RE_TOKEN.findall(bloco.group(1))
            if "/" in token and not re.search(r"\s", token)
        ]
        encontrados.append(
            Invariante(codigo=codigo_por_posicao[indice], guardas=caminhos)
        )

    if not encontrados:
        raise ErroDeInstrumentacao(
            f"nenhuma linha `Teste-Guarda:` encontrada em {DOCUMENTO}",
            "O documento existe mas o parse não achou um único bloco no formato\n"
            "  - **Teste-Guarda:** `caminho` — descrição\n\n"
            "Ou a seção sumiu, ou o formato mudou. Zero blocos NÃO é zero\n"
            "violações: é o instrumento cego. Conserte o documento ou o parse.",
        )
    sem_caminho = [inv.codigo for inv in encontrados if not inv.guardas]
    if sem_caminho:
        raise ErroDeInstrumentacao(
            f"invariante com `Teste-Guarda:` sem caminho: {', '.join(sem_caminho)}",
            "Um bloco Teste-Guarda que não cita nenhum caminho entre crases é um\n"
            "guarda que este portão não sabe localizar. Cite o arquivo entre\n"
            "crases (ex.: `services/checkout/tests/test_inv_p1_snapshot.py`) ou\n"
            "mova o invariante para a tabela de dívida do fim do documento.",
        )
    return encontrados


# ------------------------------------------------- os dentes de um guarda .py


def _marcas_de_desligar(no: ast.AST) -> list[str]:
    """`pytest.mark.skip` e parentes achados numa árvore de decoradores/valores."""
    achadas = []
    for filho in ast.walk(no):
        if not isinstance(filho, ast.Attribute):
            continue
        if filho.attr not in MARCAS_QUE_DESLIGAM:
            continue
        dono = filho.value
        if isinstance(dono, ast.Attribute) and dono.attr == "mark":
            achadas.append(f"pytest.mark.{filho.attr}")
        elif isinstance(dono, ast.Name) and dono.id == "mark":
            achadas.append(f"mark.{filho.attr}")
    return achadas


def _corpo_vazio(funcao: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """O corpo é só `pass` / `return` / `...` / docstring?"""
    corpo = list(funcao.body)
    if (
        corpo
        and isinstance(corpo[0], ast.Expr)
        and isinstance(corpo[0].value, ast.Constant)
        and isinstance(corpo[0].value.value, str)
    ):
        corpo = corpo[1:]
    if not corpo:
        return True
    for comando in corpo:
        if isinstance(comando, ast.Pass):
            continue
        if isinstance(comando, ast.Return) and (
            comando.value is None or isinstance(comando.value, ast.Constant)
        ):
            continue
        if isinstance(comando, ast.Expr) and isinstance(comando.value, ast.Constant):
            continue
        return False
    return True


def problemas_do_guarda(caminho: Path, relativo: str) -> list[str]:
    """As regras 2 e 3 aplicadas a UM arquivo `.py`. Lista vazia = está mordendo.

    Erro de parse levanta `ErroDeInstrumentacao`: um guarda que o Python não
    consegue ler não é um guarda aprovado, é uma medição impossível.
    """
    try:
        fonte = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"não foi possível ler o guarda {relativo}", str(exc)
        ) from exc
    try:
        arvore = ast.parse(fonte, filename=str(caminho))
    except SyntaxError as exc:
        raise ErroDeInstrumentacao(
            f"o guarda {relativo} não parseia como Python",
            f"{exc}\n\nArquivo ilegível não é arquivo aprovado.",
        ) from exc

    problemas: list[str] = []

    for comando in arvore.body:
        if isinstance(comando, (ast.Assign, ast.AnnAssign)):
            alvos = (
                comando.targets if isinstance(comando, ast.Assign) else [comando.target]
            )
            nomes = {a.id for a in alvos if isinstance(a, ast.Name)}
            if "pytestmark" in nomes and comando.value is not None:
                for marca in _marcas_de_desligar(comando.value):
                    problemas.append(f"`pytestmark` de módulo com `{marca}`")

    funcoes = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
        and no.name.startswith("test_")
    ]
    if not funcoes:
        problemas.append("nenhum `def test_` — o arquivo existe mas não testa nada")

    for funcao in funcoes:
        for decorador in funcao.decorator_list:
            for marca in _marcas_de_desligar(decorador):
                problemas.append(f"`{funcao.name}` decorado com `{marca}`")
        if _corpo_vazio(funcao):
            problemas.append(
                f"`{funcao.name}` tem corpo vazio (só pass/return/.../docstring)"
            )
    return problemas


# -------------------------------------------------------------- a catraca


@dataclass
class Divida:
    caminhos: dict[str, str]  # caminho -> motivo
    total_declarado: int


def ler_divida(raiz: Path) -> Divida:
    """Lê `ci/guardas-nao-declarados.txt`. Qualquer malformação é ERROR.

    Ausente ⇒ ERROR, nunca "dívida vazia": apagar o arquivo não pode ser um
    caminho para ficar verde. Motivo curto ou ausente ⇒ ERROR, pelo mesmo
    motivo que o INV-CI01 exige motivo escrito para um SKIP.
    """
    caminho = raiz / DIVIDA
    if not caminho.is_file():
        raise ErroDeInstrumentacao(
            f"arquivo de dívida ausente: {DIVIDA}",
            "Ele é a linha de base da catraca do item 5. Sem ele o portão não\n"
            "sabe o que já era dívida reconhecida e o que é dívida NOVA —\n"
            "e tratar isso como 'nenhuma dívida' aprovaria qualquer guarda\n"
            "não declarado. Restaure o arquivo (ele é versionado).",
        )
    texto = caminho.read_text(encoding="utf-8")
    achado = RE_TOTAL.search(texto)
    if achado is None:
        raise ErroDeInstrumentacao(
            f"{DIVIDA} sem a linha `# TOTAL: <n>`",
            "O total existe para que acrescentar uma linha exija editar DOIS\n"
            "lugares: a linha nova e o número. O diff então mostra, em texto,\n"
            "que a dívida cresceu — que é justamente o que não deve acontecer.",
        )
    total = int(achado.group(1))

    caminhos: dict[str, str] = {}
    for numero, linha in enumerate(texto.splitlines(), start=1):
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        if SEPARADOR_DA_DIVIDA not in limpa:
            raise ErroDeInstrumentacao(
                f"{DIVIDA}:{numero} sem motivo escrito",
                f"Linha: {limpa!r}\n\nFormato: `caminho :: motivo`. Dívida sem\n"
                "motivo é carimbo; o motivo é o que a próxima sessão lê para\n"
                "saber se pode quitá-la.",
            )
        alvo, _, motivo = limpa.partition(SEPARADOR_DA_DIVIDA)
        alvo, motivo = alvo.strip(), motivo.strip()
        if not RE_GUARDA_DE_CELULA.fullmatch(alvo):
            raise ErroDeInstrumentacao(
                f"{DIVIDA}:{numero} aponta para algo que não é guarda de célula",
                f"Caminho: {alvo!r}\n\nEsta lista isenta de DECLARAÇÃO um\n"
                "`services/<celula>/tests/test_inv_*.py`, e mais nada. Usá-la\n"
                "para calar outra coisa a transformaria num interruptor geral.",
            )
        if len(motivo) < MOTIVO_MINIMO:
            raise ErroDeInstrumentacao(
                f"{DIVIDA}:{numero} com motivo de carimbo",
                f"Motivo: {motivo!r} ({len(motivo)} caracteres; mínimo "
                f"{MOTIVO_MINIMO}).\nEscreva por que o invariante ainda não foi "
                "redigido em INVARIANTES.md.",
            )
        if alvo in caminhos:
            raise ErroDeInstrumentacao(
                f"{DIVIDA}:{numero} repete o caminho {alvo}",
                "Caminho duplicado torna o TOTAL mentiroso e esconde uma linha.",
            )
        caminhos[alvo] = motivo

    if len(caminhos) != total:
        raise ErroDeInstrumentacao(
            f"{DIVIDA}: TOTAL diz {total}, mas há {len(caminhos)} linhas",
            "Os dois números têm de bater. Se você acrescentou uma linha, o\n"
            "TOTAL sobe junto — e é exatamente esse `-# TOTAL: n` / `+# TOTAL: n+1`\n"
            "no diff que denuncia dívida crescendo em vez de encolhendo.",
        )
    return Divida(caminhos=caminhos, total_declarado=total)


# ------------------------------------------------------------------ o portão


def _regra_declaracao(
    raiz: Path, invariantes: list[Invariante]
) -> tuple[Resultado, list[str]]:
    faltando: list[str] = []
    declarados: list[str] = []
    for inv in invariantes:
        for alvo in inv.guardas:
            declarados.append(alvo)
            if not (raiz / alvo).is_file():
                faltando.append(f"[{inv.codigo}] {alvo}")
    if faltando:
        return (
            Resultado(
                "guardas/declaracao",
                Estado.FAIL,
                f"{len(faltando)} guarda(s) declarado(s) que não existem em disco",
                "Teste-Guarda citado em INVARIANTES.md e ausente do disco:\n  "
                + "\n  ".join(faltando)
                + "\n\nOu o arquivo foi apagado/renomeado sem atualizar o documento\n"
                "(e aí um invariante ficou sem guarda — RITOS.md §2.3 proíbe), ou\n"
                "o documento cita um caminho errado. Nos dois casos, a lei está\n"
                "sem mecanismo até isto ser consertado.",
            ),
            declarados,
        )
    return (
        Resultado(
            "guardas/declaracao",
            Estado.PASS,
            f"{len(declarados)} guardas declarados em {len(invariantes)} invariantes, "
            "todos em disco",
        ),
        declarados,
    )


def _regra_dentes(raiz: Path, alvos: list[str]) -> Resultado:
    problemas: list[str] = []
    for alvo in alvos:
        for queixa in problemas_do_guarda(raiz / alvo, alvo):
            problemas.append(f"{alvo}: {queixa}")
    if problemas:
        return Resultado(
            "guardas/dentes",
            Estado.FAIL,
            f"{len(problemas)} guarda(s) desativado(s) ou esvaziado(s)",
            "Guardas que existem mas deixaram de morder:\n  "
            + "\n  ".join(problemas)
            + "\n\nRITOS.md §2.3: proibido deletar, desativar, comentar ou afrouxar\n"
            "teste para passar. Se o guarda está quebrado, conserte o CÓDIGO que\n"
            "ele acusa — desligar o guarda transforma a lei em decoração.\n"
            "Se você acredita que este guarda precisa mesmo de um skip, isso é\n"
            "conversa com o mantenedor, não uma decisão de sessão.",
        )
    return Resultado(
        "guardas/dentes",
        Estado.PASS,
        f"{len(alvos)} guardas .py com teste de verdade, sem skip/xfail",
    )


def _regra_nao_python(raiz: Path, alvos: list[str]) -> Resultado:
    problemas: list[str] = []
    for alvo in alvos:
        caminho = raiz / alvo
        if not caminho.is_file():
            problemas.append(f"{alvo}: ausente")
            continue
        try:
            conteudo = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ErroDeInstrumentacao(f"não consegui ler {alvo}", str(exc)) from exc
        if not conteudo.strip():
            problemas.append(f"{alvo}: existe mas está vazio")
            continue
        if caminho.name == ".importlinter":
            if "[importlinter" not in conteudo:
                problemas.append(
                    f"{alvo}: sem nenhuma seção `[importlinter...]` — não declara contrato"
                )
            makefile = caminho.parent / "Makefile"
            if not makefile.is_file():
                problemas.append(
                    f"{alvo}: a célula não tem Makefile — nada invoca `lint-imports`"
                )
            elif "lint-imports" not in makefile.read_text(
                encoding="utf-8", errors="replace"
            ):
                problemas.append(
                    f"{alvo}: o Makefile de {caminho.parent.name} não invoca "
                    "`lint-imports` — o arquivo existe e ninguém o roda"
                )
    if problemas:
        return Resultado(
            "guardas/nao-python",
            Estado.FAIL,
            f"{len(problemas)} guarda(s) fora do pytest sem dentes",
            "Guardas declarados que não são `.py` e não estão em ordem:\n  "
            + "\n  ".join(problemas)
            + "\n\nO caso que deu origem a esta regra: o `Makefile` de 10 células\n"
            "roda `@if [ -f .importlinter ]; then lint-imports; fi`. Apagar o\n"
            "`.importlinter` faz o `if` sumir junto — `make ci` fica VERDE e o\n"
            "guarda do INV-P9 evapora sem uma linha de aviso. Este portão é o\n"
            "único lugar de onde isso se enxerga.",
        )
    return Resultado(
        "guardas/nao-python",
        Estado.PASS,
        f"{len(alvos)} guardas fora do pytest existem, têm conteúdo e são invocados",
    )


def _regra_inverso(
    em_disco: list[str], declarados: set[str], divida: Divida
) -> Resultado:
    nao_declarados = [alvo for alvo in em_disco if alvo not in declarados]
    novos = [alvo for alvo in nao_declarados if alvo not in divida.caminhos]
    quitados = sorted(set(divida.caminhos) - set(nao_declarados))

    if novos:
        return Resultado(
            "guardas/inverso",
            Estado.FAIL,
            f"{len(novos)} guarda(s) em disco sem invariante declarado e fora da dívida",
            "Guarda de célula que não está no INVARIANTES.md nem na dívida:\n  "
            + "\n  ".join(sorted(novos))
            + "\n\nUm arquivo chamado `test_inv_*` promete guardar um invariante.\n"
            "Se o invariante não está escrito, ninguém sabe o que ele guarda —\n"
            "e no dia em que o teste for apagado nada vai reclamar.\n\n"
            "O CERTO: escreva o invariante em INVARIANTES.md no formato\n"
            "  - **Teste-Guarda:** `caminho` — o que ele prova\n"
            "(caminho CODEOWNERS: precisa de mandato do despacho).\n\n"
            f"O ACEITÁVEL, se o despacho não comporta: acrescente a linha em {DIVIDA}\n"
            "no formato `caminho :: motivo` E suba o `# TOTAL:` na mesma edição.\n"
            "A dívida existe para encolher — cada linha nova aparece no diff\n"
            "como uma promessa que alguém vai ter de pagar.",
        )

    resumo = (
        f"{len(em_disco)} guardas de célula em disco: "
        f"{len(em_disco) - len(nao_declarados)} declarados, "
        f"{len(nao_declarados)} na dívida versionada"
    )
    if quitados:
        resumo += f" ({len(quitados)} linha(s) da dívida já quitada(s))"
    return Resultado("guardas/inverso", Estado.PASS, resumo)


def rodar(raiz: Path | None = None) -> Relatorio:
    """O portão inteiro. Devolve `Relatorio` — o pior estado vence."""
    relatorio = Relatorio("GUARDA DOS GUARDAS — os guardas ainda mordem?")
    try:
        raiz = raiz or raiz_do_repo()
        documento = raiz / DOCUMENTO
        if not documento.is_file():
            raise ErroDeInstrumentacao(
                f"{DOCUMENTO} não encontrado",
                f"Esperado em:\n  {documento}\n\nSem o documento não há o que\n"
                "verificar — e 'nada a verificar' não é 'tudo em ordem'.",
            )
        invariantes = invariantes_declarados(documento.read_text(encoding="utf-8"))
        versionados = arquivos_versionados(raiz)
        divida = ler_divida(raiz)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("guarda-dos-guardas", erro))
        return relatorio

    em_disco = sorted(
        alvo
        for alvo in versionados
        if RE_GUARDA_DE_CELULA.fullmatch(alvo) and (raiz / alvo).is_file()
    )
    if not em_disco:
        relatorio.registrar(
            Resultado(
                "guarda-dos-guardas",
                Estado.ERROR,
                "nenhum `services/*/tests/test_inv_*.py` versionado",
                "O git respondeu, mas o padrão de guarda de célula não casou com\n"
                "arquivo nenhum. Zero guardas em disco não é 'tudo declarado' —\n"
                "é o instrumento medindo a coisa errada (raiz? padrão? worktree\n"
                "vazio?). INV-CI01: não medir nunca é PASS.",
            )
        )
        return relatorio

    try:
        resultado_declaracao, declarados = _regra_declaracao(raiz, invariantes)
        relatorio.registrar(resultado_declaracao)

        # Regras 2 e 3 valem para TODOS os guardas .py — declarados ou na
        # dívida. A dívida isenta de declaração, nunca de morder.
        alvos_py = sorted(
            {alvo for alvo in declarados if alvo.endswith(".py")} | set(em_disco)
        )
        alvos_py = [alvo for alvo in alvos_py if (raiz / alvo).is_file()]
        relatorio.registrar(_regra_dentes(raiz, alvos_py))

        alvos_outros = sorted({alvo for alvo in declarados if not alvo.endswith(".py")})
        relatorio.registrar(_regra_nao_python(raiz, alvos_outros))

        relatorio.registrar(_regra_inverso(em_disco, set(declarados), divida))
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("guarda-dos-guardas", erro))
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Guarda dos guardas — INVARIANTES.md × disco [INV-CI01]"
    )
    parser.add_argument(
        "--raiz", default=None, help="raiz do repositório (padrão: detectar)"
    )
    args = parser.parse_args(argv)
    relatorio = rodar(Path(args.raiz).resolve() if args.raiz else None)
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — a fronteira do processo é aqui
        import traceback

        print("")
        print("ERROR guarda-dos-guardas: exceção não tratada dentro do portão.")
        print(traceback.format_exc())
        print(
            "A medição NÃO foi concluída. Isto não é PASS nem FAIL: nada foi "
            "provado sobre os guardas."
        )
        raise SystemExit(2)
