import asyncio
import json
import uuid

import httpx
import pytest
import respx
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.core import feed_previa_social as social
from apps.feed_previa import notificacoes as avisos
from apps.feed_previa.models import FeedPreviaNotificacao, FeedPreviaPerfil, FeedPreviaPost

pytestmark = pytest.mark.django_db


def req(data=None, admin='a', host='testserver'):
    r = RequestFactory().get('/', HTTP_HOST=host) if data is None else RequestFactory().post('/', data=json.dumps(data), content_type='application/json', HTTP_HOST=host)
    r.admin = {'id': admin, 'nome': 'Admin '+admin}
    return r


def perfil(admin, host='testserver'):
    r = social.dados(req(admin=admin, host=host))
    assert r.status_code == 200
    return social.contexto(req(admin=admin, host=host))[1]


def acao(d, admin='a', host='testserver'):
    r = social.acao(req(d, admin, host))
    assert r.status_code == 200, r.content
    return r


def test_eventos_reais_quatro_tipos_sem_avisos_para_si_mesmo():
    a, b, c = perfil('a'), perfil('b'), perfil('c')
    post = FeedPreviaPost.objects.create(site_host='testserver', chave='de-b', autor=b, categoria='creation', titulo='A espada de B', texto='Estudo de malha.')
    acao({'op':'like','post':post.chave,'active':True})
    acao({'op':'follow','profile':b.chave,'active':True})
    acao({'op':'comment','post':post.chave,'text':'O contraste ficou legível. @'+c.handle, 'request_key':str(uuid.uuid4())})
    assert set(FeedPreviaNotificacao.objects.filter(destinatario=b).values_list('tipo',flat=True)) == {'like','follow','comment'}
    assert list(FeedPreviaNotificacao.objects.filter(destinatario=c).values_list('tipo',flat=True)) == ['mention']
    assert not FeedPreviaNotificacao.objects.filter(destinatario=a).exists()
    acao({'op':'like','post':post.chave,'active':True},'b')
    acao({'op':'comment','post':post.chave,'text':'@'+b.handle+' Minha própria observação.', 'request_key':str(uuid.uuid4())},'b')
    assert FeedPreviaNotificacao.objects.count() == 4
    item = avisos.retrato(c)['items'][0]
    assert item['kind']=='mention' and item['post']=='de-b' and item['excerpt'].startswith('O contraste')


def test_repeticao_e_mencao_ao_autor_nao_duplicam_aviso():
    a,b=perfil('a'),perfil('b')
    post=FeedPreviaPost.objects.create(site_host='testserver',chave='de-b',autor=b,categoria='creation',titulo='Criação',texto='Estudo')
    like={'op':'like','post':post.chave,'active':True}
    follow={'op':'follow','profile':b.chave,'active':True}
    comment={'op':'comment','post':post.chave,'text':'👏 @'+b.handle+' Gostei da silhueta.','request_key':str(uuid.uuid4())}
    for data in [like,follow,comment]:
        acao(data);acao(data)
    assert list(FeedPreviaNotificacao.objects.order_by('pk').values_list('tipo',flat=True)) == ['like','follow','mention']
    acao({**like,'active':False});acao({**follow,'active':False})
    assert FeedPreviaNotificacao.objects.count()==3
    acao(like);acao(follow)
    assert FeedPreviaNotificacao.objects.count()==5


def test_notificacoes_privadas_e_leitura_persistida_sem_apagar():
    a,b=perfil('a'),perfil('b')
    avisos.emitir(b,a,'follow','teste-follow')
    assert json.loads(avisos.lista(req()).content)['items']==[]
    data=json.loads(avisos.lista(req(admin='b')).content)
    n=data['items'][0]
    assert data['unread']==1
    avisos.ler(req({'id':n['id']}))
    assert FeedPreviaNotificacao.objects.get().lida_em is None
    assert json.loads(avisos.ler(req({'id':n['id']},'b')).content)['unread']==0
    assert json.loads(avisos.lista(req(admin='b')).content)['items'][0]['read']
    assert FeedPreviaNotificacao.objects.count()==1
    assert json.loads(avisos.lista(req(admin='b',host='outro.test')).content)['items']==[]


