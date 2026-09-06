#!/usr/bin/env python3
"""A COBRANÇA DO CHECKLIST, EM SOMBRA: o roteiro que sumia no meio do caminho.

POR QUE ELA EXISTE (06/09/2026)
-------------------------------
O mantenedor pediu em 05/09/2026, com as palavras dele, que "toda e cada tarefa
mostre um checklist e um roadmap claro de onde está e o que ainda precisa ser
feito ao final de cada etapa, fase, parte, executada". A lei está no
`CLAUDE.md` ("Plano na abertura, contas no fecho", ponta 2), e a própria lei
declara que essa ponta NÃO tem mecanismo.

Medido na semana seguinte: o checklist marcado apareceu **3 vezes em 121 PRs**.
É a peça que ele pediu e a única que quase não recebeu. Lei sem mecanismo é a
doença-mãe desta casa (Constituição, Lei 1), e aqui ela estava com número.

O QUE A `armadilhas/350` PROIBIU, E QUAL É A RESPOSTA DAQUI
-----------------------------------------------------------
A 350 diz que "etapa" não existe para a máquina: contar reimpressões contra
CHAMADAS de ferramenta produz um portão que grita a cada `ls`, e um portão que
grita a cada `ls` o mantenedor aprende a ignorar em um dia.

A resposta deste arquivo não é "etapa". É **N mudanças no mundo**. O
discriminador já existia e já foi medido contra 40 sessões reais: o
`_mudanca_na_entrada` da `ci/prestacao_de_contas.py`, que separa quem editou,
commitou ou abriu PR de quem só leu. Leitura não conta, e por isso o `ls` da
350 nunca chega aqui. "8 mudanças no mundo sem uma caixinha na tela" não é
etapa nenhuma: é uma proxy honesta dela, e está dito assim de propósito.

POR QUE EM SOMBRA, E O QUE SOMBRA SIGNIFICA AQUI
-------------------------------------------------
O Sistema Imunológico manda regra nova nascer em sombra (o mesmo rito da
`ci/muralha_das_armadilhas.py`): a regra roda, mede, DIZ o que teria feito, e
não impede nada. A graduação para cobrança de verdade é PR futuro, depois de o
caderninho mostrar quantas vezes ela dispararia e em quantas delas estaria
certa. Aqui a sombra é mais fraca ainda que a da muralha, porque o exit code
de um `PostToolUse` não tem como impedir coisa alguma: a ferramenta já rodou.

O canal é o `hookSpecificOutput.additionalContext`, o mesmo do sino, e é
deliberado: um aviso que só aparecesse no stdout do modo transcript seria
invisível para o robô E para o mantenedor, quer dizer, um mecanismo nascido
morto (`armadilhas/176`). Sombra é sobre a AUTORIDADE da regra, nunca sobre
ela ser silenciosa.

A CONTAGEM ZERA SEM GUARDAR ESTADO
-----------------------------------
Duas coisas zeram a contagem, e nenhuma das duas precisa de arquivo de estado:

1. **A caixinha na tela.** Uma fala do robô com uma linha `- [x]`/`- [ ]` E a
   linha "Onde estou:" vira a nova âncora, e a contagem recomeça dali.
2. **A própria cobrança**, pelo resto: cobra-se quando a contagem é múltipla
   de `TETO_SEM_CAIXINHA`. Cobrado no 8, cala no 9 até o 15, cobra de novo no
   16. Sem sidecar, sem cache para envelhecer, sem duas sessões disputando o
   mesmo arquivo (padrão 7 da RETROSPECTIVA-FASE-D).

O CUSTO, MEDIDO E DECLARADO
----------------------------
Este gancho roda em TODO Edit, Write, Bash e PowerShell da sessão, e o
transcript cresce o dia inteiro. Duas coisas o mantêm barato, e as duas
nasceram de medição, não de palpite:

1. **Ele lê o arquivo DE TRÁS PARA A FRENTE e para na âncora.** Só interessa o
   que aconteceu depois da última caixinha, e num transcript de 9 MB isso
   costuma ser o último punhado de quilobytes.
2. **Um filtro de substring em texto cru** decide o que vira `json.loads`: uma
   linha sem `"tool_use"` e sem `nde estou` não pode ser âncora nem mudança, e
   desserializá-la é custo puro.

Medido em 06/09/2026 contra o maior transcript real desta casa (10 MB, cerca de
8.100 linhas, 67 caixinhas): **385 ms lendo o arquivo inteiro para a frente,
5,6 ms lendo de trás para a frente**. O teto de referência da casa é 130 ms por
gancho, e a versão para a frente estourava esse teto três vezes.

A primeira versão deste arquivo dispensou a leitura de trás para frente por
escrito, com o argumento de que ela só barateia a sessão que JÁ imprime
checklist. O argumento estava errado, e foi a medição que o derrubou: a sessão
mais cara da casa imprimiu 67 caixinhas E fez 293 mudanças. Sobra o pior caso
honesto, e ele fica declarado: a sessão que nunca imprime caixinha nenhuma é
varrida inteira, toda vez.

FAIL-OPEN TOTAL
----------------
Transcript ausente, JSON quebrado, erro interno: silêncio e exit 0. A muralha
impede e na dúvida recusa; a sombra ensina e na dúvida cala. Este arquivo é do
segundo tipo, e é por isso que ele não segue o fail-open BARULHENTO da
`ci/prestacao_de_contas.py`: lá o portão é a única voz de uma lei, aqui ele é
um instrumento de medição que ainda não tem autoridade nenhuma. Um instrumento
que grita ao quebrar em TODO comando seria pior que instrumento nenhum.

Uso (fora do harness, para depurar):

    echo '{"transcript_path":"..."}' | python ci/cobranca_do_checklist.py

Exit code: 0, sempre.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402  (irmão de pasta; o insert acima é o que o permite)
from prestacao_de_contas import CAIXINHA, _mudanca_na_entrada  # noqa: E402

# O único parâmetro desta regra, e ele é constante no código de propósito: uma
# flag "para dar flexibilidade" só produziria duas casas com teto diferente e
# nenhuma medição comparável. Graduar o número é mudar esta linha, por PR.
TETO_SEM_CAIXINHA = 8

# A âncora: a fala em que o robô reimprimiu o roteiro. As duas metades são
# exigidas juntas porque só a caixinha não diz onde a tarefa está (o plano de
# abertura colado de novo, intocado, passaria), e só o "Onde estou" não é
# roteiro nenhum.
ONDE_ESTOU = re.compile(r"\bonde\s+estou\b", re.I)

# O filtro barato, aplicado à linha CRUA do transcript, antes de qualquer
# json.loads. Uma linha que não tenha nenhum dos dois não pode ser âncora nem
# mudança, e desserializá-la é o custo que este gancho não pode pagar.
#
# `nde estou` é a metade barata da MESMA regra do `ONDE_ESTOU` acima, e por
# isso a exigência do "Onde estou" está guardada duas vezes: quem sabota uma
# das duas ainda esbarra na outra. Isso é deliberado, e está dito aqui para
# ninguém "limpar" a duplicação achando que é descuido.
PENEIRA = ('"tool_use"', "nde estou")

# Quanto se lê por vez ao voltar do fim do arquivo. 256 KB cobre de sobra a
# distância típica até a última caixinha, e uma sessão sem caixinha nenhuma
# volta bloco a bloco até o começo, que é o pior caso declarado.
BLOCO = 256 * 1024


def _utf8_na_saida() -> None:
    """armadilhas/003: console cp1252 estoura no emoji, e como aqui tudo é
    fail-open a exceção viraria silêncio. Um instrumento mudo é indistinguível
    de um instrumento que não tinha o que dizer."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _texto(linha: bytes) -> str:
    """Bytes de uma linha viram texto. O `\\r` final some porque a leitura é
    binária: em modo texto o Python o comeria sozinho, e um arquivo escrito
    nesta máquina (Windows) traz `\\r\\n` no fim de cada linha."""
    return linha.decode("utf-8", errors="replace").rstrip("\r")


