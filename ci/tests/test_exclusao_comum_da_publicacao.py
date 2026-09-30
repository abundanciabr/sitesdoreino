"""Exclusão no receptor, inclusive reentrada e descritor de outro inode."""
from __future__ import annotations

import os
import re
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


MUTADORES_MANUAIS = (
    "abrir-a-sala-de-aula.sh", "cadastrar-os-dois-cursos.sh",
    "conceder-fundador-aos-alunos.sh", "ligar-a-appmax.sh",
    "semear-areas-do-forum.sh", "semear-boas-vindas.sh", "semear-caixa.sh",
    "semear-convite-para-a-comunidade.sh", "semear-demo-caixa.sh",
    "semear-duvidas-do-forum.sh", "semear-economia.sh",
    "semear-experimento.sh", "semear-quiz.sh",
)


def trava_imediata_apos_entrada(texto, fragmento):
    entrada = re.search(r'(?m)^cd "\$RAIZ"[^\n]*\n', texto)
    return bool(entrada and texto[entrada.end():].startswith("\n" + fragmento + "\n"))


@pytest.mark.parametrize("nome", MUTADORES_MANUAIS)
def test_mutador_manual_trava_antes_de_operar(nome):
    texto = (RAIZ / "infra" / nome).read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    assert trava_imediata_apos_entrada(texto, fragmento)
    assert texto.index(fragmento) < texto.index("docker compose", texto.index(fragmento))


def test_escrita_de_env_antes_da_trava_e_reprovada():
    texto = (RAIZ / "infra/ligar-a-appmax.sh").read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    mutado = texto.replace(fragmento, 'printf %s alterado > "$RAIZ/env/pagamentos.env"\n' + fragmento, 1)
    assert trava_imediata_apos_entrada(texto, fragmento)
    assert not trava_imediata_apos_entrada(mutado, fragmento)


PROVISIONADORES_1 = (
    "admin", "aprovadores", "aviso-de-liberacao", "aviso-no-celular",
    "cursos", "email", "encomendas", "equipe-da-gamificacao",
    "evolution", "forum", "gamificacao", "identidade", "metricas",
)


@pytest.mark.parametrize("nome", PROVISIONADORES_1)
def test_provisionador_trava_antes_de_operar(nome):
    texto = (RAIZ / "infra" / f"provisionar-{nome}.sh").read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    entrada = re.search(r'(?m)^cd (?:"\$RAIZ"|/opt/plataforma)[^\n]*\n', texto)
    assert entrada and texto[entrada.end():].startswith("\n" + fragmento + "\n")
    alterado = texto[:entrada.end()] + 'printf %s alterado > "env/prova.env"\n' + texto[entrada.end():]
    entrada_alterada = re.search(r'(?m)^cd (?:"\$RAIZ"|/opt/plataforma)[^\n]*\n', alterado)
    assert not alterado[entrada_alterada.end():].startswith("\n" + fragmento + "\n")


MUTADORES_PARES = (
    "par-da-caixa", "par-da-economia", "par-da-gamificacao-com-o-forum",
    "par-da-gamificacao-com-os-alunos", "par-da-medicao",
    "par-do-forum-com-a-gamificacao", "par-do-funil-com-a-gamificacao",
    "par-do-menu", "par-do-portfolio-com-a-admin", "par-do-teste-de-aviso",
    "par-dos-parametros", "pares-da-prancheta", "pares-da-sala-de-aula",
    "pares-de-categorias",
)


@pytest.mark.parametrize("nome", MUTADORES_PARES)
def test_par_trava_mesma_raiz_antes_de_operar(nome):
    texto = (RAIZ / "infra" / f"provisionar-{nome}.sh").read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    assert 'RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"' in texto
    assert trava_imediata_apos_entrada(texto, fragmento)
    sem_trava = texto.replace(fragmento, "", 1)
    escrita_antecipada = texto.replace(fragmento, 'printf %s alterado > "env/prova.env"\n' + fragmento, 1)
    assert not trava_imediata_apos_entrada(sem_trava, fragmento)
    assert not trava_imediata_apos_entrada(escrita_antecipada, fragmento)


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
                "restaurar-backup.sh": "$COMPOSE exec",
                "reverter-celula-na-vps.sh": 'publicacao-local.py" recuperar',
                "sincronizar-infra-na-vps.sh": "docker compose up -d"}.get(nome, "docker compose")
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




