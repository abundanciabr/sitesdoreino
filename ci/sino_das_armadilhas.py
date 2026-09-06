#!/usr/bin/env python3
"""O SINO DAS ARMADILHAS — a saída do comando reconhece a lição e a chama.

Por que ele existe (29/08/2026): a maior parte do catálogo não é erro de digitar
comando — é conhecimento de arquitetura (Django, Traefik, testes, migrations)
que só se manifesta DEPOIS que o comando roda. Muralha não serve para isso: não
há o que recusar. Mas o erro traz uma assinatura, e a lição está catalogada por
essa mesma assinatura desde que o `INDICE.md` existe. O que faltava era alguém
dar o Ctrl+F — hoje isso depende de o agente lembrar que o catálogo existe, e é
justamente aí que se perde a rodada cara: investigar do zero algo que já custou
caro uma vez.

O sino compara a saída de cada comando com as assinaturas declaradas nas
entradas (campo `sinal` do frontmatter, compiladas em `armadilhas/SINAIS.json`
pelo gerador) e, quando reconhece, ENTREGA a lição ali mesmo: a `licao` do
frontmatter, o sintoma, a causa e a solução, com o endereço junto para quem
precisar do caso inteiro. Até 06/09/2026 ele entregava só o endereço, e o preço
disso está medido no bloco "A LIÇÃO VEM JUNTO", mais abaixo.

FAIL-OPEN, ao contrário das muralhas — e a assimetria é a lei da autoridade
proporcional à certeza, não descuido:

    muralha IMPEDE  ⇒ na dúvida, impede (erro interno vira recusa)
    sino  ACONSELHA ⇒ na dúvida, CALA   (erro interno vira silêncio)

Um conselho que trava a sessão seria pior que conselho nenhum. Por isso o
`main()` inteiro engole a própria falha: SINAIS.json ausente, JSON quebrado,
formato inesperado de resposta — tudo vira exit 0 e silêncio.

O CANAL (documentação oficial de hooks, conferida em 29/08/2026): exit 0 e o
texto em `hookSpecificOutput.additionalContext`. A documentação avisa que
`additionalContext` no TOPO do JSON é ignorado EM SILÊNCIO — falso-verde
perfeito: o sino pareceria funcionar e nunca falaria com ninguém. Há teste-guarda
para o aninhamento por causa disso.

O que ele NÃO cobre, declarado (a documentação não responde, e supor seria a
armadilhas/104): comando em segundo plano pode não passar por PostToolUse; e a
forma exata de `tool_response` para o Bash não é documentada — por isso a
extração abaixo é defensiva, e o silêncio nunca é lido como "nada aconteceu".
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:  # fail-open: sem caderninho o sino ensina toda vez, nunca cala por isso
    import telemetria
except Exception:  # pragma: no cover - só num checkout quebrado
    telemetria = None

RAIZ = Path(__file__).resolve().parents[1]
SINAIS = RAIZ / "armadilhas" / "SINAIS.json"
GATILHOS = RAIZ / "armadilhas" / "GATILHOS.json"

TETO_DA_SAIDA = 200_000  # o erro mora no fim; log de build inteiro não é regex
MAXIMO_DE_TOQUES = 3
TETO_DO_TRECHO = 120
TETO_DO_RESUMO = 1500  # por armadilha; ver "A LIÇÃO VEM JUNTO" abaixo
EVENTO_ENSINOU = "sino_ensinou"

# Ler o próprio catálogo não pode tocar o sino: o texto do sintoma contém, de
# propósito, a mensagem de erro crua que serve de assinatura.
LENDO_O_CATALOGO = re.compile(
    r"armadilhas[/\\]|INDICE\.md|SINAIS\.json|GUARDAS\.json", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# LER CÓDIGO-FONTE NÃO É SINTOMA (TAR-048, 04/09/2026)
# ---------------------------------------------------------------------------
# Medido em 30/08/2026 (TAR-043) e de novo em 04/09/2026: a assinatura de uma
# armadilha baseada em MENSAGEM aparece, inevitavelmente, no arquivo que imprime
# a mensagem — e em teste, registro do livro, workflow e documento que a citam.
# Na véspera deste conserto, 43 das 81 armadilhas com sinal casavam texto benigno
# do próprio repositório (205 arquivos), e um `cat` em qualquer um deles fazia o
# sino tocar como se a falha estivesse acontecendo. Estreitar o sinal não cura:
# a TAR-043 mediu que leva à cegueira. O que distingue não é o TEXTO, é o
# CONTEXTO em que a saída foi produzida: um comando cuja natureza é LER
# (`cat`, `sed -n`, `head`, `grep`, `git show`) não pode acordar o sino por causa
# do que estava escrito no arquivo.
#
# A régua é FAIL-NOISY, de propósito (barulho se cura estreitando; cegueira não
# se cura): o comando só cala o sino quando TODOS os seus segmentos (separados
# por `|`, `&&`, `||`, `;`, quebra de linha, `$(`, crase) são leitores. Um único
# executor em qualquer ponto do encanamento (`python x.py | grep FAIL`,
# `echo "$(make ci)"`, `find -exec`) mantém o sino acordado, porque aí a saída é
# de uma falha REAL que passou por um filtro. E ler um ARTEFATO DE SAÍDA (`.log`,
# `.out`, a pasta `tasks/` do harness, `/tmp`, scratchpad) também mantém o sino
# acordado: o arquivo carrega a falha de um comando que rodou em segundo plano,
# e é exatamente aí que o hook do PostToolUse pode não ter passado.
#
# O que fica de fora, declarado: o nome do arquivo lido NÃO é conferido contra
# `git ls-files` (o hook roda do espelho, não da bancada, e teria 20 s). A
# aproximação é "leitor + não é artefato de saída"; quem ler um arquivo NÃO
# versionado com `cat` (um `.txt` solto) também cala o sino, e isso é barulho a
# menos, não cegueira: a saída de um `cat` nunca é o evento de uma falha.

# Quem só lê e reescreve fluxo, sem executar código do projeto. Comando fora
# desta lista NÃO é leitor, e o sino continua acordado (a direção segura).
LEITORES = frozenset({
    # unix / Git Bash
    "cat", "tac", "head", "tail", "sed", "grep", "egrep", "fgrep", "rg", "awk",
    "cut", "tr", "sort", "uniq", "wc", "nl", "od", "xxd", "hexdump", "strings",
    "less", "more", "bat", "ls", "dir", "tree", "find", "stat", "file", "du",
    "diff", "cmp", "comm", "column", "paste", "join", "fold", "fmt", "expand",
    "rev", "jq", "yq", "echo", "printf", "true", "false", ":", "test", "[", "[[",
    "cd", "pwd", "pushd", "popd", "which", "type", "basename", "dirname",
    "realpath", "readlink", "date", "whoami", "hostname", "uname",
    "export", "set", "unset", "local", "declare", "read", "shift", "return",
    "break", "continue", "exit", "mkdir", "touch", "tee", "md5sum", "sha256sum",
    "iconv", "sleep",
    # PowerShell (o hook também cobre a ferramenta PowerShell)
    "get-content", "gc", "select-string", "sls", "get-childitem", "gci",
    "get-item", "gi", "test-path", "write-output", "write-host", "select-object",
    "select", "where-object", "where", "?", "foreach-object", "foreach", "%",
    "measure-object", "measure", "sort-object", "out-string", "out-host",
    "format-table", "ft", "format-list", "fl", "get-location", "set-location",
    "resolve-path", "split-path", "join-path", "compare-object", "get-date",
    "new-item",
})
# `git` só é leitor em subcomando que lê. `worktree`, `fetch`, `commit`,
# `push`, `rebase`… produzem saída de EVENTO, e o sino tem de ouvi-los.
LEITORES_DO_GIT = frozenset({
    "show", "diff", "log", "grep", "ls-files", "ls-tree", "status", "blame",
    "cat-file", "rev-parse", "describe", "branch", "tag", "remote", "show-ref",
    "name-rev", "shortlog", "config", "check-ignore", "rev-list",
})
# Invólucros que não executam nada por si: o comando de verdade vem depois.
INVOLUCROS = frozenset({
    "sudo", "env", "nohup", "command", "builtin", "exec", "nice", "time",
    "timeout", "xargs", "stdbuf",
})
# Palavras do shell: nenhuma delas é um comando.
PALAVRAS_QUE_CONSOMEM_O_SEGMENTO = frozenset({"for", "case", "select", "function"})
PALAVRAS_QUE_PRECEDEM_O_COMANDO = frozenset({
    "do", "then", "else", "if", "elif", "while", "until", "!", "{", "(",
})
PALAVRAS_QUE_NAO_SAO_NADA = frozenset({"done", "fi", "}", ")", ";;", "in", "esac"})

# Artefato de saída: quem lê isto está lendo o resultado de um comando REAL.
ARTEFATO_DE_SAIDA = re.compile(
    r"\.(?:log|out|output|err)\b|[/\\]tasks[/\\]|scratchpad|(?:^|[\s/\\])tmp[/\\]"
    r"|[/\\]Temp[/\\]|\$TMPDIR|\$TEMP\b|\$TMP\b|%TEMP%",
    re.IGNORECASE,
)

_SEPARADORES = re.compile(r"\|\||&&|\||;|\n|\$\(|<\(|>\(|`")
_ASPAS_SIMPLES = re.compile(r"'[^']*'")
_ASPAS_DUPLAS = re.compile(r'"((?:[^"\\]|\\.)*)"')
_SUBSTITUICAO = re.compile(r"\$\([^)]*\)|`[^`]*`")
# Guarda a LINHA de abertura (`cat <<'EOF' | python -` ainda executa python) e
# tira só o CORPO, que é texto.
_HEREDOC = re.compile(
    r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n).*?^\s*\3\s*$", re.DOTALL | re.MULTILINE
)
_REDIRECAO = re.compile(r"^(?:\d*[<>]{1,2}&?\d*|&>|\d*>\||<<<?)")
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _sem_texto_literal(comando: str) -> str:
    """Tira o que é TEXTO (corpo de heredoc, aspas simples, aspas duplas) e deixa
    o que é COMANDO — inclusive as substituições `$(…)` que vivem dentro de aspas
    duplas, porque `echo "$(make ci)"` executa."""
    sem_heredoc = _HEREDOC.sub(r"\1", comando)
    sem_simples = _ASPAS_SIMPLES.sub(" ", sem_heredoc)

    def so_as_substituicoes(m) -> str:
        return " " + " ".join(_SUBSTITUICAO.findall(m.group(1))) + " "

    return _ASPAS_DUPLAS.sub(so_as_substituicoes, sem_simples)


def _nome_do_comando(token: str) -> str:
    nome = token.strip().lstrip("\\").rstrip(";")
    nome = nome.replace("\\", "/").rsplit("/", 1)[-1]
    if nome.lower().endswith(".exe"):
        nome = nome[:-4]
    return nome.lower()


def _comando_do_segmento(segmento: str) -> str | None:
    """A palavra de comando de um segmento, ou None se o segmento não executa
    nada (só palavra do shell, atribuição, redirecionamento)."""
    tokens = segmento.split()
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if _REDIRECAO.match(t) or _ATRIBUICAO.match(t):
            i += 1
            continue
        baixo = t.lower()
        if baixo in PALAVRAS_QUE_CONSOMEM_O_SEGMENTO:
            return None
        if baixo in PALAVRAS_QUE_NAO_SAO_NADA or baixo in PALAVRAS_QUE_PRECEDEM_O_COMANDO:
            i += 1
            continue
        nome = _nome_do_comando(t)
        if nome in INVOLUCROS:
            # pula opções e números do invólucro (`timeout 30 python`, `xargs -0 cat`)
            i += 1
            while i < len(tokens) and (
                tokens[i].startswith("-") or tokens[i].isdigit() or _ATRIBUICAO.match(tokens[i])
            ):
                i += 1
            continue
        if nome == "git":
            sub = next((x.lower() for x in tokens[i + 1:] if not x.startswith("-")), "")
            return f"git {sub}"
        if nome == "find" and any(
            x in ("-exec", "-execdir", "-ok", "-okdir", "-delete") for x in tokens
        ):
            return "find -exec"
        return nome
    return None


def e_so_leitura(comando: str) -> bool:
    """O comando inteiro é só LEITURA de arquivo, sem executar código do projeto
    e sem ler artefato de saída de outro comando?

    Fail-noisy: na dúvida (segmento que não reconheço, executor em qualquer
    ponto do encanamento, `.log`), responde False e o sino continua acordado.
    """
    if not comando or not comando.strip():
        return False
    limpo = _sem_texto_literal(comando)
    if ARTEFATO_DE_SAIDA.search(limpo):
        return False
    viu_leitor = False
    for segmento in _SEPARADORES.split(limpo):
        nome = _comando_do_segmento(segmento)
        if nome is None:
            continue
        if nome.startswith("git "):
            if nome[4:] not in LEITORES_DO_GIT:
                return False
        elif nome not in LEITORES:
            return False
        viu_leitor = True
    return viu_leitor


# ---------------------------------------------------------------------------
# A LIÇÃO VEM JUNTO, NÃO O ENDEREÇO (06/09/2026)
# ---------------------------------------------------------------------------
# Medido na semana de 06/09/2026: o sino disparou 891 vezes e, em cada uma, ele
# dizia "LEIA armadilhas/NNN". O robô então gastava UMA CHAMADA INTEIRA — com o
# contexto mediano de 206.460 tokens — para ler um arquivo de 996 bytes em
# média. Foram 4,3% da cota da semana pagando ida e volta, não conhecimento: o
# sino em si custa 227 bytes por disparo, e é barato. Caro é o que ele obriga a
# fazer em seguida.
#
# Agora ele entrega o miolo junto do endereço: a `licao` do frontmatter (quando
# a entrada declarou uma, compilada em GATILHOS.json) e as seções de Sintoma,
# Causa e Solução, com teto de TETO_DO_RESUMO caracteres e corte no fim de um
# parágrafo. O endereço continua na tela para quem precisar do caso inteiro.
#
# UMA VEZ POR SESSÃO, POR ARMADILHA — o mesmo desenho da lição do caminho, e o
# MESMO caderninho (`ci/telemetria.py`, dentro do `.git` comum). A segunda vez
# que a mesma assinatura casar volta a ser só o endereço em uma linha: repetir
# 1.500 caracteres a cada comando seria trocar uma conta cara por outra, e
# ruído é o que faz alguém desligar o mecanismo (a lição da TAR-043).
#
# Os nomes das seções VARIAM no catálogo, e por isso a leitura é por família e
# não por título exato: 327 das 347 entradas escrevem `**Sintoma:**` em negrito
# no início da linha, 20 usam `## Sintoma`, e a cura aparece como "Solução",
# "Como se cura" ou "O que fazer". Entrada que não tem nenhuma das três não
# quebra nada: sai só a lição, ou só o endereço.
#
# FAIL-OPEN como todo o resto deste arquivo: catálogo ausente, JSON corrompido,
# arquivo de armadilha que não existe neste checkout ou erro interno voltam ao
# comportamento de antes (o endereço), nunca ao silêncio e nunca à recusa.

_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.DOTALL)
_TITULO = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_RUBRICA_EM_NEGRITO = re.compile(r"^\*\*([^*\n]{1,90}?)\*\*([:：])?\s*(.*)$")
_ACENTOS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")

# Rótulo entregue -> os começos de nome que valem por ele. A ordem aqui é a
# ordem em que o resumo sai na tela.
RUBRICAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Sintoma", ("sintoma", "o que estava acontecendo", "o que aconteceu",
                 "o que voce ve", "o problema")),
    ("Causa", ("causa", "por que acontece", "por que isso acontece",
               "por que isto acontece")),
    ("Solução", ("solucao", "como se cura", "o que fazer", "a cura", "conserto",
                 "correcao", "a saida", "como curar", "o conserto")),
)


def _normalizar_rubrica(nome: str) -> str:
    limpo = re.sub(r"^\d+(\.\d+)*\s+", "", nome.strip())  # "4.2 Sintoma"
    limpo = limpo.replace("`", "").lower().translate(_ACENTOS)
    return re.sub(r"\s+", " ", limpo).strip(" :.—–-")


def familia_da_rubrica(nome: str) -> str | None:
    """O rótulo que este título/etiqueta representa, ou None se não é rubrica."""
    limpo = _normalizar_rubrica(nome)
    for rotulo, comecos in RUBRICAS:
        for comeco in comecos:
            if limpo == comeco:
                return rotulo
            if limpo.startswith(comeco) and not limpo[len(comeco)].isalnum():
                return rotulo
    return None


def _parece_etiqueta(rotulo: str, dois_pontos: str | None) -> bool:
    """Negrito no começo da linha é ETIQUETA, ou é só ênfase no meio da frase?

    A diferença tem preço medido: a armadilhas/179 escreve
    `**Sintoma.** O PR fica verde …, e ele volta com` e a linha seguinte começa
    em `**três** checks vermelhos`. Tratar esse `**três**` como etiqueta cortava
    o sintoma na segunda linha e entregava meia frase. Etiqueta fecha com `:` ou
    `.`; ênfase, não.
    """
    return bool(dois_pontos) or rotulo.rstrip().endswith((":", ".", "："))


def _segmentos(texto: str):
    """(nome, corpo) de cada trecho rotulado do arquivo, na ordem do documento.

    Um título (`## …`) sempre abre trecho novo. Uma etiqueta em negrito no
    começo da linha abre trecho novo só quando é rubrica conhecida ou quando o
    trecho aberto veio de outra etiqueta — assim `## Solução` sobrevive inteira
    às sub-etiquetas em negrito que ela contém.
    """
    texto = _COMENTARIO_HTML.sub("", _FRONTMATTER.sub("", texto))
    nome: str | None = None
    de_negrito = False
    corpo: list[str] = []
    for linha in texto.splitlines():
        titulo = _TITULO.match(linha)
        if titulo:
            if nome is not None:
                yield nome, "\n".join(corpo)
            nome, de_negrito, corpo = titulo.group(1), False, []
            continue
        etiqueta = _RUBRICA_EM_NEGRITO.match(linha)
        if etiqueta and (
            familia_da_rubrica(etiqueta.group(1))
            or ((de_negrito or nome is None)
                and _parece_etiqueta(etiqueta.group(1), etiqueta.group(2)))
        ):
            if nome is not None:
                yield nome, "\n".join(corpo)
            nome, de_negrito, corpo = etiqueta.group(1), True, [etiqueta.group(3)]
            continue
        if nome is not None:
            corpo.append(linha)
    if nome is not None:
        yield nome, "\n".join(corpo)


def secoes_da_armadilha(texto: str) -> dict[str, str]:
    """As seções de Sintoma, Causa e Solução que a entrada realmente tem."""
    achadas: dict[str, str] = {}
    for nome, corpo in _segmentos(texto):
        rotulo = familia_da_rubrica(nome)
        if rotulo and rotulo not in achadas and corpo.strip():
            achadas[rotulo] = corpo.strip()
    return achadas


def _cortar_no_paragrafo(texto: str, teto: int, arquivo: str) -> str:
    """Corte limpo no fim de um parágrafo (ou de uma frase), com o endereço do
    resto. Nunca devolve pedaço vazio: o teto é grande e o piso é 1/3 dele."""
    if len(texto) <= teto:
        return texto
    sufixo = f"\n… o resto em {arquivo}"
    limite = max(teto - len(sufixo), teto // 2)
    recorte = texto[:limite]
    for separador, sobra in (("\n\n", 0), (". ", 1), ("\n", 0)):
        posicao = recorte.rfind(separador)
        if posicao > limite // 3:
            recorte = recorte[: posicao + sobra]
            break
    return recorte.rstrip() + sufixo


def licoes_por_armadilha(caminho: Path = GATILHOS) -> dict[str, str]:
    """A `licao` do frontmatter, por número de armadilha. {} se não der para ler."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return {}
    licoes: dict[str, str] = {}
    for item in dados.get("gatilhos") or []:
        numero, licao = str(item.get("armadilha") or ""), str(item.get("licao") or "")
        if numero and licao and numero not in licoes:
            licoes[numero] = licao.strip()
    return licoes


