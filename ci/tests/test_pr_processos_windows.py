"""Guardas novas específicas do sistema operacional da validação."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ci'))
import pr


def test_windows_limites_do_job_seguem_layout_oficial():
    from pr_processos_windows import LimitesBasicosJob, LimitesEstendidosJob

    nomes = [nome for nome, _tipo in LimitesBasicosJob._fields_]
    assert nomes == [
        'per_process_user_time_limit',
        'per_job_user_time_limit',
        'limit_flags',
        'minimum_working_set_size',
        'maximum_working_set_size',
        'active_process_limit',
        'affinity',
        'priority_class',
        'scheduling_class',
    ]
    assert LimitesEstendidosJob._fields_[0][1] is LimitesBasicosJob


@pytest.mark.skipif(sys.platform != 'win32', reason='API Job Object do Windows')
@pytest.mark.parametrize('codigo', [0, 7, 259, 0xF0000001])
def test_windows_preserva_returncode_dword(tmp_path, codigo):
    import os
    from pr_processos_windows import GrupoWindows

    grupo = GrupoWindows()
    try:
        processo = grupo.iniciar(
            [sys.executable, '-c', f'import ctypes;ctypes.windll.kernel32.ExitProcess({codigo})'],
            tmp_path,
            {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'},
        )
        stdout, stderr = processo.communicate(timeout=5)
        assert stdout == ''
        assert stderr == ''
        assert processo.returncode == codigo
        assert processo.poll() == codigo
    finally:
        grupo.encerrar()


@pytest.mark.skipif(sys.platform != 'win32', reason='API Job Object do Windows')
def test_windows_morte_durante_janela_de_associacao_nao_deixa_filho(tmp_path):
    import ctypes
    import subprocess
    import time
    from ctypes import wintypes

    def ativo(pid):
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            codigo = wintypes.DWORD()
            if not api.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                raise ctypes.WinError(ctypes.get_last_error())
            return codigo.value == 259
        finally:
            api.CloseHandle(handle)

    ci = Path(__file__).resolve().parents[1]
    filho = "from pathlib import Path;import os,time;Path('filho.pid').write_text(str(os.getpid()));time.sleep(60)"
    executor = f"""
import sys
import time
from pathlib import Path
sys.path.insert(0, {str(ci)!r})
import pr
from pr_processos_windows import GrupoWindows
def janela(self, processo):
    Path('janela.pid').write_text(str(processo.pid))
    time.sleep(60)
GrupoWindows.associar_e_iniciar = janela
pr.rodar([sys.executable, '-c', {filho!r}], Path({str(tmp_path)!r}), log=Path({str(tmp_path)!r})/'executor.log', prazo_segundos=60)
"""
    processo = subprocess.Popen([sys.executable, '-c', executor], cwd=tmp_path)
    try:
        limite = time.monotonic() + 8
        while not (tmp_path/'filho.pid').exists() and not (tmp_path/'janela.pid').exists():
            assert processo.poll() is None
            assert time.monotonic() < limite
            time.sleep(.02)
        pid = int(((tmp_path/'janela.pid') if (tmp_path/'janela.pid').exists() else (tmp_path/'filho.pid')).read_text())
        processo.kill()
        processo.wait(timeout=5)
        limite = time.monotonic() + 5
        while time.monotonic() < limite and ativo(pid):
            time.sleep(.02)
        assert not ativo(pid)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=5)


@pytest.mark.skipif(sys.platform != 'win32', reason='API Job Object do Windows')
def test_windows_morte_do_executor_fecha_pai_filho_e_neto(tmp_path):
    import ctypes
    import subprocess
    import time
    from ctypes import wintypes

    def ativo(pid):
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetExitCodeProcess.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            codigo = wintypes.DWORD()
            if not api.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                raise ctypes.WinError(ctypes.get_last_error())
            return codigo.value == 259
        finally:
            api.CloseHandle(handle)

    ci = Path(__file__).resolve().parents[1]
    neto = "from pathlib import Path;import os,time;Path('neto.pid').write_text(str(os.getpid()));time.sleep(60)"
    filho = (
        "import subprocess,sys,time;from pathlib import Path;"
        f"subprocess.Popen([sys.executable, '-c', {neto!r}], cwd=Path.cwd());"
        "Path('filho.pid').write_text(str(__import__('os').getpid()));time.sleep(60)"
    )
    executor = (
        "import sys;from pathlib import Path;"
        f"sys.path.insert(0, {str(ci)!r});import pr;"
        f"pr.rodar([sys.executable, '-c', {filho!r}], Path({str(tmp_path)!r}), "
        f"log=Path({str(tmp_path)!r})/'executor.log', prazo_segundos=60)"
    )
    processo = subprocess.Popen([sys.executable, '-c', executor], cwd=tmp_path)
    try:
        limite = time.monotonic() + 8
        while not (tmp_path/'filho.pid').exists() or not (tmp_path/'neto.pid').exists():
            assert processo.poll() is None
            assert time.monotonic() < limite
            time.sleep(.02)
        filho_pid = int((tmp_path/'filho.pid').read_text())
        neto_pid = int((tmp_path/'neto.pid').read_text())
        processo.kill()
        processo.wait(timeout=5)
        limite = time.monotonic() + 5
        while time.monotonic() < limite and (ativo(filho_pid) or ativo(neto_pid)):
            time.sleep(.02)
        assert not ativo(filho_pid)
        assert not ativo(neto_pid)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=5)
