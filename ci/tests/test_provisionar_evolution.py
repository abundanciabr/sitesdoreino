from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from conftest import BASH


RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-evolution.sh"
TOKEN = "0123456789abcdef" * 4


def _plataforma(tmp_path: Path) -> Path:
    plataforma = tmp_path / "plataforma"
    env = plataforma / "env"
    env.mkdir(parents=True)
    (plataforma / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (env / "identidade.env").write_text("REFERENCIA=1\n", encoding="utf-8")
    (env / "mensageria.env").write_text(
        "DJANGO_SECRET_KEY=preservar\n"
        "DATABASE_URL=postgres://mensageria\n"
        "WHATSAPP_GATEWAY_URL=\n"
        f"WHATSAPP_GATEWAY_TOKEN={TOKEN}\n",
        encoding="utf-8",
    )
    binario = tmp_path / "bin"
    binario.mkdir()
    docker = binario / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "printf '%s\\n' \"$*\" >> \"${FAKE_DOCKER_LOG:?}\"\n"
        "case \"$*\" in\n"
        "  *\"SELECT 1 FROM pg_roles\"*) [ \"${FAKE_ROLE_EXISTS:-1}\" = __EMPTY__ ] || printf '%s' \"${FAKE_ROLE_EXISTS:-1}\" ;;\n"
        "  *\"SELECT 1 FROM pg_database\"*) [ \"${FAKE_DB_EXISTS:-1}\" = __EMPTY__ ] || printf '%s' \"${FAKE_DB_EXISTS:-1}\" ;;\n"
        "  *\"SELECT pg_get_userbyid\"*) printf '%s' \"${FAKE_DB_OWNER:-evolution_user}\" ;;\n"
        "esac\n"
        "if [ ! -t 0 ]; then\n"
        "  SQL=$(cat)\n"
        "  if [ \"${FAKE_ALTER_FAIL:-0}\" = 1 ] && printf '%s' \"$SQL\" | grep -q 'ALTER ROLE'; then exit 1; fi\n"
        "fi\n",
        encoding="utf-8",
        newline="\n",
    )
    docker.chmod(0o755)
    return plataforma


