import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FRAGMENTO = (RAIZ / "infra/trava-de-publicacao.sh").read_text(encoding="utf-8").strip()
SHELL = (
    "provisionar-notificacoes.sh",
    "provisionar-pages.sh",
    "provisionar-sugestoes.sh",
    "provisionar-porta-de-avisos.sh",
    "por-a-chave-da-ia-do-admin.sh",
    "por-a-chave-da-ia-do-forum.sh",
    "por-a-chave-do-github.sh",
    "fechar-porta-lateral.sh",
)
PYTHON = (
    "ativar-appmax-canario.py",
    "ativar-appmax-meshcraft-sandbox.py",
    "drill-appmax-rollback-sandbox.py",
)


@pytest.mark.parametrize("nome", SHELL)
def test_shell_carrega_a_trava_comum_antes_de_operar(nome):
    texto = (RAIZ / "infra" / nome).read_text(encoding="utf-8")
    assert texto.count(FRAGMENTO) == 1
    assert texto.index('cd "$RAIZ"') < texto.index(FRAGMENTO)


def executar_linux(codigo, pasta):
    ambiente = os.environ | {"PLATAFORMA_DIR": str(pasta)}
    comando = ["bash", "-euc", codigo]
    if os.name == "nt":
        comando = [
            "docker", "run", "--rm", "--network", "none", "--cpus", "1",
            "--memory", "512m", "--volume", f"{pasta}:/plataforma",
            "--env", "PLATAFORMA_DIR=/plataforma", "--entrypoint", "bash",
            "python:3.12-slim", "-euc", codigo,
        ]
    return subprocess.run(
        comando, env=ambiente, capture_output=True, text=True, timeout=40
    )


@pytest.mark.parametrize(
    ("nome", "comando"),
    (
        ("provisionar-porta-de-avisos.sh", 'bash "$PLATAFORMA_DIR/provisionar-porta-de-avisos.sh"'),
        ("ativar-appmax-canario.py", 'python3 "$PLATAFORMA_DIR/ativar-appmax-canario.py" --site cc06b8c3-043b-4c06-92c5-5ea624e00586 --executar'),
        ("ativar-appmax-meshcraft-sandbox.py", 'python3 "$PLATAFORMA_DIR/ativar-appmax-meshcraft-sandbox.py"'),
        ("drill-appmax-rollback-sandbox.py", 'python3 "$PLATAFORMA_DIR/drill-appmax-rollback-sandbox.py" executar'),
    ),
)
def test_entrada_real_espera_fd8_sem_escrever_antes(tmp_path, nome, comando):
    shutil.copy2(RAIZ / "infra" / nome, tmp_path / nome)
    if nome == "drill-appmax-rollback-sandbox.py":
        shutil.copy2(RAIZ / "infra/ativar-appmax-canario.py", tmp_path / "ativar-appmax-canario.py")
    (tmp_path / "docker-compose.yml").touch()
    (tmp_path / "env").mkdir()
    (tmp_path / "env/guarda.env").write_bytes(b"intacto\n")
    codigo = r"""
    mkfifo "$PLATAFORMA_DIR/liberar"
    : > "$PLATAFORMA_DIR/.publicacao.lock"
    (exec 8<"$PLATAFORMA_DIR/.publicacao.lock"; flock --exclusive 8;
     touch "$PLATAFORMA_DIR/segurando"; read -r sinal < "$PLATAFORMA_DIR/liberar") &
    detentor=$!
    for tentativa in {1..100}; do
      [ -f "$PLATAFORMA_DIR/segurando" ] && break
      kill -0 "$detentor" || exit 10
      sleep 0.05
    done
    test -f "$PLATAFORMA_DIR/segurando"
    {comando} > "$PLATAFORMA_DIR/resultado" 2>&1 &
    receptor=$!
    sleep 0.3
    kill -0 "$receptor"
    test "$(cat "$PLATAFORMA_DIR/env/guarda.env")" = intacto
    test -z "$(find "$PLATAFORMA_DIR/env" -name '*.bak-*' -print)"
    printf 'liberar\n' > "$PLATAFORMA_DIR/liberar"
    wait "$detentor"
    if wait "$receptor"; then exit 11; fi
    test "$(cat "$PLATAFORMA_DIR/env/guarda.env")" = intacto
    flock --nonblock --exclusive "$PLATAFORMA_DIR/.publicacao.lock" -c true
    echo disputa-confirmada
    """.replace("{comando}", comando)
    processo = executar_linux(codigo, tmp_path)
    assert processo.returncode == 0, (processo.stdout, processo.stderr)
    assert "disputa-confirmada" in processo.stdout


