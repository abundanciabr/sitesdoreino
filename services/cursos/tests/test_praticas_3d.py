import json,uuid
from contextlib import nullcontext
from io import BytesIO
from datetime import timedelta
from types import SimpleNamespace
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from apps.cursos.models import Base3D,Atividade3D,Projeto3D,Tentativa3D,Jornada3D,Progresso,Pessoa,Curso
from apps.core import praticas_3d
from tests.conftest import ANA,BETO,COOKIE,dublar_sessao,dublar_matricula,publicar

pytestmark=pytest.mark.django_db

@pytest.fixture
def pratica(aluna,esqueleto):
    aula=esqueleto.aulas.get(numero='E00');publicar(aula)
    base=Base3D.objects.create(chave='espada',versao=1,dados={'nome':'Espada','partes':{'lamina':{'nome':'Lâmina','cor':'#abcdef'}},'forma':{'parte':'lamina','eixo':'x','nome':'Largura'}})
    atividade=Atividade3D.objects.create(aula=aula,grupo='teste',dia=1,configuracao={'modelos':['espada@1']})
    return atividade,base

def enviar(client,atividade,id=None,revisao=0,cor='#4b82ed',titulo='Meu item',proporcao=1,explicacao=''):
    b=BytesIO();Image.new('RGB',(48,30),'#4b82ed').save(b,format='PNG')
    dados={'id':str(id or uuid.uuid4()),'revisao':revisao,'modelo':'espada','versao':1,'titulo':titulo,'receita':{'cores':{'lamina':cor},'vista':{'posicao':[3,2,7],'alvo':[0,0,0]},'proporcao':proporcao,'etapa':2,'explicacao':explicacao}}
    return client.post(reverse('salvar-item-3d',args=[atividade.pk]),{'dados':json.dumps(dados),'imagem':SimpleUploadedFile('item.png',b.getvalue(),content_type='image/png')},HTTP_COOKIE=COOKIE)

def test_salva_recupera_imagem_receita_sem_concluir_aula(pratica,client):
    a,b=pratica;r=enviar(client,a);assert r.status_code==200
    p=Projeto3D.objects.get();assert p.receita['cores']['lamina']=='#4b82ed';assert p.revisao==1
    assert client.get(reverse('imagem-item-3d',args=[p.pk]),HTTP_COOKIE=COOKIE).status_code==200
    url=reverse('aula-do-curso',args=[a.aula.curso.slug,a.aula.bloco.parte,a.aula.numero]);page=client.get(url,HTTP_COOKIE=COOKIE)
    assert page.status_code==200 and b'#4b82ed' in page.content
    assert not Progresso.objects.get(pessoa=p.pessoa,aula=a.aula).concluida_em

def test_retry_nao_duplica_e_duas_abas_nao_sobrescrevem(pratica,client):
    a,_=pratica;id=uuid.uuid4()
    assert enviar(client,a,id).status_code==200
    assert enviar(client,a,id).status_code==200
    assert Projeto3D.objects.count()==1
    assert enviar(client,a,id,1,'#ff0000').status_code==200
    assert enviar(client,a,id,1,'#00ff00').status_code==409
    assert Projeto3D.objects.get().receita['cores']['lamina']=='#ff0000'

def test_historico_compara_versoes_salvas_do_mesmo_item(pratica,client):
    a,_=pratica;item=uuid.uuid4()
    assert enviar(client,a,item).status_code==200
    assert enviar(client,a,item,1,'#ff0000').status_code==200
    estado=Tentativa3D.objects.get(atividade=a).estado
    assert len(estado['historico'])==2
    primeira,segunda=estado['historico']
    assert primeira['antes'] is None
    assert segunda['projeto_id']==primeira['projeto_id']==str(item)
    assert segunda['antes']['cores']['lamina']=='#4b82ed'
    assert segunda['depois']['cores']['lamina']=='#ff0000'

