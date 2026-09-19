#!/usr/bin/env python3
"""VIGIA DO SITE — a loja abre? Perguntado DE FORA, pela internet pública.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Até 18/09/2026 nenhum mecanismo desta casa perguntava se o site RESPONDE.
O inventário, medido na `origin/main`:

  - `ci/vigia_do_cadeado.py` era o único olho externo, e ele importa `ssl`,
    abre um handshake e lê `notAfter`. Nenhuma requisição HTTP, nenhum código
    de status. Um Traefik com cadeado perfeito na frente de células mortas
    passava nele todo dia.
  - `git grep -niE "autoheal|watchtower|uptime" -- infra/ ci/ .github/` volta
    vazio.
  - `ci/sonda_da_vps.py::http_do_site` sabe medir um status, mas só é chamada
    DENTRO do diagnóstico de um deploy doente, num endereço fixo. Deploy que
    não acontece é medição que não acontece.
  - O `healthcheck` do compose só é LIDO no `up -d --wait` da publicação. Em
    regime, `restart: unless-stopped` reage a processo MORTO, nunca a processo
    vivo e travado: uvicorn com pool esgotado, consumidor em deadlock, migrate
    pendurado.

Resultado: a loja podia amanhecer fechada e o primeiro a descobrir seria um
visitante. É GARANTIA SEM MECANISMO, um dos oito padrões da
`docs/decisoes/RETROSPECTIVA-FASE-D.md`. Este arquivo é o mecanismo.

PROVA DE FORA
-------------
A medição sai do runner do Actions, pela internet pública, como a do vigia do
cadeado e a do smoke do `deploy-infra`. O que vale é o que o VISITANTE recebe:
perguntar ao container se ele está bem é deixá-lo dar a própria nota.

FAIL-CLOSED (INV-CI01)
----------------------
"Não consegui medir" nunca vira "está no ar". A distinção entre os dois modos
de não passar está escrita aqui e é deliberada:

  FAIL  (1) — o host não entregou a página: status diferente de 200, DNS que
              não resolve, porta fechada, tempo estourado. Tudo isso é a loja
              fechada para quem chega, que é exatamente o fato a vigiar.
  ERROR (2) — o INSTRUMENTO quebrou: a lista de hosts saiu vazia, o registro
              de sites não abriu. "Medi zero hosts, todos passaram" é o
              falso-verde de vacuidade, e é a mentira que o INV-CI01 mata.

O oposto também está guardado: uma queda de rede de um segundo não pode abrir
chamado. Por isso `medir()` insiste algumas vezes, com pausa, ANTES de dizer
que não conseguiu. Um status ruim, ao contrário, é fato estável: repeti-lo só
atrasaria o alarme.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from vigia_do_cadeado import (
    PAUSA_ENTRE_TENTATIVAS,
    ROTAS,
    SITES,
    TENTATIVAS,
    a_vigiar,
)

# A régua. Um número só, num lugar só: a raiz de todo site listado tem de
# entregar a página. É o mesmo contrato que o smoke do `deploy-infra` já exige
# por dentro da VPS (raiz 200) — aqui ele passa a valer também nos 23 dias
# seguidos em que ninguém publica nada.
RESPOSTA_ESPERADA = 200

TEMPO_MAXIMO = 15.0  # segundos por tentativa; teto explícito, nunca espera aberta

# Quem está batendo na porta, dito no log de acesso do servidor. Um user agent
# anônimo transformaria a própria vigilância num acesso suspeito de origem
# desconhecida no dia em que alguém for ler o log.
CRACHA = "vigia-do-site/1.0 (+https://github.com/abundanciabr/sitesdoreino)"

# QUEM SONDAR — a MESMA lista do vigia do cadeado, de propósito. Duas listas
# divergem sozinhas no dia em que um site novo nasce: uma é atualizada, a outra
# não, e ninguém percebe porque as duas continuam verdes. `a_vigiar` lê
# `infra/sites.json` (todo site ativo) mais os `www.` que têm router próprio, e
# devolve, por escrito, quem ficou de fora e por quê.
a_sondar = a_vigiar


@dataclass(frozen=True)
class Resposta:
    """O que a raiz do host devolveu — ou por que não devolveu nada."""

    status: int | None = None
    url_final: str | None = None
    erro: str | None = None


# ---------------------------------------------------------------------------
# A MEDIÇÃO — rede de verdade, com insistência limitada.
# ---------------------------------------------------------------------------
def _uma_tentativa(host: str, timeout: float) -> Resposta:
    pedido = urllib.request.Request(
        f"https://{host}/", method="GET", headers={"User-Agent": CRACHA}
    )
    try:
        # Redirecionamento é seguido de propósito: a raiz do `www.` responde
        # 301 por desenho (armadilhas/177), e o visitante que digita o `www.`
        # termina na página. O que se julga é onde ele CHEGA.
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return Resposta(status=int(resposta.status), url_final=resposta.geturl())
    except urllib.error.HTTPError as erro:
        # O servidor respondeu, e respondeu mal. Isto é medição, não falha de
        # medição: 500, 502 e 404 são exatamente o que este vigia procura.
        return Resposta(status=int(erro.code), url_final=erro.url)
    except (urllib.error.URLError, OSError, ValueError) as erro:
        # Nem chegou a haver resposta: DNS, porta fechada, TLS, tempo estourado.
        return Resposta(erro=f"não consegui medir: {erro}")


def medir(host: str, timeout: float = TEMPO_MAXIMO) -> Resposta:
    """Mede insistindo um pouco: blip de rede não pode virar chamado aberto.

    A insistência (as mesmas 3 tentativas e a mesma pausa do vigia do cadeado,
    importadas de lá para que os dois não possam divergir) vale só para o "não
    consegui medir". Status recebido é fato estável.
    """
    ultima = Resposta(erro="não consegui medir: nenhuma tentativa foi feita")
    for tentativa in range(1, TENTATIVAS + 1):
        ultima = _uma_tentativa(host, timeout)
        if ultima.erro is None:
            return ultima
        if tentativa < TENTATIVAS:
            time.sleep(PAUSA_ENTRE_TENTATIVAS)
    return ultima


# ---------------------------------------------------------------------------
# O JULGAMENTO — função pura, para os testes a exercitarem sem rede.
# ---------------------------------------------------------------------------
def julgar(host: str, resposta: Resposta) -> list[str]:
    """As queixas sobre UM host. Lista vazia = a loja está aberta."""
    if resposta.erro is not None:
        return [
            f"{host}: não entregou página nenhuma — {resposta.erro}. O vigia já "
            f"insistiu {TENTATIVAS} vezes, então não é soluço de rede: ou o DNS, "
            "ou a porta 443, ou o servidor inteiro está fora do ar."
        ]
    if resposta.status is None:
        return [f"{host}: medição pela metade, sem status e sem erro — isso é não medir"]
    if resposta.status != RESPOSTA_ESPERADA:
        return [
            f"{host}: respondeu {resposta.status} na raiz, e a raiz de todo site "
            f"listado tem de responder {RESPOSTA_ESPERADA}. O cadeado pode estar "
            "perfeito e a loja, fechada: 5xx é célula viva e travada (o `restart` "
            "do compose só reage a processo morto), 404 na raiz é site sem oferta "
            "padrão em infra/sites.json."
        ]
    return []


def linha_de_estado(host: str, resposta: Resposta) -> str:
    """Uma linha por host, verde ou não — log que se lê sem abrir mais nada."""
    if resposta.status is None:
        return f"  {host:<28} {'FAIL':<5}{resposta.erro or 'sem status e sem erro'}"
    veredito = "PASS" if resposta.status == RESPOSTA_ESPERADA else "FAIL"
    destino = f" · {resposta.url_final}" if resposta.url_final else ""
    return f"  {host:<28} {veredito:<5}HTTP {resposta.status}{destino}"


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vigia do site: pergunta de fora se cada host responde."
    )
    parser.add_argument("--host", action="append", help="sondar só este host (repetível)")
    parser.add_argument("--timeout", type=float, default=TEMPO_MAXIMO)
    args = parser.parse_args(argv)

    print("VIGIA DO SITE — [INV-CI01] fail-closed · prova de fora\n")

    if args.host:
        hosts, dispensados = list(args.host), []
    else:
        try:
            registro = json.loads(SITES.read_text(encoding="utf-8"))
            hosts, dispensados = a_sondar(registro, ROTAS.read_text(encoding="utf-8"))
        except (OSError, ValueError, AssertionError) as erro:
            print(f"  lista de hosts       ERROR  não consegui montá-la: {erro}")
            print("\nRESULTADO  ERROR — instrumento quebrado, nada foi medido.")
            return 2

    if not hosts:
        print("  lista de hosts       ERROR  saiu VAZIA — nada foi medido")
        print("\nRESULTADO  ERROR — instrumento quebrado, nada foi medido.")
        return 2

    queixas: list[str] = []
    for host in hosts:
        resposta = medir(host, timeout=args.timeout)
        print(linha_de_estado(host, resposta))
        queixas.extend(julgar(host, resposta))

    if dispensados:
        print("\n  dispensados de propósito (declarado, não esquecido):")
        for linha in dispensados:
            print(f"    - {linha}")

    if queixas:
        print("\n--- FAIL site " + "-" * 56)
        for queixa in queixas:
            print(f"  {queixa}")
        print("\nRESULTADO  FAIL")
        return 1

    print(f"\nRESULTADO  PASS — {len(hosts)} host(s), todos entregando a página.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
