import importlib.util
from pathlib import Path
import unittest
import threading
import http.client

spec = importlib.util.spec_from_file_location('gateway', Path(__file__).with_name('gateway.py'))
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class Contracts(unittest.TestCase):
    def test_http_rejects_without_upstream(self):
        server = gateway.HTTPServer(('127.0.0.1', 0), gateway.HTTPGateway)
        server.config = {'client_token': 'test-only', 'site_id': 'meshcraft'}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for method, path, headers, status in [
                ('GET', '/api/identidade/sessao/completa', {}, 401),
                ('GET', '/admin/', {'Authorization':'Bearer test-only'}, 403),
                ('POST', '/api/identidade/sessao/completa', {'Authorization':'Bearer test-only'}, 405),
                ('CONNECT', 'example.com:443', {'Authorization':'Bearer test-only'}, 405)]:
                c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
                c.request(method,path,headers=headers)
                response = c.getresponse()
                self.assertEqual(response.status,status)
                response.read()
                c.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_allowed(self):
        for path, pair in [('/api/identidade/sessao/completa', 'identidade'),
                           ('/api/alunos/alunos/prova%40example.invalid/matriculas', 'alunos'),
                           ('/api/cursos/cursos/primeiros-dolares/aulas?site_id=meshcraft', 'cursos'),
                           ('/api/cursos/cursos/primeiros-dolares/aulas/D02?site_id=meshcraft&parte=1', 'cursos')]:
            self.assertEqual(gateway.contract(path), pair)

    def test_attacks(self):
        for path in ['http://attacker/api/identidade/sessao/completa', '//attacker/api/identidade/sessao/completa',
                     '/api/identidade/sessao/completa?extra=1', '/api/identidade/../senhas',
                     '/api/alunos/alunos/a%2540x/matriculas', '/api/alunos/alunos/a%2Fb%40x/matriculas',
                     '/api/alunos/alunos/a@x/matriculas', '/api/cursos/cursos/a/aulas?site_id=other',
                     '/api/cursos/cursos/a/aulas?site_id=meshcraft&site_id=other',
                     '/api/cursos/cursos/a/aulas?site_id=meshcraft&url=http://attacker',
                     '/api/cursos/cursos/a/aulas', '/api/identidade/sessao/completa#x']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                gateway.contract(path)

    def test_private_lesson_content_removed(self):
        source = [{'estado': 'rascunho', 'titulo_exibido': 'private'},
                  {'estado': 'publicada', 'numero': 'D02', 'titulo_exibido': 'Normals', 'pecas': ['mentor-only'], 'quiz': ['answer'], 'cliente': 'private'}]
        self.assertEqual(gateway.lesson_metadata(source), [{'estado': 'publicada', 'numero': 'D02', 'titulo_exibido': 'Normals'}])


if __name__ == '__main__':
    unittest.main()
