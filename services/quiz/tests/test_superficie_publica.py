"""A SUPERFÍCIE PÚBLICA do Crivo: onde o formulário mora, e quem pode postar
nele.

Os dois assuntos moram no mesmo arquivo porque são a mesma coisa vista de fora:
o que a internet enxerga do formulário desta célula. Nenhum dos dois aparece
pelo caminho interno, que é onde todo o resto da suíte mede — e foi exatamente
por isso que os dois defeitos abaixo viveram meses sem nada reclamar.

1. O ENDEREÇO. Até este PR o urlconf escrevia o prefixo por dentro
   (`path("quiz/<slug>/")`) e a célula subia com `SCRIPT_NAME=/quiz`. O handler
   ASGI do Django REMOVE o `SCRIPT_NAME` do `path_info` antes de casar rotas —
   lido em `django/core/handlers/asgi.py` do 5.1.4 desta célula:

       self.script_name = get_script_prefix(scope)   # FORCE_SCRIPT_NAME
       self.path_info = scope["path"].removeprefix(self.script_name)

   Resultado: o único endereço que existia de verdade era o DOBRADO,
   `/quiz/quiz/<slug>/`, e `/quiz/<slug>/` (o que qualquer pessoa escreveria, e
   o único que faz sentido divulgar) respondia 404. Medindo só o caminho
   interno, os dois lados do erro se cancelam e a suíte fica verde.

2. O CSRF. `formulario.html` sempre emitiu `{% csrf_token %}`, mas
   `settings.MIDDLEWARE` não tinha `CsrfViewMiddleware`: o token era decoração.
   Um formulário hospedado em qualquer domínio conseguia postar em
   `https://<site>/quiz/<slug>/` e gravar `Submission` com e-mail e telefone
   escolhidos por quem publicou o formulário, disparando `quiz.completado.v1`
   por lead que nunca existiu.

POR QUE `set_script_prefix` APARECE AQUI (armadilhas/081)
---------------------------------------------------------
`reverse()` não lê `settings.FORCE_SCRIPT_NAME`: ele lê um prefixo de variável
de THREAD que só o servidor preenche (`WSGIHandler.__call__` e
`ASGIHandler.__call__` chamam `set_script_prefix`; o handler de teste do Django
não chama). Sem emular isso, o `Location` do POST apareceria aqui sem o prefixo
e o teste diria que está tudo bem com um endereço que produção não usa. O
prefixo é de thread e VAZA entre testes, daí a limpeza no fim da fixture.

O QUE É NECESSÁRIO ATRÁS DO TRAEFIK, E O QUE NÃO É
---------------------------------------------------
`CSRF_TRUSTED_ORIGINS` **não** é necessário: ele serve para aceitar origens
DIFERENTES do host da requisição, e aqui o formulário e o POST são sempre do
mesmo host (Lei 9: um deploy, N domínios, cada um falando consigo mesmo).

`SECURE_PROXY_SSL_HEADER` **é**, e sem ele nenhum POST legítimo passaria em
produção. O TLS termina no Traefik e o uvicorn recebe `http`; o navegador manda
`Origin: https://<site>`; o Django compara a origem com
`"%s://%s" % (request.scheme, request.get_host())` e, sem o header, monta
`http://<site>`, diferente por uma letra: 403 em todo envio honesto. É a mesma
linha que as outras nove células com CSRF desta casa já têm, e não custa
variável de ambiente nenhuma (o Traefik sempre emite `X-Forwarded-Proto`).
"""

import uuid

import pytest
from django.test import Client
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.quiz.models import Option, Question, Quiz, ResultBand, Site, Submission

HOST = "quiz-publico.exemplo.com"
PREFIXO = "/quiz"

pytestmark = pytest.mark.django_db


@pytest.fixture
def env_de_producao(settings):
    """O que o `/opt/plataforma/env/quiz.env` da VPS faz, e o que o servidor
    faz por cima disso."""
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


