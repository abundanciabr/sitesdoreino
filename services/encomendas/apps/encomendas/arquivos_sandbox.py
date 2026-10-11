"""Formatos do envio de modelos e imagens; a avaliação continua na fila."""

import ctypes
import ctypes.util
import gzip
import json
from functools import lru_cache
from pathlib import Path
import struct

FORMATOS = {'.glb': 'model/gltf-binary', '.blend': 'application/octet-stream',
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'}
ACEITAR = ','.join(FORMATOS)
ORIENTACAO = 'Envie o modelo em .glb ou .blend e as imagens do briefing em PNG, JPG ou WebP. ZIP, PDF e outros formatos não são aceitos.'


class ArquivoInvalido(ValueError):
    pass


def formato(nome):
    extensao = Path(str(nome).replace('\\', '/')).suffix.lower()
    if extensao not in FORMATOS:
        raise ArquivoInvalido(ORIENTACAO)
    return extensao


@lru_cache(maxsize=1)
def _zstd():
    lib = ctypes.CDLL(ctypes.util.find_library('zstd') or 'libzstd.so.1')
    lib.ZSTD_createDStream.restype = ctypes.c_void_p
    lib.ZSTD_initDStream.argtypes = [ctypes.c_void_p]
    lib.ZSTD_initDStream.restype = ctypes.c_size_t
    lib.ZSTD_decompressStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.ZSTD_decompressStream.restype = ctypes.c_size_t
    lib.ZSTD_freeDStream.argtypes = [ctypes.c_void_p]
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    lib.ZSTD_isError.restype = ctypes.c_uint
    return lib


def _cabecalho_zstd(arquivo):
    # Apenas os primeiros 12 bytes descomprimidos; nunca expande o projeto inteiro.
    class Buffer(ctypes.Structure):
        _fields_ = [('data', ctypes.c_void_p), ('size', ctypes.c_size_t), ('pos', ctypes.c_size_t)]
    lib = _zstd()
    stream = lib.ZSTD_createDStream()
    if not stream:
        raise ArquivoInvalido('Não foi possível conferir o projeto comprimido. Salve o .blend sem comprimir e tente novamente.')
    saida = ctypes.create_string_buffer(12)
    out = Buffer(ctypes.cast(saida, ctypes.c_void_p), 12, 0)
    try:
        if lib.ZSTD_isError(lib.ZSTD_initDStream(stream)):
            raise ArquivoInvalido('Projeto Blender comprimido inválido.')
        # Limita também a leitura comprimida usada para descobrir o cabeçalho.
        for _ in range(16):
            bloco = arquivo.read(65536)
            if not bloco:
                break
            entrada = ctypes.create_string_buffer(bloco)
            src = Buffer(ctypes.cast(entrada, ctypes.c_void_p), len(bloco), 0)
            while src.pos < src.size and out.pos < out.size:
                antes = (src.pos, out.pos)
                result = lib.ZSTD_decompressStream(stream, ctypes.byref(out), ctypes.byref(src))
                if lib.ZSTD_isError(result) or antes == (src.pos, out.pos):
                    raise ArquivoInvalido('Projeto Blender comprimido inválido.')
            if out.pos == 12:
                return saida.raw
        raise ArquivoInvalido('Cabeçalho do projeto Blender incompleto.')
    finally:
        lib.ZSTD_freeDStream(stream)


def _blend(arquivo, tamanho):
    inicio = arquivo.read(12)
    arquivo.seek(0)
    try:
        if inicio.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=arquivo) as comprimido:
                inicio = comprimido.read(12)
        elif inicio.startswith(b'\x28\xb5\x2f\xfd'):
            inicio = _cabecalho_zstd(arquivo)
    except (OSError, EOFError) as exc:
        raise ArquivoInvalido('Projeto Blender comprimido inválido. Salve novamente no Blender.') from exc
    if (len(inicio) != 12 or inicio[:7] != b'BLENDER' or inicio[7:8] not in (b'_', b'-')
            or inicio[8:9] not in (b'v', b'V') or not inicio[9:12].isdigit() or tamanho <= 12):
        raise ArquivoInvalido('Este arquivo não tem um cabeçalho Blender válido. Salve o projeto como .blend no Blender; renomear outro arquivo não funciona.')


