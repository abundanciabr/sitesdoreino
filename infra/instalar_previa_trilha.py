#!/usr/bin/env python3
"""Instala a candidata privada sem trocar a aplicaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o usada pelos alunos.

Segredos continuam no servidor. NÃƒÆ’Ã‚Â£o modifica main, Traefik, checkout nem as
bases atuais. Em falha, para somente processos novos e preserva os dados.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path('/opt/plataforma')
FIXED = Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
TRUSTED = Path('/usr/local/lib/meshcraft-publicador/atual')
EXECUTOR = ROOT / 'analise-pratica/20261008-v3/executor_host.py'
ANALYZER_ID = 'sha256:e067accf6a9183c27f66c7181fe27659dba607d7f79a285acb08cb2f913b4a9c'
EXECUTOR_HASH = '4a1983010ac0327e90f23745020099d79dd9f32edb4b676f3b760db2680665f8'
ISOLATED = ('gamificacao', 'cursos', 'encomendas')
NAMES = ('meshcraft-trilha-previa', 'meshcraft-trilha-previa-pg', 'meshcraft-trilha-previa-redis')

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def run(args, *, log=None, timeout=900, input=None):
    r = subprocess.run([str(x) for x in args], input=input, stdout=log or subprocess.PIPE,
                       stderr=log or subprocess.PIPE, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError('operacao_falhou_' + Path(str(args[0])).name)
    return r.stdout or ''

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def anchors():
    paths = [ROOT / 'docker-compose.yml', ROOT / '.env',
             ROOT / 'traefik/dynamic/plataforma.yml',
             FIXED / 'mercadopago/politica.json', FIXED / 'infra/mercadopago_congelado.py',
             TRUSTED / 'docs/politica.json', TRUSTED / 'infra/docs_somente_admin.py',
             Path('/home/robo/.ssh/authorized_keys'), Path('/home/deploy/.ssh/authorized_keys')]
    paths += sorted((ROOT / 'env').glob('*.env'))
    result = {str(p): digest(p) for p in paths if p.is_file()}
    # O verificador independente já normaliza somente o destino variável do Funil.
    route = ROOT / 'traefik/dynamic/plataforma.yml'
    result[str(route)] = module('mp_rotas', FIXED / 'infra/mercadopago_congelado.py').capturar_rotas(ROOT)
    return result

def parse_env(path):
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, sep, value = line.partition('=')
        if sep:
            value = value.strip()
            if value[:1] in ('"', "'") and value[-1:] == value[:1]:
                value = value[1:-1]
            elif ' #' in value:
                value = value.split(' #', 1)[0].rstrip()
            values[key.strip()] = value
    return values

def env_file(path, values):
    if any('\n' in str(v) or '\r' in str(v) for v in values.values()):
        raise RuntimeError('ambiente_multilinha_inesperado')
    path.write_text(''.join(k + '=' + str(v) + '\n' for k, v in values.items()))
    path.chmod(0o600)

def wait_pg(log):
    for _ in range(60):
        r = subprocess.run(['docker', 'exec', NAMES[1], 'pg_isready', '-U', 'trilha_previa'],
                           stdout=log, stderr=log)
        if r.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError('postgres_privado_indisponivel')

def montar_privado(codigo, fontes, imagem, registro):
    """Mesmo transformador confiável, com espaço para os assets 3D da candidata."""
    nome = 'meshcraft-montagem-previa-' + uuid.uuid4().hex
    preparar = TRUSTED / 'preparar-aplicacao.py'
    if not preparar.is_file():
        raise RuntimeError('transformador_confiavel_ausente')
    comando = ['docker', 'create', '--name', nome, '--network', 'none',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--user', '65532:65532', '--memory', '4096m', '--cpus', '1',
               '--pids-limit', '96', '--tmpfs', '/tmp:rw,nosuid,nodev,size=2048m',
               '-v', str(fontes) + ':/fontes:ro',
               '-v', str(preparar) + ':/ferramentas/preparar.py:ro',
               '--entrypoint', 'python', imagem, '-c',
               "import runpy,sys,time; sys.argv=['/ferramentas/preparar.py','--origem','/fontes','--destino','/tmp/modules']; runpy.run_path('/ferramentas/preparar.py',run_name='__main__'); print('MONTAGEM-CONCLUIDA',flush=True); time.sleep(300)"]
    try:
        run(comando, log=registro)
        run(['docker', 'start', nome], log=registro)
        for _ in range(180):
            logs = subprocess.check_output(['docker', 'logs', nome], stderr=subprocess.STDOUT)
            if b'MONTAGEM-CONCLUIDA' in logs:
                processo = subprocess.Popen(['docker', 'exec', nome, 'tar', '-C', '/tmp', '-cf', '-', 'modules'],
                                            stdout=subprocess.PIPE, stderr=registro)
                with tarfile.open(fileobj=processo.stdout, mode='r|') as arquivo:
                    arquivo.extractall(codigo, filter='data')
                processo.stdout.close()
                if processo.wait() != 0:
                    raise RuntimeError('saida_da_montagem_indisponivel')
                return
            if run(['docker', 'inspect', '--format', '{{.State.Running}}', nome]).strip() != 'true':
                registro.write(logs.decode('utf-8', errors='replace')[-2000:])
                raise RuntimeError('montagem_privada_falhou')
            time.sleep(1)
        raise RuntimeError('montagem_privada_excedeu_prazo')
    finally:
        # Somente o contêiner temporário desta chamada, sem volume nem dado persistente.
        subprocess.run(['docker', 'rm', '-f', nome], stdout=registro, stderr=registro)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch('[0-9a-f]{40}', args.commit):
        raise RuntimeError('console_e_commit_obrigatorios')
    os.umask(0o077)
    sys.path.insert(0, str(TRUSTED / 'infra'))
    mp = module('mp_confiavel', FIXED / 'infra/mercadopago_congelado.py')
    policy = json.loads((FIXED / 'mercadopago/politica.json').read_text())
    mp.conferir_ambiente(ROOT, policy)
    state = json.loads((ROOT / 'publicacoes/aplicacao.json').read_text())
    approved = state['aprovada']
    if approved['sha'] != state['atual']:
        raise RuntimeError('aplicacao_atual_nao_aprovada')
    image = approved['imagem']
    live = Path(approved['codigo'])
    mp.conferir_pacote(live, image, policy)
    if run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}']).strip() != image:
        raise RuntimeError('imagem_aprovada_divergiu')
    if digest(EXECUTOR) != EXECUTOR_HASH:
        raise RuntimeError('executor_preservado_divergiu')
    if run(['docker', 'image', 'inspect', 'meshcraft-analise-pratica:20261008-v3',
            '--format', '{{.Id}}']).strip() != ANALYZER_ID:
        raise RuntimeError('analisador_preservado_divergiu')
    for name in NAMES:
        if subprocess.run(['docker', 'inspect', name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError('previa_ja_existe_preservada')
    unit = 'meshcraft-trilha-previa-analisador.service'
    unit_path = Path('/etc/systemd/system') / unit
    if unit_path.exists():
        raise RuntimeError('unidade_privada_ja_existe')
    before = anchors()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ROOT / 'previas/trilha' / (args.commit + '-' + stamp)
    backup = ROOT / 'backups-de-codigo' / ('trilha-previa-' + stamp)
    base.mkdir(parents=True, mode=0o700)
    backup.mkdir(mode=0o700)
    created = []
    with (base / 'instalacao.log').open('w') as log:
        try:
            from armazenamento_codigo import snapshot, image_archive
            from ensaio_entregas import _imagem_id_tar
            store = ROOT / 'objetos-de-codigo-previas'
            snapshot(store, {'codigo': live, 'env': ROOT / 'env', 'dotenv': ROOT / '.env',
                      'compose': ROOT / 'docker-compose.yml', 'traefik': ROOT / 'traefik',
                      'publicacoes': ROOT / 'publicacoes/aplicacao.json'},
                     backup / 'codigo-configuracoes.json', {'aprovada': approved['sha']})
            image_archive(store, image, backup / 'imagem.tar', _imagem_id_tar, log)
            env = dict(os.environ, PLATAFORMA_DIR=str(ROOT), PRESERVAR_COPIAS='1',
                       PASTA_DOS_BACKUPS=str(backup / 'bancos'))
            r = subprocess.run(['bash', str(TRUSTED / 'infra/backup-do-banco.sh'),
                                'trilha-previa'], env=env, stdout=log, stderr=log, timeout=900)
            if r.returncode:
                raise RuntimeError('backup_dos_bancos_falhou')
            (backup / 'referencias.json').write_text(json.dumps(before, sort_keys=True))
            print('BACKUP_RECUPERAVEL_OK', str(backup), flush=True)
            source = base / 'fonte'
            source.mkdir(mode=0o755)
            git = subprocess.Popen(['git', '-c', 'safe.directory=' + str(ROOT / 'codigo/repo.git'),
                                    '--git-dir', str(ROOT / 'codigo/repo.git'), 'archive', args.commit],
                                    stdout=subprocess.PIPE, stderr=log)
            with tarfile.open(fileobj=git.stdout, mode='r|') as archive:
                archive.extractall(source, filter='data')
            git.stdout.close()
            if git.wait() != 0:
                raise RuntimeError('exportacao_git_falhou')
            for p in [source, *source.rglob('*')]:
                if p.is_symlink():
                    raise RuntimeError('fonte_com_link_recusada')
                p.chmod(0o755 if p.is_dir() or p.stat().st_mode & 0o111 else 0o644)
            mp.conferir_fontes(source, policy)
            package = base / 'codigo'
            shutil.copytree(source / 'services/aplicacao', package)
            montar_privado(package, source / 'services', image, log)
            shutil.copytree(source / 'documentos', package / 'documentos_embutidos')
            (package / 'infra').mkdir(mode=0o755)
            for file in ('previa_trilha.py', 'previa_trilha_transporte.py'):
                shutil.copy2(source / 'infra' / file, package / 'infra' / file)
            mp.conferir_pacote(package, image, policy)
            envdir = base / 'env'
            envdir.mkdir(mode=0o700)
            pg_password = secrets.token_hex(32)
            redis_url = 'redis://' + NAMES[2] + ':6379/'
            for original in sorted((ROOT / 'env').glob('*.env')):
                service = original.stem
                private_dsn = ('postgresql://trilha_previa:' + pg_password + '@' +
                               NAMES[1] + ':5432/' + service + '_db')
                if service in (*ISOLATED, 'admin', 'funil', 'identidade', 'alunos', 'catalogo'):
                    values = parse_env(original)
                else:
                    # CÃƒÂ©lulas sem papel na prÃƒÂ©via nÃƒÂ£o recebem segredo nem base real.
                    values = {'DJANGO_SECRET_KEY': secrets.token_hex(32),
                              'DATABASE_URL': private_dsn}
                if service in ('identidade', 'alunos', 'catalogo'):
                    url = urlsplit(values['DATABASE_URL'])
                    query = dict(parse_qsl(url.query, keep_blank_values=True))
                    query['options'] = (query.get('options', '') +
                                        ' -c default_transaction_read_only=on').strip()
                    values['DATABASE_URL'] = urlunsplit(url._replace(query=urlencode(query)))
                values['REDIS_STREAMS_URL'] = redis_url + '0'
                values['HUEY_REDIS_URL'] = redis_url + str({'gamificacao': 1, 'cursos': 9,
                                                         'encomendas': 11}.get(service, 15))
                values['SITE_ERRORS_REDIS_URL'] = redis_url + '0'
                if service in ISOLATED:
                    values['DATABASE_URL'] = private_dsn
                if service == 'encomendas':
                    values['MARKETPLACE_UPLOAD_ROOT'] = '/arquivos/encomendas/marketplace'
                env_file(envdir / original.name, values)
            env_file(base / 'postgres.env', {'POSTGRES_USER': 'trilha_previa',
                                            'POSTGRES_PASSWORD': pg_password})
            uploads = base / 'arquivos'
            uploads.mkdir(mode=0o700)
            pgvol = 'meshcraft-trilha-previa-pg-' + stamp.lower()
            redisvol = 'meshcraft-trilha-previa-redis-' + stamp.lower()
            run(['docker', 'run', '-d', '--name', NAMES[1], '--network', 'interna',
                 '--restart', 'unless-stopped', '--env-file', base / 'postgres.env',
                 '-v', pgvol + ':/var/lib/postgresql/data', '--memory', '512m',
                 '--cpus', '.5', 'postgres:17'], log=log)
            created.append(NAMES[1])
            wait_pg(log)
            for service in ISOLATED:
                run(['docker', 'exec', NAMES[1], 'psql', '-U', 'trilha_previa', '-d', 'postgres',
                     '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE DATABASE ' + service + '_db'], log=log)
            run(['docker', 'run', '-d', '--name', NAMES[2], '--network', 'interna',
                 '--restart', 'unless-stopped', '-v', redisvol + ':/data',
                 '--memory', '256m', '--cpus', '.25', 'redis:7',
                 'redis-server', '--appendonly', 'yes'], log=log)
            created.append(NAMES[2])
            mounts = ['-v', str(package) + ':/app:ro', '-v', str(envdir) + ':/run/previa-env:ro',
                      '-v', str(uploads) + ':/arquivos/encomendas',
                      '-v', str(ROOT / 'admin-dados') + ':/opt/plataforma/admin-dados:ro',
                      '-v', str(ROOT / 'admin-midia') + ':/opt/plataforma/admin-midia:ro']
            common = ['--network', 'interna', '--cap-drop', 'ALL', '--security-opt',
                      'no-new-privileges', '--memory', '2048m', '--cpus', '1.5',
                      '--pids-limit', '128', '-e', 'APLICACAO_ENV_DIR=/run/previa-env',
                      '-e', 'PYTHONDONTWRITEBYTECODE=1', '-w', '/app', *mounts]
            migrate = """import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from config.runtime import load_original_settings,install_contextual_settings,serving
