"""O caminho de volta: de um número do placar para as tarefas que o movem.

O que estes guardas não deixam apodrecer:

1. **"ninguém declarou" nunca vira "nenhuma tarefa move este número".** As 123
   tarefas que já existiam em 04/09/2026 nasceram antes do campo `move`. Uma
   tela que dissesse "nada está sendo feito pela meta" com base nelas estaria
   mentindo, e essa é a classe de falso que esta casa mais persegue.
2. **Manutenção não vira trabalho de crescimento.** Quem se declarou
   `manutencao` não aparece pendurado em número nenhum.
3. **Tarefa terminada não conta.** O caminho de volta é sobre o que está
   acontecendo, não sobre o histórico.
4. **A palavra reservada é a MESMA que a fila escreve.** Duas definições da
   mesma palavra divergiriam no primeiro dia em que alguém mexesse numa só.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from apps.core import elo

RAIZ = Path(__file__).resolve().parents[3]


def fila(tarefas, reivindicadas=(), bloqueadas=(), terminadas=()):
    """A forma que `latencias.ler_a_fila` devolve, montada à mão."""
    hoje = dt.date(2026, 9, 4)
    return {
        "tarefas": {tid: hoje for tid in tarefas},
        "titulos": {tid: f"titulo de {tid}" for tid in tarefas},
        "move": dict(tarefas),
        "reivindicadas": {tid: hoje for tid in reivindicadas},
        "bloqueadas": set(bloqueadas),
        "terminadas": set(terminadas),
    }


# --------------------------------------------------------------- o caminho de volta


def test_sem_fila_devolve_none_e_nao_zero():
    assert elo.trabalho_por_cartao(None) is None
    assert elo.resumo_da_declaracao(None) is None


def test_a_tarefa_aparece_pendurada_no_numero_que_declarou():
    f = fila({"TAR-001": ["compras-no-mes"]})
    assert elo.trabalho_por_cartao(f) == {
        "compras-no-mes": [
            {"id": "TAR-001", "titulo": "titulo de TAR-001", "estado": "na fila"}
        ]
    }


def test_uma_tarefa_pode_mover_dois_numeros():
    f = fila({"TAR-001": ["compras-no-mes", "liberacoes-em-48h"]})
    volta = elo.trabalho_por_cartao(f)
    assert set(volta) == {"compras-no-mes", "liberacoes-em-48h"}


def test_manutencao_nao_se_pendura_em_numero_nenhum():
    f = fila({"TAR-001": ["manutencao"]})
    assert elo.trabalho_por_cartao(f) == {}


def test_quem_nao_declarou_nao_se_pendura_em_numero_nenhum():
    f = fila({"TAR-001": None})
    assert elo.trabalho_por_cartao(f) == {}


def test_tarefa_terminada_nao_conta_como_trabalho_em_curso():
    f = fila({"TAR-001": ["compras-no-mes"]}, terminadas=["TAR-001"])
    assert elo.trabalho_por_cartao(f) == {}


def test_o_estado_de_cada_tarefa_vem_junto():
    f = fila(
        {
            "TAR-001": ["compras-no-mes"],
            "TAR-002": ["compras-no-mes"],
            "TAR-003": ["compras-no-mes"],
        },
        reivindicadas=["TAR-002"],
        bloqueadas=["TAR-003"],
    )
    estados = {
        t["id"]: t["estado"] for t in elo.trabalho_por_cartao(f)["compras-no-mes"]
    }
    assert estados == {
        "TAR-001": "na fila",
        "TAR-002": "em andamento",
        "TAR-003": "bloqueada",
    }


# ------------------------------------- o resumo que impede a tela de mentir


def test_o_resumo_separa_declarou_de_manutencao_de_calou():
    f = fila(
        {
            "TAR-001": ["compras-no-mes"],
            "TAR-002": ["manutencao"],
            "TAR-003": None,
            "TAR-004": None,
            "TAR-005": ["compras-no-mes"],
        },
        terminadas=["TAR-005"],
    )
    assert elo.resumo_da_declaracao(f) == {
        "vivas": 4,
        "declararam": 1,
        "manutencao": 1,
        "nao_declararam": 2,
    }


def test_fila_so_de_antigas_diz_que_ninguem_declarou_e_nao_que_nada_se_move():
    """O caso real de 04/09/2026: 123 tarefas, nenhuma declarando."""
    f = fila({f"TAR-{n:03d}": None for n in range(1, 124)})
    resumo = elo.resumo_da_declaracao(f)
    assert resumo["nao_declararam"] == 123
    assert resumo["declararam"] == 0
    assert elo.trabalho_por_cartao(f) == {}


# --------------------------------------------------- a palavra reservada é UMA


def test_a_palavra_manutencao_e_a_mesma_que_a_fila_escreve():
    """`ci/fila.py` é a dona da palavra; aqui ela é repetida, e o guarda compara."""
    sys.path.insert(0, str(RAIZ / "ci"))
    try:
        import fila as fila_do_ci
    finally:
        sys.path.pop(0)
    assert elo.MANUTENCAO == fila_do_ci.MANUTENCAO


def test_todo_cartao_citado_por_uma_tarefa_real_existe_em_painel_cartoes():
    """Contraprova viva: se alguém apagar um cartão que uma tarefa move, isto morde."""
    tarefas = sorted((RAIZ / "fila" / "tarefas").glob("*.json"))
    assert tarefas, "a fila real não veio neste checkout"
    cartoes = {c.stem for c in (RAIZ / "painel" / "cartoes").glob("*.json")}
    assert cartoes, "os cartões reais não vieram neste checkout"
    for arquivo in tarefas:
        declarado = json.loads(arquivo.read_text(encoding="utf-8")).get("move")
        for alvo in declarado or []:
            if alvo != elo.MANUTENCAO:
                assert alvo in cartoes, f"{arquivo.name} move {alvo!r}, que não existe"
