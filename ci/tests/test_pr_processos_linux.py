"""Guardas novas específicas do sistema operacional da validação."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ci'))
import pr


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
@pytest.mark.parametrize('anterior', [0, 1])
def test_linux_restaura_adocao_e_recusa_concorrencia(tmp_path, anterior):
    import ctypes
    from pr_processos_linux import GrupoLinux
    libc = ctypes.CDLL(None)
    original = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(original), 0, 0, 0) == 0
    try:
        assert libc.prctl(36, anterior, 0, 0, 0) == 0
        grupo = GrupoLinux()
        try:
            with pytest.raises(OSError, match='Já há uma validação'):
                GrupoLinux()
        finally:
            grupo.encerrar()
        atual = ctypes.c_int()
        assert libc.prctl(37, ctypes.byref(atual), 0, 0, 0) == 0
        assert atual.value == anterior
        pr.rodar([sys.executable, '-c', "print('aprovado')"], tmp_path, log=tmp_path/'ok.log', prazo_segundos=1)
        assert libc.prctl(37, ctypes.byref(atual), 0, 0, 0) == 0
        assert atual.value == anterior
    finally:
        assert libc.prctl(36, original.value, 0, 0, 0) == 0


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_preserva_filho_preexistente(tmp_path):
    import subprocess
    filho = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
    try:
        with pytest.raises(pr.ErroDeInstrumentacao):
            pr.rodar([sys.executable, '-c', "print('não executar')"], tmp_path, log=tmp_path/'error.log', prazo_segundos=1)
        assert filho.poll() is None
        assert 'ERROR' in (tmp_path/'error.log').read_text(encoding='utf-8')
        assert 'processo sem outros filhos' in (tmp_path/'error.log').read_text(encoding='utf-8')
    finally:
        filho.kill()
        filho.wait(timeout=5)


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_recolhe_filho_desanexado_apos_sucesso_do_pai(tmp_path):
    import os
    import signal
    filho = "import os,time;from pathlib import Path;Path('pid-filho').write_text(str(os.getpid()));time.sleep(60)"
    pai = f'''import subprocess,sys,time
from pathlib import Path
subprocess.Popen([sys.executable, '-c', {filho!r}], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
limite = time.monotonic() + 3
while not Path('pid-filho').exists() or not Path('pid-filho').read_text():
    if time.monotonic() > limite: raise SystemExit(1)
    time.sleep(.01)
print('pai concluído')
'''
    try:
        assert 'pai concluído' in pr.rodar([sys.executable, '-c', pai], tmp_path, log=tmp_path/'ok.log', prazo_segundos=5)
        pid = int((tmp_path/'pid-filho').read_text())
        assert not Path(f'/proc/{pid}').exists(), 'filho órfão continua executando ou sem recolhimento'
    finally:
        caminho = tmp_path/'pid-filho'
        if caminho.exists():
            try:
                os.kill(int(caminho.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_nao_confunde_proc_indisponivel_com_ausencia_de_filhos(tmp_path):
    from pr_processos_linux import GrupoLinux
    grupo = object.__new__(GrupoLinux)
    grupo.tarefas = tmp_path
    with pytest.raises(OSError, match='não informou os descendentes'):
        grupo._filhos()
