"""Objetos privados reutilizáveis para novos backups e imagens de ensaio.

Não migra, remove ou reescreve backups. Recuperação sempre em pasta nova.
Os bancos e sua retenção não participam deste armazenamento.
"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import uuid


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path):
    return stat.S_ISREG(Path(path).lstat().st_mode)


def sync_dir(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def new_json(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    with temp.open('x', encoding='utf-8') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, sort_keys=True, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temp, path)  # criação exclusiva, inclusive com outro escritor
    temp.unlink()  # somente o temporário criado nesta chamada
    sync_dir(path.parent)


@contextlib.contextmanager
def locked(store):
    store = Path(store)
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    if store.is_symlink() or not store.is_dir():
        raise ValueError('armazenamento inválido')
    if os.name == 'posix' and (store.stat().st_uid != os.geteuid() or store.stat().st_mode & 0o077):
        raise ValueError('armazenamento deve ser privado ao executor')
    fd = os.open(store / '.lock', os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+b') as stream:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        else:
            import msvcrt
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield store
        finally:
            if os.name == 'posix':
                fcntl.flock(stream, fcntl.LOCK_UN)
            else:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _object(store, sha):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('identidade inválida')
    return store / 'objetos' / (sha + '.gz')


def _check_object(path, sha, output=None):
    if not regular(path):
        raise ValueError('objeto ausente ou irregular')
    h = hashlib.sha256()
    size = 0
    with gzip.open(path, 'rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk); size += len(chunk)
            if output is not None:
                output.write(chunk)
    if h.hexdigest() != sha:
        raise ValueError('conteúdo de backup divergente')
    return size


def snapshot(store, roots, destination, reference=None):
    """Guarda cada conteúdo uma vez; cada versão tem manifesto independente."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    entries = []
    logical = added = 0
    names = set()
    with locked(store) as store:
        (store / 'objetos').mkdir(mode=0o700, exist_ok=True)
        for prefix, source in sorted(roots.items()):
            source = Path(source)
            paths = [source] + (sorted(source.rglob('*')) if source.is_dir() else [])
            for path in paths:
                name = (PurePosixPath(prefix) / path.relative_to(source).as_posix()).as_posix()
                _safe_name(name)
                if name in names:
                    raise ValueError('caminho repetido')
                names.add(name)
                before = path.lstat()
                item = {'path': name, 'mode': stat.S_IMODE(before.st_mode),
                        'uid': before.st_uid, 'gid': before.st_gid, 'mtime_ns': before.st_mtime_ns}
                if stat.S_ISDIR(before.st_mode):
                    item['type'] = 'dir'
                elif stat.S_ISREG(before.st_mode):
                    sha = digest(path)
                    obj = _object(store, sha)
                    if not obj.exists():
                        temp = store / 'objetos' / ('.parcial-' + uuid.uuid4().hex)
                        with temp.open('xb') as raw:
                            os.chmod(temp, 0o600)
                            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as zipped:
                                with path.open('rb') as stream:
                                    shutil.copyfileobj(stream, zipped)
                            raw.flush(); os.fsync(raw.fileno())
                        size = _check_object(temp, sha)
                        added += temp.stat().st_size
                        os.rename(temp, obj)
                        sync_dir(obj.parent)
                    else:
                        size = _check_object(obj, sha)
                    after = path.lstat()
                    if (before.st_size, before.st_mtime_ns, before.st_ino, before.st_mode) != (
                            after.st_size, after.st_mtime_ns, after.st_ino, after.st_mode) or size != before.st_size:
                        raise ValueError('origem mudou durante o backup')
                    item.update(type='file', sha256=sha, size=size)
                    logical += size
                else:
                    raise ValueError('backup de código não aceita links ou arquivos especiais')
                entries.append(item)
        value = {'format': 'meshcraft-codigo-1', 'reference': reference, 'entries': entries,
                 'logical_bytes': logical, 'new_object_bytes': added}
        new_json(destination, value)
    actual = added + destination.stat().st_size
    return {'logical_bytes': logical, 'new_bytes': actual, 'saved_bytes': logical - actual,
            'files': sum(e['type'] == 'file' for e in entries), 'manifest': str(destination)}


