import asyncio
import json
import uuid

import httpx
import pytest
import respx
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.core import feed_previa_social as social
from apps.feed_previa import mensagens as dm
from apps.feed_previa.models import FeedPreviaConversa as Conversa, FeedPreviaMensagem as Mensagem, FeedPreviaPerfil as Perfil

pytestmark = pytest.mark.django_db


def req(data=None, admin='a', host='testserver', query=''):
    factory = RequestFactory()
    r = factory.get('/'+query, HTTP_HOST=host) if data is None else factory.post('/', data=json.dumps(data), content_type='application/json', HTTP_HOST=host)
    r.admin = {'id': admin, 'nome': 'Admin '+admin}
    return r


def perfil(admin, host='testserver'):
    social.dados(req(admin=admin, host=host))
    return social.contexto(req(admin=admin, host=host))[1]


def iniciar(a='a', b='b'):
    perfil(a);par=perfil(b)
    r=dm.iniciar(req({'profile':par.chave},a))
    assert r.status_code==200, r.content
    return json.loads(r.content)['chat']['id']


def enviar(c, text='Uma ideia para sua criação 🚀', admin='a', key=None):
    data={'conversation':c,'text':text,'request_key':str(key or uuid.uuid4())}
    r=dm.enviar(req(data,admin))
    assert r.status_code==200, r.content
    return json.loads(r.content)


def test_ciclo_privado_envio_resposta_leitura_e_persistencia():
    c=iniciar()
    data=enviar(c)
    assert data['chat']['messages'][0]['mine'] and not data['chat']['messages'][0]['read']
    b=json.loads(dm.lista(req(admin='b')).content)
    assert b['unread']==1 and len(b['conversations'])==1
    assert not b['conversations'][0]['last_mine']
    received=json.loads(dm.conversa(req(admin='b'),c).content)
    assert not received['messages'][0]['mine'] and received['messages'][0]['text'].endswith('🚀')
    assert Mensagem.objects.get().lida_em is None  # Abrir a API não marca mensagens invisíveis como lidas.
    dm.ler(req({'conversation':c,'before':received['messages'][0]['id']},'b'))
    assert json.loads(dm.lista(req(admin='b')).content)['unread']==0
    assert json.loads(dm.conversa(req(),c).content)['messages'][0]['read']
    enviar(c,'Vamos comparar as silhuetas! 👏','b')
    assert json.loads(dm.lista(req()).content)['unread']==1
    assert Mensagem.objects.count()==2 and Conversa.objects.count()==1


def test_dupla_canonica_reutiliza_conversa_de_ambos_os_lados():
    c=iniciar()
    assert iniciar('b','a')==c
    assert Conversa.objects.count()==1
    par=perfil('a')
    assert dm.iniciar(req({'profile':par.chave})).status_code==400


def test_reenvio_idempotente_identidade_imposta_pela_sessao():
    c=iniciar();key=uuid.uuid4()
    enviar(c,key=key);enviar(c,key=key)
    assert Mensagem.objects.count()==1
    assert dm.enviar(req({'conversation':c,'text':'Outro texto','request_key':str(key)})).status_code==400
    assert dm.enviar(req({'conversation':c,'text':'Uma ideia para sua criação 🚀','request_key':str(key)},'b')).status_code==400
    forged={'conversation':c,'text':'Mensagem legítima','request_key':str(uuid.uuid4()),'autor':perfil('b').chave,'demonstracao':True}
    assert dm.enviar(req(forged)).status_code==200
    m=Mensagem.objects.latest('pk')
    assert m.autor==perfil('a') and not m.demonstracao


def test_outro_admin_nao_pode_listar_ler_enviar_ou_assinar_conversa():
    c=iniciar();enviar(c);perfil('c')
    assert json.loads(dm.lista(req(admin='c')).content)['conversations']==[]
    assert dm.conversa(req(admin='c'),c).status_code==404
    assert dm.stream(req(admin='c',query='?conversation='+c)).status_code==404
    for view in [dm.enviar,dm.ler,dm.simular]:
        assert view(req({'conversation':c,'text':'Intrusão','before':99999,'request_key':str(uuid.uuid4())},'c')).status_code==404
    assert Mensagem.objects.count()==1 and Mensagem.objects.get().lida_em is None


def test_isolamento_entre_hosts_e_ausencia_no_feed_publico():
    c=iniciar();enviar(c,'SEGREDO-PRIVADO-DO-TESTE')
    eu=perfil('a','outro.test')
    assert dm.iniciar(req({'profile':perfil('b').chave},host='outro.test')).status_code==404
    assert dm.conversa(req(host='outro.test'),c).status_code==404
    assert json.loads(dm.lista(req(host='outro.test')).content)['conversations']==[]
    assert 'SEGREDO-PRIVADO-DO-TESTE' not in social.dados(req()).content.decode()
    assert all(m._meta.db_table.startswith('admin_feed_previa_') for m in [Conversa,Mensagem])


def test_ler_apenas_recebidas_ate_o_limite_preserva_nova_mensagem():
    c=iniciar();enviar(c,admin='b');cut=Mensagem.objects.latest('pk').pk
    enviar(c,admin='b');enviar(c,admin='a')
    data=json.loads(dm.ler(req({'conversation':c,'before':cut})).content)
    assert data['unread']==1
    assert list(Mensagem.objects.order_by('pk').values_list('lida_em',flat=True))[0] is not None
    assert Mensagem.objects.order_by('pk')[1].lida_em is None and Mensagem.objects.order_by('pk')[2].lida_em is None
    assert dm.ler(req({'conversation':c,'before':True})).status_code==400