@pytest.fixture
def navegador():
    """O cliente que se comporta como navegador de verdade.

    O `client` padrão do pytest-django nasce com `enforce_csrf_checks=False`:
    ele ignora o middleware de propósito, para que a suíte de negócio não
    precise carregar token. Um teste de CSRF escrito com ele passaria com o
    middleware DESLIGADO, que é exatamente o estado que este arquivo denuncia.
    """
    return Client(enforce_csrf_checks=True)


@pytest.fixture
def quiz_a(db):
    site = Site.objects.create(id="site-publico", host=HOST, name="Site Público")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    pergunta = Question.objects.create(quiz=quiz, order=1, text="Pergunta 1")
    Option.objects.create(question=pergunta, order=1, text="Zero", points=0)
    Option.objects.create(question=pergunta, order=2, text="Dez", points=10)
    ResultBand.objects.create(
        quiz=quiz, key="alto", title="Alto", min_score=0, max_score=10
    )
    return quiz


def _resposta_do_quiz(quiz):
    pergunta = quiz.questions.get(order=1)
    return {
        f"pergunta_{pergunta.id}": pergunta.options.get(points=10).id,
        "email": "lead@exemplo.com",
        "nome": "Lead",
        "telefone": "11999999999",
    }


# ---------------------------------------------------------------------------
# 1. O endereço que se divulga
# ---------------------------------------------------------------------------


def test_o_formulario_abre_no_endereco_que_se_divulga(client, quiz_a, env_de_producao):
    """`https://<site>/quiz/crivo/` abre o formulário.

    O caminho passado ao cliente de teste é o INTERNO (é isso que o handler
    entrega ao resolver depois de cortar o prefixo); `request.path` é o endereço
    público, e é ele que este teste afirma.
    """
    resposta = client.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST)

    assert resposta.wsgi_request.path == f"{PREFIXO}/{quiz_a.slug}/"
    assert resposta.wsgi_request.path_info == f"/{quiz_a.slug}/"
    assert resposta.status_code == 200, resposta.content
    assert b"Pergunta 1" in resposta.content


def test_o_endereco_dobrado_deixou_de_existir(client, quiz_a, env_de_producao):
    """`/quiz/quiz/crivo/` era o ÚNICO endereço que funcionava. Ele não pode
    voltar por descuido: um `quiz/` reposto no urlconf faz este teste passar de
    404 para 200, e o de cima cair junto."""
    resposta = client.get(f"{PREFIXO}/{quiz_a.slug}/", HTTP_HOST=HOST)

    assert resposta.wsgi_request.path == f"{PREFIXO}{PREFIXO}/{quiz_a.slug}/"
    assert resposta.status_code == 404


def test_o_redirect_do_post_manda_o_navegador_para_o_endereco_publico(
    client, quiz_a, env_de_producao
):
    """A jornada inteira só fecha se o `Location` carregar o prefixo: sem ele o
    navegador vai a `/crivo/resultado`, que no host público não é rota de
    ninguém."""
    envio = client.post(f"/{quiz_a.slug}/", _resposta_do_quiz(quiz_a), HTTP_HOST=HOST)

    assert envio.status_code == 302
    caminho, _, query = envio["Location"].partition("?")
    assert caminho == f"{PREFIXO}/{quiz_a.slug}/resultado"
    chave, _, valor = query.partition("=")
    assert chave == "lead"
    uuid.UUID(valor)  # o `lead` é a identidade da submissão, não enfeite


def test_reverse_das_duas_paginas_carrega_o_prefixo(quiz_a, env_de_producao):
    """O que os templates e o `redirect()` das views usam."""
    assert reverse("quiz-formulario", args=[quiz_a.slug]) == f"{PREFIXO}/crivo/"
    assert reverse("quiz-resultado", args=[quiz_a.slug]) == f"{PREFIXO}/crivo/resultado"


