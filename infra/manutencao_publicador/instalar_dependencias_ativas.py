#!/usr/bin/env python3
"""Instala a correção 27de802 pelo instalador transacional já existente.

Executar na VPS Linux com privilégio administrativo: --aplicar.
Não altera permissões SSH, políticas, banco, fila ou código do site.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.request import urlopen

COMMIT = '27de802b709e25dd2dd77bd8dfe77fdad02adce9'
RAW = 'https://raw.githubusercontent.com/abundanciabr/sitesdoreino/' + COMMIT + '/'
SITE = 'https://meshcraft.top/'
PROVA_ID = '626fb260b252'
INSTALLER = 'infra/manutencao_publicador/aplicar_canal.py'
INSTALLER_HASH = '40b8f5a5685e2eb01a8b53b142a97bc7fdcb05f5b918c05f13e1a3ba419dc305'
SOURCES = {
    'infra/integrador_servico.py': (
        '17917ea2002d3a0fc5d47eb2033472639f54f4a2e72db246ecfb7b1bd03ac415',
        '770268cb9d74fd0186d8c1af62c5eca034ae62008bae0456bd3a79af61e006e3',
        ('integrador/integrador_servico.py',)),
    'infra/ponte_entregas.py': (
        '058e7cad9d321f2c4d91ecf49635ab120f5046e5ead4391869f76045ee92d0ed',
        '5257e63fcb36c9c654a42a07721f430ce2bf027fe041274ab6927d6c99dd0aa0',
        ('integrador/ponte_entregas.py', 'publicador/infra/ponte_entregas.py')),
}


def download(path):
    with urlopen(RAW + path, timeout=60) as response:
        return response.read(2_000_001)


def verified(data, expected, path):
    if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Fonte diferente da revisão aprovada: ' + path)
    compile(data, path, 'exec')
    return data


def prepare(destination, fetch=download):
    # Confere todas as fontes antes de criar o manifesto ou importar o instalador.
    files = {path: verified(fetch(path), spec[1], path) for path, spec in SOURCES.items()}
    installer = verified(fetch(INSTALLER), INSTALLER_HASH, INSTALLER)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'aplicar_canal.py').write_bytes(installer)
    entries = []
    for path, (before, after, targets) in SOURCES.items():
        for target in targets:
            source = 'fontes/' + target
            output = destination / source
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(files[path])
            entries.append({'alvo': target, 'antes': before, 'depois': after, 'origem': source})
    (destination / 'manifest.json').write_text(json.dumps({
        'prova_id': PROVA_ID, 'commit': COMMIT, 'arquivos': entries}, indent=2), encoding='utf-8')


def site_ok():
    with urlopen(SITE, timeout=20) as response:
        if response.status != 200 or response.url.rstrip('/') != SITE.rstrip('/'):
            raise RuntimeError('A página inicial não respondeu no endereço esperado.')


def install(package, installer, probe=site_ok):
    release = installer.release_atual()
    manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    already = all(installer.required_hash(installer.alvo_path(item['alvo'], release)) == item['depois']
                  for item in manifest['arquivos'])
    probe()
    if already:
        # Bytes em disco não provam qual versão um processo antigo carregou.
        return {'alterado': False, 'arquivos_ja_presentes': True,
                'execucao_da_correcao': 'não comprovada nesta consulta', 'site_http': 200}
    installer.manifest(package, release)  # Recusa base divergente antes de parar serviços.
    original_resume = installer.resume_units

    def resume_and_check(active, *, restart=False):
        original_resume(active, restart=restart)
        if restart:
            return  # Recuperação usa o procedimento original, inclusive suas conferências.
        for unit in active:
            state = installer.run('systemctl', 'is-active', unit, check=False).stdout.strip()
            if state != 'active':
                raise RuntimeError('Serviço não retomou: ' + unit)
        probe()  # Uma falha ainda está dentro do try/except que retorna o código anterior.

    installer.resume_units = resume_and_check
    started = time.monotonic()
    try:
        installer.apply(package)
    finally:
        installer.resume_units = original_resume
    return {'alterado': True, 'commit': COMMIT, 'site_http': 200,
            'duracao_instalacao_segundos': round(time.monotonic() - started, 3),
            'medicao_de_entrega_posterior': 'ainda não realizada'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true', required=True)
    parser.parse_args()
    if sys.platform != 'linux' or not hasattr(os, 'geteuid') or os.geteuid() != 0:
        parser.error('Execute na VPS, em uma sessão SSH administrativa, com sudo ou root.')
    os.umask(0o077)
    parent = Path('/opt/plataforma/manutencoes')
    parent.mkdir(parents=True, exist_ok=True)
    package = Path(tempfile.mkdtemp(prefix='dependencias-27de802-', dir=parent))
    try:
        prepare(package)
        spec = importlib.util.spec_from_file_location('instalador_existente', package / 'aplicar_canal.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        print(json.dumps(install(package, installer), ensure_ascii=False))
        return 0
    except Exception as error:
        # O instalador preserva seu backup e tenta o retorno; não afirmar sucesso na falha.
        print(json.dumps({'instalacao_confirmada': False, 'tipo': type(error).__name__,
                          'erro': str(error)[:300]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
