#!/usr/bin/env python3
"""A muralha do travessão na escrita — a risca é recusada ANTES de entrar no arquivo.

Por que ela existe (06/09/2026): a lei do travessão está no CLAUDE.md de toda
sessão desde 30/08/2026, e mesmo assim um robô escreveu cinco riscas numa lei
nova — o portão do PR (`ci/travessao.py`) pegou, mas só DEPOIS de tudo pronto,
e o conserto virou uma rodada extra de reescrita e CI. Instrução que toda
sessão lê e ainda assim descumpre é o caso provado de que só aviso não basta;
o que faltava era o mecanismo no momento da escrita. Pedido do mantenedor no
mesmo dia: que a garantia exista ANTES de o agente escrever, não depois.

O que ela faz: no PreToolUse de Write e Edit, mede o arquivo como ele ficaria
DEPOIS da gravação, com o MESMO cérebro do portão do PR (importado de
`ci/travessao.py`: superfície, poda de comentários, rótulos de Choices,
bastidor). Se a gravação AUMENTARIA o número de travessões de um arquivo de
texto público, ela recusa, lista as riscas com linha e trecho, e ensina as
quatro trocas na mesma tela. O robô reescreve ali, segundos depois — não
horas depois, com o PR aberto.

A régua é crescimento, não presença: arquivo herdado com riscas antigas pode
ser editado à vontade (e limpá-lo continua sendo o objetivo); o que não pode é
sair da gravação com MAIS riscas do que entrou. É a mesma catraca do portão.

Como o harness a chama (fiação em .claude/settings.json):

  PreToolUse — recebe no stdin o JSON {tool_name, tool_input, cwd, ...}.
               exit 0 permite; exit 2 recusa e o stderr vira o motivo que o
               agente lê. Fail-closed no que é candidato: se o arquivo é de
               texto público e a medição falhou, RECUSA dizendo por quê —
               "não consegui medir" nunca vira permissão (INV-CI01).

O que ela NÃO vê, dito na cara:

  * Texto gravado por shell (heredoc, `echo >`, script) — o gancho cobre as
    ferramentas de edição, o caminho normal desta casa. A rede continua sendo
    o portão do PR, que mede o arquivo inteiro no CI.
  * Texto que já mora no banco (fórum, documentos do editor) — nenhum portão
    de arquivo vê banco; a lei do CLAUDE.md explica o conserto (migração).
  * O Edit que vai falhar sozinho (arquivo inexistente, old_string ausente) —
    recusar o que a própria ferramenta recusaria só duplicaria erro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

CABECALHO = "🧱 MURALHA DO TRAVESSÃO: escrita recusada."


def _utf8_na_saida() -> None:
    # armadilhas/003: acento/emoji em console cp1252 estoura UnicodeEncodeError
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _recusar(motivo: str) -> int:
    print(motivo, file=sys.stderr)
    return 2


def _texto_do_disco(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def decidir(dados: dict) -> int:
    ferramenta = dados.get("tool_name", "")
    entrada = dados.get("tool_input") or {}
    if ferramenta not in ("Write", "Edit"):
        return 0

    bruto = entrada.get("file_path") or ""
    if not bruto:
        return 0  # sem caminho a própria ferramenta falha; nada a medir
    caminho = Path(bruto)
    if not caminho.is_absolute():
        caminho = Path(dados.get("cwd") or ".") / caminho
    try:
        caminho = caminho.resolve()
    except OSError:
        return 0

    checkout = raiz_do_checkout(caminho)
    if checkout is None:
        return 0  # fora de qualquer repo não existe texto público
    raiz = checkout[0]
    relativo = caminho.relative_to(raiz)
    # O corte barato que mantém o gancho invisível no caminho comum: só
    # documentos/ e services/ têm texto público, e é só aí que se paga medição.
    if not relativo.parts or relativo.parts[0] not in ("documentos", "services"):
        return 0

    antes_texto = _texto_do_disco(caminho)
    if ferramenta == "Write":
        depois_texto = entrada.get("content") or ""
    else:
        if antes_texto is None:
            return 0  # o Edit vai falhar sozinho: não há o que gravar
        velho = entrada.get("old_string") or ""
        if not velho or velho not in antes_texto:
            return 0  # idem: o Edit recusa old_string ausente
        novo = entrada.get("new_string") or ""
        if entrada.get("replace_all"):
            depois_texto = antes_texto.replace(velho, novo)
        else:
            depois_texto = antes_texto.replace(velho, novo, 1)

    # Deste ponto em diante o arquivo é candidato a texto público: erro de
    # medição RECUSA em vez de permitir (INV-CI01, o mesmo das outras muralhas).
    try:
        import travessao

        if not travessao.pertence_a_superficie(raiz, relativo, depois_texto):
            return 0
        modo = travessao.modo_de_leitura(caminho, depois_texto)
        caminho_posix = relativo.as_posix()
        depois = travessao.achar(depois_texto, modo, caminho_posix)
        antes = (
            travessao.achar(antes_texto, modo, caminho_posix) if antes_texto else []
        )
    except Exception as erro:
        return _recusar(
            f"{CABECALHO}\n\n"
            f"Este caminho é candidato a texto público e a medição falhou:\n"
            f"  {type(erro).__name__}: {erro}\n\n"
            '"Não consegui medir" nunca vira permissão (INV-CI01). Confira se o\n'
            "checkout está íntegro (ci/travessao.py, ci/texto-publico-bastidor.txt)\n"
            "e tente de novo."
        )

    if len(depois) <= len(antes):
        return 0

    ja_existiam = {(a.forma, a.trecho) for a in antes}
    novos = [a for a in depois if (a.forma, a.trecho) not in ja_existiam] or depois
    conta = "1 travessão" if len(depois) == 1 else f"{len(depois)} travessões"
    linhas = [
        CABECALHO,
        "",
        f"Esta gravação deixaria {relativo.as_posix()} com {conta} em texto",
        f"público (tinha {len(antes)}). O portão do PR (ci/travessao.py) reprovaria",
        "isto depois de tudo pronto; esta recusa só antecipa a conta.",
        "",
        "O que a gravação acrescentaria:",
    ]
    for achado in novos[:8]:
        linhas.append(f"  linha {achado.linha}  {achado.forma}: {achado.trecho}")
    if len(novos) > 8:
        linhas.append(f"  … e mais {len(novos) - 8}")
    linhas += [
        "",
        "REESCREVA a frase sem a risca e grave de novo.",
        "",
        travessao.COMO_TROCAR,
    ]
    return _recusar("\n".join(linhas))


def main() -> int:
    _utf8_na_saida()
    try:
        dados = json.load(sys.stdin)
    except Exception:
        return _recusar(
            f"{CABECALHO}\n\nNão entendi o pedido (o stdin não era JSON de hook)."
        )
    try:
        return decidir(dados)
    except Exception as erro:  # fail-closed, INV-CI01
        return _recusar(
            f"{CABECALHO}\n\nErro interno da muralha: {type(erro).__name__}: {erro}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
