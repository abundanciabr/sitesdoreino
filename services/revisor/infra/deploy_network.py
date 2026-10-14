"""Independent Revisor infrastructure delivery; no shared Compose/code changes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import shutil
import subprocess
import sys

ROOT = Path('/opt/plataforma')
OWN = ROOT / 'revisor'
PRIVATE = ROOT / 'revisor-private'


def run(args, data=None, timeout=60):
    p = subprocess.run(args, input=data, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('failed: ' + args[0] + ' (details retained privately)')
    return p.stdout


def freeze():
    root = Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
    policy = json.loads((root / 'mercadopago/politica.json').read_text())
    check = runpy.run_path(str(root / 'infra/mercadopago_congelado.py'))
    check['conferir_ambiente'](ROOT, policy)
    app = json.loads(run(['docker', 'inspect', 'plataforma-aplicacao-1']))[0]
    source = next(m['Source'] for m in app['Mounts'] if m['Destination'] == '/app')
    check['conferir_pacote'](source, app['Image'], policy)
    return app


def ip(container, network):
    return json.loads(run(['docker', 'inspect', container]))[0]['NetworkSettings']['Networks'][network]['IPAddress']


def add_rule(chain, args):
    check = subprocess.run(['iptables', '-w', '10', '-C', chain] + args, capture_output=True)
    if check.returncode:
        run(['iptables', '-w', '10', '-A', chain] + args)


def start():
    config = json.loads((OWN / 'network.json').read_text())
    # Add complete private chains before attaching them; never flush host rules.
    for chain in ['REVISOR-OUT', 'REVISOR-HOST']:
        p = subprocess.run(['iptables', '-w', '10', '-S', chain], capture_output=True)
        if p.returncode:
            run(['iptables', '-w', '10', '-N', chain])
    add_rule('REVISOR-OUT', ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
    add_rule('REVISOR-OUT', ['-s', '172.16.2.250/32', '-d', config['postgres_ip']+'/32', '-p', 'tcp', '--dport', '5432', '-j', 'ACCEPT'])
    add_rule('REVISOR-OUT', ['-s', '172.16.1.251/32', '-d', config['application_ip']+'/32', '-p', 'tcp', '--dport', '8000', '-j', 'ACCEPT'])
    add_rule('REVISOR-OUT', ['-s', '172.16.20.0/24', '-d', '172.16.20.0/24', '-j', 'ACCEPT'])
    add_rule('REVISOR-OUT', ['-j', 'DROP'])
    add_rule('REVISOR-HOST', ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
    add_rule('REVISOR-HOST', ['-j', 'DROP'])
    for source in ['172.16.20.0/24', '172.16.2.250/32', '172.16.1.251/32']:
        for chain, target in [('DOCKER-USER', 'REVISOR-OUT'), ('INPUT', 'REVISOR-HOST')]:
            args = ['-s', source, '-j', target]
            if subprocess.run(['iptables', '-w', '10', '-C', chain]+args, capture_output=True).returncode:
                run(['iptables', '-w', '10', '-I', chain, '1']+args)
    run(['docker', 'compose', '-p', 'revisor', '-f', str(OWN/'compose.yml'), 'up', '-d', '--pull', 'never'], timeout=90)


def prepare():
    os.umask(0o077)
    assert not (OWN/'network.json').exists(), 'already prepared: inspect/reuse, never rotate implicitly'
    app = freeze()
    network = json.loads(run(['docker', 'network', 'inspect', 'meshcraft-revisor']))[0]
    assert network['Internal'] and not network['EnableIPv6']
    for name, reserved in [('edge', '172.16.1.251'), ('interna', '172.16.2.250')]:
        n = json.loads(run(['docker', 'network', 'inspect', name]))[0]
        assert all(c['IPv4Address'].split('/')[0] != reserved for c in n['Containers'].values())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT/'backups-de-codigo'/('revisor-http-'+stamp)
    backup.mkdir(mode=0o700)
    originals = {}
    ownership = {}
    for name in ['identidade', 'alunos', 'cursos']:
        path = ROOT/'env'/(name+'.env')
        originals[name] = path.read_bytes()
        ownership[name] = (path.stat().st_uid, path.stat().st_gid)
        shutil.copy2(path, backup/path.name)
        os.chmod(backup/path.name, 0o600)
        assert not any(line.startswith(b'TOKENS_ACEITOS_REVISOR=') or line.startswith(b'TOKENS_COMPLETOS_REVISOR=') for line in originals[name].splitlines())
    (backup/'iptables.txt').write_text(run(['iptables-save']))
    (backup/'manifest.json').write_text(json.dumps({n:hashlib.sha256(v).hexdigest() for n,v in originals.items()}))
    (backup/'ownership.json').write_text(json.dumps(ownership))
    OWN.mkdir(mode=0o755, exist_ok=True)
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    app_ip = app['NetworkSettings']['Networks']['edge']['IPAddress']
    pg_ip = ip('plataforma-postgres-1', 'interna')
    site_id = next(line.split('=',1)[1] for line in originals['cursos'].decode().splitlines() if line.startswith('SITE_ID='))
    tokens = {name: secrets.token_hex(32) for name in originals}
    http = {'listen_ip': '172.16.20.3', 'upstream_ip': app_ip, 'site_id': site_id, 'client_token': secrets.token_hex(32), 'tokens': tokens}
    db = {'listen_ip': '172.16.20.2', 'upstream_ip': pg_ip}
    for name, data in [('http', http), ('db', db)]:
        path = PRIVATE/(name+'.json')
        path.write_text(json.dumps(data))
        os.chown(path, 65534, 65534)
        os.chmod(path, 0o400)
    image = run(['docker', 'image', 'inspect', 'python:3.12-slim', '--format', '{{.Id}}']).strip()
    services = {}
    for name, shared, shared_ip, own_ip, port in [('http', 'edge', '172.16.1.251', '172.16.20.3', 8080), ('db', 'interna', '172.16.2.250', '172.16.20.2', 5432)]:
        services[name] = {'image': image, 'container_name': 'meshcraft-revisor-'+name,
            'entrypoint': ['python', '-B', '/app/gateway.py', name], 'user': '65534:65534',
            'read_only': True, 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'restart': 'no', 'pids_limit': 32, 'mem_limit': '64m', 'cpus': .25,
            'sysctls': {'net.ipv4.ip_forward':'0', 'net.ipv6.conf.all.disable_ipv6':'1', 'net.ipv6.conf.default.disable_ipv6':'1'},
            'ulimits': {'nofile': {'soft':128,'hard':128}},
            'volumes': [str(OWN/'gateway.py')+':/app/gateway.py:ro', str(PRIVATE/(name+'.json'))+':/run/revisor/config.json:ro'],
            'networks': {'meshcraft-revisor': {'ipv4_address': own_ip}, shared: {'ipv4_address': shared_ip}},
            'logging': {'driver':'none'}}
    compose = {'services': services, 'networks': {name:{'external':True} for name in ['meshcraft-revisor','edge','interna']}}
    (OWN/'compose.yml').write_text(json.dumps(compose, indent=2))
    (OWN/'network.json').write_text(json.dumps({'application_ip':app_ip,'postgres_ip':pg_ip,'backup':str(backup)}))
    # Provider files are atomically replaced and the already-installed runtime
    # picks them up on its next normal, freeze-checked pipeline activation.
    for name, original in originals.items():
        path = ROOT/'env'/(name+'.env')
        assert path.read_bytes() == original, 'concurrent provider edit'
        suffix = '\nTOKENS_ACEITOS_REVISOR='+tokens[name]+'\n'
        if name == 'identidade':
            suffix += 'TOKENS_COMPLETOS_REVISOR='+tokens[name]+'\n'
        tmp = path.with_suffix('.revisor.tmp')
        tmp.write_bytes(original+suffix.encode())
        shutil.copystat(path,tmp)
        os.chown(tmp, *ownership[name])
        os.replace(tmp,path)
    freeze()
    unit = '''[Unit]
Description=Meshcraft Revisor private network intermediaries
Requires=docker.service
After=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 /opt/plataforma/revisor/deploy_network.py start
ExecStop=/usr/bin/docker compose -p revisor -f /opt/plataforma/revisor/compose.yml stop
TimeoutStartSec=120
[Install]
WantedBy=multi-user.target
'''
    unit_path = Path('/etc/systemd/system/meshcraft-revisor-network.service')
    assert not unit_path.exists()
    unit_path.write_text(unit)
    run(['systemctl','daemon-reload'])
    run(['systemctl','enable','--now','meshcraft-revisor-network.service'], timeout=120)
    (backup/'result.json').write_text(json.dumps({'backup':str(backup),'provider_pairs':'configured_pending_pipeline_reload','ai':'closed','disclosure':'pending'}))
    print(json.dumps({'backup':str(backup),'network_services':'started','provider_pairs':'configured_pending_pipeline_reload','freeze':'passed','ai':'closed'}))


if __name__ == '__main__':
    if sys.argv[1:] == ['start']:
        start()
    else:
        prepare()