def resumo_da_armadilha(arquivo: Path, relativo: str, licao: str = "") -> str:
    """O que salva a rodada: a lição primeiro, depois Sintoma, Causa e Solução.

    Devolve "" quando não há nada a entregar (arquivo ausente, entrada sem
    nenhuma das seções e sem lição) — e aí o sino volta a dar só o endereço.
    """
    blocos = []
    if licao:
        blocos.append(f"Lição: {licao}")
    try:
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        texto = ""
    secoes = secoes_da_armadilha(texto)
    for rotulo, _ in RUBRICAS:
        if secoes.get(rotulo):
            blocos.append(f"{rotulo}: {secoes[rotulo]}")
    if not blocos:
        return ""
    return _cortar_no_paragrafo("\n\n".join(blocos), TETO_DO_RESUMO, relativo)


def _texto_da_resposta(resposta) -> str:
    """A saída do comando, seja qual for a forma que o harness use.

    Defensivo de propósito: a documentação não fixa o formato de
    `tool_response` para o Bash, e um formato novo não pode virar exceção.
    """
    if resposta is None:
        return ""
    if isinstance(resposta, str):
        return resposta
    partes: list[str] = []
    if isinstance(resposta, dict):
        for chave in ("stdout", "stderr", "output", "content", "error", "result"):
            valor = resposta.get(chave)
            if isinstance(valor, str):
                partes.append(valor)
            elif isinstance(valor, list):
                partes.extend(str(item) for item in valor if isinstance(item, str))
        if not partes:
            try:
                return json.dumps(resposta, ensure_ascii=False)
            except Exception:
                return str(resposta)
    elif isinstance(resposta, list):
        partes.extend(str(item) for item in resposta)
    return "\n".join(partes)


