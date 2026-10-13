#!/usr/bin/env python3
"""Instalação pelo console: backup privado e reversão automática do canal em falha."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ACCESS = Path('/usr/local/lib/meshcraft-acessos')
COMMAND = ACCESS / 'robo_comando.py'
BASE = Path('/usr/local/lib/meshcraft-servicos')
STATE = Path('/var/lib/meshcraft-servicos')
SYSTEMD = Path('/etc/systemd/system')
UNITS = {
    'meshcraft-servicos.socket': '''[Unit]
Description=Diagnostico operacional dos robos
[Socket]
ListenStream=/run/meshcraft-servicos.sock
SocketUser=root
SocketGroup=robo
SocketMode=0660
RemoveOnStop=yes
[Install]
WantedBy=sockets.target
''',
    'meshcraft-servicos.service': '''[Unit]
Description=Saude, eventos sem texto privado e reinicios especificos
Requires=meshcraft-servicos.socket
After=meshcraft-servicos.socket
[Service]
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-servicos/servicos_manutencao.py
User=root
Group=root
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/meshcraft-servicos
Restart=on-failure
MemoryMax=192M
TasksMax=32
'''
}


def run(args, timeout=60):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def anchors():
    root = Path('/opt/plataforma')
    fixed = Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
    current = Path('/usr/local/lib/meshcraft-publicador/atual').resolve(strict=True)
    paths = [root/'traefik/dynamic/plataforma.yml', root/'docker-compose.yml', root/'bin/plataforma',
             Path('/home/robo/.ssh/authorized_keys'), Path('/home/deploy/.ssh/authorized_keys')]
    for base in (fixed, current):
        for relative in ('mercadopago/politica.json', 'infra/mercadopago_congelado.py',
                         'docs/politica.json', 'infra/docs_somente_admin.py', 'infra/publicar.py'):
            paths.append(base/relative)
    paths += list((root/'env').glob('*.env'))
    return {str(p): sha(p) for p in paths}


def site():
    with urllib.request.urlopen('https://meshcraft.top/', timeout=30) as r:
        if r.status != 200:
            raise RuntimeError('site_indisponivel')


def request(args):
    env = dict(os.environ, SSH_ORIGINAL_COMMAND=' '.join(args))
    r = subprocess.run(['/usr/sbin/runuser', '-u', 'robo', '--', '/usr/bin/python3', str(COMMAND)],
                       env=env, capture_output=True, text=True, timeout=180)
    return r.returncode, json.loads(r.stdout)


def patch_command(source):
    old = '    pedido = json.dumps(args, ensure_ascii=True).encode()'
    new = '''    destino = SOCKET
    if args[0] == "servicos":
        destino = "/run/meshcraft-servicos.sock"
        args = args[1:]
    pedido = json.dumps(args, ensure_ascii=True).encode()'''
    if source.count(old) != 1 or source.count('canal.connect(SOCKET)') != 1:
        raise RuntimeError('comando_atual_divergente')
    allowed = 'PERMITIDOS = {"entregar", "consultar", "estado", "analisador"}'
    if source.count(allowed) != 1:
        raise RuntimeError('permissoes_atuais_divergentes')
    source = source.replace(allowed, allowed[:-1] + ', "servicos"}')
    source = source.replace(old, new).replace('canal.connect(SOCKET)', 'canal.connect(destino)')
    compile(source, 'robo_comando.py', 'exec')
    return source


def main():
    if os.geteuid() != 0:
        raise RuntimeError('console_root_necessario')
    os.umask(0o077)
    if BASE.exists() or any((SYSTEMD/n).exists() for n in UNITS):
        raise RuntimeError('extensao_ja_existe')
    run(['/usr/bin/python3', '-m', 'unittest', 'test_servicos_manutencao.py'])
    modified = patch_command(COMMAND.read_text())
    site()
    before = anchors()
    # Imagens em uso são observadas sem expor ambiente, mounts ou configurações.
    images_before = run(['/usr/bin/docker', 'ps', '--no-trunc', '--format', '{{.Names}} {{.Image}}']).stdout
    if '--instalar' not in sys.argv:
        print(json.dumps({'estado': 'preparado', 'testes': 8, 'referencias_conferidas': len(before),
                          'comando_atual_sha256': sha(COMMAND), 'site_http': 200,
                          'reiniciaveis': ['robo', 'analisador']}))
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/opt/plataforma/backups-de-codigo') / ('canal-servicos-' + stamp)
    backup.mkdir(mode=0o700)
    shutil.copy2(COMMAND, backup/'robo_comando.py')
    (backup/'referencias.json').write_text(json.dumps(before))
    with tarfile.open(backup/'canal-anterior.tar.gz', 'w:gz') as tar:
        tar.add(ACCESS, arcname='meshcraft-acessos')
        for name in ('meshcraft-robo.socket', 'meshcraft-robo.service'):
            tar.add(SYSTEMD/name, arcname=name)
    with tarfile.open(backup/'canal-anterior.tar.gz') as tar:
        for member in tar:
            if member.isfile():
                stream = tar.extractfile(member)
                while stream.read(1024*1024):
                    pass
    BASE.mkdir(mode=0o755)
    STATE.mkdir(mode=0o700)
    shutil.copyfile(HERE/'servicos_manutencao.py', BASE/'servicos_manutencao.py')
    (BASE/'servicos_manutencao.py').chmod(0o644)
    try:
        for name, text in UNITS.items():
            (SYSTEMD/name).write_text(text)
            (SYSTEMD/name).chmod(0o644)
        run(['/usr/bin/systemd-analyze', 'verify', *[str(SYSTEMD/n) for n in UNITS]])
        run(['/usr/bin/systemctl', 'daemon-reload'])
        run(['/usr/bin/systemctl', 'enable', '--now', 'meshcraft-servicos.socket'])
        candidate = COMMAND.with_suffix('.candidate')
        candidate.write_text(modified)
        candidate.chmod(0o755)
        os.replace(candidate, COMMAND)
        checks = {}
        for name, args in (
            ('listar', ['servicos', 'listar']), ('saude', ['servicos', 'saude']),
            ('logs', ['servicos', 'logs', 'analisador', '60', '20']),
            ('analisador', ['analisador', 'consultar']), ('entregas', ['estado']),
            ('reinicio', ['servicos', 'reiniciar', 'analisador']),
            ('apos_reinicio', ['analisador', 'consultar']),
        ):
            code, data = request(args)
            if code or (name == 'reinicio' and data.get('estado') != 'concluida'):
                raise RuntimeError('prova_falhou_' + name)
            checks[name] = {'codigo': code, 'comprovado': True}
            if name == 'reinicio':
                checks[name]['resultado'] = data
        for args in (['servicos', 'reiniciar', 'aplicacao'], ['servicos', 'logs', '/etc/shadow', '1', '1']):
            code, data = request(args)
            if code != 2 or not data.get('recusado'):
                raise RuntimeError('restricao_nao_preservada')
        site()
        if anchors() != before:
            raise RuntimeError('referencias_alteradas')
        images_after = run(['/usr/bin/docker', 'ps', '--no-trunc', '--format', '{{.Names}} {{.Image}}']).stdout
        if images_after != images_before:
            raise RuntimeError('imagens_em_execucao_alteradas')
        evidence = {'estado': 'instalado', 'backup': str(backup), 'provas': checks,
                    'referencias_preservadas': len(before), 'imagens_preservadas': True, 'site_http': 200,
                    'observado_em': datetime.now(timezone.utc).isoformat()}
        (STATE/'instalacao.json').write_text(json.dumps(evidence))
        print(json.dumps(evidence))
    except Exception:
        shutil.copy2(backup/'robo_comando.py', COMMAND)
        subprocess.run(['/usr/bin/systemctl', 'disable', '--now', 'meshcraft-servicos.socket'], capture_output=True)
        subprocess.run(['/usr/bin/systemctl', 'stop', 'meshcraft-servicos.service'], capture_output=True)
        print(json.dumps({'estado': 'canal_anterior_restaurado', 'backup': str(backup)}))
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"erro":"instalacao_nao_concluida; detalhes privados preservados no servidor"}')
        sys.exit(1)