def linhas_de_tras_para_frente(caminho: Path) -> Iterator[str]:
    """As linhas do transcript, da última para a primeira, sem carregar tudo.

    O arquivo é lido em blocos a partir do fim. O primeiro pedaço de cada bloco
    pode ser meia linha (o corte cai no meio dela), então ele volta como resto
    e é colado no bloco anterior. Só o último bloco lido (o começo do arquivo)
    não tem essa dívida.
    """
    with caminho.open("rb") as arquivo:
        arquivo.seek(0, 2)
        fim = arquivo.tell()
        resto = b""
        while fim > 0:
            comeco = max(0, fim - BLOCO)
            arquivo.seek(comeco)
            pedaco = arquivo.read(fim - comeco) + resto
            fim = comeco
            linhas = pedaco.split(b"\n")
            resto = linhas.pop(0) if fim > 0 else b""
            for linha in reversed(linhas):
                yield _texto(linha)
        if resto:
            yield _texto(resto)


def entradas_de_interesse(caminho: Path) -> Iterator[dict]:
    """As entradas que podem ser âncora ou mudança, da mais nova para a mais velha.

    Sidechain fica de fora pelo mesmo motivo da `ci/prestacao_de_contas.py`: as
    escritas de um sub-agente já contam pelo `Agent` do fio principal, e
    contá-las aqui adiantaria a cobrança sem ninguém ter mudado nada a mais.
    """
    for linha in linhas_de_tras_para_frente(caminho):
        if not any(marca in linha for marca in PENEIRA):
            continue
        try:
            entrada = json.loads(linha)
        except json.JSONDecodeError:
            continue  # linha meio-escrita no fim do arquivo: o resto serve
        if isinstance(entrada, dict) and not entrada.get("isSidechain"):
            yield entrada


