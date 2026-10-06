"""Transportes fixados pelo publicador; não importam o código da célula."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import BoundedSemaphore
import http.client
import json
import time
from urllib.parse import urlsplit
import uuid

EVENTOS_FUNIL = frozenset({
    'funil.pagina-vista', 'funil.secao-vista', 'funil.cta-clicado',
    'funil.lead-capturado',
})
PARES_FUNIL = frozenset({'catalogo', 'identidade', 'leads', 'alunos',
                        'notificacoes', 'mensageria', 'quiz'})
MAX_CORPO = 262144


def conferir_evento(stream, campos):
    if not stream.startswith('eventos.') or stream[8:] not in EVENTOS_FUNIL:
        raise ValueError('produtor não autorizado')
    if set(campos) != {'json'} or len(campos['json'].encode()) > 65536:
        raise ValueError('envelope fora do alcance')
    evento = json.loads(campos['json'])
    if (evento.get('event') != stream[8:] or type(evento.get('version')) is not int
            or evento['version'] != 1 or not isinstance(evento.get('data'), dict)
            or not isinstance(evento.get('occurred_at'), str)
            or not evento['data'].get('site_id')):
        raise ValueError('contrato incompatível')
    uuid.UUID(evento['event_id'])
    return evento


class API(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass  # URL, corpo e cabeçalhos podem conter dados privados.

    def responder(self, status):
        self.send_response(status)
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def encaminhar(self):
        host = self.headers.get('Host', '').split(':', 1)[0]
        if host not in PARES_FUNIL or not self.path.startswith('/') or self.path.startswith('//'):
            return self.responder(403)
        if self.headers.get('Transfer-Encoding'):
            return self.responder(400)
        try:
            tamanho = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.responder(400)
        if not 0 <= tamanho <= MAX_CORPO:
            return self.responder(413)
        corpo = self.rfile.read(tamanho)
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in {'connection', 'transfer-encoding',
                                        'proxy-authorization', 'proxy-connection'}}
        headers['Host'] = host + ':8000'
        headers['Connection'] = 'close'
        conexao = http.client.HTTPConnection(self.server.destino, 8000, timeout=10)
        try:
            conexao.request(self.command, self.path, body=corpo, headers=headers)
            resposta = conexao.getresponse()
            dados = resposta.read(8 * 1024 * 1024 + 1)
            if len(dados) > 8 * 1024 * 1024:
                return self.responder(502)
            self.send_response(resposta.status)
            for k, v in resposta.getheaders():
                if k.lower() not in {'connection', 'transfer-encoding', 'content-length'}:
                    self.send_header(k, v)
            self.send_header('Content-Length', str(len(dados)))
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(dados)
            self.close_connection = True
        except (OSError, http.client.HTTPException):
            self.responder(502)
        finally:
            conexao.close()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = encaminhar


class Servidor(HTTPServer):
    def __init__(self, destino, bind='0.0.0.0'):
        self.destino = destino
        self.executor = ThreadPoolExecutor(max_workers=12)
        self.vagas = BoundedSemaphore(24)
        super().__init__((bind, 8000), API)

    def process_request(self, request, address):
        if not self.vagas.acquire(blocking=False):
            request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            self.shutdown_request(request)
            return
        self.executor.submit(self.atender, request, address)

    def atender(self, request, address):
        request.settimeout(15)
        try:
            self.finish_request(request, address)
        except (OSError, ValueError):
            pass
        finally:
            self.shutdown_request(request)
            self.vagas.release()


# Escrita e avanço da posição na mesma transação Redis. Reentrega mantém o
# event_id original; duplicação do mesmo evento não vira outro fato no barramento.
PUBLICAR = '''
if redis.call('EXISTS',KEYS[2]) == 0 then
 redis.call('XADD',KEYS[1],'*','json',ARGV[1])
 redis.call('SET',KEYS[2],'1','EX',2592000)
end
redis.call('SET',KEYS[3],ARGV[2])
return 1
'''


def eventos(origem, destino):
    import redis
    local = redis.Redis.from_url(origem, decode_responses=True, socket_timeout=8)
    central = redis.Redis.from_url(destino, decode_responses=True, socket_timeout=8)
    streams = sorted('eventos.' + e for e in EVENTOS_FUNIL)
    while True:
        try:
            posicoes = {s: central.get('meshcraft:ponte:funil:' + s) or '0-0' for s in streams}
            for stream, mensagens in local.xread(posicoes, count=50, block=5000):
                for id_local, campos in mensagens:
                    try:
                        evento = conferir_evento(stream, campos)
                    except (ValueError, KeyError, TypeError):
                        # Só o contador e posição, sem copiar o conteúdo inválido.
                        central.incr('meshcraft:ponte:funil:recusados')
                        central.set('meshcraft:ponte:funil:' + stream, id_local)
                        continue
                    central.eval(PUBLICAR, 3, stream,
                        'meshcraft:ponte:funil:evento:' + evento['event_id'],
                        'meshcraft:ponte:funil:' + stream, campos['json'], id_local)
        except redis.RedisError:
            print('PONTE-INDISPONIVEL: nova tentativa em cinco segundos', flush=True)
            time.sleep(5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('modo', choices=('http', 'eventos'))
    parser.add_argument('--destino', required=True)
    parser.add_argument('--origem')
    args = parser.parse_args()
    if args.modo == 'http':
        Servidor(args.destino).serve_forever()
    else:
        eventos(args.origem, args.destino)
