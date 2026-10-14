import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import recuperacao_integrador as m


class Refused(ValueError):
    pass


class Tests(unittest.TestCase):
    def before(self, state='inactive'):
        return {'servico': 'integrador', 'estado': state, 'carregado': True,
                'executando': state == 'active'}

    def test_operacoes_fechadas(self):
        self.assertTrue(m.valid(['recuperar', 'integrador']))
        self.assertTrue(m.valid(['consultar', 'a' * 32]))
        for args in ([], None, ['recuperar', 'publicador'], ['reiniciar', 'integrador'],
                     ['recuperar', 'integrador;id'], ['consultar', '../etc/shadow'],
                     ['consultar', 'A' * 32], ['recuperar', 'integrador', 'extra']):
            self.assertFalse(m.valid(args), args)

    def test_recusa_nao_executa(self):
        run = Mock()
        with self.assertRaises(Refused):
            m.dispatch(['recuperar', 'postgres'], Mock(), run, Refused, Path('.'))
        run.assert_not_called()

    def test_ativo_nao_interrompe(self):
        run = Mock()
        result = m.dispatch(['recuperar', 'integrador'], Mock(return_value=self.before('active')),
                            run, Refused, Path('.'))
        self.assertEqual(result['estado'], 'ja_ativo')
        run.assert_not_called()

    def test_transicao_nao_interrompe(self):
        for state in ('activating', 'deactivating', 'reloading', 'indisponivel'):
            run = Mock()
            with self.assertRaisesRegex(Refused, 'servico_em_transicao'):
                m.dispatch(['recuperar', 'integrador'], Mock(return_value=self.before(state)),
                           run, Refused, Path('.'))
            run.assert_not_called()

    def test_ausente_nao_inicia(self):
        run = Mock()
        with self.assertRaisesRegex(Refused, 'servico_ausente'):
            m.dispatch(['recuperar', 'integrador'], Mock(return_value={'carregado': False}),
                       run, Refused, Path('.'))
        run.assert_not_called()

    def test_liga_parado_com_intencao_anterior(self):
        with tempfile.TemporaryDirectory() as folder:
            def start(args, timeout):
                saved = list(Path(folder).glob('*.json'))
                self.assertEqual(len(saved), 1)
                self.assertEqual(json.loads(saved[0].read_text())['estado'], 'iniciando')
                return SimpleNamespace(returncode=0, stdout='PRIVADO', stderr='PRIVADO')
            run = Mock(side_effect=start)
            result = m.dispatch(['recuperar', 'integrador'],
                                Mock(side_effect=[self.before(), self.before('active')]),
                                run, Refused, folder)
            run.assert_called_once_with(['/usr/bin/systemctl', 'start', '--no-block', m.UNIT], timeout=10)
            self.assertEqual(result['estado'], 'concluida')
            self.assertNotIn('PRIVADO', json.dumps(result))
            self.assertEqual(m.dispatch(['consultar', result['id']], Mock(), Mock(), Refused, folder), result)

    def test_comando_falhou_sem_texto_privado(self):
        with tempfile.TemporaryDirectory() as folder:
            result = m.dispatch(['recuperar', 'integrador'], Mock(return_value=self.before('failed')),
                                Mock(return_value=SimpleNamespace(returncode=1, stderr='PRIVADO')),
                                Refused, folder)
            self.assertEqual(result['estado'], 'falha')
            self.assertEqual(result['codigo'], 'inicio_recusado')
            self.assertNotIn('PRIVADO', json.dumps(result))

    def test_resposta_perdida_consulta_nao_repete_inicio(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Mock(side_effect=subprocess.TimeoutExpired('systemctl', 10, output='PRIVADO'))
            result = m.dispatch(['recuperar', 'integrador'], Mock(return_value=self.before()),
                                run, Refused, folder)
            self.assertEqual(result['estado'], 'iniciando')
            query_run = Mock()
            resumed = m.dispatch(['consultar', result['id']], Mock(return_value=self.before('active')),
                                 query_run, Refused, folder)
            self.assertEqual(resumed['estado'], 'concluida')
            query_run.assert_not_called()
            self.assertNotIn('PRIVADO', json.dumps(resumed))

    def test_falha_do_servico_nao_afirma_recuperacao(self):
        with tempfile.TemporaryDirectory() as folder:
            result = m.dispatch(['recuperar', 'integrador'],
                                Mock(side_effect=[self.before(), self.before('failed')]),
                                Mock(return_value=SimpleNamespace(returncode=0)), Refused, folder)
            self.assertEqual(result['estado'], 'falha')

    def test_inicio_nao_confirmado_e_consultavel(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(m.time, 'monotonic', side_effect=[0, 9]):
            result = m.dispatch(['recuperar', 'integrador'], Mock(return_value=self.before()),
                                Mock(return_value=SimpleNamespace(returncode=0)), Refused, folder)
            self.assertEqual(result['estado'], 'iniciando')
            self.assertEqual(result['codigo'], 'inicio_ainda_nao_confirmado')

    def test_consulta_nao_le_outros_registros(self):
        with tempfile.TemporaryDirectory() as folder:
            id_ = 'b' * 32
            Path(folder, id_ + '.json').write_text(json.dumps({'id': id_, 'acao': 'outra'}))
            with self.assertRaisesRegex(Refused, 'operacao_incompativel'):
                m.dispatch(['consultar', id_], Mock(), Mock(), Refused, folder)


if __name__ == '__main__':
    unittest.main()
