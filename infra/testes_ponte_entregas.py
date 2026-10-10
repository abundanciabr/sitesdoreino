import io
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ponte_entregas as ponte


PEDIDO = {"acao": "preparar", "id": "1" * 12, "candidata": "a" * 40,
          "celula": "aplicacao"}


def test_sigterm_na_preparacao_executa_limpeza_e_restaura_handler():
    anterior = signal.getsignal(signal.SIGTERM)
    eventos = []
    autoridade = ponte.Autoridade()

    def preparar(*_args):
        try:
            eventos.append("ensaio iniciado")
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        finally:
            eventos.append("contenedores removidos")

    autoridade.preparar = preparar
    with pytest.raises(ponte.PreparacaoInterrompida):
        autoridade.atender(PEDIDO)
    assert eventos == ["ensaio iniciado", "contenedores removidos"]
    assert signal.getsignal(signal.SIGTERM) == anterior

    autoridade.publicar = lambda *_args: ("publicacao", signal.getsignal(signal.SIGTERM))
    assert autoridade.atender({**PEDIDO, "acao": "publicar"}) == ("publicacao", anterior)


def test_servidor_fecha_conexao_sem_resposta_de_sucesso_apos_interrupcao(monkeypatch):
    class Conexao:
        fechada = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.fechada = True

        def getsockopt(self, *_args):
            return struct.pack("3i", 0, 1234, 0)

        def makefile(self, *_args):
            return io.BytesIO(json.dumps(PEDIDO).encode() + b"\n")

        def sendall(self, _dados):
            pytest.fail("interrupcao nao pode gerar resposta de sucesso")

    conexao = Conexao()
    servidor = SimpleNamespace(getsockname=lambda: "/run/ponte-teste.sock",
                              accept=lambda: (conexao, None))
    autoridade = ponte.Autoridade()
    autoridade.preparar = lambda *_args: signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    monkeypatch.setattr(ponte.sys, "platform", "linux")
    monkeypatch.setattr(ponte.socket, "fromfd", lambda *_args: servidor, raising=False)
    monkeypatch.setattr(ponte.socket, "AF_UNIX", 1, raising=False)
    monkeypatch.setattr(ponte.socket, "SO_PEERCRED", 17, raising=False)
    monkeypatch.setitem(sys.modules, "pwd", SimpleNamespace(
        getpwnam=lambda _usuario: SimpleNamespace(pw_uid=1234)))
    monkeypatch.setenv("LISTEN_FDS", "1")
    monkeypatch.setenv("LISTEN_PID", str(os.getpid()))

    assert ponte.servir(autoridade, esperado="/run/ponte-teste.sock") is None
    assert conexao.fechada


@pytest.mark.skipif(os.name != "posix", reason="sinais POSIX exigidos")
def test_sigterm_real_desempilha_finally_em_subprocesso(tmp_path):
    marcador = tmp_path / "limpeza.txt"
    codigo = """
import signal, sys, time
from pathlib import Path
import ponte_entregas as ponte
marcador = Path(sys.argv[1])
autoridade = ponte.Autoridade()
def preparar(*_args):
    try:
        marcador.write_text('iniciado', encoding='utf-8')
        time.sleep(30)
    finally:
        marcador.write_text('limpo', encoding='utf-8')
autoridade.preparar = preparar
try:
    autoridade.atender({'acao': 'preparar', 'id': '111111111111',
                        'candidata': 'a' * 40, 'celula': 'aplicacao'})
except ponte.PreparacaoInterrompida:
    pass
"""
    ambiente = {**os.environ, "PYTHONPATH": str(Path(ponte.__file__).parent)}
    processo = subprocess.Popen([sys.executable, "-c", codigo, str(marcador)], env=ambiente)
    try:
        limite = time.monotonic() + 5
        while not marcador.exists() and time.monotonic() < limite:
            time.sleep(0.01)
        assert marcador.read_text(encoding="utf-8") == "iniciado"
        processo.send_signal(signal.SIGTERM)
        assert processo.wait(timeout=5) == 0
        assert marcador.read_text(encoding="utf-8") == "limpo"
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=5)
