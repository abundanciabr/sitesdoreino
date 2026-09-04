"""O caminho de volta: de um número do placar para as tarefas que o movem.

A segunda metade do degrau 19 de `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`. A
IDA (a tarefa declara `move`) mora em `ci/fila.py` e chegou no PR #1031; a
VOLTA é este módulo, e ele é só leitura: nada aqui guarda estado, tudo se
calcula da fila a cada requisição, como manda a primeira lei do painel.

A pergunta que ele responde, do quinto documento do Scale OS (§1): *que ações
estão sendo executadas para movimentar este indicador?*

Três respostas possíveis por número, e elas são diferentes de propósito:

- **tarefas vivas apontando para ele** — a lista, com o estado de cada uma;
- **nenhuma tarefa aponta** — ninguém está trabalhando neste número agora;
- **a fila não veio nesta versão do site** — não é o mesmo que "nenhuma".

E um resumo honesto por cima, porque em 04/09/2026 as 123 tarefas que já
existiam nasceram antes do campo e não declararam nada: dizer "nenhuma tarefa
move a meta" seria mentira quando a verdade é "ninguém declarou ainda".
"""

from __future__ import annotations

# O valor reservado do campo `move`. UMA definição, em `ci/fila.py`; aqui ela é
# repetida porque a célula não importa o CI, e a divergência é barata de guardar
# com teste (test_elo.py compara com o que a fila escreve).
MANUTENCAO = "manutencao"


def _vivas(fila: dict) -> list[str]:
    """As tarefas que ainda podem receber trabalho: nem concluídas, nem canceladas."""
    return [tid for tid in fila["tarefas"] if tid not in fila["terminadas"]]


def _estado(fila: dict, tid: str) -> str:
    if tid in fila["bloqueadas"]:
        return "bloqueada"
    if tid in fila["reivindicadas"]:
        return "em andamento"
    return "na fila"


def trabalho_por_cartao(fila: dict | None) -> dict[str, list[dict]] | None:
    """`{nome do cartão: [{id, titulo, estado}, ...]}`; `None` sem fila."""
    if fila is None:
        return None
    por_cartao: dict[str, list[dict]] = {}
    for tid in _vivas(fila):
        alvos = fila["move"].get(tid)
        if not alvos or alvos == [MANUTENCAO]:
            continue
        for alvo in alvos:
            if alvo == MANUTENCAO:
                continue
            por_cartao.setdefault(alvo, []).append(
                {
                    "id": tid,
                    "titulo": fila["titulos"].get(tid, tid),
                    "estado": _estado(fila, tid),
                }
            )
    for lista in por_cartao.values():
        lista.sort(key=lambda t: t["id"])
    return por_cartao


def resumo_da_declaracao(fila: dict | None) -> dict | None:
    """Quantas tarefas vivas declararam, quantas são manutenção, quantas calaram.

    É o que impede a tela de dizer "nenhuma tarefa move este número" quando a
    verdade é "ninguém declarou ainda". Enquanto `nao_declararam` for a maioria,
    a ausência de tarefas num número não prova ausência de trabalho.
    """
    if fila is None:
        return None
    vivas = _vivas(fila)
    manutencao = 0
    declararam = 0
    nao_declararam = 0
    for tid in vivas:
        alvos = fila["move"].get(tid)
        if alvos is None:
            nao_declararam += 1
        elif alvos == [MANUTENCAO]:
            manutencao += 1
        else:
            declararam += 1
    return {
        "vivas": len(vivas),
        "declararam": declararam,
        "manutencao": manutencao,
        "nao_declararam": nao_declararam,
    }
