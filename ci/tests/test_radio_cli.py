import runpy
import sys
from pathlib import Path
from urllib.request import OpenerDirector

import pytest


@pytest.mark.parametrize(
    "argumentos",
    [[], ["--help"], ["ler"], ["ler", "--desde", "3"],
     ["dizer", "oi", "--autor", "codex"],
     ["dizer", "oi", "--quem", "fila", "--tipo", "boletim", "--tarefa", "TAR-001"],
     ["comando-invalido"]],
)
@pytest.mark.parametrize("configurado", [False, True])
def test_cli_encerrada_recusa_sem_acessar_rede(
    argumentos, configurado, monkeypatch, tmp_path, capsys
):
    # guarda: ci/radio.py:11
    def rede_proibida(*args, **kwargs):
        pytest.fail("O comando encerrado tentou acessar a rede")

    monkeypatch.setattr(OpenerDirector, "open", rede_proibida)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    if configurado:
        monkeypatch.setenv("ADMIN_RADIO_URL", "http://admin.invalid")
        monkeypatch.setenv("ADMIN_RADIO_TOKEN", "token-de-teste")
    else:
        monkeypatch.delenv("ADMIN_RADIO_URL", raising=False)
        monkeypatch.delenv("ADMIN_RADIO_TOKEN", raising=False)
    caminho = Path(__file__).parents[1] / "radio.py"
    monkeypatch.setattr(sys, "argv", [str(caminho), *argumentos])
    with pytest.raises(SystemExit) as saida:
        runpy.run_path(str(caminho), run_name="__main__")
    assert saida.value.code == 2
    capturado = capsys.readouterr()
    assert capturado.out == ""
    assert "encerrado" in capturado.err
    assert "Remova" in capturado.err
    assert "token-de-teste" not in capturado.err
