#!/usr/bin/env python3
"""A VACINA DA ARMADILHA 127 — o deploy recusado pela VPS se resolve sozinho.

Por que ela existe (29/08/2026): a `armadilhas/127` é o MAIOR sangramento
medido deste catálogo. A contagem de citações no livro de ocorrências deu 5
registros, com frases como "quinta vez em três dias" e "sexta vez"; e ela mordeu
mais uma vez em 29/08/2026, durante a própria auditoria que a elegeu campeã.

Cada queda custava a mesma coisa: um robô relia a entrada, media a porta 22 à
mão, decidia se era blip ou a `armadilhas/017`, repetia o deploy e conferia o
veredito — um diagnóstico do zero, no modelo caro, para um procedimento que é
inteiramente DECIDIDO. Documentar não bastou: a lição estava escrita, completa e
correta, e mesmo assim era re-executada à mão toda vez.

Este script é o degrau 2 da hierarquia da vacina (o procedimento vira
mecanismo), e não o degrau 6 (documentar). O que ele faz, na ordem exata que a
entrada manda:

  1. Colhe o veredito REAL do run por `gh run view --json status,conclusion` —
     nunca pelo exit de um pipe (armadilhas/045).
  2. Se o run não falhou, não faz nada. Repetir o que passou é ruído.
  3. Lê o log do run: a falha É de SSH (`dial tcp ...:22: i/o timeout`)?
     Se não for, PARA. Repetir uma falha de código não conserta código, e
     tratar toda falha como blip é a receita para esconder defeito real.
  4. Mede a porta 22 da VPS, do PC — é a medição que separa a 127 (blip
     intermitente entre o runner e a VPS) da 017 (falha PERMANENTE de
     configuração, território do mantenedor). Porta morta ⇒ PARA e reporta.
  5. Repete o deploy. Entre a segunda e a terceira tentativa, espera —
     em 26/08/2026 duas tentativas falharam a 80 s uma da outra e a terceira,
     depois da pausa, passou. Reruns emendados batem na mesma janela ruim.
  6. Regra de parada: três reruns vermelhos com a porta respondendo ⇒ para,
     e escreve o texto do registro de pendência para o livro. Uma quarta
     tentativa não é diagnóstico.

E diz sempre a frase que o mantenedor precisa ouvir: deploy vermelho por SSH
significa que a imagem NOVA não subiu — a antiga continua servindo, ninguém fica
fora do ar, mas o merge não está em produção até o verde. É fácil esquecer disso
e anunciar a entrega como no ar.

Uso:
    python ci/rerun_de_deploy.py --run <id>        # cuida deste run
    python ci/rerun_de_deploy.py --ultimo          # o último deploy-celula
    python ci/rerun_de_deploy.py --run <id> --so-diagnosticar   # não repete

Semântica de saída [INV-CI01]: 0 PASS (verde, ou nada a fazer) · 1 FAIL (parou
por regra: é a 017, é outra falha, ou estourou a regra de parada) · 2 ERROR
(não consegui medir — e não medir nunca vira "deu certo").
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import configurar_saida  # noqa: E402

VPS_PADRAO = "217.196.62.220"
BANNER_SSH = "SSH-2.0"
SONDA_DO_SITE = "https://meshcraft.top/healthz"
MAXIMO_DE_TENTATIVAS = 3
PAUSA_ENTRE_TENTATIVAS_S = 60
INTERVALO_DE_CONFERENCIA_S = 15
TETO_PADRAO_MIN = 15

RE_TIMEOUT_SSH = re.compile(r"dial tcp [^\n]*:22: i/o timeout")
# Outras falhas de SSH que NÃO são a 127 — não se resolvem repetindo.
RE_SSH_AUTENTICACAO = re.compile(
    r"ssh: handshake failed|permission denied|unable to authenticate", re.IGNORECASE
)


class ErroDeMedicao(Exception):
    """Não consegui medir — vira ERROR (2), nunca um veredito otimista."""


@dataclass
class Fatos:
    """Tudo o que se sabe do mundo. Colher e decidir são separados de propósito:
    a tabela de decisão inteira fica testável sem rede, sem `gh` e sem VPS."""

    run: str
    status: str = ""
    conclusion: str = ""
    tem_timeout_ssh: bool = False
    tem_falha_de_autenticacao: bool = False
    porta22_viva: bool | None = None
    site_http: int | None = None
    tentativas_feitas: int = 0


@dataclass
class Decisao:
    acao: str  # "nada" | "repetir" | "parar"
    codigo: int
    motivo: str
    recado: str = ""
    pendencia: str = field(default="")


def decidir(fatos: Fatos) -> Decisao:
    """A tabela de decisão da armadilhas/127, pura e completa."""
    if fatos.status != "completed":
        return Decisao(
            "nada", 2,
            f"o run {fatos.run} ainda está '{fatos.status}' — não terminou de "
            "ser medido, e medir pela metade não vira veredito (INV-CI01)",
        )
    if fatos.conclusion == "success":
        return Decisao("nada", 0, f"o run {fatos.run} está VERDE — nada a repetir")
    if fatos.conclusion in ("cancelled", "skipped"):
        return Decisao(
            "nada", 1,
            f"o run {fatos.run} terminou '{fatos.conclusion}', não 'failure' — "
            "cancelamento tem causa própria (veja a armadilhas/173) e não se "
            "cura repetindo",
        )
    if fatos.tem_falha_de_autenticacao:
        return Decisao(
            "parar", 1,
            "a falha de SSH é de AUTENTICAÇÃO, não de alcance — chave ou "
            "usuário, território do mantenedor. Repetir não conserta credencial.",
        )
    if not fatos.tem_timeout_ssh:
        return Decisao(
            "parar", 1,
            f"o run {fatos.run} falhou, mas NÃO com o timeout de SSH da "
            "armadilhas/127. Repetir uma falha de código não conserta código — "
            "e trataria um defeito real como blip. Veja o log: "
            f"gh run view {fatos.run} --log-failed",
        )
    if fatos.porta22_viva is False:
        return Decisao(
            "parar", 1,
            "a porta 22 da VPS NÃO respondeu do PC. Isso não é o blip da "
            "armadilhas/127: é a armadilhas/017 (falha permanente — o que o "
            "VPS_HOST resolve? há Cloudflare na frente?). Repetir só gasta "
            "tempo; o conserto é de configuração e passa pelo mantenedor.",
            pendencia=_texto_da_pendencia(fatos, permanente=True),
        )
    if fatos.porta22_viva is None:
        return Decisao(
            "nada", 2,
            "não consegui medir a porta 22 — e sem essa medição não dá para "
            "separar o blip da armadilhas/127 da falha permanente da 017. "
            "'Não medi' não vira 'pode repetir'.",
        )
    if fatos.tentativas_feitas >= MAXIMO_DE_TENTATIVAS:
        return Decisao(
            "parar", 1,
            f"{fatos.tentativas_feitas} tentativas vermelhas com a porta 22 "
            "respondendo. A regra de parada da armadilhas/127 é justamente "
            "esta: a quarta tentativa não é diagnóstico, é teimosia.",
            pendencia=_texto_da_pendencia(fatos, permanente=False),
        )
    return Decisao(
        "repetir", 0,
        "a porta 22 respondeu e o site está de pé: é o blip intermitente entre "
        "o runner e a VPS (armadilhas/127), não a 017. Repetindo o deploy.",
    )


def _texto_da_pendencia(fatos: Fatos, permanente: bool) -> str:
    """O que o mantenedor precisa saber — em linguagem de resultado."""
    site = (
        "o site continua no ar (a versão ANTIGA está servindo)"
        if fatos.site_http == 200
        else f"ATENÇÃO: a sonda do site respondeu {fatos.site_http} — confira o ar"
    )
    causa = (
        "a VPS não está aceitando conexão na porta 22 — é configuração, e o "
        "conserto passa por você"
        if permanente
        else "a rede entre o GitHub e a VPS falhou repetidamente"
    )
    return (
        f"O deploy do run {fatos.run} não conseguiu subir a versão nova: {causa}. "
        f"Enquanto isso, {site} — ninguém ficou fora do ar, mas o que foi "
        "mergeado ainda NÃO está em produção. "
        f"Tentativas feitas: {fatos.tentativas_feitas}."
    )


# --------------------------------------------------------------- o mundo ----


def _rodar(comando: list[str], teto_s: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            comando, capture_output=True, text=True, timeout=teto_s,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as erro:
        raise ErroDeMedicao(f"{' '.join(comando[:3])}…: {erro}") from erro
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def veredito_do_run(run: str) -> tuple[str, str]:
    """O veredito vem da fonte estruturada, nunca do exit de um pipe (045)."""
    codigo, saida = _rodar(
        ["gh", "run", "view", run, "--json", "status,conclusion"]
    )
    if codigo != 0:
        raise ErroDeMedicao(f"gh run view {run} falhou: {saida.strip()[:200]}")
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeMedicao(f"resposta do gh não é JSON: {erro}") from erro
    return str(dados.get("status") or ""), str(dados.get("conclusion") or "")


def log_da_falha(run: str) -> str:
    _codigo, saida = _rodar(["gh", "run", "view", run, "--log-failed"], teto_s=180)
    return saida  # exit != 0 é normal aqui: o run falhou


def porta_22_responde(host: str) -> bool:
    import socket

    try:
        with socket.create_connection((host, 22), timeout=10) as conexao:
            conexao.settimeout(10)
            return BANNER_SSH in conexao.recv(64).decode("utf-8", "replace")
    except OSError:
        return False


def http_do_site(url: str = SONDA_DO_SITE) -> int | None:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=15) as resposta:
            return int(resposta.status)
    except urllib.error.HTTPError as erro:
        return int(erro.code)
    except Exception:
        return None


def ultimo_run(workflow: str = "deploy-celula.yml") -> str:
    codigo, saida = _rodar(
        ["gh", "run", "list", "--workflow", workflow, "--limit", "1",
         "--json", "databaseId"]
    )
    if codigo != 0:
        raise ErroDeMedicao(f"gh run list falhou: {saida.strip()[:200]}")
    dados = json.loads(saida)
    if not dados:
        raise ErroDeMedicao(f"nenhum run de {workflow} encontrado")
    return str(dados[0]["databaseId"])


def colher(run: str, host: str, tentativas: int) -> Fatos:
    status, conclusion = veredito_do_run(run)
    fatos = Fatos(run=run, status=status, conclusion=conclusion,
                  tentativas_feitas=tentativas)
    if status == "completed" and conclusion not in ("success", "cancelled", "skipped"):
        log = log_da_falha(run)
        fatos.tem_timeout_ssh = bool(RE_TIMEOUT_SSH.search(log))
        fatos.tem_falha_de_autenticacao = bool(RE_SSH_AUTENTICACAO.search(log))
        if fatos.tem_timeout_ssh:
            try:
                fatos.porta22_viva = porta_22_responde(host)
            except Exception:
                fatos.porta22_viva = None
            fatos.site_http = http_do_site()
    return fatos


def esperar_o_run(run: str, teto_min: int) -> str:
    """Espera com TETO e com VOZ — espera muda é a armadilhas/161."""
    limite = time.time() + teto_min * 60
    while time.time() < limite:
        status, conclusion = veredito_do_run(run)
        if status == "completed":
            return conclusion
        restam = int((limite - time.time()) / 60)
        print(f"   … o run {run} ainda roda (restam ~{restam} min de teto)",
              flush=True)
        time.sleep(INTERVALO_DE_CONFERENCIA_S)
    raise ErroDeMedicao(
        f"o run {run} não terminou em {teto_min} min — parei de esperar e "
        "não vou adivinhar o resultado"
    )


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Cuida do deploy recusado pela VPS (armadilhas/127)."
    )
    alvo = parser.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--run", help="id do run de deploy")
    alvo.add_argument("--ultimo", action="store_true",
                      help="o último run de deploy-celula")
    parser.add_argument("--host", default=VPS_PADRAO)
    parser.add_argument("--teto", type=int, default=TETO_PADRAO_MIN)
    parser.add_argument("--so-diagnosticar", action="store_true",
                        help="decide e explica, mas não repete nada")
    args = parser.parse_args(argv)

    try:
        run = args.run or ultimo_run()
        tentativas = 0
        while True:
            fatos = colher(run, args.host, tentativas)
            decisao = decidir(fatos)
            print(f"\nrun {run}: status={fatos.status} conclusion={fatos.conclusion}"
                  f" · timeout-ssh={fatos.tem_timeout_ssh}"
                  f" · porta22={fatos.porta22_viva} · site={fatos.site_http}")
            print(f"{decisao.acao.upper()}: {decisao.motivo}")

            if decisao.acao != "repetir" or args.so_diagnosticar:
                if args.so_diagnosticar and decisao.acao == "repetir":
                    print("(--so-diagnosticar: não repeti nada)")
                if decisao.pendencia:
                    print("\n--- para o livro (registro de pendência) ---")
                    print(decisao.pendencia)
                print(f"\nRESULTADO  {'PASS' if decisao.codigo == 0 else 'FAIL'}"
                      if decisao.codigo != 2 else "\nRESULTADO  ERROR")
                return decisao.codigo

            if tentativas >= 1:
                print(f"   pausa de {PAUSA_ENTRE_TENTATIVAS_S}s antes da próxima "
                      "(reruns emendados batem na mesma janela ruim)", flush=True)
                time.sleep(PAUSA_ENTRE_TENTATIVAS_S)

            tentativas += 1
            print(f"   repetindo o deploy (tentativa {tentativas} de "
                  f"{MAXIMO_DE_TENTATIVAS})…", flush=True)
            codigo, saida = _rodar(["gh", "run", "rerun", run, "--failed"])
            if codigo != 0:
                raise ErroDeMedicao(f"gh run rerun falhou: {saida.strip()[:200]}")
            time.sleep(INTERVALO_DE_CONFERENCIA_S)
            conclusion = esperar_o_run(run, args.teto)
            if conclusion == "success":
                site = http_do_site()
                print(f"\n✅ o deploy do run {run} FICOU VERDE na tentativa "
                      f"{tentativas} — a versão nova subiu. Sonda do site: {site}.")
                print("RESULTADO  PASS")
                return 0
    except ErroDeMedicao as erro:
        print(f"\n🧱 PAROU POR SEGURANÇA: {erro}\n"
              "'Não consegui medir' nunca vira 'deu certo' (INV-CI01).",
              file=sys.stderr)
        print("RESULTADO  ERROR", file=sys.stderr)
        return 2
    except Exception as erro:  # pragma: no cover - rede/ambiente
        print(f"\n🧱 PAROU POR SEGURANÇA: erro inesperado "
              f"({erro.__class__.__name__}: {erro})", file=sys.stderr)
        print("RESULTADO  ERROR", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
