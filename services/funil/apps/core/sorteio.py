"""Qual versão da página este visitante vê, num experimento ativo.

A FÓRMULA É CONTRATO
--------------------
Ela vem do desenho comum do sistema de experimentos (26/09/2026), e o admin
confere o SRM contra os mesmos pesos que ela reparte:

    balde = int(sha256(f"{experimento_id}:{visitor_id}").hexdigest()[:8], 16) % 10000

As variantes são ordenadas por `variante_id` e a escolhida é a primeira cujo
peso acumulado (em pontos-base, somando 10000) passa de `balde`. Nada é
guardado: o mesmo visitante no mesmo experimento cai sempre no mesmo braço,
em qualquer processo e em qualquer máquina. Mudar a fórmula com um experimento
no ar troca gente de braço no meio da medição e contamina as duas amostras.

O `experimento_id` entra no hash para que dois experimentos sorteiem de forma
independente: quem caiu em `a` num não tem mais chance de cair em `a` no outro.

FAIL-OPEN
---------
Experimento malformado ou visitante ausente devolvem `None`, e a página mostra
a versão publicada. Um catálogo com defeito nunca derruba a vitrine; ele só
deixa de medir, e o log de erro diz por quê. `None` na entrada é o caso comum
(nenhum experimento ativo) e passa em silêncio.
"""

import hashlib
import logging
import re

logger = logging.getLogger("funil.sorteio")

#: O total dos pesos em pontos-base: 50/50 é 5000 e 5000.
PONTOS_BASE = 10000

VARIANTE_ID = re.compile(r"[a-z][a-z0-9-]{0,31}")


def balde(experimento_id: str, visitor_id: str) -> int:
    """O número de 0 a 9999 que decide o braço deste visitante."""
    resumo = hashlib.sha256(f"{experimento_id}:{visitor_id}".encode()).hexdigest()
    return int(resumo[:8], 16) % PONTOS_BASE


def sortear(experimento: dict | None, visitor_id: str | None) -> dict | None:
    """A variante (`{variante_id, peso, valor}`) que este visitante vê.

    `experimento` tem a forma de `experimento_ativo` no catálogo:
    `{id, secao, slot, variantes: [{variante_id, peso, valor}]}`.
    """
    if experimento is None:
        return None
    defeito = _defeito(experimento)
    if defeito:
        logger.error(
            "sorteio: experimento %r inválido (%s); a página mostra a versão publicada",
            experimento.get("id") if isinstance(experimento, dict) else experimento,
            defeito,
        )
        return None
    if not visitor_id:
        logger.error(
            "sorteio: experimento %s sem visitor_id; a página mostra a versão publicada",
            experimento["id"],
        )
        return None

    posicao = balde(experimento["id"], visitor_id)
    acumulado = 0
    for variante in sorted(experimento["variantes"], key=lambda v: v["variante_id"]):
        acumulado += variante["peso"]
        if acumulado > posicao:
            break
    return variante


def _defeito(experimento) -> str:
    """O que impede sortear neste experimento, ou `""` se nada impede."""
    if not isinstance(experimento, dict):
        return "não é um objeto"
    if not isinstance(experimento.get("id"), str) or not experimento["id"]:
        return "sem id"
    variantes = experimento.get("variantes")
    if not isinstance(variantes, list) or not variantes:
        return "sem variantes"
    vistos = set()
    for variante in variantes:
        if not isinstance(variante, dict):
            return f"variante {variante!r} não é um objeto"
        vid = variante.get("variante_id")
        if not isinstance(vid, str) or not VARIANTE_ID.fullmatch(vid):
            return f"variante_id {vid!r} fora do padrão ^[a-z][a-z0-9-]{{0,31}}$"
        if vid in vistos:
            return f"variante_id {vid!r} repetida"
        vistos.add(vid)
        peso = variante.get("peso")
        if type(peso) is not int or peso < 0:
            return (
                f"peso {peso!r} da variante {vid!r} não é inteiro de 0 a {PONTOS_BASE}"
            )
    total = sum(v["peso"] for v in variantes)
    if total != PONTOS_BASE:
        return f"pesos somam {total}, não {PONTOS_BASE}"
    return ""
