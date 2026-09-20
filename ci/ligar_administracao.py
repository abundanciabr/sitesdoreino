"""Prepara e abre a administração do PC; só imprime links depois da prova HTTP."""

from __future__ import annotations

import hashlib
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = "http://127.0.0.1:8000"
PAGINAS = {
    "Plano mestre": "plano-mestre/",
    "Documentos": "documentos/",
    "Biblioteca": "livro/",
    "Reunião": "reuniao/",
    "Painel": "painel/",
    "Caixa": "caixa/",
    "Escola": "escola/",
}


class FalhaLocal(Exception):
    pass


def ler_conexao(dados):
    arquivo = dados / "credencial-producao.txt"
    try:
        linhas = arquivo.read_text(encoding="utf-8-sig").splitlines()
        valores = [
            linha[13:].strip() for linha in linhas if linha.startswith("DATABASE_URL=")
        ]
        if len(valores) != 1:
            raise ValueError
        conexao = urllib.parse.urlsplit(valores[0])
        if (
            conexao.scheme not in {"postgres", "postgresql"}
            or conexao.hostname != "postgres"
            or not conexao.port
            or not conexao.username
            or not conexao.password
            or len(conexao.path) < 2
            or conexao.query
            or conexao.fragment
        ):
            raise ValueError
        return conexao
    except (OSError, ValueError):
        raise FalhaLocal(
            f"A credencial de produção está ausente ou incompleta. Confira a única linha DATABASE_URL= em {arquivo}; não cole a senha no chat."
        ) from None


def comando_ssh():
    ssh = Path.home() / ".ssh"
    return [
        "ssh",
        "-F",
        "none",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        f"UserKnownHostsFile={ssh / 'known_hosts'}",
        "-i",
        str(ssh / "id_ed25519"),
        "-p",
        "22",
    ]


def descobrir_postgres():
    remoto = (
        "cd /opt/plataforma && container=$(docker compose ps -q postgres) "
        '&& test -n "$container" && docker inspect --format '
        "'{{range .NetworkSettings.Networks}}{{.IPAddress}}{{println}}{{end}}' \"$container\""
    )
    try:
        resultado = subprocess.run(
            comando_ssh() + ["deploy@217.196.62.220", remoto],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if resultado.returncode:
            raise ValueError
        enderecos = resultado.stdout.split()
        if len(enderecos) != 1:
            raise ValueError
        endereco = ipaddress.IPv4Address(enderecos[0])
        if not endereco.is_private or endereco.is_loopback or endereco.is_unspecified:
            raise ValueError
        return str(endereco)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise FalhaLocal(
            "Não foi possível descobrir o Postgres por SSH. Confira a chave autorizada, a identidade conhecida da VPS e se o container está ligado."
        ) from None


def comando_tunel(destino, porta_postgres, porta_local):
    return comando_ssh() + [
        "-N",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        "-L",
        f"127.0.0.1:{porta_local}:{destino}:{porta_postgres}",
        "deploy@217.196.62.220",
    ]


def url_do_tunel(conexao, porta):
    autoridade = conexao.netloc.rsplit("@", 1)[0]
    return conexao._replace(netloc=f"{autoridade}@127.0.0.1:{porta}").geturl()


def encerrar(processo):
    if processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=5)


