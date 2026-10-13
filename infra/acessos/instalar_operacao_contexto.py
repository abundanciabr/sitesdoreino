"""Instala consultas compostas sem reiniciar serviços nem ampliar permissões."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ACCESS = Path('/usr/local/lib/meshcraft-acessos')
COMMAND = ACCESS / 'robo_comando.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query(args):
    result = subprocess.run(['/usr/sbin/runuser', '-u', 'robo', '--', '/usr/bin/python3', str(COMMAND)],
        env=dict(os.environ, SSH_ORIGINAL_COMMAND=' '.join(args)), capture_output=True,
        text=True, timeout=180, check=False)
    return result.returncode, json.loads(result.stdout)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('instalacao_exige_console_administrativo')
    os.umask(0o077)
    source = COMMAND.read_text()
    if 'from operacao_contexto import atender' in source:
        raise RuntimeError('ja_instalado_consultar_contexto')
    marker = '    if not args or args[0] not in PERMITIDOS'
    if source.count('import sys\n') != 1 or source.count(marker) != 1:
        raise RuntimeError('fonte_atual_divergente')
    updated = source.replace('import sys\n', 'import sys\nfrom operacao_contexto import atender\n')
    updated = updated.replace(marker, '    consulta = atender(args, __file__)\n'
                              '    if consulta is not None:\n        return consulta\n' + marker)
    compile(updated, str(COMMAND), 'exec')
    subprocess.run(['/usr/bin/python3', '-m', 'unittest', 'test_operacao_contexto.py'],
                   cwd=HERE, check=True, timeout=30, capture_output=True)
    roots = [Path('/home/robo/.ssh/authorized_keys'), Path('/home/deploy/.ssh/authorized_keys'),
             Path('/opt/plataforma/docker-compose.yml'), Path('/opt/plataforma/traefik/dynamic/plataforma.yml')]
    for root in (Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z'),
                 Path('/usr/local/lib/meshcraft-publicador/atual').resolve()):
        roots += [root/'mercadopago/politica.json', root/'infra/mercadopago_congelado.py',
                  root/'docs/politica.json', root/'infra/docs_somente_admin.py', root/'infra/publicar.py']
    roots += list(Path('/opt/plataforma/env').glob('*.env'))
    anchors = {str(p): sha(p) for p in roots}
    command_stat = COMMAND.stat()
    before_rc, before = query(['operacao-inexistente'])
    if before_rc != 2 or not before.get('recusado'):
        raise RuntimeError('restricao_anterior_nao_confirmada')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/opt/plataforma/backups-de-codigo') / ('operacao-contexto-' + stamp)
    backup.mkdir(mode=0o700)
    shutil.copy2(COMMAND, backup/'robo_comando.py')
    (backup/'referencias.json').write_text(json.dumps(anchors))
    record = {'estado': 'backup_conferido', 'backup': str(backup),
              'inicio': datetime.now(timezone.utc).isoformat(), 'anterior_sha256': sha(COMMAND)}
    result_path = backup/'resultado.json'
    result_path.write_text(json.dumps(record))
    try:
        module = ACCESS/'operacao_contexto.py'
        if module.exists():
            shutil.copy2(module, backup/'operacao_contexto.py')
        temp_module = ACCESS/'operacao_contexto.py.candidate'
        shutil.copyfile(HERE/'operacao_contexto.py', temp_module)
        temp_module.chmod(0o644)
        os.replace(temp_module, module)
        candidate = COMMAND.with_suffix('.contexto-candidate')
        candidate.write_text(updated)
        os.chmod(candidate, command_stat.st_mode & 0o777)
        os.chown(candidate, command_stat.st_uid, command_stat.st_gid)
        os.replace(candidate, COMMAND)
        checks = {}
        for name, args in [('ajuda', ['ajuda']), ('contexto', ['contexto']),
                           ('operacoes', ['operacoes', '2']), ('servicos', ['servicos', 'listar'])]:
            rc, data = query(args)
            if rc:
                raise RuntimeError('consulta_falhou_' + name)
            checks[name] = True
            if name == 'operacoes':
                record['entregas_existentes'] = data['total']
                sample = data['operacoes'][-1]['id']
        rc, data = query(['retomar', sample])
        if rc or data['entrega']['id'] != sample:
            raise RuntimeError('retomada_falhou')
        checks['retomar'] = sample
        for args in (['retomar', '../etc/shadow'], ['contexto', 'exec'], ['operacoes', '51'], ['shell']):
            rc, data = query(args)
            if rc != 2 or not data.get('recusado'):
                raise RuntimeError('restricao_nao_preservada')
        if {str(p): sha(p) for p in roots} != anchors:
            raise RuntimeError('referencia_mudou_durante_instalacao')
        after_stat = COMMAND.stat()
        if (after_stat.st_uid, after_stat.st_gid, after_stat.st_mode) != (
                command_stat.st_uid, command_stat.st_gid, command_stat.st_mode):
            raise RuntimeError('permissoes_divergentes')
        with urllib.request.urlopen('https://meshcraft.top/', timeout=20) as response:
            if response.status != 200:
                raise RuntimeError('site_indisponivel')
        record.update(estado='instalado', fim=datetime.now(timezone.utc).isoformat(),
                      provas=checks, referencias_preservadas=len(anchors),
                      permissoes_preservadas=True, reinicios=0, site_http=200,
                      comando_sha256=sha(COMMAND), modulo_sha256=sha(module))
        result_path.write_text(json.dumps(record, indent=2))
        print(json.dumps(record))
    except Exception:
        candidate = COMMAND.with_suffix('.contexto-restore')
        shutil.copy2(backup/'robo_comando.py', candidate)
        os.chown(candidate, command_stat.st_uid, command_stat.st_gid)
        os.replace(candidate, COMMAND)
        record.update(estado='codigo_anterior_restaurado', fim=datetime.now(timezone.utc).isoformat())
        result_path.write_text(json.dumps(record, indent=2))
        print(json.dumps(record))
        raise


if __name__ == '__main__':
    main()
