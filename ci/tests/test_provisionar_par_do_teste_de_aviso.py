"""O script do botão de teste não pode dizer PRONTO se o reinício falhar."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-par-do-teste-de-aviso.sh"


@pytest.mark.skipif(
    BASH is None,
    reason="sem bash nesta máquina — o guarda não tem como medir",
)
def test_falha_do_reinicio_deixa_o_script_com_erro(tmp_path):
    bash = BASH
    assert bash is not None

    plataforma = tmp_path / "plataforma"
    (plataforma / "env").mkdir(parents=True)
    (plataforma / "env" / "notificacoes.env").write_text(
        "DJANGO_SECRET_KEY=x\n", encoding="utf-8"
    )
    (plataforma / "env" / "admin.env").write_text(
        "DJANGO_SECRET_KEY=y\n", encoding="utf-8"
    )

    binarios = tmp_path / "bin"
    binarios.mkdir()
    docker = binarios / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n" "exit 37\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    ambiente = {
        **os.environ,
        "PLATAFORMA_DIR": str(plataforma),
        "PATH": f"{binarios}{os.pathsep}{os.environ['PATH']}",
    }
    resultado = subprocess.run(
        [bash, str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
        stdin=subprocess.DEVNULL,
    )

    assert resultado.returncode != 0
    assert "reinicio das celulas FALHOU" in resultado.stdout
    assert "PRONTO" not in resultado.stdout
