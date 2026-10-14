"""Operação fechada para ligar o integrador parado, sem interromper o ativo."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

UNIT = 'meshcraft-integrador.service'
ID = re.compile(r'[0-9a-f]{32}\Z')


def valid(args):
    return (args == ['recuperar', 'integrador'] or
            isinstance(args, list) and len(args) == 2 and args[0] == 'consultar'
            and isinstance(args[1], str) and ID.fullmatch(args[1]) is not None)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(state, record):
    path = Path(state) / (record['id'] + '.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=True), encoding='utf-8')
    os.replace(temporary, path)


def dispatch(args, health, run, refused, state):
    if not valid(args):
        raise refused('comando_nao_permitido')
    if args[0] == 'consultar':
        path = Path(state) / (args[1] + '.json')
        if not path.is_file():
            raise refused('operacao_ausente')
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('acao') != 'recuperar_integrador' or record.get('id') != args[1]:
            raise refused('operacao_incompativel')
        # O registro de intenção continua consultável se o processo cair.
        if record['estado'] == 'iniciando':
            current = health('integrador')
            if current.get('estado') == 'active' and current.get('executando'):
                record.update(estado='concluida', fim=now(), depois=current)
                save(state, record)
        return record

    before = health('integrador')
    if not before.get('carregado'):
        raise refused('servico_ausente')
    if before.get('estado') == 'active' and before.get('executando'):
        return {'servico': 'integrador', 'estado': 'ja_ativo', 'observado': before}
    if before.get('estado') not in {'inactive', 'failed'}:
        raise refused('servico_em_transicao')
    record = {'id': uuid.uuid4().hex, 'acao': 'recuperar_integrador',
              'servico': 'integrador', 'inicio': now(), 'estado': 'iniciando', 'antes': before}
    save(state, record)
    try:
        result = run(['/usr/bin/systemctl', 'start', '--no-block', UNIT], timeout=10)
        if result.returncode:
            record.update(estado='falha', codigo='inicio_recusado', fim=now())
        else:
            # O serviço continua na VPS mesmo se a conexão SSH terminar.
            deadline = time.monotonic() + 8
            while True:
                after = health('integrador')
                record['depois'] = after
                if after.get('estado') == 'active' and after.get('executando'):
                    record.update(estado='concluida', fim=now())
                    break
                if after.get('estado') == 'failed':
                    record.update(estado='falha', codigo='servico_falhou', fim=now())
                    break
                if time.monotonic() >= deadline:
                    record['codigo'] = 'inicio_ainda_nao_confirmado'
                    break
                time.sleep(0.25)
    except (OSError, subprocess.TimeoutExpired):
        # A intenção é preservada; consulta por ID reconcilia somente a saúde.
        record['codigo'] = 'inicio_ainda_nao_confirmado'
    save(state, record)
    return record
