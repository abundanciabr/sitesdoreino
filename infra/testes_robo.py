import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('robo', Path(__file__).with_name('robo.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_entrega_envia_commit_observado_e_base(monkeypatch, tmp_path):
    chamadas = []
    sha, base = 'a' * 40, 'b' * 40
    def executar(argv, **kwargs):
        chamadas.append(argv)
        if 'symbolic-ref' in argv: return 'codex/entrega/prova'
        if 'rev-parse' in argv: return sha
        if 'config' in argv: return base
        if argv[0] == 'ssh': return '{"id":"0123456789ab"}'
        return ''
    monkeypatch.setattr(r, 'executar', executar)
    assert '0123456789ab' in r.entregar(tmp_path, 'sitesdoreino-robo', ['f' * 12])
    push = next(c for c in chamadas if 'push' in c)
    assert push[-1] == sha + ':refs/heads/codex/entrega/prova'
    ssh = chamadas[-1]
    assert ssh[-2] == 'sitesdoreino-robo'
    assert '--commit ' + sha in ssh[-1]
    assert '--base ' + base in ssh[-1]
    assert '--depende-de ' + 'f' * 12 in ssh[-1]
    assert 'promover' not in ssh[-1]


def test_falha_no_push_nao_envia_entrega(monkeypatch, tmp_path):
    chamadas = []
    def executar(argv, **kwargs):
        chamadas.append(argv)
        if 'symbolic-ref' in argv: return 'claude/entrega/prova'
        if 'rev-parse' in argv or 'config' in argv: return 'a' * 40
        if 'push' in argv: raise RuntimeError('remoto indisponível')
        return ''
    monkeypatch.setattr(r, 'executar', executar)
    with pytest.raises(RuntimeError): r.entregar(tmp_path, 'sitesdoreino-robo')
    assert not any(c[0] == 'ssh' for c in chamadas)


@pytest.mark.parametrize('servidor', ['-oProxyCommand=x', 'site;comando', 'robo@site'])
def test_alias_nao_pode_injetar_opcao_ssh(servidor):
    with pytest.raises(ValueError): r.remoto(servidor, ['estado'])


def test_consulta_rejeita_id_antes_da_rede(monkeypatch):
    monkeypatch.setattr(r, 'remoto', lambda *a: pytest.fail('não deveria conectar'))
    assert r.main(['consultar', '../../registro']) == 2
