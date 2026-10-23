import httpx
import pytest
import respx
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory
from apps.core.primeiro_acesso import PrimeiroAcesso
POST_ORIGINAL = httpx.Client.post

@respx.mock
def test_pagina_real_cookie_opaco_e_falha_aberta(monkeypatch):
    monkeypatch.setattr(httpx.Client, 'post', POST_ORIGINAL)
    for k,v in {'ALUNOS_API_URL':'http://alunos.test','ALUNOS_API_TOKEN':'par','SITE_ID':'escola'}.items():monkeypatch.setenv(k,v)
    rota=respx.post('http://alunos.test/jornada-acesso/observar').respond(204)
    resposta=HttpResponse('pagina')
    req=RequestFactory().get('/pagina',HTTP_COOKIE='meshcraft_sessao=opaco')
    middleware=PrimeiroAcesso(lambda r:resposta)
    assert middleware(req) is resposta and rota.call_count==1
    assert rota.calls.last.request.headers['Cookie']=='meshcraft_sessao=opaco'
    assert 'apps.core.primeiro_acesso.PrimeiroAcesso' in settings.MIDDLEWARE
    rota.mock(side_effect=httpx.ReadTimeout('sintético'))
    assert middleware(req) is resposta

@pytest.mark.parametrize('metodo,status,tipo,cookie,headers',[
 ('HEAD',200,'text/html','meshcraft_sessao=x',{}),('POST',200,'text/html','meshcraft_sessao=x',{}),
 ('GET',404,'text/html','meshcraft_sessao=x',{}),('GET',302,'text/html','meshcraft_sessao=x',{}),
 ('GET',200,'application/json','meshcraft_sessao=x',{}),('GET',200,'text/html','',{}),
 ('GET',200,'text/html','meshcraft_sessao=x; meshcraft_ver_como=aluno',{}),
 ('GET',200,'text/html','meshcraft_sessao=x',{'HTTP_SEC_PURPOSE':'prefetch'}),
 ('GET',200,'text/html','meshcraft_sessao=x',{'HTTP_SEC_FETCH_DEST':'empty'})])
@respx.mock
def test_nao_conta_simulacao_recurso_erro_precarregamento(metodo,status,tipo,cookie,headers,monkeypatch):
    for k,v in {'ALUNOS_API_URL':'http://alunos.test','ALUNOS_API_TOKEN':'par','SITE_ID':'escola'}.items():monkeypatch.setenv(k,v)
    resposta=HttpResponse('',status=status,content_type=tipo)
    req=RequestFactory().generic(metodo,'/pagina',HTTP_COOKIE=cookie,**headers)
    assert PrimeiroAcesso(lambda r:resposta)(req) is resposta
    assert not respx.calls
