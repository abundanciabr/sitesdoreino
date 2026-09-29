#!/usr/bin/env python3
"""Ensaio de rollback do cartão Appmax no sandbox da Meshcraft, pela esteira.

Plano mestre Appmax, seções 18.2 e 22.1: o rollback é esvaziar a trava
APPMAX_CARD_ENABLED_SITES e medir, pela porta pública, o cartão bloqueado com
explicação e o Pix inalterado. Este ensaio faz isso num dia calmo, no sandbox:

1. confere que a Appmax aponta inteira para o sandbox, que a instalação 1888
   atende só a Meshcraft e que a trava contém só a Meshcraft; fora disso para
   sem gravar nada;
2. lê https://meshcraft.top/checkout/curso-teste/ com curl e exige o cartão
   ligado e o Pix oferecido antes de mexer;
3. recria os serviços com uma sobreposição temporária do Compose que esvazia a
   trava e prova a leitura; os env/*.env nunca são gravados, porque o usuário
   deploy da esteira lê esses arquivos mas não escreve neles (run 36316492477);
4. lê a página de novo: cartão bloqueado, explicação ao comprador e o Pix igual;
5. religa SEMPRE, recriando os serviços pelos env intactos, e prova que o
   cartão voltou.

Nenhum pedido, cobrança ou estorno nasce aqui. A saída é uma linha JSON com
estados e booleanos, sem valor de env nem identificador.

Na esteira (.github/workflows/appmax-drill-rollback.yml):
  python infra/drill-appmax-rollback-sandbox.py preparar   (runner: monta o script da VPS)
  python infra/drill-appmax-rollback-sandbox.py conferir   (runner: valida e publica o resumo)
Na VPS, pelo script montado:
  python3 drill-appmax-rollback-sandbox.py executar
Estados: 0 PASS, 1 FAIL, 2 ERROR (não medido ou volta não confirmada).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "canario_appmax", Path(__file__).resolve().with_name("ativar-appmax-canario.py")
)
assert _SPEC and _SPEC.loader
canario = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(canario)

TRAVA = canario.TRAVA
SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
INSTALACAO = "1888"
AUTH_SANDBOX = "https://auth.sandboxappmax.com.br/oauth2/token"
API_SANDBOX = "https://api.sandboxappmax.com.br"
PAGINA = "https://meshcraft.top/checkout/curso-teste/"
EXPLICACAO = "O cartão ainda não pode ser concluído neste site."
ENVS = ("pagamentos", "checkout")
TENTATIVAS = 6
ESPERA_SEGUNDOS = 5
CODIGOS = {"PASS": 0, "FAIL": 1, "ERROR": 2}
MOMENTOS = ("antes", "desligado", "religado")
SONDA = {
    "http": (int,),
    "pix_oferecido": (bool,),
    "pix_na_appmax": (bool, type(None)),
    "cartao_ligado": (bool, type(None)),
    "explicacao_ao_comprador": (bool,),
}
FIXOS = {"ensaio": "appmax-rollback-sandbox", "site": "meshcraft.top", "ambiente": "sandbox"}


class Falha(Exception):
    pass


def buscar_pagina() -> tuple[str, str]:
    """A página de dados do checkout como a internet a recebe, sem criar pedido."""
    try:
        resposta = subprocess.run(
            [
                "curl",
                "--silent",
                "--max-time",
                "20",
                "--header",
                "Cache-Control: no-cache",
                "--write-out",
                "\n%{http_code}",
                f"{PAGINA}?ensaio={time.time_ns()}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return "", "0"
    corpo, _, codigo = resposta.stdout.rpartition("\n")
    return corpo, codigo


def _declaracao(html: str, nome: str) -> bool | None:
    achado = re.search(
        rf'<script id="{nome}" type="application/json">\s*(true|false)\s*</script>', html
    )
    return None if achado is None else achado.group(1) == "true"


def ler_pagina(html: str, codigo: str) -> dict:
    return {
        "http": int(codigo) if codigo.isdecimal() else 0,
        "pix_oferecido": ">Pix</button>" in html,
        "pix_na_appmax": _declaracao(html, "appmax-pix-enabled"),
        "cartao_ligado": _declaracao(html, "appmax-card-enabled"),
        "explicacao_ao_comprador": EXPLICACAO in html and ">Cartão indisponível</button>" in html,
    }


def sondar_ate(*, cartao_ligado: bool) -> dict:
    """Relê a página até o cartão aparecer como esperado, com teto de tentativas."""
    for tentativa in range(TENTATIVAS):
        leitura = ler_pagina(*buscar_pagina())
        if leitura["http"] == 200 and leitura["cartao_ligado"] is cartao_ligado:
            return leitura
        if tentativa < TENTATIVAS - 1:
            time.sleep(ESPERA_SEGUNDOS)
    return leitura


def conferir_sandbox_da_meshcraft(pagamentos: dict[str, str]) -> None:
    if pagamentos.get("APPMAX_AUTH_URL") != AUTH_SANDBOX or pagamentos.get("APPMAX_API_URL") != API_SANDBOX:
        raise canario.ParouPorSeguranca(
            "a Appmax não aponta inteiramente para o sandbox; o ensaio nunca roda "
            "na produção; nada foi alterado"
        )
    try:
        sites = json.loads(pagamentos["APPMAX_INSTALACOES"])[INSTALACAO]["sites"]
    except (KeyError, TypeError, json.JSONDecodeError):
        sites = None
    if sites != [SITE]:
        raise canario.ParouPorSeguranca(
            "a instalação sandbox 1888 não atende só a Meshcraft; nada foi alterado"
        )


def _mudou_o_pix(leitura: dict, antes: dict) -> bool:
    return not leitura["pix_oferecido"] or leitura["pix_na_appmax"] != antes["pix_na_appmax"]


def julgar_desligado(leitura: dict, antes: dict) -> str | None:
    if leitura["http"] != 200:
        return f"a página pública respondeu HTTP {leitura['http']} com o cartão desligado"
    if leitura["cartao_ligado"] is not False:
        return "o cartão continuou oferecido na página pública depois de desligado"
    if not leitura["explicacao_ao_comprador"]:
        return "a página não trouxe a explicação ao comprador com o cartão desligado"
    if _mudou_o_pix(leitura, antes):
        return "o Pix mudou na página pública com o cartão desligado"
    return None


def julgar_religado(leitura: dict, antes: dict) -> str | None:
    if leitura["http"] != 200 or leitura["cartao_ligado"] is not True:
        return "o cartão não voltou na página pública depois de religar"
    if _mudou_o_pix(leitura, antes):
        return "o Pix mudou na página pública depois de religar"
    return None


def evidencia(resultado: str, **campos) -> dict:
    return {
        **FIXOS,
        "resultado": resultado,
        "motivo": None,
        "acao": None,
        "alterou_a_vps": True,
        "env_devolvido_identico": None,
        "sondas": {},
        **campos,
    }


def ler_env(caminho: Path) -> dict[str, str]:
    try:
        return canario.ler_env(caminho, escrever=False)
    except OSError:
        raise canario.ParouPorSeguranca(
            f"{caminho.name} sem leitura para o usuário da esteira; nada foi alterado"
        ) from None


def sobrepor_trava_vazia(raiz: Path, pasta: Path) -> str:
    """COMPOSE_FILE que recria os serviços do cartão com a trava vazia, sem gravar env."""
    sobreposicao = pasta / "trava-vazia.yml"
    servicos = {servico: {"environment": {TRAVA: ""}} for servico in canario.SERVICOS}
    sobreposicao.write_text(json.dumps({"services": servicos}), encoding="utf-8")
    return os.pathsep.join((str(raiz / "docker-compose.yml"), str(sobreposicao)))


def religar(raiz: Path, ambiente: dict[str, str]) -> str | None:
    try:
        if not canario.recarregar(raiz, ambiente):
            raise Falha("recriação das células falhou")
        canario.provar_leitura(raiz, ambiente, {nome: SITE for nome in ENVS})
    except (OSError, subprocess.TimeoutExpired, canario.ParouPorSeguranca, Falha) as erro:
        return f"religar não se confirmou: {erro}"
    return None


def executar(raiz: Path) -> dict:
    with canario.trava_publicacao(raiz):
        return _executar(raiz)


def _executar(raiz: Path) -> dict:
    caminhos = {nome: raiz / f"env/{nome}.env" for nome in ENVS}
    envs = {nome: ler_env(caminho) for nome, caminho in caminhos.items()}
    conferir_sandbox_da_meshcraft(envs["pagamentos"])
    for nome, valores in envs.items():
        if valores.get(TRAVA) != SITE:
            raise canario.ParouPorSeguranca(
                f"{TRAVA} em {nome}.env não contém só a Meshcraft; o ensaio parte do "
                "cartão ligado somente nela; nada foi alterado"
            )
    admin = ler_env(raiz / "env/admin.env")
    if not admin.get("ALUNOS_API_TOKEN") or not admin.get("TOKEN_CATALOGO"):
        raise canario.ParouPorSeguranca(
            "tokens de operação do Compose ausentes em admin.env; nada foi alterado"
        )
    ambiente = {
        **os.environ,
        "ALUNOS_API_TOKEN": admin["ALUNOS_API_TOKEN"],
        "TOKEN_CATALOGO": admin["TOKEN_CATALOGO"],
    }
    canario.conferir_servicos(raiz, ambiente)
    antes = sondar_ate(cartao_ligado=True)
    if antes["http"] != 200 or antes["cartao_ligado"] is not True:
        raise canario.ParouPorSeguranca(
            "a página pública não mostra o cartão ligado da Meshcraft; nada foi alterado"
        )
    if not antes["pix_oferecido"] or antes["pix_na_appmax"] is None:
        raise canario.ParouPorSeguranca(
            "a página pública não oferece o Pix com provedor declarado; nada foi alterado"
        )

    originais = {caminho: caminho.read_bytes() for caminho in caminhos.values()}
    sondas = {"antes": antes}
    try:
        with tempfile.TemporaryDirectory(prefix="drill-appmax-") as pasta:
            desligado = {**ambiente, "COMPOSE_FILE": sobrepor_trava_vazia(raiz, Path(pasta))}
            if not canario.recarregar(raiz, desligado):
                raise Falha("recriação das células falhou")
        canario.provar_leitura(raiz, ambiente, {nome: "" for nome in ENVS})
        sondas["desligado"] = sondar_ate(cartao_ligado=False)
        motivo = julgar_desligado(sondas["desligado"], antes)
    except Exception as erro:  # qualquer falha depois de recriar ainda precisa religar
        motivo = f"desligar não se confirmou: {erro}"

    erro_ao_religar = religar(raiz, ambiente)
    identico = all(caminho.read_bytes() == bytes_ for caminho, bytes_ in originais.items())
    if erro_ao_religar:
        return evidencia(
            "ERROR",
            motivo=erro_ao_religar,
            acao=(
                "O Pix não foi tocado e o cartão sandbox da Meshcraft pode ter ficado "
                "desligado, que é o estado seguro. Os env não foram gravados; confira "
                "docker compose ps, e um deploy de checkout e pagamentos religa o cartão."
            ),
            env_devolvido_identico=identico,
            sondas=sondas,
        )
    sondas["religado"] = sondar_ate(cartao_ligado=True)
    motivo = motivo or julgar_religado(sondas["religado"], antes)
    return evidencia(
        "FAIL" if motivo else "PASS",
        motivo=motivo,
        env_devolvido_identico=identico,
        sondas=sondas,
    )


def preparar() -> None:
    destino = Path(os.environ["RUNNER_TEMP"]) / "drill-appmax-rollback-sandbox.sh"
    partes = ["#!/bin/sh\nset -eu\n", 'DIR="$(mktemp -d)"\n', "trap 'rm -rf \"$DIR\"' EXIT\n"]
    for arquivo, fim in (
        (canario.__spec__.origin, "PY_ATIVAR_APPMAX_CANARIO"),
        (__file__, "PY_DRILL_APPMAX_ROLLBACK"),
    ):
        fonte = Path(arquivo).read_text(encoding="utf-8")
        partes.append(f"cat > \"$DIR/{Path(arquivo).name}\" <<'{fim}'\n{fonte}{fim}\n")
    # O ssh-action fecha a saída multilinha com `echo EOF` sob `bash -e -o pipefail`:
    # saída diferente de zero aqui apaga a evidência. O veredito vem do JSON, no `conferir`.
    partes.append('python3 "$DIR/drill-appmax-rollback-sandbox.py" executar || true\n')
    destino.write_text("".join(partes), encoding="utf-8", newline="\n")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as saida:
        saida.write(f"script={destino}\n")


def _valida(dados: object) -> bool:
    if not isinstance(dados, dict) or set(dados) != set(evidencia("PASS")):
        return False
    textos_ok = all(
        dados[chave] is None or (isinstance(dados[chave], str) and len(dados[chave]) <= 500)
        for chave in ("motivo", "acao")
    )
    sondas = dados["sondas"]
    sondas_ok = isinstance(sondas, dict) and set(sondas) <= set(MOMENTOS) and all(
        isinstance(leitura, dict)
        and set(leitura) == set(SONDA)
        and all(type(leitura[chave]) in tipos for chave, tipos in SONDA.items())
        for leitura in sondas.values()
    )
    return (
        all(dados[chave] == valor for chave, valor in FIXOS.items())
        and dados["resultado"] in CODIGOS
        and type(dados["alterou_a_vps"]) is bool
        and type(dados["env_devolvido_identico"]) in (bool, type(None))
        and textos_ok
        and sondas_ok
    )


def _sim(valor: bool | None) -> str:
    return "não lido" if valor is None else ("sim" if valor else "não")


def conferir() -> int:
    dados = None
    for linha in reversed(os.environ.get("SAIDA", "").splitlines()):
        if linha.startswith("{"):
            try:
                dados = json.loads(linha)
            except ValueError:
                dados = None
            break
    if not _valida(dados):
        print("ERROR: a VPS não devolveu a evidência do ensaio; confira o log do passo remoto.")
        return 2
    linhas = [
        "## Ensaio de rollback do cartão Appmax no sandbox da Meshcraft",
        "",
        f"Resultado: {dados['resultado']}",
    ]
    for rotulo, chave in (("Motivo", "motivo"), ("Ação", "acao")):
        if dados[chave]:
            linhas.append(f"{rotulo}: {dados[chave]}")
    linhas += [
        f"Alterou a VPS: {_sim(dados['alterou_a_vps'])}. "
        f"Env devolvidos idênticos: {_sim(dados['env_devolvido_identico'])}.",
    ]
    if dados["sondas"]:
        linhas += [
            "",
            "| Momento | HTTP | Pix oferecido | Pix na Appmax | Cartão ligado | Explicação ao comprador |",
            "|---|---|---|---|---|---|",
        ]
    for momento in MOMENTOS:
        if momento in dados["sondas"]:
            s = dados["sondas"][momento]
            linhas.append(
                f"| {momento} | {s['http']} | {_sim(s['pix_oferecido'])} | {_sim(s['pix_na_appmax'])} "
                f"| {_sim(s['cartao_ligado'])} | {_sim(s['explicacao_ao_comprador'])} |"
            )
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumo:
        resumo.write("\n".join(linhas) + "\n")
    print(json.dumps(dados, ensure_ascii=False, sort_keys=True))
    return CODIGOS[dados["resultado"]]


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if argumentos == ["preparar"]:
        preparar()
        return 0
    if argumentos == ["conferir"]:
        return conferir()
    if argumentos == ["executar"]:
        try:
            dados = executar(Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma")))
        except canario.ParouPorSeguranca as erro:
            dados = evidencia("ERROR", motivo=str(erro), alterou_a_vps=False)
        print(json.dumps(dados, ensure_ascii=False, sort_keys=True))
        return CODIGOS[dados["resultado"]]
    print("PAROU POR SEGURANÇA: use preparar ou conferir na esteira; executar roda só na VPS")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
