"""Adota e encerra descendentes da validação, mesmo após setsid ou double fork."""

import ctypes
import os
import signal
import sys
import threading
import time
from pathlib import Path

TRAVA = threading.Lock()


class GrupoLinux:
    def __init__(self):
        if sys.platform != 'linux':
            raise OSError('Contenção de validação disponível em Windows e Linux; execute ci/pr.py em um desses ambientes.')
        if not TRAVA.acquire(blocking=False):
            raise OSError('Já há uma validação neste processo; execute ci/pr.py em processo separado.')
        try:
            self._preparar()
        except BaseException:
            TRAVA.release()
            raise

    def _preparar(self):
        self.tarefas = Path(f'/proc/{os.getpid()}/task')
        if not self.tarefas.is_dir() or self._filhos():
            raise OSError('A validação exige /proc acessível e processo sem outros filhos; execute ci/pr.py em processo separado.')
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        self.libc.prctl.restype = ctypes.c_int
        anterior = ctypes.c_int()
        self._prctl(37, ctypes.addressof(anterior))
        self.anterior = anterior.value
        self._prctl(36, 1)
        self.processo = None
        self.fechado = False

    def _prctl(self, operacao, valor):
        if self.libc.prctl(operacao, valor, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'Não foi possível configurar a adoção dos processos órfãos da validação.')

    def _filhos(self):
        filhos = set()
        leituras = 0
        for tarefa in self.tarefas.iterdir():
            try:
                filhos.update(map(int, (tarefa/'children').read_text().split()))
                leituras += 1
            except FileNotFoundError:
                pass  # A thread pode terminar entre a listagem e a leitura.
        if not leituras:
            raise OSError('O /proc não informou os descendentes; execute a validação com /proc acessível.')
        return filhos

    def associar_e_iniciar(self, processo):
        self.processo = processo

    def encerrar(self):
        if self.fechado:
            return
        try:
            # Matar o pai entrega seus filhos ao subreaper; repetir alcança
            # também netos que mudaram de sessão ou perderam os pais cedo.
            if self.processo is not None:
                if self.processo.poll() is None:
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
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
                if time.monotonic() >= limite:
                    raise OSError('O Linux não confirmou o encerramento dos descendentes em 5 segundos.')
                time.sleep(.01)
        finally:
            try:
                self._prctl(36, self.anterior)
            finally:
                self.fechado = True
                TRAVA.release()