def _rodar(plataforma: Path, **variaveis: str):
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(plataforma)
    ambiente["PATH"] = str(plataforma.parent / "bin") + os.pathsep + ambiente["PATH"]
    ambiente["FAKE_DOCKER_LOG"] = str(plataforma.parent / "docker.log")
    ambiente.update(variaveis)
    return subprocess.run(
        [BASH, str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(arquivo: Path, chave: str) -> str:
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", arquivo.read_text(encoding="utf-8"), re.MULTILINE)
    assert achado, chave
    return achado.group(1)


def test_script_tem_sintaxe_valida_e_roda_sem_argumento():
    assert SCRIPT.is_file()
    resultado = subprocess.run([BASH, "-n", str(SCRIPT)], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "PAROU POR SEGURANÇA" in texto
    assert "Uso:" not in texto


def test_grava_os_dois_lados_sem_expor_token_e_preserva_mensageria(tmp_path):
    plataforma = _plataforma(tmp_path)
    resultado = _rodar(plataforma)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "PRONTO:" in resultado.stdout
    assert TOKEN not in resultado.stdout + resultado.stderr
    assert TOKEN not in (plataforma.parent / "docker.log").read_text(encoding="utf-8")

    evolution = plataforma / "env" / "evolution.env"
    mensageria = plataforma / "env" / "mensageria.env"
    assert _valor(evolution, "AUTHENTICATION_API_KEY") == TOKEN
    assert _valor(mensageria, "WHATSAPP_GATEWAY_TOKEN") == TOKEN
    assert _valor(mensageria, "WHATSAPP_GATEWAY_URL") == "http://evolution:8080"
    assert _valor(evolution, "AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES") == "false"
    assert "DJANGO_SECRET_KEY=preservar" in mensageria.read_text(encoding="utf-8")
    assert "DATABASE_URL=postgres://mensageria" in mensageria.read_text(encoding="utf-8")


def test_reexecucao_preserva_segredos_e_nao_duplica_chaves(tmp_path):
    plataforma = _plataforma(tmp_path)
    primeiro = _rodar(plataforma)
    assert primeiro.returncode == 0, primeiro.stdout + primeiro.stderr
    evolution = plataforma / "env" / "evolution.env"
    senha_antes = _valor(evolution, "DATABASE_CONNECTION_URI")

    segundo = _rodar(plataforma)
    assert segundo.returncode == 0, segundo.stdout + segundo.stderr
    senha_depois = _valor(evolution, "DATABASE_CONNECTION_URI")
    mensageria = (plataforma / "env" / "mensageria.env").read_text(encoding="utf-8")
    assert senha_depois == senha_antes
    assert mensageria.count("WHATSAPP_GATEWAY_URL=") == 1
    assert mensageria.count("WHATSAPP_GATEWAY_TOKEN=") == 1
    assert _valor(evolution, "AUTHENTICATION_API_KEY") == TOKEN


def test_duplicata_para_antes_de_tocar_nos_arquivos(tmp_path):
    plataforma = _plataforma(tmp_path)
    mensageria = plataforma / "env" / "mensageria.env"
    mensageria.write_text(mensageria.read_text(encoding="utf-8") + f"WHATSAPP_GATEWAY_TOKEN={TOKEN}\n", encoding="utf-8")
    antes = mensageria.read_text(encoding="utf-8")

    resultado = _rodar(plataforma)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in resultado.stdout
    assert mensageria.read_text(encoding="utf-8") == antes
    assert not (plataforma / "env" / "evolution.env").exists()


def test_senha_do_banco_viaja_por_stdin_e_nao_por_argumento():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "printf \"%s\\n\" \"ALTER ROLE evolution_user" in texto
    assert 'psql -U postgres -c "ALTER ROLE evolution_user' not in texto
    assert "awk -v token=" not in texto


def test_env_gerado_e_molde_declaram_as_mesmas_chaves(tmp_path):
    plataforma = _plataforma(tmp_path)
    resultado = _rodar(plataforma)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    padrao = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)
    geradas = set(padrao.findall((plataforma / "env" / "evolution.env").read_text(encoding="utf-8")))
    molde = set(padrao.findall((RAIZ / "infra" / "env" / "evolution.env.exemplo").read_text(encoding="utf-8")))
    assert geradas == molde


def test_token_previsivel_e_recusado_antes_de_criar_env(tmp_path):
    plataforma = _plataforma(tmp_path)
    mensageria = plataforma / "env" / "mensageria.env"
    mensageria.write_text(mensageria.read_text(encoding="utf-8").replace(TOKEN, "a" * 64), encoding="utf-8")

    resultado = _rodar(plataforma)

    assert resultado.returncode != 0
    assert "previsivel demais" in resultado.stdout
    assert not (plataforma / "env" / "evolution.env").exists()


def test_banco_existente_com_dono_errado_para_sem_tocar_nos_envs(tmp_path):
    plataforma = _plataforma(tmp_path)
    mensageria = plataforma / "env" / "mensageria.env"
    antes = mensageria.read_text(encoding="utf-8")

    resultado = _rodar(plataforma, FAKE_DB_OWNER="postgres")

    assert resultado.returncode != 0
    assert "nao a evolution_user" in resultado.stdout
    assert mensageria.read_text(encoding="utf-8") == antes
    assert not (plataforma / "env" / "evolution.env").exists()


def test_falha_sql_restaura_arquivos_remove_recursos_novos_e_libera_trava(tmp_path):
    plataforma = _plataforma(tmp_path)
    mensageria = plataforma / "env" / "mensageria.env"
    antes = mensageria.read_text(encoding="utf-8")

    resultado = _rodar(
        plataforma,
        FAKE_ROLE_EXISTS="__EMPTY__",
        FAKE_DB_EXISTS="__EMPTY__",
        FAKE_ALTER_FAIL="1",
    )

    assert resultado.returncode != 0
    assert "os dois envs foram restaurados" in resultado.stdout
    assert mensageria.read_text(encoding="utf-8") == antes
    assert not (plataforma / "env" / "evolution.env").exists()
    assert not (plataforma / "env" / ".provisionar-evolution.lock").exists()
    log = (plataforma.parent / "docker.log").read_text(encoding="utf-8")
    assert "-v ON_ERROR_STOP=1" in log
    assert "DROP DATABASE evolution_db" in log
    assert "DROP ROLE evolution_user" in log


def test_trava_concorrente_nao_e_removida_por_segunda_execucao(tmp_path):
    plataforma = _plataforma(tmp_path)
    trava = plataforma / "env" / ".provisionar-evolution.lock"
    trava.mkdir()

    resultado = _rodar(plataforma)

    assert resultado.returncode != 0
    assert "outro provisionamento" in resultado.stdout
    assert trava.is_dir()
