import unittest
import operacao_contexto as c


class ContextoTests(unittest.TestCase):
    def test_catalogo_nao_consulta_nem_executa(self):
        rc, data = c.dispatch(['ajuda'], lambda _: self.fail('não deve executar'))
        self.assertEqual(rc, 0)
        self.assertIn('limite', data['execucao'])

    def test_retomar_so_consulta_mesmo_id(self):
        calls = []
        def query(args):
            calls.append(args)
            return 0, {'id': 'a'*12, 'estado': 'recebida'}
        rc, data = c.dispatch(['retomar', 'a'*12], query)
        self.assertEqual(calls, [['consultar', 'a'*12]])
        self.assertEqual(data['entrega']['id'], 'a'*12)
        self.assertEqual(rc, 0)

    def test_id_divergente_nao_e_confirmado(self):
        with self.assertRaises(ValueError):
            c.dispatch(['retomar', 'a'*12], lambda _: (0, {'id': 'b'*12}))

    def test_injecoes_e_comandos_desconhecidos_nao_executam(self):
        for args in (['retomar', '../arquivo'], ['retomar', 'a'*12, 'x'],
                     ['operacoes', '0'], ['operacoes', '51'], ['operacoes', ';id'],
                     ['contexto', 'exec'], ['shell'], ['entregar'], ['ajuda', 'x']):
            with self.subTest(args=args):
                rc, _ = c.dispatch(args, lambda _: self.fail('não deve executar'))
                self.assertEqual(rc, 2)

    def test_saida_resumida_nao_carrega_provas_volumosas(self):
        rows = [{'id': f'{n:012x}', 'provas': 'x'*10000,
                 'operacao': {'fase': 'ativa'}, 'segredo': 'nao-exibir'} for n in range(80)]
        data = c.resumir(rows, 3)
        self.assertEqual(data['total'], 80)
        self.assertEqual(len(data['operacoes']), 3)
        self.assertNotIn('segredo', str(data))
        self.assertNotIn('provas', str(data))
        self.assertNotIn('em_andamento', data['operacoes'][0]['operacao'])

    def test_contexto_parcial_nao_afirma_sucesso(self):
        calls = []
        def query(args):
            calls.append(args)
            return (0, []) if args == ['estado'] else (3, {'indisponivel': True})
        rc, data = c.dispatch(['contexto'], query)
        self.assertEqual(rc, 3)
        self.assertFalse(data['completo'])
        self.assertEqual(calls, [['estado'], ['servicos', 'saude'], ['analisador', 'consultar']])

    def test_recusa_existente_preservada(self):
        refusal = {'recusado': True, 'motivo': 'entrega não existe'}
        self.assertEqual(c.dispatch(['retomar', 'a'*12], lambda _: (2, refusal)), (2, refusal))


if __name__ == '__main__':
    unittest.main()
