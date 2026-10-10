import importlib.util
import hashlib
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('robo', Path(__file__).with_name('robo.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_entrega_envia_commit_observado_e_base(monkeypatch, tmp_path):
    chamadas = []
    sha, base = 'a' * 40, 'b' * 40
    id_ = hashlib.sha256(('codex/entrega/prova\n' + sha).encode()).hexdigest()[:12]
    def executar(argv, **kwargs):
        chamadas.append(argv)
        if 'symbolic-ref' in argv: return 'codex/entrega/prova'
        if 'rev-parse' in argv: return sha
        if 'config' in argv: return base
        if argv[0] == 'ssh': return json.dumps({'id': id_})
        return ''
    monkeypatch.setattr(r, 'executar', executar)
    assert id_ in r.entregar(tmp_path, 'sitesdoreino-robo', ['f' * 12])
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


def test_resposta_perdida_consulta_mesma_entrega(monkeypatch, tmp_path):
    sha, base = 'a' * 40, 'b' * 40
    ramo = 'codex/entrega/prova'
    id_ = hashlib.sha256((ramo + '\n' + sha).encode()).hexdigest()[:12]
    chamadas = []
    def executar(argv, **kwargs):
        if 'symbolic-ref' in argv: return ramo
        if 'rev-parse' in argv: return sha
        if 'config' in argv: return base
        return ''
    def remoto(servidor, args):
        chamadas.append(args)
        if args[0] == 'entregar':
            raise r.RemotoIndisponivel('resposta perdida')
        return json.dumps({'id': id_, 'ramo': ramo, 'commit': sha, 'estado': 'recebida'})
    monkeypatch.setattr(r, 'executar', executar)
    monkeypatch.setattr(r, 'remoto', remoto)
    assert json.loads(r.entregar(tmp_path, 'sitesdoreino-robo'))['id'] == id_
    assert chamadas[-1] == ['consultar', id_]


def test_falha_ssh_nao_expoe_stderr(monkeypatch):
    class Resultado:
        returncode = 255
        stdout = ''
        stderr = 'SEGREDO_TESTE'
    monkeypatch.setattr(r.subprocess, 'run', lambda *a, **k: Resultado())
    with pytest.raises(r.RemotoIndisponivel) as erro:
        r.remoto('sitesdoreino-robo', ['estado'])
    assert 'SEGREDO_TESTE' not in str(erro.value)


def test_recusa_integrador_codigo_seguro_e_id(monkeypatch):
    class Resultado:
        returncode = 2
        stdout = json.dumps({'recusado': True, 'motivo': 'entrega ' + 'a' * 12 + ' não existe'})
        stderr = 'SEGREDO_TESTE'
    monkeypatch.setattr(r.subprocess, 'run', lambda *a, **k: Resultado())
    with pytest.raises(r.RecusaRemota) as erro:
        r.remoto('sitesdoreino-robo', ['consultar', 'a' * 12])
    assert erro.value.codigo == 'entrega_inexistente'
    assert erro.value.id == 'a' * 12
    assert 'SEGREDO_TESTE' not in str(erro.value)


def test_recusa_desconhecida_nao_repassa_motivo(monkeypatch):
    class Resultado:
        returncode = 2
        stdout = json.dumps({'recusado': True, 'motivo': 'SEGREDO_TESTE'})
        stderr = ''
    monkeypatch.setattr(r.subprocess, 'run', lambda *a, **k: Resultado())
    with pytest.raises(r.RecusaRemota) as erro:
        r.remoto('sitesdoreino-robo', ['estado'])
    assert erro.value.codigo == 'operacao_recusada'
    assert 'SEGREDO_TESTE' not in str(erro.value)


def test_indisponibilidade_explicita_nao_vira_recusa(monkeypatch):
    class Resultado:
        returncode = 3
        stdout = json.dumps({'indisponivel': True, 'motivo': 'SEGREDO_TESTE'})
        stderr = ''
    monkeypatch.setattr(r.subprocess, 'run', lambda *a, **k: Resultado())
    with pytest.raises(r.RemotoIndisponivel) as erro:
        r.remoto('sitesdoreino-robo', ['estado'])
    assert 'SEGREDO_TESTE' not in str(erro.value)