load_original_settings();install_contextual_settings()
for s in ('gamificacao','cursos','encomendas'):
 if settings.DATABASES[s]['HOST'] != 'meshcraft-trilha-previa-pg': raise RuntimeError('banco_nao_privado')
 with serving(s): call_command('migrate',database=s,interactive=False,verbosity=1)
print('MIGRACOES_SOMENTE_BASES_PRIVADAS_OK')
"""
            run(['docker', 'run', '--rm', *common, '--entrypoint', 'python', image,
                 '-c', migrate], log=log)
            private_root = uploads / 'marketplace'
            private_root.mkdir(mode=0o700, exist_ok=True)
            unit_path.write_text('[Unit]\nDescription=Analisador dos anexos da previa privada da Trilha\n'
                'After=docker.service\n[Service]\nType=simple\n'
                'ExecStart=/usr/bin/python3 ' + str(EXECUTOR) + ' --root ' + str(private_root) + '\n'
                'Restart=on-failure\nUMask=0077\nNoNewPrivileges=yes\nPrivateTmp=yes\n'
                'ProtectSystem=strict\nProtectHome=yes\nReadWritePaths=' + str(uploads) + '\n'
                '[Install]\nWantedBy=multi-user.target\n')
            unit_path.chmod(0o644)
            run(['systemctl', 'daemon-reload'], log=log)
            run(['systemctl', 'enable', '--now', unit], log=log)
            run(['docker', 'run', '-d', '--name', NAMES[0], '--network-alias', 'trilha-previa',
                 '--restart', 'unless-stopped', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
                 *common, '--entrypoint', 'python', image, '-m', 'uvicorn',
                 'infra.previa_trilha:application', '--host', '0.0.0.0', '--port', '8000',
                 '--lifespan', 'on', '--no-access-log'], log=log)
            created.append(NAMES[0])
            # A cÃ©lula Funil vigente fica em sua rede privada, sem acesso ao PG.
            run(['docker', 'network', 'connect', '--alias', 'trilha-previa',
                 'meshcraft-funil', NAMES[0]], log=log)
            probe = """import urllib.request,urllib.error
