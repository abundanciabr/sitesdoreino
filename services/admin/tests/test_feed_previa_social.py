import io
import json
import uuid

import httpx
import pytest
import respx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory
from django.urls import reverse
from PIL import Image

from apps.core import feed_previa_social as social
from apps.feed_previa.models import (FeedPreviaArquivo, FeedPreviaComentario,
    FeedPreviaInteracao, FeedPreviaPerfil, FeedPreviaPost)

pytestmark = pytest.mark.django_db


def req(method='get', data=None, admin='admin-1', host='testserver'):
    factory = RequestFactory()
    r = factory.get('/', HTTP_HOST=host) if method == 'get' else factory.post('/', data=json.dumps(data), content_type='application/json', HTTP_HOST=host)
    r.admin = {'id': admin, 'nome': 'Admin de teste'}
    return r


def load(admin='admin-1', host='testserver'):
    r = social.dados(req(admin=admin, host=host))
    assert r.status_code == 200
    return json.loads(r.content)


def action(data, admin='admin-1', host='testserver'):
    r = social.acao(req('post', data, admin, host))
    assert r.status_code == 200, r.content
    return json.loads(r.content)


def post(data, files=None, admin='admin-1', host='testserver'):
    r = RequestFactory().post('/', {'data': json.dumps(data), **(files or {})}, HTTP_HOST=host)
    r.admin = {'id': admin, 'nome': 'Admin de teste'}
    return social.publicar(r)


def creation(**extra):
    return {'kind': 'creation', 'title': 'Minha criação', 'story': 'Estudo da silhueta.', 'request_key': str(uuid.uuid4()), **extra}


def test_ciclo_persistido_e_colecao_pessoal():
    initial = load()
    assert len(initial['state']['posts']) == 6
    assert [p['id'] for p in initial['state']['posts']] == ['sword','first','before','ugc','world','help']
    action({'op': 'follow', 'profile': 'nina', 'active': True})
    action({'op': 'like', 'post': 'before', 'active': True})
    action({'op': 'save', 'post': 'before', 'active': True})
    views = action({'op': 'view', 'posts': ['before', 'before']})
    assert views['views'] == {'before': 1}
    assert action({'op': 'view', 'posts': ['before']})['views']['before'] == 1
    again = load()['state']
    assert again['saved'] == ['before'] and again['follows'] == ['nina']
    assert next(p for p in again['posts'] if p['id'] == 'before')['likes'] == 74
    other = load('admin-2')
    assert other['state']['saved'] == [] and other['state']['follows'] == []
    assert next(p for p in other['people'] if p['id'] == 'nina')['followers'] == 1
    assert action({'op': 'view', 'posts': ['before']}, 'admin-2')['views']['before'] == 2
    action({'op': 'save', 'post': 'before', 'active': False})
    action({'op': 'follow', 'profile': 'nina', 'active': False})
    assert load()['state']['saved'] == []
    assert FeedPreviaInteracao.objects.filter(tipo='save', ativa=False).exists()
    assert FeedPreviaInteracao.objects.filter(tipo='follow', ativa=False).exists()


def test_comentario_mencoes_e_reenvio_sem_duplicar():
    load()
    data = {'op': 'comment', 'post': 'sword', 'text': '👏 @nina-souza Gostei do contraste. @inexistente', 'request_key': str(uuid.uuid4()), 'author': 'nina', 'xp': 999}
    action(data)
    action(data)
    c = FeedPreviaComentario.objects.get()
    assert c.mencoes == ['nina-souza']
    assert c.autor.demonstracao is False
    assert len(next(p for p in load()['state']['posts'] if p['id'] == 'sword')['comments']) == 2
    data['text'] = 'Outro comentário'
    assert social.acao(req('post', data)).status_code == 400
    assert FeedPreviaComentario.objects.count() == 1


def test_publicacao_anexo_privado_persistente_e_reenvio():
    load()
    buf = io.BytesIO()
    Image.new('RGB', (12, 12), 'blue').save(buf, format='PNG')
    payload = creation(author='nina', xp=999)
    r = post(payload, {'images': SimpleUploadedFile('modelo.png', buf.getvalue(), content_type='image/png')})
    assert r.status_code == 200, r.content
    identifier = json.loads(r.content)['published']
    assert post(payload).status_code == 200
    p = FeedPreviaPost.objects.get(chave=identifier)
    assert p.autor.demonstracao is False
    assert FeedPreviaArquivo.objects.count() == 1
    f = FeedPreviaArquivo.objects.get()
    assert social.arquivo(req(), f.pk).content == buf.getvalue()
    assert social.arquivo(req(host='outro.test'), f.pk).status_code == 404
    assert next(p for p in load()['state']['posts'] if p['id'] == identifier)['images']


