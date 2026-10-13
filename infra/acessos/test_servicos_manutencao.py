import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import servicos_manutencao as m


class Tests(unittest.TestCase):
    def test_comandos_fechados(self):
        for args in (['listar'], ['saude'], ['saude', 'aplicacao'], ['logs', 'robo', '60', '100'], ['reiniciar', 'analisador']):
            self.assertTrue(m.valid(args), args)
        for args in ([], ['reiniciar', 'aplicacao'], ['reiniciar', 'postgres'],
                     ['saude', '../../etc/passwd'], ['logs', 'robo', '0', '1'],
                     ['logs', 'robo', '1441', '1'], ['logs', 'robo', '1', '201'],
                     ['logs', 'robo', '1;id', '1'], ['saude', 'robo', 'extra'],
                     ['reiniciar', 'robo;id'], ['logs', 'pagamentos', '1', '1'], [None]):
            self.assertFalse(m.valid(args), args)

    def test_privacidade_journal(self):
        private = 'Nome Inventado cpf=000.000.000-00 email=teste@example.invalid password=nao_real TOKEN-TESTE'
        line = json.dumps({'MESSAGE': 'OperationalError ' + private, 'PRIORITY': '3',
                           '__REALTIME_TIMESTAMP': '1791892800000000', 'EXTRA': private})
        with patch.object(m, 'run', return_value=SimpleNamespace(returncode=0, stdout=line, stderr='')):
            result = m.logs('robo', 60, 100)
        text = json.dumps(result)
        for value in ('Nome', '000.000', 'example.invalid', 'nao_real', 'TOKEN-TESTE', 'EXTRA'):
            self.assertNotIn(value, text)
        self.assertEqual(result['eventos'][0]['classes'], ['OperationalError'])

    def test_docker_stderr_nao_vaza(self):
        with patch.object(m, 'run', return_value=SimpleNamespace(returncode=0,
                stdout='2026-10-13T13:00:00.123Z ValueError nome=Teste Inventado',
                stderr='2026-10-13T13:01:00.123Z password=TESTE_TOKEN')):
            data = m.logs('aplicacao', 60, 100)
        text = json.dumps(data)
        self.assertNotIn('Inventado', text)
        self.assertNotIn('TESTE_TOKEN', text)
        self.assertEqual(data['eventos'][0]['classes'], ['ValueError'])

    def test_falha_fonte_nao_vaza(self):
        with patch.object(m, 'run', return_value=SimpleNamespace(returncode=1, stdout='TOKEN_TESTE', stderr='SEGREDO_TESTE')):
            with self.assertRaisesRegex(RuntimeError, '^fonte_indisponivel$'):
                m.logs('aplicacao', 60, 100)

    def test_fonte_journal_malformada(self):
        raw = '\n'.join(('nao-json SEGREDO', 'null', '[]', json.dumps({'MESSAGE': ['SEGREDO'], 'PRIORITY': 'segredo'})))
        with patch.object(m, 'run', return_value=SimpleNamespace(returncode=0, stdout=raw, stderr='')):
            self.assertNotIn('SEGREDO', json.dumps(m.logs('robo', 1, 10)))

    def test_reinicio_recusa_analisador_ocupado(self):
        with patch.object(m, 'health', return_value={'carregado': True}), patch.object(m, 'run', return_value=SimpleNamespace(stdout='active')) as run:
            with self.assertRaisesRegex(m.Refused, 'operacao_em_andamento'):
                m.restart('analisador')
        self.assertEqual(run.call_count, 1)

    def test_saude_descarta_campos_livres(self):
        raw = 'ActiveState=SECRET\nLoadState=loaded\nSubState=SECRET\nNRestarts=SECRET'
        with patch.object(m, 'run', return_value=SimpleNamespace(returncode=0, stdout=raw)):
            self.assertNotIn('SECRET', json.dumps(m.health('robo')))

    def test_recusa_sem_executar(self):
        with patch.object(m, 'run') as run:
            with self.assertRaises(m.Refused):
                m.dispatch(['reiniciar', 'aplicacao'])
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
