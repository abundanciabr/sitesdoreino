"""Guardas novas específicas do sistema operacional da validação."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ci'))
import pr


@pytest.mark.skipif(sys.platform != 'win32', reason='API Job Object do Windows')
def test_windows_recusa_execucao_sem_conter_processos(tmp_path, monkeypatch):
    import subprocess
    from pr_processos_windows import GrupoWindows
    processos = []
    def negar(self, processo):
        processos.append(processo)
        with pytest.raises(subprocess.TimeoutExpired):
            processo.wait(timeout=.2)
        raise OSError('associação recusada pelo sistema')
    monkeypatch.setattr(GrupoWindows, 'associar_e_iniciar', negar)
    log = tmp_path/'error.log'
    with pytest.raises(pr.ErroDeInstrumentacao, match='não pôde executar'):
        pr.rodar([sys.executable, '-c', "from pathlib import Path;Path('executou').touch()"], tmp_path, log=log, prazo_segundos=1)
    assert len(processos) == 1 and processos[0].poll() is not None
    assert not (tmp_path/'executou').exists()
    assert 'ERROR' in log.read_text(encoding='utf-8')
