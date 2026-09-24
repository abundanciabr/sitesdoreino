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
def test_linux_morte_do_executor_fecha_pai_filho_e_neto(tmp_path):
    import os
    import signal
    import subprocess
    import time

    ci = Path(__file__).resolve().parents[1]
    neto = "import os,time;from pathlib import Path;Path('pid-neto').write_text(str(os.getpid()));time.sleep(60)"
    filho = (
        "import os,subprocess,sys,time;from pathlib import Path;"
        f"subprocess.Popen([sys.executable, '-c', {neto!r}], start_new_session=True);"
        "Path('pid-filho').write_text(str(os.getpid()));time.sleep(60)"
    )
    executor = (
        "import sys;from pathlib import Path;"
        f"sys.path.insert(0, {str(ci)!r});import pr;"
        f"pr.rodar([sys.executable, '-c', {filho!r}], Path({str(tmp_path)!r}), "
        f"log=Path({str(tmp_path)!r})/'executor.log', prazo_segundos=60)"
    )
    processo = subprocess.Popen([sys.executable, '-c', executor], cwd=tmp_path)
    filhos = []
    try:
        limite = time.monotonic() + 8
        while not (tmp_path/'pid-filho').exists() or not (tmp_path/'pid-neto').exists():
            assert processo.poll() is None
            assert time.monotonic() < limite
            time.sleep(.02)
        filhos = [int((tmp_path/'pid-filho').read_text()), int((tmp_path/'pid-neto').read_text())]
        processo.kill()
        processo.wait(timeout=5)
        limite = time.monotonic() + 5
        while time.monotonic() < limite and any(Path(f'/proc/{pid}').exists() for pid in filhos):
            time.sleep(.02)
        assert all(not Path(f'/proc/{pid}').exists() for pid in filhos)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=5)
        for pid in filhos:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_preserva_returncode_negativo_de_sinal(tmp_path):
    import signal

    log = tmp_path/'sinal.log'
    comando = "import os,signal;os.kill(os.getpid(), signal.SIGTERM)"
    with pytest.raises(pr.ValidacaoReprovada, match='exit -15'):
        pr.rodar([sys.executable, '-c', comando], tmp_path, log=log, prazo_segundos=5)
    assert 'Exit: -15' in log.read_text(encoding='utf-8')


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_supervisor_limpa_arvore_em_erro_inesperado(tmp_path, monkeypatch):
    import os
    import select
    from pr_processos_linux import SupervisorLinux

    leitura, escrita = os.pipe()
    supervisor = SupervisorLinux(leitura)
    chamado = False
    encerrar = SupervisorLinux._encerrar_arvore

    def encerrar_medido(self):
        nonlocal chamado
        chamado = True
        return encerrar(self)

    def falhar(*_args, **_kwargs):
        raise RuntimeError('falha interna medida')

    monkeypatch.setattr(SupervisorLinux, '_encerrar_arvore', encerrar_medido)
    monkeypatch.setattr(select, 'select', falhar)
    try:
        with pytest.raises(RuntimeError, match='falha interna medida'):
            supervisor.executar([sys.executable, '-c', 'import time;time.sleep(60)'])
        assert chamado
    finally:
        os.close(escrita)


@pytest.mark.skipif(sys.platform != 'linux', reason='Adoção de órfãos do Linux')
def test_linux_nao_confunde_proc_indisponivel_com_ausencia_de_filhos(tmp_path):
    from pr_processos_linux import GrupoLinux
    grupo = object.__new__(GrupoLinux)
    grupo.tarefas = tmp_path
    with pytest.raises(OSError, match='não informou os descendentes'):
        grupo._filhos()
