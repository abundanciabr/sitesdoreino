import io
from unittest import mock
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


def _reg_espelho(candidata, base_candidata="c" * 40):
    return {"id": "1" * 12, "ramo": "codex/entrega/prova", "commit": "d" * 40,
            "base": "e" * 40, "origem": "codex", "estado": "pronta",
            "candidata": candidata, "base_da_candidata": base_candidata}


def _ambiente_espelho(tmp_path, novo, antigo):
    origem, destino = tmp_path / "origem", tmp_path / "plataforma"
    for raiz in (origem, destino):
        (raiz / "codigo/repo.git").mkdir(parents=True)
        (raiz / "entregas").mkdir()
    (origem / "entregas" / (novo["id"] + ".json")).write_text(json.dumps(novo), encoding="utf-8")
    (destino / "entregas" / (antigo["id"] + ".json")).write_text(json.dumps(antigo), encoding="utf-8")
    return ponte.Autoridade(origem=origem, plataforma=destino), destino


def test_espelho_aceita_candidata_recomposta_da_mesma_entrega(tmp_path, monkeypatch):
    anterior = _reg_espelho("a" * 40, "f" * 40)
    atual = _reg_espelho("b" * 40, "c" * 40)
    autoridade, destino = _ambiente_espelho(tmp_path, atual, anterior)
    def executar(comando, **_):
        return SimpleNamespace(returncode=0, stdout=atual["candidata"] + "\n"
                               if "rev-parse" in comando else "")
    monkeypatch.setattr(ponte.subprocess, "run", executar)
    assert autoridade.espelhar(atual["id"], atual["candidata"]) == {"ok": True, "estado": "pronta"}
    salvo = json.loads((destino / "entregas" / (atual["id"] + ".json")).read_text())
    assert salvo == atual


def test_espelho_recusa_pedido_de_candidata_desatualizada(tmp_path):
    atual = _reg_espelho("b" * 40)
    autoridade, _ = _ambiente_espelho(tmp_path, atual, _reg_espelho("a" * 40))
    with mock.patch.object(ponte.subprocess, "run") as executar:
        with pytest.raises(ponte.ErroPonte) as erro:
            autoridade.espelhar(atual["id"], "a" * 40)
        executar.assert_not_called()
    assert erro.value.diagnostico["codigo"] == "espelho_candidata_divergente"


@pytest.mark.parametrize("modificacao,codigo", [
    ({"base": "f" * 40}, "espelho_identidade_divergente"),
    ({"promocao": {"estado": "intencao", "candidata": "a" * 40}}, "espelho_promocao_protegida"),
    ({"estado": "integrada na main", "promovida_candidata": "a" * 40,
      "promocao": {"estado": "remota", "candidata": "a" * 40, "remoto": "integrador"}},
     "espelho_promocao_protegida"),
])
def test_espelho_recusa_identidade_ou_promocao_sem_fetch(tmp_path, monkeypatch, modificacao, codigo):
    anterior = _reg_espelho("a" * 40)
    anterior.update(modificacao)
    atual = _reg_espelho("b" * 40)
    autoridade, destino = _ambiente_espelho(tmp_path, atual, anterior)
    with mock.patch.object(ponte.subprocess, "run") as executar:
        with pytest.raises(ponte.ErroPonte) as erro:
            autoridade.espelhar(atual["id"], atual["candidata"])
        executar.assert_not_called()
    assert erro.value.diagnostico["codigo"] == codigo
    assert json.loads((destino / "entregas" / (atual["id"] + ".json")).read_text()) == anterior


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
