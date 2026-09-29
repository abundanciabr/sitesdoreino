"""Ensaia o provisionamento no Linux com PostgreSQL 17 descartável."""

import shutil
import subprocess
import time
import uuid
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]


def docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], text=True, capture_output=True, check=check, timeout=90
    )


def test_provisionamento_preserva_configuracao_e_recupera_falhas(tmp_path):
    nome = "pme995-" + uuid.uuid4().hex[:12]
    (tmp_path / "env").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "env" / "admin.env").write_text(
        "DJANGO_SECRET_KEY=fixture\nDATABASE_URL=postgres://admin:fixture@postgres/admin_db\n"
        "DEBUG=0\nSCRIPT_NAME=/admin\nIDENTIDADE_API_URL=http://identidade:8000/interno\n"
        "IDENTIDADE_API_TOKEN=fixture\nADMIN_EMAILS=admin@exemplo.test\n"
        "TOKENS_ACEITOS_PAGES=fixture-pages\nGITHUB_TOKEN_FILA=SENTINELA_NAO_VAZAR\n"
        "ANTHROPIC_API_KEY=fixture-ia\nANTHROPIC_WORKSPACE_ID=fixture-workspace\n"
        "VARIAVEL_ALHEIA=preservar\n",
        encoding="utf-8",
    )
    (tmp_path / "env" / "identidade.env").write_text(
        "IDENTIDADE_STAFF_EMAILS=admin@exemplo.test\n", encoding="utf-8"
    )
    for origem, destino in (
        ("infra/provisionar-coordenacao.sh", "provisionar-coordenacao.sh"),
        ("infra/provisionar-admin.sh", "provisionar-admin.sh"),
        ("services/admin/apps/core/coordenacao.sql", "coordenacao.sql"),
    ):
        shutil.copy2(RAIZ / origem, tmp_path / destino)
    stub = tmp_path / "bin" / "docker"
    stub.write_text(
        """#!/usr/bin/env bash
set -eu
if [ "$1" = inspect ]; then
  { [ ! -e /opt/plataforma/falha-saude ] || [ ! -e /opt/plataforma/recarregou ]; } && echo healthy || echo unhealthy
  exit 0
fi
[ "$1" = compose ] || exit 2
shift
case "$1" in
  ps)
    case " $* " in *' -q admin '*) echo admin-isolada;; esac
    exit 0;;
  up)
    touch /opt/plataforma/recarregou
    [ ! -e /opt/plataforma/falha-recarga ]; exit $?;;
  exec)
    shift
    [ "$1" = -T ] && shift
    if [ "$1" = -e ]; then shift 2; fi
    servico="$1"; shift
    if [ "$servico" = postgres ]; then exec "$@"; fi
    [ "$servico" = admin ] && [ "$1" = python ] || exit 2
    entrada="$(cat)"
    if [[ "$entrada" = ghcr.io/* ]]; then
      printf '%s' "$entrada" | perl -MJSON::PP -e '$imagem=<STDIN>; chomp $imagem; $d=decode_json(join("",<STDIN>)); $e=$d->{estado}; exit 1 unless $e eq "publicada" || $e eq "falhou"; exit 1 if $e eq "publicada" && $d->{aceite_funcional} ne "conferido"; exit 1 unless $d->{digest}=~/^sha256:[0-9a-f]{64}$/ && $d->{anterior_digest}=~/^ghcr.io\\/abundanciabr\\/plataforma-admin\\@sha256:[0-9a-f]{64}$/; $v=$e eq "publicada" ? "ghcr.io/abundanciabr/plataforma-admin\\@".$d->{digest} : $d->{anterior_digest}; exit($imagem eq $v ? 0:1)'
      exit $?
    fi
    if [[ "$entrada" = postgres://coordenacao_user:* ]]; then
      [ ! -e /opt/plataforma/falha-esquema ] || exit 1
      senha="${entrada#postgres://coordenacao_user:}"
      senha="${senha%%@*}"
      PGPASSWORD="$senha" exec psql -h 127.0.0.1 -U coordenacao_user -d coordenacao_db -v ON_ERROR_STOP=1 -f /opt/plataforma/coordenacao.sql
    fi
    [ "$entrada" = '{}' ]; exit $?;;
esac
exit 2
""",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    for arquivo in tmp_path.rglob("*"):
        if arquivo.is_file():
            arquivo.write_bytes(arquivo.read_bytes().replace(b"\r\n", b"\n"))
    docker(
        "run",
        "-d",
        "--rm",
        "--name",
        nome,
        "--cpus",
        "1",
        "--memory",
        "1g",
        "--network",
        "none",
        "-e",
        "POSTGRES_HOST_AUTH_METHOD=trust",
        "-v",
        f"{tmp_path}:/opt/plataforma",
        "postgres:17",
    )
    try:
        for _ in range(30):
            if (
                docker(
                    "exec", nome, "pg_isready", "-U", "postgres", check=False
                ).returncode
                == 0
            ):
                break
            time.sleep(1)
        else:
            raise AssertionError("PostgreSQL 17 não ficou pronto")
        docker(
            "exec", nome, "psql", "-U", "postgres", "-c", "CREATE ROLE admin_user LOGIN"
        )
        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "CREATE DATABASE admin_db OWNER admin_user",
        )
        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "REVOKE ALL ON DATABASE admin_db FROM PUBLIC",
        )

        def executar(script="provisionar-coordenacao.sh", timeout=90):
            return subprocess.run(
                [
                    "docker",
                    "exec",
                    "-e",
                    "PATH=/opt/plataforma/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    nome,
                    "bash",
                    f"/opt/plataforma/{script}",
                ],
                text=True,
                capture_output=True,
                timeout=timeout,
            )

        (tmp_path / "falha-esquema").touch()
        esquema = executar()
        assert esquema.returncode != 0 and "esquema" in esquema.stderr
        assert (
            "COORDENACAO_DATABASE_URL="
            not in (tmp_path / "env" / "admin.env").read_text()
        )
        preparo = (tmp_path / "env" / "coordenacao.preparo").read_text()
        (tmp_path / "falha-esquema").unlink()
        (tmp_path / "falha-recarga").touch()
        falha = executar()
        assert falha.returncode != 0 and "falharam" in falha.stderr
        assert (
            "COORDENACAO_DATABASE_URL="
            not in (tmp_path / "env" / "admin.env").read_text()
        )
        assert (tmp_path / "env" / "coordenacao.preparo").read_text() == preparo
        (tmp_path / "falha-recarga").unlink()
        (tmp_path / "falha-saude").touch()
        (tmp_path / "recarregou").unlink()
        saude = executar()
        assert saude.returncode != 0 and "admin" in saude.stderr
        assert (
            "COORDENACAO_DATABASE_URL="
            not in (tmp_path / "env" / "admin.env").read_text()
        )
        (tmp_path / "falha-saude").unlink()
        primeira = executar()
        assert primeira.returncode == 0, primeira.stderr
        assert not (tmp_path / "env" / "coordenacao.preparo").exists()
        env = (tmp_path / "env" / "admin.env").read_text()
        assert "VARIAVEL_ALHEIA=preservar" in env
        assert "GITHUB_TOKEN_FILA=SENTINELA_NAO_VAZAR" in env
        assert "COORDENACAO_IDENTIDADES={}" in env
        assert "PRONTO:" in primeira.stdout
        assert "SENTINELA_NAO_VAZAR" not in primeira.stdout + primeira.stderr
        segredo = next(
            linha.split("=", 1)[1]
            for linha in env.splitlines()
            if linha.startswith("COORDENACAO_RECIBOS_CHAVE=")
        )
        assert segredo not in primeira.stdout + primeira.stderr
        segunda = executar()
        assert segunda.returncode == 0, segunda.stderr
        assert (tmp_path / "env" / "admin.env").read_text() == env
        assert (
            docker(
                "exec",
                nome,
                "psql",
                "-U",
                "postgres",
                "-tAc",
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='coordenacao_db'",
            ).stdout.strip()
            == "coordenacao_user"
        )
        assert (
            docker(
                "exec",
                nome,
                "psql",
                "-U",
                "postgres",
                "-d",
                "coordenacao_db",
                "-tAc",
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='coordenacao'",
            ).stdout.strip()
            == "9"
        )
        cruzado = docker(
            "exec",
            nome,
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            "coordenacao_user",
            "-d",
            "admin_db",
            "-c",
            "SELECT 1",
            check=False,
        )
        assert (
            cruzado.returncode != 0
            and 'permission denied for database "admin_db"' in cruzado.stderr
        )
        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "GRANT CONNECT ON DATABASE admin_db TO coordenacao_user",
        )
        privilegio_cruzado = executar()
        assert (
            privilegio_cruzado.returncode != 0 and "outra" in privilegio_cruzado.stderr
        )
        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "REVOKE CONNECT ON DATABASE admin_db FROM coordenacao_user",
        )
        assert (tmp_path / "env" / "admin.env").read_text() == env

        holder = subprocess.Popen(
            [
                "docker",
                "exec",
                nome,
                "flock",
                "-x",
                "/opt/plataforma/.publicacao.lock",
                "sleep",
                "3",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.3)
            bloqueada = docker(
                "exec",
                "-e",
                "PATH=/opt/plataforma/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                nome,
                "timeout",
                "1",
                "bash",
                "/opt/plataforma/provisionar-coordenacao.sh",
                check=False,
            )
            assert bloqueada.returncode == 124
            assert (tmp_path / "env" / "admin.env").read_text() == env
        finally:
            holder.wait(timeout=10)
        herdada = docker(
            "exec",
            "-e",
            "PATH=/opt/plataforma/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            nome,
            "bash",
            "-c",
            "cd /opt/plataforma; exec 8<.publicacao.lock; flock --exclusive 8; bash provisionar-coordenacao.sh",
        )
        assert "PRONTO:" in herdada.stdout

        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "ALTER ROLE coordenacao_user CREATEDB",
        )
        privilegiada = executar()
        assert privilegiada.returncode != 0 and "privil" in privilegiada.stderr
        docker(
            "exec",
            nome,
            "psql",
            "-U",
            "postgres",
            "-c",
            "ALTER ROLE coordenacao_user NOCREATEDB",
        )
        assert (tmp_path / "env" / "admin.env").read_text() == env

        (tmp_path / "publicacoes-candidatos").mkdir()
        (tmp_path / "publicacoes-candidatos" / "admin.json").write_text(
            '{"estado":"incerta"}', encoding="utf-8"
        )
        (tmp_path / ".env").write_text(
            "ADMIN_IMAGE=ghcr.io/abundanciabr/plataforma-admin@sha256:"
            + "a" * 64
            + "\n",
            encoding="utf-8",
        )
        recusada = executar()
        assert recusada.returncode != 0 and "admin em curso" in recusada.stderr
        assert (tmp_path / "env" / "admin.env").read_text() == env
        admin_recusada = executar("provisionar-admin.sh")
        assert (
            admin_recusada.returncode != 0
            and "admin em curso" in admin_recusada.stdout + admin_recusada.stderr
        )
        assert (tmp_path / "env" / "admin.env").read_text() == env
        (tmp_path / "publicacoes-candidatos" / "admin.json").write_bytes(
            (
                '{"estado":"publicada","digest":"sha256:'
                + "b" * 64
                + '","anterior_digest":"ghcr.io/abundanciabr/plataforma-admin@sha256:'
                + "a" * 64
                + '"}'
            ).encode()
        )
        divergente = executar()
        assert divergente.returncode != 0 and "admin em curso" in divergente.stderr
        assert (tmp_path / "env" / "admin.env").read_text() == env
        (tmp_path / ".env").write_bytes(
            (
                "ADMIN_IMAGE=ghcr.io/abundanciabr/plataforma-admin@sha256:"
                + "b" * 64
                + "\n"
            ).encode()
        )
        (tmp_path / "publicacoes-candidatos" / "admin.json").write_bytes(
            (
                '{"estado":"publicada","aceite_funcional":"pendente","digest":"sha256:'
                + "b" * 64
                + '","anterior_digest":"ghcr.io/abundanciabr/plataforma-admin@sha256:'
                + "a" * 64
                + '"}'
            ).encode()
        )
        pendente = executar()
        assert pendente.returncode != 0 and "admin em curso" in pendente.stderr
        (tmp_path / "publicacoes-candidatos" / "admin.json").write_bytes(
            (tmp_path / "publicacoes-candidatos" / "admin.json")
            .read_bytes()
            .replace(b'"pendente"', b'"conferido"')
        )
        conferido = executar()
        assert conferido.returncode == 0 and "PRONTO:" in conferido.stdout
        (tmp_path / "publicacoes-candidatos" / "admin.json").unlink()
        (tmp_path / "env" / "admin.env").write_bytes(
            env.replace(
                "COORDENACAO_IDENTIDADES={}", "COORDENACAO_IDENTIDADES={invalido}"
            ).encode()
        )
        invalida = executar()
        assert (
            invalida.returncode != 0
            and "env/admin.env antes de repetir" in invalida.stderr
        )
        (tmp_path / "env" / "admin.env").write_bytes(env.encode())

        # A reprovisão da admin conhece e preserva as três chaves da coordenação.
        (tmp_path / "env" / "admin.env").write_bytes(
            env.replace("VARIAVEL_ALHEIA=preservar\n", "").encode()
        )
        admin = executar("provisionar-admin.sh")
        assert admin.returncode == 0, admin.stderr
        novo = (tmp_path / "env" / "admin.env").read_text()
        for chave in (
            "COORDENACAO_DATABASE_URL",
            "COORDENACAO_IDENTIDADES",
            "COORDENACAO_RECIBOS_CHAVE",
        ):
            assert (
                next(l for l in env.splitlines() if l.startswith(chave + "=")) in novo
            )
    finally:
        docker("rm", "-f", nome, check=False)
