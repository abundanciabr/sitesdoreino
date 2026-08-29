#!/usr/bin/env python3
"""A MURALHA DAS ARMADILHAS — a lição que já custou caro vira recusa.

Por que ela existe (29/08/2026): o catálogo de `armadilhas/` tem mais de 150
entradas e é CONSELHO — depende de o agente ter lido a entrada certa antes de
digitar o comando. Ele não leu, e caiu de novo: a armadilhas/136 (crase que o
shell EXECUTA dentro de aspas duplas) corrompeu a mensagem de um commit no
PR #475, três dias depois de a lição ser escrita. É a doença que este projeto
já nomeou — "garantia sem mecanismo apodrece" (RETROSPECTIVA-FASE-D §2) — e a
resposta que ele já provou funcionar duas vezes: uma muralha, no molde exato
da `ci/muralha_pasta_compartilhada.py` e da `ci/muralha_da_espera.py`.

Como o harness a chama (fiação em .claude/settings.json):

  PreToolUse — recebe no stdin o JSON {tool_name, tool_input, cwd, ...}.
               exit 0 permite; exit 2 recusa e o stderr vira o motivo que o
               agente lê. Fail-closed: erro interno TAMBÉM recusa (INV-CI01).

A LEI DA AUTORIDADE PROPORCIONAL À CERTEZA — o que separa esta muralha de um
lint entusiasmado. Falso positivo também queima tokens, e uma regra que recusa
comando legítimo é pior que a armadilha que ela evita:

  confiança ESTRUTURAL (o padrão É a armadilha, sósia legítimo não existe)
      nasce em `bloqueia`. O corpus de teste é a prova.
  confiança ALTA (sósias legítimos existem, mas o detector os exclui)
      nasce em `sombra`: o detector roda, NÃO impede nada, e grava no
      caderninho "R<N> teria bloqueado isto". Promove-se a `bloqueia` com o
      relatório do `ci/termometro.py` na mão — 10 disparos ou 7 dias sem um
      único falso positivo. É o que impede uma regex plausível no teste, mas
      errada no mundo real, de tijolar as sessões do mantenedor.
  confiança MÉDIA — não entra aqui. Vai para o sino (detecta DEPOIS, aconselha,
      fail-open) ou fica sem guarda, em vermelho honesto no índice.

A LINHA DE PRECISÃO — uma regra só entra se as três valem:
  1. o detector prova a MECÂNICA danosa pelo input sozinho (não a intenção);
  2. toda variante legítima conhecida é excluída pelo próprio detector;
  3. a recusa entrega uma alternativa EXECUTÁVEL na hora.
Exemplo do que fica de fora por desenho: a armadilhas/093 (contrabarra dupla
que some no transporte) tem uso legítimo constante em `python -c` e heredoc —
ela pertence ao sino, pela assinatura de erro, nunca a esta muralha.

O que ela NÃO é: um parser de shell, nem um catálogo espelhado. Só o punhado
de armadilhas cujo dano é provável pelo texto do comando entra aqui; o resto do
catálogo continua sendo lido por quem trabalha. Ela também NÃO lê arquivo nenhum
em tempo de execução — a autoridade de cada regra mora na tabela abaixo, em
código. Um JSON de configuração ausente ou corrompido faria uma muralha
fail-closed recusar TODO comando da sessão, e nenhuma proteção vale isso.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)

# --------------------------------------------------------------------------
# Ferramentas de leitura do comando, compartilhadas por todos os detectores.
# --------------------------------------------------------------------------

RE_HEREDOC_CITADO = re.compile(r"<<-?\s*(['\"])(\w+)\1")


def podar_heredocs_citados(comando: str) -> str:
    """Remove o CORPO de heredocs com delimitador entre aspas.

    `<<'EOF' … EOF` não é comando: o bash não expande nada lá dentro. Um agente
    escrevendo documentação que CITA um comando perigoso não pode ser recusado
    por citá-lo — esta poda é o que mata a maior família de falsos positivos.
    Heredoc SEM aspas (`<<EOF`) continua sujeito às regras: ali o shell expande
    de verdade, e o dano é real.
    """
    saida: list[str] = []
    delimitador: str | None = None
    for linha in comando.split("\n"):
        if delimitador is None:
            saida.append(linha)
            achado = RE_HEREDOC_CITADO.search(linha)
            if achado:
                delimitador = achado.group(2)
        elif linha.strip() == delimitador:
            delimitador = None
    return "\n".join(saida)


# --------------------------------------------------------------------------
# R136 — crase viva em mensagem de commit / corpo de PR
# --------------------------------------------------------------------------

# Só Bash: no PowerShell a crase é caractere de ESCAPE, não substituição de
# comando — a mesma linha lá é inofensiva, e recusá-la seria falso positivo.
RE_COMANDO_DE_MENSAGEM = re.compile(
    r"\b(?:git\s+(?:commit|tag)|gh\s+(?:pr|issue|release)\s+\w+)\b"
)
FLAGS_DE_MENSAGEM = frozenset(
    {"-m", "-b", "-t", "--message", "--body", "--title", "--notes", "--description"}
)
# Dentro de aspas duplas, `\`` está escapado e é literal; a crase nua executa.
RE_CRASE_VIVA = re.compile(r"(?<!\\)`")


def argumentos(texto: str, inicio: int) -> list:
    """Os argumentos de UM comando, a partir de `inicio`, respeitando aspas.

    Regex não serve aqui: `--title "x" --body "…"` tem dois argumentos com
    aspas, e uma expressão preguiçosa enxerga só o primeiro (foi assim que o
    corpus pegou o primeiro furo desta regra). Este percurso devolve
    (texto, tipo de aspas) e PARA no primeiro separador de comando que esteja
    fora de aspas — assim uma mensagem que contenha `|` ou `;` não confunde, e
    o comando seguinte de uma linha composta não é atribuído a este.
    """
    tokens: list = []
    atual, tipo, i, fim = "", "nu", inicio, len(texto)
    while i < fim:
        letra = texto[i]
        if letra in "&|;":
            break
        if letra.isspace():
            if atual or tipo != "nu":
                tokens.append((atual, tipo))
                atual, tipo = "", "nu"
            i += 1
            continue
        if letra == "'":
            corte = texto.find("'", i + 1)
            corte = fim if corte == -1 else corte
            atual += texto[i + 1:corte]
            tipo = "simples"
            i = corte + 1
            continue
        if letra == '"':
            j, buffer = i + 1, ""
            while j < fim:
                if texto[j] == "\\" and j + 1 < fim:
                    buffer += texto[j:j + 2]
                    j += 2
                    continue
                if texto[j] == '"':
                    break
                buffer += texto[j]
                j += 1
            atual += buffer
            tipo = "duplas"
            i = j + 1
            continue
        atual += letra
        i += 1
    if atual or tipo != "nu":
        tokens.append((atual, tipo))
    return tokens


def detectar_crase_em_mensagem(comando: str, _entrada: dict) -> str | None:
    for achado in RE_COMANDO_DE_MENSAGEM.finditer(comando):
        corpo = None
        esperando = False
        for texto, tipo in argumentos(comando, achado.end()):
            if esperando:
                esperando = False
                if tipo == "duplas" and RE_CRASE_VIVA.search(texto):
                    corpo = texto
                    break
                continue
            if texto in FLAGS_DE_MENSAGEM:
                esperando = True
                continue
            nome, igual, valor = texto.partition("=")
            if igual and nome in FLAGS_DE_MENSAGEM and tipo == "duplas":
                if RE_CRASE_VIVA.search(valor):
                    corpo = valor
                    break
        if corpo is not None:
            trecho = corpo.strip()
            if len(trecho) > 90:
                trecho = trecho[:90] + "…"
            return (
                "há crase NÃO escapada dentro de aspas duplas numa mensagem de "
                f'commit/PR: "{trecho}". Dentro de aspas duplas o shell EXECUTA '
                "o que está entre crases — a mensagem grava a saída do comando "
                "no lugar do nome do arquivo, e o commit não falha: fica verde, "
                "com o texto corrompido, e o estrago só aparece meses depois "
                "(26/08/2026, PR #257; de novo em 28/08/2026, PR #475)"
            )
    return None


# --------------------------------------------------------------------------
# A tabela de regras. Uma linha por armadilha mecanizada.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Regra:
    armadilha: str
    detector_nome: str
    ferramentas: frozenset
    detectar: Callable[[str, dict], "str | None"]
    confianca: str  # "estrutural" | "alta"
    autoridade: str  # "sombra" | "bloqueia"
    caminho_certo: str


REGRAS: tuple[Regra, ...] = (
    Regra(
        armadilha="136",
        detector_nome="crase_em_mensagem",
        ferramentas=frozenset({"Bash"}),
        detectar=detectar_crase_em_mensagem,
        confianca="alta",
        autoridade="sombra",
        caminho_certo=(
            "escreva a mensagem num arquivo do scratchpad e passe por arquivo — "
            "`git commit -F <arquivo>` / `gh pr create --body-file <arquivo>`. "
            "Se for curta, vários -m simples e SEM crase nenhuma "
            "(armadilhas/136)"
        ),
    ),
)

FERRAMENTAS_COBERTAS = frozenset(
    ferramenta for regra in REGRAS for ferramenta in regra.ferramentas
)


@dataclass(frozen=True)
class Achado:
    regra: Regra
    motivo: str


def avaliar(entrada: dict) -> Achado | None:
    """A decisão pura, sem autoridade: qual regra reconheceu, e por quê.

    Separada do `main` de propósito — é o que permite provar por teste uma
    regra que ainda está em sombra (e que, por isso, não muda o exit).
    """
    ferramenta = str(entrada.get("tool_name") or "")
    if ferramenta not in FERRAMENTAS_COBERTAS:
        return None
    tool_input = entrada.get("tool_input") or {}
    comando = str(tool_input.get("command") or "")
    if not comando:
        return None
    podado = podar_heredocs_citados(comando)
    for regra in REGRAS:
        if ferramenta not in regra.ferramentas:
            continue
        motivo = regra.detectar(podado, tool_input)
        if motivo:
            return Achado(regra=regra, motivo=motivo)
    return None


def _utf8_na_saida() -> None:
    # armadilhas/003: acento/emoji em console cp1252 estoura UnicodeEncodeError
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _recusar(motivo: str, caminho_certo: str, armadilha: str = "") -> int:
    ponteiro = f" (armadilhas/{armadilha})" if armadilha else ""
    print(
        "🧱 MURALHA DAS ARMADILHAS: recusado — " + motivo + ponteiro + ".\n"
        "   O caminho certo: " + caminho_certo + "\n"
        "   Se isto for um falso positivo, reporte na entrada da armadilha "
        "em vez de contornar.",
        file=sys.stderr,
    )
    return 2


def _ler_stdin() -> dict:
    # armadilhas/138: o PowerShell 5.1 injeta BOM ao canalizar; ler bytes crus e
    # decodificar com utf-8-sig é o que impede todo JSON de reprovar no Windows.
    return json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))


def main() -> int:
    _utf8_na_saida()
    try:
        entrada = _ler_stdin()
    except Exception:
        return _recusar(
            "não consegui ler a chamada (JSON quebrado no stdin) — e não medir "
            "nunca vira permissão (INV-CI01)",
            "reporte esta recusa: ela indica defeito na muralha, não no comando",
        )
    try:
        achado = avaliar(entrada)
        if achado is None:
            return 0
        # Medir vem antes de agir: em sombra, o caderninho é o ÚNICO efeito.
        telemetria.registrar(
            "regra_disparou",
            {
                "armadilha": achado.regra.armadilha,
                "detector": achado.regra.detector_nome,
                "modo": achado.regra.autoridade,
                "ferramenta": str(entrada.get("tool_name") or ""),
                "comando": str((entrada.get("tool_input") or {}).get("command") or ""),
            },
            cwd=entrada.get("cwd"),
            sessao=entrada.get("session_id"),
        )
        if achado.regra.autoridade == "bloqueia":
            return _recusar(
                achado.motivo, achado.regra.caminho_certo, achado.regra.armadilha
            )
        return 0  # sombra: observa e deixa passar, para provar a precisão antes
    except Exception as erro:  # fail-closed: erro interno também recusa
        return _recusar(
            f"erro interno da muralha ({erro.__class__.__name__}: {erro}) — "
            "fail-closed: na dúvida, recuso",
            "reporte esta recusa: ela indica defeito na muralha, não no comando",
        )


if __name__ == "__main__":
    sys.exit(main())
