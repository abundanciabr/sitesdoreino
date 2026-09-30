"""Ensaia o provisionamento no Linux com PostgreSQL 17 descartável."""

import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]


def docker(*args, check=True):
    resultado = subprocess.run(
        ["docker", *args], text=True, capture_output=True, timeout=90
    )
    if check and resultado.returncode:
        erro = re.sub(r"postgres(?:ql)?://\S+", "postgres://[oculto]", resultado.stderr)
        erro = re.sub(r"SENTINELA_[A-Z_]+", "[oculto]", erro)
        erro = re.sub(
            r"(?i)(password|token|secret|chave)(=|:)\S+", r"\1\2[oculto]", erro
        )
        raise AssertionError(
            f"Docker do fixture falhou ({resultado.returncode}): {erro[-500:]}"
        )
    return resultado


def preparar_compose_real(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    conteudo = (RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8")
    compose.write_text(conteudo, encoding="utf-8")
    for nome in set(re.findall(r"env/[a-z0-9-]+\.env", conteudo)):
        arquivo = tmp_path / nome
        arquivo.parent.mkdir(exist_ok=True)
        arquivo.write_text("FIXTURE=1\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "POSTGRES_SUPER_PASSWORD=fixture-descartavel\n", encoding="utf-8"
    )
    docker_config = tmp_path / "docker-config"
    docker_config.mkdir()
    (docker_config / "config.json").write_text("{}\n", encoding="utf-8")
    return compose, {**os.environ, "DOCKER_CONFIG": str(docker_config)}


def test_compose_real_exige_chaves_nominais(tmp_path):
    compose, ambiente = preparar_compose_real(tmp_path)
    ambiente.pop("ALUNOS_API_TOKEN", None)
    ambiente.pop("TOKEN_CATALOGO", None)

    def configurar(chaves, *argumentos):
        return subprocess.run(
            ["docker", "compose", "-f", str(compose), "config", *argumentos],
            cwd=tmp_path,
            env={**ambiente, **chaves},
            text=True,
            capture_output=True,
            timeout=30,
        )

    valores = {
        "ALUNOS_API_TOKEN": "sentinela-alunos-descartavel",
        "TOKEN_CATALOGO": "sentinela-catalogo-descartavel",
    }
    for ausente in valores:
        parcial = {chave: valor for chave, valor in valores.items() if chave != ausente}
        vermelho = configurar(parcial, "--quiet")
        assert vermelho.returncode != 0 and ausente in vermelho.stderr
        assert not any(
            valor in vermelho.stdout + vermelho.stderr for valor in valores.values()
        )
    verde = configurar(valores, "--services")
    assert verde.returncode == 0, verde.stderr
    assert {"postgres", "admin"}.issubset(set(verde.stdout.splitlines()))
    assert not any(valor in verde.stdout + verde.stderr for valor in valores.values())


def test_provisionamento_preserva_configuracao_e_recupera_falhas(tmp_path):
    nome = "pme995-" + uuid.uuid4().hex[:12]
    (tmp_path / "env").mkdir()
    (tmp_path / "bin").mkdir()
    compose, ambiente_compose = preparar_compose_real(tmp_path)
    ambiente_compose.pop("ALUNOS_API_TOKEN", None)
    ambiente_compose.pop("TOKEN_CATALOGO", None)
    (tmp_path / "env" / "admin.env").write_text(
        "DJANGO_SECRET_KEY=fixture\nDATABASE_URL=postgres://admin:fixture@postgres/admin_db\n"
        "DEBUG=0\nSCRIPT_NAME=/admin\nIDENTIDADE_API_URL=http://identidade:8000/interno\n"
        "IDENTIDADE_API_TOKEN=fixture\nADMIN_EMAILS=admin@exemplo.test\n"
        "TOKENS_ACEITOS_PAGES=fixture-pages\nGITHUB_TOKEN_FILA=SENTINELA_NAO_VAZAR\n"
        "ANTHROPIC_API_KEY=fixture-ia\nANTHROPIC_WORKSPACE_ID=fixture-workspace\n"
        "VARIAVEL_ALHEIA=preservar\n"
        "ALUNOS_API_TOKEN=SENTINELA_GATEWAY_ALUNOS\n"
        "TOKEN_CATALOGO=SENTINELA_GATEWAY_CATALOGO\n",
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
if [ -n "${PME_COORD_VERIFICACAO:-}" ]; then
  if [ "${ALUNOS_API_TOKEN:-}" = SENTINELA_GATEWAY_ALUNOS ] && [ "${TOKEN_CATALOGO:-}" = SENTINELA_GATEWAY_CATALOGO ]; then
    printf 'ok\n' >"/opt/plataforma/compose-$PME_COORD_VERIFICACAO.tmp"
  else
    printf 'sem-chaves\n' >"/opt/plataforma/compose-$PME_COORD_VERIFICACAO.tmp"
  fi
  chmod 644 "/opt/plataforma/compose-$PME_COORD_VERIFICACAO.tmp"
  mv "/opt/plataforma/compose-$PME_COORD_VERIFICACAO.tmp" "/opt/plataforma/compose-$PME_COORD_VERIFICACAO"
  tentativas=0
  while [ ! -f "/opt/plataforma/compose-$PME_COORD_VERIFICACAO.resultado" ] && [ "$tentativas" -lt 100 ]; do
    sleep .05
    tentativas=$((tentativas + 1))
  done
  [ "$(cat "/opt/plataforma/compose-$PME_COORD_VERIFICACAO.resultado" 2>/dev/null || true)" = ok ] || exit 47
fi
if [ "${PME_COORD_FIXTURE:-}" = 1 ]; then
  [ "${ALUNOS_API_TOKEN:-}" = SENTINELA_GATEWAY_ALUNOS ] && [ "${TOKEN_CATALOGO:-}" = SENTINELA_GATEWAY_CATALOGO ] || exit 47
fi
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
                    "exec",
                    nome,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    check=False,
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

        def executar(
            script="provisionar-coordenacao.sh", timeout=90, validar_compose_real=False
        ):
            identificador = uuid.uuid4().hex if validar_compose_real else ""
            comando = [
                "docker",
                "exec",
                "-e",
                "PATH=/opt/plataforma/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "-e",
                (
                    "PME_COORD_FIXTURE=1"
                    if script == "provisionar-coordenacao.sh"
                    else "PME_COORD_FIXTURE=0"
                ),
                "-e",
                f"PME_COORD_VERIFICACAO={identificador}",
                nome,
                "bash",
                f"/opt/plataforma/{script}",
            ]
            if not validar_compose_real:
                return subprocess.run(
                    comando, text=True, capture_output=True, timeout=timeout
                )
            processo = subprocess.Popen(
                comando, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            captura = tmp_path / f"compose-{identificador}"
            limite = time.monotonic() + 10
            while (
                not captura.exists()
                and processo.poll() is None
                and time.monotonic() < limite
            ):
                time.sleep(0.05)
            assert captura.exists(), "provisionador não alcançou o Compose real"
            marcador = captura.read_text(encoding="utf-8").strip()
            assert marcador in ("ok", "sem-chaves")
            exportou_chaves = marcador == "ok"
            valores = (
                {
                    "ALUNOS_API_TOKEN": "SENTINELA_GATEWAY_ALUNOS",
                    "TOKEN_CATALOGO": "SENTINELA_GATEWAY_CATALOGO",
                }
                if exportou_chaves
                else {}
            )
            resultado_compose = subprocess.run(
                ["docker", "compose", "-f", str(compose), "config", "--quiet"],
                cwd=tmp_path,
                env={**ambiente_compose, **valores},
                text=True,
                capture_output=True,
                timeout=30,
            )
            (tmp_path / f"compose-{identificador}.resultado").write_text(
                "ok" if resultado_compose.returncode == 0 else "erro",
                encoding="utf-8",
                newline="\n",
            )
            stdout, stderr = processo.communicate(timeout=timeout)
            return (
                subprocess.CompletedProcess(
                    comando, processo.returncode, stdout, stderr
                ),
                resultado_compose,
            )

        env_admin = tmp_path / "env" / "admin.env"
        original = env_admin.read_text(encoding="utf-8")
        for chave, valor in (
            ("ALUNOS_API_TOKEN", "SENTINELA_GATEWAY_ALUNOS"),
            ("TOKEN_CATALOGO", "SENTINELA_GATEWAY_CATALOGO"),
        ):
            env_admin.write_text(
                original.replace(f"{chave}={valor}\n", ""),
                encoding="utf-8",
                newline="\n",
            )
            sem_chave = executar()
            assert sem_chave.returncode != 0 and chave in sem_chave.stderr
            assert not (tmp_path / "env" / "coordenacao.preparo").exists()
            assert valor not in sem_chave.stdout + sem_chave.stderr
            env_admin.write_text(original, encoding="utf-8", newline="\n")
        env_admin.write_text(
            original + "TOKEN_CATALOGO=duplicada\n", encoding="utf-8", newline="\n"
        )
        duplicada = executar()
        assert duplicada.returncode != 0 and "TOKEN_CATALOGO" in duplicada.stderr
        assert not (tmp_path / "env" / "coordenacao.preparo").exists()
        env_admin.write_text(original, encoding="utf-8", newline="\n")

        (tmp_path / "falha-esquema").touch()
        esquema, composicao = executar(validar_compose_real=True)
        assert composicao.returncode == 0, composicao.stderr
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
            check=False,
        )
        assert herdada.returncode == 0, herdada.stderr
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
            env.replace("VARIAVEL_ALHEIA=preservar\n", "")
            .replace("ALUNOS_API_TOKEN=SENTINELA_GATEWAY_ALUNOS\n", "")
            .replace("TOKEN_CATALOGO=SENTINELA_GATEWAY_CATALOGO\n", "")
            .encode()
        )
        admin = executar("provisionar-admin.sh")
        assert admin.returncode == 0, admin.stdout + admin.stderr
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
