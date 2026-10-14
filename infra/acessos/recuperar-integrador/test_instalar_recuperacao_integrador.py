from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from contextlib import ExitStack
import io

import instalar_recuperacao_integrador as installer
import recuperacao_integrador


class Tests(unittest.TestCase):
    def load_service(self):
        source = installer.service_source(Path(__file__).with_name('servicos_manutencao.py').read_text(encoding='utf-8'))
        module = types.ModuleType('candidate')
        exec(compile(source, 'candidate', 'exec'), module.__dict__)
        return module

    def test_catalogo_sem_ampliar_reinicio(self):
        module = self.load_service()
        catalog = module.dispatch(['listar'])
        self.assertEqual(catalog['reiniciaveis'], ['analisador', 'robo'])
        self.assertEqual(catalog['recuperaveis'], ['integrador'])
        self.assertTrue(module.valid(['recuperar', 'integrador']))
        self.assertFalse(module.valid(['reiniciar', 'integrador']))

    def test_extensao_integrada_nao_interrompe_ativo(self):
        module = self.load_service()
        module.health = Mock(return_value={'carregado': True, 'estado': 'active', 'executando': True})
        module.run = Mock()
        result = module.dispatch(['recuperar', 'integrador'])
        self.assertEqual(result['estado'], 'ja_ativo')
        module.run.assert_not_called()

    def test_codigo_divergente_nao_e_substituido(self):
        with self.assertRaisesRegex(RuntimeError, 'fonte_instalada_divergente'):
            installer.service_source('arquivo diverso')

    def test_patch_nao_e_reaplicado(self):
        original = Path(__file__).with_name('servicos_manutencao.py').read_text(encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'fonte_instalada_divergente'):
            installer.service_source(installer.service_source(original))

    def test_consulta_integrada_sem_repetir_inicio(self):
        module = self.load_service()
        with tempfile.TemporaryDirectory() as folder:
            module.STATE = Path(folder)
            id_ = 'c' * 32
            record = {'id': id_, 'acao': 'recuperar_integrador', 'estado': 'concluida'}
            recuperacao_integrador.save(folder, record)
            module.run = Mock()
            self.assertEqual(module.dispatch(['consultar', id_]), record)
            module.run.assert_not_called()

    def test_contexto_descreve_operacao(self):
        source = "def catalogo():\n    return {'comandos': {\n            'servicos reiniciar robo|analisador': 'Reinício existente, quando autorizado na tarefa.',\n    }}\n"
        candidate = types.ModuleType('context_candidate')
        exec(installer.context_source(source), candidate.__dict__)
        self.assertIn('servicos recuperar integrador', candidate.catalogo()['comandos'])
        self.assertIn('servicos consultar ID', candidate.catalogo()['comandos'])

    def installation(self, folder, requests):
        root = Path(folder)
        service = root / 'servicos_manutencao.py'
        context = root / 'operacao_contexto.py'
        original = Path(__file__).with_name('servicos_manutencao.py').read_bytes()
        service.write_bytes(original)
        original_context = "def catalogo():\n    return {'comandos': {\n            'servicos reiniciar robo|analisador': 'Reinício existente, quando autorizado na tarefa.',\n    }}\n"
        context.write_text(original_context, encoding='utf-8')
        backups = root / 'backups'
        backups.mkdir()
        stack = ExitStack()
        for name, value in [('SERVICE', service), ('CONTEXT', context),
                            ('MODULE', root / 'recuperacao_integrador.py'), ('BACKUPS', backups)]:
            stack.enter_context(patch.object(installer, name, value))
        stack.enter_context(patch.object(installer.os, 'geteuid', return_value=0, create=True))
        stack.enter_context(patch.object(installer.os, 'umask'))
        stack.enter_context(patch.object(installer.sys, 'argv', ['installer', '--instalar']))
        stack.enter_context(patch.object(installer.sys, 'stdout', io.StringIO()))
        runner = stack.enter_context(patch.object(installer, 'run', return_value=Mock()))
        stack.enter_context(patch.object(installer, 'request', side_effect=requests))
        return stack, service, context, original, original_context, runner

    def test_falha_restaura_codigo_anterior(self):
        with tempfile.TemporaryDirectory() as folder:
            stack, service, context, original, original_context, runner = self.installation(folder, [(1, {})])
            with stack:
                with self.assertRaisesRegex(RuntimeError, 'catalogo_nao_confirmado'):
                    installer.main()
                self.assertEqual(service.read_bytes(), original)
                self.assertEqual(context.read_text(encoding='utf-8'), original_context)
                self.assertNotIn('import recuperacao_integrador', service.read_text(encoding='utf-8'))
                self.assertEqual(sum(c.args[0] == ['/usr/bin/systemctl', 'restart', installer.UNIT]
                                     for c in runner.call_args_list), 2)

    def test_instalacao_nao_inicia_integrador_ou_modifica_unidades(self):
        responses = [(0, {'recuperaveis': ['integrador']}),
                     (0, {'acesso': {'comandos': {'servicos recuperar integrador': 'ok'}}}),
                     (2, {'recusado': True}), (2, {'recusado': True}), (2, {'recusado': True})]
        with tempfile.TemporaryDirectory() as folder:
            stack, service, context, original, original_context, runner = self.installation(folder, responses)
            with stack:
                installer.main()
                self.assertIn('import recuperacao_integrador', service.read_text(encoding='utf-8'))
                commands = [c.args[0] for c in runner.call_args_list]
                self.assertFalse(any('meshcraft-integrador.service' in c for c in commands))
                self.assertFalse(any('daemon-reload' in c for c in commands))
                self.assertEqual(len(list(Path(folder, 'backups').glob('*/resultado.json'))), 1)


if __name__ == '__main__':
    unittest.main()
