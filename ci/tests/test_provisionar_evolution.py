from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from conftest import BASH


RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-evolution.sh"
TOKEN = "a" * 64


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
        "if printf '%s\\n' \"$*\" | grep -q -- '-tAc'; then printf '1\\n'; fi\n"
        "if [ ! -t 0 ]; then cat >/dev/null; fi\n",
        encoding="utf-8",
        newline="\n",
    )
    docker.chmod(0o755)
    return plataforma


def _rodar(plataforma: Path):
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(plataforma)
    ambiente["PATH"] = str(plataforma.parent / "bin") + os.pathsep + ambiente["PATH"]
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
    assert "PAROU POR SEGURANCA" in texto
    assert "${1:-" not in texto and "$@" not in texto and "$#" not in texto


def test_grava_os_dois_lados_sem_expor_token_e_preserva_mensageria(tmp_path):
    plataforma = _plataforma(tmp_path)
    resultado = _rodar(plataforma)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "PRONTO:" in resultado.stdout
    assert TOKEN not in resultado.stdout + resultado.stderr

    evolution = plataforma / "env" / "evolution.env"
    mensageria = plataforma / "env" / "mensageria.env"
    assert _valor(evolution, "AUTHENTICATION_API_KEY") == TOKEN
    assert _valor(mensageria, "WHATSAPP_GATEWAY_TOKEN") == TOKEN
    assert _valor(mensageria, "WHATSAPP_GATEWAY_URL") == "http://evolution:8080"
    assert _valor(evolution, "AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES") == "false"
    assert "DJANGO_SECRET_KEY=preservar" in mensageria.read_text(encoding="utf-8")
    assert "DATABASE_URL=postgres://mensageria" in mensageria.read_text(encoding="utf-8")


def test_reexecucao_nao_duplica_e_rotaciona_so_a_senha_do_banco(tmp_path):
    plataforma = _plataforma(tmp_path)
    primeiro = _rodar(plataforma)
    assert primeiro.returncode == 0, primeiro.stdout + primeiro.stderr
    evolution = plataforma / "env" / "evolution.env"
    senha_antes = _valor(evolution, "DATABASE_CONNECTION_URI")

    segundo = _rodar(plataforma)
    assert segundo.returncode == 0, segundo.stdout + segundo.stderr
    senha_depois = _valor(evolution, "DATABASE_CONNECTION_URI")
    mensageria = (plataforma / "env" / "mensageria.env").read_text(encoding="utf-8")
    assert senha_depois != senha_antes
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
    assert "PAROU POR SEGURANCA" in resultado.stdout
    assert mensageria.read_text(encoding="utf-8") == antes
    assert not (plataforma / "env" / "evolution.env").exists()


def test_senha_do_banco_viaja_por_stdin_e_nao_por_argumento():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "printf \"%s\\n\" \"ALTER ROLE evolution_user" in texto
    assert 'psql -U postgres -c "ALTER ROLE evolution_user' not in texto


def test_env_gerado_e_molde_declaram_as_mesmas_chaves(tmp_path):
    plataforma = _plataforma(tmp_path)
    resultado = _rodar(plataforma)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    padrao = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)
    geradas = set(padrao.findall((plataforma / "env" / "evolution.env").read_text(encoding="utf-8")))
    molde = set(padrao.findall((RAIZ / "infra" / "env" / "evolution.env.exemplo").read_text(encoding="utf-8")))
    assert geradas == molde


def test_falha_depois_da_rotacao_tem_trap_de_reversao():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "ROTACAO_INICIADA=1" in texto
    assert "restaurar_tudo" in texto
    assert "trap 'CODIGO=$?; encerrar" in texto
