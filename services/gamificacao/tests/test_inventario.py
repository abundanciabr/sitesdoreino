import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, RegistroDaJornada, PerfilJogador
from apps.gamificacao.bonus_faixas import configurar
from apps.gamificacao.jornada import situacao
from apps.core.sessao import IdentidadeIndisponivel

pytestmark=pytest.mark.django_db
URL='/inventario/'
P='aluna-a'
SITE='escola-inventario'

@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv('SITE_ID',SITE)
    monkeypatch.setattr('apps.core.inventario._sessao',lambda cookie:{'autenticado':True,'id':P})

def file(name='modelo.obj',body=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'):
    return SimpleUploadedFile(name,body)

def post(client,**extras):
    dados=dict(acao='declaracao',passo='2',estado='feito',revisao=situacao(P,SITE)['revisao'])
    dados.update(extras)
    return client.post(URL,dados,HTTP_COOKIE='meshcraft_sessao=A')


def preparar_inicio(client):
    assert post(client,acao='inicio-motivo',motivo='ugc').status_code==200
    assert post(client,acao='inicio-plano',objetivo='Criar meu item',
                compromisso='Praticar e guardar minha peça',assumir='sim').status_code==200

def test_get_nao_cria_registro_e_privacidade(client):
    r=client.get(URL,HTTP_COOKIE='meshcraft_sessao=A')
    assert r.status_code==200
    assert r['Cache-Control']=='private, no-store'
    assert r['X-Robots-Tag']=='noindex, nofollow'
    assert not JornadaPessoal.objects.exists()
    assert len(r.json()['etapas'])==13

def test_anexo_obrigatorio_e_bonus_unico(client):
    configurar(SITE)
    assert post(client).status_code==400
    assert not AnexoDaJornada.objects.exists()
    assert situacao(P,SITE)['atual']['ordem']==1
    preparar_inicio(client)
    r=post(client,arquivo=file())
    assert r.status_code==200
    assert r.json()['atual_ordem']==2
    assert len(r.json()['anexos'])==1
    perfil=PerfilJogador.objects.get(pessoa_id=P,site_id=SITE)
    # A repetição não concede XP nem escreve a declaração outra vez.
    before=perfil.xp_total
    assert post(client,revisao='0',arquivo=file()).status_code==200
    perfil.refresh_from_db()
    assert perfil.xp_total==before==5000
    assert RegistroDaJornada.objects.filter(pessoa_id=P,site_id=SITE,acao='declaracao').count()==1
    assert AnexoDaJornada.objects.count()==1

def test_guardar_arquivo_sem_concluir_nao_libera_faixa(client):
    r=post(client,acao='anexo',arquivo=file())
    assert r.status_code==200 and r.json()['atual_ordem']==1
    assert not RegistroDaJornada.objects.exists()
    from apps.gamificacao.checklist_trilha import montar_checklists
    item=montar_checklists(P,SITE,situacao(P,SITE))[2]['itens'][2]
    assert item['estado']=='andamento'
    assert item['acao']['url']=='/conquistas/inicio/item/'
    assert post(client).status_code==400
    preparar_inicio(client)
    assert post(client).json()['atual_ordem']==2

def test_download_privado_por_conta_e_site(client,monkeypatch):
    r=post(client,acao='anexo',arquivo=file())
    id_=r.json()['anexos'][0]['id']
    url=f'/inventario/arquivos/{id_}/'
    r=client.get(url,HTTP_COOKIE='meshcraft_sessao=A')
    assert r.status_code==200
    assert b''.join(r.streaming_content).startswith(b'v 0')
    assert r['Content-Disposition'].startswith('attachment;')
    assert r['X-Content-Type-Options']=='nosniff'
    monkeypatch.setattr('apps.core.inventario._sessao',lambda cookie:{'autenticado':True,'id':'aluna-b'})
    assert client.get(url,HTTP_COOKIE='meshcraft_sessao=B').status_code==404
    r=client.get(URL,{'pessoa_id':P,'site_id':SITE},HTTP_COOKIE='meshcraft_sessao=B')
    assert r.json()['anexos']==[]
    monkeypatch.setattr('apps.core.inventario._sessao',lambda cookie:{'autenticado':True,'id':P})
    monkeypatch.setenv('SITE_ID','outro-site')
    assert client.get(url,HTTP_COOKIE='meshcraft_sessao=A').status_code==404

@pytest.mark.parametrize('name,body',[('modelo.html',b'<script>'),('modelo.obj',b'')])
def test_arquivo_invalido_nao_grava(client,name,body):
    assert post(client,arquivo=file(name,body)).status_code==400
    assert not AnexoDaJornada.objects.exists()
    assert not RegistroDaJornada.objects.exists()

def test_limite_de_arquivo(client,monkeypatch):
    monkeypatch.setattr('apps.core.inventario.MAX_ARQUIVO',3)
    assert post(client,arquivo=file()).status_code==400
    assert not AnexoDaJornada.objects.exists()

def test_concorrencia_revisao_nao_guarda_anexo_sem_declaracao(client):
    assert post(client,revisao='999',arquivo=file()).status_code==400
    assert not AnexoDaJornada.objects.exists()
    assert not JornadaPessoal.objects.exists()

def test_csrf_real_e_identidade_do_corpo_ignorada(monkeypatch):
    c=Client(enforce_csrf_checks=True)
    dados=c.get(URL,HTTP_COOKIE='meshcraft_sessao=A').json()
    assert c.post(URL,{'acao':'declaracao','passo':'2'},HTTP_COOKIE='meshcraft_sessao=A').status_code==403
    # O cliente conserva o cookie CSRF, e a pessoa vem da sessão.
    r=c.post(URL,{'acao':'anexo','passo':'2','revisao':0,'arquivo':file(),'pessoa_id':'aluna-b','site_id':'outro'},HTTP_X_CSRFTOKEN=dados['csrf'])
    assert r.status_code==200
    assert AnexoDaJornada.objects.get().pessoa_id==P
    assert AnexoDaJornada.objects.get().site_id==SITE

def test_sem_sessao_e_falha_identidade_nao_escrevem(client,monkeypatch):
    assert client.get(URL).status_code==403
    def fail(cookie):raise IdentidadeIndisponivel('interno')
    monkeypatch.setattr('apps.core.inventario._sessao',fail)
    r=post(client,arquivo=file())
    assert r.status_code==503 and b'interno' not in r.content
    assert not AnexoDaJornada.objects.exists()

def test_formulario_antigo_nao_contorna_anexo(client,monkeypatch):
    monkeypatch.setattr('apps.core.views.quem_e',lambda req:P)
    r=client.post('/jornada/salvar',{'acao':'declaracao','passo':'2','estado':'feito','revisao':0})
    assert r.status_code==303 and r['Location']=='/trilha/inventario/#primeiro-item'
    assert not RegistroDaJornada.objects.exists()

def test_meta_e_recebimentos_continuam_com_criterios_existentes(client):
    assert post(client,acao='meta',meta='250',proposito='Meu projeto').status_code==200
    r=client.get(URL,HTTP_COOKIE='meshcraft_sessao=A').json()
    assert r['meta_cents']==25000 and r['proposito']=='Meu projeto'
    assert post(client,acao='meta',meta='10').status_code==400
    assert post(client,acao='recebimento',valor='10',chave=r['chave'],origem='fora',recebido_em='2026-10-01').status_code==400


def test_troca_de_conta_com_formulario_aberto_nao_grava(client):
    r=post(client,arquivo=file(),contexto_pessoa='outra-pessoa',contexto_site=SITE)
    assert r.status_code==403
    assert not AnexoDaJornada.objects.exists()
    assert not RegistroDaJornada.objects.exists()
