"""Canal de prévias sem credenciais: planos declarativos, código em sandbox, estado durável."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import socket
import struct
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path('/opt/plataforma/previas/operacionais')
CONFIG = Path('/usr/local/lib/meshcraft-previas/config.json')
SOCKET = '/run/meshcraft-previas.sock'
SHA = re.compile(r'[0-9a-f]{40}\Z')
ID = re.compile(r'[0-9a-f]{24}\Z')
NAME = re.compile(r'[a-z][a-z0-9-]{2,39}\Z')
TERMINAL = {'concluida', 'recuperada', 'recusada'}
LOCK = threading.RLock()
PREFIXES = ('services/', 'packages/', 'infra/previas/exemplos/')
PROTECTED = ('services/aplicacao/', 'services/checkout/', 'services/pagamentos/',
             'packages/site_errors/', 'packages/outbox-relay/',
             'services/cursos/apps/core/templatetags/botoes_admin.py',
             'services/cursos/apps/core/views.py',
             'services/cursos/apps/core/templates/cursos/catalogo.html',
             'services/cursos/apps/core/templates/cursos/mapa.html',
             'services/quiz/apps/quiz/models.py', 'services/quiz/apps/quiz/editor.py',
             'services/quiz/apps/quiz/nps', 'services/quiz/apps/quiz/participacao.py')
EXTENSIONS = {'.py', '.js', '.mjs', '.cjs', '.html', '.css', '.json', '.txt'}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    tmp = path.with_suffix(path.suffix + '.new')
    with tmp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.chmod(0o644)
    os.replace(tmp, path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def safe_path(value):
    if not isinstance(value, str) or len(value) > 180 or not re.fullmatch(r'[A-Za-z0-9_./-]+', value):
        return False
    p = PurePosixPath(value)
    return (not p.is_absolute() and str(p) == value and all(x not in {'.', '..'} and not x.startswith('.') for x in p.parts)
            and p.suffix in EXTENSIONS and not any(x in value.lower() for x in
            ('secret', 'credential', 'privad', 'satisfacao', 'satisfação', 'mercadopago', 'pagamento', 'checkout')))


def plan_valid(plan):
    if not isinstance(plan, dict) or set(plan) != {'runtime', 'files', 'test', 'page'}:
        return False
    files = plan['files']
    if plan['runtime'] not in {'node', 'python'} or not isinstance(files, dict) or not 1 <= len(files) <= 80:
        return False
    for target, source in files.items():
        if not safe_path(target) or not safe_path(source) or not source.startswith(PREFIXES) or source.startswith(PROTECTED):
            return False
        if target.startswith(('node_modules/', '__pycache__/')) or '/config/' in source or '/migrations/' in source:
            return False
    test = plan['test']
    return (test in files and test.startswith('tests/') and
            PurePosixPath(test).suffix in ({'.js', '.cjs', '.mjs'} if plan['runtime'] == 'node' else {'.py'})
            and plan['page'] in files and plan['page'].endswith('.html'))


def valid(args):
    if not isinstance(args, list) or not all(type(a) is str for a in args):
        return False
    if args == ['listar'] or args == ['ajuda']:
        return True
    if len(args) == 2 and args[0] in {'consultar', 'retomar'}:
        return bool(ID.fullmatch(args[1]))
    return (len(args) == 4 and args[0] == 'aplicar' and bool(NAME.fullmatch(args[1]))
            and bool(SHA.fullmatch(args[2])) and (args[3] == 'nova' or bool(ID.fullmatch(args[3]))))


def fetch(commit, path):
    url = 'https://raw.githubusercontent.com/abundanciabr/sitesdoreino/' + commit + '/' + path
    with urllib.request.urlopen(url, timeout=25) as response:
        if response.url != url:
            raise ValueError('origem_divergente')
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError('arquivo_grande')
    body.decode('utf-8')
    return body


def public_state():
    operations = [read(p) for p in (ROOT/'operations').glob('*.json')]
    operations.sort(key=lambda r: r['inicio'], reverse=True)
    result = {'observado_em': now(), 'previas': read(ROOT/'active.json', {}), 'operacoes': operations[:50],
              'url': 'https://meshcraft.top/admin/previas-operacionais/',
              'isolamento': 'Sem rede, credenciais, bancos, volumes privados ou shell remoto; páginas em iframe de origem opaca.'}
    atomic(ROOT/'public.json', result)
    return result


def save(record):
    record['atualizada_em'] = now()
    atomic(ROOT/'operations'/(record['id']+'.json'), record)
    public_state()


def dispatch(args):
    if not valid(args):
        return {'recusado': True, 'motivo': 'comando_nao_permitido'}
    with LOCK:
        if args == ['ajuda']:
            return {'comandos': ['previas listar', 'previas aplicar NOME COMMIT BASE_OU_nova',
                                 'previas consultar ID', 'previas retomar ID'],
                    'manifesto': 'infra/previas/candidatas/NOME.json',
                    'formato': {'runtime': 'node ou python', 'files': {'destino.py': 'services/AREA/arquivo.py'}, 'test': 'tests/arquivo_de_teste.py', 'page': 'index.html'},
                    'origens': list(PREFIXES), 'arvores_protegidas_recusadas': list(PROTECTED),
                    'runtime': ['node --test', 'python unittest'], 'limite': 'Bibliotecas já presentes; sem instalação de dependências.',
                    'escopo': 'Somente novas prévias deste canal. Trilha, produção e demais trabalhos não são destinos.',
                    'documentacao': 'https://meshcraft.top/admin/documentos/operacao-site-contexto-retomada-20261013'}
        if args == ['listar']:
            return public_state()
        if args[0] in {'consultar', 'retomar'}:
            return read(ROOT/'operations'/(args[1]+'.json'), {'recusado': True, 'motivo': 'id_inexistente'})
        _, name, commit, base = args
        ident = hashlib.sha256(('\n'.join(args)).encode()).hexdigest()[:24]
        path = ROOT/'operations'/(ident+'.json')
        if path.exists():
            return read(path)
        operations = [read(p) for p in (ROOT/'operations').glob('*.json')]
        if any(r['estado'] not in TERMINAL for r in operations):
            return {'recusado': True, 'motivo': 'operacao_em_andamento',
                    'id': next(r['id'] for r in operations if r['estado'] not in TERMINAL)}
        active = read(ROOT/'active.json', {})
        if active.get(name, 'nova') != base:
            return {'recusado': True, 'motivo': 'base_divergente', 'atual': active.get(name, 'nova')}
        if name not in active and len(active) >= 20:
            return {'recusado': True, 'motivo': 'capacidade_de_previas'}
        if shutil.disk_usage(ROOT).free < 1024**3:
            return {'recusado': True, 'motivo': 'espaco_insuficiente'}
        record = {'id': ident, 'nome': name, 'commit': commit, 'base': base, 'estado': 'recebida',
                  'inicio': now(), 'banco_alterado': False, 'publicacao_alunos': False,
                  'url': 'https://meshcraft.top/admin/previas-operacionais/?previa=' + name}
        save(record)
        return record


def sandbox(record, plan, stage):
    config = read(CONFIG)
    image = config['images'][plan['runtime']]
    name = 'meshcraft-previa-teste-' + record['id']
    # Eventual contêiner do MESMO ensaio interrompido; nunca outro trabalho.
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    args = ['docker', 'run', '--rm', '--name', name, '--pull', 'never', '--network', 'none',
            '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '192m', '--memory-swap', '192m', '--cpus', '0.5', '--pids-limit', '40',
            '--log-driver', 'none', '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
            '--mount', 'type=bind,src='+str(stage)+',dst=/work,readonly', '--workdir', '/work']
    if plan['runtime'] == 'node':
        args += ['--entrypoint', 'node', image, '--test', plan['test']]
    else:
        args += ['--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python', image,
                 '-B', '-m', 'unittest', plan['test'].replace('/', '.').removesuffix('.py')]
    process = None
    try:
        # Drena continuamente, guarda no máximo 64 KiB e publica apenas contadores.
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        tail = b''
        deadline = time.monotonic() + 90
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() > deadline:
                    process.kill()
                    return 124
                for key, _ in selector.select(0.5):
                    chunk = os.read(key.fd, 8192)
                    if chunk:
                        tail = (tail + chunk)[-65536:]
                    else:
                        selector.unregister(key.fileobj)
            rc = process.wait(timeout=5)
        output = tail.decode('utf-8', errors='replace')
        counts = {name: int(value) for name, value in re.findall(r'^# (tests|pass|fail|cancelled|skipped) ([0-9]{1,6})$', output, re.M)}
        python_count = re.search(r'Ran ([0-9]{1,6}) tests?', output)
        if python_count:
            counts['tests'] = int(python_count.group(1))
        record['testes'] = counts
        record['classes_de_falha'] = [name for name in ('AssertionError', 'SyntaxError', 'ImportError', 'ModuleNotFoundError', 'TypeError', 'ReferenceError', 'PermissionError') if name in output]
        return rc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restore(record, reason):
    with LOCK:
        active = read(ROOT/'active.json', {})
        if active.get(record['nome']) == record['id']:
            if record['base'] == 'nova':
                active.pop(record['nome'], None)
            else:
                active[record['nome']] = record['base']
            atomic(ROOT/'active.json', active)
        record.update(estado='recuperada', motivo=reason, fim=now(),
                      codigo_atual=active.get(record['nome']), candidato_preservado=True)
        save(record)


def execute(record):
    stage = ROOT/'releases'/record['id']
    try:
        # Após queda de processo durante a ativação, primeiro volta à referência anterior.
        if record['estado'] in {'ativando', 'testando'}:
            restore(record, 'execucao_interrompida')
            return
        record['estado'] = 'preparando'
        with LOCK:
            save(record)
        plan = json.loads(fetch(record['commit'], 'infra/previas/candidatas/'+record['nome']+'.json'))
        if not plan_valid(plan):
            raise ValueError('manifesto_recusado')
        stage.mkdir(parents=True, exist_ok=True, mode=0o755)
        hashes, total = {}, 0
        for target, source in plan['files'].items():
            body = fetch(record['commit'], source)
            total += len(body)
            if total > 12 * 1024 * 1024:
                raise ValueError('pacote_grande')
            path = stage/target
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            path.write_bytes(body)
            path.chmod(0o644)
            hashes[target] = hashlib.sha256(body).hexdigest()
        backup = ROOT/'backups'/record['id']
        backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        with LOCK:
            active = read(ROOT/'active.json', {})
            if active.get(record['nome'], 'nova') != record['base']:
                raise ValueError('base_divergente')
            atomic(backup/'anterior.json', active)
            if record['base'] != 'nova' and not (backup/'codigo').exists():
                shutil.copytree(ROOT/'releases'/record['base'], backup/'codigo')
            record.update(backup=str(backup), arquivos_sha256=hashes, runtime=plan['runtime'], pagina=plan['page'], estado='ativando')
            save(record)  # persistido ANTES de trocar a referência
            active[record['nome']] = record['id']
            atomic(ROOT/'active.json', active)
            record['estado'] = 'testando'
            save(record)
        rc = sandbox(record, plan, stage)
        record['teste_exit_code'] = rc
        if rc:
            restore(record, 'teste_falhou' if rc != 124 else 'teste_tempo_esgotado')
            return
        with LOCK:
            if read(ROOT/'active.json', {}).get(record['nome']) != record['id']:
                raise ValueError('base_divergente')
            record.update(estado='concluida', fim=now(), codigo_atual=record['id'])
            save(record)
    except Exception as error:
        # Sem imprimir erros potencialmente derivados do código recebido.
        reason = str(error) if type(error) is ValueError and str(error) in {
            'manifesto_recusado', 'origem_divergente', 'arquivo_grande', 'pacote_grande', 'base_divergente'} else 'preparacao_ou_execucao_falhou'
        restore(record, reason)


def worker():
    while True:
        with LOCK:
            pending = [read(p) for p in (ROOT/'operations').glob('*.json')]
        for record in sorted(pending, key=lambda r: r['inicio']):
            if record['estado'] not in TERMINAL:
                execute(record)
        time.sleep(1)


def serve():
    import pwd
    os.umask(0o022)
    for name in ('operations', 'releases', 'backups'):
        (ROOT/name).mkdir(parents=True, exist_ok=True, mode=0o755 if name != 'backups' else 0o700)
    uid = pwd.getpwnam('robo').pw_uid
    threading.Thread(target=worker, daemon=True).start()
    listener = socket.socket(fileno=3)  # SocketActivation: dono/grupo definidos pelo systemd
    while True:
        conn, _ = listener.accept()
        with conn:
            try:
                _, peer, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if peer not in {0, uid}:
                    continue
                conn.settimeout(3)
                data = b''
                while b'\n' not in data and len(data) <= 4096:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                result = dispatch(json.loads(data)) if len(data) <= 4096 else {'recusado': True}
                conn.sendall(json.dumps(result).encode() + b'\n')
            except (OSError, ValueError, TypeError):
                pass


if __name__ == '__main__':
    serve()
