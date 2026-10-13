#!/usr/bin/env python3
"""Restaura a copia conferida do Drive em PostgreSQL novo e isolado; nao apaga dados."""
import argparse
from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

TAG = '20261013-201215Z-747b9e0ee636-1161673'
REMOTE = 'meshcraft_crypt:2026-10-13/' + TAG + '-conferencia-e308ce7f15c2'
LOCAL_PROOF = Path('/var/lib/meshcraft-backup-drive/correcao-concorrencia-20261013T201401Z-ce567517')
MANIFEST = LOCAL_PROOF / 'conferencia' / TAG / 'manifesto.json'
CONF = Path('/etc/meshcraft-backup-drive/rclone.conf')
STATE = Path('/var/lib/meshcraft-backup-drive')
PRODUCTION = 'plataforma-postgres-1'
LOGS = None
CALL = 0
KINDS = ('TABLE', 'SEQUENCE', 'INDEX', 'CONSTRAINT', 'FK CONSTRAINT', 'DEFAULT',
         'TRIGGER', 'FUNCTION', 'PROCEDURE', 'VIEW', 'MATERIALIZED VIEW', 'TYPE',
         'DOMAIN', 'RULE', 'SCHEMA', 'EXTENSION', 'POLICY', 'ROW SECURITY',
         'TABLE ATTACH', 'INDEX ATTACH', 'SEQUENCE OWNED BY')
