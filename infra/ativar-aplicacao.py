#!/usr/bin/env python3
"""Sincroniza Compose e rotas da aplicação, com foto da topologia e volta própria.

Chamado pelo publicador quando a infra muda: `ativar-aplicacao.py --sincronizar-infra SHA`.
O banco nunca é tocado aqui.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4


RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
PUBLICACOES = RAIZ / "publicacoes"
JOURNAL = PUBLICACOES / "aplicacao.json"
ARQUIVOS_AUXILIARES = (
    "sites.json", "sincronizar_sites.py", "publicacao-local.py",
    "provisionar-usuario-ponte.sh", "instalar-provisionador-usuario-ponte.sh",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
CURL_RETRY = ("--retry", "5", "--retry-delay", "1", "--retry-all-errors",
              "--retry-max-time", "45", "--connect-timeout", "3")


def executar(*comando: str, saida: bool = False, ambiente: dict | None = None) -> str:
    resultado = subprocess.run(comando, cwd=RAIZ, env=ambiente, text=True,
                               capture_output=True, stdin=subprocess.DEVNULL)
    if resultado.returncode:
        # Saídas dos comandos podem conter detalhes do ambiente. O log registra
        # somente o comando fixo e código de retorno; nunca os valores dos env.
        raise RuntimeError(f"{comando[0]} {comando[1] if len(comando)>1 else ''} falhou ({resultado.returncode})")
    return resultado.stdout.strip() if saida else ""


def compose(*argumentos: str, arquivo: Path | None = None, override: Path | None = None,
            ambiente: dict | None = None) -> str:
    comando = ["docker", "compose", "--project-directory", str(RAIZ), "-p", "plataforma"]
    if arquivo:
        comando += ["-f", str(arquivo)]
    if override and override.is_file():
        comando += ["-f", str(override)]
    return executar(*comando, *argumentos, saida=True, ambiente=ambiente)


def salvar(caminho: Path, valor: dict) -> None:
    caminho.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=f".{caminho.name}-", dir=caminho.parent)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(valor, arquivo, ensure_ascii=False)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        Path(temporario).unlink(missing_ok=True)


def id_tentativa(sha: str) -> str:
    return f"{sha}-{uuid4().hex}"


def ambiente_da_aplicacao(imagem: str, codigo: Path) -> dict:
    ambiente = os.environ.copy()
    ambiente["APLICACAO_IMAGEM"] = imagem
    ambiente["APLICACAO_CODIGO"] = str(codigo)
    admin = RAIZ / "env" / "admin.env"
    # O Compose precisa dos nomes dos tokens para renderizar o Traefik. Valores
    # ficam somente no ambiente do processo e nunca são escritos no journal.
    chaves = ("ALUNOS_API_TOKEN", "TOKEN_CATALOGO")
    linhas = admin.read_text(encoding="utf-8").splitlines() if admin.is_file() else []
    for linha in linhas:
        chave, separador, valor = linha.partition("=")
        if separador and chave in chaves and valor:
            ambiente[chave] = valor
    return ambiente


def provar_site() -> None:
    """A página inicial responde 200."""
    codigo = executar("curl", "-sL", *CURL_RETRY, "--max-time", "20", "--max-redirs", "3",
                      "--resolve", "meshcraft.top:443:127.0.0.1", "-o", "/dev/null",
                      "-w", "%{http_code}", "https://meshcraft.top/", saida=True)
    if codigo != "200":
        raise RuntimeError(f"página inicial respondeu {codigo}")


def sincronizar_sites(fonte: Path, ambiente: dict) -> None:
    """Executa a convergência aditiva do catálogo já usada pelo deploy antigo."""
    sites = fonte / "sites.json"
    roteiro = fonte / "sincronizar_sites.py"
    if not sites.is_file() or not roteiro.is_file():
        return
    ambiente = ambiente | {"SITES_JSON": sites.read_text(encoding="utf-8")}
    comando = ["docker", "compose", "--project-directory", str(RAIZ), "-p", "plataforma",
               "-f", str(fonte / "docker-compose.yml"), "exec", "-T", "-e", "SITES_JSON",
               "aplicacao", "python", "-m", "config.executar", "catalogo", "-"]
    processo = subprocess.run(comando, cwd=RAIZ, env=ambiente,
                              input=roteiro.read_text(encoding="utf-8"), text=True,
                              capture_output=True)
    if processo.returncode:
        raise RuntimeError("sincronização dos sites no catálogo falhou")


def restaurar(snapshot: Path) -> None:
    compose_antigo = snapshot / "docker-compose.yml"
    if not compose_antigo.is_file() or not (snapshot / "traefik").is_dir():
        raise RuntimeError("snapshot da topologia anterior incompleto")
    shutil.copy2(compose_antigo, RAIZ / "docker-compose.yml")
    atual = RAIZ / "traefik"
    # Uma tentativa de recuperação pode falhar depois de mover a rota atual.
    # Cada nova tentativa guarda a candidata em caminho próprio, sem apagar a
    # cópia anterior nem impedir que a topologia aprovada volte novamente.
    antigo = RAIZ / ("traefik.candidata-" + id_tentativa(snapshot.name))
    if atual.exists():
        atual.rename(antigo)
    shutil.copytree(snapshot / "traefik", atual)
    for nome in ARQUIVOS_AUXILIARES:
        if (snapshot / nome).is_file():
            shutil.copy2(snapshot / nome, RAIZ / nome)
    if (snapshot / "imagens.json").is_file():
        shutil.copy2(snapshot / "imagens.json", PUBLICACOES / "imagens.json")
    if JOURNAL.is_file():
        versao = json.loads(JOURNAL.read_text(encoding="utf-8"))["atual_versao"]
        ambiente = ambiente_da_aplicacao(versao["imagem"], Path(versao["codigo"]))
    else:
        ambiente = ambiente_da_aplicacao("imagem-antiga", snapshot)
    override = snapshot / "imagens.json"
    antigos = compose("config", "--services", arquivo=compose_antigo,
                      override=override, ambiente=ambiente).splitlines()
    compose("up", "-d", "--wait", "--wait-timeout", "180", *antigos,
            arquivo=compose_antigo, override=override, ambiente=ambiente)
    compose("up", "-d", "--force-recreate", "traefik", arquivo=compose_antigo,
            override=override, ambiente=ambiente)
    provar_site()


def sincronizar_infra(sha: str) -> None:
    """Atualiza só Compose/rotas após o primeiro corte; nunca sobe os legados."""
    if not SHA.fullmatch(sha):
        raise RuntimeError("SHA inválido")
    if not JOURNAL.is_file():
        raise RuntimeError("aplicação ainda sem primeira aprovação")
    fonte = Path(os.environ["FONTE_INFRA"]).resolve()
    if not (fonte / "docker-compose.yml").is_file() or not (fonte / "traefik").is_dir():
        raise RuntimeError("infra de origem incompleta")
    estado = json.loads(JOURNAL.read_text(encoding="utf-8"))
    versao = estado["atual_versao"]
    ambiente = ambiente_da_aplicacao(versao["imagem"], Path(versao["codigo"]))
    compose("config", "--quiet", arquivo=fonte / "docker-compose.yml", ambiente=ambiente)
    snapshot = PUBLICACOES / "topologias" / ("infra-" + id_tentativa(sha))
    snapshot.mkdir(mode=0o700, parents=True, exist_ok=False)
    shutil.copy2(RAIZ / "docker-compose.yml", snapshot / "docker-compose.yml")
    shutil.copytree(RAIZ / "traefik", snapshot / "traefik")
    for nome in ARQUIVOS_AUXILIARES:
        if (RAIZ / nome).is_file():
            shutil.copy2(RAIZ / nome, snapshot / nome)
    if (PUBLICACOES / "imagens.json").is_file():
        shutil.copy2(PUBLICACOES / "imagens.json", snapshot / "imagens.json")
    try:
        shutil.copy2(fonte / "docker-compose.yml", RAIZ / "docker-compose.yml")
        alvo = RAIZ / "traefik"
        anterior = RAIZ / ("traefik.anterior-" + snapshot.name)
        if anterior.exists():
            raise RuntimeError("snapshot da rota anterior já existe")
        alvo.rename(anterior)
        shutil.copytree(fonte / "traefik", alvo)
        for nome in ARQUIVOS_AUXILIARES:
            if (fonte / nome).is_file():
                shutil.copy2(fonte / nome, RAIZ / nome)
        compose("up", "-d", "--wait", "--wait-timeout", "180", "aplicacao", ambiente=ambiente)
        sincronizar_sites(fonte, ambiente)
        compose("up", "-d", "--force-recreate", "traefik", ambiente=ambiente)
        provar_site()
        print(f"INFRA-APLICACAO-SINCRONIZADA: {sha}", flush=True)
    except BaseException:
        restaurar(snapshot)
        raise


def main(argumentos: list[str]) -> int:
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError("publicação superada")))
    try:
        if len(argumentos) == 2 and argumentos[0] == "--sincronizar-infra":
            sincronizar_infra(argumentos[1])
        else:
            raise RuntimeError("uso: ativar-aplicacao.py --sincronizar-infra SHA")
        return 0
    except Exception as erro:
        print(f"APLICACAO-FALHOU: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
