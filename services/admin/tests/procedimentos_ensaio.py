"""Ensaio isolado: python tests/procedimentos_ensaio.py (SQLite em memória, sem rede)."""
import json
import sys
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from django.conf import settings
if not settings.configured:
    settings.configure(SECRET_KEY='ensaio-isolado', USE_TZ=True, TIME_ZONE='America/Sao_Paulo',
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        INSTALLED_APPS=['django.contrib.contenttypes','apps.core','apps.agentes','apps.atendimento','apps.auditoria','apps.comercial','apps.voz','apps.assistente','apps.hotmart','apps.feed_previa'],
        DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
        TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}], ROOT_URLCONF='urls_ensaio')
import django
django.setup()
from django.apps import apps
from django.db import connection
from django.utils import timezone
from django.test import RequestFactory
from django.urls import path
from apps.agentes import procedimentos as p
from apps.agentes.models import (RotinaProcedimentos, AgrupamentoProcedimento, CasoProcedimento,
    Execucao, Consumo, AutorizacaoDeGasto, MelhoriaSuperEquipe, RotinaSuperEquipe, EventoSuperEquipe)
from apps.agentes.procedimentos_texto import limpar, teste_identificado
from apps.agentes.views_procedimentos import painel
from apps.atendimento.models import Conversa, Mensagem, Assunto
urls = ModuleType('urls_ensaio')
urls.urlpatterns = [path('procedimentos/', painel, name='procedimentos_painel'),
    path('super-equipe/', painel, name='super_equipe'), path('documentos/', painel, name='documentos_admin')]
sys.modules['urls_ensaio'] = urls