def test_simulacao_explicita_so_com_perfil_ficticio_sem_alterar_comunidade():
    perfil('a');perfil('b')
    lia=Perfil.objects.get(site_host='testserver',chave='lia')
    c=json.loads(dm.iniciar(req({'profile':lia.chave})).content)['chat']['id']
    original=social.dados(req()).content
    data={'conversation':c,'request_key':str(uuid.uuid4())}
    assert dm.simular(req(data)).status_code==200 and dm.simular(req(data)).status_code==200
    m=Mensagem.objects.get();assert m.demonstracao and m.autor==lia
    assert dm.retrato(perfil('a'))['unread']==1
    assert social.dados(req()).content==original
    real=iniciar()
    assert dm.simular(req({'conversation':real,'request_key':str(uuid.uuid4())})).status_code==400
    assert Mensagem.objects.count()==1


def test_paginacao_carrega_todo_historico_sem_apagar():
    c=iniciar();autor=perfil('b')
    Mensagem.objects.bulk_create([Mensagem(conversa_id=c,autor=autor,texto=f'Mensagem {i}',chave_pedido=uuid.uuid4()) for i in range(115)])
    last=json.loads(dm.conversa(req(),c).content)
    assert len(last['messages'])==50 and last['has_more']
    middle=json.loads(dm.conversa(req(query='?before='+str(last['messages'][0]['id'])),c).content)
    first=json.loads(dm.conversa(req(query='?before='+str(middle['messages'][0]['id'])),c).content)
    combined=first['messages']+middle['messages']+last['messages']
    assert len(combined)==115 and len({m['id'] for m in combined})==115 and not first['has_more']
    assert combined[0]['text']=='Mensagem 0' and combined[-1]['text']=='Mensagem 114'
    assert dm.retrato(perfil('a'))['unread']==115


def test_stream_assincrono_entrega_mensagem_e_leitura(monkeypatch):
    perfil('a')
    states=iter([{'conversations':[],'unread':0,'latest':0}, {'conversations':[{'last_id':1}],'unread':1,'latest':1}, {'conversations':[{'last_id':1}],'unread':0,'latest':1}])
    monkeypatch.setattr(dm,'pulso',lambda *args:next(states))
    async def sem_espera(*args):
        return None
    monkeypatch.setattr(dm.asyncio,'sleep',sem_espera)
    response=dm.stream(req())
    assert response.status_code==200 and response.is_async and response['X-Accel-Buffering']=='no'
    assert 'no-store' in response['Cache-Control']
    async def receber():
        stream=response.streaming_content
        chunks=[await anext(stream) for _ in range(4)]
        await response._iterator.aclose()
        return b''.join(chunks).decode()
    text=asyncio.run(receber())
    assert text.count('event: messages')==3 and '"unread":1' in text and '"unread":0' in text


@pytest.mark.parametrize('papel',['aluno','professor','anonimo'])
@respx.mock
def test_rotas_mensagens_exclusivas_admin(settings,monkeypatch,papel):
    settings.ADMIN_EMAILS='admin@example.test';settings.URL_DE_ENTRADA='/entrar/google'
    monkeypatch.setenv('IDENTIDADE_API_URL','http://identidade:8000/interno');monkeypatch.setenv('IDENTIDADE_API_TOKEN','teste')
    respx.get('http://identidade:8000/interno/sessao/completa').mock(return_value=httpx.Response(200,json={'autenticado':papel!='anonimo','id':'outro','email':'outro@example.test','papel':papel}))
    client=Client(HTTP_COOKIE='meshcraft_sessao=teste');expected=302 if papel=='anonimo' else 404
    for name in ['feed_previa_mensagens','feed_previa_mensagens_stream','feed_previa_mensagens_conversa']:
        args=[uuid.uuid4()] if name.endswith('conversa') else []
        assert client.get(reverse(name,args=args)).status_code==expected
    for name in ['feed_previa_mensagens_iniciar','feed_previa_mensagens_enviar','feed_previa_mensagens_ler','feed_previa_mensagens_simular']:
        assert client.post(reverse(name),{}).status_code==expected
    assert Perfil.objects.count()==0


def test_equipe_e_pedidos_invalidos_nao_gravam_mensagens():
    perfil('a')
    for view,data in [(dm.lista,None),(dm.stream,None),(dm.iniciar,{}),(dm.enviar,{}),(dm.ler,{}),(dm.simular,{})]:
        r=req(data);r.admin['equipe_apenas']=True
        assert view(r).status_code==404
    c=iniciar()
    for text in ['', ' '*10, 'x'*4001, 42]:
        assert dm.enviar(req({'conversation':c,'text':text,'request_key':str(uuid.uuid4())})).status_code==400
    assert dm.enviar(req({'conversation':c,'text':'Oi','request_key':'invalid'})).status_code==400
    assert Mensagem.objects.count()==0


@respx.mock
def test_envio_exige_csrf(settings,monkeypatch):
    settings.ADMIN_EMAILS='admin@example.test'
    monkeypatch.setenv('IDENTIDADE_API_URL','http://identidade:8000/interno');monkeypatch.setenv('IDENTIDADE_API_TOKEN','teste')
    respx.get('http://identidade:8000/interno/sessao/completa').mock(return_value=httpx.Response(200,json={'autenticado':True,'id':'a','email':'admin@example.test','papel':'admin'}))
    client=Client(enforce_csrf_checks=True,HTTP_COOKIE='meshcraft_sessao=teste')
    assert client.post(reverse('feed_previa_mensagens_enviar'),{},content_type='application/json').status_code==403
    assert Mensagem.objects.count()==0
