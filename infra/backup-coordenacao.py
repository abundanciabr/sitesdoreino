#!/usr/bin/env python3
"""Cria uma cópia cifrada e consistente da coordenação no host da plataforma."""

import hashlib
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import sys
import time

RAIZ = Path('/opt/plataforma')
DESTINO = RAIZ / 'backups-coordenacao'
CERTIFICADO = '''-----BEGIN CERTIFICATE-----
MIIFNTCCAx2gAwIBAgIUOgC+r+7G+UfvszAIIGrqrrmtemkwDQYJKoZIhvcNAQEL
BQAwKjEoMCYGA1UEAwwfU2l0ZXNkb1JlaW5vLWNvb3JkZW5hY2FvLWJhY2t1cDAe
Fw0yNjA5MjkxNjA3MjZaFw0zNjA5MjYxNjA3MjZaMCoxKDAmBgNVBAMMH1NpdGVz
ZG9SZWluby1jb29yZGVuYWNhby1iYWNrdXAwggIiMA0GCSqGSIb3DQEBAQUAA4IC
DwAwggIKAoICAQCU4YvIcChPSO7kML4xWf1zRTLwW8Tm3ssI/monOZlRtO2wpho7
IrukT9j3vdbUWxVzLNc3OfMbkwvx44eOD2gCJSfrk6BRQcyhEIhrDugBKs0Ts4nA
vQl48KFTcJGK6Yi5sKyfFfLUj0dz1qtEnDTcn8dmK4qzO9Trk7pC9n3jMKIbPh2Y
EGC11DoQGzfYNAOXx15e55BYztloaVe80bOUqSPzldmmj/f8Jp8HjRTaMNd2lB+r
jEewqEeQJIJqc+Zzkjb66LVH9zuigCNPKeLTnwLilmVfrCb3C0bChuShETG++iNo
HabdqhN0wHftk44TdAtcMUD8XDlD6Reg/H9K1LARBVxi4n2KIE5MFbhGuJ7+DS3R
/78aJV90NZ9ADtzSNApzp2lNtf0unb6Vvlqcmp6c/g0rd43f6mWWPHP+eZQZWppq
t9VjUhXVc9cU1T9wqBG4wfQydXSIUZ3QuQIZxSTl0fpCVgF9Lq6gDQYqR/y7z/sq
4lpx6I1sFslizNdI1f0rLKFz7mYVrUtAL+GsvHzuA1Ljw3okU0moqgYHZBh8kebz
t9oqi8pi69tEWcpImLi1rXw9wnASXFerfVug+mrt9JsZ0/hczaxp2bB2jxCVB0EB
G15ISHxEBLIx1nSlZzzmappFsbOJynnskLYNy3nEKhNRTRgksOZgrtk1RQIDAQAB
o1MwUTAdBgNVHQ4EFgQUuhFsRlOJOTgZxsbbLpGt3jrLuh0wHwYDVR0jBBgwFoAU
uhFsRlOJOTgZxsbbLpGt3jrLuh0wDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0B
AQsFAAOCAgEAcyoY/9rPDpigPyG6BOiBYo3qv2b89JO/6QCMpNw3jymNJX5v7ANd
J/l4QXdNIAs2EcN2P1ScIXRV87uxZ6XO2Hhjqkj48Lwc3L1i4dRj+wOBE0uvw+NE
4jtyNOaM82yNGE4rnW8PO4qSH+wftXqfbRNtqwe/ZPmdGL3SiBpx7C3x5ig+aAAq
fXD7m0q50F+LUlvoxVbUXbe+SdTy+F3IP/rhXZhT/yWT5wWTR2LSvHTWL+X7L/Z6
21zL6vLLLiwZryjM8KUvVmEE6hEVcNVRN91K37ZBFaywgdYBvT9LJ1hymwRum8QC
mx3JbozDbVpS/NEkTswqpAoPw0HpyCiBb1DP7bTOt/Y7uSTpQ1z+sAMEq9j1wDzx
QvtG8Iot3l9EkpnLSCVwa6Wf8zE0rm2/awbzmNPoaSvFMa1kg5ZJoIjWV0ume/5I
ubXX4agKf5CqqGsD7x3vpG5tZ58Cy3SKx7lFDDa+ikA+kHEMlJ2HNFNAiPZE3yVp
Jmo5emmYZfG3Qh4fVWfAQ6EuMHoAdO5w8GhTQrYdWxSYNCWXlojMsSNCb5EMEgbg
SdkNrRc3ziNIw7TiTVN6BKsgO/gKMcY7RXaqiPcYrNAnGvFzVK8svGcoidXbV1wr
UV+gfWWEIHIf0IXlh+FSRGFykgUFoeE+/r97JctRGExsQU3+Ge+9oB8=
-----END CERTIFICATE-----'''
CAPTURA = '''import json, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
fase = 'inicializacao'
manifesto_emitido = False
try:
    import django
    django.setup()
    from apps.core.coordenacao import banco, capturar_snapshot
    fase = 'conexao'
    with banco():
        pass
    fase = 'captura'
    with capturar_snapshot() as manifesto:
        print(json.dumps(manifesto, ensure_ascii=False, separators=(',', ':')), flush=True)
        manifesto_emitido = True
        if sys.stdin.readline() != 'concluido\\n':
            raise RuntimeError('pg_dump não confirmou conclusão; snapshot descartado')
except Exception:
    if not manifesto_emitido:
        print(json.dumps({'falha': fase}), flush=True)
    raise SystemExit(1)
'''


