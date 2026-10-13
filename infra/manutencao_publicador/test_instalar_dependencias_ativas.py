import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('instalar', Path(__file__).with_name('instalar_dependencias_ativas.py'))
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name)

    def fetch(self, path):
        # As constantes do instalador conferem estes bytes contra a revisão fixada.
        return (Path(__file__).resolve().parents[2] / path).read_bytes().replace(b'\r\n', b'\n')

    def test_manifest_uses_exact_reviewed_code_and_only_three_targets(self):
        install.prepare(self.package, self.fetch)
        data = json.loads((self.package / 'manifest.json').read_text())
        self.assertEqual({item['alvo'] for item in data['arquivos']}, {
            'integrador/integrador_servico.py', 'integrador/ponte_entregas.py',
            'publicador/infra/ponte_entregas.py'})
        for item in data['arquivos']:
            path = 'infra/' + item['alvo'].split('/')[-1]
            self.assertEqual((self.package / item['origem']).read_bytes(), self.fetch(path))
        self.assertEqual((self.package / 'aplicar_canal.py').read_bytes(), self.fetch(install.INSTALLER))

    def test_altered_download_is_refused_before_any_package_is_written(self):
        with self.assertRaisesRegex(RuntimeError, 'Fonte diferente'):
            install.prepare(self.package, lambda path: self.fetch(path) + b'\n# unexpected\n')
        self.assertEqual(list(self.package.iterdir()), [])

    def fake_installer(self):
        (self.package / 'manifest.json').write_text(json.dumps({'arquivos': [
            {'alvo': 'integrador/integrador_servico.py', 'depois': 'new'}]}))
        fake = types.SimpleNamespace(
            release_atual=lambda: Path('/release'),
            alvo_path=lambda key, release: release / key,
            required_hash=lambda path: 'old', manifest=Mock(), resume_units=Mock(),
            run=Mock(return_value=types.SimpleNamespace(stdout='active\n')))
        self.events = []

        def apply(package):
            self.events.append('backup and apply')
            try:
                fake.resume_units({'meshcraft-integrador.service'})
            except Exception:
                self.events.append('recover')
                fake.resume_units({'meshcraft-integrador.service'}, restart=True)
                raise
        fake.apply = Mock(side_effect=apply)
        return fake

    def test_failed_baseline_never_invokes_installer(self):
        fake = self.fake_installer()
        with self.assertRaisesRegex(RuntimeError, 'offline'):
            install.install(self.package, fake, Mock(side_effect=RuntimeError('offline')))
        fake.apply.assert_not_called()

    def test_unexpected_base_never_invokes_installer(self):
        fake = self.fake_installer()
        fake.manifest.side_effect = RuntimeError('base divergente')
        with self.assertRaisesRegex(RuntimeError, 'base divergente'):
            install.install(self.package, fake, Mock())
        fake.apply.assert_not_called()

    def test_http_failure_occurs_inside_transaction_and_calls_recovery(self):
        fake = self.fake_installer()
        resume = fake.resume_units
        with self.assertRaisesRegex(RuntimeError, 'offline'):
            install.install(self.package, fake, Mock(side_effect=[None, RuntimeError('offline')]))
        self.assertEqual(self.events, ['backup and apply', 'recover'])
        self.assertIs(fake.resume_units, resume)
        self.assertTrue(resume.call_args.kwargs['restart'])

    def test_service_failure_also_calls_recovery(self):
        fake = self.fake_installer()
        fake.run.return_value.stdout = 'failed\n'
        with self.assertRaisesRegex(RuntimeError, 'Serviço não retomou'):
            install.install(self.package, fake, Mock())
        self.assertEqual(self.events, ['backup and apply', 'recover'])

    def test_success_does_not_claim_delivery_timing(self):
        fake = self.fake_installer()
        result = install.install(self.package, fake, Mock())
        self.assertTrue(result['alterado'])
        self.assertEqual(result['medicao_de_entrega_posterior'], 'ainda não realizada')

    def test_matching_disk_does_not_claim_running_version(self):
        fake = self.fake_installer()
        fake.required_hash = lambda path: 'new'
        result = install.install(self.package, fake, Mock())
        self.assertFalse(result['alterado'])
        self.assertEqual(result['execucao_da_correcao'], 'não comprovada nesta consulta')
        fake.apply.assert_not_called()


if __name__ == '__main__':
    unittest.main()
