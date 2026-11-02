from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
from runtime import application


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


if __name__ == '__main__':
    with make_server('0.0.0.0', 8000, application, server_class=Server, handler_class=Quiet) as server:
        server.serve_forever()