r=urllib.request.Request('http://127.0.0.1:8000/trilha/previa/',headers={'Host':'meshcraft.top'})
try: urllib.request.urlopen(r,timeout=10); raise RuntimeError('previa_sem_autenticacao')
except urllib.error.HTTPError as e:
 if e.code not in (403,404): raise
print('PREVIA_REJEITA_SEM_SESSAO')
"""
            for attempt in range(30):
                r = subprocess.run(['docker', 'exec', NAMES[0], 'python', '-c', probe],
                                   stdout=log, stderr=log)
                if r.returncode == 0:
                    break
                time.sleep(2)
            else:
                raise RuntimeError('porta_privada_nao_comprovada')
            mp.conferir_ambiente(ROOT, policy)
            mp.conferir_pacote(live, image, policy)
            if anchors() != before:
                raise RuntimeError('referencias_atuais_alteradas')
            metadata = {'estado': 'privada_pronta', 'commit': args.commit,
                        'base': str(base), 'backup': str(backup), 'imagem': image,
                        'aprovada_alunos': approved['sha'], 'bancos': list(ISOLATED),
                        'url': 'https://meshcraft.top/trilha/previa/', 'alunos_liberados': False}
            (base / 'resultado.json').write_text(json.dumps(metadata, sort_keys=True))
            print(json.dumps(metadata, ensure_ascii=False), flush=True)
        except Exception:
            if unit_path.exists():
                subprocess.run(['systemctl', 'stop', unit], stdout=log, stderr=log)
            for name in reversed(created):
                subprocess.run(['docker', 'stop', name], stdout=log, stderr=log)
            print('PREVIA_NAO_ATIVADA_DADOS_PRESERVADOS', str(base), flush=True)
            raise

if __name__ == '__main__':
    main()
