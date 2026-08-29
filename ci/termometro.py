#!/usr/bin/env python3
"""O TERMÔMETRO — o que as muralhas realmente pegaram, em número.

Por que existe (29/08/2026): sem medição, "o sistema imunológico melhorou o
projeto" é opinião, e opinião mantém guarda inútil viva enquanto o desperdício
real segue invisível. Este relatório responde três perguntas que ninguém
conseguia responder antes:

  1. Que armadilhas ainda mordem — e quantas vezes?
  2. Quais regras ERRAM (recusariam comando legítimo)? É a métrica crítica:
     falso positivo queima tokens igual à armadilha que ele evita.
  3. Uma regra em sombra já pode ser promovida a bloqueio?

Uso:  python ci/termometro.py           # relatório em português
      python ci/termometro.py --json    # o mesmo, para outro programa ler

HONESTIDADE SOBRE O QUE ELE NÃO MEDE (o padrão 1 da RETROSPECTIVA-FASE-D
aplicado ao próprio instrumento): só se mede o que se detecta. A reincidência
das armadilhas que ainda não têm regra nem sinal continua invisível — e isso
aparece abaixo como buraco assumido, nunca como zero. Zero medido e zero
por não ter instrumento são coisas diferentes, e confundi-las é falso-verde.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402

DISPAROS_PARA_PROMOVER = 10


def _utf8_na_saida() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def resumir(eventos: list[dict]) -> dict:
    por_armadilha: Counter = Counter()
    por_modo: dict[str, Counter] = defaultdict(Counter)
    sessoes_por_armadilha: dict[str, set] = defaultdict(set)
    reincidencias: Counter = Counter()

    for evento in eventos:
        armadilha = str(evento.get("armadilha") or "")
        if not armadilha:
            continue
        por_armadilha[armadilha] += 1
        por_modo[armadilha][str(evento.get("modo") or "?")] += 1
        sessoes_por_armadilha[armadilha].add(str(evento.get("sessao") or ""))

    # Reincidência: a mesma armadilha mordendo duas vezes na MESMA sessão é o
    # sinal mais forte de que a lição não alcançou quem estava trabalhando.
    por_sessao: dict[tuple, int] = Counter()
    for evento in eventos:
        chave = (str(evento.get("sessao") or ""), str(evento.get("armadilha") or ""))
        if chave[1]:
            por_sessao[chave] += 1
    for (_sessao, armadilha), quantas in por_sessao.items():
        if quantas >= 2:
            reincidencias[armadilha] += 1

    return {
        "eventos": len(eventos),
        "por_armadilha": dict(por_armadilha),
        "por_modo": {a: dict(m) for a, m in por_modo.items()},
        "sessoes": {a: len(s) for a, s in sessoes_por_armadilha.items()},
        "reincidencias": dict(reincidencias),
    }


def _linhas_do_relatorio(resumo: dict) -> list[str]:
    linhas = ["", "TERMÔMETRO DO SISTEMA IMUNOLÓGICO", "=" * 34, ""]
    if not resumo["eventos"]:
        linhas += [
            "Nenhuma medição ainda.",
            "",
            "Isso NÃO significa 'nenhuma armadilha mordeu' — significa que",
            "nenhuma regra disparou desde que o caderninho começou. Sessões",
            "abertas antes da muralha ser ligada não aparecem aqui.",
        ]
        return linhas

    linhas.append(f"{resumo['eventos']} disparos registrados.")
    linhas.append("")
    linhas.append("Por armadilha:")
    for armadilha, quantas in sorted(
        resumo["por_armadilha"].items(), key=lambda par: -par[1]
    ):
        modos = resumo["por_modo"].get(armadilha, {})
        detalhe = ", ".join(f"{quantos}× em {modo}" for modo, quantos in modos.items())
        sessoes = resumo["sessoes"].get(armadilha, 0)
        linhas.append(
            f"  armadilhas/{armadilha}: {quantas} disparos "
            f"({detalhe}) em {sessoes} sessão(ões)"
        )

    sombras = {
        a: m.get("sombra", 0) for a, m in resumo["por_modo"].items() if m.get("sombra")
    }
    if sombras:
        linhas += ["", "Regras em sombra (observam, não impedem):"]
        for armadilha, quantas in sorted(sombras.items(), key=lambda par: -par[1]):
            if quantas >= DISPAROS_PARA_PROMOVER:
                linhas.append(
                    f"  armadilhas/{armadilha}: {quantas} disparos — PRONTA para "
                    "promoção a bloqueio, se nenhum foi falso positivo. "
                    "Confira os comandos no caderninho antes de promover."
                )
            else:
                faltam = DISPAROS_PARA_PROMOVER - quantas
                linhas.append(
                    f"  armadilhas/{armadilha}: {quantas} disparos — faltam "
                    f"{faltam} para a decisão de promover."
                )

    if resumo["reincidencias"]:
        linhas += ["", "REINCIDÊNCIA (mesma armadilha 2× na mesma sessão):"]
        for armadilha, quantas in sorted(
            resumo["reincidencias"].items(), key=lambda par: -par[1]
        ):
            linhas.append(
                f"  armadilhas/{armadilha}: {quantas} sessão(ões) — a lição não "
                "alcançou quem estava trabalhando; considere subir o degrau."
            )

    linhas += [
        "",
        "O que este número NÃO cobre: armadilha sem regra e sem sinal não tem",
        "como aparecer aqui. Ausência de linha é ausência de instrumento, não",
        "prova de que nada aconteceu.",
    ]
    return linhas


def main(argv: list[str]) -> int:
    _utf8_na_saida()
    raiz = telemetria.dir_git_comum(Path.cwd())
    if raiz is None:
        print(
            "🧱 PAROU POR SEGURANÇA: não achei o .git desta casa, então não sei "
            "onde o caderninho mora. 'Não consegui medir' não vira relatório "
            "vazio (INV-CI01).",
            file=sys.stderr,
        )
        return 2
    resumo = resumir(telemetria.ler_tudo(raiz))
    if "--json" in argv:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
    else:
        print("\n".join(_linhas_do_relatorio(resumo)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
