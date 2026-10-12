import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

import pytest
import backup_imagens as b
import armazenamento_codigo as storage


def imagem(path):
    config = b'{}'
    digest = hashlib.sha256(config).hexdigest()
    with tarfile.open(path, 'w') as archive:
        for name, data in ((digest+'.json', config),
                           ('manifest.json', json.dumps([{'Config': digest+'.json', 'RepoTags': []}]).encode())):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return 'sha256:'+digest


def test_mesma_imagem_exportada_uma_vez_e_tags_recuperadas(tmp_path, monkeypatch):
    source = tmp_path/'source.tar'
    identity = imagem(source)
    calls = []
    monkeypatch.setattr(b, 'docker', lambda *a: (calls.append(a) or identity))
    original = storage.image_archive
    exports = []
    def exporter(image_id, output):
        exports.append(image_id)
        output.write(source.read_bytes())
    monkeypatch.setattr(b, 'image_archive', lambda *a: original(*a, exporter=exporter))
    a, c = tmp_path/'a.tar', tmp_path/'c.tar'
    first = b.backup_image('app:primeira', a, tmp_path/'store')
    second = b.backup_image('app:segunda', c, tmp_path/'store')
    assert len(exports) == 1 and not first['reused'] and second['reused']
    assert os.path.samefile(a, c) and a.read_bytes() == source.read_bytes()
    assert second['new_bytes'] == 0 and second['saved_bytes'] == source.stat().st_size
    assert b.restore_image(c) == identity
    assert ('tag', identity, 'app:segunda') in calls
    assert ('load', '-i', str(c)) in calls
    usage = json.loads((tmp_path/'store/uso.json').read_text())
    assert usage['exportacoes'] == 1 and usage['reutilizacoes'] == 1
    # Corrupção impede recuperação antes de chamar Docker.
    os.chmod(c, 0o600)
    c.write_bytes(b'divergente')
    before = len(calls)
    with pytest.raises(ValueError):
        b.restore_image(c)
    assert len(calls) == before


def test_imagem_divergente_nao_e_compartilhada(tmp_path, monkeypatch):
    source = tmp_path/'source.tar'
    imagem(source)
    monkeypatch.setattr(b, 'docker', lambda *a: 'sha256:'+'f'*64)
    original = storage.image_archive
    monkeypatch.setattr(b, 'image_archive', lambda *a: original(*a, exporter=lambda i, out: out.write(source.read_bytes())))
    with pytest.raises(ValueError):
        b.backup_image('app:teste', tmp_path/'a.tar', tmp_path/'store')
    assert not (tmp_path/'a.tar').exists()


def test_acervo_anterior_e_reusado_sem_exportar_ou_alterar_backup(tmp_path, monkeypatch):
    legacy = tmp_path/'anterior'
    legacy.mkdir()
    source = legacy/'source.tar'
    identity = imagem(source)
    source = source.rename(legacy/('imagem-'+identity[7:]+'.tar'))
    source.with_suffix('.json').write_text(json.dumps({'imagem': identity,
        'sha256': storage.digest(source), 'bytes': source.stat().st_size}))
    monkeypatch.setattr(b, 'IMAGENS_PRESERVADAS', legacy)
    monkeypatch.setattr(b, 'docker', lambda *args: identity)
    def nao_exportar(*args, **kwargs):
        raise AssertionError('A imagem já preservada não deve ser exportada novamente')
    monkeypatch.setattr(storage.subprocess, 'run', nao_exportar)
    before = source.stat()
    result = b.backup_image(identity, tmp_path/'nova.tar', tmp_path/'store')
    assert result['reused'] and result['new_bytes'] == 0
    assert os.path.samefile(source, tmp_path/'nova.tar')
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    assert source.stat().st_mode == before.st_mode