def test_imagem_invalida_nao_deixa_publicacao_parcial():
    load()
    count = FeedPreviaPost.objects.count()
    r = post(creation(), {'images': SimpleUploadedFile('x.png', b'invalido', content_type='image/png')})
    assert r.status_code == 400
    assert FeedPreviaPost.objects.count() == count
    assert FeedPreviaArquivo.objects.count() == 0


def test_isolamento_por_site_e_preferencias():
    load()
    payload = creation()
    identifier = json.loads(post(payload).content)['published']
    assert all(p['id'] != identifier for p in load(host='outro.test')['state']['posts'])
    assert social.acao(req('post', {'op': 'save', 'post': identifier, 'active': True}, host='outro.test')).status_code == 400
    action({'op': 'proposal', 'level': 2})
    action({'op': 'application', 'job': 'props', 'story': 'Meu portfólio de props.'})
    assert load()['state']['proposal'] == 2
    assert load()['state']['applicationStories']['props'] == 'Meu portfólio de props.'
    assert load('admin-2')['state']['proposal'] == 0


@pytest.mark.parametrize('op,data', [('follow', {'profile':'nina','active':'sim'}), ('save',{'post':'sword','active':1}), ('comment',{'post':'sword','text':'a'*2401,'request_key':str(uuid.uuid4())}), ('proposal',{'level':99}), ('unknown',{})])
def test_pedidos_invalidos(op, data):
    load()
    assert social.acao(req('post', {'op':op, **data})).status_code == 400


@pytest.mark.parametrize('papel', ['aluno','professor','anonimo'])
@respx.mock
def test_api_exclusiva_admin(settings, monkeypatch, papel):
    settings.ADMIN_EMAILS = 'admin@example.test'
    settings.URL_DE_ENTRADA = '/entrar/google'
    monkeypatch.setenv('IDENTIDADE_API_URL', 'http://identidade:8000/interno')
    monkeypatch.setenv('IDENTIDADE_API_TOKEN', 'teste')
    respx.get('http://identidade:8000/interno/sessao/completa').mock(return_value=httpx.Response(200, json={'autenticado':papel!='anonimo', 'id':'outro','email':'outro@example.test','papel':papel}))
    c = Client(HTTP_COOKIE='meshcraft_sessao=teste')
    for name, args in [('feed_previa_dados', []), ('feed_previa_arquivo', [uuid.uuid4()])]:
        assert c.get(reverse(name,args=args)).status_code == (302 if papel=='anonimo' else 404)
    for name in ['feed_previa_acao','feed_previa_publicar']:
        assert c.post(reverse(name),{}).status_code == (302 if papel=='anonimo' else 404)
    assert FeedPreviaPerfil.objects.count() == 0


def test_equipe_e_csrf_bloqueados(settings, monkeypatch):
    r=req();r.admin['equipe_apenas']=True
    assert social.dados(r).status_code == 404
    r=req('post',{'op':'view','posts':[]});r.admin['equipe_apenas']=True
    assert social.acao(r).status_code == 404
    with respx.mock:
        settings.ADMIN_EMAILS='admin@example.test'
        monkeypatch.setenv('IDENTIDADE_API_URL','http://identidade:8000/interno')
        monkeypatch.setenv('IDENTIDADE_API_TOKEN','teste')
        respx.get('http://identidade:8000/interno/sessao/completa').mock(return_value=httpx.Response(200,json={'autenticado':True,'id':'admin','nome_exibido':'Admin','email':'admin@example.test','papel':'admin'}))
        c=Client(enforce_csrf_checks=True)
        c.cookies['meshcraft_sessao']='teste'
        assert c.post(reverse('feed_previa_acao'),{},content_type='application/json').status_code == 403
        page=c.get(reverse('feed_previa'))
        assert page.status_code == 200
        token=c.cookies[settings.CSRF_COOKIE_NAME].value
        assert c.post(reverse('feed_previa_acao'),json.dumps({'op':'view','posts':[]}),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code == 200