class Ensaio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            for model in apps.get_models():
                editor.create_model(model)

    def setUp(self):
        self.rotina = RotinaProcedimentos.objects.create(host=uuid.uuid4().hex, site_id=uuid.uuid4().hex)
        self.agora = timezone.now()
        self.inicio = self.agora-timedelta(days=14)

    def caso(self, chave, pessoa, **campos):
        return {'chave': chave, 'pessoa': pessoa, 'titulo': 'Modelo gigante ao importar no Roblox Studio',
            'sintoma': 'Modelo gigante ao importar no Roblox Studio', 'solucao': 'Aplicar escala antes de exportar',
            'confirmada': True, 'ocorrida_em': self.agora.isoformat(), 'referencia': 'https://meshcraft.top/forum/t/'+chave,
            'contexto': '', 'publico': 'alunos', **campos}

    def incorporar(self, itens):
        p.incorporar(self.rotina, 'forum', itens, self.inicio, self.agora)
        p.agrupar(self.rotina, self.inicio)
        return AgrupamentoProcedimento.objects.get(rotina=self.rotina)

    def test_tres_independentes_e_reenvio(self):
        itens = [self.caso(str(i),str(i)) for i in range(3)]
        g = self.incorporar(itens)
        self.incorporar(itens)
        self.assertEqual(g.redacoes.count(), 1)
        self.assertEqual(g.casos.count(), 3)
        self.assertEqual(g.casos_independentes, 3)

    def test_mesma_pessoa_nao_infla(self):
        g = self.incorporar([self.caso(str(i),'mesma') for i in range(3)])
        self.assertEqual(g.casos_independentes,1)
        self.assertFalse(g.redacoes.exists())

    def test_janela_e_fontes_revogadas(self):
        itens = [self.caso(str(i),str(i)) for i in range(3)]
        itens[2]['ocorrida_em'] = (self.inicio-timedelta(seconds=1)).isoformat()
        g = self.incorporar(itens)
        self.assertEqual(g.casos_independentes,2)
        self.incorporar([itens[0]])
        g.refresh_from_db()
        self.assertEqual(g.casos_independentes,1)

    def test_testes_e_segredos(self):
        self.assertTrue(teste_identificado('Teste técnico autorizado pelo mantenedor'))
        self.assertFalse(teste_identificado('Como testar o modelo no Studio?'))
        limpo = limpar('cpf 123.456.789-00 email pessoa@example.com token=segredo https://a.com/?token=abc')
        self.assertNotIn('segredo', limpo.replace('[segredo omitido]',''))
        self.assertNotIn('123.456',limpo)
        self.assertNotIn('pessoa@example',limpo)
        p.incorporar(self.rotina, 'forum', [self.caso('1','1',titulo='Teste técnico autorizado')], self.inicio, self.agora)
        self.assertEqual(CasoProcedimento.objects.filter(rotina=self.rotina).count(),0)

    def test_sem_solucao_nao_chama_ia(self):
        g = self.incorporar([self.caso(str(i),str(i),confirmada=False,solucao='') for i in range(3)])
        self.assertTrue(g.elegivel)
        self.assertFalse(g.redacoes.exists())

    def test_publicos_e_contextos_separados(self):
        p.incorporar(self.rotina,'forum',[self.caso('1','1'),self.caso('2','2',publico='interno'),
            self.caso('3','3',contexto='curso-a'),self.caso('4','4',contexto='curso-b')],self.inicio,self.agora)
        p.agrupar(self.rotina,self.inicio)
        self.assertEqual(AgrupamentoProcedimento.objects.filter(rotina=self.rotina,publico='interno').count(),1)
        # Contexto vazio não pode servir de ponte entre cursos incompatíveis.
        contextos = [set(g.casos.values_list('contexto',flat=True))-{''} for g in AgrupamentoProcedimento.objects.filter(rotina=self.rotina)]
        self.assertTrue(all(len(c)<=1 for c in contextos))

    def test_suporte_encerrado_nao_confirmado_e_teste_excluido(self):
        a = Assunto.objects.create(site_id=self.rotina.site_id,nome='Studio')
        c = Conversa.objects.create(site_id=self.rotina.site_id,pessoa_id='a',assunto=a,estado='encerrado')
        Mensagem.objects.create(conversa=c,referencia='1',autor='aluno',texto='Modelo gigante no Studio')
        Mensagem.objects.create(conversa=c,referencia='2',autor='equipe',texto='Aplique escala')
        itens, _ = p.suporte(self.rotina,self.inicio)
        self.assertFalse(itens[0]['confirmada'])
        c.resolucao='confirmada'; c.save()
        self.assertTrue(p.suporte(self.rotina,self.inicio)[0][0]['confirmada'])
        Mensagem.objects.filter(conversa=c,referencia='1').update(texto='Teste técnico autorizado')
        self.assertEqual(p.suporte(self.rotina,self.inicio)[1],1)

    def test_monitor_repeticoes_nao_sao_novos_episodios(self):
        rt = RotinaSuperEquipe.objects.create(host=self.rotina.host)
        m = MelhoriaSuperEquipe.objects.create(rotina=rt,chave='x',titulo='Servidor com erros HTTP',observada_em=self.agora,
            evidencia={'operacao':'fonte','episodio':'um'})
        EventoSuperEquipe.objects.create(melhoria=m,situacao='pendente',texto='Identificada automaticamente pelas fontes do site.')
        for _ in range(3):
            itens, _ = p.monitor(self.rotina,self.inicio)
            p.incorporar(self.rotina,'monitor',itens,self.inicio,self.agora+timedelta(minutes=1))
        self.assertEqual(CasoProcedimento.objects.filter(rotina=self.rotina).count(),1)

    def test_redacao_custo_e_retomada_sem_reenvio(self):
        g = self.incorporar([self.caso(str(i),str(i)) for i in range(3)])
        e = g.redacoes.get().execucao
        e.situacao='executando';e.trabalhador='ensaio';e.save()
        with patch('apps.agentes.modelo.conexao',return_value=SimpleNamespace(modelo_forte='modelo-teste')), \
             patch('apps.agentes.modelo.responder',return_value=SimpleNamespace(texto=json.dumps({'corpo':'Sintoma: escala. Causa não confirmada.','respostas':{}}),completa=True)) as chamada:
            p.executar(e)
            e.situacao='executando'; e.save(update_fields=['situacao'])
            p.executar(e)
        self.assertEqual(chamada.call_count,1)
        g.refresh_from_db();self.assertTrue(g.rascunho)
        self.assertEqual(chamada.call_args.kwargs['origem'],'procedimentos')
        self.assertEqual(chamada.call_args.kwargs['execucao'].pk,e.pk)

    def test_consumo_previo_impede_chamada(self):
        g = self.incorporar([self.caso(str(i),str(i)) for i in range(3)])
        e = g.redacoes.get().execucao
        e.situacao='executando';e.trabalhador='ensaio';e.save()
        a = AutorizacaoDeGasto.objects.create(teto_mensal_usd=10, descricao='Ensaio', fonte='Ensaio isolado')
        Consumo.objects.create(execucao=e,autorizacao=a,modelo='teste',origem='procedimentos',custo_estimado_usd='.01',desconhecido=True)
        with patch('apps.agentes.modelo.responder') as chamada:
            p.executar(e)
        chamada.assert_not_called()
        e.refresh_from_db();self.assertEqual(e.situacao,'falhou')

    def test_painel_e_idiomas(self):
        req = RequestFactory().get('/procedimentos/')
        req.admin={'email':'admin@example.com'}
        with patch('apps.agentes.modelo.autorizacao_ativa',return_value=None):
            r=painel(req)
        self.assertEqual(r.status_code,200)
        self.assertIn('Guardar idiomas'.encode(),r.content)
        req.admin={'equipe_apenas':True}
        self.assertEqual(painel(req).status_code,403)
        req=RequestFactory().post('/procedimentos/',{'acao':'idiomas','idioma1':'Português','idioma2':'Inglês','idioma3':'Espanhol'})
        req.admin={'email':'admin@example.com'}
        self.assertEqual(painel(req).status_code,302)
        self.assertEqual(RotinaProcedimentos.objects.get(host='meshcraft.top').idiomas,['Português','Inglês','Espanhol'])

    def test_agenda_sao_paulo(self):
        seguinte=p.proxima_noite(self.agora)
        self.assertGreater(seguinte,self.agora)
        self.assertEqual(seguinte.astimezone(p.SP).hour,2)

    def test_coleta_parcial_nao_redige_e_lease_impede_duplicacao(self):
        rt,_=RotinaProcedimentos.objects.get_or_create(host='meshcraft.top')
        rt.site_id=self.rotina.site_id;rt.proxima_em=self.agora;rt.save()
        with patch.object(p,'forum',side_effect=ValueError()), patch.object(p,'suporte',return_value=([],0)), \
             patch.object(p,'monitor',return_value=([],0)), patch.object(p,'agrupar') as agrupador:
            self.assertTrue(p.ciclo())
            self.assertFalse(p.ciclo())
            agrupador.assert_not_called()
        rt.refresh_from_db()
        self.assertEqual(rt.fontes['forum']['estado'],'indisponivel')
        self.assertEqual(rt.proxima_em.astimezone(p.SP).hour,2)
        rt.proxima_em=self.agora;rt.ocupada_ate=self.agora+timedelta(minutes=20);rt.save()
        self.assertFalse(p.ciclo())

if __name__=='__main__':
    unittest.main()
