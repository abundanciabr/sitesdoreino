import io
import json
import unittest
from estado_transporte import enviar, receber, MAX_LINE


class Connection:
    def __init__(self, raw=b''):
        self.raw = raw
    def sendall(self, value):
        self.raw += value
    def makefile(self, mode):
        return io.BytesIO(self.raw)


class Tests(unittest.TestCase):
    def test_historico_grande_integro(self):
        records = [{'id': '%012x' % i, 'estado': 'integração concluída 😀', 'operacao': {'provas': ['ação'] * 30}} for i in range(12000)]
        text = json.dumps(records, ensure_ascii=False) + '\n'
        conn = Connection()
        enviar(conn, {'codigo': 0, 'saida': text, '_blocos': True})
        self.assertGreater(len(conn.raw), 262144)
        self.assertTrue(all(len(line) < MAX_LINE for line in conn.raw.splitlines()))
        out = io.StringIO()
        self.assertEqual(receber(conn, out), 0)
        self.assertEqual(out.getvalue(), text)
        self.assertEqual(len(json.loads(out.getvalue())), 12000)

    def test_legado_preservado(self):
        for code in (0, 2, 3):
            conn = Connection()
            enviar(conn, {'codigo': code, 'saida': 'resposta antiga\n'})
            out = io.StringIO()
            self.assertEqual(receber(conn, out), code)
            self.assertEqual(out.getvalue(), 'resposta antiga\n')

    def test_vazio(self):
        conn = Connection()
        enviar(conn, {'codigo': 0, 'saida': '[]\n', '_blocos': True})
        out = io.StringIO()
        self.assertEqual(receber(conn, out), 0)
        self.assertEqual(out.getvalue(), '[]\n')

    def test_truncamento_sem_saida_parcial(self):
        conn = Connection()
        enviar(conn, {'codigo': 0, 'saida': 'x' * 300000, '_blocos': True})
        conn.raw = conn.raw[:-30]
        out = io.StringIO()
        with self.assertRaises(ValueError):
            receber(conn, out)
        self.assertEqual(out.getvalue(), '')

    def test_adulteracao_sem_saida(self):
        conn = Connection()
        enviar(conn, {'codigo': 0, 'saida': 'abc', '_blocos': True})
        conn.raw = conn.raw.replace(b'abc', b'abd')
        out = io.StringIO()
        with self.assertRaises(ValueError):
            receber(conn, out)
        self.assertEqual(out.getvalue(), '')

    def test_excesso_no_bloco(self):
        conn = Connection(b'{"formato":"blocos-v1","codigo":0}\n' + b'x' * (MAX_LINE + 1))
        with self.assertRaises(ValueError):
            receber(conn, io.StringIO())

    def test_nao_acrescenta_dados_ao_json_publico(self):
        text = '[{"id":"123456789abc","estado":"pronta"}]'
        conn = Connection()
        enviar(conn, {'codigo': 0, 'saida': text, '_blocos': True})
        out = io.StringIO()
        receber(conn, out)
        self.assertEqual(out.getvalue(), text)


if __name__ == '__main__':
    unittest.main()
