#!/usr/bin/env python3
"""Liga ou desliga o cartão Appmax de produção em UM site, sem mostrar credenciais.

É a chave do canário (plano mestre Appmax, seções 5.4 e 18.2). Sem --executar
ela só mostra o que mudaria. Ligar confere a Appmax de produção, a instalação
do site e a ausência de outro site ligado; se a recarga não se confirmar, os
dois env voltam como estavam. Desligar é o caminho de volta: tira só o site
pedido e, na dúvida, deixa a trava fechada.

Uso na VPS (PLATAFORMA_DIR, padrão /opt/plataforma, é onde moram docker-compose.yml e env/):
  python3 ativar-appmax-canario.py --site <platform_site_id>
  python3 ativar-appmax-canario.py --site <platform_site_id> --executar
  python3 ativar-appmax-canario.py --site <platform_site_id> --desligar --executar
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SERVICOS = (
    "pagamentos",
    "pagamentos-appmax",
    "checkout",
    "checkout-relay",
    "checkout-consumer",
)
TRAVA = "APPMAX_CARD_ENABLED_SITES"
AUTH_PRODUCAO = "https://auth.appmax.com.br/oauth2/token"
API_PRODUCAO = "https://api.appmax.com.br"
SCRIPT_DE_TESTE_NO_CHECKOUT = (
    "a página do cartão carregaria o script de teste da Appmax; defina "
    f"APPMAX_API_URL={API_PRODUCAO} em checkout.env; nada foi alterado"
)
USO = (
    "use --site <platform_site_id> para ver a prévia, acrescente --executar para "
    "gravar e --desligar para o caminho de volta"
)


class ParouPorSeguranca(Exception):
    pass


@contextmanager
def trava_publicacao(raiz: Path):
    if not (raiz / "docker-compose.yml").is_file():
        raise ParouPorSeguranca(
            "docker-compose.yml ausente; execute na VPS correta; nada foi alterado"
        )
    try:
        import fcntl
    except ImportError:
        raise ParouPorSeguranca(
            "flock do Linux indisponível; execute na VPS Linux antes de alterar a configuração"
        ) from None

    caminho = raiz / ".publicacao.lock"
    try:
        herdado = os.fstat(8)
    except OSError:
        herdado = None
    descritor = None
    anterior = None
    proprio = False
    try:
        mascara = os.umask(0o022)
        try:
            descritor = (
                os.open(caminho, os.O_RDONLY)
                if caminho.exists()
                else os.open(caminho, os.O_RDONLY | os.O_CREAT, 0o644)
            )
        finally:
            os.umask(mascara)
        atual = os.fstat(descritor)
        if not stat.S_ISREG(atual.st_mode):
            os.close(descritor)
            descritor = None
            raise ParouPorSeguranca(
                "a trava comum não é um arquivo regular; corrija o caminho "
                ".publicacao.lock antes de alterar a configuração"
            )
        mesmo_inode = (
            herdado is not None
            and (herdado.st_dev, herdado.st_ino) == (atual.st_dev, atual.st_ino)
        )
        if mesmo_inode:
            os.close(descritor)
            descritor = None
            fcntl.flock(8, fcntl.LOCK_EX)
        else:
            fcntl.flock(descritor, fcntl.LOCK_EX)
            if herdado is not None:
                anterior = os.dup(8)
            if descritor != 8:
                os.dup2(descritor, 8)
                os.close(descritor)
            descritor = None
            proprio = True
    except OSError as erro:
        if descritor is not None:
            os.close(descritor)
        if anterior is not None:
            os.dup2(anterior, 8)
            os.close(anterior)
        raise ParouPorSeguranca(
            f"não consegui obter a trava comum em {caminho}: {erro.strerror}; "
            "confira as permissões da plataforma e o mutador em andamento"
        ) from None
    try:
        yield
    finally:
        if proprio:
            fcntl.flock(8, fcntl.LOCK_UN)
            os.close(8)
            if anterior is not None:
                os.dup2(anterior, 8)
                os.close(anterior)


def ler_env(caminho: Path, *, escrever: bool) -> dict[str, str]:
    if not caminho.is_file() or (escrever and not os.access(caminho, os.W_OK)):
        raise ParouPorSeguranca(
            f"{caminho.name} ausente ou sem permissão necessária; nada foi alterado"
        )
    valores: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        entrada = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", linha)
        if entrada:
            chave, valor = entrada.groups()
            if chave in valores:
                raise ParouPorSeguranca(
                    f"{chave} repetida em {caminho.name}; corrija o env antes de continuar"
                )
            valores[chave] = valor.strip()
    return valores


def lista(valor: str) -> list[str]:
    return [site.strip() for site in valor.split(",") if site.strip()]


def mostrar(sites: list[str]) -> str:
    return ",".join(sites) or "(vazia)"


def instalacao_do_site(pagamentos: dict[str, str], site: str) -> str:
    """Confere a Appmax de produção e devolve o app_id que pode cobrar pelo site."""
    if (
        pagamentos.get("APPMAX_AUTH_URL") != AUTH_PRODUCAO
        or pagamentos.get("APPMAX_API_URL") != API_PRODUCAO
    ):
        raise ParouPorSeguranca(
            "a Appmax não aponta inteiramente para a produção; o canário exige a "
            "instalação de produção; nada foi alterado"
        )
    if not all(
        pagamentos.get(chave)
        for chave in ("APPMAX_MERCHANT_CLIENT_ID", "APPMAX_MERCHANT_CLIENT_SECRET")
    ):
        raise ParouPorSeguranca(
            "credencial MERCHANT de produção incompleta; conclua a instalação antes "
            "de ligar o cartão; nada foi alterado"
        )
    try:
        instalacoes = json.loads(pagamentos.get("APPMAX_INSTALACOES", ""))
        donos = [
            app_id
            for app_id, entrada in instalacoes.items()
            if site in entrada["sites"]
        ]
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError):
        donos = []
    if len(donos) != 1:
        raise ParouPorSeguranca(
            "o site não está vinculado a exatamente uma instalação em "
            "APPMAX_INSTALACOES; nada foi alterado"
        )
    return donos[0]


def trocar_trava(caminho: Path, sites: list[str]) -> None:
    original = caminho.read_bytes().decode("utf-8")
    novo = re.compile(rf"^{TRAVA}=[^\r\n]*", re.MULTILINE).sub(
        f"{TRAVA}={','.join(sites)}", original
    )
    estado = caminho.stat()
    descritor, temporario = tempfile.mkstemp(prefix=".appmax-canario-", dir=caminho.parent)
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(novo.encode("utf-8"))
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


def conferir_servicos(raiz: Path, ambiente: dict[str, str]) -> None:
    try:
        ativos = compose(raiz, ambiente, "ps", "--services", "--status", "running")
    except (OSError, subprocess.TimeoutExpired):
        raise ParouPorSeguranca("não consegui consultar o Compose; nada foi alterado") from None
    if ativos.returncode != 0 or not set(SERVICOS).issubset(ativos.stdout.splitlines()):
        raise ParouPorSeguranca(
            "checkout, pagamentos ou consumidores não estão todos ativos; nada foi alterado"
        )


def external_id_no_banco(
    raiz: Path, ambiente: dict[str, str], app_id: str, site: str
) -> str:
    script = (
        "from pagamentos.core.models import InstalacaoAppmax; "
        f"i = InstalacaoAppmax.objects.get(app_id={app_id!r}); "
        f"assert {site!r} in i.platform_site_ids; print(i.external_id)"
    )
    try:
        resposta = compose(
            raiz, ambiente, "exec", "-T", "pagamentos", "python", "manage.py", "shell", "-c", script
        )
        if resposta.returncode != 0:
            raise ValueError("consulta recusada")
        return str(uuid.UUID(resposta.stdout.strip()))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ParouPorSeguranca(
            "instalação Appmax do site não confirmada no banco; nada foi alterado"
        ) from None


def provar_leitura(raiz: Path, ambiente: dict[str, str], esperado: dict[str, str]) -> None:
    for servico, valor in esperado.items():
        prova = compose(
            raiz,
            ambiente,
            "exec",
            "-T",
            servico,
            "python",
            "-c",
            f"import os; assert os.environ.get({TRAVA!r}, '') == {valor!r}",
        )
        if prova.returncode != 0:
            raise ParouPorSeguranca(f"{servico} não leu a trava nova")


def executar(raiz: Path, site: str, *, ligar: bool, gravar: bool) -> None:
    if not gravar:
        return _executar(raiz, site, ligar=ligar, gravar=False)
    with trava_publicacao(raiz):
        return _executar(raiz, site, ligar=ligar, gravar=True)


def _executar(raiz: Path, site: str, *, ligar: bool, gravar: bool) -> None:
    if not (raiz / "docker-compose.yml").is_file():
        raise ParouPorSeguranca(
            "docker-compose.yml ausente; execute na VPS correta; nada foi alterado"
        )
    caminhos = {nome: raiz / f"env/{nome}.env" for nome in ("pagamentos", "checkout")}
    envs = {nome: ler_env(caminho, escrever=gravar) for nome, caminho in caminhos.items()}
    for nome, valores in envs.items():
        if TRAVA not in valores:
            raise ParouPorSeguranca(
                f"trava ausente em {nome}.env; aplique a infraestrutura dormente antes; "
                "nada foi alterado"
            )
    admin = ler_env(raiz / "env/admin.env", escrever=False)
    if not admin.get("ALUNOS_API_TOKEN") or not admin.get("TOKEN_CATALOGO"):
        raise ParouPorSeguranca(
            "tokens de operação do Compose ausentes em admin.env; nada foi alterado"
        )
    ambiente = {
        **os.environ,
        "ALUNOS_API_TOKEN": admin["ALUNOS_API_TOKEN"],
        "TOKEN_CATALOGO": admin["TOKEN_CATALOGO"],
    }
    antes = {nome: lista(valores[TRAVA]) for nome, valores in envs.items()}
    if ligar:
        app_id = instalacao_do_site(envs["pagamentos"], site)
        for nome, valores in envs.items():
            if lista(valores.get("APPMAX_PIX_ENABLED_SITES", "")):
                raise ParouPorSeguranca(
                    f"Pix Appmax ligado em {nome}.env; o canário é só cartão e o Pix "
                    "segue no Mercado Pago; nada foi alterado"
                )
            if set(antes[nome]) - {site}:
                raise ParouPorSeguranca(
                    f"{TRAVA} em {nome}.env já contém outro site; o canário liga um "
                    "site por vez; nada foi alterado"
                )
        if envs["checkout"].get("APPMAX_API_URL") != API_PRODUCAO:
            raise ParouPorSeguranca(SCRIPT_DE_TESTE_NO_CHECKOUT)
        conferir_servicos(raiz, ambiente)
        if envs["checkout"].get("APPMAX_EXTERNAL_ID", "") != external_id_no_banco(
            raiz, ambiente, app_id, site
        ):
            raise ParouPorSeguranca(
                "o identificador externo do checkout não é o da instalação do site; "
                "nada foi alterado"
            )
        depois = {nome: [site] for nome in envs}
    else:
        depois = {nome: [s for s in sites if s != site] for nome, sites in antes.items()}

    acao = "ligar" if ligar else "desligar"
    if depois == antes:
        print(f"Nada a fazer: o cartão Appmax do site {site} já está como pedido ({acao}).")
        return
    if not gravar:
        print(f"PRÉVIA: {acao} o cartão Appmax no site {site}")
        for nome in envs:
            print(f"  {nome}.env {TRAVA}: {mostrar(antes[nome])} -> {mostrar(depois[nome])}")
        print("Nada foi alterado. Para aplicar, repita o mesmo comando com --executar.")
        return

    marca = str(time.time_ns())
    copias = [
        (caminho, caminho.with_name(caminho.name + ".bak-" + marca))
        for caminho in caminhos.values()
    ]
    for caminho, copia in copias:
        shutil.copy2(caminho, copia)
    try:
        for nome, caminho in caminhos.items():
            trocar_trava(caminho, depois[nome])
        if not recarregar(raiz, ambiente):
            raise ParouPorSeguranca("recriação das células falhou")
        provar_leitura(raiz, ambiente, {nome: ",".join(depois[nome]) for nome in envs})
    except (OSError, subprocess.TimeoutExpired, ParouPorSeguranca) as erro:
        if not ligar:
            raise ParouPorSeguranca(
                f"desligamento gravado mas não confirmado ({erro}); a trava continua "
                "fechada nos env; confira docker compose ps e rode de novo com "
                "--desligar --executar"
            ) from None
        for caminho, copia in copias:
            shutil.copy2(copia, caminho)
        try:
            recarregar(raiz, ambiente)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise ParouPorSeguranca(
            f"ativação não confirmada e env anterior restaurado: {erro}; confira "
            "docker compose ps sem enviar segredos"
        ) from None
    if ligar:
        print(
            f"APPMAX_CANARIO_LIGADO: cartão Appmax de produção ligado somente no site {site}. "
            "Para voltar atrás: --desligar --executar"
        )
    else:
        print(f"APPMAX_CANARIO_DESLIGADO: cartão Appmax desligado no site {site}")


def ler_argumentos(argv: list[str]) -> tuple[str, bool, bool]:
    restantes = list(argv)
    opcoes = {}
    for opcao in ("--desligar", "--executar"):
        opcoes[opcao] = restantes.count(opcao)
        restantes = [argumento for argumento in restantes if argumento != opcao]
    if any(vezes > 1 for vezes in opcoes.values()) or len(restantes) != 2 or restantes[0] != "--site":
        raise ParouPorSeguranca(USO)
    try:
        site = str(uuid.UUID(restantes[1]))
    except ValueError:
        raise ParouPorSeguranca(
            "--site precisa ser o platform_site_id (UUID) do catálogo, nunca o endereço"
        ) from None
    return site, not opcoes["--desligar"], bool(opcoes["--executar"])


def main(argv: list[str] | None = None) -> int:
    try:
        site, ligar, gravar = ler_argumentos(sys.argv[1:] if argv is None else argv)
        executar(
            Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma")),
            site,
            ligar=ligar,
            gravar=gravar,
        )
    except ParouPorSeguranca as erro:
        print(f"PAROU POR SEGURANÇA: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
