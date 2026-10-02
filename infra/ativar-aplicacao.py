#!/usr/bin/env python3
"""Primeiro corte para a aplicação única, com cópia e retorno da topologia anterior.

Chamado pelo publicador depois de construir a imagem.
O banco é copiado antes do primeiro boot e nunca restaurado automaticamente.
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
from datetime import datetime, timezone


RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
PUBLICACOES = RAIZ / "publicacoes"
TRANSICAO = PUBLICACOES / "aplicacao-transicao.json"
JOURNAL = PUBLICACOES / "aplicacao.json"
ARQUIVOS_AUXILIARES = (
    "sites.json", "sincronizar_sites.py", "publicacao-local.py",
    "provisionar-usuario-ponte.sh", "instalar-provisionador-usuario-ponte.sh",
)
BASES = (
    "catalogo", "identidade", "notificacoes", "admin", "quiz", "leads",
    "checkout", "pagamentos", "alunos", "mensageria", "sugestoes", "forum",
    "gamificacao", "metricas", "cursos", "pages", "encomendas",
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
    for linha in admin.read_text(encoding="utf-8").splitlines():
        chave, separador, valor = linha.partition("=")
        if separador and chave in chaves and valor:
            ambiente[chave] = valor
    if any(not ambiente.get(chave) for chave in chaves):
        raise RuntimeError("tokens da entrada privada ausentes em env/admin.env")
    return ambiente


def conferir_fonte(fonte: Path, codigo: Path, imagem: str) -> None:
    if not fonte.is_dir() or not (fonte / "docker-compose.yml").is_file():
        raise RuntimeError("FONTE_INFRA sem Compose")
    if not (fonte / "traefik" / "dynamic" / "plataforma.yml").is_file():
        raise RuntimeError("FONTE_INFRA sem rotas")
    if not codigo.is_dir() or not (codigo / "entrypoint.py").is_file():
        raise RuntimeError("bundle da aplicação ausente")
    if not imagem or any(c.isspace() for c in imagem):
        raise RuntimeError("imagem inválida")
    if subprocess.run(["docker", "image", "inspect", imagem], capture_output=True).returncode:
        raise RuntimeError("imagem testada indisponível")


def copiar_bancos(ambiente: dict) -> list[str]:
    destino = RAIZ / "backups-de-banco"
    destino.mkdir(mode=0o700, exist_ok=True)
    os.chmod(destino, 0o700)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    copias = []
    override = PUBLICACOES / "imagens.json"
    for base in BASES:
        nome = base + "_db"
        presente = compose("exec", "-T", "postgres", "psql", "-U", "postgres",
                           "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{nome}'",
                           arquivo=RAIZ / "docker-compose.yml", override=override, ambiente=ambiente)
        if presente.strip() != "1":
            raise RuntimeError(f"base esperada ausente: {nome}")
        final = destino / f"{nome}-{carimbo}.dump"
        parcial = final.with_suffix(".dump.parcial")
        with parcial.open("wb") as arquivo:
            processo = subprocess.run(
                ["docker", "compose", "--project-directory", str(RAIZ), "-p", "plataforma",
                 "-f", str(RAIZ / "docker-compose.yml"),
                 *([] if not override.is_file() else ["-f", str(override)]),
                 "exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-Fc", "-d", nome],
                cwd=RAIZ, env=ambiente, stdout=arquivo, stderr=subprocess.DEVNULL)
        if processo.returncode or parcial.stat().st_size == 0:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(f"backup falhou: {nome}")
        with parcial.open("rb") as arquivo:
            prova = subprocess.run(
                ["docker", "compose", "--project-directory", str(RAIZ), "-p", "plataforma",
                 "-f", str(RAIZ / "docker-compose.yml"),
                 *([] if not override.is_file() else ["-f", str(override)]),
                 "exec", "-T", "postgres", "pg_restore", "-l"],
                cwd=RAIZ, env=ambiente, stdin=arquivo, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        if prova.returncode:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(f"backup não abre: {nome}")
        os.chmod(parcial, 0o600)
        os.replace(parcial, final)
        copias.append(str(final))
    return copias


def provar_site() -> None:
    sites = json.loads((RAIZ / "sites.json").read_text(encoding="utf-8"))["sites"]
    for site in sites:
        host = site["host"]
        tls = [] if host == "meshcraft.top" else ["-k"]
        codigo = executar("curl", "-sL", *tls, *CURL_RETRY, "--max-time", "20", "--max-redirs", "3",
                          "--resolve", f"{host}:443:127.0.0.1", "-o", "/dev/null",
                          "-w", "%{http_code}", f"https://{host}/", saida=True)
        if codigo != "200":
            raise RuntimeError(f"site {host} respondeu {codigo}")
    for caminho, esperados in (
        ("/forum/", {"200", "302", "303"}),
        ("/quiz/crivo/", {"200", "302", "303"}),
        ("/portfolio/", {"200", "302", "303"}),
        ("/cursos/", {"200", "302", "303"}),
        ("/admin/", {"302"}),
    ):
        codigo = executar("curl", "-s", *CURL_RETRY, "--max-time", "20", "--resolve",
                          "meshcraft.top:443:127.0.0.1", "-o", "/dev/null",
                          "-w", "%{http_code}", f"https://meshcraft.top{caminho}", saida=True)
        if codigo not in esperados:
            raise RuntimeError(f"rota {caminho} respondeu {codigo}")
    for caminho in ("/static/funil/api.js", "/checkout/static/checkout/api.js"):
        resposta = executar("curl", "-s", *CURL_RETRY, "--max-time", "20", "--resolve",
                            "meshcraft.top:443:127.0.0.1", "-o", "/dev/null",
                            "-w", "%{http_code} %{content_type}",
                            f"https://meshcraft.top{caminho}", saida=True)
        codigo, _, tipo = resposta.partition(" ")
        if codigo != "200" or "javascript" not in tipo.lower():
            raise RuntimeError(f"estático {caminho} respondeu {codigo} ({tipo})")
    for caminho in (
        "/alunos/api/alunos/pre-matriculas?status=aguardando",
        "/alunos/api/alunos/pre-matriculas?status=recusada",
        "/alunos/api/alunos/matriculas",
        "/catalogo/api/catalogo/produtos",
    ):
        codigo = executar("curl", "-s", *CURL_RETRY, "--max-time", "15", "-o", "/dev/null",
                          "-w", "%{http_code}", f"http://127.0.0.1:8443{caminho}", saida=True)
        if codigo != "200":
            raise RuntimeError(f"entrada privada {caminho} respondeu {codigo}")


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


def restaurar(snapshot: Path, parar_aplicacao: bool = True) -> None:
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
    env_antigo = snapshot / ".env"
    if env_antigo.is_file():
        shutil.copy2(env_antigo, RAIZ / ".env")
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
    if parar_aplicacao:
        subprocess.run(["docker", "stop", "plataforma-aplicacao-1"], capture_output=True)


def ativar(sha: str, imagem: str, codigo_arg: str) -> None:
    if not SHA.fullmatch(sha):
        raise RuntimeError("SHA inválido")
    if JOURNAL.exists():
        raise RuntimeError("primeira transição já registrada")
    if TRANSICAO.exists():
        fase = json.loads(TRANSICAO.read_text(encoding="utf-8")).get("fase")
        if fase not in {"revertida", "recuperada"}:
            raise RuntimeError("transição anterior pendente")
    fonte = Path(os.environ["FONTE_INFRA"]).resolve()
    codigo = Path(codigo_arg).resolve()
    conferir_fonte(fonte, codigo, imagem)
    ambiente = ambiente_da_aplicacao(imagem, codigo)
    compose("config", "--quiet", arquivo=fonte / "docker-compose.yml", ambiente=ambiente)
    # O publicador já provou a imagem com dados isolados. Antes do primeiro boot
    # contra produção, preservamos cada banco e a configuração anterior.
    copias = copiar_bancos(ambiente)
    snapshot = PUBLICACOES / "topologias" / id_tentativa(sha)
    snapshot.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(snapshot, 0o700)
    shutil.copy2(RAIZ / "docker-compose.yml", snapshot / "docker-compose.yml")
    shutil.copytree(RAIZ / "traefik", snapshot / "traefik")
    for nome in ARQUIVOS_AUXILIARES:
        if (RAIZ / nome).is_file():
            shutil.copy2(RAIZ / nome, snapshot / nome)
    if (PUBLICACOES / "imagens.json").is_file():
        shutil.copy2(PUBLICACOES / "imagens.json", snapshot / "imagens.json")
    if (RAIZ / ".env").is_file():
        shutil.copy2(RAIZ / ".env", snapshot / ".env")
        os.chmod(snapshot / ".env", 0o600)
    estado = {"sha": sha, "snapshot": str(snapshot), "backups": copias,
              "fase": "candidato"}
    salvar(TRANSICAO, estado)
    try:
        # As filas Redis preservam o trabalho enquanto os auxiliares antigos
        # param. Assim o novo processo nunca compete com outro consumidor.
        anteriores = compose("config", "--services", arquivo=snapshot / "docker-compose.yml",
                             override=snapshot / "imagens.json", ambiente=ambiente).splitlines()
        auxiliares = [servico for servico in anteriores if "-" in servico]
        if auxiliares:
            compose("stop", *auxiliares, arquivo=snapshot / "docker-compose.yml",
                    override=snapshot / "imagens.json", ambiente=ambiente)
        # Mesmo projeto e redes, porém só a nova aplicação. Traefik ainda
        # aponta para os serviços antigos enquanto as migrações terminam.
        compose("up", "-d", "--wait", "--wait-timeout", "240", "aplicacao",
                arquivo=fonte / "docker-compose.yml", ambiente=ambiente)
        sincronizar_sites(fonte, ambiente)
        shutil.copy2(fonte / "docker-compose.yml", RAIZ / "docker-compose.yml")
        rota_atual = RAIZ / "traefik"
        rota_anterior = RAIZ / ("traefik.anterior-" + snapshot.name)
        if rota_anterior.exists():
            raise RuntimeError("snapshot da rota anterior já existe")
        rota_atual.rename(rota_anterior)
        shutil.copytree(fonte / "traefik", rota_atual)
        for nome in ARQUIVOS_AUXILIARES:
            if (fonte / nome).is_file():
                shutil.copy2(fonte / nome, RAIZ / nome)
        # Variáveis de pin sem segredos. A .env antiga foi preservada acima.
        with (RAIZ / ".env").open("a", encoding="utf-8") as arquivo:
            arquivo.write(f"\nAPLICACAO_IMAGEM={imagem}\nAPLICACAO_CODIGO={codigo}\n")
        estado["fase"] = "rotas-trocadas"
        salvar(TRANSICAO, estado)
        compose("up", "-d", "--force-recreate", "traefik", ambiente=ambiente)
        provar_site()
        # Os antigos ficam parados, ainda existentes para recuperação. O novo
        # Compose põe esses serviços sob profile legado para futuros 'up'.
        anteriores = [s for s in anteriores if s not in {"traefik", "postgres", "redis"}]
        compose("stop", *anteriores, arquivo=snapshot / "docker-compose.yml",
                override=snapshot / "imagens.json", ambiente=ambiente)
        provar_site()
        versao = {"imagem": imagem, "codigo": str(codigo)}
        compatibilidade = {"dados": os.environ.get("COMPATIBILIDADE_DADOS", "existente"),
                            "configuracao": os.environ.get("COMPATIBILIDADE_CONFIGURACAO", "existente")}
        salvar(JOURNAL, {"celula": "aplicacao", "atual": sha, "candidata": None,
                         "aprovada": {"sha": sha, "verificada_em": datetime.now(timezone.utc).isoformat(),
                                      **compatibilidade, **versao},
                         "anterior_aprovada": None, "atual_versao": versao,
                         "compatibilidade": compatibilidade, "servicos": ["aplicacao"],
                         "endereco": os.environ.get("ENDERECO_PROVA", "https://meshcraft.top/")})
        estado["fase"] = "aprovada"
        salvar(TRANSICAO, estado)
        print(f"APLICACAO-ATIVADA: {sha}", flush=True)
    except BaseException:
        try:
            restaurar(snapshot)
            if JOURNAL.is_file():
                os.replace(JOURNAL, snapshot / "aplicacao-journal-falhou.json")
            estado["fase"] = "revertida"
            salvar(TRANSICAO, estado)
        except BaseException as erro:
            estado["fase"] = "recuperacao-falhou"
            salvar(TRANSICAO, estado)
            print(f"RECUPERACAO-TERMINAL: {erro}", file=sys.stderr)
        raise


def recuperar() -> None:
    estado = json.loads(TRANSICAO.read_text(encoding="utf-8"))
    if estado["fase"] != "aprovada":
        raise RuntimeError("transição sem primeira aprovação")
    esperado = os.environ.get("ATUAL_ESPERADA")
    if esperado and esperado != estado["sha"]:
        raise RuntimeError("versão mudou desde o incidente")
    restaurar(Path(estado["snapshot"]))
    if JOURNAL.exists():
        os.replace(JOURNAL, Path(estado["snapshot"]) / "aplicacao-journal-recuperado.json")
    estado["fase"] = "recuperada"
    salvar(TRANSICAO, estado)
    print("APLICACAO-RECUPERADA: topologia anterior no ar; bancos preservados", flush=True)


def concluir_recuperacao() -> None:
    """Repete a volta do código após falha transitória, sem restaurar bancos."""
    estado = json.loads(TRANSICAO.read_text(encoding="utf-8"))
    if estado.get("fase") != "recuperacao-falhou":
        raise RuntimeError("não há recuperação pendente para concluir")
    esperado = os.environ.get("ATUAL_ESPERADA")
    if esperado and esperado != estado["sha"]:
        raise RuntimeError("versão mudou desde o incidente")
    snapshot = Path(estado["snapshot"])
    restaurar(snapshot)
    if JOURNAL.exists():
        os.replace(JOURNAL, snapshot / "aplicacao-journal-falhou.json")
    estado["fase"] = "revertida"
    salvar(TRANSICAO, estado)
    print("APLICACAO-RECUPERADA: topologia anterior no ar; bancos preservados", flush=True)


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
    if (RAIZ / ".env").exists():
        shutil.copy2(RAIZ / ".env", snapshot / ".env")
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
        restaurar(snapshot, parar_aplicacao=False)
        raise


def main(argumentos: list[str]) -> int:
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError("publicação superada")))
    try:
        if argumentos == ["--recuperar"]:
            recuperar()
        elif argumentos == ["--concluir-recuperacao"]:
            concluir_recuperacao()
        elif len(argumentos) == 2 and argumentos[0] == "--sincronizar-infra":
            sincronizar_infra(argumentos[1])
        elif len(argumentos) == 3:
            ativar(*argumentos)
        else:
            raise RuntimeError("uso: ativar-aplicacao.py SHA IMAGEM CODIGO | --recuperar | --concluir-recuperacao")
        return 0
    except Exception as erro:
        print(f"APLICACAO-FALHOU: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
