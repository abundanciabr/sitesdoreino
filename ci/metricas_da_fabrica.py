"""MÉTRICAS DA FÁBRICA — "está apodrecendo?" vira número.

Onda 6 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (P13 e B14). O
diagnóstico da consultoria foi direto: *"vocês estão voando sem instrumento"*.
O projeto media a saúde de cada MUDANÇA (testes, muralhas, portões) e não media
a saúde da FÁBRICA — se ela está ficando mais lenta, mais retrabalhosa, mais
dependente do dono. Sem número, "está apodrecendo?" só tem resposta por
impressão, e impressão de quem está dentro é a pior fonte que existe.

AS QUATRO MEDIDAS, e por que estas
-----------------------------------
1. **Tempo de pouso** (mediana): do PR aberto ao merge. É o relógio do ciclo
   inteiro. Se subir, alguma coisa na esteira está engasgando.
2. **Retrabalho**: quantos pushes um PR precisou depois do primeiro. Foi a dor
   medida em 28/08 — oito voltas num PR de quatro arquivos (`armadilhas/156`).
   É o número que a pista de pouso existe para derrubar.
3. **Devoluções da pista**: PRs que pediram pouso e voltaram reprovados. Taxa
   alta = a catraca está pegando trabalho quebrado cedo (bom) ou a esteira está
   implicando com trabalho são (ruim) — o número sozinho não decide, mas sem
   ele ninguém nem pergunta.
4. **Pedidos ao dono** (B14): quantos registros do livro esperam resposta dele.
   **O mantenedor é o único recurso do projeto que não escala**, e esta é a
   única medida aqui que fala de uma pessoa, não de máquina.

O QUE ELE NÃO FAZ, de propósito
-------------------------------
**Não reprova nada.** Métrica que reprova vira meta, e meta vira gente
otimizando o número em vez do trabalho. Ele mede e mostra; a decisão continua
humana.

**Não guarda estado.** Cada execução mede o presente, direto do GitHub e do
livro. Um arquivo de histórico aqui seria uma segunda fonte de verdade sobre
fatos que o GitHub já guarda — e a lei anti-duplicação do `CLAUDE.md` existe
porque essa segunda fonte SEMPRE diverge (`PLANO-10X`, o painel que mentia).

Uso:

    python ci/metricas_da_fabrica.py            # últimos 7 dias
    python ci/metricas_da_fabrica.py --dias 30

Exit codes: 0 medi e mostrei · 2 ERROR (não consegui medir; nunca "está tudo
bem"). Não existe exit 1: este arquivo não julga.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)

DIAS_PADRAO = 7
ETIQUETA_DE_POUSO = "pousar"

# Teto da AMOSTRA usada para medir tempos — nunca a contagem de entregas. O
# campo `commits` é caro no GraphQL do GitHub, e acima disto a consulta inteira
# é recusada. Quem conta entregas é o Git (ver `coletar`).
TETO_DA_AMOSTRA = 40


def _gh_json(args: list[str], raiz: Path, descricao: str):
    """Consulta o GitHub e devolve JSON — ou levanta. Nunca devolve [] por erro.

    A distinção que este projeto já pagou caro para aprender: "a lista veio
    vazia" e "não consegui perguntar" são fatos diferentes.
    """
    saida = executar(
        ["gh", *args], cwd=raiz, descricao=descricao, exigir_stdout=True
    ).stdout
    try:
        return json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeInstrumentacao(
            f"{descricao}: o GitHub respondeu algo que não é JSON",
            f"Primeiros 300 caracteres:\n{saida[:300]}\n\n{erro}",
        ) from erro


def _quando(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def coletar(raiz: Path, dias: int, agora: datetime | None = None) -> dict:
    """Mede tudo. Qualquer falha interrompe — não existe medida parcial."""
    agora = agora or datetime.now(timezone.utc)
    corte = agora - timedelta(days=dias)

    # A CONTAGEM VEM DO GIT — exata, local, sem teto. A lição é de hoje de
    # manhã (registro 20260828-077): o boletim anunciava "40" num dia de 98
    # porque somava o tamanho da própria lista limitada. Aqui o mesmo erro
    # apareceu na primeira execução — a consulta com `commits` estoura o
    # orçamento do GraphQL acima de ~40 PRs — e a resposta certa não é baixar o
    # teto e chamar de total: é contar noutro lugar.
    contagem = executar(
        [
            "git",
            "rev-list",
            "--count",
            "--first-parent",
            f"--since={dias} days ago",
            "origin/main",
        ],
        cwd=raiz,
        descricao="contar as entregas que pousaram na janela",
        exigir_stdout=True,
    ).stdout.strip()
    if not contagem.isdigit():
        raise ErroDeInstrumentacao(
            "não consegui contar as entregas da janela",
            f"`git rev-list --count --first-parent` devolveu: {contagem!r}",
        )
    pousos = int(contagem)

    # A AMOSTRA, para os tempos. `commits` é o campo caro: com 100 PRs o GitHub
    # recusa a consulta inteira ("exceeds the maximum limit of 500,000 nodes").
    # Ela é amostra POR CONSTRUÇÃO, e o texto diz isso — nunca vira o total.
    mergeados = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(TETO_DA_AMOSTRA),
            "--json",
            "number,title,createdAt,mergedAt,commits",
        ],
        raiz,
        "amostrar os PRs mergeados",
    )
    janela = [
        pr
        for pr in mergeados
        if pr.get("mergedAt") and _quando(pr["mergedAt"]) >= corte
    ]

    minutos = [
        (_quando(pr["mergedAt"]) - _quando(pr["createdAt"])).total_seconds() / 60
        for pr in janela
    ]
    # O retrabalho aparece como COMMITS além do primeiro: cada volta de "a base
    # envelheceu, atualiza e empurra de novo" deixa um commit a mais. É uma
    # aproximação, e está dita como tal — o número exato de pushes exigiria a
    # API de eventos, que é paginada e cara.
    commits = [len(pr.get("commits") or []) for pr in janela]

    devolvidos = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,labels",
        ],
        raiz,
        "listar os PRs abertos",
    )
    na_fila = [
        pr
        for pr in devolvidos
        if any(r.get("name") == ETIQUETA_DE_POUSO for r in pr.get("labels") or [])
    ]

    return {
        "dias": dias,
        "pousos": pousos,
        "amostra": len(janela),
        "minutos": minutos,
        "commits": commits,
        "na_fila": len(na_fila),
        "abertos": len(devolvidos),
        "pedidos_ao_dono": pedidos_ao_dono(raiz),
        "leis_sem_mecanismo": leis_sem_mecanismo(raiz),
    }


def pedidos_ao_dono(raiz: Path) -> int:
    """Pedidos do livro esperando resposta — a fila de UMA pessoa (B14).

    A regra é a MESMA do painel: pedido é registro com `precisa_do_dono: true`
    sem nenhum outro registro apontando `responde_a` para ele. Reimplementar a
    regra aqui daria dois números diferentes para a mesma pergunta no primeiro
    dia em que alguém mexesse numa das cópias — então esta função lê o livro
    cru e aplica a definição, e o teste-guarda compara com o painel.
    """
    pasta = raiz / "painel" / "registros"
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            "painel/registros/ não existe",
            "Sem o livro não dá para medir a fila do mantenedor.",
        )
    pedidos: set[str] = set()
    respondidos: set[str] = set()
    for arquivo in sorted(pasta.glob("*.js")):
        texto = arquivo.read_text(encoding="utf-8")
        ident = arquivo.stem
        if '"precisa_do_dono": true' in texto.replace(" ", "").replace(
            "precisa_do_dono:true", '"precisa_do_dono": true'
        ) or "precisa_do_dono: true" in texto:
            pedidos.add(ident)
        for linha in texto.splitlines():
            if "responde_a" in linha and '"' in linha:
                alvo = linha.split('"')
                if len(alvo) >= 2 and alvo[-2] and alvo[-2] != "null":
                    respondidos.add(alvo[-2])
    return len(pedidos - respondidos)


def leis_sem_mecanismo(raiz: Path) -> int:
    """Quantas regras ninguém faz valer — o censo da Onda 6, reusado."""
    caminho = raiz / "ci" / "leis-sem-mecanismo.txt"
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "ci/leis-sem-mecanismo.txt ilegível", str(exc)
        ) from exc
    return len(
        [
            linha
            for linha in texto.splitlines()
            if linha.strip() and not linha.strip().startswith("#")
        ]
    )


def montar(dados: dict) -> str:
    """Rende o boletim de saúde. Sem dados, não inventa linha."""
    faltando = [c for c in ("pousos", "minutos", "commits") if c not in dados]
    if faltando:
        raise ErroDeInstrumentacao(
            "medida incompleta — não vou imprimir meia-verdade",
            "Campos ausentes: " + ", ".join(faltando),
        )

    linhas = [
        "",
        "=" * 72,
        f"SAÚDE DA FÁBRICA — últimos {dados['dias']} dia(s)",
        "=" * 72,
        "",
    ]

    if not dados["amostra"]:
        linhas += [
            "Nenhuma entrega pousou na janela. Isto não é 'tudo bem' nem 'tudo",
            "mal' — é ausência de dado. Amplie a janela (--dias) ou volte depois.",
            "",
        ]
    else:
        mediana = statistics.median(dados["minutos"])
        pior = max(dados["minutos"])
        media_commits = statistics.mean(dados["commits"])
        retrabalho = [c for c in dados["commits"] if c > 2]
        linhas += [
            f"POUSOS                {dados['pousos']} entrega(s) — contadas no Git",
            f"TEMPO DE POUSO        mediana {mediana:.0f} min · pior {pior:.0f} min",
            f"                      (do PR aberto ao merge; amostra de "
            f"{dados['amostra']} PR(s))",
            f"RETRABALHO            média de {media_commits:.1f} commit(s) por PR;"
            f" {len(retrabalho)} PR(s) com mais de 2",
            "                      (cada volta de 'a base envelheceu' deixa um commit)",
            "",
        ]

    linhas += [
        f"NA FILA DA PISTA      {dados['na_fila']} de {dados['abertos']} PR(s) abertos",
        f"PEDIDOS AO DONO       {dados['pedidos_ao_dono']} esperando resposta dele",
        "                      (é o único recurso do projeto que não escala)",
        f"LEIS SEM MECANISMO    {dados['leis_sem_mecanismo']} regra(s) que ninguém faz valer",
        "",
        "Este arquivo MEDE e não julga: nenhum destes números reprova nada.",
        "Métrica que reprova vira meta, e meta vira gente otimizando o número.",
        "=" * 72,
        "",
    ]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Métricas da fábrica (Onda 6)")
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO)
    args = parser.parse_args(argv)
    if args.dias < 1:
        print("ERROR: --dias precisa ser >= 1.")
        return 2
    try:
        raiz = raiz_do_repo()
        print(montar(coletar(raiz, args.dias)))
    except ErroDeInstrumentacao as erro:
        print("\nPAROU POR SEGURANÇA — as métricas NÃO foram impressas.\n")
        print(f"  {erro.resumo}")
        if erro.detalhe:
            print(f"\n{erro.detalhe}")
        print(
            "\nIsto não é 'a fábrica está bem': é não saber. Meia-medida sobre "
            "saúde\nengana mais que medida nenhuma.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
