import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('protecao_publicacao', Path(__file__).with_name('protecao_publicacao.py'))
protecao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protecao)


class ProtecaoTest(unittest.TestCase):
    def test_substituicao_de_arquivo_altera_identificacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            codigo = raiz / 'codigo'
            codigo.mkdir()
            arquivo = codigo / 'app.py'
            arquivo.write_text('aprovada')
            config = raiz / 'compose.yml'
            config.write_text('configuracao')
            with patch.object(protecao, 'imagem_id', return_value='sha256:imagem'):
                antes = protecao.identificar(codigo, 'base', config)
                arquivo.write_text('substituida')
                self.assertNotEqual(antes, protecao.identificar(codigo, 'base', config))

    def test_mudanca_na_combinacao_ou_imagem_invalida_a_prova(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            codigo = raiz / 'codigo'
            codigo.mkdir()
            config = raiz / 'compose.yml'
            config.write_text('antiga')
            with patch.object(protecao, 'imagem_id', return_value='sha256:imagem1'):
                antes = protecao.identificar(codigo, 'base', config)
                config.write_text('concorrente')
                self.assertNotEqual(antes, protecao.identificar(codigo, 'base', config))
            with patch.object(protecao, 'imagem_id', return_value='sha256:imagem2'):
                self.assertNotEqual(antes, protecao.identificar(codigo, 'base', config))

    def test_prova_ausente_pulada_interrompida_ou_falha_nao_aprova(self):
        with tempfile.TemporaryDirectory() as pasta:
            xml = Path(pasta) / 'prova.xml'
            with self.assertRaises(FileNotFoundError):
                protecao.conferir_relatorio(xml)
            for conteudo in ('<testsuites/>', '<testsuites>',
                             '<testsuites><testcase><skipped/></testcase></testsuites>',
                             '<testsuites><testcase><failure/></testcase></testsuites>',
                             '<testsuites><testcase><error/></testcase></testsuites>'):
                xml.write_text(conteudo)
                with self.assertRaises((ValueError, protecao.ET.ParseError)):
                    protecao.conferir_relatorio(xml)
            xml.write_text('<testsuites><testcase name="executada"/></testsuites>')
            self.assertEqual(protecao.conferir_relatorio(xml)['casos'], 1)


if __name__ == '__main__':
    unittest.main()
