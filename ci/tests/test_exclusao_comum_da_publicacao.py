"""Exclusão no receptor, inclusive reentrada e descritor de outro inode."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

RAIZ = Path(__file__).resolve().parents[2]
TRAVA = RAIZ / "infra/trava-de-publicacao.sh"
MUTADORES = (
    "deploy-celula-na-vps.sh", "reverter-celula-na-vps.sh",
    "sincronizar-infra-na-vps.sh", "publicar-dados-admin-na-vps.sh",
    "backfill-mensagens-do-forum.sh", "backfill-pontos-do-forum.sh",
    "canario-fase-3-outbox.sh", "conferir-as-fichas.sh", "esvaziar-caixa.sh",
    "ligar-os-degraus.sh", "limpar-avisos-orfaos.sh", "restaurar-backup.sh",
)


def executar(codigo, pasta, *, como_root=False, **kwargs):
    ambiente = os.environ | {"PLATAFORMA_DIR": str(pasta), "FRAGMENTO": str(TRAVA)}
    comando = ["bash", "-eu", "-c", "echo preparado; " + codigo]
    if os.name == "nt" or (como_root and os.geteuid() != 0):
        comando = ["docker", "run", "--rm", "--network", "none", "--cpus", "1",
                   "--memory", "512m", "--volume", f"{pasta}:/plataforma",
                   "--volume", f"{TRAVA}:/fragmento:ro", "--env",
                   "PLATAFORMA_DIR=/plataforma", "--env", "FRAGMENTO=/fragmento",
                   "--entrypoint", "bash", "ubuntu:24.04", "-eu", "-c",
                   "echo preparado; " + codigo]
        if "stdin" in kwargs:
            comando.insert(2, "--interactive")
    processo = subprocess.Popen(comando, env=ambiente, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, **kwargs)
    assert processo.stdout.readline().strip() == "preparado", processo.stderr.read()
    return processo


def concluir(processo):
    saida, erro = processo.communicate(timeout=30)
    assert processo.returncode == 0, erro
    return saida


@pytest.mark.parametrize("nome", MUTADORES)
def test_mutador_transportado_tem_mesma_trava_antes_de_docker(nome):
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    texto = (RAIZ / "infra" / nome).read_text(encoding="utf-8")
    assert fragmento in texto
    codigo = [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]
    indice_trava = next(i for i, linha in enumerate(codigo) if "flock --exclusive 8" in linha)
    operacao = {"publicar-dados-admin-na-vps.sh": 'mkdir -p "$RAIZ_DADOS"',
                "restaurar-backup.sh": "$COMPOSE exec"}.get(nome, "docker compose")
    indice_operacao = next(i for i, linha in enumerate(codigo) if operacao in linha
                            and not linha.lstrip().startswith(("echo ", "COMPOSE=")))
    assert indice_trava < indice_operacao


def test_mutacoes_de_dois_processos_nao_se_sobrepoem(tmp_path):
    # guarda: infra/trava-de-publicacao.sh:10
    primeiro = executar('source "$FRAGMENTO"; echo iniciou; read -r sinal; echo terminou', tmp_path,
                        stdin=subprocess.PIPE)
    assert primeiro.stdout.readline().strip() == "iniciou"
    segundo = None
    try:
        sonda = executar('flock --nonblock --exclusive "$PLATAFORMA_DIR/.publicacao.lock" -c "echo invadiu"', tmp_path)
        saida, erro = sonda.communicate(timeout=30)
        assert sonda.returncode == 1, (saida, erro)
        segundo = executar('source "$FRAGMENTO"; echo segundo', tmp_path)
        with pytest.raises(subprocess.TimeoutExpired):
            segundo.communicate(timeout=0.2)
        primeiro.stdin.write("liberar\n")
        primeiro.stdin.flush()
        assert concluir(primeiro).strip() == "terminou"
        assert concluir(segundo).strip() == "segundo"
    finally:
        for processo in (primeiro, segundo):
            if processo is not None and processo.poll() is None:
                if processo.stdin is not None:
                    processo.stdin.close()
                processo.wait(timeout=30)


def test_recuperacao_reentra_com_descritor_herdado_sem_deadlock(tmp_path):
    processo = executar("""source "$FRAGMENTO"; bash -eu -c 'source "$FRAGMENTO"; echo recuperou'""", tmp_path)
    assert concluir(processo).strip() == "recuperou"


def test_descritor_de_outro_inode_nao_desvia_a_trava(tmp_path):
    primeiro = executar('source "$FRAGMENTO"; echo iniciou; read -r sinal', tmp_path,
                        stdin=subprocess.PIPE)
    assert primeiro.stdout.readline().strip() == "iniciou"
    segundo = executar('exec 8>>"$PLATAFORMA_DIR/outra.lock"; PUBLICACAO_JA_TRAVADA=1; '
                        'source "$FRAGMENTO"; echo segundo', tmp_path)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            segundo.communicate(timeout=0.2)
        primeiro.stdin.write("liberar\n")
        primeiro.stdin.flush()
        concluir(primeiro)
        assert concluir(segundo).strip() == "segundo"
    finally:
        for processo in (primeiro, segundo):
            if processo is not None and processo.poll() is None:
                if processo.stdin is not None:
                    processo.stdin.close()
                processo.wait(timeout=30)


def test_flock_ausente_para_antes_da_mutacao_e_diz_acao(tmp_path):
    processo = executar('PATH=/inexistente; source "$FRAGMENTO"; echo mutou', tmp_path)
    saida, erro = processo.communicate(timeout=30)
    assert processo.returncode != 0
    assert "mutou" not in saida
    assert "flock" in erro and "instale util-linux" in erro


def test_root_e_deploy_revezam_mesmo_inode_com_umask_restritiva(tmp_path):
    codigo = r"""
    pasta=$(mktemp -d /tmp/trava-permissoes-XXXXXX)
    chmod 777 "$pasta"
    export PLATAFORMA_DIR="$pasta"
    umask 077
    source "$FRAGMENTO"
    inode=$(stat -c %i "$pasta/.publicacao.lock")
    test "$(stat -c %a "$pasta/.publicacao.lock")" = 644
    if su nobody -s /bin/bash -c 'flock --nonblock --exclusive "$PLATAFORMA_DIR/.publicacao.lock" -c true'; then
      echo "segunda posse atravessou a trava" >&2; exit 1
    fi
    exec 8<&-
    su nobody -s /bin/bash -c 'source "$FRAGMENTO"'
    source "$FRAGMENTO"
    test "$(stat -c %i "$pasta/.publicacao.lock")" = "$inode"
    exec 8<&-
    pasta=$(mktemp -d /tmp/trava-permissoes-XXXXXX)
    chmod 777 "$pasta"
    export PLATAFORMA_DIR="$pasta"
    su nobody -s /bin/bash -c 'umask 077; source "$FRAGMENTO"'
    inode=$(stat -c %i "$pasta/.publicacao.lock")
    test "$(stat -c %a "$pasta/.publicacao.lock")" = 644
    source "$FRAGMENTO"
    test "$(stat -c %i "$pasta/.publicacao.lock")" = "$inode"
    echo alternancia-confirmada
    """
    assert concluir(executar(codigo, tmp_path, como_root=True)).strip() == "alternancia-confirmada"