def _glb(arquivo, tamanho):
    cabecalho = arquivo.read(12)
    if len(cabecalho) != 12 or struct.unpack('<4sII', cabecalho) != (b'glTF', 2, tamanho):
        raise ArquivoInvalido('Este arquivo não é um GLB 2.0 válido. Exporte o modelo como glTF Binary (.glb); renomear outro arquivo não funciona.')
    posicao, documento, primeiro = 12, None, True
    while posicao < tamanho:
        cabecalho = arquivo.read(8)
        if len(cabecalho) != 8:
            raise ArquivoInvalido('O arquivo GLB está incompleto. Exporte novamente.')
        comprimento, tipo = struct.unpack('<II', cabecalho)
        posicao += 8
        if comprimento % 4 or posicao + comprimento > tamanho or (primeiro and tipo != 0x4E4F534A):
            raise ArquivoInvalido('A estrutura do GLB é inválida. Exporte novamente.')
        if primeiro:
            # A malha binária pode ser grande; somente o JSON é lido em memória.
            if comprimento > 16 * 1024 * 1024:
                raise ArquivoInvalido('Os metadados do GLB excedem a capacidade do leitor. Simplifique a exportação.')
            try:
                documento = json.loads(arquivo.read(comprimento))
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ArquivoInvalido('Os metadados do GLB são ilegíveis. Exporte novamente.') from exc
        else:
            arquivo.seek(comprimento, 1)
        posicao += comprimento
        primeiro = False
    if not isinstance(documento, dict) or not isinstance(documento.get('asset'), dict) or documento['asset'].get('version') != '2.0':
        raise ArquivoInvalido('O arquivo não contém um projeto glTF 2.0 válido.')
    meshes, accessors = documento.get('meshes', []), documento.get('accessors', [])
    if not isinstance(meshes, list) or not isinstance(accessors, list):
        raise ArquivoInvalido('A estrutura do modelo GLB é inválida.')
    for malha in meshes:
        if not isinstance(malha, dict) or not isinstance(malha.get('primitives'), list):
            continue
        for parte in malha['primitives']:
            atributos = parte.get('attributes', {}) if isinstance(parte, dict) else {}
            indice = atributos.get('POSITION') if isinstance(atributos, dict) else None
            if type(indice) is int and 0 <= indice < len(accessors) and isinstance(accessors[indice], dict):
                quantidade = accessors[indice].get('count')
                if type(quantidade) is int and quantidade > 0:
                    return
    raise ArquivoInvalido('O GLB não contém uma malha 3D. Exporte o modelo, em vez de uma cena vazia.')


def validar(nome, arquivo):
    """Confere o formato básico sem executar o projeto e preserva o cursor."""
    extensao = formato(nome)
    posicao = arquivo.tell()
    try:
        arquivo.seek(0, 2)
        tamanho = arquivo.tell()
        arquivo.seek(0)
        if extensao == '.blend':
            _blend(arquivo, tamanho)
        elif extensao == '.glb':
            _glb(arquivo, tamanho)
        else:
            # A decodificação completa das imagens continua no leitor isolado.
            cabecalho = arquivo.read(32)
            if extensao == '.png':
                valido = len(cabecalho) >= 24 and cabecalho[:8] == b'\x89PNG\r\n\x1a\n' and cabecalho[12:16] == b'IHDR' and all(struct.unpack('>II', cabecalho[16:24]))
            elif extensao in ('.jpg', '.jpeg'):
                arquivo.seek(max(0, tamanho - 2))
                valido = cabecalho.startswith(b'\xff\xd8\xff') and arquivo.read(2) == b'\xff\xd9'
            else:
                valido = len(cabecalho) >= 16 and cabecalho[:4] == b'RIFF' and cabecalho[8:12] == b'WEBP' and struct.unpack('<I', cabecalho[4:8])[0] + 8 == tamanho and cabecalho[12:16] in (b'VP8 ', b'VP8L', b'VP8X')
            if not valido:
                raise ArquivoInvalido('A imagem não corresponde ao formato informado. Exporte uma imagem PNG, JPG ou WebP; renomear outro arquivo não funciona.')
        return FORMATOS[extensao]
    finally:
        arquivo.seek(posicao)