def _reimprimiu_o_roteiro(entrada: dict) -> bool:
    """Esta fala do robô tem caixinha E diz onde a tarefa está?"""
    if entrada.get("type") != "assistant":
        return False
    conteudo = (entrada.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        texto = conteudo
    elif isinstance(conteudo, list):
        texto = "\n".join(
            str(b.get("text") or "")
            for b in conteudo
            if isinstance(b, dict) and b.get("type") == "text"
        )
    else:
        return False
    return bool(CAIXINHA.search(texto) and ONDE_ESTOU.search(texto))


def contar_desde_a_caixinha(entradas: Iterable[dict]) -> int:
    """Quantas mudanças no mundo desde a última reimpressão do roteiro.

    Consome as entradas da mais NOVA para a mais velha e para na âncora: é o
    que torna a leitura de trás para frente barata de verdade.
    """
    quantas = 0
    for entrada in entradas:
        if _reimprimiu_o_roteiro(entrada):
            break
        if _mudanca_na_entrada(entrada):
            quantas += 1
    return quantas


def decidir(entradas: Iterable[dict]) -> int | None:
    """A contagem, quando ela merece a linha de sombra. Senão, None."""
    quantas = contar_desde_a_caixinha(entradas)
    if quantas >= TETO_SEM_CAIXINHA and quantas % TETO_SEM_CAIXINHA == 0:
        return quantas
    return None


def linha_de_sombra(quantas: int) -> str:
    return (
        f"🧾 sombra: eu teria cobrado o checklist ({quantas} mudanças desde a "
        "última caixinha; a lei manda reimprimir o plano marcado com "
        '"Onde estou: passo X de Y")'
    )


def main() -> int:
    _utf8_na_saida()
    try:
        # armadilhas/138: o PowerShell 5.1 injeta BOM ao canalizar; ler bytes
        # crus e decodificar com utf-8-sig é o que impede o JSON de reprovar.
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        # Transcript ausente, vazio ou ilegível cai no `except` lá embaixo e
        # vira silêncio. Uma conferência de `is_file()` aqui em cima seria uma
        # segunda porta para a mesma saída, e uma delas ficaria sem teste.
        caminho = Path(str(entrada.get("transcript_path") or ""))
        quantas = decidir(entradas_de_interesse(caminho))
        if quantas is None:
            return 0

        # Medir vem antes de falar: em sombra, o caderninho é o efeito que
        # sobrevive à sessão, e é dele que sai a decisão de graduar ou não.
        telemetria.registrar(
            "checklist_em_sombra",
            {
                "mudancas": quantas,
                "teto": TETO_SEM_CAIXINHA,
                "modo": "sombra",
                "ferramenta": str(entrada.get("tool_name") or ""),
            },
            cwd=entrada.get("cwd"),
            sessao=entrada.get("session_id"),
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": linha_de_sombra(quantas),
            }
        }, ensure_ascii=False))
        return 0
    except Exception:
        return 0  # fail-open TOTAL: sombra que trava a casa é pior que sombra nenhuma


if __name__ == "__main__":
    sys.exit(main())
