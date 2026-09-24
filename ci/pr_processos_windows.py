"""Cria a validação já associada ao Job Object no Windows."""

from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x00000001
STILL_ACTIVE = 259


class SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


class StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", StartupInfo),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class ProcessInformation(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class Contabilidade(ctypes.Structure):
    _fields_ = [
        ("total_user_time", ctypes.c_longlong),
        ("total_kernel_time", ctypes.c_longlong),
        ("this_period_total_user_time", ctypes.c_longlong),
        ("this_period_total_kernel_time", ctypes.c_longlong),
        ("total_page_fault_count", wintypes.DWORD),
        ("total_processes", wintypes.DWORD),
        ("active_processes", wintypes.DWORD),
        ("total_terminated_processes", wintypes.DWORD),
    ]


class LimitesBasicosJob(ctypes.Structure):
    _fields_ = [
        ("per_process_user_time_limit", ctypes.c_longlong),
        ("per_job_user_time_limit", ctypes.c_longlong),
        ("limit_flags", wintypes.DWORD),
        ("minimum_working_set_size", ctypes.c_size_t),
        ("maximum_working_set_size", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority_class", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class ContadoresDeEntradaSaida(ctypes.Structure):
    _fields_ = [
        ("read_operation_count", ctypes.c_ulonglong),
        ("write_operation_count", ctypes.c_ulonglong),
        ("other_operation_count", ctypes.c_ulonglong),
        ("read_transfer_count", ctypes.c_ulonglong),
        ("write_transfer_count", ctypes.c_ulonglong),
        ("other_transfer_count", ctypes.c_ulonglong),
    ]


class LimitesEstendidosJob(ctypes.Structure):
    _fields_ = [
        ("basic_limit_information", LimitesBasicosJob),
        ("io_info", ContadoresDeEntradaSaida),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory_used", ctypes.c_size_t),
        ("peak_job_memory_used", ctypes.c_size_t),
    ]


class ProcessoWindows:
    def __init__(self, api, handle, pid, stdout_leitura, stderr_leitura):
        self.api = api
        self.handle = handle
        self.pid = pid
        self.returncode = None
        self._stdout = []
        self._stderr = []
        self._stdout_thread = threading.Thread(target=self._ler_pipe, args=(stdout_leitura, self._stdout), daemon=True)
        self._stderr_thread = threading.Thread(target=self._ler_pipe, args=(stderr_leitura, self._stderr), daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _ler_pipe(self, handle, destino):
        import msvcrt

        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        with os.fdopen(fd, "rb") as origem:
            while True:
                bloco = origem.read(8192)
                if not bloco:
                    return
                destino.append(bloco)

    def _saida(self, partes):
        return b"".join(partes).decode("utf-8", errors="replace")

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        estado = self.api.WaitForSingleObject(self.handle, 0)
        if estado == 258:
            return None
        if estado != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        codigo = wintypes.DWORD()
        if not self.api.GetExitCodeProcess(self.handle, ctypes.byref(codigo)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.returncode = codigo.value
        return self.returncode

    def wait(self, timeout=None):
        if timeout is None:
            espera = 0xFFFFFFFF
        else:
            espera = max(0, int(timeout * 1000))
        resultado = self.api.WaitForSingleObject(self.handle, espera)
        if resultado == 258:
            raise subprocess.TimeoutExpired(None, timeout, self._saida(self._stdout), self._saida(self._stderr))
        if resultado != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.poll()

    def communicate(self, input=None, timeout=None):
        if input is not None:
            raise ValueError("stdin da validação é fechado")
        limite = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if limite is not None and time.monotonic() >= limite:
                raise subprocess.TimeoutExpired(None, timeout, self._saida(self._stdout), self._saida(self._stderr))
            restante = 0.05 if limite is None else min(0.05, max(0, limite - time.monotonic()))
            resultado = self.api.WaitForSingleObject(self.handle, int(restante * 1000))
            if resultado == 258:
                continue
            if resultado != 0:
                raise ctypes.WinError(ctypes.get_last_error())
            self.poll()
        for thread in (self._stdout_thread, self._stderr_thread):
            restante = None if limite is None else max(0, limite - time.monotonic())
            thread.join(restante)
            if thread.is_alive():
                raise subprocess.TimeoutExpired(None, timeout, self._saida(self._stdout), self._saida(self._stderr))
        return self._saida(self._stdout), self._saida(self._stderr)

    def kill(self):
        if self.poll() is None and not self.api.TerminateProcess(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())


class GrupoWindows:
    def __init__(self):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self._assinar_api()
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limites = LimitesEstendidosJob()
            limites.basic_limit_information.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(
                self.handle,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limites),
                ctypes.sizeof(limites),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.api.CloseHandle(self.handle)
            self.handle = None
            raise

    def _assinar_api(self):
        H, D, B = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
        assinaturas = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], H),
            "SetInformationJobObject": ([H, ctypes.c_int, ctypes.c_void_p, D], B),
            "TerminateJobObject": ([H, wintypes.UINT], B),
            "QueryInformationJobObject": ([H, ctypes.c_int, ctypes.c_void_p, D, ctypes.c_void_p], B),
            "InitializeProcThreadAttributeList": ([ctypes.c_void_p, D, D, ctypes.POINTER(ctypes.c_size_t)], B),
            "UpdateProcThreadAttribute": ([ctypes.c_void_p, D, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p], B),
            "DeleteProcThreadAttributeList": ([ctypes.c_void_p], None),
            "CreatePipe": ([ctypes.POINTER(H), ctypes.POINTER(H), ctypes.POINTER(SecurityAttributes), D], B),
            "SetHandleInformation": ([H, D, D], B),
            "CreateFileW": ([wintypes.LPCWSTR, D, D, ctypes.c_void_p, D, D, H], H),
            "CreateProcessW": ([wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, B, D, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(StartupInfoEx), ctypes.POINTER(ProcessInformation)], B),
            "GetExitCodeProcess": ([H, ctypes.POINTER(D)], B),
            "WaitForSingleObject": ([H, D], D),
            "TerminateProcess": ([H, wintypes.UINT], B),
            "CloseHandle": ([H], B),
        }
        for nome, (argumentos, retorno) in assinaturas.items():
            funcao = getattr(self.api, nome)
            funcao.argtypes, funcao.restype = argumentos, retorno

    def iniciar(self, comando, raiz, ambiente):
        atributo = None
        info = ProcessInformation()
        stdin = stdout_leitura = stdout_escrita = stderr_leitura = stderr_escrita = None
        try:
            atributo, jobs = self._atributo_job()
            stdout_leitura, stdout_escrita = self._pipe()
            stderr_leitura, stderr_escrita = self._pipe()
            stdin = self._nul()
            inicio = StartupInfoEx()
            inicio.StartupInfo.cb = ctypes.sizeof(inicio)
            inicio.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            inicio.StartupInfo.hStdInput = stdin
            inicio.StartupInfo.hStdOutput = stdout_escrita
            inicio.StartupInfo.hStdError = stderr_escrita
            inicio.lpAttributeList = ctypes.cast(atributo, ctypes.c_void_p)
            linha = ctypes.create_unicode_buffer(subprocess.list2cmdline(comando))
            bloco_ambiente = ctypes.create_unicode_buffer(_bloco_de_ambiente(ambiente))
            if not self.api.CreateProcessW(
                None,
                linha,
                None,
                None,
                True,
                EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT,
                bloco_ambiente,
                str(raiz),
                ctypes.byref(inicio),
                ctypes.byref(info),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return ProcessoWindows(self.api, info.hProcess, info.dwProcessId, stdout_leitura, stderr_leitura)
        except BaseException:
            if info.hProcess:
                self.api.TerminateProcess(info.hProcess, 1)
                self.api.CloseHandle(info.hProcess)
            for handle in (stdout_leitura, stderr_leitura):
                if handle:
                    self.api.CloseHandle(handle)
            raise
        finally:
            for handle in (stdin, stdout_escrita, stderr_escrita):
                if handle:
                    self.api.CloseHandle(handle)
            if info.hThread:
                self.api.CloseHandle(info.hThread)
            if atributo is not None:
                self.api.DeleteProcThreadAttributeList(ctypes.cast(atributo, ctypes.c_void_p))

    def _atributo_job(self):
        tamanho = ctypes.c_size_t()
        self.api.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(tamanho))
        atributo = ctypes.create_string_buffer(tamanho.value)
        if not self.api.InitializeProcThreadAttributeList(atributo, 1, 0, ctypes.byref(tamanho)):
            raise ctypes.WinError(ctypes.get_last_error())
        jobs = (wintypes.HANDLE * 1)(self.handle)
        if not self.api.UpdateProcThreadAttribute(
            atributo,
            0,
            PROC_THREAD_ATTRIBUTE_JOB_LIST,
            jobs,
            ctypes.sizeof(jobs),
            None,
            None,
        ):
            erro = ctypes.WinError(ctypes.get_last_error())
            self.api.DeleteProcThreadAttributeList(ctypes.cast(atributo, ctypes.c_void_p))
            raise erro
        return atributo, jobs

    def _pipe(self):
        atributos = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, True)
        leitura = wintypes.HANDLE()
        escrita = wintypes.HANDLE()
        if not self.api.CreatePipe(ctypes.byref(leitura), ctypes.byref(escrita), ctypes.byref(atributos), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.api.SetHandleInformation(leitura, HANDLE_FLAG_INHERIT, 0):
            self.api.CloseHandle(leitura)
            self.api.CloseHandle(escrita)
            raise ctypes.WinError(ctypes.get_last_error())
        return leitura.value, escrita.value

    def _nul(self):
        atributos = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, True)
        handle = self.api.CreateFileW("NUL", 0x80000000, 0x00000001 | 0x00000002, ctypes.byref(atributos), 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def associar_e_iniciar(self, processo):
        raise OSError("Processos Windows são criados já associados ao Job Object.")

    def encerrar(self):
        if self.handle is None:
            return
        try:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            limite = time.monotonic() + 5
            dados = Contabilidade()
            while True:
                if not self.api.QueryInformationJobObject(
                    self.handle,
                    JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
                    ctypes.byref(dados),
                    ctypes.sizeof(dados),
                    None,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                if dados.active_processes == 0:
                    break
                if time.monotonic() >= limite:
                    raise OSError("O Windows não confirmou o encerramento dos processos em 5 segundos.")
                time.sleep(0.01)
        finally:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _bloco_de_ambiente(ambiente):
    pares = [f"{chave}={valor}" for chave, valor in sorted(ambiente.items()) if "\x00" not in chave and "\x00" not in valor]
    return "\0".join(pares) + "\0\0"
