"""Supervisiona a validação Linux para não deixar descendentes órfãos."""

from __future__ import annotations

import ctypes
import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

TRAVA = threading.Lock()
PR_GET_CHILD_SUBREAPER = 37
PR_SET_CHILD_SUBREAPER = 36


class GrupoLinux:
    def __init__(self):
        if sys.platform != "linux":
            raise OSError("Contenção de validação disponível em Windows e Linux; execute ci/pr.py em um desses ambientes.")
        if not TRAVA.acquire(blocking=False):
            raise OSError("Já há uma validação neste processo; execute ci/pr.py em processo separado.")
        self.tarefas = Path(f"/proc/{os.getpid()}/task")
        try:
            if not self.tarefas.is_dir() or self._filhos():
                raise OSError("A validação exige /proc acessível e processo sem outros filhos; execute ci/pr.py em processo separado.")
        except BaseException:
            TRAVA.release()
            raise
        self._vivo_leitura = None
        self._vivo_escrita = None
        self.processo = None
        self.fechado = False

    def _filhos(self):
        return _filhos_do_processo(self.tarefas)

    def iniciar(self, comando, raiz, ambiente):
        leitura, escrita = os.pipe()
        os.set_inheritable(leitura, True)
        try:
            supervisor = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--supervisionar",
                    str(leitura),
                    json.dumps(comando),
                ],
                cwd=raiz,
                env=ambiente,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                pass_fds=(leitura,),
                start_new_session=True,
            )
        finally:
            os.close(leitura)
        self._vivo_escrita = escrita
        self.processo = supervisor
        return supervisor

    def associar_e_iniciar(self, processo):
        self.processo = processo

    def encerrar(self):
        if self.fechado:
            return
        try:
            if self._vivo_escrita is not None:
                os.close(self._vivo_escrita)
                self._vivo_escrita = None
            if self.processo is not None and self.processo.poll() is None:
                limite = time.monotonic() + 5
                while self.processo.poll() is None and time.monotonic() < limite:
                    time.sleep(0.01)
                if self.processo.poll() is None:
                    self.processo.kill()
                    self.processo.wait(timeout=5)
        finally:
            self.fechado = True
            TRAVA.release()


class SupervisorLinux:
    def __init__(self, vivo_leitura):
        self.tarefas = Path(f"/proc/{os.getpid()}/task")
        if not self.tarefas.is_dir() or self._filhos():
            raise OSError("A validação exige /proc acessível e supervisor sem outros filhos.")
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        self.libc.prctl.restype = ctypes.c_int
        anterior = ctypes.c_int()
        self._prctl(PR_GET_CHILD_SUBREAPER, ctypes.addressof(anterior))
        self.anterior = anterior.value
        self._prctl(PR_SET_CHILD_SUBREAPER, 1)
        self.vivo_leitura = vivo_leitura
        self.processo = None

    def _prctl(self, operacao, valor):
        if self.libc.prctl(operacao, valor, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "Não foi possível configurar a adoção dos processos órfãos da validação.")

    def _filhos(self):
        return _filhos_do_processo(self.tarefas)

    def executar(self, comando):
        limpeza_feita = False
        try:
            self.processo = subprocess.Popen(
                comando,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            stdout_fechado = threading.Event()
            stderr_fechado = threading.Event()
            threading.Thread(
                target=_repassar_pipe,
                args=(self.processo.stdout, sys.stdout.buffer, stdout_fechado),
                daemon=True,
            ).start()
            threading.Thread(
                target=_repassar_pipe,
                args=(self.processo.stderr, sys.stderr.buffer, stderr_fechado),
                daemon=True,
            ).start()
            while self.processo.poll() is None:
                leitura, _, _ = select.select([self.vivo_leitura], [], [], 0.05)
                if leitura and os.read(self.vivo_leitura, 1) == b"":
                    self._encerrar_arvore()
                    limpeza_feita = True
                    return 124
            while not stdout_fechado.is_set() or not stderr_fechado.is_set():
                leitura, _, _ = select.select([self.vivo_leitura], [], [], 0.05)
                if leitura and os.read(self.vivo_leitura, 1) == b"":
                    self._encerrar_arvore()
                    limpeza_feita = True
                    return 124
            codigo = self.processo.returncode
            self._encerrar_arvore()
            limpeza_feita = True
            return codigo
        except BaseException:
            if not limpeza_feita:
                self._encerrar_arvore()
            raise
        finally:
            try:
                os.close(self.vivo_leitura)
            except OSError:
                pass
            self._prctl(PR_SET_CHILD_SUBREAPER, self.anterior)

    def _encerrar_arvore(self):
        if self.processo is not None and self.processo.poll() is None:
            self.processo.kill()
            self.processo.wait(timeout=5)
        limite = time.monotonic() + 5
        while filhos := self._filhos():
            for pid in filhos:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
            if time.monotonic() >= limite:
                raise OSError("O Linux não confirmou o encerramento dos descendentes em 5 segundos.")
            time.sleep(0.01)


def _supervisionar():
    leitura = int(sys.argv[2])
    comando = json.loads(sys.argv[3])
    codigo = SupervisorLinux(leitura).executar(comando)
    if codigo < 0:
        sinal = -codigo
        signal.signal(sinal, signal.SIG_DFL)
        os.kill(os.getpid(), sinal)
    return codigo


def _filhos_do_processo(tarefas):
    filhos = set()
    leituras = 0
    for tarefa in tarefas.iterdir():
        try:
            filhos.update(map(int, (tarefa / "children").read_text().split()))
            leituras += 1
        except FileNotFoundError:
            pass
    if not leituras:
        raise OSError("O /proc não informou os descendentes; execute a validação com /proc acessível.")
    return filhos


def _repassar_pipe(origem, destino, concluido):
    try:
        while True:
            bloco = origem.read(8192)
            if not bloco:
                return
            destino.write(bloco)
            destino.flush()
    finally:
        origem.close()
        concluido.set()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--supervisionar":
        raise SystemExit(_supervisionar())
