"""Bounded fixed-destination HTTP gateway / PostgreSQL byte relay. No access logs."""
import hmac
import http.client
import http.cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import selectors
import socket
import socketserver
import sys
import time
from urllib.parse import urlsplit, parse_qsl, unquote, quote


def contract(path, site_id='meshcraft'):
    if len(path) > 2048 or any(ord(c) < 33 for c in path):
        raise ValueError('path')
    u = urlsplit(path)
    if u.scheme or u.netloc or u.fragment or not path.startswith('/') or path.startswith('//'):
        raise ValueError('origin')
    if u.path == '/api/identidade/sessao/completa' and not u.query:
        return 'identidade'
    m = re.fullmatch(r'/api/alunos/alunos/([^/]+)/matriculas', u.path)
    if m and not u.query:
        email = unquote(m[1], errors='strict')
        if re.fullmatch(r'[A-Za-z0-9.!#$&\x27*+=?^_`{|}~-]+@[A-Za-z0-9.-]+', email) and quote(email, safe='') == m[1]:
            return 'alunos'
    if re.fullmatch(r'/api/cursos/cursos/[a-z0-9][a-z0-9-]{0,100}/aulas(?:/[A-Za-z0-9_-]{1,40})?', u.path):
        q = parse_qsl(u.query, strict_parsing=True)
        if len(q) != len(dict(q)) or set(dict(q)) - {'site_id', 'parte'}:
            raise ValueError('query')
        if dict(q).get('site_id') == site_id and all(re.fullmatch('[A-Za-z0-9_-]{1,80}', v) for k,v in q):
            return 'cursos'
    raise ValueError('contract')


def lesson_metadata(data):
    def one(x):
        if not isinstance(x, dict) or x.get('estado') != 'publicada':
            return None
        return {k: x[k] for k in ('numero', 'titulo_exibido', 'estado', 'versao') if k in x}
    if isinstance(data, list):
        return [v for x in data if (v := one(x)) is not None]
    return one(data)


def upstream_path(path, service):
    if service == 'identidade':
        return '/entrar/revisor/sessao/completa'
    return '/' + service + path


class HTTPGateway(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self, *args):
        pass
    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        c = self.server.config
        supplied = self.headers.get_all('Authorization', [])
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0], 'Bearer ' + c['client_token']):
            return self.send_json(401, {'error': 'unauthorized'})
        try:
            service = contract(self.path, c['site_id'])
        except (ValueError, UnicodeError):
            return self.send_json(403, {'error': 'contract_denied'})
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
            return self.send_json(400, {'error': 'body_denied'})
        headers = {'Host': 'meshcraft.top', 'Authorization': 'Bearer ' + c['tokens'][service], 'Accept': 'application/json'}
        if service == 'identidade':
            cookie = http.cookies.SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                if 'meshcraft_sessao' in cookie:
                    headers['Cookie'] = cookie['meshcraft_sessao'].OutputString()
            except http.cookies.CookieError:
                return self.send_json(400, {'error': 'cookie_invalid'})
        connection = None
        try:
            # DNS must still identify the address approved by the firewall.
            if socket.gethostbyname('aplicacao') != c['upstream_ip']:
                raise OSError('upstream changed')
            deadline = time.monotonic() + 5
            connection = http.client.HTTPConnection(c['upstream_ip'], 8000, timeout=2)
            connection.connect()
            connection.sock.settimeout(max(.01, deadline-time.monotonic()))
            connection.request('GET', upstream_path(self.path, service), headers=headers)
            response = connection.getresponse()
            # A redirect is never followed and never handed to the caller.
            if response.status not in (200, 401, 403, 404):
                raise OSError('upstream status')
            if 'application/json' not in response.getheader('Content-Type', ''):
                raise ValueError('not a contracted JSON response')
            raw = bytearray()
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if connection.sock:
                    connection.sock.settimeout(remaining)
                part = response.read1(min(65536, 1048577-len(raw)))
                if not part:
                    break
                raw.extend(part)
                if len(raw) > 1048576:
                    raise ValueError('too large')
            data = json.loads(raw)
            if service == 'cursos' and response.status == 200:
                data = lesson_metadata(data)
            self.send_json(response.status, data if response.status == 200 else {'error': 'upstream_denied'})
        except (OSError, ValueError, http.client.HTTPException):
            self.send_json(503, {'error': 'upstream_unavailable'})
        finally:
            if connection:
                connection.close()
    def do_POST(self):
        self.send_json(405, {'error': 'method_denied'})
    do_PUT = do_PATCH = do_DELETE = do_CONNECT = do_TRACE = do_OPTIONS = do_HEAD = do_POST


class DBRelay(socketserver.BaseRequestHandler):
    def handle(self):
        cfg = self.server.config
        try:
            if socket.gethostbyname('postgres') != cfg['upstream_ip']:
                return
            with socket.create_connection((cfg['upstream_ip'], 5432), 2) as upstream, selectors.DefaultSelector() as sel:
                self.request.settimeout(5)
                upstream.settimeout(5)
                sel.register(self.request, selectors.EVENT_READ, upstream)
                sel.register(upstream, selectors.EVENT_READ, self.request)
                while True:
                    ready = sel.select(60)
                    if not ready:
                        return
                    for key, _ in ready:
                        data = key.fileobj.recv(65536)
                        if not data:
                            return
                        key.data.sendall(data)
        except OSError:
            pass


if __name__ == '__main__':
    cfg = json.loads(Path('/run/revisor/config.json').read_text())
    if sys.argv[1] == 'http':
        server = HTTPServer((cfg['listen_ip'], 8080), HTTPGateway)
    else:
        server = socketserver.TCPServer((cfg['listen_ip'], 5432), DBRelay)
    server.config = cfg
    server.serve_forever()
