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
        if argv[0] == 'ssh':
            return json.dumps({'id': id_, 'ramo': 'codex/entrega/prova', 'commit': sha,
                               'base': base, 'origem': 'codex', 'depende_de': ['f' * 12]})
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
        return json.dumps({'id': id_, 'ramo': ramo, 'commit': sha, 'base': base,
                           'origem': 'codex', 'depende_de': [], 'estado': 'recebida'})
    monkeypatch.setattr(r, 'executar', executar)
    monkeypatch.setattr(r, 'remoto', remoto)
    assert json.loads(r.entregar(tmp_path, 'sitesdoreino-robo'))['id'] == id_
    assert chamadas[-1] == ['consultar', id_]


@pytest.mark.parametrize('mudanca', [
    {'base': 'c' * 40}, {'origem': 'claude'}, {'depende_de': []},
    {'depende_de': ['e' * 12, 'd' * 12]},
    {'depende_de': ['d' * 12]}, {'base': None}, {'origem': None},
    {'depende_de': None},
])
def test_resposta_perdida_nao_confirma_registro_divergente(monkeypatch, tmp_path, capsys, mudanca):
    ramo, sha, base = 'codex/entrega/prova', 'a' * 40, 'b' * 40
    deps = ['d' * 12, 'e' * 12, 'd' * 12]
    id_ = hashlib.sha256((ramo + '\n' + sha).encode()).hexdigest()[:12]
    registro = {'id': id_, 'ramo': ramo, 'commit': sha, 'base': base,
                'origem': 'codex', 'depende_de': deps, 'estado': 'precisa de correção'}
    registro.update(mudanca)
    chamadas = []

    def git_falso(_repo, *args):
        if args[0] == 'symbolic-ref': return ramo
        if args[0] == 'rev-parse': return sha
        if args[0] == 'config': return base
        return ''

    def remoto_falso(_servidor, args):
        chamadas.append(args)
        if args[0] == 'entregar': raise r.RemotoIndisponivel('resposta perdida')
        return json.dumps(registro)

    monkeypatch.setattr(r, 'git', git_falso)
    monkeypatch.setattr(r, 'remoto', remoto_falso)
    codigo = r.main(['--repo', str(tmp_path), 'entregar',
                     *[item for dep in deps for item in ('--depende-de', dep)]])
    saida = capsys.readouterr()
    assert codigo == 2 and not saida.out
    assert 'confirmação indisponível' in saida.err
    assert chamadas[-1] == ['consultar', id_]
    assert sum(args[0] == 'entregar' for args in chamadas) == 1


def test_resposta_direta_divergente_consulta_pedido_persistido(monkeypatch, tmp_path):
    ramo, sha, base = 'codex/entrega/prova', 'a' * 40, 'b' * 40
    deps = ['d' * 12, 'e' * 12, 'd' * 12]
    id_ = hashlib.sha256((ramo + '\n' + sha).encode()).hexdigest()[:12]
    registro = {'id': id_, 'ramo': ramo, 'commit': sha, 'base': base,
                'origem': 'codex', 'depende_de': deps}
    chamadas = []

    def git_falso(_repo, *args):
        if args[0] == 'symbolic-ref': return ramo
        if args[0] == 'rev-parse': return sha
        if args[0] == 'config': return base
        return ''

    def remoto_falso(_servidor, args):
        chamadas.append(args)
        if args[0] == 'entregar': return json.dumps({**registro, 'base': 'c' * 40})
        return json.dumps(registro)

    monkeypatch.setattr(r, 'git', git_falso)
    monkeypatch.setattr(r, 'remoto', remoto_falso)
    assert json.loads(r.entregar(tmp_path, 'sitesdoreino-robo', deps)) == registro
    assert [args[0] for args in chamadas] == ['entregar', 'consultar']


def test_resposta_direta_completa_confirma_sem_consulta(monkeypatch, tmp_path):
    ramo, sha, base = 'codex/entrega/prova', 'a' * 40, 'b' * 40
    deps = ['d' * 12, 'e' * 12, 'd' * 12]
    id_ = hashlib.sha256((ramo + '\n' + sha).encode()).hexdigest()[:12]
    registro = {'id': id_, 'ramo': ramo, 'commit': sha, 'base': base,
                'origem': 'codex', 'depende_de': deps}
    chamadas = []

    def git_falso(_repo, *args):
        if args[0] == 'symbolic-ref': return ramo
        if args[0] == 'rev-parse': return sha
        if args[0] == 'config': return base
        return ''

    def remoto_falso(_servidor, args):
        chamadas.append(args)
        return json.dumps(registro)

    monkeypatch.setattr(r, 'git', git_falso)
    monkeypatch.setattr(r, 'remoto', remoto_falso)
    assert json.loads(r.entregar(tmp_path, 'sitesdoreino-robo', deps)) == registro
    assert [args[0] for args in chamadas] == ['entregar']


@pytest.mark.parametrize('campo', ['id', 'ramo', 'commit', 'base', 'origem', 'depende_de'])
def test_confirmacao_exige_todos_os_campos(campo):
    esperado = {'id': 'a' * 12, 'ramo': 'codex/entrega/prova', 'commit': 'b' * 40,
                'base': 'c' * 40, 'origem': 'codex', 'depende_de': []}
    incompleto = {k: v for k, v in esperado.items() if k != campo}
    assert not r.confirma_entrega(json.dumps(incompleto), esperado)


def test_cli_confirma_resposta_perdida_quando_pedido_foi_persistido(monkeypatch, tmp_path, capsys):
    ramo, sha, base = 'codex/entrega/prova', 'a' * 40, 'b' * 40
    deps = ['d' * 12, 'd' * 12]
    id_ = hashlib.sha256((ramo + '\n' + sha).encode()).hexdigest()[:12]
    registro = {'id': id_, 'ramo': ramo, 'commit': sha, 'base': base,
                'origem': 'codex', 'depende_de': deps}
    chamadas = []

    def git_falso(_repo, *args):
        if args[0] == 'symbolic-ref': return ramo
        if args[0] == 'rev-parse': return sha
        if args[0] == 'config': return base
        return ''

    def remoto_falso(_servidor, args):
        chamadas.append(args)
        if args[0] == 'entregar': raise r.RemotoIndisponivel('resposta perdida')
        return json.dumps(registro)

    monkeypatch.setattr(r, 'git', git_falso)
    monkeypatch.setattr(r, 'remoto', remoto_falso)
    assert r.main(['--repo', str(tmp_path), 'entregar',
                   '--depende-de', deps[0], '--depende-de', deps[1]]) == 0
    assert json.loads(capsys.readouterr().out) == registro
    assert [args[0] for args in chamadas] == ['entregar', 'consultar']


def test_recusa_explicita_na_entrega_nao_consulta(monkeypatch, tmp_path):
    chamadas = []

    def git_falso(_repo, *args):
        if args[0] == 'symbolic-ref': return 'codex/entrega/prova'
        if args[0] in ('rev-parse', 'config'): return 'a' * 40
        return ''

    def remoto_falso(_servidor, args):
        chamadas.append(args)
        raise r.RecusaRemota('operacao_recusada')

    monkeypatch.setattr(r, 'git', git_falso)
    monkeypatch.setattr(r, 'remoto', remoto_falso)
    with pytest.raises(r.RecusaRemota):
        r.entregar(tmp_path, 'sitesdoreino-robo')
    assert [args[0] for args in chamadas] == ['entregar']


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
