"""Teste-guarda do H10.1 (ARMADILHAS §4.10): /healthz sob o env de produção.

Em produção o quiz sobe atrás do Traefik com SCRIPT_NAME=/quiz
(FORCE_SCRIPT_NAME) e o Traefik NÃO remove o prefixo: a borda pública chega
como GET /quiz/healthz. request.path vira "/quiz/healthz"; uma isenção do
middleware CONV-SITE escrita sobre request.path deixa de casar, a sonda cai
na resolução de site (Host sem cadastro ⇒ 404) — medido em 22/08/2026:
https://basileiatoutheou.org/quiz/healthz respondia 404 enquanto o
healthcheck interno (localhost:8000/healthz, sem prefixo) respondia 200.
A comparação correta é request.path_info, que segue "/healthz" independente
do prefixo do gateway. Mesma classe do bug corrigido no checkout (PR #65);
aqui a resolução de site é LOCAL (apps.quiz.models.Site, ver LICOES.md),
por isso o cenário usa o banco em vez de respx.
"""

import pytest


@pytest.fixture
def env_de_producao(settings):
    """O que o env real da VPS faz: SCRIPT_NAME=/quiz via FORCE_SCRIPT_NAME."""
    settings.FORCE_SCRIPT_NAME = "/quiz"


# django_db de propósito: no estado bugado o middleware consulta o cadastro
# local de Site — sem a marca, o vermelho seria um erro de acesso a banco em
# vez do 404 genuíno medido em produção.
@pytest.mark.django_db
def test_healthz_responde_200_com_force_script_name(client, env_de_producao):
    # Nenhum host cadastrado no Site local: se o middleware tentar resolver o
    # site (o bug), recebe 404 — exatamente o cenário da sonda do gateway, que
    # chega com um Host que não é de site.
    resp = client.get("/healthz")
    # Sanidade do cenário: sob FORCE_SCRIPT_NAME a requisição É a /quiz/healthz
    # do ponto de vista do Django (o path público, com prefixo).
    assert resp.wsgi_request.path == "/quiz/healthz"
    assert resp.wsgi_request.path_info == "/healthz"
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
def test_static_isento_do_conv_site_com_force_script_name(
    client, env_de_producao, django_assert_num_queries
):
    # A MESMA isenção cobre /static/ — se o middleware interceptar, haverá uma
    # query ao cadastro local de Site; aqui só provamos que a requisição NÃO
    # morre na resolução de site (zero queries).
    with django_assert_num_queries(0):
        client.get("/static/quiz/inexistente.js")