def test_marcar_todas_preserva_notificacao_mais_nova():
    a,b=perfil('a'),perfil('b')
    avisos.emitir(b,a,'follow','primeira')
    corte=avisos.retrato(b)['latest']
    avisos.emitir(b,a,'follow','segunda')
    resposta=json.loads(avisos.ler(req({'before':corte},'b')).content)
    assert resposta['unread']==1
    assert FeedPreviaNotificacao.objects.count()==2


def test_simulacao_identificada_sem_fabricar_interacao_ou_duplicar():
    perfil('a');perfil('b')
    for tipo in avisos.TIPOS:
        data={'kind':tipo,'request_key':str(uuid.uuid4())}
        assert avisos.simular(req(data)).status_code==200
        assert avisos.simular(req(data)).status_code==200
    snapshot=avisos.retrato(social.contexto(req())[1])
    assert snapshot['unread']==4 and all(n['demo'] for n in snapshot['items'])
    assert all(n['post'] is None for n in snapshot['items'])
    assert not json.loads(social.dados(req()).content)['state']['follows']
    assert json.loads(avisos.lista(req(admin='b')).content)['unread']==0


def test_nao_emite_entre_sites():
    a=perfil('a');b=perfil('b',host='outro.test')
    with pytest.raises(ValueError):
        avisos.emitir(b,a,'follow','invalida')
    assert FeedPreviaNotificacao.objects.count()==0


def test_stream_assincrono_entrega_mudanca_e_leitura(monkeypatch):
    eu=perfil('a')
    states=iter([{'items':[],'unread':0,'latest':0}, {'items':[{'id':1,'read':False}],'unread':1,'latest':1}, {'items':[{'id':1,'read':True}],'unread':0,'latest':1}])
    monkeypatch.setattr(avisos,'pulso',lambda p:next(states))
    async def sem_espera(*args):
        return None
    monkeypatch.setattr(avisos.asyncio,'sleep',sem_espera)
    response=avisos.stream(req())
    assert response.status_code==200 and response.is_async
    assert response['X-Accel-Buffering']=='no' and 'no-store' in response['Cache-Control']
    async def receber():
        stream=response.streaming_content
        chunks=[await anext(stream) for _ in range(4)]
        await response._iterator.aclose()
        return b''.join(chunks).decode()
    text=asyncio.run(receber())
    assert 'retry: 2000' in text and text.count('event: notifications')==3
    assert '"unread":1' in text and '"read":true' in text


@pytest.mark.parametrize('papel',['aluno','professor','anonimo'])
@respx.mock
def test_rotas_notificacoes_exclusivas_admin(settings,monkeypatch,papel):
    settings.ADMIN_EMAILS='admin@example.test';settings.URL_DE_ENTRADA='/entrar/google'
    monkeypatch.setenv('IDENTIDADE_API_URL','http://identidade:8000/interno');monkeypatch.setenv('IDENTIDADE_API_TOKEN','teste')
    respx.get('http://identidade:8000/interno/sessao/completa').mock(return_value=httpx.Response(200,json={'autenticado':papel!='anonimo','id':'outro','email':'outro@example.test','papel':papel}))
    client=Client(HTTP_COOKIE='meshcraft_sessao=teste')
    esperado=302 if papel=='anonimo' else 404
    for name in ['feed_previa_notificacoes','feed_previa_notificacoes_stream']:
        assert client.get(reverse(name)).status_code==esperado
    for name in ['feed_previa_notificacoes_ler','feed_previa_notificacoes_simular']:
        assert client.post(reverse(name),{}).status_code==esperado
    assert FeedPreviaPerfil.objects.count()==0


def test_equipe_e_pedidos_invalidos_nao_criam_avisos():
    for view,data in [(avisos.lista,None),(avisos.stream,None),(avisos.ler,{}),(avisos.simular,{})]:
        r=req(data);r.admin['equipe_apenas']=True
        assert view(r).status_code==404
    perfil('a')
    assert avisos.simular(req({'kind':'other','request_key':str(uuid.uuid4())})).status_code==400
    assert avisos.ler(req({'id':True})).status_code==400
    assert FeedPreviaNotificacao.objects.count()==0
