"""A proteção aceita o pacote real e recusa alterações específicas da pesquisa."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'infra'))
import satisfacao_congelada as guarda


class PesquisaCongeladaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporario = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temporario.name)
        cls.fonte = cls.base / 'fonte'
        for servico in ('cursos', 'quiz'):
            shutil.copytree(RAIZ / 'services' / servico, cls.fonte / 'services' / servico,
                ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
        cls.referencia = guarda.resumo(cls.fonte)
        spec = importlib.util.spec_from_file_location('empacotador_aprovado', RAIZ / 'services/aplicacao/preparar.py')
        cls.empacotador = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.empacotador)
        cls.pacote = cls.base / 'pacote'
        with patch.object(cls.empacotador, 'MODULOS', ('cursos', 'quiz')):
            cls.empacotador.preparar(cls.fonte / 'services', cls.pacote / 'modules')

    @classmethod
    def tearDownClass(cls):
        cls.temporario.cleanup()

    def test_empacotamento_real_equivale_a_fonte(self):
        guarda.comparar(guarda.resumo(self.pacote, pacote=True), self.referencia)

    def alterar(self, nome, substituir):
        caminho = self.fonte / nome
        original = caminho.read_text(encoding='utf-8')
        novo = substituir(original)
        self.assertNotEqual(original, novo)
        try:
            caminho.write_text(novo, encoding='utf-8')
            with self.assertRaises(guarda.IntegridadePesquisaErro):
                guarda.comparar(guarda.resumo(self.fonte), self.referencia)
        finally:
            caminho.write_text(original, encoding='utf-8')

    def test_calculo_controlador_modelos_template_rotas_e_auth(self):
        casos = {
            'services/quiz/apps/quiz/nps_revisado.py': lambda t: t + '\nCALCULO_ALTERADO = True\n',
            'services/cursos/apps/core/satisfacao.py': lambda t: t.replace('if not ator.matricula_conferida', 'if False and not ator.matricula_conferida'),
            'services/quiz/apps/quiz/models.py': lambda t: t.replace('class NPSTentativa(models.Model):', 'class NPSTentativa(models.Model):\n    alterada = models.BooleanField(default=True)'),
            'services/cursos/apps/core/templates/cursos/satisfacao.html': lambda t: t.replace('Começar avaliação', 'Outro formulário'),
            'services/quiz/config/urls.py': lambda t: t.replace('nps.respostas)', 'quiz_views.healthz)'),
            'services/cursos/config/urls.py': lambda t: t.replace('pesquisa as satisfacao', 'outro as satisfacao'),
            'services/quiz/apps/quiz/editor.py': lambda t: t.replace('and bool(token)', 'or bool(token)'),
            'services/cursos/apps/core/views.py': lambda t: t.replace('if pode_avaliar_curso(ator, curso):', 'if ator.eh_admin:'),
            'services/cursos/apps/core/templates/cursos/mapa.html': lambda t: t.replace('Avaliar este curso', 'Outro destino'),
        }
        for nome, substituir in casos.items():
            with self.subTest(nome=nome):
                self.alterar(nome, substituir)

    def test_migracao_nova_que_altera_nps_e_recusada(self):
        caminho = self.fonte / 'services/quiz/apps/quiz/migrations/9999_teste.py'
        try:
            caminho.write_text("from django.db import migrations\nclass Migration(migrations.Migration):\n    operations = [migrations.DeleteModel(name='NPSTentativa')]\n", encoding='utf-8')
            with self.assertRaises(guarda.IntegridadePesquisaErro):
                guarda.comparar(guarda.resumo(self.fonte), self.referencia)
        finally:
            caminho.unlink()

    def test_outros_quizzes_e_cursos_continuam_livres(self):
        nomes = ('services/cursos/apps/core/views.py', 'services/quiz/apps/quiz/models.py',
            'services/quiz/config/urls.py', 'services/cursos/apps/core/templates/cursos/mapa.html')
        for nome in nomes:
            caminho = self.fonte / nome
            original = caminho.read_text(encoding='utf-8')
            try:
                caminho.write_text(original + ('\nAREA_INDEPENDENTE = 1\n' if nome.endswith('.py')
                    else '\n<p>Outro conteúdo do curso</p>\n'), encoding='utf-8')
                guarda.comparar(guarda.resumo(self.fonte), self.referencia)
            finally:
                caminho.write_text(original, encoding='utf-8')

    def test_politica_da_candidata_nao_substitui_referencia(self):
        politica = self.base / 'politica-independente.json'
        politica.write_text(json.dumps({'resumo': self.referencia}), encoding='utf-8')
        falsa = self.fonte / 'satisfacao/politica.json'
        falsa.parent.mkdir(exist_ok=True)
        falsa.write_text(json.dumps({'resumo': {'qualquer': '0' * 64}}), encoding='utf-8')
        with patch.object(guarda, 'POLITICA', politica):
            guarda.conferir_fontes_satisfacao(self.fonte)
        with patch.object(guarda, 'POLITICA', self.base / 'ausente.json'):
            with self.assertRaises(guarda.IntegridadePesquisaErro):
                guarda.conferir_fontes_satisfacao(self.fonte)

    def test_arquivo_ausente_recusa_publicacao(self):
        caminho = self.fonte / 'services/cursos/apps/core/satisfacao.py'
        reserva = caminho.with_suffix('.reserva')
        caminho.rename(reserva)
        try:
            with self.assertRaises(guarda.IntegridadePesquisaErro):
                guarda.resumo(self.fonte)
        finally:
            reserva.rename(caminho)

    def test_referencia_invalida_recusa(self):
        with self.assertRaises(guarda.IntegridadePesquisaErro):
            guarda.comparar(self.referencia, {})

    def test_recuperacao_recusa_pesquisa_alterada_antes_de_trocar_codigo(self):
        plataforma = self.base / 'plataforma'
        (plataforma / 'publicacoes').mkdir(parents=True, exist_ok=True)
        atual, alvo = '1' * 40, '2' * 40
        journal = plataforma / 'publicacoes/aplicacao.json'
        original = json.dumps({'atual': atual, 'servicos': ['aplicacao'],
            'aprovada': {'sha': alvo, 'codigo': str(self.pacote), 'imagem': 'sha256:' + 'a' * 64}})
        journal.write_text(original, encoding='utf-8')
        politica = self.base / 'politica-recuperacao.json'
        politica.write_text(json.dumps({'resumo': self.referencia}), encoding='utf-8')
        spec = importlib.util.spec_from_file_location('publicacao_local_pesquisa', RAIZ / 'infra/publicacao-local.py')
        local = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'PLATAFORMA_DIR': str(plataforma), 'CELULA': 'aplicacao',
                'TAG': alvo, 'ATUAL_ESPERADA': atual}):
            spec.loader.exec_module(local)
            caminho = self.pacote / 'modules/cursos/apps/core/templates/cursos/satisfacao.html'
            texto = caminho.read_text(encoding='utf-8')
            pin, imagem = Mock(), Mock()
            try:
                caminho.write_text(texto + '<p>Pesquisa alterada</p>', encoding='utf-8')
                with patch.object(guarda, 'POLITICA', politica), patch.object(local, 'conferir_codigo_docs'), \
                        patch.object(local, 'pin', pin), patch.object(local, 'garantir_imagem', imagem):
                    with self.assertRaises(guarda.IntegridadePesquisaErro):
                        local.executar('recuperar')
                pin.assert_not_called()
                imagem.assert_not_called()
                self.assertEqual(journal.read_text(encoding='utf-8'), original)
            finally:
                caminho.write_text(texto, encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
