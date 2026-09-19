"""Contém os processos da validação antes de liberar sua execução no Windows."""

import ctypes
import time
from ctypes import wintypes


class ThreadEntry(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
        ('th32ThreadID', wintypes.DWORD), ('th32OwnerProcessID', wintypes.DWORD),
        ('tpBasePri', wintypes.LONG), ('tpDeltaPri', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
    ]


class Contabilidade(ctypes.Structure):
    _fields_ = [
        ('tempos', ctypes.c_longlong * 4),
        ('faltas_de_pagina', wintypes.DWORD), ('total', wintypes.DWORD),
        ('ativos', wintypes.DWORD), ('encerrados', wintypes.DWORD),
    ]


class GrupoWindows:
    def __init__(self):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        H, D, B = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
        assinaturas = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], H),
            'OpenProcess': ([D, B, D], H),
            'AssignProcessToJobObject': ([H, H], B),
            'TerminateJobObject': ([H, wintypes.UINT], B),
            'QueryInformationJobObject': ([H, ctypes.c_int, ctypes.c_void_p, D, ctypes.c_void_p], B),
            'CreateToolhelp32Snapshot': ([D, D], H),
            'Thread32First': ([H, ctypes.POINTER(ThreadEntry)], B),
            'Thread32Next': ([H, ctypes.POINTER(ThreadEntry)], B),
            'OpenThread': ([D, B, D], H),
            'ResumeThread': ([H], D),
            'CloseHandle': ([H], B),
        }
        for nome, (argumentos, retorno) in assinaturas.items():
            funcao = getattr(self.api, nome)
            funcao.argtypes, funcao.restype = argumentos, retorno
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def associar_e_iniciar(self, processo):
        # O Popen criou o processo com CREATE_SUSPENDED. Nenhum filho pode
        # nascer antes da associação, nem escapar se o pai terminar cedo.
        handle = self.api.OpenProcess(0x0101, False, processo.pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(handle)
        snapshot = self.api.CreateToolhelp32Snapshot(0x00000004, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entrada = ThreadEntry()
            entrada.dwSize = ctypes.sizeof(entrada)
            existe = self.api.Thread32First(snapshot, ctypes.byref(entrada))
            while existe:
                if entrada.th32OwnerProcessID == processo.pid:
                    thread = self.api.OpenThread(0x0002, False, entrada.th32ThreadID)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        self.api.CloseHandle(thread)
                existe = self.api.Thread32Next(snapshot, ctypes.byref(entrada))
            raise OSError('A thread da validação suspensa não foi encontrada.')
        finally:
            self.api.CloseHandle(snapshot)

    def encerrar(self):
        if self.handle is None:
            return
        try:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            limite = time.monotonic() + 5
            dados = Contabilidade()
            while True:
                if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(dados), ctypes.sizeof(dados), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if dados.ativos == 0:
                    break
                if time.monotonic() >= limite:
                    raise OSError('O Windows não confirmou o encerramento dos processos em 5 segundos.')
                time.sleep(.01)
        finally:
            self.api.CloseHandle(self.handle)
            self.handle = None
