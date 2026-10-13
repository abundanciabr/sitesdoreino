#!/usr/bin/env python3
"""Diagnóstico operacional: somente metadados e classes de eventos, nunca texto bruto."""
import datetime
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import time
import uuid

SOCKET = '/run/meshcraft-servicos.sock'
STATE = Path('/var/lib/meshcraft-servicos')
UNITS = {
    'robo': 'meshcraft-robo.service',
    'analisador': 'meshcraft-analisador-manutencao.service',
    'integrador': 'meshcraft-integrador.service',
    'publicador': 'meshcraft-entregas-publicador.service',
    'super-equipe': 'meshcraft-super-equipe.service',
    'trilha-analisador': 'meshcraft-trilha-previa-analisador.service',
    'backup': 'meshcraft-backup-drive.service',
}
CONTAINERS = {'aplicacao': 'plataforma-aplicacao-1', 'proxy': 'plataforma-traefik-1',
              'postgres': 'plataforma-postgres-1', 'redis': 'plataforma-redis-1',
              'funil-api': 'meshcraft-funil-api', 'funil-eventos': 'meshcraft-funil-eventos'}
# Estes dois processos atendem consultas; nenhum executa pagamento ou trabalho de fila.
RESTART = {'robo', 'analisador'}
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'}
ERRORS = ('TimeoutError', 'ConnectionError', 'ConnectionRefusedError', 'PermissionError',
          'FileNotFoundError', 'ModuleNotFoundError', 'ImportError', 'OperationalError',
          'IntegrityError', 'ProgrammingError', 'ValueError', 'TypeError', 'KeyError',
          'AttributeError', 'RuntimeError', 'MemoryError', 'OSError')


class Refused(ValueError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def valid(args):
    if not isinstance(args, list) or not all(type(x) is str for x in args):
        return False
    if args == ['listar'] or args == ['saude']:
        return True
    if len(args) == 2 and args[0] == 'saude':
        return args[1] in UNITS or args[1] in CONTAINERS
    if len(args) == 2 and args[0] == 'reiniciar':
        return args[1] in RESTART
    return (len(args) == 4 and args[0] == 'logs' and args[1] in UNITS.keys() | CONTAINERS.keys()
            and re.fullmatch(r'[0-9]{1,4}', args[2]) is not None
            and re.fullmatch(r'[0-9]{1,3}', args[3]) is not None
            and 1 <= int(args[2]) <= 1440 and 1 <= int(args[3]) <= 200)


def run(args, timeout=20):
    # Nenhum argumento do solicitante se torna comando, caminho, unidade ou expressão.
    return subprocess.run(args, capture_output=True, text=True, errors='replace',
                          timeout=timeout, env=ENV, check=False)


def health(name):
    result = {'servico': name, 'reiniciavel': name in RESTART, 'observado_em': now()}
    if name in UNITS:
        r = run(['/usr/bin/systemctl', 'show', UNITS[name], '--no-pager',
                 '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState', '-p', 'NRestarts'])
        fields = dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)
        states = {'active', 'inactive', 'failed', 'activating', 'deactivating', 'reloading'}
        state = fields.get('ActiveState')
        result['estado'] = state if r.returncode == 0 and state in states else 'indisponivel'
        result['carregado'] = fields.get('LoadState') == 'loaded'
        result['executando'] = fields.get('SubState') == 'running'
        n = fields.get('NRestarts', '')
        if re.fullmatch(r'[0-9]{1,9}', n):
            result['reinicios_automaticos'] = int(n)
    else:
        r = run(['/usr/bin/docker', 'inspect', '--format',
                 '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.RestartCount}}',
                 CONTAINERS[name]])
        f = r.stdout.strip().split('|')
        result['estado'] = f[0] if r.returncode == 0 and f[0] in {
            'created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead'} else 'indisponivel'
        if r.returncode == 0 and len(f) == 3:
            result['healthcheck'] = f[1] if f[1] in {'healthy', 'unhealthy', 'starting', 'none'} else 'indisponivel'
            if re.fullmatch(r'[0-9]{1,9}', f[2]):
                result['reinicios_automaticos'] = int(f[2])
    return result


def classify(message):
    # Saída é vocabulário fechado. Nem mesmo trechos supostamente "limpos" escapam.
    classes = [name for name in ERRORS if re.search(r'\b' + name + r'\b', message)]
    for code, pattern in (
        ('tempo_esgotado', r'\b(?:timed out|timeout)\b'),
        ('conexao_recusada', r'\bconnection refused\b'),
        ('memoria_esgotada', r'\b(?:out of memory|oom-kill)\b'),
        ('espaco_esgotado', r'\bno space left on device\b'),
        ('falha', r'\b(?:error|exception|failed|failure|traceback)\b'),
        ('aviso', r'\b(?:warning|warn)\b'),
        ('inicio', r'\b(?:starting|started|listening)\b'),
        ('parada', r'\b(?:stopping|stopped|shutdown)\b'),
    ):
        if re.search(pattern, message, re.I):
            classes.append(code)
    return classes or ['texto_omitido']


