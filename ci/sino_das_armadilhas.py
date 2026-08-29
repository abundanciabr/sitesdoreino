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
pelo gerador) e, quando reconhece, diz ao agente qual entrada abrir.

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
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SINAIS = RAIZ / "armadilhas" / "SINAIS.json"

TETO_DA_SAIDA = 200_000  # o erro mora no fim; log de build inteiro não é regex
MAXIMO_DE_TOQUES = 3
TETO_DO_TRECHO = 120

# Ler o próprio catálogo não pode tocar o sino: o texto do sintoma contém, de
# propósito, a mensagem de erro crua que serve de assinatura.
LENDO_O_CATALOGO = re.compile(
    r"armadilhas[/\\]|INDICE\.md|SINAIS\.json|GUARDAS\.json", re.IGNORECASE
)


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


def montar_aviso(achados: list[tuple]) -> str:
    linhas = []
    for sinal, trecho in achados:
        linhas.append(
            f"🔔 SINO DAS ARMADILHAS: a saída deste comando casa com a assinatura "
            f"da armadilhas/{sinal['armadilha']} — \"{sinal['titulo']}\".\n"
            f"   Casou: {trecho!r}\n"
            f"   LEIA {sinal['arquivo']} ANTES de tentar de novo: esta falha já "
            f"custou uma rodada nesta casa, e a solução está escrita lá."
        )
    return "\n".join(linhas)


def decidir(entrada: dict, sinais: list[dict]) -> str | None:
    ferramenta = str(entrada.get("tool_name") or "")
    if ferramenta not in ("Bash", "PowerShell"):
        return None
    comando = str((entrada.get("tool_input") or {}).get("command") or "")
    if LENDO_O_CATALOGO.search(comando):
        return None
    saida = _texto_da_resposta(entrada.get("tool_response"))
    if not saida:
        return None
    achados = reconhecer(saida[-TETO_DA_SAIDA:], sinais)
    return montar_aviso(achados) if achados else None


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
        aviso = decidir(entrada, carregar_sinais())
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
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import telemetria

            telemetria.registrar(
                "sino_tocou",
                {"armadilhas": aviso.count("SINO DAS ARMADILHAS"),
                 "ferramenta": str(entrada.get("tool_name") or "")},
                cwd=entrada.get("cwd"), sessao=entrada.get("session_id"),
            )
        except Exception:
            pass
        return 0
    except Exception:
        return 0  # fail-open: conselho que trava a sessão é pior que conselho nenhum


if __name__ == "__main__":
    sys.exit(main())