def id_conteiner(servico):
    try:
        lista = subprocess.run(
            ['docker', 'ps', '--all', '--quiet', '--no-trunc',
             '--filter', 'label=com.docker.compose.project=plataforma',
             '--filter', f'label=com.docker.compose.service={servico}'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
            text=True, encoding='ascii', errors='replace',
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise RuntimeError(f'Docker não listou {servico}; confira o serviço na VPS.') from erro
    if lista.returncode:
        raise RuntimeError(f'Docker não listou {servico}; confira o serviço na VPS.')
    ids = lista.stdout.splitlines()
    if not ids:
        raise RuntimeError(f'Contêiner {servico} ausente; confira o serviço na VPS.')
    if len(ids) != 1:
        raise RuntimeError(f'Contêiner {servico} duplicado; reconcilie o serviço na VPS.')
    identificador = ids[0]
    if not re.fullmatch(r'[0-9a-f]{64}', identificador):
        raise RuntimeError(f'ID do contêiner {servico} inválido; confira o Docker na VPS.')
    try:
        inspecao = subprocess.run(
            ['docker', 'inspect', '--format',
             '{{json .State.Running}}|{{index .Config.Labels "com.docker.compose.project"}}|'
             '{{index .Config.Labels "com.docker.compose.service"}}', identificador],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
            text=True, encoding='ascii', errors='replace',
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise RuntimeError(f'Docker não conferiu {servico}; confira o serviço na VPS.') from erro
    if inspecao.returncode:
        raise RuntimeError(f'Docker não conferiu {servico}; confira o serviço na VPS.')
    estado = inspecao.stdout.strip()
    if estado == f'false|plataforma|{servico}':
        raise RuntimeError(f'Contêiner {servico} parado; recupere o serviço na VPS.')
    if estado != f'true|plataforma|{servico}':
        raise RuntimeError(f'Identidade do contêiner {servico} divergiu; reconcilie o serviço na VPS.')
    return identificador


def executar(identificador):
    if not re.fullmatch(r'[0-9]{1,20}', identificador):
        raise ValueError('Identificador de execução inválido; use o número do run oficial.')
    os.chdir(RAIZ)
    DESTINO.mkdir(mode=0o700, exist_ok=True)
    os.chmod(DESTINO, 0o700)
    final = DESTINO / f'{identificador}.p7m'
    temporario = DESTINO / f'.{identificador}.p7m.tmp'
    certificado = DESTINO / f'.{identificador}.cert.pem'
    if final.exists() or temporario.exists():
        raise ValueError('Execução já possui pacote; use um novo run oficial.')
    certificado.write_text(CERTIFICADO, encoding='ascii')
    os.chmod(certificado, 0o600)
    inicio = time.monotonic()
    captura = None
    cifra = None
    dump = None
    try:
        admin = id_conteiner('admin')
        postgres = id_conteiner('postgres')
        captura = subprocess.Popen(
            ['docker', 'exec', '-i', admin, 'python', '-c', CAPTURA],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        if not select.select([captura.stdout], [], [], 60)[0]:
            raise RuntimeError('Snapshot não respondeu em 60 segundos; confira o admin e repita em novo run.')
        linha = captura.stdout.readline()
        if not linha:
            raise RuntimeError('Snapshot não abriu; confira a célula admin e o banco de coordenação.')
        try:
            manifesto = json.loads(linha)
        except json.JSONDecodeError as erro:
            raise RuntimeError('Resposta da captura inválida; confira a célula admin.') from erro
        if isinstance(manifesto, dict) and set(manifesto) == {'falha'}:
            acoes = {
                'inicializacao': 'Falha na inicialização da captura; confira a imagem e o serviço admin.',
                'conexao': 'Falha na conexão com o banco de coordenação; confira o banco na célula admin.',
                'captura': 'Falha na captura do esquema; confira as nove tabelas da coordenação.',
            }
            fase = manifesto['falha']
            if not isinstance(fase, str) or fase not in acoes:
                raise RuntimeError('Fase de falha inválida; confira a célula admin.')
            raise RuntimeError(acoes[fase])
        if (not isinstance(manifesto, dict) or not manifesto.get('snapshot_id')
                or not isinstance(manifesto.get('tabelas'), dict)
                or len(manifesto['tabelas']) != 9):
            raise RuntimeError('Snapshot incompleto; confira o contrato da coordenação.')
        snapshot_id = manifesto.pop('snapshot_id')
        manifesto.pop('autoridades', None)
        manifesto['capturado_em_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        cabecalho = json.dumps(manifesto, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        if len(cabecalho) > 1024 * 1024:
            raise RuntimeError('Manifesto excede 1 MiB; confira a quantidade de autoridades.')
        cifra = subprocess.Popen(
            ['openssl', 'cms', '-encrypt', '-binary', '-outform', 'DER',
             '-aes-256-gcm', '-recip', str(certificado),
             '-keyopt', 'rsa_padding_mode:oaep', '-keyopt', 'rsa_oaep_md:sha256',
             '-out', str(temporario)],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        dump = subprocess.Popen(
            ['docker', 'exec', postgres, 'pg_dump', '-U', 'postgres',
             '-d', 'coordenacao_db', '-Fc', '--no-owner', '--no-acl',
             '--snapshot', snapshot_id, '--lock-wait-timeout=30000'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        try:
            cifra.stdin.write(b'SDRCOORD1' + struct.pack('!I', len(cabecalho)) + cabecalho)
            total = len(cabecalho) + 13
            while bloco := dump.stdout.read(1024 * 1024):
                total += len(bloco)
                if total > 16 * 1024 * 1024 - 16384:
                    raise RuntimeError('Dump excede o piloto de 16 MiB; aumente o limite com aprovação antes de repetir.')
                cifra.stdin.write(bloco)
            if dump.wait(timeout=120) != 0:
                raise RuntimeError('pg_dump falhou; confira o banco de coordenação e repita em novo run.')
        finally:
            cifra.stdin.close()
            if dump.poll() is None:
                dump.kill()
                dump.wait()
        if cifra.wait(timeout=120) != 0:
            raise RuntimeError('Cifra CMS falhou; confira OpenSSL e certificado público.')
        captura.stdin.write(b'concluido\n')
        captura.stdin.flush()
        captura.stdin.close()
        if captura.wait(timeout=30) != 0:
            raise RuntimeError('Snapshot não confirmou o fim; descarte o pacote e repita.')
        temporario.replace(final)
        resumo = {
            'arquivo': final.name,
            'bytes': final.stat().st_size,
            'sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
            'capturado_em_utc': manifesto['capturado_em_utc'],
            'segundos': round(time.monotonic() - inicio, 3),
        }
        print(json.dumps(resumo, sort_keys=True))
    finally:
        for processo in (dump, cifra):
            if processo is not None and processo.poll() is None:
                processo.kill()
                processo.wait()
        if captura is not None and captura.poll() is None:
            captura.kill()
            captura.wait()
        certificado.unlink(missing_ok=True)
        temporario.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        executar(sys.argv[1] if len(sys.argv) == 2 else '')
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError,
            subprocess.SubprocessError) as erro:
        print(f'PAROU POR SEGURANÇA: {erro}', file=sys.stderr)
        raise SystemExit(1)
