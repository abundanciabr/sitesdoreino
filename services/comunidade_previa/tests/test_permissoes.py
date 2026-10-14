"""Executa as funções REAIS do fórum com dados controlados, sem banco/rede."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PermissoesReais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.salvos = dict(sys.modules)
        for name in ('apps', 'apps.core', 'apps.forum', 'apps.forum.models', 'apps.core.sessao'):
            sys.modules[name] = types.ModuleType(name)
        class Area:
            Visibilidade = types.SimpleNamespace(PUBLICA='publica', ALUNOS='alunos', TURMA='turma')
            QuemEscreve = types.SimpleNamespace(EQUIPE='equipe', ALUNO='aluno', CADASTRADO='cadastrado')
        cls.vinculos = set()
        class Membros:
            def filter(self, grupo, pessoa, ate__isnull):
                return types.SimpleNamespace(exists=lambda: (grupo.slug, pessoa.pk) in cls.vinculos)
        sys.modules['apps.forum.models'].Area = Area
        sys.modules['apps.forum.models'].MembroDoGrupo = types.SimpleNamespace(objects=Membros())
        sys.modules['apps.core.sessao'].Ator = object
        source = ROOT / 'permissoes.py'
        if not source.exists():
            source = ROOT.parent / 'forum/apps/core/permissoes.py'
        spec = importlib.util.spec_from_file_location('apps.core.permissoes', source)
        cls.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.p)

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules):
            if name not in cls.salvos:
                sys.modules.pop(name, None)
        sys.modules.update(cls.salvos)

    def setUp(self):
        self.vinculos.clear()
        self.vinculos.add(('grupo-a', 'ana'))
        self.a = types.SimpleNamespace(ativa=True, visibilidade='turma', quem_escreve='aluno', slug='grupo-a')

    def ator(self, id='ana', aluno=True, equipe=False, autenticado=True):
        return types.SimpleNamespace(pessoa=types.SimpleNamespace(pk=id) if autenticado else None,
                                     eh_aluno=aluno, eh_equipe=equipe, autenticado=autenticado)

    def test_membro_ativo_le_e_escreve(self):
        self.assertTrue(self.p.pode_ler(self.a, self.ator()))
        self.assertTrue(self.p.pode_escrever(self.a, self.ator()))

    def test_outro_grupo_nao_le_nem_escreve(self):
        self.assertFalse(self.p.pode_ler(self.a, self.ator('bia')))
        self.assertFalse(self.p.pode_escrever(self.a, self.ator('bia')))

    def test_matricula_encerrada_nao_abre_vinculo(self):
        self.assertFalse(self.p.pode_ler(self.a, self.ator(aluno=False)))

    def test_visitante_nao_abre_grupo(self):
        self.assertFalse(self.p.pode_ler(self.a, self.ator(aluno=False, autenticado=False)))

    def test_equipe_nao_precisa_de_vinculo(self):
        self.assertTrue(self.p.pode_escrever(self.a, self.ator('escola', aluno=False, equipe=True)))

    def test_saida_revoga_leitura(self):
        self.vinculos.clear()
        self.assertFalse(self.p.pode_ler(self.a, self.ator()))

    def test_retorno_reabre_pelo_vinculo(self):
        self.vinculos.clear()
        self.vinculos.add(('grupo-a', 'ana'))
        self.assertTrue(self.p.pode_ler(self.a, self.ator()))

    def test_arquivado_so_equipe(self):
        self.a.ativa = False
        self.assertFalse(self.p.pode_ler(self.a, self.ator()))
        self.assertTrue(self.p.pode_ler(self.a, self.ator('escola', equipe=True)))

    def test_area_geral_exige_matricula(self):
        self.a.visibilidade = 'alunos'
        self.assertTrue(self.p.pode_ler(self.a, self.ator('bia')))
        self.assertFalse(self.p.pode_ler(self.a, self.ator('bia', aluno=False)))

    def test_publica_so_escola_escreve(self):
        self.a.visibilidade = 'publica'
        self.assertTrue(self.p.pode_ler(self.a, self.ator(autenticado=False)))
        self.assertFalse(self.p.pode_escrever(self.a, self.ator()))
        self.assertTrue(self.p.pode_escrever(self.a, self.ator('escola', equipe=True)))

    def test_visibilidade_desconhecida_fecha(self):
        self.a.visibilidade = 'desconhecida'
        self.assertFalse(self.p.pode_ler(self.a, self.ator()))

    def test_escrita_exclusiva_da_equipe(self):
        self.a.quem_escreve = 'equipe'
        self.assertFalse(self.p.pode_escrever(self.a, self.ator()))

    def test_html_nao_chama_api_nem_publica(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('fetch(', html)
        self.assertNotIn('XMLHttpRequest', html)
        self.assertNotIn('localStorage', html)
        self.assertIn('dados de teste', html)
        self.assertIn('Grupo A · teste', html)
        self.assertIn((ROOT / 'motor.cjs').read_text(encoding='utf-8'), html)


if __name__ == '__main__':
    unittest.main()
