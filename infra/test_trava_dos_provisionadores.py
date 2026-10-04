"""Provas locais: recarregar contêiner à mão usa a mesma trava do publicador."""
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

INFRA = Path(__file__).parent
OPERACAO = INFRA / "operacao-aplicacao.sh"
BASH = shutil.which("bash")
FLOCK = shutil.which("flock")


def test_trava_e_o_mesmo_arquivo_do_publicador():
    publicar = (INFRA / "publicar.py").read_text(encoding="utf-8")
    assert 'LOTES = PUBLICACOES / "lotes"' in publicar
    assert '(LOTES / ".lote.lock").open("a")' in publicar
    assert "publicacoes/lotes/.lote.lock" in OPERACAO.read_text(encoding="utf-8")


def test_provisionador_so_recria_conteiner_por_recarregar_servicos():
    # recarregar-aplicacao.py é quem recria; todo provisionador chega nele por recarregar_servicos.
    for roteiro in INFRA.glob("provisionar-*.sh"):
        for numero, linha in enumerate(roteiro.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            assert not re.search(r"recarregar-aplicacao\.py|compose\s+up\b[^#]*--force-recreate", linha), (roteiro.name, numero)


@pytest.mark.skipif(not (BASH and FLOCK), reason="precisa de bash e flock (só existem na VPS/Linux)")
def test_recarregar_espera_a_publicacao_terminar(tmp_path):
    raiz = tmp_path / "plataforma"
    lotes = raiz / "publicacoes" / "lotes"
    lotes.mkdir(parents=True)
    falso = tmp_path / "bin"
    falso.mkdir()
    marca = tmp_path / "recarregou"
    (falso / "python3").write_text(f"#!/bin/sh\ntouch '{marca}'\n", encoding="utf-8")
    (falso / "python3").chmod(0o755)
    publicando = subprocess.Popen([FLOCK, str(lotes / ".lote.lock"), "sleep", "2"])
    time.sleep(0.5)
    inicio = time.monotonic()
    processo = subprocess.run(
        [BASH, "-c", f". '{OPERACAO}'; recarregar_servicos provisionar-admin.sh"],
        env={"PATH": f"{falso}:/usr/bin:/bin", "PLATAFORMA_DIR": str(raiz)},
        capture_output=True, text=True, timeout=30,
    )
    esperou = time.monotonic() - inicio
    publicando.wait()
    assert processo.returncode == 0, processo.stderr
    assert "publicação em andamento" in processo.stdout
    assert esperou >= 1.0
    assert marca.exists()
