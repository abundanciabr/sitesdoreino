import pytest
from django.test import Client
from django.urls import reverse
from apps.cursos.models import ComentarioDoEvento, Pessoa
from apps.core.comentarios_desafio import EVENTO
from tests.conftest import ANA, COOKIE, SITE, dublar_sessao, dublar_matricula

pytestmark = pytest.mark.django_db

@pytest.fixture
def conversa(client, env_dos_pares, rede):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    client.defaults["HTTP_COOKIE"] = COOKIE
    return client

def criar(autor=None, **kw):
    autor = autor or Pessoa.objects.create(id_da_plataforma="outro", nome_exibido="Outro Participante")
    return ComentarioDoEvento.objects.create(site_id=SITE, evento=EVENTO, autor=autor, corpo=kw.pop("corpo", "Expectativa real"), **kw)

def enviar(client, **dados):
    return client.post(reverse("comentar-desafio-roblox"), {"corpo": "Quero aprender a modelar!", **dados})

def test_publica_persiste_e_autoria_nao_pode_ser_falsificada(conversa):
    assert enviar(conversa, autor="outra-pessoa", equipe="true", oculto="true", site_id="outro-site").status_code == 302
    item=ComentarioDoEvento.objects.get()
    assert item.autor_id == ANA["id"] and item.site_id == SITE
    assert not item.equipe and not item.oculto
    html=Client().get(reverse("acesso-desafio-roblox")).content.decode()
    assert item.corpo in html and "Ana" in html and "Entrar para comentar" in html
    assert ANA["email"] not in html

def test_anonimo_nao_publica_e_formulario_exige_csrf(env_dos_pares, rede):
    dublar_sessao(rede, {"autenticado":False})
    assert enviar(Client()).status_code == 403
    assert enviar(Client(enforce_csrf_checks=True, HTTP_COOKIE=COOKIE)).status_code == 403
    assert not ComentarioDoEvento.objects.exists()

@pytest.mark.parametrize("texto", ["", "   ", "x"*4001])
def test_recusa_texto_invalido(conversa,texto):
    assert enviar(conversa,corpo=texto).status_code == 400
    assert not ComentarioDoEvento.objects.exists()

def test_resposta_aparece_no_comentario_certo(conversa):
    raiz=criar()
    assert enviar(conversa,resposta_a=raiz.pk,corpo="Também quero aprender!").status_code==302
    resposta=ComentarioDoEvento.objects.get(resposta_a=raiz)
    html=conversa.get(reverse("acesso-desafio-roblox")).content.decode()
    assert raiz.corpo in html and resposta.corpo in html and 'Comentários <span>2</span>' in html
    r=conversa.get(reverse("acesso-desafio-roblox"), {"responder":raiz.pk})
    assert 'Responder a Outro' in r.content.decode()

@pytest.mark.parametrize("tipo", ["outro_site","outro_evento","oculto","resposta"])
def test_nao_responde_alvo_invalido(conversa,tipo):
    raiz=criar()
    if tipo=="outro_site": raiz.site_id="outro-site"
    if tipo=="outro_evento": raiz.evento="outro-evento"
    if tipo=="oculto": raiz.oculto=True
    if tipo=="resposta": raiz=criar(autor=raiz.autor,resposta_a=raiz)
    raiz.save()
    antes=ComentarioDoEvento.objects.count()
    assert enviar(conversa,resposta_a=raiz.pk).status_code==404
    assert ComentarioDoEvento.objects.count()==antes

def test_privacidade_escaping_e_sem_cache(conversa):
    pessoa=Pessoa.objects.create(id_da_plataforma="email",nome_exibido="privado@example.com")
    criar(autor=pessoa,corpo='<script>alert("x")</script>')
    criar(autor=pessoa,oculto=True,corpo="texto oculto")
    fora=criar(autor=pessoa,corpo="outra escola")
    fora.site_id="outro-site"
    fora.save()
    r=conversa.get(reverse("acesso-desafio-roblox"))
    html=r.content.decode()
    assert "&lt;script&gt;" in html and '<script>alert(' not in html
    assert "texto oculto" not in html and "outra escola" not in html and "privado@example.com" not in html
    assert "no-store" in r["Cache-Control"] and "Cookie" in r["Vary"]

def test_admin_oculta_sem_apagar_e_aluno_nao_muda(conversa,monkeypatch):
    raiz=criar()
    criar(autor=raiz.autor,resposta_a=raiz,corpo="Resposta preservada")
    url=reverse("ocultar-comentario-desafio",args=[raiz.pk])
    assert conversa.post(url).status_code==403
    monkeypatch.setenv("ADMIN_EMAILS",ANA["email"])
    assert conversa.post(url).status_code==302
    assert ComentarioDoEvento.objects.count()==2
    raiz.refresh_from_db()
    assert raiz.oculto
    html=conversa.get(reverse("acesso-desafio-roblox")).content.decode()
    assert "Resposta preservada" not in html and raiz.corpo not in html and 'Comentários <span>0</span>' in html

def test_so_admin_ganha_identificacao_equipe(conversa,monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS",ANA["email"])
    assert enviar(conversa).status_code==302
    assert ComentarioDoEvento.objects.get().equipe

def test_paginacao_e_remocoes(conversa):
    pessoa=Pessoa.objects.create(id_da_plataforma="paginacao",nome_exibido="Pessoa")
    for i in range(21): criar(autor=pessoa,corpo=f"Mensagem {i}")
    r=conversa.get(reverse("acesso-desafio-roblox"),{"comentarios_pagina":"2"})
    assert len(r.context["comentarios"])==1 and r.context["total_comentarios"]==21
    html=r.content.decode()
    for controle in ('id="estrelas"','id="concluir"','class="pontos"','class="navegar"','id="fechar-lateral"','abrem em breve'):
        assert controle not in html


def test_resposta_em_conversa_antiga_volta_para_a_pagina_certa(conversa):
    raiz=criar()
    for i in range(20): criar(autor=raiz.autor,corpo=f"Mais recente {i}")
    r=enviar(conversa,resposta_a=raiz.pk,corpo="Resposta recente na conversa antiga")
    assert "comentarios_pagina=2" in r.url
    html=conversa.get(r.url).content.decode()
    assert "Resposta recente na conversa antiga" in html