@pytest.mark.parametrize(("nome", "ambiente", "erro"), (
    ("ligar-a-appmax.sh", "env/pagamentos.env", "docker-compose.yml"),
    ("provisionar-admin.sh", "env/pagamentos.env", "docker-compose.yml"),
    ("provisionar-identidade.sh", "env/pagamentos.env", "docker-compose.yml"),
    ("provisionar-par-da-caixa.sh", "env/sugestoes.env", "env/admin.env"),
))
def test_receptor_manual_ou_provisionador_espera_sem_escrever_env(tmp_path, nome, ambiente, erro):
    roteiro = RAIZ / "infra" / nome
    (tmp_path / roteiro.name).write_bytes(roteiro.read_bytes())
    env = tmp_path / ambiente
    env.parent.mkdir(parents=True)
    env.write_bytes(b"inalterado\n")
    codigo = r"""
    mkfifo "$PLATAFORMA_DIR/liberar"
    (source "$FRAGMENTO"; touch "$PLATAFORMA_DIR/segurando";
     read -r sinal < "$PLATAFORMA_DIR/liberar") &
    detentor=$!
    for tentativa in {1..100}; do
      [ -f "$PLATAFORMA_DIR/segurando" ] && break
      kill -0 "$detentor" || { echo "detentor terminou antes da posse" >&2; exit 1; }
      sleep 0.05
    done
    test -f "$PLATAFORMA_DIR/segurando" || { echo "detentor nao assumiu a trava" >&2; exit 1; }
    bash "$PLATAFORMA_DIR/{nome}" > "$PLATAFORMA_DIR/resultado" 2>&1 &
    receptor=$!
    sleep 0.3
    kill -0 "$receptor" || { echo "receptor nao esperou a trava" >&2; exit 1; }
    if flock --nonblock --exclusive "$PLATAFORMA_DIR/.publicacao.lock" -c true; then
      echo "segunda posse atravessou a trava" >&2; exit 1
    fi
    test "$(cat "$PLATAFORMA_DIR/{ambiente}")" = inalterado
    printf 'liberar\n' > "$PLATAFORMA_DIR/liberar"
    wait "$detentor"
    if wait "$receptor"; then
      echo "roteiro sem Compose terminou com sucesso indevido" >&2; exit 1
    fi
    grep -Fq '{erro}' "$PLATAFORMA_DIR/resultado"
    if [ "{nome}" = provisionar-identidade.sh ]; then
      grep -Fq "$PLATAFORMA_DIR" "$PLATAFORMA_DIR/resultado"
    fi
    test "$(cat "$PLATAFORMA_DIR/{ambiente}")" = inalterado
    echo exclusao-manual-confirmada
    """
    codigo = codigo.replace("{nome}", nome).replace("{ambiente}", ambiente).replace("{erro}", erro)
    assert concluir(executar(codigo, tmp_path)).strip() == "exclusao-manual-confirmada"
    assert env.read_text(encoding="utf-8") == "inalterado\n"


@pytest.mark.parametrize("nome", (
    "provisionar-usuario-ponte.sh", "instalar-provisionador-usuario-ponte.sh",
))
def test_kit_root_trava_mesmo_inode_antes_de_operar(nome):
    texto = (RAIZ / "infra" / nome).read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    assert trava_imediata_apos_entrada(texto, fragmento)
    assert not trava_imediata_apos_entrada(texto.replace(fragmento, "", 1), fragmento)


def test_sincronizador_fecha_fd8_antes_do_sudo_e_revalida_apos_a_posse():
    texto = (RAIZ / "infra/sincronizar-infra-na-vps.sh").read_text(encoding="utf-8")
    fragmento = TRAVA.read_text(encoding="utf-8").strip()
    assert texto.count(fragmento) == 1
    assert texto.index("\nconferir_publicacao_admin\n") < texto.index('sudo -n "$PROVISIONADOR_DA_PONTE"')
    assert texto.index('if ! docker compose --project-directory') < texto.index('sudo -n "$PROVISIONADOR_DA_PONTE"')
    assert texto.index("exec 8<&-\n  sudo -n") < texto.index(fragmento)
    assert texto.index(fragmento) < texto.index("STAGING_AGORA=")
    assert texto.index(fragmento) < texto.rindex('if ! docker compose --project-directory')
    assert texto.index("STAGING_AGORA=") < texto.index("mv -f infra.new/docker-compose.yml")
    assert texto.index("conferir_publicacao_admin\nSTAGING_AGORA=") > texto.index(fragmento)