def carregar_sinais(caminho: Path = SINAIS) -> list[dict]:
    corpo = json.loads(caminho.read_text(encoding="utf-8"))
    return [s for s in corpo.get("sinais", []) if s.get("regex")]


def reconhecer(saida: str, sinais: list[dict]) -> list[tuple]:
    """(sinal, trecho casado) para cada assinatura reconhecida na saída."""
    achados: list[tuple] = []
    vistos: set = set()
    for sinal in sinais:
        if sinal["armadilha"] in vistos:
            continue
        try:
            achado = re.compile(sinal["regex"]).search(saida)
        except re.error:
            continue  # regex ruim é problema do gerador, não do sino em uso
        if achado:
            vistos.add(sinal["armadilha"])
            achados.append((sinal, achado.group(0)[:TETO_DO_TRECHO]))
        if len(achados) >= MAXIMO_DE_TOQUES:
            break
    return achados


def montar_aviso(
    achados: list[tuple],
    raiz: Path = RAIZ,
    ja_ensinadas: frozenset | set = frozenset(),
    licoes: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """O texto do aviso e os números que receberam a lição inteira agora.

    Quem já recebeu a lição nesta sessão volta a levar só o endereço: repetir
    1.500 caracteres a cada comando trocaria uma conta cara por outra.
    """
    if licoes is None:
        licoes = licoes_por_armadilha(raiz / "armadilhas" / "GATILHOS.json")
    linhas: list[str] = []
    ensinadas: list[str] = []
    for sinal, trecho in achados:
        numero, arquivo = sinal["armadilha"], sinal["arquivo"]
        cabeca = (
            f"🔔 SINO DAS ARMADILHAS: a saída deste comando casa com a assinatura "
            f"da armadilhas/{numero} — \"{sinal['titulo']}\".\n"
            f"   Casou: {trecho!r}"
        )
        resumo = ""
        if numero not in ja_ensinadas:
            resumo = resumo_da_armadilha(raiz / arquivo, arquivo, licoes.get(numero, ""))
        if resumo:
            ensinadas.append(numero)
            linhas.append(
                f"{cabeca}\n"
                f"   Esta falha já custou uma rodada nesta casa. O essencial está "
                f"aqui; LEIA {arquivo} se precisar do caso inteiro.\n"
                f"{textwrap.indent(resumo, '   ')}"
            )
        else:
            linhas.append(
                f"{cabeca}\n"
                f"   LEIA {arquivo} ANTES de tentar de novo: esta falha já "
                f"custou uma rodada nesta casa, e a solução está escrita lá."
            )
    return "\n\n".join(linhas), ensinadas


def avaliar(
    entrada: dict,
    sinais: list[dict],
    raiz: Path = RAIZ,
    ja_ensinadas: frozenset | set = frozenset(),
) -> tuple[str | None, list[str]]:
    ferramenta = str(entrada.get("tool_name") or "")
    if ferramenta not in ("Bash", "PowerShell"):
        return None, []
    comando = str((entrada.get("tool_input") or {}).get("command") or "")
    # Ler o catálogo, ou ler código-fonte, não é sintoma (TAR-048).
    if LENDO_O_CATALOGO.search(comando) or e_so_leitura(comando):
        return None, []
    saida = _texto_da_resposta(entrada.get("tool_response"))
    if not saida:
        return None, []
    achados = reconhecer(saida[-TETO_DA_SAIDA:], sinais)
    if not achados:
        return None, []
    return montar_aviso(achados, raiz, ja_ensinadas)


def decidir(entrada: dict, sinais: list[dict], raiz: Path = RAIZ,
            ja_ensinadas: frozenset | set = frozenset()) -> str | None:
    """Só o texto do aviso. Quem precisa saber o que foi ensinado usa `avaliar`."""
    return avaliar(entrada, sinais, raiz, ja_ensinadas)[0]


def ja_ensinadas_nesta_sessao(cwd: str | None, sessao: str) -> set[str]:
    """Os números que esta sessão já recebeu por extenso.

    O caderninho da telemetria é a memória — o MESMO que a lição do caminho usa
    (`ci/licao_do_caminho.py`). Ele já existe, já é por sessão e já é comum ao
    clone e a todos os worktrees: guardar isto à parte seria uma segunda
    verdade sobre o mesmo fato.
    """
    if telemetria is None or not sessao:
        return set()
    raiz_git = telemetria.dir_git_comum(Path(cwd) if cwd else Path.cwd())
    if raiz_git is None:
        return set()
    return {
        str(linha.get("armadilha"))
        for linha in telemetria.ler_tudo(raiz_git)
        if linha.get("evento") == EVENTO_ENSINOU and linha.get("sessao") == sessao
    }


def _utf8_na_saida() -> None:
    """armadilhas/003, e ela mordeu ESTE arquivo em 29/08/2026.

    O aviso tem emoji e acento; num console cp1252 o `print` estoura
    UnicodeEncodeError — e como o sino é fail-open, a exceção virava silêncio.
    Um sino mudo é indistinguível de um sino que não tinha o que dizer: o
    defeito se esconde atrás da própria tolerância a falha (padrão 1,
    falso-verde). Por isso a reconfiguração vem ANTES de qualquer decisão.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _utf8_na_saida()
    try:
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        sessao = str(entrada.get("session_id") or "")[:64]
        try:
            ja_ensinadas = ja_ensinadas_nesta_sessao(entrada.get("cwd"), sessao)
        except Exception:
            ja_ensinadas = set()  # sem memória o sino ensina de novo, nunca cala
        aviso, ensinadas = avaliar(
            entrada, carregar_sinais(), RAIZ, ja_ensinadas
        )
        if not aviso:
            return 0
        # O aninhamento em hookSpecificOutput é obrigatório: no topo do JSON,
        # additionalContext é ignorado EM SILÊNCIO pelo harness.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": aviso,
            }
        }, ensure_ascii=False))
        try:
            telemetria.registrar(
                "sino_tocou",
                {"armadilhas": aviso.count("SINO DAS ARMADILHAS"),
                 "ferramenta": str(entrada.get("tool_name") or "")},
                cwd=entrada.get("cwd"), sessao=entrada.get("session_id"),
            )
            # Uma linha por armadilha ensinada: é o que a próxima chamada lê
            # para não repetir a lição inteira nesta mesma sessão.
            for numero in ensinadas:
                telemetria.registrar(
                    EVENTO_ENSINOU, {"armadilha": numero},
                    cwd=entrada.get("cwd"), sessao=sessao,
                )
        except Exception:
            pass
        return 0
    except Exception:
        return 0  # fail-open: conselho que trava a sessão é pior que conselho nenhum


if __name__ == "__main__":
    sys.exit(main())
