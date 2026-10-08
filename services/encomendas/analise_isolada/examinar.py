"""Leitores executados exclusivamente no contêiner descartável, sem rede."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import subprocess
import sys
import zipfile

from PIL import Image

Image.MAX_IMAGE_PIXELS = 24000000
MAX_BYTES = 256 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_FILES = 200
OUT = Path('/saida')
WORK = Path('/tmp/extraidos')


def imagem(path, nome):
    with Image.open(path) as im:
        im.load()
        medidas = {'largura_px': im.width, 'altura_px': im.height, 'formato': im.format}
        im.thumbnail((1024, 1024))
        destino = hashlib.sha256(nome.encode()).hexdigest()[:24] + '.png'
        im.convert('RGB').save(OUT / destino)
    return {'medidas': medidas, 'imagens': [{'arquivo': destino, 'vista': 'imagem enviada', 'evidencia': nome}]}


def glb_info(path):
    with path.open('rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        if magic != b'glTF' or version != 2 or length != path.stat().st_size:
            raise ValueError('Cabeçalho GLB ilegível ou incompleto.')
        n, kind = struct.unpack('<I4s', f.read(8))
        if kind != b'JSON' or n > 8 * 1024 * 1024 or n + 20 > length:
            raise ValueError('Estrutura GLB ilegível.')
        dados = json.loads(f.read(n))
    # A geometria e UV são lidas pelo Blender; aqui constam declarações do GLB.
    return {'materiais_declarados': dados.get('materials', []),
            'texturas_declaradas': dados.get('textures', []),
            'imagens_declaradas': [{'nome': i.get('name', ''), 'mime': i.get('mimeType'),
                                   'embutida': 'bufferView' in i or str(i.get('uri', '')).startswith('data:'),
                                   'externa': bool(i.get('uri')) and not str(i.get('uri')).startswith('data:')}
                                  for i in dados.get('images', [])],
            'extensoes_requeridas': dados.get('extensionsRequired', [])}


def modelo(path, nome):
    prefix = hashlib.sha256(nome.encode()).hexdigest()[:24]
    extra = glb_info(path) if path.suffix.lower() == '.glb' else {}
    proc = subprocess.run(['blender', '--background', '--factory-startup', '--disable-autoexec',
                           '--threads', '2', '--python-exit-code', '2', '--python',
                           '/analisador/blender_examinar.py', '--', str(path), prefix],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=150)
    if proc.returncode and not (OUT / (prefix + '.json')).is_file():
        raise ValueError('Não foi possível abrir ou renderizar este projeto 3D.')
    dados = json.loads((OUT / (prefix + '.json')).read_text())
    if proc.returncode:
        dados['aviso'] = 'Geometria examinada, mas as vistas não puderam ser renderizadas.'
    dados['medidas'].update(extra)
    for i in dados['imagens']:
        i['evidencia'] = nome
    return dados


def examinar(path, nome, resultado, budget, depth=0):
    item = {'arquivo': nome, 'estado': 'concluida', 'medidas': {}, 'imagens': []}
    resultado.append(item)
    try:
        if not path.stat().st_size:
            raise ValueError('Arquivo vazio: nenhum conteúdo foi examinado.')
        ext = path.suffix.lower()
        if ext == '.zip':
            if depth >= 2:
                raise ValueError('ZIP aninhado além da capacidade de extração; conteúdo não examinado.')
            with zipfile.ZipFile(path) as z:
                entries = z.infolist()
                if len(entries) + budget['files'] > MAX_FILES:
                    raise ValueError('ZIP ultrapassa a capacidade de extração de arquivos.')
                # Confere todos os caminhos ANTES de extrair qualquer membro.
                for info in entries:
                    p = PurePosixPath(info.filename.replace('\\', '/'))
                    if p.is_absolute() or '..' in p.parts or ':' in str(p) or stat.S_ISLNK(info.external_attr >> 16):
                        raise ValueError('ZIP contém caminho inseguro ou link; não foi extraído.')
                    if info.flag_bits & 1:
                        raise ValueError('ZIP protegido por senha: não foi extraído.')
                    if info.file_size > MAX_FILE or info.file_size > max(1, info.compress_size) * 200:
                        raise ValueError('ZIP excede a capacidade de descompressão segura.')
                size = sum(i.file_size for i in entries)
                if budget['bytes'] + size > MAX_BYTES:
                    raise ValueError('ZIP excede a memória de extração disponível.')
                budget['files'] += len(entries)
                budget['bytes'] += size
                directory = WORK / hashlib.sha256(nome.encode()).hexdigest()
                directory.mkdir(parents=True, exist_ok=True)
                for info in entries:
                    if info.is_dir():
                        continue
                    dest = directory / PurePosixPath(info.filename.replace('\\', '/'))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, dest.open('xb') as target:
                        total = 0
                        while block := src.read(65536):
                            total += len(block)
                            if total > info.file_size or total > MAX_FILE:
                                raise ValueError('ZIP excedeu o tamanho declarado.')
                            target.write(block)
                item['medidas'] = {'arquivos_no_zip': [i.filename for i in entries if not i.is_dir()]}
                for info in entries:
                    if not info.is_dir():
                        examinar(directory / PurePosixPath(info.filename.replace('\\', '/')),
                                 nome + ' / ' + info.filename, resultado, budget, depth + 1)
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
            item.update(imagem(path, nome))
        elif ext in ('.glb', '.blend'):
            item.update(modelo(path, nome))
        elif ext in ('.txt', '.md', '.json', '.csv', '.mtl'):
            item['texto'] = path.read_bytes()[:24000].decode('utf-8', errors='replace')
            item['texto_truncado'] = path.stat().st_size > 24000
        else:
            item['estado'] = 'nao_examinado'
            item['falha'] = 'Formato sem leitor disponível; conteúdo não foi aberto.'
    except Exception as exc:
        item['estado'] = 'falha'
        item['falha'] = (str(exc) if isinstance(exc, ValueError) else
                         'Arquivo ilegível ou processamento excedeu os recursos disponíveis.')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    source = Path('/entrada')
    name = sys.argv[1]
    # Preserva a extensão para selecionar o leitor; entrada é um único arquivo ro.
    local = WORK / ('arquivo' + Path(name).suffix.lower())
    local.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(source, local)
    result = []
    examinar(local, name, result, {'bytes': 0, 'files': 0})
    (OUT / 'resultado.json').write_text(json.dumps({'arquivos': result}, ensure_ascii=False))