COUNTS_SQL = """SELECT table_schema || '.' || table_name,
 (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
 table_schema, table_name), false, true, '')))[1]::text
 FROM information_schema.tables WHERE table_type = 'BASE TABLE'
 AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(args, *, data=None, source=None, timeout=600, check=True):
    global CALL
    CALL += 1
    if source is not None:
        with source.open('rb') as stream:
            result = subprocess.run(args, stdin=stream, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout)
    else:
        result = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
    if result.stderr and LOGS is not None:
        (LOGS / ('comando-%04d.stderr' % CALL)).write_bytes(result.stderr)
    if check and result.returncode:
        raise RuntimeError('comando_%04d_falhou_codigo_%d' % (CALL, result.returncode))
    return result


def rclone(*args):
    return run(['rclone', '--config', str(CONF), '--log-level', 'ERROR', '--stats', '0',
                *args], timeout=1800).stdout


def manifest_entries(raw):
    doc = json.loads(raw)
    if doc.get('carimbo_utc') != TAG or doc.get('bases') != 19:
        raise RuntimeError('manifesto_nao_corresponde_as_19_bases')
    entries = doc.get('arquivos')
    if not isinstance(entries, dict) or len(entries) != 23:
        raise RuntimeError('quantidade_de_arquivos_divergente')
    for name, info in entries.items():
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name) or name in ('.', '..'):
            raise RuntimeError('nome_de_arquivo_invalido')
        if not isinstance(info, dict) or type(info.get('bytes')) is not int or info['bytes'] <= 0:
            raise RuntimeError('tamanho_invalido')
        if not re.fullmatch(r'[0-9a-f]{64}', str(info.get('sha256', ''))):
            raise RuntimeError('hash_invalido')
    databases = {}
    for name in entries:
        match = re.fullmatch(r'([a-z0-9_]+)-' + re.escape(TAG) + r'\.dump', name)
        if match:
            databases[match[1]] = name
    if len(databases) != 19 or TAG + '.contagens.tsv' not in entries:
        raise RuntimeError('conjunto_de_bases_incompleto')
    return entries, databases


def verify_files(folder, entries):
    for name, info in entries.items():
        path = folder / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != info['bytes'] or file_sha(path) != info['sha256']:
            raise RuntimeError('arquivo_baixado_divergente')


def expected_counts(raw, databases):
    result = {db: {} for db in databases}
    for line in raw.decode().splitlines():
        parts = line.split('\t')
        if len(parts) != 3 or parts[0] not in result or not parts[2].isdigit() or '.' not in parts[1]:
            raise RuntimeError('contagem_de_backup_invalida')
        if parts[1] in result[parts[0]]:
            raise RuntimeError('contagem_de_backup_duplicada')
        result[parts[0]][parts[1]] = int(parts[2])
    return result


def inventory(toc):
    result = Counter()
    for line in toc.decode().splitlines():
        match = re.match(r'^\d+;\s+\d+\s+\d+\s+(.+)$', line)
        if not match:
            continue
        rest = match[1]
        for kind in sorted(KINDS, key=len, reverse=True):
            if rest.startswith(kind + ' '):
                # TABLE DATA e SEQUENCE SET sao dados, nao objetos de esquema.
                if (kind == 'TABLE' and rest.startswith('TABLE DATA ')) or (kind == 'SEQUENCE' and rest.startswith('SEQUENCE SET ')):
                    break
                result[rest.rsplit(' ', 1)[0]] += 1  # donos sao intencionalmente locais
                break
    return result


def sql(container, database, statement):
    return run(['docker', 'exec', '-i', container, 'psql', '-U', 'postgres', '-d', database,
                '-X', '-A', '-t', '-F', '\t', '-v', 'ON_ERROR_STOP=1', '-c', statement]).stdout


def restore_database(container, database, source, expected):
    if not re.fullmatch(r'[a-z0-9_]+', database):
        raise RuntimeError('nome_de_base_invalido')
    toc = run(['docker', 'exec', '-i', container, 'pg_restore', '--list'], source=source).stdout
    sql(container, 'postgres', 'CREATE DATABASE "' + database + '" TEMPLATE template0')
    run(['docker', 'exec', '-i', container, 'pg_restore', '-U', 'postgres', '-d', database,
         '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges'], source=source)
    redump = run(['docker', 'exec', container, 'pg_dump', '-U', 'postgres', '-d', database,
                  '-Fc', '--schema-only', '--no-owner', '--no-privileges']).stdout
    restored_toc = run(['docker', 'exec', '-i', container, 'pg_restore', '--list'], data=redump).stdout
    original_objects, restored_objects = inventory(toc), inventory(restored_toc)
    schema_diff = sum((original_objects - restored_objects).values()) + sum((restored_objects - original_objects).values())
    actual = {}
    for line in sql(container, database, COUNTS_SQL).decode().splitlines():
        table, count = line.split('\t')
        actual[table] = int(count)
    differences = [{'tabela': name, 'backup': expected.get(name), 'restaurado': actual.get(name)}
                   for name in sorted(expected.keys() | actual.keys()) if expected.get(name) != actual.get(name)]
    (LOGS / (database + '-contagens.json')).write_text(json.dumps({'esperadas': expected, 'restauradas': actual, 'diferencas': differences}, indent=2))
    (LOGS / (database + '-esquema.json')).write_text(json.dumps({'ausentes': list((original_objects - restored_objects).elements()),
                                                              'adicionais': list((restored_objects - original_objects).elements())}, indent=2))
    invalid_indexes = int(sql(container, database, "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND (NOT i.indisvalid OR NOT i.indisready)").strip())
    sequences = int(sql(container, database, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname NOT IN ('pg_catalog','information_schema')").strip())
    return {'base': database, 'restaurada': True, 'tabelas': len(actual), 'linhas': sum(actual.values()),
            'tabelas_com_contagem_diferente': len(differences), 'divergencias_esquema': schema_diff,
            'indices_invalidos': invalid_indexes, 'sequencias_restauradas': sequences,
            'objetos_de_esquema': sum(restored_objects.values())}


def production_identity():
    result = run(['docker', 'inspect', '--format',
                  '{{.Id}} {{.Image}} {{.State.Running}}', PRODUCTION]).stdout.decode().split()
    # A consulta nao solicita env, segredos ou montagens de producao.
    if len(result) != 3 or not re.fullmatch(r'[a-f0-9]{64}', result[0]) or not re.fullmatch(r'sha256:[a-f0-9]{64}', result[1]):
        raise RuntimeError('identidade_de_producao_invalida')
    return {'id': result[0], 'imagem': result[1], 'rodando': result[2] == 'true'}


def payment_reference():
    base = Path('/usr/local/lib/meshcraft-publicador/atual')
    policy_path = base / 'mercadopago/politica.json'
    raw = policy_path.read_bytes()
    spec = importlib.util.spec_from_file_location('mp_preservado', base / 'infra/mercadopago_congelado.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.conferir_ambiente('/opt/plataforma', json.loads(raw))
    return sha(raw)


def http_status():
    with urllib.request.urlopen('https://meshcraft.top/', timeout=30) as response:
        return response.status


def main():
    global LOGS
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executar', action='store_true')
    if not parser.parse_args().executar:
        print('Use --executar para testar a copia especifica em PostgreSQL novo e isolado.')
        return
    if os.geteuid() != 0:
        raise RuntimeError('execute_no_ssh_administrativo')
    os.umask(0o077)
    original_manifest = MANIFEST.read_bytes()
    entries, databases = manifest_entries(original_manifest)
    before = production_identity()
    if not before['rodando']:
        raise RuntimeError('postgres_de_producao_nao_esta_rodando')
    frozen = payment_reference()
    if http_status() != 200:
        raise RuntimeError('site_nao_respondeu_200_antes')
    if shutil.disk_usage(STATE).free < max(5 * 1024**3, 20 * sum(x['bytes'] for x in entries.values())):
        raise RuntimeError('espaco_insuficiente_para_ensaio')
    token = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    folder = STATE / ('restauracao-drive-' + token)
    folder.mkdir(mode=0o700)
    downloaded = folder / 'baixado'; downloaded.mkdir(mode=0o700)
    pgdata = folder / 'postgres'; pgdata.mkdir(mode=0o700)
    LOGS = folder / 'logs'; LOGS.mkdir(mode=0o700)
    print('ETAPA: baixando a copia do Drive e conferindo todos os SHA256', flush=True)
    remote_manifest = rclone('cat', REMOTE + '/manifesto.json')
    if remote_manifest != original_manifest:
        raise RuntimeError('manifesto_do_drive_divergente')
    listing = folder / 'arquivos.txt'; listing.write_text('\n'.join(sorted(entries)) + '\nmanifesto.json\n')
    rclone('copy', REMOTE, str(downloaded), '--files-from-raw', str(listing), '--immutable', '--transfers', '2')
    verify_files(downloaded, entries)
    if (downloaded / 'manifesto.json').read_bytes() != original_manifest:
        raise RuntimeError('manifesto_baixado_divergente')
    counts = expected_counts((downloaded / (TAG + '.contagens.tsv')).read_bytes(), databases)
    container = 'meshcraft-ensaio-drive-' + token.lower()
    created = None
    report = {'backup': TAG, 'destino_drive': REMOTE, 'diretorio_privado': str(folder),
              'container': container, 'comprovacao_privada': str(folder / 'resultado.json'), 'arquivos_conferidos': len(entries), 'manifesto_sha256': sha(original_manifest),
              'bases': [], 'exclusoes': 0, 'producao_restaurada': False,
              'limite': 'Esquema, dados e sequencias; donos e permissoes de producao nao sao reativados. Redis e sessoes externas nao sao iniciados.'}
    try:
        print('ETAPA: iniciando PostgreSQL isolado, sem rede ou portas, com dados novos', flush=True)
        created = run(['docker', 'run', '-d', '--pull', 'never', '--name', container,
                       '--label', 'meshcraft.ensaio.drive=' + token, '--network', 'none', '--cpus', '1',
                       '--memory', '1536m', '--pids-limit', '256', '--mount',
                       'type=bind,src=' + str(pgdata) + ',dst=/var/lib/postgresql/data',
                       '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', before['imagem'],
                       '-c', 'listen_addresses=', '-c', 'shared_buffers=128MB', '-c', 'max_connections=20']).stdout.decode().strip()
        if not re.fullmatch(r'[a-f0-9]{64}', created):
            raise RuntimeError('identidade_do_ensaio_invalida')
        details = json.loads(run(['docker', 'inspect', '--format', '{{json .}}', created]).stdout)
        if details['HostConfig']['NetworkMode'] != 'none' or details['HostConfig'].get('PortBindings') or len(details['Mounts']) != 1 or Path(details['Mounts'][0]['Source']) != pgdata:
            raise RuntimeError('isolamento_nao_comprovado')
        for attempt in range(90):
            ready = run(['docker', 'exec', created, 'pg_isready', '-U', 'postgres'], check=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('postgres_isolado_nao_iniciou')
        version = int(sql(created, 'postgres', 'SHOW server_version_num').strip())
        if not 170000 <= version < 180000:
            raise RuntimeError('imagem_postgresql_nao_e_17')
        report.update({'postgres_version_num': version, 'rede': 'none', 'portas_publicadas': 0, 'imagem_existente': before['imagem']})
        for database, filename in sorted(databases.items()):
            try:
                item = restore_database(created, database, downloaded / filename, counts[database])
            except Exception as error:
                item = {'base': database, 'restaurada': False, 'classe': type(error).__name__,
                        'motivo': str(error) if type(error) is RuntimeError and re.fullmatch(r'[a-z0-9_]+', str(error)) else 'detalhes_em_log_privado'}
            report['bases'].append(item)
            (folder / 'resultado-parcial.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(item), flush=True)
        report.update({'bases_restauradas': sum(x['restaurada'] for x in report['bases']),
                       'bases_com_falha': sum(not x['restaurada'] for x in report['bases']),
                       'tabelas_conferidas': sum(x.get('tabelas', 0) for x in report['bases']),
                       'divergencias_contagens': sum(x.get('tabelas_com_contagem_diferente', 0) for x in report['bases']),
                       'divergencias_esquema': sum(x.get('divergencias_esquema', 0) for x in report['bases']),
                       'indices_invalidos': sum(x.get('indices_invalidos', 0) for x in report['bases'])})
    finally:
        if created and re.fullmatch(r'[a-f0-9]{64}', created):
            run(['docker', 'stop', '--time', '30', created])
            report['container_parado_dados_preservados'] = True
        (folder / 'resultado-parcial.json').write_text(json.dumps(report, indent=2))
    report.update({'postgres_producao_mesma_identidade': production_identity() == before,
                   'mercado_pago_ambiente_conferido': payment_reference() == frozen,
                   'site_http': http_status(), 'duracao_segundos': round(time.monotonic() - started, 3), 'concluido_em': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    report['aprovado'] = (report['bases_restauradas'] == 19 and report['divergencias_esquema'] == 0
                          and report['divergencias_contagens'] == 0 and report['indices_invalidos'] == 0
                          and report['postgres_producao_mesma_identidade'] and report['mercado_pago_ambiente_conferido']
                          and report['site_http'] == 200)
    (folder / 'resultado.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'bases'}), flush=True)
    if not report['aprovado']:
        sys.exit(2)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'concluido': False, 'classe': type(error).__name__,
                          'motivo': str(error) if type(error) is RuntimeError and re.fullmatch(r'[a-z0-9_]+', str(error)) else 'detalhes_em_log_privado',
                          'logs_privados': str(LOGS) if LOGS else None}), flush=True)
        sys.exit(1)
