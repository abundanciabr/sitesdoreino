#!/usr/bin/env python3
"""Confere pacote CMS e restaura a coordenação apenas em banco de ensaio novo."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

TABELAS = {
    'autoridade': 'coorte', 'tarefa': 'id', 'historico': 'id',
    'operacao': 'coorte,chave', 'evento': 'id', 'outbox': 'evento',
    'candidato': 'id', 'publicador': 'celula', 'publicacao': 'id',
}


def comando(argumentos, entrada=None):
    resultado = subprocess.run(argumentos, input=entrada, capture_output=True)
    if resultado.returncode:
        if argumentos[:3] == ['docker', 'image', 'inspect']:
            raise RuntimeError('Imagem postgres:17 ausente no Docker local; obtenha a imagem aprovada antes de repetir.')
        if argumentos[:2] == ['docker', 'run']:
            raise RuntimeError('Contêiner isolado não iniciou; confira Docker e use um nome novo sem apagar contêiner existente.')
        raise RuntimeError(f'{argumentos[0]} recusou o pacote ou banco isolado; confira o artefato e o contêiner. Nenhum banco oficial foi alterado.')
    return resultado.stdout


def executar(pacote, certificado, chave, banco, sha256_esperado):
    inicio = time.monotonic()
    if not re.fullmatch(r'coordenacao_ensaio_[a-z0-9_]{1,40}', banco):
        raise ValueError('Destino recusado; use um banco novo coordenacao_ensaio_<nome>.')
    if not re.fullmatch(r'[0-9a-f]{64}', sha256_esperado):
        raise ValueError('SHA-256 oficial ausente; copie o resumo do run antes de restaurar.')
    for arquivo in (pacote, certificado, chave):
        if not arquivo.is_file():
            raise ValueError(f'Arquivo ausente: {arquivo.name}. Confira o caminho local e repita.')
    if hashlib.sha256(pacote.read_bytes()).hexdigest() != sha256_esperado:
        raise ValueError('Pacote divergiu do SHA-256 do run oficial; baixe o artefato novamente.')
    if not shutil.which('openssl') or not shutil.which('docker'):
        raise RuntimeError('OpenSSL ou Docker ausente no computador; instale a ferramenta faltante antes de repetir.')
    comando(['docker', 'image', 'inspect', 'postgres:17'])
    with tempfile.TemporaryDirectory(prefix='coordenacao-restauro-') as pasta:
        claro = Path(pasta) / 'pacote.bin'
        comando(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                 '-in', str(pacote), '-recip', str(certificado),
                 '-inkey', str(chave), '-passin', 'stdin', '-out', str(claro)])
        with claro.open('rb') as origem:
            if origem.read(9) != b'SDRCOORD1':
                raise ValueError('Formato do pacote inválido; obtenha novamente o artefato oficial.')
            comprimento = origem.read(4)
            if len(comprimento) != 4:
                raise ValueError('Manifesto truncado; obtenha novamente o artefato oficial.')
            tamanho = struct.unpack('!I', comprimento)[0]
            if not 0 < tamanho <= 1024 * 1024:
                raise ValueError('Manifesto inválido; obtenha novamente o artefato oficial.')
            manifesto = json.loads(origem.read(tamanho))
            tabelas = manifesto.get('tabelas') if isinstance(manifesto, dict) else None
            if not isinstance(tabelas, dict) or set(tabelas) != set(TABELAS):
                raise ValueError('Manifesto incompleto; obtenha novamente o artefato oficial.')
            if any(not isinstance(meta, dict) or type(meta.get('linhas')) is not int
                   or not isinstance(meta.get('sha256'), str)
                   or not re.fullmatch(r'[0-9a-f]{64}', meta['sha256'])
                   for meta in tabelas.values()):
                raise ValueError('Hashes do manifesto inválidos; obtenha novamente o artefato oficial.')
            dump = origem.read()
        if not dump.startswith(b'PGDMP'):
            raise ValueError('Dump PostgreSQL ausente ou inválido; obtenha novamente o artefato oficial.')
        try:
            data = datetime.fromisoformat(manifesto['capturado_em_utc'].replace('Z', '+00:00'))
            if data.tzinfo is None or data > datetime.now(timezone.utc):
                raise ValueError
        except (KeyError, AttributeError, ValueError) as erro:
            raise ValueError('Data da cópia inválida; obtenha novamente o artefato oficial.') from erro
        comando(['docker', 'run', '-d', '--pull=never', '--name', banco,
                 '--network', 'none', '--cpus', '1', '--memory', '512m',
                 '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17'])
        for _ in range(30):
            pronto = subprocess.run(['docker', 'exec', banco, 'pg_isready',
                                     '-U', 'postgres'], capture_output=True)
            if pronto.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('PostgreSQL isolado não iniciou em 30 segundos; confira o contêiner local antes de repetir.')
        comando(['docker', 'exec', '-i', banco, 'createdb',
                 '-U', 'postgres', 'coordenacao_db'])
        comando(['docker', 'exec', '-i', banco, 'pg_restore',
                 '-U', 'postgres', '-d', 'coordenacao_db', '--no-owner', '--no-acl',
                 '--exit-on-error'], entrada=dump)
        medidos = {}
        for tabela, ordem in TABELAS.items():
            sql = ("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY " + ordem +
                   "), '[]'::jsonb) FROM coordenacao." + tabela + " t")
            saida = comando(['docker', 'exec', '-i', banco, 'psql',
                             '-X', '-q', '-A', '-t', '-U', 'postgres', '-d', 'coordenacao_db',
                             '-c', "SET TIME ZONE 'UTC'; " + sql])
            linhas = json.loads(saida)
            canonico = json.dumps(linhas, ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':'), allow_nan=False).encode()
            medidos[tabela] = {'linhas': len(linhas), 'sha256': hashlib.sha256(canonico).hexdigest()}
        if medidos != manifesto['tabelas']:
            raise RuntimeError('Hashes do ensaio divergiram; não retome escritores. Inspecione o banco isolado.')
        print(json.dumps({
            'estado': 'INTEGRO_ISOLADO', 'conteiner': banco,
            'tabelas_conferidas': len(medidos),
            'idade_copia_segundos': round((datetime.now(timezone.utc) - data).total_seconds(), 3),
            'rto_ensaio_segundos': round(time.monotonic() - inicio, 3),
            'retomada': 'BLOQUEADA_SEM_CONTINUIDADE_DAS_ESCRITAS_POSTERIORES',
        }, sort_keys=True))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 6:
            raise ValueError('Uso: restaurar-coordenacao.py pacote.p7m certificado.pem chave.pem coordenacao_ensaio_<nome> SHA256_DO_RUN. Senha da chave pela entrada padrão, nunca em argumento.')
        executar(*(Path(item) for item in sys.argv[1:4]), sys.argv[4], sys.argv[5])
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as erro:
        print(f'PAROU POR SEGURANÇA: {erro}', file=sys.stderr)
        raise SystemExit(1)
