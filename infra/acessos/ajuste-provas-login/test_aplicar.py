import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import aplicar

HERE = Path(__file__).resolve().parent
PAYLOAD = json.loads((HERE / 'mudancas.json').read_text(encoding='utf-8'))


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tests = self.root / 'tests'
        self.tests.mkdir()
        for name in aplicar.NAMES:
            (self.tests / name).write_bytes((HERE / 'originais' / name).read_bytes())
        self.sentinel = self.tests / 'test_preservado.py'
        self.sentinel.write_bytes(b'def test_preservado(): assert True\n')

    def test_aplica_exatamente_os_hashes_e_preserva_outros_arquivos(self):
        result = aplicar.apply(self.root, PAYLOAD)
        self.assertEqual(result['estado'], 'aplicado')
        for name, sha in PAYLOAD['novos'].items():
            self.assertEqual(aplicar.digest((self.tests / name).read_bytes()), sha)
        self.assertEqual(self.sentinel.read_bytes(), b'def test_preservado(): assert True\n')

    def test_backup_confere_com_cada_original(self):
        result = aplicar.apply(self.root, PAYLOAD)
        for name, sha in PAYLOAD['originais'].items():
            self.assertEqual(aplicar.digest((self.root / result['backup'] / name).read_bytes()), sha)

    def test_repetir_nao_reaplica_efeitos(self):
        aplicar.apply(self.root, PAYLOAD)
        self.assertEqual(aplicar.apply(self.root, PAYLOAD)['estado'], 'ja_aplicado')

    def test_fonte_divergente_recusa_sem_modificar(self):
        path = self.tests / aplicar.NAMES[1]
        path.write_bytes(path.read_bytes() + b'\n# outra tarefa\n')
        before = {p.name:p.read_bytes() for p in self.tests.iterdir()}
        with self.assertRaisesRegex(ValueError, 'referencia_mudou'):
            aplicar.apply(self.root, PAYLOAD)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.tests.iterdir()})

    def test_falha_em_cada_gravacao_recupera_somente_o_proprio_ajuste(self):
        for fail_at in range(1,5):
            calls = []
            def fail():
                calls.append(1)
                if len(calls) == fail_at:
                    raise RuntimeError('falha_simulada')
            with self.assertRaisesRegex(RuntimeError, 'falha_simulada'):
                aplicar.apply(self.root, PAYLOAD, hook=fail)
            for name, sha in PAYLOAD['originais'].items():
                self.assertEqual(aplicar.digest((self.tests / name).read_bytes()), sha)
            self.assertFalse((self.tests / aplicar.NEW).exists())

    def test_arquivo_novo_de_outra_tarefa_nao_e_sobrescrito(self):
        (self.tests / aplicar.NEW).write_bytes(b'# trabalho existente\n')
        with self.assertRaisesRegex(ValueError, 'arquivo_novo_ja_existe'):
            aplicar.apply(self.root, PAYLOAD)

    def test_link_simbolico_e_recusado(self):
        path = self.tests / aplicar.NAMES[0]
        private = self.root / 'private'
        private.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(private)
        with self.assertRaisesRegex(ValueError, 'link_recusado'):
            aplicar.apply(self.root, PAYLOAD)

    def test_permissoes_e_funcoes_de_teste_sao_preservadas(self):
        path = self.tests / aplicar.NAMES[0]
        path.chmod(0o444)
        def names(source):
            return {n.name for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
        before = {n:names((self.tests/n).read_bytes()) for n in aplicar.NAMES}
        aplicar.apply(self.root, PAYLOAD)
        for name in aplicar.NAMES:
            self.assertEqual(before[name], names((self.tests/name).read_bytes()))
        self.assertEqual(path.stat().st_mode & 0o777,0o444)
        self.assertTrue(names((self.tests/aplicar.NEW).read_bytes()))

    def test_hash_do_destino_impede_pacote_divergente(self):
        payload = copy.deepcopy(PAYLOAD)
        payload['arquivo_novo'] += '\n# mudança não aprovada\n'
        with self.assertRaisesRegex(ValueError, 'destino_divergente'):
            aplicar.apply(self.root, payload)


if __name__ == '__main__':
    unittest.main()