def abrir_tunel(dados):
    import psycopg

    conexao = ler_conexao(dados)
    destino = descobrir_postgres()
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        porta = reserva.getsockname()[1]
    url = url_do_tunel(conexao, porta)
    processo = subprocess.Popen(
        comando_tunel(destino, conexao.port, porta),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        limite = time.monotonic() + 12
        while time.monotonic() < limite and processo.poll() is None:
            try:
                with psycopg.connect(
                    url,
                    connect_timeout=3,
                    options="-c default_transaction_read_only=on",
                ) as banco:
                    identidade = banco.execute(
                        "SELECT current_database(), current_user, host(inet_server_addr())"
                    ).fetchone()
                    esperado = (
                        urllib.parse.unquote(conexao.path[1:]),
                        urllib.parse.unquote(conexao.username),
                        destino,
                    )
                    if identidade != esperado:
                        raise FalhaLocal(
                            "O túnel chegou a outro banco. Confira a credencial de produção antes de abrir novamente."
                        )
                    return processo, url
            except psycopg.Error:
                time.sleep(0.2)
        raise FalhaLocal(
            "O túnel não conectou ao Postgres de produção. Confira a credencial e o acesso SSH; nenhuma migração foi executada."
        )
    except BaseException:
        encerrar(processo)
        raise


def vigiar_tunel(tunel, servidor, terminou):
    while not terminou.wait(0.5):
        if tunel.poll() is not None:
            servidor.should_exit = True
            return


def servir(tunel, url):
    import django
    import uvicorn

    os.environ["DATABASE_URL"] = url
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DEBUG"] = "0"
    sys.path.insert(0, str(RAIZ / "services/admin"))
    django.setup()
    from django.conf import settings
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor

    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
    settings.CSRF_COOKIE_SECURE = False
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise FalhaLocal(
                "O banco de produção precisa de migrações. Encaminhe a atualização pelo pipeline antes de abrir; o lançador não altera o esquema."
            )
    connection.close()
    print(
        "Banco PostgreSQL de produção conferido por consulta somente leitura; esquema compatível.",
        flush=True,
    )
    servidor = uvicorn.Server(
        uvicorn.Config(
            "config.asgi:application",
            host="127.0.0.1",
            port=8000,
            access_log=False,
            log_level="warning",
            timeout_graceful_shutdown=3,
        )
    )
    terminou = threading.Event()

    vigia = threading.Thread(
        target=vigiar_tunel, args=(tunel, servidor, terminou), daemon=True
    )
    vigia.start()
    try:
        servidor.run()
    finally:
        terminou.set()
        vigia.join(timeout=2)


def supervisionar(dados):
    tunel, url = abrir_tunel(dados)
    try:
        servir(tunel, url)
    finally:
        encerrar(tunel)


class SomenteLocal(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).netloc != "127.0.0.1:8000":
            raise FalhaLocal(
                "O acesso tentou sair do PC. Confira a configuração de acesso local."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verificar_paginas(token):
    cliente = urllib.request.build_opener(
        SomenteLocal(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    enderecos = []
    for titulo, rota in PAGINAS.items():
        entrada = f"{ORIGEM}/acesso-local/{token}/?next=/{rota}"
        with cliente.open(entrada, timeout=5) as resposta:
            corpo = resposta.read().decode("utf-8")
            if resposta.status != 200 or resposta.url != f"{ORIGEM}/{rota}":
                raise FalhaLocal(
                    f"{titulo} não abriu a página esperada. Consulte o log do servidor."
                )
            if titulo == "Plano mestre" and "00-SINTESE" not in corpo:
                raise FalhaLocal(
                    "O plano mestre não contém a síntese. Confira a pasta sitesdoreino-docs/administracao-local."
                )
            enderecos.append((titulo, entrada))
    return enderecos


def porta_ocupada():
    with socket.socket() as porta:
        return porta.connect_ex(("127.0.0.1", 8000)) == 0


def executar(comando, log, ambiente=None):
    with log.open("ab") as saida:
        try:
            resultado = subprocess.run(
                comando,
                cwd=RAIZ / "services/admin",
                env=ambiente,
                stdin=subprocess.DEVNULL,
                stdout=saida,
                stderr=saida,
                timeout=240,
            )
        except subprocess.TimeoutExpired as erro:
            raise FalhaLocal(
                f"A preparação ultrapassou 4 minutos. Veja {log} e execute novamente após corrigir o erro."
            ) from erro
    if resultado.returncode:
        raise FalhaLocal(
            f"A preparação falhou. Veja {log}, corrija o erro indicado e execute novamente."
        )


def iniciar():
    planos = RAIZ.parent / "sitesdoreino-docs/administracao-local"
    if not (planos / "00-SINTESE-desenho-final.md").is_file():
        raise FalhaLocal(
            f"Os planos não foram encontrados em {planos}. Restaure essa pasta de documentos e execute novamente."
        )
    dados = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
        / "SitesDoReino/administracao-local"
    )
    dados.mkdir(parents=True, exist_ok=True)
    estado = dados / "servidor.json"
    log = dados / "servidor.log"
    anterior = {}
    if estado.exists():
        try:
            anterior = json.loads(estado.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    if porta_ocupada():
        if (
            anterior.get("token")
            and anterior.get("raiz") == str(RAIZ)
            and anterior.get("banco") == "postgresql-via-ssh"
        ):
            try:
                executar(["node", str(RAIZ / "painel/gerar_manifesto.js")], log)
                return (
                    verificar_paginas(anterior["token"]),
                    "A administração já estava ligada.",
                )
            except (OSError, urllib.error.URLError, FalhaLocal) as erro:
                raise FalhaLocal(
                    "A porta 8000 está ocupada, mas o servidor desta bancada "
                    "não respondeu ao convite local. Feche o servidor na janela "
                    "em que foi iniciado e execute este comando novamente."
                ) from erro
        if anterior.get("raiz"):
            raise FalhaLocal(
                "A porta 8000 está ocupada por outra bancada. Feche o servidor "
                "na janela em que foi iniciado e execute este comando novamente. "
                "Nenhum processo foi encerrado."
            )
        raise FalhaLocal(
            "A porta 8000 está ocupada por outro processo. Feche o servidor anterior na janela em que foi iniciado e execute este comando novamente. Nenhum processo foi encerrado."
        )

    ler_conexao(dados)
    ambiente_dir = dados / "ambiente"
    python = ambiente_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requisitos = RAIZ / "services/admin/requirements.txt"
    assinatura = hashlib.sha256(requisitos.read_bytes()).hexdigest()
    marcador = dados / "dependencias.sha256"
    if not python.exists():
        print("Primeiro uso: preparando o Python da administração...", flush=True)
        executar([sys.executable, "-m", "venv", str(ambiente_dir)], log)
    if not marcador.exists() or marcador.read_text() != assinatura:
        print(
            "Instalando as dependências da administração. Aguarde; limite de 4 minutos.",
            flush=True,
        )
        executar(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(requisitos),
            ],
            log,
        )
        marcador.write_text(assinatura)

    executar(["node", str(RAIZ / "painel/gerar_manifesto.js")], log)
    token = secrets.token_urlsafe(32)
    ambiente = os.environ.copy()
    ambiente.update(
        {
            "PYTHONUTF8": "1",
            "SCRIPT_NAME": "",
            "DEBUG": "0",
            "DJANGO_SECRET_KEY": anterior.get("chave") or secrets.token_urlsafe(48),
            "ADMIN_PLANOS_DIR": str(planos),
            "ADMIN_LOCAL_EMAIL": "mantenedor@localhost",
            "ADMIN_EMAILS": "mantenedor@localhost",
            "ADMIN_LINK_TOKEN": token,
            "URL_DE_ENTRADA": f"/acesso-local/{token}/",
        }
    )
    ambiente.pop("DATABASE_URL", None)
    print("Abrindo o túnel de produção e verificando as páginas...", flush=True)
    with log.open("ab") as saida:
        processo = subprocess.Popen(
            [str(python), str(Path(__file__).resolve()), "--servir"],
            cwd=RAIZ / "services/admin",
            env=ambiente,
            stdin=subprocess.DEVNULL,
            stdout=saida,
            stderr=saida,
            creationflags=(
                (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                if os.name == "nt"
                else 0
            ),
            start_new_session=os.name != "nt",
        )
    limite = time.monotonic() + 45
    erro_final = "servidor sem resposta"
    while time.monotonic() < limite:
        if processo.poll() is not None:
            raise FalhaLocal(
                f"O servidor encerrou durante a abertura. Veja {log}, corrija o erro e execute novamente."
            )
        try:
            enderecos = verificar_paginas(token)
            estado.write_text(
                json.dumps(
                    {
                        "raiz": str(RAIZ),
                        "pid": processo.pid,
                        "token": token,
                        "chave": ambiente["DJANGO_SECRET_KEY"],
                        "banco": "postgresql-via-ssh",
                    }
                ),
                encoding="utf-8",
            )
            return enderecos, "Administração local pronta. Pode fechar este terminal."
        except (OSError, urllib.error.URLError, FalhaLocal) as erro:
            erro_final = str(erro)
            time.sleep(1)
    if os.name == "nt" and processo.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
        )
    else:
        encerrar(processo)
    raise FalhaLocal(
        f"O servidor não ficou pronto em 45 segundos ({erro_final}). Veja {log}; corrija a causa e execute novamente."
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        enderecos, mensagem = iniciar()
    except (FalhaLocal, OSError, urllib.error.URLError) as erro:
        print(f"NÃO FOI POSSÍVEL ABRIR: {erro}")
        if not isinstance(erro, FalhaLocal):
            print(
                "Confira servidor.log em LOCALAPPDATA/SitesDoReino/administracao-local, corrija a causa indicada e execute novamente."
            )
        return 1
    print(mensagem)
    for titulo, endereco in enderecos:
        print(f"{titulo} | HTTP 200 | {endereco}")
    if not webbrowser.open(enderecos[0][1]):
        print("O navegador não abriu. Abra o link do Plano mestre exibido acima.")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--servir"]:
        try:
            supervisionar(
                Path(os.environ["LOCALAPPDATA"]) / "SitesDoReino/administracao-local"
            )
        except FalhaLocal as erro:
            print(str(erro), flush=True)
            raise SystemExit(1)
        except Exception:
            print(
                "A administração não iniciou. Confira a conexão de produção e a compatibilidade do banco; nenhum segredo foi registrado.",
                flush=True,
            )
            raise SystemExit(1)
        raise SystemExit(0)
    raise SystemExit(main())