def test_a_sonda_continua_respondendo_no_endereco_do_gateway(client, env_de_producao):
    """O urlconf novo não pode ter roubado `/healthz` para o curinga da página:
    a rota exata vem antes, e o `path_info` chega sem prefixo."""
    resposta = client.get("/healthz")

    assert resposta.wsgi_request.path == f"{PREFIXO}/healthz"
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. Quem pode postar no formulário
# ---------------------------------------------------------------------------


def test_post_sem_token_e_recusado_e_nao_grava_lead(navegador, quiz_a):
    """O guarda. Sem `CsrfViewMiddleware` isto responde 302 e grava a submissão:
    é assim que o vermelho aparece."""
    resposta = navegador.post(
        f"/{quiz_a.slug}/", _resposta_do_quiz(quiz_a), HTTP_HOST=HOST
    )

    assert resposta.status_code == 403, (
        "POST sem token de CSRF foi aceito: qualquer página da internet pode "
        "gravar leads neste funil"
    )
    assert Submission.objects.count() == 0


def test_post_com_origem_de_outro_site_e_recusado(navegador, quiz_a):
    """A forma como o ataque chega de verdade: um formulário publicado em outro
    domínio, com o cookie e o token da vítima já no lugar."""
    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST)
    token = navegador.cookies["quiz_csrf"].value

    resposta = navegador.post(
        f"/{quiz_a.slug}/",
        {**_resposta_do_quiz(quiz_a), "csrfmiddlewaretoken": token},
        HTTP_HOST=HOST,
        HTTP_ORIGIN="https://site-do-atacante.exemplo.com",
    )

    assert resposta.status_code == 403
    assert Submission.objects.count() == 0


def test_o_fluxo_normal_do_navegador_continua_passando(navegador, quiz_a):
    """O outro lado da moeda: proteção que quebra o caminho honesto é pior que
    proteção nenhuma, porque ninguém se inscreve e ninguém percebe."""
    formulario = navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST)
    assert formulario.status_code == 200
    token = navegador.cookies["quiz_csrf"].value

    resposta = navegador.post(
        f"/{quiz_a.slug}/",
        {**_resposta_do_quiz(quiz_a), "csrfmiddlewaretoken": token},
        HTTP_HOST=HOST,
    )

    assert resposta.status_code == 302, resposta.content
    assert Submission.objects.get().lead_email == "lead@exemplo.com"


def test_https_atras_do_traefik_aceita_a_origem_do_proprio_site(navegador, quiz_a):
    """O cenário de PRODUÇÃO, e o motivo de `SECURE_PROXY_SSL_HEADER` existir.

    Em produção a requisição chega ao uvicorn em http, com
    `X-Forwarded-Proto: https`, e o navegador manda `Origin: https://<site>`.
    Sem o header declarado no settings, o Django monta `http://<site>` para
    comparar e recusa TODO envio legítimo com 403. Aqui isso é medido, não
    confiado: comente a linha do settings e este teste fica vermelho.
    """
    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST, HTTP_X_FORWARDED_PROTO="https")
    token = navegador.cookies["quiz_csrf"].value

    resposta = navegador.post(
        f"/{quiz_a.slug}/",
        {**_resposta_do_quiz(quiz_a), "csrfmiddlewaretoken": token},
        HTTP_HOST=HOST,
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN=f"https://{HOST}",
    )

    assert resposta.status_code == 302, (
        "o POST honesto de produção foi recusado: sem SECURE_PROXY_SSL_HEADER o "
        "Django compara a origem https do navegador com um http inventado"
    )
    assert Submission.objects.count() == 1


def test_o_cookie_de_csrf_tem_nome_e_alcance_desta_celula(
    navegador, quiz_a, env_de_producao, settings
):
    """Um `csrftoken` genérico colide com o das outras células no MESMO domínio
    (Lei 9: um host, N células sob prefixos). E o alcance é o prefixo da célula:
    o token protege os formulários que moram aqui, não o site inteiro."""
    settings.CSRF_COOKIE_PATH = PREFIXO

    navegador.get(f"/{quiz_a.slug}/", HTTP_HOST=HOST)

    assert navegador.cookies["quiz_csrf"]["path"] == PREFIXO