def _safe_name(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or any(x in ('.', '..') for x in name.split('/')) or '\\' in name or ':' in name:
        raise ValueError('caminho de backup inválido')
    return p


def restore(store, manifest, destination):
    """Copia os bytes em diretório novo; nunca altera objetos ou versões antigas."""
    store, destination = Path(store), Path(destination)
    data = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if data.get('format') != 'meshcraft-codigo-1':
        raise ValueError('formato desconhecido')
    seen = set()
    for e in data['entries']:
        _safe_name(e['path'])
        if e['path'] in seen or e['type'] not in ('file', 'dir'):
            raise ValueError('manifesto inválido')
        seen.add(e['path'])
        if e['type'] == 'file' and _check_object(_object(store, e['sha256']), e['sha256']) != e['size']:
            raise ValueError('tamanho divergente')
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    for e in sorted(data['entries'], key=lambda x: (x['path'].count('/'), x['path'])):
        path = destination / e['path']
        if e['type'] == 'dir':
            path.mkdir(mode=0o700)
        else:
            with path.open('xb') as output:
                _check_object(_object(store, e['sha256']), e['sha256'], output)
                output.flush(); os.fsync(output.fileno())
    for e in sorted(data['entries'], key=lambda x: x['path'].count('/'), reverse=True):
        path = destination / e['path']
        if os.name == 'posix' and os.geteuid() == 0:
            os.chown(path, e['uid'], e['gid'])
        os.chmod(path, e['mode'])
        os.utime(path, ns=(e['mtime_ns'], e['mtime_ns']))
    sync_dir(destination)
    return {'restored_files': sum(e['type'] == 'file' for e in data['entries'])}


def image_archive(store, image_id, destination, validate, log=None, exporter=None):
    """Exportação única por ID; novos caminhos são hardlinks privados, nunca symlinks.

    O destino tem que ser novo. Nenhum consumidor abre estes arquivos para escrita.
    Cópias de recuperação independentes são feitas por docker load ou shutil.copy2.
    """
    if not re.fullmatch('sha256:[0-9a-f]{64}', image_id):
        raise ValueError('imagem precisa de identidade imutável')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    with locked(store) as store:
        images = store / 'imagens'
        images.mkdir(mode=0o700, exist_ok=True)
        obj = images / (image_id[7:] + '.tar')
        meta = obj.with_suffix('.json')
        reused = obj.exists()
        if reused:
            if not regular(obj) or not regular(meta):
                raise ValueError('imagem compartilhada irregular')
            expected = json.loads(meta.read_text())
            if digest(obj) != expected['sha256'] or validate(obj) != image_id:
                raise ValueError('imagem compartilhada divergente')
        else:
            temp = images / ('.parcial-' + uuid.uuid4().hex)
            with temp.open('xb') as output:
                os.chmod(temp, 0o400)
                if exporter is not None:
                    exporter(image_id, output)
                else:
                    subprocess.run(['docker', 'save', image_id], stdout=output, stderr=log,
                                   timeout=900, check=True)
                output.flush(); os.fsync(output.fileno())
            if validate(temp) != image_id:
                raise ValueError('exportação de imagem divergente')
            expected = {'image_id': image_id, 'sha256': digest(temp), 'size': temp.stat().st_size}
            # A referência só é publicada depois de todos os bytes terem sido comprovados.
            if meta.exists():
                if not regular(meta) or json.loads(meta.read_text()) != expected:
                    raise ValueError('exportação interrompida divergiu; arquivos preservados')
            else:
                new_json(meta, expected)
            os.rename(temp, obj)
            sync_dir(images)
        os.link(obj, destination)
        sync_dir(destination.parent)
    size = obj.stat().st_size
    return {'logical_bytes': size, 'new_bytes': 0 if reused else size + meta.stat().st_size,
            'saved_bytes': size if reused else 0, 'reused': reused, 'sha256': expected['sha256']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['snapshot', 'restore'])
    parser.add_argument('store', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.action == 'restore':
        result = restore(args.store, args.source, args.destination)
    else:
        result = snapshot(args.store, {'codigo': args.source}, args.destination)
    print(json.dumps(result))
