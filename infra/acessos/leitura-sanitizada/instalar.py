"""Instalador pontual: dois arquivos existentes, um módulo e cache sanitizado."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from datetime import datetime, timezone
from leitura import ACCESS, CACHE, ENTREGA, atomic, read_regular


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('fonte_instalada_divergente')
    return source.replace(old, new)


def transform(command, context):
    command = once(command, 'import sys\n', 'import sys\nfrom leitura_sanitizada import atender_leitura\n')
    marker = '    consulta = atender(args, __file__)'
    command = once(command, marker,
                   '    leitura = atender_leitura(args)\n    if leitura is not None:\n        return leitura\n' + marker)
    context = once(context, "            'console': 'https://hpanel.hostinger.com/vps/1893584/overview',\n", '')
    marker = "            'consultar ID': 'Registro completo da entrega e evidências disponíveis.',\n"
    context = once(context, marker, marker +
                   "            'diagnostico ed31b0c03f97': 'Leitura sanitizada do funil; sem logs brutos, execução ou alteração de dados.',\n")
    compile(command, 'robo_comando.py', 'exec')
    compile(context, 'operacao_contexto.py', 'exec')
    return command, context


def install(access=ACCESS, module=None, prove=True):
    module = module if module is not None else Path(__file__).with_name('leitura.py').read_bytes()
    command, context = access / 'robo_comando.py', access / 'operacao_contexto.py'
    target = access / 'leitura_sanitizada.py'
    if target.exists() or target.is_symlink():
        raise ValueError('extensao_existente_nao_sobrescrita')
    paths = (command, context)
    previous = {path: read_regular(path, access, 262144) for path in paths}
    metadata = {path: path.stat() for path in paths}
    if os.name == 'posix' and any(info.st_mode & 0o022 for info in metadata.values()):
        raise ValueError('permissoes_inesperadas')
    if os.name == 'posix' and any(info.st_uid != 0 or info.st_gid != 0 for info in metadata.values()):
        raise ValueError('proprietario_inesperado')
    updated = transform(*(previous[path].decode('utf-8') for path in paths))
    compile(module, str(target), 'exec')
    backup = access / ('backup-leitura-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700)
    for path, data in previous.items():
        atomic(backup / path.name, data, 0o600)
        if read_regular(backup / path.name, backup, 262144) != data:
            raise ValueError('backup_nao_conferido')
    cache = access / CACHE.name
    if cache.is_symlink():
        raise ValueError('cache_invalido')
    cache.mkdir(mode=0o755, exist_ok=True)
    if os.name == 'posix' and (cache.stat().st_uid != 0 or cache.stat().st_mode & 0o022):
        raise ValueError('cache_permissoes_invalidas')
    hashes = {path.name: hashlib.sha256(data).hexdigest() for path, data in previous.items()}
    atomic(backup / 'originais.json', json.dumps(hashes).encode(), 0o600)
    try:
        if any(read_regular(path, access, 262144) != previous[path] for path in paths):
            raise ValueError('codigo_alterado_concorrentemente')
        atomic(target, module)
        for path, source in zip(paths, updated):
            atomic(path, source.encode('utf-8'), stat.S_IMODE(metadata[path].st_mode))
        if prove:
            env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
                   'SSH_ORIGINAL_COMMAND': 'ajuda'}
            check = subprocess.run([sys.executable, str(command)], capture_output=True,
                                   env=env, timeout=20, check=True)
            help_data = json.loads(check.stdout)
            if ('diagnostico ' + ENTREGA not in help_data.get('comandos', {})
                    or 'console' in help_data.get('referencias', {})):
                raise ValueError('catalogo_nao_comprovado')
        result = {'estado': 'instalado', 'backup': backup.name, 'originais_sha256': hashes,
                  'bancos_alterados': False, 'chaves_alteradas': False, 'reinicios': 0}
        atomic(backup / 'resultado.json', json.dumps(result).encode(), 0o600)
        return result
    except Exception:
        for path, source in zip(paths, updated):
            if read_regular(path, access, 262144) == source.encode('utf-8'):
                atomic(path, previous[path], stat.S_IMODE(metadata[path].st_mode))
        if target.is_file() and not target.is_symlink() and target.read_bytes() == module:
            target.unlink()
        atomic(backup / 'resultado.json', b'{"estado":"codigo_anterior_recuperado"}', 0o600)
        raise


if __name__ == '__main__':
    try:
        if os.geteuid() != 0:
            raise ValueError('instalador_exige_identidade_administrativa')
        print(json.dumps(install()), flush=True)
    except Exception:
        print('{"estado":"instalacao_recusada_ou_recuperada"}', flush=True)
        sys.exit(2)
