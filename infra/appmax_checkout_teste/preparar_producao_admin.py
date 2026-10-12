"""Install the public Appmax preview without changing the frozen application.

Run the reviewed source directory on the hosting console. Backup and rollback
reuse the already deployed checkout procedure. Existing databases are never
restored automatically; production starts with separate, empty order tables.
"""
from __future__ import annotations
import datetime as dt
import fcntl
import importlib.util
import json
import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path('/opt/plataforma')
TASK = ROOT / 'appmax-clones/checkout-roblox-20261009'
WEB = 'meshcraft-checkout-appmax-roblox-20261009'
PG = 'meshcraft-appmax-roblox-sandbox-postgres-20261009'
NETWORK = 'meshcraft-appmax-roblox-sandbox-20261009'
PANEL = 'https://meshcraft.top/checkout/curso-primeiros-passos-no-blender/producao'
BLOCK = '\nif os.environ.get("APPMAX_PRODUCTION_CHILD") != "1":\n    from production_admin import wrap\n    application = wrap(application, Path(__file__).resolve().parent / "assets")\n'


def run(args, *, input=None, timeout=30):
    result = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Operacao isolada falhou: ' + args[0])
    return result.stdout


def private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def http(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main(source):
    spec = importlib.util.spec_from_file_location('existing_backup', source / 'infra/appmax_checkout_teste/publicar_curso_blender.py')
    backup_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup_module)
    checker = backup_module.frozen_checker()
    policy = json.loads(backup_module.POLICY.read_text())
    approved = backup_module.prove_frozen(checker, policy)
    old = json.loads(run(['docker', 'inspect', WEB]))[0]
    if old['Image'] != policy['imagem']:
        raise RuntimeError('A imagem aprovada deve permanecer intacta')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = TASK / 'backups-producao-admin' / stamp
    server = TASK / 'servico/server.py'
    before = server.read_bytes()
    originals = {name: (TASK/'servico'/name).read_bytes() for name in ('server.py', 'production_admin.py', 'production_runtime.py', 'assets/homologacao.js') if (TASK/'servico'/name).exists()}
    backup_module.complete_backup(backup, approved, originals)
    production = TASK / 'producao'
    if production.exists():
        descriptor = os.open(backup/'producao-isolada.privado.tar.gz', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                archive.add(production, arcname='producao')
        for name in ('checkout', 'pagamentos'):
            backup_module.backup_database(production/'env'/(name+'.env'), PG, backup/('producao-'+name+'.dump'), clone=True)
    private(backup / 'container-antes.privado.json', json.dumps(old).encode())
    print(json.dumps({'etapa': 'backup_completo_conferido'}), flush=True)
    production.mkdir(mode=0o700, exist_ok=True)
    env_dir = production / 'env'
    env_dir.mkdir(mode=0o700, exist_ok=True)
    main_env = backup_module.env_values(ROOT / 'env/pagamentos.env')
    installations = json.loads(main_env.get('APPMAX_INSTALACOES') or '{}')
    current = [(app_id, value) for app_id, value in installations.items() if isinstance(value, dict) and backup_module.EXPECTED.get('slug') and 'cc06b8c3-043b-4c06-92c5-5ea624e00586' in value.get('sites', [])]
    if len(current) != 1:
        raise RuntimeError('O aplicativo existente nao foi identificado de forma unica')
    app_id, app = current[0]
    for path in (TASK / 'env-privado').glob('*.env'):
        target = env_dir / path.name
        if target.exists():
            continue
        values = backup_module.env_values(path)
        if path.stem in {'checkout', 'pagamentos'}:
            url = urllib.parse.urlparse(values['DATABASE_URL'])
            if url.hostname != 'postgres' or url.username != 'appmax_clone':
                raise RuntimeError('A base da copia precisa continuar isolada')
            name = url.path.lstrip('/') + '_producao'
            existing = run(['docker', 'exec', PG, 'psql', '-X', '-U', 'appmax_clone', '-d', 'postgres', '-Atc', "SELECT 1 FROM pg_database WHERE datname='" + name + "'"])
            if not existing.strip():
                run(['docker', 'exec', PG, 'createdb', '-U', 'appmax_clone', name])
                schema = run(['docker', 'exec', PG, 'pg_dump', '-U', 'appmax_clone', '-d', url.path.lstrip('/'), '--schema-only', '--no-owner', '--no-privileges'], timeout=60)
                run(['docker', 'exec', '-i', PG, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'appmax_clone', '-d', name], input=schema, timeout=60)
            values['DATABASE_URL'] = urllib.parse.urlunparse(url._replace(path='/' + name))
            values.update({'APPMAX_AUTH_URL': 'https://auth.appmax.com.br/oauth2/token', 'APPMAX_API_URL': 'https://api.appmax.com.br', 'APPMAX_MERCHANT_CLIENT_ID': '', 'APPMAX_MERCHANT_CLIENT_SECRET': '', 'APPMAX_EXTERNAL_ID': '', 'APPMAX_CARD_ENABLED_SITES': 'cc06b8c3-043b-4c06-92c5-5ea624e00586', 'APPMAX_PIX_ENABLED_SITES': 'cc06b8c3-043b-4c06-92c5-5ea624e00586'})
        if path.stem == 'pagamentos':
            values.update({k: main_env[k] for k in ('APPMAX_APP_CLIENT_ID', 'APPMAX_APP_CLIENT_SECRET')})
        if 'REDIS_URL' in values:
            values['REDIS_URL'] = 'redis://redis-producao:6379/0'
        if any(k.startswith('MP_') and v for k, v in values.items()):
            raise RuntimeError('Nenhuma credencial Mercado Pago deve entrar na copia')
        private(target, ('\n'.join(k + '=' + v for k, v in values.items()) + '\n').encode())
    if not (production / 'controle.privado').exists():
        private(production / 'controle.privado', secrets.token_bytes(32))
    if not (production / 'instalacao.json').exists():
        private(production / 'instalacao.json', json.dumps({'status': 'preparacao', 'app_id': app_id, 'app_uuid': app.get('app_uuid', ''), 'source_existing_application': True, 'price_cents': 2700}).encode())
    redis_name = 'meshcraft-appmax-producao-redis-20261012'
    existing = subprocess.run(['docker', 'inspect', redis_name], capture_output=True)
    if existing.returncode:
        run(['docker', 'run', '-d', '--name', redis_name, '--network', NETWORK, '--network-alias', 'redis-producao', '--restart', 'unless-stopped', '--mount', 'type=volume,source=meshcraft-appmax-producao-redis-20261012,target=/data', 'redis:7', 'redis-server', '--appendonly', 'yes'])
    else:
        run(['docker', 'start', redis_name])
    updated = before.decode()
    if 'from production_admin import wrap' not in updated:
        updated += BLOCK
    bootstrap = production / ('bootstrap-' + stamp + '.privado.env')
    private(bootstrap, ('\n'.join(old['Config']['Env']) + '\n').encode())
    previous_name = WEB + '-antes-' + stamp
    replacement_started = False
    try:
        for name in ('production_admin.py', 'production_runtime.py', 'assets/homologacao.js'):
            destination = TASK / 'servico' / name
            replacement = destination.with_name(destination.name + '.preparando-' + stamp)
            shutil.copyfile(source / 'services/checkout_appmax' / name, replacement)
            os.replace(replacement, destination)
        replacement = server.with_name('server.preparando-' + stamp + '.py')
        replacement.write_text(updated)
        os.replace(replacement, server)
        run(['docker', 'stop', WEB])
        run(['docker', 'rename', WEB, previous_name])
        first = next(n for n in old['NetworkSettings']['Networks'] if n != 'edge')
        command = ['docker', 'run', '-d', '--name', WEB, '--network', first, '--network-alias', WEB, '--restart', 'unless-stopped', '--env-file', str(bootstrap), '--workdir', old['Config']['WorkingDir'] or '/clone', '--entrypoint', old['Path']]
        for mount in old['Mounts']:
            if mount['Type'] != 'bind':
                raise RuntimeError('Montagem da copia nao reconhecida')
            command += ['--mount', 'type=bind,src=' + mount['Source'] + ',dst=' + mount['Destination'] + ('' if mount['RW'] else ',readonly')]
        if not any(mount['Destination'] == '/appmax-producao' for mount in old['Mounts']):
            command += ['--mount', 'type=bind,src=' + str(production) + ',dst=/appmax-producao']
        for port, bindings in (old['HostConfig'].get('PortBindings') or {}).items():
            for binding in bindings or []:
                command += ['-p', (binding.get('HostIp') or '127.0.0.1') + ':' + binding['HostPort'] + ':' + port]
        command += [old['Image']] + old['Args']
        run(command)
        replacement_started = True
        for network in old['NetworkSettings']['Networks']:
            if network != first:
                run(['docker', 'network', 'connect', '--alias', WEB, network, WEB])
        good = False
        for _ in range(20):
            try:
                public_status, public_body = http('https://meshcraft.top/checkout/curso-primeiros-passos-no-blender')
                admin_status, admin_body = http(PANEL)
                urls = [http(PANEL + suffix)[0] for suffix in ('/checkout', '/validacao', '/webhooks', '/retorno', '/autorizar')]
                if public_status == 200 and b'scripts.sandboxappmax.com.br' in public_body and admin_status == 200 and all(value == 200 for value in urls) and b'/admin/' not in admin_body:
                    good = True
                    break
            except Exception:
                pass
            time.sleep(1)
        if not good:
            raise RuntimeError('As URLs publicas sem login nao foram comprovadas')
        backup_module.prove_frozen(checker, policy)
        if http('https://meshcraft.top/')[0] != 200:
            raise RuntimeError('O site principal nao respondeu')
        print(json.dumps({'etapa': 'previa_instalada', 'url': PANEL, 'publico': 'sandbox_preservado', 'visitante_http': 200, 'login_necessario': False, 'mercadopago': 'conferido', 'cobrancas': 0, 'backup': str(backup)}), flush=True)
    except Exception:
        for name, content in originals.items():
            (TASK/'servico'/name).write_bytes(content)
        if replacement_started:
            run(['docker', 'stop', WEB])
            run(['docker', 'rename', WEB, WEB + '-falhou-' + stamp])
        if subprocess.run(['docker', 'inspect', previous_name], capture_output=True).returncode == 0:
            run(['docker', 'rename', previous_name, WEB])
            run(['docker', 'start', WEB])
        print(json.dumps({'codigo_anterior_restaurado': True, 'bancos_restaurados': False}), flush=True)
        raise


if __name__ == '__main__':
    try:
        with (ROOT/'publicacoes/.receber.lock').open('a') as receiving, (ROOT/'publicacoes/.ativacao.lock').open('a') as activation:
            fcntl.flock(receiving, fcntl.LOCK_EX)
            fcntl.flock(activation, fcntl.LOCK_EX)
            main(pathlib.Path(sys.argv[1]).resolve())
    except Exception as error:
        print(json.dumps({'preparacao_concluida': False, 'erro_tipo': type(error).__name__}), flush=True)
        raise SystemExit(1)