def test_avalia_5_6_7_apos_salvar_servidor_e_envia_evidencia(pratica,client,monkeypatch):
    a,_=pratica;item=uuid.uuid4();ordem={'valor':5};registros=[];imagens=[];leituras=[]
    monkeypatch.setattr(praticas_3d,'_passo_curto',lambda pessoa,site:('aprender',ordem['valor']))
    class Jornada:
        inicio={'motivo':'aprender','item_nome':'Boné novo','item_acao':'Mudei a cor da lâmina.'}
        def save(self,**kwargs):pass
    j=Jornada()
    class Jornadas:
        def filter(self,**kwargs):return self
        def first(self):return j
        def select_for_update(self):return self
        def get(self,**kwargs):return j
    class Lancamentos:
        def filter(self,**kwargs):return self
        def exclude(self,**kwargs):return self
        def exists(self):return True
    class Anexos:
        def get_or_create(self,**kwargs):
            imagens.append(kwargs)
            return SimpleNamespace(pk=1,pessoa_id=kwargs['pessoa_id'],site_id=kwargs['site_id'],
                                   nome=kwargs['defaults']['nome'],conteudo=kwargs['defaults']['conteudo'],
                                   sha256=kwargs['sha256']),True
    def avaliar(pessoa,site,passo,dados,anexos=()):
        assert passo==7 and dados['item_nome']=='Boné novo' and dados['explicacao']
        assert dados['item_acao']=='Mudei a cor da lâmina.'
        assert any(r['tipo']=='cor' and r['antes']=='#abcdef' and r['depois']=='#4b82ed'
                   and r['fonte'].startswith('tentativa:') for r in dados['registro_alteracoes'])
        assert any(r['tipo']=='proporcao' and r['antes']==1.2 and r['depois']==1.35
                   for r in dados['registro_alteracoes'])
        assert anexos[0].nome.endswith('.webp')
        leituras.append(dados['chave'])
        if len(leituras)==1:
            return {'resultado':'falha','feedback':'A análise automática não terminou. Tente novamente.',
                    'evidencia':{'observacoes':[]}}
        if len(leituras)==2:
            j.inicio={**j.inicio,'motivo':'jogo'}
        return {'resultado':'reconhecida','feedback':'A imagem mostra o item e a frase descreve seu uso imaginado.',
                'evidencia':{'observacoes':[{'fonte':'imagem','observacao':'Item visível'}]}}
    modulos={
        'config.runtime':SimpleNamespace(serving=lambda service:nullcontext()),
        'modules.gamificacao.apps.gamificacao.models':SimpleNamespace(
            JornadaPessoal=SimpleNamespace(objects=Jornadas()),LancamentoDeXP=SimpleNamespace(objects=Lancamentos()),
            AnexoDaJornada=SimpleNamespace(objects=Anexos())),
        'modules.gamificacao.apps.gamificacao.avaliacao_inicio':SimpleNamespace(avaliar=avaliar),
        'modules.gamificacao.apps.gamificacao.jornada':SimpleNamespace(
            situacao=lambda *args:{'caminho':j.inicio['motivo'],'proxima':{'ordem':ordem['valor']}},
            registrar_avaliacao=lambda *args:registros.append(args) or {'atual':{'ordem':ordem['valor']},'bonus_xp':{5:20000,6:25000,7:30000}[ordem['valor']]}),
        'modules.gamificacao.apps.gamificacao.bonus_faixas':SimpleNamespace(PONTOS={},SLUGS={5:'verde',6:'marrom',7:'preta-grau-1'}),
    }
    monkeypatch.setattr(praticas_3d,'importlib',SimpleNamespace(import_module=lambda name:modulos[name]))
    verde_resposta=enviar(client,a,item,titulo='Boné novo',proporcao=1.3)
    verde=verde_resposta.json()['avaliacao']
    assert verde['resultado']=='reconhecida' and verde['ordem']==5 and verde['bonus_xp']==20000
    assert verde_resposta.json()['url_trilha']=='/trilha/'
    assert j.inicio['projeto_ciclo_id']==str(item) and j.inicio['projeto_ciclo_base']=='espada@1'
    ordem['valor']=6
    outro=enviar(client,a,uuid.uuid4(),titulo='Boné novo',proporcao=1.4).json()['avaliacao']
    assert outro['resultado']=='incompleta' and len(registros)==1
    queda=enviar(client,a,item,1,titulo='Boné novo',proporcao=1.2).json()['avaliacao']
    assert queda['resultado']=='incompleta' and len(registros)==2
    marrom=enviar(client,a,item,2,titulo='Boné novo',proporcao=1.35).json()['avaliacao']
    assert marrom['resultado']=='reconhecida' and marrom['ordem']==6
    assert registros[2][-1]['antes']['proporcao']==1.2
    ordem['valor']=7
    inicial=enviar(client,a,item,3,titulo='Boné novo',proporcao=1.35,
                   explicacao='Vou usar o boné no personagem.').json()['avaliacao']
    assert inicial['resultado']=='falha'
    trocado=enviar(client,a,item,4,titulo='Boné novo',proporcao=1.35,
                 explicacao='Vou usar o boné no personagem.').json()['avaliacao']
    assert trocado['resultado']=='falha' and len(registros)==4
    j.inicio={**j.inicio,'motivo':'aprender'}
    preta=enviar(client,a,item,4,titulo='Boné novo',proporcao=1.35,
                 explicacao='Vou usar o boné no personagem.').json()['avaliacao']
    assert preta['resultado']=='reconhecida' and preta['ordem']==7
    assert Projeto3D.objects.get(pk=item).revisao==4
    assert len(Tentativa3D.objects.get(atividade=a).estado['historico'])==5
    assert len(imagens)==3 and len(registros)==5
    assert registros[3][-1]['chave']!=registros[4][-1]['chave']

