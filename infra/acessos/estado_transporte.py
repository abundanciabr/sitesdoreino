"""Transporte em blocos; mantém integralmente o JSON público já produzido pelo broker."""
import hashlib
import json
import shutil
import sys
import tempfile

MAX_LINE = 131072
BLOCK = 8192


def enviar(conn, response):
    if not response.pop('_blocos', False):
        conn.sendall(json.dumps(response, ensure_ascii=True).encode())
        return
    def line(data):
        conn.sendall(json.dumps(data, ensure_ascii=True).encode() + b'\n')
    output = response['saida']
    line({'formato': 'blocos-v1', 'codigo': response['codigo']})
    digest = hashlib.sha256()
    size = 0
    for offset in range(0, len(output), BLOCK):
        part = output[offset:offset + BLOCK]
        raw = part.encode('utf-8')
        digest.update(raw)
        size += len(raw)
        line({'trecho': part})
    line({'fim': True, 'bytes': size, 'sha256': digest.hexdigest()})


def receber(conn, output=None):
    """Só mostra a resposta após conferir fim e integridade; truncamento não vira sucesso."""
    if output is None:
        output = sys.stdout
    with conn.makefile('rb') as stream:
        first = stream.readline(MAX_LINE + 1)
        if not first:
            raise ValueError('resposta ausente')
        # Comandos antigos continuam com o envelope e limites originais.
        try:
            head = json.loads(first) if len(first) <= MAX_LINE else None
        except ValueError:
            head = None
        if isinstance(head, dict) and head.get('formato') == 'blocos-v1':
            if set(head) != {'formato', 'codigo'} or type(head['codigo']) is not int or head['codigo'] not in (0, 2, 3):
                raise ValueError('cabecalho invalido')
            digest = hashlib.sha256()
            size = 0
            with tempfile.SpooledTemporaryFile(max_size=1048576, mode='w+', encoding='utf-8', newline='') as saved:
                while True:
                    raw = stream.readline(MAX_LINE + 1)
                    if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
                        raise ValueError('bloco incompleto')
                    item = json.loads(raw)
                    if isinstance(item, dict) and set(item) == {'trecho'} and type(item['trecho']) is str:
                        part = item['trecho']
                        if len(part) > BLOCK:
                            raise ValueError('bloco excessivo')
                        encoded = part.encode('utf-8')
                        digest.update(encoded)
                        size += len(encoded)
                        saved.write(part)
                    elif (isinstance(item, dict) and set(item) == {'fim', 'bytes', 'sha256'}
                          and item['fim'] is True and type(item['bytes']) is int
                          and item['bytes'] == size and item['sha256'] == digest.hexdigest()):
                        if stream.read(1):
                            raise ValueError('dados depois do fim')
                        saved.seek(0)
                        shutil.copyfileobj(saved, output, length=65536)
                        return head['codigo']
                    else:
                        raise ValueError('integridade invalida')
        raw = first + stream.read(262145 - len(first))
        if len(raw) > 262144:
            raise ValueError('resposta excessiva')
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {'codigo', 'saida'}
                or type(data['codigo']) is not int or data['codigo'] not in (0, 2, 3)
                or not isinstance(data['saida'], str)):
            raise ValueError('resposta invalida')
        output.write(data['saida'])
        return data['codigo']