def logs(name, minutes, limit):
    entries = []
    if name in UNITS:
        r = run(['/usr/bin/journalctl', '-u', UNITS[name], '--since', f'{minutes} minutes ago',
                 '-n', str(limit), '--no-pager', '-o', 'json', '--output-fields=__REALTIME_TIMESTAMP,PRIORITY,MESSAGE'])
        for line in r.stdout.splitlines()[-limit:]:
            try:
                data = json.loads(line)
                msg = data.get('MESSAGE', '')
                entry = {'classes': classify(msg if isinstance(msg, str) else '')}
                stamp = data.get('__REALTIME_TIMESTAMP', '')
                if isinstance(stamp, str) and re.fullmatch(r'[0-9]{16}', stamp):
                    entry['em'] = datetime.datetime.fromtimestamp(int(stamp) / 1e6, datetime.timezone.utc).isoformat()
                priority = data.get('PRIORITY')
                if type(priority) is str and priority in tuple(str(x) for x in range(8)):
                    entry['prioridade'] = int(priority)
                entries.append(entry)
            except (ValueError, TypeError, AttributeError, OverflowError):
                entries.append({'classes': ['registro_omitido']})
    else:
        r = run(['/usr/bin/docker', 'logs', '--since', f'{minutes}m', '--tail', str(limit),
                 '--timestamps', CONTAINERS[name]])
        if r.returncode == 0:
            for line in (r.stdout + '\n' + r.stderr).splitlines()[-limit:]:
                if not line:
                    continue
                entry = {'classes': classify(line)}
                stamp = line.split(' ', 1)[0]
                if re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{1,9}Z', stamp):
                    entry['em'] = stamp
                entries.append(entry)
    if r.returncode:
        raise RuntimeError('fonte_indisponivel')
    return {'servico': name, 'minutos': minutes, 'limite': limit, 'eventos': entries,
            'observado_em': now(), 'formato': 'classes de eventos; texto e dados pessoais omitidos'}


def restart(name):
    before = health(name)
    if not before.get('carregado'):
        raise Refused('servico_ausente')
    # Não interromper uma entrega em curso nem uma recuperação do analisador.
    if name == 'robo':
        connections = Path('/proc/net/unix').read_text().splitlines()
        if any(len(f) >= 8 and f[5] == '03' and f[7] == '/run/meshcraft-robo.sock'
               for f in (line.split() for line in connections)):
            raise Refused('operacao_em_andamento')
    else:
        busy = run(['/usr/bin/systemctl', 'is-active', 'meshcraft-analisador-operacao.service']).stdout.strip()
        if busy in {'active', 'activating', 'deactivating', 'reloading'}:
            raise Refused('operacao_em_andamento')
    operation = {'id': uuid.uuid4().hex, 'servico': name, 'inicio': now(), 'antes': before}
    record = STATE / (operation['id'] + '.json')
    record.write_text(json.dumps(operation), encoding='utf-8')
    r = run(['/usr/bin/systemctl', 'restart', UNITS[name]], timeout=45)
    after = health(name)
    operation.update({'fim': now(), 'depois': after,
                      'estado': 'concluida' if r.returncode == 0 and after['estado'] == 'active' else 'falha'})
    record.write_text(json.dumps(operation), encoding='utf-8')
    return operation


def dispatch(args):
    if not valid(args):
        raise Refused('comando_nao_permitido')
    if args[0] == 'listar':
        return {'servicos': list(UNITS) + list(CONTAINERS), 'reiniciaveis': sorted(RESTART),
                'comandos': ['servicos listar', 'servicos saude [servico]',
                             'servicos logs SERVICO MINUTOS LINHAS', 'servicos reiniciar SERVICO']}
    if args[0] == 'saude':
        return {'servicos': [health(n) for n in ([args[1]] if len(args) == 2 else list(UNITS) + list(CONTAINERS))]}
    if args[0] == 'logs':
        return logs(args[1], int(args[2]), int(args[3]))
    return restart(args[1])


def serve():
    import pwd
    allowed_uid = pwd.getpwnam('robo').pw_uid
    if int(os.environ.get('LISTEN_FDS', '0')) != 1:
        raise RuntimeError('socket_systemd_necessario')
    listener = socket.socket(fileno=3)
    while True:
        conn, _ = listener.accept()
        with conn:
            conn.settimeout(5)
            try:
                _, uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != allowed_uid:
                    raise Refused('identidade_recusada')
                with conn.makefile('rb') as stream:
                    raw = stream.readline(1025)
                if len(raw) > 1024 or not raw.endswith(b'\n'):
                    raise Refused('entrada_invalida')
                data = dispatch(json.loads(raw))
                response = {'codigo': 0, 'saida': json.dumps(data, ensure_ascii=True) + '\n'}
            except Refused as exc:
                response = {'codigo': 2, 'saida': json.dumps({'recusado': True, 'motivo': str(exc)}) + '\n'}
            except Exception:
                response = {'codigo': 3, 'saida': '{"indisponivel":true,"motivo":"operacao_indisponivel"}\n'}
            try:
                conn.sendall(json.dumps(response).encode())
            except OSError:
                pass


if __name__ == '__main__':
    serve()
