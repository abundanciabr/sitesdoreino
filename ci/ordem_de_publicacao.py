"""ORDEM DE PUBLICAÇÃO — quem sobe antes de quem, derivado do código.

O PROBLEMA QUE ISTO FECHA
-------------------------
O `deploy-celula` publica uma célula por vez (`max-parallel: 1`), mas na ordem
em que a detecção as devolveu — que é alfabética, isto é, arbitrária. Num push
que toca `checkout` e `pagamentos` juntos, `checkout` sobe PRIMEIRO e passa
alguns minutos falando com uma versão de `pagamentos` que ainda não existe. O
site fica no ar respondendo errado, sem nada ficar vermelho.

A ordem certa é **provedor antes de consumidor**: quando o consumidor chega, a
API de que ele precisa já está de pé.

DE ONDE VEM O GRAFO
-------------------
De `celulas.yml`: a chave `consome` de cada célula diz de quem ela lê API.

CICLO NÃO BLOQUEIA A ENTREGA — MAS NUNCA PASSA CALADO
------------------------------------------------------
Se duas células se consomem em círculo, não existe ordem perfeita. Recusar
publicar seria transformar uma questão de arquitetura em site parado; escolher
em silêncio seria mentir. Então ele desempata pelo alfabeto DENTRO do ciclo e
ANUNCIA, com nome e sobrenome, quais células formam o círculo.

Uso:

    python ci/ordem_de_publicacao.py '["checkout","pagamentos"]'
    ORDEM_CELULAS='["checkout","pagamentos"]' python ci/ordem_de_publicacao.py

Escreve em stdout o JSON ordenado (é isso que o workflow consome) e a
explicação legível em stderr — separados de propósito, para o `$(...)` do YAML
nunca engolir texto de explicação junto com o dado.

Exit codes:

    0  ordenei (a explicação diz como)
    2  ERROR: não consegui medir. Célula fora de `celulas.yml` entra aqui: um
       nome que ninguém declarou viraria uma matriz de deploy inventada.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mapa_de_celulas  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    raiz_declarada,
    raiz_do_repo,
)

def _raiz() -> Path:
    declarada = os.environ.get("ORDEM_RAIZ", "").strip()
    return raiz_declarada(Path(declarada)) if declarada else raiz_do_repo()


def celulas_declaradas(raiz: Path) -> list[str]:
    """A lista autoritativa é `celulas.yml`."""
    return sorted(mapa_de_celulas.carregar(raiz))


def dependencias(raiz: Path, celulas: list[str]) -> dict[str, set[str]]:
    """Para cada célula, de quais OUTRAS ela consome, lido de `celulas.yml`."""
    mapa = mapa_de_celulas.carregar(raiz)
    return {nome: set(celula.consome) for nome, celula in mapa.items() if nome in celulas}


def ordenar(
    tocadas: list[str], grafo: dict[str, set[str]]
) -> tuple[list[str], list[str]]:
    """Provedor antes de consumidor. Devolve (ordem, avisos).

    Kahn com desempate alfabético: o desempate não é estética — sem ele, dois
    runs do MESMO push poderiam publicar em ordens diferentes, e a ordem
    deixaria de ser uma propriedade para virar sorte.
    """
    alvo = set(tocadas)
    # Só as arestas ENTRE as células tocadas importam: uma dependência que não
    # está sendo publicada agora já está no ar, e não tem ordem a respeitar.
    entrada = {c: sorted(grafo.get(c, set()) & alvo) for c in sorted(alvo)}
    ordem: list[str] = []
    avisos: list[str] = []
    pendentes = dict(entrada)
    while pendentes:
        prontas = sorted(c for c, deps in pendentes.items() if not deps)
        if not prontas:
            # Ciclo. Não bloqueia: desempata pelo alfabeto e ANUNCIA.
            preso = sorted(pendentes)
            avisos.append(
                "CICLO entre "
                + ", ".join(preso)
                + " — não existe ordem perfeita entre elas. Publiquei em ordem "
                "alfabética dentro do ciclo. Isto é uma questão de arquitetura "
                "para resolver, não um erro desta entrega."
            )
            prontas = [preso[0]]
        for celula in prontas:
            ordem.append(celula)
            pendentes.pop(celula, None)
        for deps in pendentes.values():
            for celula in prontas:
                if celula in deps:
                    deps.remove(celula)
    return ordem, avisos


def _entrada() -> list[str]:
    bruto = ""
    if len(sys.argv) > 1:
        bruto = sys.argv[1].strip()
    if not bruto:
        bruto = os.environ.get("ORDEM_CELULAS", "").strip()
    if not bruto:
        raise ErroDeInstrumentacao(
            "nenhuma lista de células recebida",
            "Passe o JSON como argumento ou em ORDEM_CELULAS. Lista ausente NÃO "
            "é lista vazia: quem chama precisa dizer o que está publicando.",
        )
    try:
        valor = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            "a lista de células não é json válido", f"Recebido:\n  {bruto}\n\n{exc}"
        ) from exc
    if not isinstance(valor, list) or not all(isinstance(c, str) for c in valor):
        raise ErroDeInstrumentacao(
            "a lista de células precisa ser um array json de strings",
            f"Recebido:\n  {bruto}",
        )
    return valor


def main() -> int:
    configurar_saida()
    try:
        raiz = _raiz()
        tocadas = _entrada()
        declaradas = celulas_declaradas(raiz)
        desconhecidas = sorted(set(tocadas) - set(declaradas))
        if desconhecidas:
            raise ErroDeInstrumentacao(
                "célula fora de celulas.yml na lista a publicar: "
                + ", ".join(desconhecidas),
                "Declaradas em celulas.yml:\n"
                + "\n".join(f"  - {c}" for c in declaradas)
                + "\n\nOrdenar um nome que ninguém declarou seria montar uma "
                "matriz de deploy inventada.",
            )
        grafo = dependencias(raiz, declaradas)
        ordem, avisos = ordenar(tocadas, grafo)

        print(json.dumps(ordem, ensure_ascii=False))
        print("ORDEM DE PUBLICAÇÃO — provedor antes de consumidor", file=sys.stderr)
        for posicao, celula in enumerate(ordem, start=1):
            deps = sorted(grafo.get(celula, set()) & set(tocadas))
            motivo = (" (depende de: " + ", ".join(deps) + ")") if deps else ""
            print(f"  {posicao}. {celula}{motivo}", file=sys.stderr)
        for aviso in avisos:
            print(f"  ⚠️ {aviso}", file=sys.stderr)
        return 0
    except ErroDeInstrumentacao as erro:
        print(f"ERROR ordem_de_publicacao: {erro.resumo}", file=sys.stderr)
        if erro.detalhe:
            print(erro.detalhe, file=sys.stderr)
        print(
            "A ordem NÃO foi calculada. Publicar sem ela seria publicar numa "
            "ordem que ninguém escolheu.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
