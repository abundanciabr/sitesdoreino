import io
import json
import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "consultar-transicao-coordenacao-na-vps.sh"
)


def test_receptor_so_imprime_estado_estrito_e_confere_nonce(monkeypatch, capsys):
    import urllib.request

    corpo = (
        SCRIPT.read_text(encoding="utf-8").split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    )
    for chave, valor in {
        "COORTE": "piloto",
        "TRANSICAO": "tentativa-1",
        "FASE": "preparada",
        "NONCE": "a" * 32,
        "COORDENACAO_TRANSICIONADOR_TOKEN": "segredo-que-nao-sai",
    }.items():
        monkeypatch.setenv(chave, valor)

    class Resposta(io.BytesIO):
        status = 200

    resultado = {
        "coorte": "piloto",
        "epoca_atual": 1,
        "epoca": 2,
        "transicao": "tentativa-1",
        "pausada": True,
        "concessoes_invalidas": True,
        "watermark_sha256": "b" * 64,
        "autoridade_sha256": "c" * 64,
        "fase": "preparada",
        "nonce": "a" * 32,
    }

    def responder(req, timeout):
        assert req.full_url == "http://127.0.0.1:8000/interno/coordenacao/epocas"
        assert json.loads(req.data)["nonce"] == "a" * 32
        assert req.get_header("Authorization") == "Bearer segredo-que-nao-sai"
        return Resposta(json.dumps({"estado": "PASS", "resultado": resultado}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", responder)
    exec(compile(corpo, str(SCRIPT), "exec"), {"__name__": "__main__"})
    assert json.loads(capsys.readouterr().out) == resultado
    resultado["nonce"] = "d" * 32
    with pytest.raises(SystemExit) as erro:
        exec(compile(corpo, str(SCRIPT), "exec"), {"__name__": "__main__"})
    assert erro.value.code == 1
    saida = capsys.readouterr()
    assert "divergiu" in saida.err
    assert "segredo-que-nao-sai" not in saida.out + saida.err


@pytest.mark.skipif(os.name == "nt", reason="flock e bash da VPS são POSIX")
def test_receptor_usa_mesmo_fd8_para_consultas_concorrentes(tmp_path):
    plataforma = tmp_path / "plataforma"
    (plataforma / "env").mkdir(parents=True)
    (plataforma / "env" / "admin.env").write_text("", encoding="utf-8")
    binarios = tmp_path / "bin"
    binarios.mkdir()
    log = tmp_path / "ordem.txt"
    docker = binarios / "docker"
    docker.write_text(
        '#!/bin/sh\necho inicio >>"$TEST_LOG"\ncat >/dev/null\nsleep 0.2\necho fim >>"$TEST_LOG"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    ambiente = {
        **os.environ,
        "PATH": str(binarios) + os.pathsep + os.environ["PATH"],
        "PLATAFORMA_DIR": str(plataforma),
        "TEST_LOG": str(log),
        "COORTE": "piloto",
        "TRANSICAO": "tentativa-1",
        "FASE": "preparada",
        "NONCE": "a" * 32,
    }
    primeiro = subprocess.Popen(
        ["bash", str(SCRIPT)],
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    segundo = subprocess.Popen(
        ["bash", str(SCRIPT)],
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert primeiro.communicate(timeout=10)[0] == b""
    assert segundo.communicate(timeout=10)[0] == b""
    assert primeiro.returncode == segundo.returncode == 0
    assert log.read_text(encoding="utf-8").splitlines() == [
        "inicio",
        "fim",
        "inicio",
        "fim",
    ]
