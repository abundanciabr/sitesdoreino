"""Roda os testes de uma célula com um comando só, numa cópia limpa do repositório.

    make celula CELULA=funil
    make celula CELULA=funil ARGS="-k cadastro -x"
    python ci/testar_celula.py funil [argumentos do pytest...]

O que este script faz, nesta ordem, sem nenhuma variável de ambiente preparada:

1. Ambiente Python em `<pasta temporária>/sitesdoreino-sessoes/<celula>/venv`,
   criado com o mesmo Python da imagem de produção (`celula-template/Dockerfile`).
   O caminho é CURTO de propósito: no Windows um venv em caminho longo estoura o
   limite de 260 caracteres e o pip termina "bem" com o pacote quebrado.
2. `pip install -r services/<celula>/requirements.txt`, rodado da RAIZ do clone
   (as wheels vendorizadas têm caminho relativo à raiz). Só reinstala quando o
   requirements.txt muda: o hash fica gravado dentro do venv.
3. Valores de TESTE para o que a célula exige:
   `DJANGO_SECRET_KEY`; `DATABASE_URL`, se o `config/settings.py` pede banco,
   apontando para um Postgres 17 local em Docker (container
   `sitesdoreino-testes-pg`); e `REDIS_STREAMS_URL`, se os testes dela leem essa
   variável do ambiente (Redis real), apontando para um Redis 7 local
   (`sitesdoreino-testes-redis`). Os containers escutam só em 127.0.0.1 e são
   criados ou religados se faltarem. Variável que você já exportou ganha do
   valor de teste.
4. `python -m pytest -q` dentro de `services/<celula>`, com esse venv.

Os valores de teste só existem no ambiente do processo do pytest. Nada aqui toca
`settings.py` nem o servidor: em produção a chave verdadeira continua obrigatória.
Só biblioteca padrão.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NoReturn

RAIZ = Path(__file__).resolve().parents[1]

# Valores de teste: não são segredo, valem só no processo do pytest.
CHAVE_DE_TESTE = "teste-local"

PG_NOME = "sitesdoreino-testes-pg"
PG_PORTA = 55400
PG_SENHA = "teste"

REDIS_NOME = "sitesdoreino-testes-redis"
REDIS_PORTA = 56400


def falhar(mensagem: str, codigo: int = 2) -> NoReturn:
    print(f"ERROR: {mensagem}", file=sys.stderr, flush=True)
    raise SystemExit(codigo)


def dizer(mensagem: str) -> None:
    print(f"[testar_celula] {mensagem}", flush=True)


# --------------------------------------------------------------------------
# Python do venv
# --------------------------------------------------------------------------


def versao_python_de_producao() -> tuple[int, int]:
    dockerfile = RAIZ / "celula-template" / "Dockerfile"
    try:
        achou = re.search(r"^FROM python:(\d+)\.(\d+)", dockerfile.read_text(), re.M)
    except OSError:
        achou = None
    return (int(achou.group(1)), int(achou.group(2))) if achou else (3, 12)


def versao_de(exe: Path | str) -> tuple[int, int] | None:
    try:
        saida = subprocess.run(
            [
                str(exe),
                "-c",
                "import sys;print(sys.version_info[0], sys.version_info[1])",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout.split()
        return (int(saida[0]), int(saida[1]))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def achar_python(versao: tuple[int, int]) -> str:
    """Um Python da versão pedida: o que roda este script, se servir, ou um instalado."""
    maior, menor = versao
    candidatos: list[str] = [sys.executable]
    for nome in (f"python{maior}.{menor}", "python"):
        achado = shutil.which(nome)
        if achado:
            candidatos.append(achado)
    if os.name == "nt":
        if shutil.which("py"):
            try:
                caminho = subprocess.run(
                    [
                        "py",
                        f"-{maior}.{menor}",
                        "-c",
                        "import sys;print(sys.executable)",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                ).stdout.strip()
                if caminho:
                    candidatos.append(caminho)
            except (OSError, subprocess.SubprocessError):
                pass
        sufixo = f"Python{maior}{menor}"
        locais = [Path(os.environ.get("ProgramFiles", r"C:\Program Files"))]
        if os.environ.get("LOCALAPPDATA"):
            locais.insert(0, Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python")
        candidatos += [str(base / sufixo / "python.exe") for base in locais]
    for candidato in candidatos:
        if Path(candidato).exists() and versao_de(candidato) == versao:
            return candidato
    instalar = (
        f"winget install Python.Python.{maior}.{menor}"
        if os.name == "nt"
        else f"instale o python{maior}.{menor}"
    )
    falhar(
        f"não achei Python {maior}.{menor} (o da imagem de produção). Instale: {instalar}"
    )


def python_do_venv(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def preparar_venv(celula: str, pasta_da_celula: Path) -> Path:
    venv = Path(tempfile.gettempdir()) / "sitesdoreino-sessoes" / celula / "venv"
    exe = python_do_venv(venv)
    versao = versao_python_de_producao()

    if not exe.exists() or versao_de(exe) != versao:
        dizer(f"criando o ambiente Python {versao[0]}.{versao[1]} em {venv}")
        base = achar_python(versao)
        venv.parent.mkdir(parents=True, exist_ok=True)
        feito = subprocess.run([base, "-m", "venv", "--clear", str(venv)])
        if feito.returncode != 0 or not exe.exists():
            falhar(f"não consegui criar o venv em {venv}")

    requirements = pasta_da_celula / "requirements.txt"
    if not requirements.exists():
        return exe
    selo = venv / ".requirements-sha256"
    impressao = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if selo.exists() and selo.read_text().strip() == impressao:
        return exe

    log = venv.parent / "pip.log"
    dizer(f"instalando {requirements.relative_to(RAIZ).as_posix()} (log em {log})")
    with log.open("w", encoding="utf-8") as saida:
        # Da RAIZ: a wheel vendorizada tem caminho relativo a ela. Sem `-q`: o
        # pip em silêncio engoliu um erro de caminho longo; aqui ele fica no log.
        feito = subprocess.run(
            [
                str(exe),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "-r",
                requirements.relative_to(RAIZ).as_posix(),
            ],
            cwd=RAIZ,
            stdout=saida,
            stderr=subprocess.STDOUT,
        )
    texto = log.read_text(encoding="utf-8", errors="replace")
    if feito.returncode != 0 or re.search(r"^ERROR|OSError", texto, re.M):
        print("".join(texto.splitlines(keepends=True)[-40:]), file=sys.stderr)
        falhar(f"o pip não terminou limpo (log inteiro em {log})")
    selo.write_text(impressao)
    return exe


# --------------------------------------------------------------------------
# Postgres e Redis de teste (containers locais, só em 127.0.0.1)
# --------------------------------------------------------------------------


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def garantir_container(
    nome: str,
    imagem: str,
    porta: int,
    porta_interna: int,
    opcoes: list[str],
    comando: list[str],
    pronto: list[str],
) -> None:
    """Deixa o container `nome` de pé (cria ou religa) e espera ele responder."""
    if shutil.which("docker") is None:
        falhar(
            "esta célula precisa de banco/Redis e não achei o Docker. "
            "Abra o Docker Desktop, ou exporte DATABASE_URL / REDIS_STREAMS_URL."
        )
    estado = docker("inspect", "-f", "{{.State.Running}}", nome)
    if estado.returncode != 0:
        if "no such" not in estado.stderr.lower():
            falhar(
                f"o Docker não respondeu (ligue o Docker Desktop): {estado.stderr.strip()}"
            )
        dizer(f"criando {nome} ({imagem}, 127.0.0.1:{porta})")
        criado = docker(
            "run",
            "-d",
            "--name",
            nome,
            "-p",
            f"127.0.0.1:{porta}:{porta_interna}",
            *opcoes,
            imagem,
            *comando,
        )
        # Duas células subindo juntas: quem perde a corrida só espera o container do outro.
        if criado.returncode != 0 and "already in use" not in criado.stderr.lower():
            falhar(f"não consegui subir {nome}: {criado.stderr.strip()}")
    elif estado.stdout.strip() != "true":
        dizer(f"religando {nome}")
        ligado = docker("start", nome)
        if ligado.returncode != 0:
            falhar(f"não consegui religar {nome}: {ligado.stderr.strip()}")
    for _ in range(90):
        if docker("exec", nome, *pronto).returncode == 0:
            return
        time.sleep(1)
    falhar(f"{nome} não ficou pronto em 90 s")


def garantir_postgres() -> str:
    garantir_container(
        PG_NOME,
        "postgres:17",
        PG_PORTA,
        5432,
        [
            "-e",
            f"POSTGRES_PASSWORD={PG_SENHA}",
        ],
        [
            # banco só de teste: sem fsync, criar o banco de teste é bem mais rápido
            "-c",
            "fsync=off",
            "-c",
            "synchronous_commit=off",
            "-c",
            "full_page_writes=off",
            "-c",
            "max_connections=200",
        ],
        # `-h 127.0.0.1` de propósito: durante a inicialização o Postgres do
        # container só escuta no socket local; pelo TCP só responde quando pronto.
        ["pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
    )
    return f"postgres://postgres:{PG_SENHA}@127.0.0.1:{PG_PORTA}"


def garantir_redis() -> str:
    garantir_container(
        REDIS_NOME, "redis:7", REDIS_PORTA, 6379, [], [], ["redis-cli", "ping"]
    )
    return f"redis://127.0.0.1:{REDIS_PORTA}/0"


def celula_usa_banco(pasta_da_celula: Path) -> bool:
    settings = pasta_da_celula / "config" / "settings.py"
    try:
        return "DATABASE_URL" in settings.read_text(encoding="utf-8")
    except OSError:
        return False


def celula_exige_redis_real(pasta_da_celula: Path) -> bool:
    """Algum teste da célula lê `REDIS_STREAMS_URL` do ambiente (não a define com monkeypatch)."""
    leitura = re.compile(r"""os\.environ(\.get\(|\[)\s*["']REDIS_STREAMS_URL["']""")
    for arquivo in (pasta_da_celula / "tests").rglob("*.py"):
        try:
            if leitura.search(arquivo.read_text(encoding="utf-8")):
                return True
        except OSError:
            continue
    return False


# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        falhar(
            "uso: python ci/testar_celula.py <celula> [argumentos do pytest]  (ex.: funil)"
        )
    celula, extras = argv[0], argv[1:]
    pasta = RAIZ / "services" / celula
    if not pasta.is_dir():
        falhar(f"não existe services/{celula}")

    python = preparar_venv(celula, pasta)

    ambiente = dict(os.environ)
    ambiente.setdefault("PYTHONUTF8", "1")
    if not ambiente.get("DJANGO_SECRET_KEY"):
        ambiente["DJANGO_SECRET_KEY"] = CHAVE_DE_TESTE
    if celula_usa_banco(pasta) and not ambiente.get("DATABASE_URL"):
        ambiente["DATABASE_URL"] = f"{garantir_postgres()}/{celula}"
    if celula_exige_redis_real(pasta) and not ambiente.get("REDIS_STREAMS_URL"):
        ambiente["REDIS_STREAMS_URL"] = garantir_redis()

    dizer(f"pytest de services/{celula} com {python}")
    return subprocess.run(
        [str(python), "-m", "pytest", "-q", *extras], cwd=pasta, env=ambiente
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
