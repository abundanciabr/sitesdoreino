import json,uuid
from io import BytesIO
from datetime import timedelta
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from apps.cursos.models import Base3D,Atividade3D,Projeto3D,Jornada3D,Progresso,Pessoa,Curso
from apps.core import praticas_3d
from tests.conftest import ANA,BETO,COOKIE,dublar_sessao,dublar_matricula,publicar

pytestmark=pytest.mark.django_db

@pytest.fixture
def pratica(aluna,esqueleto):
    aula=esqueleto.aulas.get(numero='E00');publicar(aula)
    base=Base3D.objects.create(chave='espada',versao=1,dados={'nome':'Espada','partes':{'lamina':{'nome':'Lâmina','cor':'#abcdef'}},'forma':{'parte':'lamina','eixo':'x','nome':'Largura'}})
    atividade=Atividade3D.objects.create(aula=aula,grupo='teste',dia=1,configuracao={'modelos':['espada@1']})
    return atividade,base

def enviar(client,atividade,id=None,revisao=0,cor='#4b82ed',titulo='Meu item'):
    b=BytesIO();Image.new('RGB',(48,30),'#4b82ed').save(b,format='PNG')
    dados={'id':str(id or uuid.uuid4()),'revisao':revisao,'modelo':'espada','versao':1,'titulo':titulo,'receita':{'cores':{'lamina':cor},'vista':{'posicao':[3,2,7],'alvo':[0,0,0]},'proporcao':1,'etapa':2}}
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

def test_dados_fora_do_catalogo_nao_gravam(pratica,client):
    a,_=pratica;assert enviar(client,a,cor='not-a-color').status_code==400
    assert Projeto3D.objects.count()==0
