#!/usr/bin/env python3
"""Espera o backup concorrente, preserva o remetente e confere uma copia no Drive."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
import urllib.request
import uuid

PROGRAM = Path('/usr/local/lib/meshcraft-backup-drive/enviar.py')
STATE = Path('/var/lib/meshcraft-backup-drive')
BEFORE = 'd085b465653bddd99fcd92f66326a02f52e38d1d3fe2c9396b5270a1f12dcf48'
AFTER = 'c9169bde14fcbbdb997ac5d1ce388eb5c62442b4f875f3b0f3eb105c3a7bac1e'
OLD = b'fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)'
NEW = b'fcntl.flock(lock,fcntl.LOCK_EX)'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def candidate(data):
    if sha(data) == AFTER:
        return data
    if sha(data) != BEFORE or data.count(OLD) != 2:
        raise RuntimeError('programa_divergente_nada_alterado')
    result = data.replace(OLD, NEW)
    if sha(result) != AFTER:
        raise RuntimeError('candidata_divergente_nada_alterado')
    compile(result, str(PROGRAM), 'exec')
    return result


def replace_preserving(target, data, expected):
    if target.is_symlink() or sha(target.read_bytes()) != expected:
        raise RuntimeError('programa_alterado_por_outra_operacao')
    metadata = target.stat()
    pending = target.with_name(target.name + '.preparado-' + uuid.uuid4().hex)
    with pending.open('xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(pending, stat.S_IMODE(metadata.st_mode))
    os.chown(pending, metadata.st_uid, metadata.st_gid)
    if sha(target.read_bytes()) != expected:
        raise RuntimeError('programa_alterado_durante_preparacao')
    os.replace(pending, target)
    if sha(target.read_bytes()) != sha(data):
        raise RuntimeError('gravacao_divergente')


def site_status():
    with urllib.request.urlopen('https://meshcraft.top/', timeout=30) as response:
        if response.status != 200:
            raise RuntimeError('site_nao_respondeu_200')
        return response.status


def prove(data, folder):
    # A trava original continua detida pelo chamador. O estado separado preserva
    # os comprovantes anteriores e obriga nova passagem por copy/check/download.
    sender = types.ModuleType('remetente_conferido')
    exec(compile(data, str(PROGRAM), 'exec'), sender.__dict__)
    sender.STATE = folder / 'conferencia'
    # Uma pasta remota nova comprova transferencia real e evita alterar o
    # manifesto ou os metadados das copias imutaveis que ja existem no Drive.
    suffix = '-conferencia-' + uuid.uuid4().hex[:12]
    original_rc = sender.rc
    destinations = set()
    def proof_rc(*args):
        mapped = []
        for value in args:
            if value.startswith('meshcraft_crypt:'):
                parts = value.split('/', 2)
                if len(parts) < 2:
                    raise RuntimeError('destino_de_conferencia_invalido')
                parts[1] += suffix
                destinations.add('/'.join(parts[:2]))
                value = '/'.join(parts)
            mapped.append(value)
        return original_rc(*mapped)
    sender.rc = proof_rc
    argv = sys.argv
    try:
        sys.argv = [str(PROGRAM)]
        sender.main()
    finally:
        sys.argv = argv
    report = json.loads((sender.STATE / 'ultimo-resultado.json').read_text())
    if report.get('estado') != 'copia conferida por leitura integral':
        raise RuntimeError('copia_sem_comprovacao')
    report['destino_relativo'] = next(iter(destinations)).removeprefix('meshcraft_crypt:') if len(destinations) == 1 else None
    if not report['destino_relativo']:
        raise RuntimeError('destino_de_conferencia_nao_comprovado')
    return {key: report.get(key) for key in (
        'estado', 'carimbo_utc', 'bases', 'arquivos', 'verificado_em', 'restauracao_banco', 'destino_relativo')}


def apply():
    os.umask(0o077)
    if os.geteuid() != 0:
        raise RuntimeError('execute_no_ssh_administrativo')
    if PROGRAM.is_symlink():
        raise RuntimeError('programa_simbolico_nada_alterado')
    original = PROGRAM.read_bytes()
    updated = candidate(original)
    site_status()
    if not STATE.is_dir():
        raise RuntimeError('estado_do_remetente_ausente')
    print('ETAPA: aguardando o envio atual terminar, sem interrompe-lo', flush=True)
    with (STATE / 'envio.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if PROGRAM.read_bytes() != original:
            raise RuntimeError('programa_mudou_durante_espera')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        folder = STATE / ('correcao-concorrencia-' + stamp + '-' + uuid.uuid4().hex[:8])
        folder.mkdir(mode=0o700)
        backup = folder / 'enviar-anterior.py'
        with backup.open('xb') as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        if backup.read_bytes() != original:
            raise RuntimeError('backup_do_programa_divergente')
        changed = updated != original
        try:
            if changed:
                replace_preserving(PROGRAM, updated, BEFORE)
            print('ETAPA: enviando e relendo a copia mais recente; historicos preservados', flush=True)
            proof = prove(updated, folder)
            http = site_status()
            result = {'corrigido': True, 'alterado': changed, 'programa_sha256': sha(PROGRAM.read_bytes()),
                      'backup_programa': str(backup), 'comprovacao_privada': str(folder / 'resultado.json'),
                      'copia': proof, 'site_http': http,
                      'escopo': 'somente duas aquisicoes da trava de backup; nenhuma credencial, agenda ou arquivo de pagamento alterado',
                      'exclusoes': 0, 'banco_producao_restaurado': False}
            if result['programa_sha256'] != AFTER:
                raise RuntimeError('programa_mudou_durante_conferencia')
            (folder / 'resultado.json').write_text(json.dumps(result, indent=2) + '\n')
        except BaseException:
            if changed:
                replace_preserving(PROGRAM, original, AFTER)
                print(json.dumps({'correcao_revertida': True, 'copias_preservadas': True}), flush=True)
            raise
    # Retoma a unidade normal apenas depois de liberar a trava; nao interrompe
    # uma eventual execucao concorrente nem muda timer, credenciais ou permissoes.
    request = subprocess.run(['systemctl', 'start', '--no-block', 'meshcraft-backup-drive.service'],
                             capture_output=True, timeout=30)
    result['acionamento_rotina_solicitado'] = request.returncode == 0
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    if not args.aplicar:
        current = PROGRAM.read_bytes()
        candidate(current)
        print(json.dumps({'programa_reconhecido': True, 'programa_sha256': sha(current), 'alterado': False}))
        return
    apply()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Nao imprimir mensagens de bibliotecas, configuracoes nem dados privados.
        print(json.dumps({'concluido': False, 'classe': type(error).__name__,
                          'motivo': str(error) if type(error) is RuntimeError and str(error).replace('_','').isalnum() else 'detalhes_privados_omitidos'}), flush=True)
        sys.exit(1)
