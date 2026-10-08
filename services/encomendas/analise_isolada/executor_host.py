"""Ponte de arquivos privados; o leitor recebe somente um anexo e saída vazia."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

IMAGE = 'meshcraft-analise-pratica:20261008-v3'


def salvar(path, data):
    tmp = path.with_suffix('.parcial')
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, path)


def executar(root, job):
    key = job.parent.name
    if not re.fullmatch('[a-f0-9]{64}', key) or job.is_symlink():
        return
    data = json.loads(job.read_text())
    if not re.fullmatch('[a-f0-9]{32}', data.get('chave', '')):
        raise ValueError('Chave de anexo inválida.')
    src = root / data['chave']
    if src.is_symlink() or not src.is_file() or src.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Arquivo ausente ou acima da capacidade do analisador.')
    if hashlib.file_digest(src.open('rb'), 'sha256').hexdigest() != data['sha256']:
        raise ValueError('Conteúdo do anexo diverge da entrega; análise recusada.')
    salvar(job.parent / 'estado.json', {'estado': 'processando'})
    temporarios = root / 'analises-v1' / '.temporarios'
    temporarios.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Mesmo caminho absoluto dentro da ponte e no host do daemon Docker.
    with tempfile.TemporaryDirectory(prefix='meshcraft-anexo-', dir=temporarios) as temp:
        stage = Path(temp) / 'saida'
        stage.mkdir(mode=0o777)
        stage.chmod(0o777)
        name = 'meshcraft-anexo-' + key[:24]
        args = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--user', '65534:65534', '--memory', '1536m', '--memory-swap', '1536m',
                '--cpus', '1.5', '--pids-limit', '64', '--ulimit', 'nofile=128:128',
                '--ulimit', 'fsize=67108864:67108864',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=512m',
                '--mount', 'type=bind,src=' + str(src) + ',dst=/entrada,readonly',
                '--mount', 'type=bind,src=' + str(stage) + ',dst=/saida', IMAGE,
                str(data['nome'])[:255]]
        try:
            proc = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=360)
            if proc.returncode:
                raise ValueError('Analisador indisponível ou limite de recursos atingido.')
            result = stage / 'resultado.json'
            if result.is_symlink() or result.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('Resultado inválido.')
            parsed = json.loads(result.read_text())
            preview = job.parent / 'previas'
            preview.mkdir(mode=0o700, exist_ok=True)
            for file in stage.glob('*.png'):
                if file.is_symlink() or not re.fullmatch('[a-f0-9]{24}(?:-(?:frontal|lateral|perspectiva))?\\.png', file.name):
                    raise ValueError('Prévia inválida.')
                if file.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError('Prévia excedeu capacidade.')
                shutil.copyfile(file, preview / file.name)
            salvar(job.parent / 'resultado.json', parsed)
            salvar(job.parent / 'estado.json', {'estado': 'concluida'})
        finally:
            subprocess.run(['docker', 'stop', '-t', '1', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def rodada(root):
    queue = root / 'analises-v1'
    if not queue.is_dir():
        return
    for job in sorted(queue.glob('*/pedido.json')):
        if (job.parent / 'estado.json').exists():
            state = json.loads((job.parent / 'estado.json').read_text())
            if state.get('estado') in ('concluida', 'falha'):
                continue
        try:
            executar(root, job)
        except Exception as exc:
            salvar(job.parent / 'estado.json', {'estado': 'falha', 'falha': str(exc) if isinstance(exc, ValueError)
                                                else 'Não foi possível examinar o anexo no ambiente isolado.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='/opt/plataforma/encomendas-arquivos/marketplace')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    while True:
        rodada(Path(args.root))
        if args.once:
            break
        time.sleep(3)
