"""Instalação pontual desta entrega; backup e retorno de código, nunca de banco."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path('/opt/plataforma')
PUB = Path('/usr/local/lib/meshcraft-publicador')
BASE = ROOT/'manutencoes/publicacao-estrutural-c19960b9e7c1/aplicar_canal.py'
BASE_SHA = '1f29d45cabb7580a8b5db6c01c67885c25a3aa056fea8fda74fa08431f85bb76'
INT = Path('/usr/local/lib/meshcraft-integrador/entregas.py')
INT_SHA = '32489117ffdf695f9f1d9c1446e9ba6f0be31a1eb69ca50315718f548c9533f6'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Gerador mudou; preservar e conferir a nova versão')
    return text.replace(old, new, 1)


def patch_appmax(text):
    old = """    fd = os.open(image, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        result = subprocess.run(['docker', 'image', 'save', approved['imagem']], stdout=stream,
                                stderr=subprocess.DEVNULL, timeout=300)
        stream.flush()
        os.fsync(stream.fileno())
    if result.returncode:
        raise RuntimeError('Approved image backup failed')
"""
    new = """    import sys
    sys.path.insert(0, '/usr/local/lib/meshcraft-publicador/atual/infra')
    from backup_imagens import backup_image
    backup_image(approved['imagem'], image, ROOT / 'objetos-imagens-manutencao')
"""
    return replace_once(text, old, new)


def patch_maintenance(text):
    # Troca apenas a exportação. Preserva correções locais do arquivo de código,
    # todas as chamadas de dump, ambiente, retenção e verificações existentes.
    tree = ast.parse(text)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'backup')
    lines = text.splitlines(keepends=True)
    body = ''.join(lines[function.lineno-1:function.end_lineno])
    start = body.index("        run('docker', 'save'")
    end = body.index('        if not tarfile.is_tarfile(image_path):', start)
    old = body[start:end]
    if 'image_path' not in old or len(old) > 500:
        raise ValueError('Exportação de manutenção não reconhecida')
    new = """        sys.path.insert(0, str(release / 'infra'))
        from backup_imagens import backup_image
        backup_image(image, image_path, ROOT / 'objetos-imagens-manutencao')
"""
    return replace_once(text, old, new)


def main(source):
    assert os.geteuid() == 0
    assert sha(BASE.read_bytes()) == BASE_SHA
    assert sha(INT.read_bytes()) == INT_SHA
    inst = load('instalador_existente', BASE)
    original = new = None
    active = set()
    changed = []
    stopped = switched = False
    task = ROOT/'manutencoes/integrador-armazenamento-20261012'
    task.mkdir(mode=0o700, exist_ok=True)
    try:
        print('ETAPA: aguardando operações correntes', flush=True)
        inst.acquire_locks()
        before = inst.inventory()
        active = {u for u in inst.UNITS if before['units'][u]['active'] == 'active'}
        original = inst.release_atual()
        stopped = True
        inst.stop_units()
        before = inst.inventory()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = ROOT/'backups-de-codigo'/('integrador-armazenamento-'+stamp)
        backup.mkdir(mode=0o700)
        shutil.copytree(original, backup/'controlador', symlinks=True)
        flats = {INT: (source/'infra/entregas.py').read_bytes(),
                 Path('/usr/local/lib/meshcraft-super-equipe/coletor.py'): (source/'infra/super_equipe_coletor.py').read_bytes(),
                 Path('/usr/local/lib/meshcraft-super-equipe/executor.py'): (source/'infra/super_equipe_executor.py').read_bytes(),
                 BASE: patch_maintenance(BASE.read_text()).encode()}
        # Estas são fontes de preparação, não os arquivos preservados de backup.
        appmax = ROOT/'appmax-clones/checkout-roblox-20261009'
        candidates = list(appmax.glob('preparacao-producao*/infra/appmax_checkout_teste/publicar_curso_blender.py'))
        candidates += [ROOT/'manutencoes/publicador-reaproveitamento-20261011/infra/appmax_checkout_teste/publicar_curso_blender.py']
        for path in candidates:
            if path.is_file():
                flats[path] = patch_appmax(path.read_text()).encode()
        records = []
        for i, (path, content) in enumerate(flats.items()):
            compile(content, str(path), 'exec')
            old = path.read_bytes()
            mode = path.stat().st_mode & 0o777
            saved = backup/(str(i)+'-'+path.name)
            saved.write_bytes(old); saved.chmod(0o600)
            records.append({'path': str(path), 'backup': str(saved), 'before': sha(old), 'after': sha(content), 'mode': mode})
        (backup/'referencia.json').write_text(json.dumps({'release': str(original), 'inventario': before, 'arquivos': records}))
        print('ETAPA: backup recuperável conferido', flush=True)
        new = PUB/('v12-integrador-armazenamento-'+stamp)
        shutil.copytree(original, new, symlinks=True)
        shutil.copyfile(source/'infra/backup_imagens.py', new/'infra/backup_imagens.py')
        (new/'infra/backup_imagens.py').chmod(0o644)
        compile((new/'infra/backup_imagens.py').read_bytes(), 'backup_imagens.py', 'exec')
        for p in original.rglob('*'):
            if p.is_file():
                assert inst.digest(p) == inst.digest(new/p.relative_to(original))
        # Arquivos substituídos atomicamente, com a identidade anterior conferida.
        for rec, (path, content) in zip(records, flats.items()):
            assert sha(path.read_bytes()) == rec['before']
            old = path.read_bytes()
            temp = path.with_name(path.name+'.armazenamento-'+stamp)
            temp.write_bytes(content); temp.chmod(rec['mode'])
            os.replace(temp, path)
            changed.append((path, old, rec['mode'], rec['after']))
        pointer = PUB/('.atual-armazenamento-'+stamp)
        pointer.symlink_to(new.name); os.replace(pointer, inst.ATUAL); switched = True
        for old, digest in before['arquivos'].items():
            path = Path(old)
            if path in flats:
                continue
            if path.is_relative_to(original):
                path = new/path.relative_to(original)
            assert inst.anchor_hash(path) == digest
        assert inst.rotas_hash() == before['rotas_sha256']
        mp = load('mp_independente', inst.VER)
        policy = json.loads(inst.POL.read_text())
        approved = json.loads((ROOT/'publicacoes/aplicacao.json').read_text())['aprovada']
        mp.conferir_pacote(Path(approved['codigo']), approved['imagem'], policy)
        mp.conferir_ambiente(ROOT, policy)
        health = {}
        for url in ('https://meshcraft.top/', 'https://meshcraft.top/admin/healthz',
                    'https://meshcraft.top/checkout/curso-primeiros-passos-no-blender'):
            health[url] = inst.run('curl', '--max-time', '30', '-L', '-sS', '-o', '/dev/null', '-w', '%{http_code}', url).stdout
            assert health[url] == '200', (url, health[url])
        inst.resume_units(active, restart=True)
        inst.run('systemctl', 'restart', 'meshcraft-super-equipe.service')
        inst.run('systemctl', 'start', 'meshcraft-super-equipe-coletor.service')
        result = {'instalado': True, 'release': str(new), 'anterior': str(original), 'backup': str(backup),
                  'arquivos': records, 'http': health, 'mercado_pago_conferido': True,
                  'bancos_alterados': False, 'retencao_alterada': False, 'dados_excluidos': False}
        (task/'resultado-instalacao.json').write_text(json.dumps(result, indent=2))
        print('INSTALADO '+json.dumps(result), flush=True)
        inst.release_locks()
    except BaseException:
        if original is not None:
            inst.recover(original, new, changed, active, stopped=stopped, switched=switched)
            inst.run('systemctl', 'restart', 'meshcraft-super-equipe.service')
            inst.run('systemctl', 'start', 'meshcraft-super-equipe-coletor.service')
        else:
            inst.release_locks()
        raise


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
