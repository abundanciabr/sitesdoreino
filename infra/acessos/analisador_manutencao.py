#!/usr/bin/env python3
"""Autoridade local do analisador. Operações fechadas, sem código do solicitante."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tarfile
import uuid

BASE = Path('/usr/local/lib/meshcraft-analisador')
STATE = Path('/var/lib/meshcraft-analisador')
ROOT = Path('/opt/plataforma')
SOCKET = '/run/meshcraft-analisador-manutencao.sock'
EXECUTOR = ROOT / 'analise-pratica/20261008-v3/executor_host.py'
EXEC_LOCK = EXECUTOR.with_name('executor.lock')
QUEUE = ROOT / 'encomendas-arquivos/marketplace/analises-v1'
IMAGE = 'meshcraft-analise-pratica:20261008-v3'
UNIT = 'meshcraft-analisador-operacao.service'
ACOES = ('consultar', 'diagnosticar', 'recuperar')
CRON = ('* * * * * /usr/bin/flock -n ' + str(EXEC_LOCK) + ' /usr/bin/python3 '
        + str(EXECUTOR) + ' --once >> ' + str(EXECUTOR.with_name('executor.log')) + ' 2>&1')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LC_ALL': 'C.UTF-8'}
HEX = re.compile(r'[a-f0-9]{32}\Z')


class Falha(RuntimeError):
    pass


def agora():
    return datetime.now(timezone.utc).isoformat()


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def regular(p):
    try:
        return stat.S_ISREG(Path(p).lstat().st_mode)
    except FileNotFoundError:
        return False


def ler(p, limite=65536):
    if not regular(p) or p.stat().st_size > limite:
        raise Falha('registro_indisponivel')
    return json.loads(p.read_text(encoding='utf-8'))


def gravar(p, data):
    temp = p.with_name(p.name + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp.chmod(0o600)
    os.replace(temp, p)


def run(args, timeout=30, check=True, **kw):
    r = subprocess.run(args, env=ENV, capture_output=True, text=True,
                       timeout=timeout, **kw)
    if check and r.returncode:
        raise Falha('comando_fixo_falhou')
    return r


def imagem_id():
    r = run(['/usr/bin/docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], check=False)
    if r.returncode:
        return None
    value = r.stdout.strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', value):
        raise Falha('identidade_imagem_invalida')
    return value


def manifesto():
    data = ler(BASE / 'manifesto.json')
    if data.get('imagem') != IMAGE or not re.fullmatch(r'sha256:[a-f0-9]{64}', data.get('imagem_id', '')):
        raise Falha('referencia_invalida')
    for name in ('executor_host.py', 'base.glb', 'fonte.blend', 'invalido.glb'):
        p = BASE / 'referencia' / name
        if not regular(p) or sha(p) != data['arquivos'].get(name):
            raise Falha('referencia_invalida')
    return data


def agenda():
    r = run(['/usr/bin/crontab', '-u', 'deploy', '-l'], check=False)
    if r.returncode not in (0, 1):
        raise Falha('agenda_indisponivel')
    return r.stdout if r.returncode == 0 else ''


def contagens():
    result = {'pendentes': 0, 'processando': 0, 'concluidas': 0, 'falhas': 0, 'ilegivel': 0}
    for p in QUEUE.glob('*/pedido.json'):
        if not re.fullmatch(r'[a-f0-9]{64}', p.parent.name) or p.parent.is_symlink():
            continue
        try:
            state = p.parent / 'estado.json'
            v = ler(state).get('estado') if state.exists() else 'pendente'
            key = {'pendente': 'pendentes', 'processando': 'processando',
                   'concluida': 'concluidas', 'falha': 'falhas'}.get(v, 'ilegivel')
            result[key] += 1
        except (OSError, ValueError, Falha):
            result['ilegivel'] += 1
    return result


def operacao_publica():
    p = STATE / 'operacao.json'
    if not p.exists():
        return None
    data = ler(p)
    return {k: data[k] for k in ('id', 'acao', 'estado', 'etapa', 'inicio', 'fim', 'codigo',
                               'backup', 'provas', 'imagem_restaurada', 'executor_restaurado',
                               'agenda_restaurada', 'estados_reabertos') if k in data}


def consultar():
    ref = manifesto()
    image = imagem_id()
    cron = agenda()
    cron_ok = run(['/usr/bin/systemctl', 'is-active', 'cron.service'], check=False).returncode == 0
    executor_ok = regular(EXECUTOR) and sha(EXECUTOR) == ref['arquivos']['executor_host.py']
    problemas = []
    if image is None:
        problemas.append('imagem_ausente')
    elif image != ref['imagem_id']:
        problemas.append('imagem_divergente')
    if not executor_ok:
        problemas.append('executor_divergente_ou_ausente')
    if CRON not in cron.splitlines():
        problemas.append('agenda_ausente')
    if not cron_ok:
        problemas.append('agendador_inativo')
    op = operacao_publica()
    if op and op['estado'] in ('recebida', 'executando'):
        active = run(['/usr/bin/systemctl', 'show', UNIT, '-p', 'ActiveState', '--value']).stdout.strip()
        if active not in ('active', 'activating', 'reloading'):
            op = dict(op, estado='interrompida', codigo='operacao_interrompida')
    return {'servico': 'analisador', 'versao_canal': 1, 'observado_em': agora(),
            'operacoes': list(ACOES), 'estado': 'disponivel' if not problemas else 'precisa_recuperacao',
            'diagnosticos': problemas, 'imagem_id': image, 'imagem_aprovada': ref['imagem_id'],
            'executor_conferido': executor_ok, 'agenda_presente': CRON in cron.splitlines(),
            'agendador_ativo': cron_ok, 'fila': contagens(), 'ultima_operacao': op}


@contextmanager
def trava(path, nonblock=False):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    existed = path.exists()
    with path.open('a') as f:
        if path == EXEC_LOCK and not existed:
            who = pwd.getpwnam('deploy')
            os.fchown(f.fileno(), who.pw_uid, who.pw_gid)
            os.fchmod(f.fileno(), 0o600)
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblock else 0))
        except BlockingIOError:
            raise Falha('operacao_em_andamento') from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def iniciar(acao):
    if acao not in ('diagnosticar', 'recuperar'):
        raise Falha('operacao_recusada')
    with trava(STATE / 'pedido.lock'):
        current = consultar()['ultima_operacao']
        if current and current['estado'] in ('recebida', 'executando'):
            return {'aceito': True, 'reutilizado': True, 'operacao': current}
        if current:
            archive = STATE / 'historico'
            archive.mkdir(mode=0o700, exist_ok=True)
            shutil.copyfile(STATE / 'operacao.json', archive / (current['id'] + '.json'))
        op = {'id': uuid.uuid4().hex, 'acao': acao, 'estado': 'recebida', 'etapa': 'aguardando_execucao', 'inicio': agora()}
        gravar(STATE / 'operacao.json', op)
        try:
            run(['/usr/bin/systemctl', 'start', '--no-block', UNIT])
        except Exception:
            op.update(estado='falhou', codigo='nao_iniciada', fim=agora())
            gravar(STATE / 'operacao.json', op)
            raise
        return {'aceito': True, 'reutilizado': False, 'operacao': op}


def provar(image, folder):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    proofs = []
    for n, name in enumerate(('base.glb', 'fonte.blend', 'invalido.glb')):
        source = BASE / 'referencia' / name
        out = folder / str(n)
        out.mkdir()
        out.chmod(0o777)
        container = 'meshcraft-diagnostico-' + uuid.uuid4().hex[:20]
        args = ['/usr/bin/docker', 'run', '--rm', '--name', container, '--network', 'none',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--user', '65534:65534', '--memory', '1536m', '--memory-swap', '1536m',
                '--cpus', '1.5', '--pids-limit', '64', '--ulimit', 'nofile=128:128',
                '--ulimit', 'fsize=67108864:67108864', '--tmpfs', '/tmp:rw,noexec,nosuid,size=512m',
                '--mount', 'type=bind,src=' + str(source) + ',dst=/entrada,readonly',
                '--mount', 'type=bind,src=' + str(out) + ',dst=/saida', image, name]
        try:
            run(args, timeout=360)
        except (subprocess.TimeoutExpired, Falha):
            raise Falha('prova_do_leitor_falhou') from None
        finally:
            run(['/usr/bin/docker', 'stop', '-t', '1', container], check=False)
        report = ler(out / 'resultado.json', 8 * 1024 * 1024)
        member = report['arquivos'][0]
        if n < 2:
            views = member.get('imagens', [])
            if (member.get('estado') != 'concluida' or member.get('medidas', {}).get('triangulos_total') != 398
                    or len(views) != 3):
                raise Falha('prova_do_modelo_falhou')
            for item in views:
                name_view = item['arquivo']
                if not re.fullmatch(r'[a-f0-9]{24}-(frontal|lateral|perspectiva)\.png', name_view):
                    raise Falha('prova_da_previa_falhou')
                if not regular(out / name_view) or (out / name_view).stat().st_size == 0:
                    raise Falha('prova_da_previa_falhou')
            proofs.append({'arquivo': name, 'estado': 'examinado', 'triangulos': 398, 'vistas': 3})
        else:
            if member.get('estado') != 'falha' or 'GLB' not in member.get('falha', ''):
                raise Falha('prova_do_invalido_falhou')
            proofs.append({'arquivo': name, 'estado': 'invalido_identificado'})
    return proofs


def backup_operacao(op):
    backup = ROOT / 'backups-de-codigo' / ('analisador-operacao-' + op['id'])
    backup.mkdir(mode=0o700)
    cron = agenda()
    (backup / 'agenda-antes.txt').write_text(cron)
    with tarfile.open(backup / 'estado-antes.tar.gz', 'w:gz') as tar:
        for p, name in ((EXECUTOR, 'executor_host.py'), (BASE / 'manifesto.json', 'manifesto.json'),
                        (QUEUE, 'analises-v1')):
            if p.exists():
                tar.add(p, arcname=name, recursive=True)
    with tarfile.open(backup / 'estado-antes.tar.gz') as tar:
        tar.getmembers()
    # A imagem aprovada já possui cópia recuperável, conferida antes de cada uso.
    ref = manifesto()
    archive = BASE / 'referencia/imagem.tar'
    if not regular(archive) or sha(archive) != ref['imagem_tar_sha256']:
        raise Falha('backup_imagem_divergente')
    (backup / 'imagem-referencia.json').write_text(json.dumps({'arquivo': str(archive), 'sha256': sha(archive)}))
    return backup, cron


def reabrir_falhas(backup):
    count = 0
    for p in QUEUE.glob('*/estado.json'):
        if p.parent.is_symlink() or not re.fullmatch(r'[a-f0-9]{64}', p.parent.name):
            continue
        try:
            value = ler(p)
        except (OSError, ValueError, Falha):
            continue
        if value.get('estado') != 'falha' or value.get('falha') != 'Analisador indisponível ou limite de recursos atingido.':
            continue
        try:
            pedido = ler(p.parent / 'pedido.json')
        except (OSError, ValueError, Falha):
            continue
        key = pedido.get('chave', '')
        if not re.fullmatch(r'[a-f0-9]{32}', key):
            continue
        src = QUEUE.parent / key
        if not regular(src) or src.stat().st_size > 128 * 1024 * 1024 or sha(src) != pedido.get('sha256'):
            continue
        saved = backup / 'estados-reabertos'
        saved.mkdir(mode=0o700, exist_ok=True)
        shutil.copyfile(p, saved / (p.parent.name + '.json'))
        # Renomear preserva o estado anterior; nenhum resultado ou anexo é apagado.
        p.rename(p.with_name('estado-antes-' + backup.name + '.json'))
        count += 1
    return count


def executar_operacao():
    with trava(STATE / 'execucao.lock', nonblock=True):
        op = ler(STATE / 'operacao.json')
        if not HEX.fullmatch(op.get('id', '')) or op.get('acao') not in ('diagnosticar', 'recuperar'):
            raise Falha('operacao_recusada')
        work = STATE / 'provas' / op['id']
        op.update(estado='executando', etapa='diagnostico')
        gravar(STATE / 'operacao.json', op)
        backup = None
        original = None
        old_image = None
        original_cron = None
        try:
            ref = manifesto()
            if op['acao'] == 'recuperar':
                with trava(EXEC_LOCK, nonblock=True):
                    op['etapa'] = 'backup'
                    gravar(STATE / 'operacao.json', op)
                    backup, original_cron = backup_operacao(op)
                    op['backup'] = str(backup)
                    original = EXECUTOR.read_bytes() if regular(EXECUTOR) else None
                    old_image = imagem_id()
                    if old_image and old_image != ref['imagem_id']:
                        # Outra implantação pode ser legítima: não substituir sua imagem.
                        raise Falha('imagem_divergente_exige_conferencia')
                    if not old_image:
                        run(['/usr/bin/docker', 'load', '-i', str(BASE / 'referencia/imagem.tar')], timeout=600)
                        loaded = run(['/usr/bin/docker', 'image', 'inspect', ref['imagem_id'], '--format', '{{.Id}}']).stdout.strip()
                        if loaded != ref['imagem_id']:
                            raise Falha('imagem_recuperada_divergente')
                    op['etapa'] = 'prova'
                    gravar(STATE / 'operacao.json', op)
                    op['provas'] = provar(ref['imagem_id'], work)
                    if original is None or hashlib.sha256(original).hexdigest() != ref['arquivos']['executor_host.py']:
                        EXECUTOR.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(BASE / 'referencia/executor_host.py', EXECUTOR)
                        who = pwd.getpwnam('deploy')
                        os.chown(EXECUTOR, who.pw_uid, who.pw_gid)
                        EXECUTOR.chmod(0o644)
                        op['executor_restaurado'] = True
                    if CRON not in original_cron.splitlines():
                        if any('analise-pratica' in x and not x.lstrip().startswith('#') for x in original_cron.splitlines()):
                            raise Falha('agenda_divergente_exige_conferencia')
                        run(['/usr/bin/crontab', '-u', 'deploy', '-'], input=original_cron.rstrip() + '\n' + CRON + '\n')
                        op['agenda_restaurada'] = True
                    run(['/usr/bin/systemctl', 'start', 'cron.service'])
                    if not old_image:
                        run(['/usr/bin/docker', 'tag', ref['imagem_id'], IMAGE])
                        op['imagem_restaurada'] = True
                    if consultar()['estado'] != 'disponivel':
                        raise Falha('recuperacao_nao_confirmada')
                    op['estados_reabertos'] = reabrir_falhas(backup)
                    op['etapa'] = 'conferido'
                    # O cron retoma a fila quando a trava existente é liberada.
            else:
                status = consultar()
                if status['diagnosticos']:
                    raise Falha(status['diagnosticos'][0])
                op['provas'] = provar(ref['imagem_id'], work)
            op.update(estado='concluida', etapa='conferido', codigo='ok')
        except Exception as exc:
            if backup is not None:
                # Recupera apenas o código e agenda que esta operação alterou. Nunca banco.
                if op.get('executor_restaurado') and original is not None:
                    EXECUTOR.write_bytes(original)
                if op.get('agenda_restaurada') and original_cron is not None:
                    run(['/usr/bin/crontab', '-u', 'deploy', '-'], input=original_cron, check=False)
                if old_image:
                    run(['/usr/bin/docker', 'tag', old_image, IMAGE], check=False)
            op.update(estado='falhou', codigo=str(exc) if isinstance(exc, Falha) else 'falha_interna')
        finally:
            op['fim'] = agora()
            gravar(STATE / 'operacao.json', op)


def atender(conn):
    _, uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != pwd.getpwnam('integrador').pw_uid:
        raise Falha('identidade_recusada')
    raw = bytearray()
    while len(raw) <= 128:
        chunk = conn.recv(129 - len(raw))
        if not chunk:
            break
        raw.extend(chunk)
    if len(raw) > 128 or not raw.endswith(b'\n'):
        raise Falha('operacao_recusada')
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) != 1 or data[0] not in ACOES:
        raise Falha('operacao_recusada')
    return consultar() if data[0] == 'consultar' else iniciar(data[0])


def servir():
    if os.environ.get('LISTEN_FDS') != '1':
        raise Falha('socket_obrigatorio')
    listener = socket.socket(fileno=3)
    while True:
        conn, _ = listener.accept()
        with conn:
            conn.settimeout(10)
            try:
                result = atender(conn)
            except (Falha, ValueError, OSError, subprocess.SubprocessError):
                result = {'erro': 'operacao_indisponivel_ou_recusada'}
            try:
                conn.sendall(json.dumps(result, ensure_ascii=True).encode() + b'\n')
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == '__main__':
    os.umask(0o077)
    if os.geteuid() != 0:
        raise SystemExit('autoridade_local_obrigatoria')
    if sys.argv[1:] == ['servir']:
        servir()
    elif sys.argv[1:] == ['executar']:
        executar_operacao()
    else:
        raise SystemExit('operacao_recusada')
