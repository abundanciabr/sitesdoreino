"""Install only the manual sidecar and its exact URL, keeping the live app intact."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import urllib.error

BASE = Path('/opt/plataforma/manual-aluno-primeiros-dolares')
ROUTE = Path('/opt/plataforma/traefik/dynamic/manual-aluno-primeiros-dolares.yml')
NAME = 'meshcraft-manual-aluno-primeiros-dolares'


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def response(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


def main():
    src = Path(__file__).resolve().parent
    if ROUTE.exists() or run('docker', 'ps', '-a', '--filter', 'name=^/' + NAME + '$', '--format', '{{.Names}}'):
        raise SystemExit('A manual installation already exists. Inspect it before a new activation.')
    live = json.loads(run('docker', 'inspect', 'plataforma-aplicacao-1'))[0]
    mounts = {m['Destination']: m['Source'] for m in live['Mounts']}
    image = live['Image']
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = BASE / ('backup-' + stamp)
    backup.mkdir(mode=0o700)
    with tarfile.open(backup / 'rotas-anteriores.tar.gz', 'w:gz') as archive:
        archive.add(ROUTE.parent, arcname='dynamic')
    code = BASE / ('codigo-' + stamp)
    shutil.copytree(src, code, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    with tarfile.open(backup / 'manual-codigo.tar.gz', 'w:gz') as archive:
        archive.add(code, arcname='manual')
    metadata = {'image': image, 'application_source': mounts['/app'], 'manual_source': str(code),
                'backup': str(backup), 'previous_manual_route': False, 'database_changes': False,
                'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code.iterdir() if p.is_file()}}
    (backup / 'registro.json').write_text(json.dumps(metadata, indent=2))
    command = ['docker', 'create', '--name', NAME, '--restart', 'unless-stopped', '--network', 'interna',
               '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '512m', '--cpus', '1',
               '--tmpfs', '/tmp:rw,nosuid,noexec,size=32m', '-e', 'APLICACAO_ENV_DIR=/run/plataforma-env',
               '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONUNBUFFERED=1',
               '-v', mounts['/app'] + ':/app:ro', '-v', mounts['/run/plataforma-env'] + ':/run/plataforma-env:ro',
               '-v', str(code) + ':/manual:ro', '-w', '/manual', '--entrypoint', 'python', image, '/manual/serve.py']
    # The original image, original modules and original env stay read-only and unchanged.
    run(*command)
    run('docker', 'network', 'connect', 'edge', NAME)
    run('docker', 'start', NAME)
    route_written = False
    try:
        probe = "import urllib.request,urllib.error; r=urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=5); assert r.status==200"
        for _ in range(25):
            try:
                run('docker', 'exec', NAME, 'python', '-c', probe)
                break
            except subprocess.CalledProcessError:
                time.sleep(2)
        else:
            raise RuntimeError('manual healthcheck failed')
        run('docker', 'exec', NAME, 'python', '-m', 'unittest', 'discover', '-s', '/manual', '-p', 'test_*.py')
        # Exercise the real enrollment and journey code before adding the public route.
        run('docker', 'exec', NAME, 'python', '/manual/verify_runtime.py')
        route = {'http': {'routers': {'manual-aluno-primeiros-dolares': {
            'rule': 'Host(`meshcraft.top`) && (Path(`/manual-do-aluno-primeiros-dolares`) || Path(`/manual-do-aluno-primeiros-dolares/`))',
            'entryPoints': ['websecure'], 'tls': {}, 'priority': 1500,
            'service': 'manual-aluno-primeiros-dolares', 'middlewares': ['seguranca@file']}},
            'services': {'manual-aluno-primeiros-dolares': {'loadBalancer': {'servers': [{'url': 'http://' + NAME + ':8000'}]}}}}}
        temporary = ROUTE.with_suffix('.tmp')
        temporary.write_text(json.dumps(route))
        os.replace(temporary, ROUTE)
        route_written = True
        for _ in range(15):
            status, body, headers = response('https://meshcraft.top/manual-do-aluno-primeiros-dolares')
            if status == 401 and 'Entrar na minha conta' in body and 'no-store' in headers.get('Cache-Control', ''):
                break
            time.sleep(2)
        else:
            raise RuntimeError('public visitor response failed')
        metadata['activated'] = True
        metadata['anonymous_http_status'] = status
        (BASE / 'ativo.json').write_text(json.dumps(metadata, indent=2))
        # Keep an independent watcher: publication failures remove only this new route.
        subprocess.Popen(['python3', str(code / 'watch.py'), str(backup)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(json.dumps({'activated': True, 'backup': str(backup), 'url': 'https://meshcraft.top/manual-do-aluno-primeiros-dolares',
                          'tests': 14, 'visitor_status': status, 'image_unchanged': image == live['Image']}))
    except Exception:
        if route_written and ROUTE.exists():
            os.replace(ROUTE, backup / 'rota-retirada-apos-falha.json')
        run('docker', 'stop', NAME)
        raise


if __name__ == '__main__':
    main()