def test_visitante_e_outra_conta_nao_leem_nem_alteram(pratica,client,rede):
    a,_=pratica;assert enviar(client,a).status_code==200;p=Projeto3D.objects.get()
    url=reverse('imagem-item-3d',args=[p.id]);assert client.get(url).status_code==404
    dublar_sessao(rede,BETO);dublar_matricula(rede,BETO['email'])
    assert client.get(url,HTTP_COOKIE=COOKIE).status_code==404
    assert enviar(client,a,p.id,1).status_code==404
    assert Projeto3D.objects.count()==1

def test_falha_imagem_nao_grava_receita_parcial(pratica,client):
    a,_=pratica;response=client.post(reverse('salvar-item-3d',args=[a.pk]),{'dados':json.dumps({'id':str(uuid.uuid4()),'modelo':'espada','versao':1,'receita':{'cores':{'lamina':'#abcdef'},'vista':{'posicao':[1,2,3],'alvo':[0,0,0]}}}),'imagem':SimpleUploadedFile('x.png',b'nao e uma imagem')},HTTP_COOKIE=COOKIE)
    assert response.status_code==400;assert Projeto3D.objects.count()==0

def test_csrf_exigido(pratica):
    from django.test import Client
    a,_=pratica;assert enviar(Client(enforce_csrf_checks=True),a).status_code==403

def test_base_preservada_ao_criar_nova_versao(pratica,client):
    a,b=pratica;assert enviar(client,a).status_code==200
    Base3D.objects.create(chave=b.chave,versao=2,dados=b.dados)
    assert Projeto3D.objects.get().base.versao==1

def test_calendario_nao_confunde_conclusao_e_tempo(pratica,client):
    a,_=pratica;curso=a.aula.curso;curso.slug=praticas_3d.DESAFIO;curso.save()
    a.dia=2;a.save();p,_=Pessoa.objects.get_or_create(id_da_plataforma=ANA['id']);j=praticas_3d.preparar_jornada(p,curso)
    assert j.inicio and not j.legado;assert praticas_3d.liberacao(a.aula,p)>timezone.now()
    url=reverse('aula-do-curso',args=[curso.slug,a.aula.bloco.parte,a.aula.numero]);assert client.get(url,HTTP_COOKIE=COOKIE).status_code==403
    j.inicio=timezone.now()-timedelta(hours=25);j.save();assert client.get(url,HTTP_COOKIE=COOKIE).status_code==200
    assert not Progresso.objects.get(pessoa=p,aula=a.aula).concluida_em

def test_legado_sem_data_inventada(pratica):
    a,_=pratica;curso=a.aula.curso;curso.slug=praticas_3d.DESAFIO;curso.save();a.dia=7;a.save();p,_=Pessoa.objects.get_or_create(id_da_plataforma=ANA['id'])
    Jornada3D.objects.create(pessoa=p,curso=curso,legado=True,inicio=None)
    j=praticas_3d.preparar_jornada(p,curso);assert j.inicio is None;assert praticas_3d.liberacao(a.aula,p) is None

def test_gesto_no_endereco_antigo_tambem_respeita_calendario(pratica,client):
    a,_=pratica;curso=a.aula.curso;curso.slug=praticas_3d.DESAFIO;curso.save();a.dia=2;a.save()
    r=client.post(reverse('concluir-aula',args=[a.aula.numero]),HTTP_COOKIE=COOKIE)
    assert r.status_code==403
    assert Jornada3D.objects.filter(curso=curso,legado=False,inicio__isnull=False).exists()

def test_dados_fora_do_catalogo_nao_gravam(pratica,client):
    a,_=pratica;assert enviar(client,a,cor='not-a-color').status_code==400
    assert Projeto3D.objects.count()==0

def test_previa_da_equipe_nao_publica_configuracao_nem_projeto(pratica,client,monkeypatch):
    a,_=pratica;monkeypatch.setenv('ADMIN_EMAILS',ANA['email'])
    config={**a.configuracao,'titulo':'Prévia sem publicação'}
    r=client.post(reverse('producao-praticas-3d'),{'atividade':str(a.pk),'acao':'previa','configuracao':json.dumps(config)},HTTP_COOKIE=COOKIE)
    assert r.status_code==200 and 'Prévia sem publicação' in r.content.decode()
    a.refresh_from_db();assert 'titulo' not in a.configuracao
    assert Projeto3D.objects.count()==0
