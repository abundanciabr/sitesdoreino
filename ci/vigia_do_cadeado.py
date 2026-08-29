#!/usr/bin/env python3
"""VIGIA DO CADEADO — o certificado de cada site, medido DE FORA, todo dia.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
A renovação do certificado já é automática: o Traefik pede um novo ~30 dias
antes de vencer (`certResolver: le`), e o `acme.json` mora num volume nomeado
(`letsencrypt:` em `infra/docker-compose.yml`) que sobrevive a toda republicação
— os dois pré-requisitos estão certos.

O que NÃO existia era alguém conferindo se a renovação ACONTECEU. E é aí que
mora o perigo, porque a `armadilhas/018` mediu o modo de falha: **se o ACME
falhar, o Traefik serve o `TRAEFIK DEFAULT CERT` indefinidamente e não avisa
ninguém.** O site cai na tela vermelha `NET::ERR_CERT_AUTHORITY_INVALID` e a
primeira pessoa a descobrir é um visitante — ou o mantenedor, por acaso, como
em 29/08/2026 (`armadilhas/177`).

"Renova sozinho" sem ninguém medindo é GARANTIA SEM MECANISMO, um dos oito
padrões da `docs/decisoes/RETROSPECTIVA-FASE-D.md`. Este arquivo é o mecanismo.

PROVA DE FORA
-------------
A medição é feita pela internet, do runner do Actions — não por dentro da VPS.
É a mesma doutrina do smoke do `deploy-infra`: o que vale é o que o VISITANTE
recebe. Um certificado perfeito no disco do servidor não serve de nada se o
handshake entrega outra coisa (e entregar outra coisa é exatamente a falha da
018, que só se enxerga por SNI, de fora).

FAIL-CLOSED (INV-CI01)
----------------------
"Não consegui medir" NUNCA vira "está limpo". Host que não responde reprova,
lista de hosts vazia reprova, `notAfter` ilegível reprova. O modo de falha
deste arquivo é gritar demais, nunca calar.

O oposto disso também está guardado: uma queda de rede de um segundo não pode
abrir chamado. Por isso `medir()` insiste algumas vezes, com pausa, ANTES de
declarar que não conseguiu — espera com limite, nunca laço aberto.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import socket
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SITES = RAIZ / "infra" / "sites.json"
ROTAS = RAIZ / "infra" / "traefik" / "dynamic" / "plataforma.yml"

# A régua, e o raciocínio por trás do número — não é chute:
#   90 dias  = validade de um certificado Let's Encrypt.
#   30 dias  = quando o Traefik COMEÇA a tentar renovar.
#   21 dias  = quando este vigia grita.
# A janela de 9 dias entre 30 e 21 é o espaço para a renovação acontecer sem
# ninguém ser acordado. Se ainda faltam menos de 21 dias, a renovação teve mais
# de uma semana e NÃO aconteceu: isso não é "ainda dá tempo", é defeito.
# Sobram 21 dias de folga para consertar com calma — mais do que o suficiente,
# já que o conserto é um merge que recria o container (armadilhas/018).
DIAS_PARA_GRITAR = 21

# O crachá de fábrica do Traefik. Não é um parser de X.509: é uma checagem
# NOMINAL do caso conhecido, para que a mensagem possa dizer o nome exato do
# problema em vez de um "certificado não confiável" genérico. Qualquer outro
# certificado ruim continua reprovando pela verificação de verdade, abaixo.
MARCA_DO_CRACHA_DE_FABRICA = b"TRAEFIK DEFAULT CERT"

TENTATIVAS = 3
PAUSA_ENTRE_TENTATIVAS = 5  # segundos


@dataclass(frozen=True)
class Medicao:
    """O que o handshake devolveu — ou por que não devolveu nada."""

    confia: bool
    vence_em: dt.date | None = None
    emissor: str | None = None
    cracha_de_fabrica: bool = False
    erro: str | None = None


# ---------------------------------------------------------------------------
# QUEM VIGIAR — lido do próprio projeto, para que site novo nasça vigiado.
# ---------------------------------------------------------------------------
RE_HOST = re.compile(r"Host\(\s*`([^`]+)`\s*\)")


def hosts_dos_sites(registro: dict) -> list[str]:
    """Todo host ATIVO de infra/sites.json."""
    sites = registro.get("sites")
    if not isinstance(sites, list):
        raise AssertionError("infra/sites.json sem `sites` — nada foi medido")
    return [
        s["host"]
        for s in sites
        if isinstance(s, dict) and s.get("host") and s.get("active", False)
    ]


def hosts_das_rotas(texto_das_rotas: str) -> set[str]:
    """Todo host nomeado num `Host(...)` da tabela de rotas do Traefik."""
    return set(RE_HOST.findall(texto_das_rotas))


def a_vigiar(registro: dict, texto_das_rotas: str) -> tuple[list[str], list[str]]:
    """(hosts vigiados, dispensados com o motivo escrito).

    Vigiamos: todo site ativo, MAIS todo `www.` que tenha router próprio — é o
    caso do `www.meshcraft.top`, que não está (e não deve estar) no sites.json,
    porque o smoke do deploy-infra exige 200 na raiz de todo host listado e a
    raiz do `www.` responde 301 de propósito (`armadilhas/177`).

    Dispensamos, POR ESCRITO e visível na saída: host de router que não é `www.`
    de um site nosso — hoje, só o domínio de operações dos webhooks, que está no
    Modo A (Cloudflare na frente). O TLS público dele é da borda do Cloudflare,
    não deste servidor: medi-lo aqui mediria a Cloudflare, não o nosso ACME.
    Dispensa DECLARADA não é omissão — omissão seria não imprimir esta lista.
    """
    sites = hosts_dos_sites(registro)
    vigiados = list(sites)
    dispensados = []
    for host in sorted(hosts_das_rotas(texto_das_rotas)):
        if host in vigiados:
            continue
        if host.startswith("www.") and host[4:] in sites:
            vigiados.append(host)
        else:
            dispensados.append(f"{host} — não é `www.` de um site ativo nosso")
    return vigiados, dispensados


# ---------------------------------------------------------------------------
# A MEDIÇÃO — rede de verdade, com insistência limitada.
# ---------------------------------------------------------------------------
def _uma_tentativa(host: str, porta: int, timeout: float) -> Medicao:
    contexto = ssl.create_default_context()
    try:
        with socket.create_connection((host, porta), timeout=timeout) as cru:
            with contexto.wrap_socket(cru, server_hostname=host) as tls:
                cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as erro:
        # Verificou e RECUSOU: este é o caso da 018. Volto sem verificar, só
        # para poder NOMEAR o que está sendo servido — o diagnóstico vale a
        # segunda viagem.
        return Medicao(
            confia=False,
            cracha_de_fabrica=_serve_o_cracha_de_fabrica(host, porta, timeout),
            erro=str(erro.verify_message or erro),
        )
    except (OSError, ssl.SSLError) as erro:
        # Nem chegou a julgar o certificado: DNS, porta fechada, timeout.
        return Medicao(confia=False, erro=f"não consegui medir: {erro}")

    if not cert:
        return Medicao(confia=False, erro="handshake sem certificado para ler")
    try:
        segundos = ssl.cert_time_to_seconds(cert["notAfter"])
    except (KeyError, ValueError) as erro:
        return Medicao(confia=False, erro=f"validade ilegível: {erro}")
    return Medicao(
        confia=True,
        vence_em=dt.datetime.fromtimestamp(segundos, dt.timezone.utc).date(),
        emissor=_nome_do_emissor(cert),
    )


def _nome_do_emissor(cert: dict) -> str:
    for parte in cert.get("issuer", ()):
        for chave, valor in parte:
            if chave == "organizationName":
                return valor
    return "emissor desconhecido"


def _serve_o_cracha_de_fabrica(host: str, porta: int, timeout: float) -> bool:
    """Só para nomear o problema; nunca para aprovar nada."""
    sem_verificar = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sem_verificar.check_hostname = False
    sem_verificar.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, porta), timeout=timeout) as cru:
            with sem_verificar.wrap_socket(cru, server_hostname=host) as tls:
                return MARCA_DO_CRACHA_DE_FABRICA in (tls.getpeercert(True) or b"")
    except (OSError, ssl.SSLError):
        return False


def medir(host: str, porta: int = 443, timeout: float = 10.0) -> Medicao:
    """Mede insistindo um pouco: blip de rede não pode virar chamado aberto.

    Só o `não consegui medir` merece nova tentativa. Certificado RECUSADO é um
    fato estável — repetir não muda o veredito e só atrasaria o alarme.
    """
    ultima = Medicao(confia=False, erro="nenhuma tentativa foi feita")
    for tentativa in range(1, TENTATIVAS + 1):
        ultima = _uma_tentativa(host, porta, timeout)
        if ultima.confia or ultima.erro is None or not ultima.erro.startswith("não consegui medir"):
            return ultima
        if tentativa < TENTATIVAS:
            time.sleep(PAUSA_ENTRE_TENTATIVAS)
    return ultima


# ---------------------------------------------------------------------------
# O JULGAMENTO — função pura, para os testes poderem exercitá-la sem rede.
# ---------------------------------------------------------------------------
def julgar(
    host: str, medicao: Medicao, hoje: dt.date, dias_para_gritar: int = DIAS_PARA_GRITAR
) -> list[str]:
    """As queixas sobre UM host. Lista vazia = está tudo bem."""
    if medicao.cracha_de_fabrica:
        return [
            f"{host}: está servindo o `TRAEFIK DEFAULT CERT` — o crachá de fábrica, "
            "que navegador nenhum aceita. O visitante vê a tela vermelha "
            "NET::ERR_CERT_AUTHORITY_INVALID. Causa e conserto: armadilhas/018 "
            "(a emissão só é re-tentada ao RECARREGAR a config; qualquer diff em "
            "infra/traefik/** faz o deploy-infra recriar o container)."
        ]
    if not medicao.confia:
        return [f"{host}: certificado não confiável — {medicao.erro}"]
    if medicao.vence_em is None:
        return [f"{host}: confiou, mas não sei dizer quando vence — isso é não medir"]

    faltam = (medicao.vence_em - hoje).days
    if faltam < 0:
        return [f"{host}: certificado VENCIDO há {-faltam} dia(s), em {medicao.vence_em}"]
    if faltam < dias_para_gritar:
        return [
            f"{host}: vence em {faltam} dia(s) ({medicao.vence_em}) e ainda não "
            f"renovou. O Traefik começa a renovar aos 30 dias — faltando menos de "
            f"{dias_para_gritar}, a renovação teve mais de uma semana e não aconteceu."
        ]
    return []


def linha_de_estado(host: str, medicao: Medicao, hoje: dt.date) -> str:
    """Uma linha por host, verde ou não — log que se lê sem abrir mais nada."""
    if medicao.confia and medicao.vence_em is not None:
        faltam = (medicao.vence_em - hoje).days
        return (
            f"  {host:<28} {'PASS' if faltam >= DIAS_PARA_GRITAR else 'FAIL':<5}"
            f"vence em {faltam} dia(s) ({medicao.vence_em}) · {medicao.emissor}"
        )
    return f"  {host:<28} {'FAIL':<5}{medicao.erro or 'crachá de fábrica'}"


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vigia do cadeado: mede o certificado de cada site, de fora."
    )
    parser.add_argument("--host", action="append", help="medir só este host (repetível)")
    parser.add_argument("--dias", type=int, default=DIAS_PARA_GRITAR)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    print("VIGIA DO CADEADO — [INV-CI01] fail-closed · prova de fora\n")

    if args.host:
        hosts, dispensados = list(args.host), []
    else:
        registro = json.loads(SITES.read_text(encoding="utf-8"))
        hosts, dispensados = a_vigiar(registro, ROTAS.read_text(encoding="utf-8"))

    # Falso-verde de instrumentação: sem host, não há o que medir — e "medi zero
    # hosts, todos passaram" é a mentira que o INV-CI01 existe para matar.
    if not hosts:
        print("  hosts a vigiar     ERROR  a lista saiu VAZIA — nada foi medido")
        print("\nRESULTADO  ERROR")
        return 2

    hoje = dt.datetime.now(dt.timezone.utc).date()
    queixas: list[str] = []
    for host in hosts:
        medicao = medir(host, timeout=args.timeout)
        print(linha_de_estado(host, medicao, hoje))
        queixas.extend(julgar(host, medicao, hoje, args.dias))

    if dispensados:
        print("\n  dispensados de propósito (declarado, não esquecido):")
        for linha in dispensados:
            print(f"    - {linha}")

    if queixas:
        print("\n--- FAIL cadeado " + "-" * 54)
        for q in queixas:
            print(f"  {q}")
        print("\nRESULTADO  FAIL")
        return 1

    print(f"\nRESULTADO  PASS — {len(hosts)} host(s), todos com cadeado válido e folgado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
