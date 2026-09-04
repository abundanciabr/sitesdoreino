"""As três latências da gestão (degrau 5 do plano do painel de gestão).

Scale OS 1.1 §166 a §169: um painel é bom quando encurta o tempo entre o
sinal e a decisão, entre a decisão e o começo do trabalho, e entre o fim de
um experimento e o aprendizado incorporado. É o único indicador dos
documentos que já tinha fonte completa no dia em que o plano nasceu, porque
as três pontas moram em duas lojas que a casa já tem:

- **sinal → decisão:** o livro. Um pedido é um registro com `precisa_do_dono`;
  a decisão é o registro que `responde_a` ele. A caixa "precisa de você" faz
  a mesma conta para listar; aqui ela vira tempo.
- **decisão → execução:** a fila de trabalho. Uma tarefa nasce em
  `fila/tarefas/` com `criada_em`; o começo é o primeiro evento
  `reivindicada` dela em `fila/eventos/`.
- **experimento → aprendizado:** o livro. Um experimento fechado é um
  registro tipo `medicao` que `responde_a` outro; o aprendizado é o registro
  posterior que responde à medição.

Os três são cartões de tipo `confianca`: medem a gestão, não a escola, e não
podem ser forçados sem produzir o próprio fato que medem. Zero pedido aberto
é zero; "nenhum experimento fechado" é dito, nunca vira zero dias.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from statistics import median

from .placar import dia_em_sao_paulo

#: `apps/core/latencias.py` → `apps/core` → `apps` → a raiz da célula.
RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

#: A fila: embutida na imagem (produção) ou a do repositório (checkout, teste).
#: Só `tarefas/` e `eventos/`, que são arquivos crus; os ESTADOS materializados
#: continuam sendo só da embutida (`robos.py`).
CANDIDATOS_DA_FILA = (
    RAIZ_DA_CELULA / "fila_embutida",
    RAIZ_DA_CELULA.parent.parent / "fila",
)

JANELA = 28
#: Tarefa na fila há mais que isto sem ninguém pegar é trabalho decidido e parado.
DIAS_PARADA = 7


def diretorio_da_fila() -> Path | None:
    for candidato in CANDIDATOS_DA_FILA:
        if (candidato / "tarefas").is_dir() and (candidato / "eventos").is_dir():
            return candidato
    return None


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------- sinal → decisão


def latencia_de_decisao(registros: list[dict] | None, hoje: dt.date) -> dict:
    if registros is None:
        return {"veredito": "nao-consigo-medir"}
    por_arquivo = {r["arquivo"]: r for r in registros}
    respostas: dict[str, dt.date] = {}
    for r in registros:
        alvo = r.get("responde_a")
        quando = _data(r.get("quando"))
        if alvo and quando and (alvo not in respostas or quando < respostas[alvo]):
            respostas[alvo] = quando
    esperas = []
    abertos = []
    for r in registros:
        if not r.get("precisa_do_dono"):
            continue
        pedido = _data(r.get("quando"))
        if pedido is None:
            continue
        resposta = respostas.get(r["arquivo"])
        if resposta is None:
            abertos.append((hoje - pedido).days)
        elif 0 <= (hoje - resposta).days < JANELA and resposta >= pedido:
            esperas.append((resposta - pedido).days)
    return {
        "veredito": "medido" if esperas or abertos else "sem-dados-ainda",
        "mediana_dias": median(esperas) if esperas else None,
        "respondidos_28": len(esperas),
        "abertos": len(abertos),
        "mais_velho_dias": max(abertos) if abertos else None,
    }


# --------------------------------------------------------- decisão → execução


def ler_a_fila(pasta: Path | None = None) -> dict | None:
    """`{ "tarefas": {id: criada_em}, "reivindicadas": {id: primeiro instante} }`."""
    pasta = pasta if pasta is not None else diretorio_da_fila()
    if pasta is None:
        return None
    tarefas: dict[str, dt.date] = {}
    bloqueadas: set[str] = set()
    for arquivo in (
        sorted((pasta / "tarefas").glob("*.json"))
        if (pasta / "tarefas").is_dir()
        else []
    ):
        try:
            t = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        criada = _data(t.get("criada_em"))
        if t.get("id") and criada:
            tarefas[t["id"]] = criada
    reivindicadas: dict[str, dt.date] = {}
    terminadas: set[str] = set()
    for arquivo in (
        sorted((pasta / "eventos").glob("*.json"))
        if (pasta / "eventos").is_dir()
        else []
    ):
        try:
            e = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tarefa = e.get("tarefa")
        dia = dia_em_sao_paulo(e.get("quando")) or _data(e.get("quando"))
        if not tarefa or dia is None:
            continue
        if e.get("evento") == "reivindicada":
            if tarefa not in reivindicadas or dia < reivindicadas[tarefa]:
                reivindicadas[tarefa] = dia
        elif e.get("evento") == "bloqueada":
            bloqueadas.add(tarefa)
        elif e.get("evento") in ("concluida", "cancelada"):
            terminadas.add(tarefa)
    return {
        "tarefas": tarefas,
        "reivindicadas": reivindicadas,
        "bloqueadas": bloqueadas,
        "terminadas": terminadas,
    }


def latencia_de_execucao(fila: dict | None, hoje: dt.date) -> dict:
    if fila is None:
        return {"veredito": "nao-consigo-medir"}
    esperas = []
    paradas = 0
    for tarefa, criada in fila["tarefas"].items():
        pegou = fila["reivindicadas"].get(tarefa)
        if pegou is not None:
            if 0 <= (hoje - pegou).days < JANELA and pegou >= criada:
                esperas.append((pegou - criada).days)
        elif tarefa not in fila["bloqueadas"] and tarefa not in fila["terminadas"]:
            if (hoje - criada).days > DIAS_PARADA:
                paradas += 1
    return {
        "veredito": "medido" if esperas or paradas else "sem-dados-ainda",
        "mediana_dias": median(esperas) if esperas else None,
        "pegas_28": len(esperas),
        "paradas": paradas,
    }


# ----------------------------------------------------- experimento → aprendizado


def latencia_de_aprendizado(registros: list[dict] | None, hoje: dt.date) -> dict:
    if registros is None:
        return {"veredito": "nao-consigo-medir"}
    respostas: dict[str, dt.date] = {}
    for r in registros:
        alvo = r.get("responde_a")
        quando = _data(r.get("quando"))
        if alvo and quando and (alvo not in respostas or quando < respostas[alvo]):
            respostas[alvo] = quando
    esperas = []
    fechados_sem_aprendizado = 0
    for r in registros:
        if r.get("tipo") != "medicao" or not r.get("responde_a"):
            continue
        fechado = _data(r.get("quando"))
        if fechado is None or not 0 <= (hoje - fechado).days < JANELA:
            continue
        aprendizado = respostas.get(r["arquivo"])
        if aprendizado is None:
            fechados_sem_aprendizado += 1
        elif aprendizado >= fechado:
            esperas.append((aprendizado - fechado).days)
    if not esperas and not fechados_sem_aprendizado:
        return {"veredito": "sem-dados-ainda"}
    return {
        "veredito": "medido",
        "mediana_dias": median(esperas) if esperas else None,
        "com_aprendizado_28": len(esperas),
        "sem_aprendizado": fechados_sem_aprendizado,
    }


def medir_as_latencias(
    registros: list[dict] | None, fila: dict | None, hoje: dt.date
) -> dict:
    return {
        "decisao": latencia_de_decisao(registros, hoje),
        "execucao": latencia_de_execucao(fila, hoje),
        "aprendizado": latencia_de_aprendizado(registros, hoje),
    }
