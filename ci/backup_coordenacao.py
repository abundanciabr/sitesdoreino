"""Confere o pacote cifrado recebido pelo runner antes de publicar o artefato."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

LIMITE = 16 * 1024 * 1024


def verificar(resumo_path, pacote_path):
    resumo = json.loads(resumo_path.read_text(encoding='utf-8'))
    if not re.fullmatch(r'[0-9]{1,20}\.p7m', resumo.get('arquivo', '')):
        raise ValueError('Nome do pacote recusado; confira o run oficial.')
    if pacote_path.name != resumo['arquivo']:
        raise ValueError('Pacote recebido não corresponde ao run oficial.')
    tamanho = pacote_path.stat().st_size
    if not 0 < tamanho <= LIMITE or tamanho != resumo.get('bytes'):
        raise ValueError('Tamanho do pacote inválido ou acima de 16 MiB; não publique.')
    with pacote_path.open('rb') as pacote:
        digest = hashlib.file_digest(pacote, 'sha256').hexdigest()
    if digest != resumo.get('sha256'):
        raise ValueError('SHA-256 divergiu no transporte; não publique.')
    cms = subprocess.run(['openssl', 'cms', '-cmsout', '-print', '-inform', 'DER',
                          '-in', str(pacote_path)], capture_output=True, text=True,
                         encoding='utf-8')
    oaep = re.search(r'algorithm:\s*rsaesOaep.*?encryptedKey:', cms.stdout, re.S)
    if (cms.returncode or not re.search(
            r'contentEncryptionAlgorithm:\s*algorithm:\s*aes-256-gcm\b', cms.stdout)
            or not oaep
            or cms.stdout.count('d.ktri:') != 1
            or len(re.findall(r'OBJECT\s*:sha256\b', oaep.group())) != 2
            or not re.search(r'OBJECT\s*:mgf1\b', oaep.group())):
        raise ValueError('CMS não prova AES-256-GCM e RSA-OAEP com SHA-256 em hash e MGF1; não publique.')
    print(json.dumps({'estado': 'CIFRA_CONFERIDA', 'arquivo': pacote_path.name,
                      'bytes': tamanho, 'sha256': digest,
                      'capturado_em_utc': resumo['capturado_em_utc']}, sort_keys=True))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError('Uso: backup_coordenacao.py resumo.json run.p7m')
        verificar(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, OSError, json.JSONDecodeError) as erro:
        print(f'PAROU POR SEGURANÇA: {erro}', file=sys.stderr)
        raise SystemExit(1)
