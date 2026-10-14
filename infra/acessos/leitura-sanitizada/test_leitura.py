import contextlib
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import leitura
import instalar

COMMAND = '''import json
import os
import shlex
import sys
from operacao_contexto import atender
def principal():
    args = shlex.split(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    consulta = atender(args, __file__)
    if consulta is not None:
        return consulta
    print('{"recusado":true}')
    return 2
if __name__ == '__main__':
    sys.exit(principal())
'''
CONTEXT = '''import json
def catalogo():
    return {
        'comandos': {
            'consultar ID': 'Registro completo da entrega e evidências disponíveis.',
            'servicos recuperar integrador': 'Preservado',
        },
        'referencias': {
            'console': 'https://hpanel.hostinger.com/vps/1893584/overview',
            'site': 'https://meshcraft.top/',
        },
    }
def atender(args, command):
    if args == ['ajuda']:
        print(json.dumps(catalogo()))
        return 0
    return None
'''


class ReaderTest(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get('MESHCRAFT_TEST_TMP', str(Path(__file__).resolve().parent / '.test-tmp')))
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        def cleanup():
            target = Path(self.temp.name).resolve()
            if target.parent != base.resolve() or not target.name.startswith('tmp'):
                raise RuntimeError('pasta_temporaria_fora_do_destino_de_testes')
            self.temp.cleanup()
        self.addCleanup(cleanup)
        self.root = Path(self.temp.name)

    def file(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        path.chmod(0o644)
        return path

    def test_xml_does_not_disclose_messages_parameters_or_properties(self):
        xml = b'''<testsuites><testsuite><properties><property name="token" value="segredo"/></properties>
        <testcase classname="tests.test_login" name="test_login[email@privado.com]">
          <failure type="AssertionError" message="CPF 11122233344 token=segredo">senha=privada</failure>
          <system-out>Authorization: Bearer privado</system-out>
        </testcase></testsuite></testsuites>'''
        result = leitura.summarize_xml(xml, {('tests.test_login', 'test_login')})
        self.assertEqual(result['falhas'], 1)
        self.assertEqual(result['problemas'][0]['teste'], 'test_login')
        output = json.dumps(result)
        for private in ('privado', 'segredo', '11122233344', 'senha', 'email@'):
            self.assertNotIn(private, output)

    def test_unknown_case_name_and_exception_are_omitted(self):
        result = leitura.summarize_xml(b'<testsuite><testcase name="segredo" classname="privado"><error type="token_privado"/></testcase></testsuite>', set())
        self.assertEqual(result['erros'], 1)
        self.assertNotIn('privado', json.dumps(result))
        self.assertNotIn('segredo', json.dumps(result))

    def test_xml_counts_all_outcomes_without_claiming_ignored_passed(self):
        result = leitura.summarize_xml(b'<testsuite><testcase/><testcase><failure/></testcase><testcase><error/></testcase><testcase><skipped/></testcase></testsuite>', set())
        self.assertEqual([result[k] for k in ('casos', 'aprovados', 'falhas', 'erros', 'ignorados')], [4, 1, 1, 1, 1])

    def test_entities_are_refused(self):
        with self.assertRaises(ValueError):
            leitura.summarize_xml(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/shadow">]><x/>', set())

    def test_logs_output_only_known_codes(self):
        raw = b'Authorization: Bearer segredo\nValueError: cpf=11122233344 email=privado@example.com\nPermission denied\n'
        result = leitura.summarize_log(raw)
        self.assertEqual(result['tipos'], ['ValueError'])
        self.assertEqual(result['causas_reconhecidas'], ['permissao_recusada'])
        self.assertNotIn('segredo', json.dumps(result))
        self.assertNotIn('11122233344', json.dumps(result))

    def test_oversized_file_refused(self):
        source = self.file('input', b'x' * 100)
        with self.assertRaises(ValueError):
            leitura.read_regular(source, self.root, 99)

    def test_traversal_refused(self):
        with self.assertRaises(ValueError):
            leitura.read_regular(self.root / '..' / 'private', self.root, 100)

    def test_symlink_refused(self):
        source = self.file('source', b'private')
        link = self.root / 'link'
        try:
            link.symlink_to(source)
        except OSError:
            self.skipTest('Ambiente não permite criar link simbólico')
        with self.assertRaises(ValueError):
            leitura.read_regular(link, self.root, 100)

    def test_catalog_contains_only_declared_tests(self):
        self.file('tests/test_login.py', 'def test_login():\n    pass\n')
        self.assertEqual(leitura.catalog(self.root / 'tests'), {('tests.test_login', 'test_login')})

    def fixture(self):
        sha, attempt = 'a' * 40, 'b' * 32
        phase = self.file('phases/fase.json', json.dumps({'id': leitura.ENTREGA, 'candidata': sha, 'privado': 'segredo'}))
        self.file('selectors/' + sha + '-funil.json', json.dumps({'tentativa': attempt}))
        self.file('runs/' + sha + '-funil/' + attempt + '/evidencias/funil.xml', '<testsuite><testcase classname="tests.test_login" name="test_login"><failure type="AssertionError"/></testcase></testsuite>')
        self.file('tests/test_login.py', 'def test_login():\n    pass\n')
        return phase

    def collect(self, phase):
        return leitura.collect(phase, self.root / 'selectors', self.root / 'runs', self.root / 'legacy', self.root / 'tests')

    def test_collect_selects_current_candidate_and_attempt(self):
        result = self.collect(self.fixture())
        self.assertEqual(result['candidata'], 'a' * 40)
        self.assertEqual(result['tentativa'], 'b' * 32)
        self.assertEqual(result['testes']['falhas'], 1)
        self.assertEqual(result['execucao']['estado'], 'arquivo_ausente')
        self.assertNotIn('segredo', json.dumps(result))

    def test_invalid_selector_cannot_read_arbitrary_path(self):
        phase = self.fixture()
        self.file('selectors/' + 'a' * 40 + '-funil.json', '{"tentativa":"../../env"}')
        with self.assertRaises(ValueError):
            self.collect(phase)

    def test_wrong_delivery_refused(self):
        phase = self.fixture()
        phase.write_text(json.dumps({'id': '000000000000', 'candidata': 'a' * 40}))
        with self.assertRaises(ValueError):
            self.collect(phase)

    def test_ssh_does_not_accept_paths_other_ids_or_actions(self):
        for args in (['diagnostico', '../etc/shadow'], ['diagnostico', '000000000000'], ['diagnostico', leitura.ENTREGA, 'exec']):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(leitura.atender_leitura(args, self.root), 2)
        self.assertIsNone(leitura.atender_leitura(['contexto'], self.root))

    def test_stale_snapshot_is_explicitly_unavailable(self):
        self.file(leitura.ENTREGA + '.json', json.dumps({'id': leitura.ENTREGA, 'observado_em': (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = leitura.atender_leitura(['diagnostico', leitura.ENTREGA], self.root)
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(output.getvalue())['leitura_atual'])

    def setup_installer(self):
        self.file('robo_comando.py', COMMAND)
        self.file('operacao_contexto.py', CONTEXT)

    def test_install_preserves_backup_and_existing_operation(self):
        self.setup_installer()
        result = instalar.install(self.root, module=b'# modulo de teste\n', prove=False)
        backup = self.root / result['backup']
        self.assertEqual((backup / 'robo_comando.py').read_text(encoding='utf-8'), COMMAND)
        self.assertEqual((backup / 'operacao_contexto.py').read_text(encoding='utf-8'), CONTEXT)
        new = (self.root / 'operacao_contexto.py').read_text(encoding='utf-8')
        self.assertNotIn("'console'", new)
        self.assertIn('servicos recuperar integrador', new)
        self.assertIn('diagnostico ed31b0c03f97', new)

    def test_failed_proof_restores_original_code(self):
        self.setup_installer()
        with patch.object(instalar.subprocess, 'run', side_effect=RuntimeError('falha de prova')):
            with self.assertRaises(RuntimeError):
                instalar.install(self.root, module=b'# modulo de teste\n')
        self.assertEqual((self.root / 'robo_comando.py').read_text(encoding='utf-8'), COMMAND)
        self.assertEqual((self.root / 'operacao_contexto.py').read_text(encoding='utf-8'), CONTEXT)
        self.assertFalse((self.root / 'leitura_sanitizada.py').exists())

    def test_installed_command_serves_help_and_refuses_other_delivery(self):
        self.setup_installer()
        module = Path(leitura.__file__).read_bytes()
        result = instalar.install(self.root, module=module, prove=True)
        self.assertEqual(result['estado'], 'instalado')
        for command in ('diagnostico 000000000000', 'shell'):
            process = instalar.subprocess.run([instalar.sys.executable, str(self.root / 'robo_comando.py')],
                        capture_output=True, env=dict(os.environ, SSH_ORIGINAL_COMMAND=command), timeout=10)
            self.assertEqual(process.returncode, 2)
            self.assertTrue(json.loads(process.stdout)['recusado'])

    def test_repeated_install_cannot_overwrite_existing_extension(self):
        self.setup_installer()
        self.file('leitura_sanitizada.py', '# existente')
        with self.assertRaises(ValueError):
            instalar.install(self.root, module=b'# modulo\n', prove=False)
        self.assertEqual((self.root / 'leitura_sanitizada.py').read_text(encoding='utf-8'), '# existente')

    def test_unrecognized_installed_source_is_not_changed(self):
        self.setup_installer()
        before = '# fonte de outro trabalho\n'
        self.file('robo_comando.py', before)
        with self.assertRaises(ValueError):
            instalar.install(self.root, module=b'# modulo\n', prove=False)
        self.assertEqual((self.root / 'robo_comando.py').read_text(encoding='utf-8'), before)


if __name__ == '__main__':
    unittest.main()
