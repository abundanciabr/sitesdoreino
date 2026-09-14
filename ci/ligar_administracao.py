"""Prepara e abre a administração do PC; só imprime links depois da prova HTTP."""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = "http://127.0.0.1:8000"
PAGINAS = {
    "Plano mestre": "plano-mestre/",
    "Documentos": "documentos/",
    "Biblioteca": "livro/",
    "Reunião": "reuniao/",
}


class FalhaLocal(Exception):
    pass


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
        if anterior.get("token"):
            return (
                verificar_paginas(anterior["token"]),
                "A administração já estava ligada.",
            )
        raise FalhaLocal(
            "A porta 8000 está ocupada por outro processo. Feche o servidor anterior na janela em que foi iniciado e execute este comando novamente. Nenhum processo foi encerrado."
        )

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

    token = secrets.token_urlsafe(32)
    ambiente = os.environ.copy()
    ambiente.update(
        {
            "PYTHONUTF8": "1",
            "SCRIPT_NAME": "",
            "DEBUG": "1",
            "DJANGO_SECRET_KEY": anterior.get("chave") or secrets.token_urlsafe(48),
            "DATABASE_URL": "sqlite:///" + (dados / "administracao.sqlite3").as_posix(),
            "ADMIN_PLANOS_DIR": str(planos),
            "ADMIN_LOCAL_EMAIL": "mantenedor@localhost",
            "ADMIN_EMAILS": "mantenedor@localhost",
            "ADMIN_LINK_TOKEN": token,
            "URL_DE_ENTRADA": f"/acesso-local/{token}/",
        }
    )
    print("Preparando o banco local...", flush=True)
    executar([str(python), "manage.py", "migrate", "--noinput"], log, ambiente)
    print("Ligando a administração e verificando as páginas...", flush=True)
    with log.open("ab") as saida:
        processo = subprocess.Popen(
            [str(python), "manage.py", "runserver", "127.0.0.1:8000"],
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
                    }
                ),
                encoding="utf-8",
            )
            return enderecos, "Administração local pronta. Pode fechar este terminal."
        except (OSError, urllib.error.URLError, FalhaLocal) as erro:
            erro_final = str(erro)
            time.sleep(1)
    processo.terminate()
    processo.wait(timeout=10)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
