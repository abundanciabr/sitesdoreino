"""Alinha três provas de aparência à home solicitada em 14/10/2026."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

COMMIT = 'a5cceeecc672cc5e6d8e33d61ccdee77c0c2c144'
FILES = {
    'test_menu_do_topo.py': ('d8d45a2cd552be695628d0ca8ad024bb3da6fb71', 'bf700ec1fadc2ce30f86b5170ff2794c7fd57b32'),
    'test_rodape.py': ('52374fc21110cf775d239db14f6dc61a9b5af559', 'c6c74e517eb16e0d4cfcbbc98109dcbc23343644'),
    'test_sessao_no_site.py': ('4cabe8527d0893fcf3fdfd6d8b744762e8c01499', 'a28e997943d74cbf1f82f603eea70add43e7461f'),
}
ROOT = Path('/opt/plataforma')
PUB = Path('/usr/local/lib/meshcraft-publicador')
DEST = ROOT / 'manutencoes/home-visitante-limpa-20261014'

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def report(state, **extra):
    result = {'estado': state, 'commit': COMMIT, **extra}
    temp = DEST / 'resultado.tmp'
    temp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, DEST / 'resultado.json')
    print(json.dumps(result, ensure_ascii=False), flush=True)

def main():
    assert os.geteuid() == 0
    os.umask(0o077)
    DEST.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = DEST / 'resultado.json'
    if existing.exists() and json.loads(existing.read_text())['estado'] == 'concluida':
        print(existing.read_text(), flush=True)
        return
    sources = {}
    for name, (_, after) in FILES.items():
        url = f'https://raw.githubusercontent.com/abundanciabr/sitesdoreino/{COMMIT}/services/funil/tests/{name}'
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        assert blob(data) == after, name
        compile(data, name, 'exec')
        sources[name] = data
    report('aguardando operacoes existentes terminarem')
    locks = []
    original = None
    new = None
    try:
        # Usa as mesmas exclusões já instaladas, sem interromper outras entregas.
        for path in (
            Path('/var/lib/meshcraft-integrador/entregas/fases/.worker.lock'),
            Path('/var/lib/meshcraft-integrador/entregas/.integrador.lock'),
            ROOT / 'publicacoes/.ativacao.lock',
            ROOT / 'publicacoes/lotes/.lote.lock',
        ):
            assert path.is_file() and not path.is_symlink()
            fd = path.open('rb')
            locks.append(fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
        pointer = PUB / 'atual'
        assert pointer.is_symlink()
        original = pointer.resolve(strict=True)
        assert original.parent == PUB
        tests = original / 'provas-funil/tests'
        for name, (before, _) in FILES.items():
            assert blob((tests / name).read_bytes()) == before, 'base divergente: ' + name
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        backup = ROOT / 'backups-de-codigo' / ('home-deslogada-provas-' + stamp)
        backup.mkdir(mode=0o700)
        for name in FILES:
            shutil.copy2(tests / name, backup / name)
        (backup / 'ponteiro-anterior.json').write_text(json.dumps({'release': str(original)}))
        new = PUB / ('home-deslogada-provas-' + stamp)
        shutil.copytree(original, new, symlinks=True)
        for name, data in sources.items():
            target = new / 'provas-funil/tests' / name
            target.write_bytes(data)
            target.chmod((tests / name).stat().st_mode & 0o777)
        # A cópia anterior continua intacta; somente essas três provas diferem.
        differences = []
        for p in original.rglob('*'):
            q = new / p.relative_to(original)
            if p.is_symlink():
                assert q.is_symlink() and os.readlink(p) == os.readlink(q)
            elif p.is_file():
                if p.read_bytes() != q.read_bytes():
                    differences.append(p.relative_to(original).as_posix())
        assert sorted(differences) == sorted('provas-funil/tests/' + n for n in FILES)
        assert pointer.resolve() == original
        temp = PUB / ('.home-deslogada-' + stamp)
        temp.symlink_to(new.name)
        os.replace(temp, pointer)
        assert pointer.resolve() == new
        report('concluida', anterior=str(original), atual=str(new), backup=str(backup), arquivos=differences)
    except Exception as exc:
        pointer = PUB / 'atual'
        if new and original and pointer.resolve() == new:
            temp = PUB / '.home-deslogada-recuperacao'
            assert not temp.exists() and not temp.is_symlink()
            temp.symlink_to(original.name)
            os.replace(temp, pointer)
        report('nao instalada', motivo=str(exc))
        raise
    finally:
        for fd in reversed(locks):
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

if __name__ == '__main__':
    main()
