#!/usr/bin/env python3
"""Liga ou desliga o sandbox Appmax da Meshcraft sem mostrar credenciais."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SERVICOS = (
    "pagamentos",
    "pagamentos-appmax",
    "checkout",
    "checkout-relay",
    "checkout-consumer",
)
CHAVES = ("APPMAX_PIX_ENABLED_SITES", "APPMAX_CARD_ENABLED_SITES")
SITE_MESHCRAFT = "cc06b8c3-043b-4c06-92c5-5ea624e00586"


class ParouPorSeguranca(Exception):
    pass


def ler_env(caminho: Path, *, escrever: bool = True) -> dict[str, str]:
    if not caminho.is_file() or (escrever and not os.access(caminho, os.W_OK)):
        raise ParouPorSeguranca(
            f"{caminho.name} ausente ou sem permissão necessária; nada foi alterado"
        )
    dados: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        entrada = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", linha)
        if entrada:
            chave, valor = entrada.groups()
            if chave in dados:
                raise ParouPorSeguranca(
                    f"{chave} repetida em {caminho.name}; corrija o env antes de continuar"
                )
            dados[chave] = valor.strip()
    return dados


def conferir_site(pagamentos: dict[str, str]) -> str:
    if (
        pagamentos.get("APPMAX_AUTH_URL")
        != "https://auth.sandboxappmax.com.br/oauth2/token"
        or pagamentos.get("APPMAX_API_URL") != "https://api.sandboxappmax.com.br"
    ):
        raise ParouPorSeguranca(
            "a Appmax não aponta inteiramente para o sandbox; nenhuma cobrança foi ligada"
        )
    if not all(
        pagamentos.get(chave)
        for chave in (
            "APPMAX_MERCHANT_CLIENT_ID",
            "APPMAX_MERCHANT_CLIENT_SECRET",
        )
    ):
        raise ParouPorSeguranca(
            "instalação MERCHANT sandbox incompleta; conclua a instalação antes de ligar cobrança"
        )
    try:
        lojas = json.loads(pagamentos["APPMAX_INSTALACOES"])
        entrada = lojas["1888"]
        if entrada["alias"] != "Meshcraft":
            raise ValueError("loja inesperada")
        sites = entrada["sites"]
        if not isinstance(sites, list) or len(sites) != 1:
            raise ValueError("quantidade de sites")
        site_id = str(uuid.UUID(sites[0]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ParouPorSeguranca(
            "instalação Appmax 1888 sem um único site Meshcraft válido; nada foi alterado"
        ) from None
    if site_id != SITE_MESHCRAFT:
        raise ParouPorSeguranca(
            "a instalação 1888 não aponta para o site Meshcraft esperado; nada foi alterado"
        )
    return site_id


def conferir_travas(dados: dict[str, str], site_id: str, nome: str) -> None:
    for chave in CHAVES:
        valor = dados.get(chave, "")
        if valor and valor != site_id:
            raise ParouPorSeguranca(
                f"{chave} em {nome} já contém outro site; nenhuma configuração foi alterada"
            )


def trocar_travas(
    caminho: Path, site_id: str, ligar: bool, external_id: str | None = None
) -> None:
    original = caminho.read_text(encoding="utf-8")
    novo = original
    alteracoes = {chave: site_id if ligar else "" for chave in CHAVES}
    if external_id is not None:
        alteracoes["APPMAX_EXTERNAL_ID"] = external_id if ligar else ""
    for chave, valor in alteracoes.items():
        linha = f"{chave}={valor}"
        padrao = re.compile(rf"^{chave}=.*$", re.MULTILINE)
        if padrao.search(novo):
            novo = padrao.sub(linha, novo)
        else:
            novo += ("" if novo.endswith("\n") else "\n") + linha + "\n"
    estado = caminho.stat()
    descritor, temporario = tempfile.mkstemp(
        prefix=".appmax-sandbox-", dir=caminho.parent
    )
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(novo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.chmod(temporario, estado.st_mode)
        if hasattr(os, "chown"):
            os.chown(temporario, estado.st_uid, estado.st_gid)
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def compose(
    raiz: Path, ambiente: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=raiz,
        env=ambiente,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )


def recarregar(raiz: Path, ambiente: dict[str, str]) -> bool:
    return (
        compose(
            raiz,
            ambiente,
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "180",
            *SERVICOS,
        ).returncode
        == 0
    )


def consultar_instalacao(raiz: Path, ambiente: dict[str, str], site_id: str) -> str:
    script = (
        "from pagamentos.core.models import InstalacaoAppmax; "
        "i = InstalacaoAppmax.objects.get(app_id='1888'); "
        "assert i.alias == 'Meshcraft' and i.platform_site_ids == "
        + repr([site_id])
        + "; print(i.external_id)"
    )
    try:
        resposta = compose(
            raiz,
            ambiente,
            "exec",
            "-T",
            "pagamentos",
            "python",
            "manage.py",
            "shell",
            "-c",
            script,
        )
        if resposta.returncode != 0:
            raise ValueError("consulta recusada")
        return str(uuid.UUID(resposta.stdout.strip()))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ParouPorSeguranca(
            "instalação Appmax 1888 não confirmada no banco; nenhuma configuração foi alterada"
        ) from None


def executar(raiz: Path, ligar: bool) -> None:
    if not (raiz / "docker-compose.yml").is_file():
        raise ParouPorSeguranca(
            "docker-compose.yml ausente; execute na VPS correta; nada foi alterado"
        )
    pagamentos_path = raiz / "env/pagamentos.env"
    checkout_path = raiz / "env/checkout.env"
    pagamentos = ler_env(pagamentos_path)
    checkout = ler_env(checkout_path)
    admin_path = raiz / "env/admin.env"
    if not admin_path.is_file():
        raise ParouPorSeguranca("admin.env ausente; nada foi alterado")
    admin = ler_env(admin_path, escrever=False)
    site_id = conferir_site(pagamentos)
    conferir_travas(pagamentos, site_id, pagamentos_path.name)
    conferir_travas(checkout, site_id, checkout_path.name)
    if not admin.get("ALUNOS_API_TOKEN") or not admin.get("TOKEN_CATALOGO"):
        raise ParouPorSeguranca(
            "tokens de operação do Compose ausentes em admin.env; nada foi alterado"
        )
    ambiente = {
        **os.environ,
        "ALUNOS_API_TOKEN": admin["ALUNOS_API_TOKEN"],
        "TOKEN_CATALOGO": admin["TOKEN_CATALOGO"],
    }
    try:
        ativos = compose(raiz, ambiente, "ps", "--services", "--status", "running")
    except (OSError, subprocess.TimeoutExpired):
        raise ParouPorSeguranca(
            "não consegui consultar o Compose; nada foi alterado"
        ) from None
    if ativos.returncode != 0 or not set(SERVICOS).issubset(
        set(ativos.stdout.splitlines())
    ):
        raise ParouPorSeguranca(
            "checkout, pagamentos ou consumidores não estão todos ativos; nada foi alterado"
        )
    external_id = consultar_instalacao(raiz, ambiente, site_id)
    if any(
        valor not in ("", external_id)
        for valor in (
            pagamentos.get("APPMAX_EXTERNAL_ID", ""),
            checkout.get("APPMAX_EXTERNAL_ID", ""),
        )
    ):
        raise ParouPorSeguranca(
            "env contém outra instalação Appmax; nenhuma configuração foi alterada"
        )
    marca = str(time.time_ns())
    copias = [
        (caminho, caminho.with_name(caminho.name + ".bak-" + marca))
        for caminho in (pagamentos_path, checkout_path)
    ]
    try:
        for caminho, copia in copias:
            shutil.copy2(caminho, copia)
        trocar_travas(pagamentos_path, site_id, ligar)
        trocar_travas(checkout_path, site_id, ligar, external_id)
        if not recarregar(raiz, ambiente):
            raise ParouPorSeguranca("recriação das células falhou")
        alvo = site_id if ligar else ""
        for servico in ("pagamentos", "checkout"):
            prova = compose(
                raiz,
                ambiente,
                "exec",
                "-T",
                servico,
                "python",
                "-c",
                "import os; assert all(os.environ.get(k, '') == "
                + repr(alvo)
                + " for k in "
                + repr(CHAVES)
                + ")",
            )
            if prova.returncode != 0:
                raise ParouPorSeguranca(
                    f"{servico} não leu as duas travas; restaurando a configuração anterior"
                )
        prova_id = compose(
            raiz,
            ambiente,
            "exec",
            "-T",
            "checkout",
            "python",
            "-c",
            "import os; assert os.environ.get('APPMAX_EXTERNAL_ID') == "
            + repr(external_id if ligar else ""),
        )
        if prova_id.returncode != 0:
            raise ParouPorSeguranca(
                "checkout não leu a instalação Appmax; restaurando a configuração anterior"
            )
    except (OSError, subprocess.TimeoutExpired, ParouPorSeguranca) as erro:
        for caminho, copia in copias:
            if copia.exists():
                shutil.copy2(copia, caminho)
        try:
            recarregar(raiz, ambiente)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise ParouPorSeguranca(
            f"ativação não confirmada e env anterior restaurado: {erro}; confira docker compose ps sem enviar segredos"
        ) from None
    print(
        "APPMAX_SANDBOX_ATIVO: Pix e cartão de meshcraft.top"
        if ligar
        else "APPMAX_SANDBOX_DESLIGADO: Pix e cartão Appmax de meshcraft.top"
    )


def main() -> int:
    if sys.argv[1:] not in ([], ["--desativar"]):
        print(
            "PAROU POR SEGURANÇA: use sem argumentos para ligar ou --desativar para desligar"
        )
        return 1
    try:
        executar(
            Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma")),
            ligar=not sys.argv[1:],
        )
    except ParouPorSeguranca as erro:
        print(f"PAROU POR SEGURANÇA: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