def test_canario_invalido_e_previa_nao_criam_trava(tmp_path):
    shutil.copy2(RAIZ / "infra/ativar-appmax-canario.py", tmp_path / "ativar-appmax-canario.py")
    (tmp_path / "docker-compose.yml").touch()
    (tmp_path / "env").mkdir()
    site = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
    for nome in ("pagamentos", "checkout"):
        (tmp_path / "env" / f"{nome}.env").write_text(
            f"APPMAX_CARD_ENABLED_SITES={site}\n", encoding="utf-8"
        )
    (tmp_path / "env/admin.env").write_text(
        "ALUNOS_API_TOKEN=teste\nTOKEN_CATALOGO=teste\n", encoding="utf-8"
    )
    codigo = r"""
    if python3 "$PLATAFORMA_DIR/ativar-appmax-canario.py" --site invalido --executar; then exit 10; fi
    test ! -e "$PLATAFORMA_DIR/.publicacao.lock"
    python3 "$PLATAFORMA_DIR/ativar-appmax-canario.py" --site cc06b8c3-043b-4c06-92c5-5ea624e00586 --desligar > "$PLATAFORMA_DIR/previa"
    grep -q 'PRÉVIA:' "$PLATAFORMA_DIR/previa"
    test ! -e "$PLATAFORMA_DIR/.publicacao.lock"
    echo previa-confirmada
    """
    processo = executar_linux(codigo, tmp_path)
    assert processo.returncode == 0, (processo.stdout, processo.stderr)
    assert "previa-confirmada" in processo.stdout




def test_python_mantem_fd8_na_recuperacao_e_restaura_descritor_anterior(tmp_path):
    for nome in PYTHON:
        shutil.copy2(RAIZ / "infra" / nome, tmp_path / nome)
    (tmp_path / "docker-compose.yml").touch()
    (tmp_path / "outro.lock").touch()
    codigo = r"""
    python3 - <<'PY'
import importlib.util
import os
import subprocess
from pathlib import Path

raiz = Path(os.environ["PLATAFORMA_DIR"])
site = "cc06b8c3-043b-4c06-92c5-5ea624e00586"

def carregar(nome):
    caminho = raiz / nome
    spec = importlib.util.spec_from_file_location(nome.removesuffix(".py").replace("-", "_"), caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo

def ocupado():
    trava = raiz / ".publicacao.lock"
    assert os.fstat(8).st_ino == trava.stat().st_ino
    assert subprocess.run(
        ["flock", "--nonblock", "--exclusive", str(trava), "-c", "true"],
        check=False,
    ).returncode == 1

antigo = os.open(raiz / "outro.lock", os.O_RDONLY)
os.dup2(antigo, 8)
if antigo != 8:
    os.close(antigo)
inode_antigo = os.fstat(8).st_ino
for nome, invocar in (
    ("ativar-appmax-canario.py", lambda m: m.executar(raiz, site, ligar=False, gravar=True)),
    ("ativar-appmax-meshcraft-sandbox.py", lambda m: m.executar(raiz, False)),
    ("drill-appmax-rollback-sandbox.py", lambda m: m.executar(raiz)),
):
    modulo = carregar(nome)
    def falha_e_recuperacao(*args, **kwargs):
        ocupado()
        try:
            raise RuntimeError("falha simulada")
        except RuntimeError:
            ocupado()
            raise
    modulo._executar = falha_e_recuperacao
    try:
        invocar(modulo)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a falha simulada não saiu do caminho crítico")
    assert os.fstat(8).st_ino == inode_antigo
    assert subprocess.run(
        ["flock", "--nonblock", "--exclusive", str(raiz / ".publicacao.lock"), "-c", "true"],
        check=False,
    ).returncode == 0
print("fd8-recuperacao-confirmada")
PY
    """
    processo = executar_linux(codigo, tmp_path)
    assert processo.returncode == 0, (processo.stdout, processo.stderr)
    assert "fd8-recuperacao-confirmada" in processo.stdout


def test_python_recusa_trava_que_nao_e_arquivo_regular(tmp_path):
    shutil.copy2(RAIZ / "infra/ativar-appmax-canario.py", tmp_path / "ativar-appmax-canario.py")
    (tmp_path / "docker-compose.yml").touch()
    (tmp_path / ".publicacao.lock").mkdir()
    codigo = r"""
    if python3 "$PLATAFORMA_DIR/ativar-appmax-canario.py" --site cc06b8c3-043b-4c06-92c5-5ea624e00586 --desligar --executar > "$PLATAFORMA_DIR/resultado"; then exit 10; fi
    grep -q 'não é um arquivo regular' "$PLATAFORMA_DIR/resultado"
    echo trava-invalida-recusada
    """
    processo = executar_linux(codigo, tmp_path)
    assert processo.returncode == 0, (processo.stdout, processo.stderr)
    assert "trava-invalida-recusada" in processo.stdout
