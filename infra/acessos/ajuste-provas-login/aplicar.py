"""Ajuste pontual das provas do login; nenhum comando livre ou dado de alunos."""
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

NAMES = ('test_categorias_na_home.py', 'test_quadrinho_de_progresso.py', 'test_sessao_no_site.py')
NEW = 'test_acesso_aluno.py'
OP = 'acesso-central-ed31-20261014'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    if path.is_symlink():
        raise ValueError('link_recusado')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
        raise ValueError('fonte_invalida')
    return path.read_bytes()


def atomic(path, data, mode=0o644):
    temporary = path.with_name('.' + path.name + '.' + OP)
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError('link_recusado')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(mode)
    os.replace(temporary, path)


def apply(root, payload, hook=lambda: None):
    tests = root / 'tests'
    if root.is_symlink() or tests.is_symlink():
        raise ValueError('link_recusado')
    if tuple(payload['originais']) != NAMES or set(payload['novos']) != {*NAMES, NEW}:
        raise ValueError('escopo_divergente')
    originals = {name: read(tests / name) for name in NAMES}
    current_new = read(tests / NEW) if (tests / NEW).exists() else None
    if all(digest(originals[n]) == payload['novos'][n] for n in NAMES) and current_new is not None and digest(current_new) == payload['novos'][NEW]:
        return {'estado': 'ja_aplicado', 'id': OP}
    if current_new is not None:
        raise ValueError('arquivo_novo_ja_existe')
    if any(digest(originals[n]) != payload['originais'][n] for n in NAMES):
        raise ValueError('referencia_mudou')
    updated = {}
    for name in NAMES:
        text = originals[name].decode('utf-8')
        for old, new, count in payload['substituicoes'][name]:
            if text.count(old) != count:
                raise ValueError('trecho_divergente')
            text = text.replace(old, new)
        updated[name] = text.encode('utf-8')
    updated[NEW] = payload['arquivo_novo'].encode('utf-8')
    for name, data in updated.items():
        compile(data, name, 'exec')
        if digest(data) != payload['novos'][name]:
            raise ValueError('destino_divergente')
    modes = {name: stat.S_IMODE((tests / name).stat().st_mode) for name in NAMES}
    if any(mode & 0o022 for mode in modes.values()):
        raise ValueError('permissoes_inesperadas')
    if os.name == 'posix' and any((tests / name).stat().st_uid != os.geteuid() for name in NAMES):
        raise ValueError('proprietario_diferente')
    backup = root / ('backup-' + OP)
    backup.mkdir(mode=0o700, exist_ok=True)
    if backup.is_symlink():
        raise ValueError('backup_invalido')
    for name, data in originals.items():
        path = backup / name
        if path.exists() and read(path) != data:
            raise ValueError('backup_divergente')
        atomic(path, data, 0o600)
        if read(path) != data:
            raise ValueError('backup_nao_conferido')
    atomic(backup / 'manifesto.json', json.dumps({'originais': payload['originais'], 'modos': modes}).encode(), 0o600)
    result_path = root / (OP + '.json')
    atomic(result_path, json.dumps({'estado': 'aplicando', 'id': OP}).encode())
    try:
        if any(read(tests / n) != originals[n] for n in NAMES):
            raise ValueError('referencia_mudou')
        for name, data in updated.items():
            atomic(tests / name, data, modes.get(name, 0o644))
            hook()
        if any(digest(read(tests / n)) != payload['novos'][n] for n in updated):
            raise ValueError('gravacao_divergente')
        result = {'estado': 'aplicado', 'id': OP, 'backup': backup.name,
                  'sha256': payload['novos'], 'bancos_alterados': False,
                  'chaves_alteradas': False, 'mercadopago_alterado': False,
                  'servicos_reiniciados': 0, 'testes_removidos': 0}
        atomic(result_path, json.dumps(result).encode())
        return result
    except BaseException:
        for name in NAMES:
            if read(tests / name) == updated[name]:
                atomic(tests / name, originals[name], modes[name])
        path = tests / NEW
        if path.exists() and read(path) == updated[NEW]:
            path.unlink()
        atomic(result_path, json.dumps({'estado': 'referencia_anterior_recuperada', 'id': OP}).encode())
        raise


def main():
    import fcntl
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(3))
    payload = json.loads(Path(__file__).with_name('mudancas.json').read_text(encoding='utf-8'))
    with Path('/travas/worker').open('rb') as lock:
        deadline = time.monotonic() + 600
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ValueError('operacao_atual_ainda_em_andamento')
                time.sleep(1)
        print(json.dumps(apply(Path('/provas'), payload)), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        known = {'referencia_mudou', 'proprietario_diferente', 'permissoes_inesperadas', 'operacao_atual_ainda_em_andamento'}
        print(json.dumps({'estado': 'ajuste_recusado_ou_recuperado',
                          'motivo': str(error) if str(error) in known else type(error).__name__}), flush=True)
        sys.exit(2)
