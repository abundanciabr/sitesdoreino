"""Somente a abertura da pesquisa e seu vínculo com a matrícula; sem responder."""
import httpx
import pytest
from django.urls import reverse
from apps.cursos.models import Curso
from tests.conftest import ANA, COOKIE, SITE, PRODUTO_DO_CURSO, PRODUTO_DE_OUTRO_CURSO, dublar_sessao, dublar_matricula, url_das_matriculas

pytestmark = pytest.mark.django_db


def outro_curso(site=SITE):
    return Curso.objects.create(site_id=site, slug="outro-curso", nome="Outro curso", produto_id=PRODUTO_DE_OUTRO_CURSO)


def sem_chamadas_pesquisa(rede):
    assert not any("/nps/" in str(call.request.url) for call in rede.calls)


def test_abre_inicial_apenas_do_curso_matriculado(client, aluna, esqueleto, rede):
    outro = outro_curso()
    resposta = client.get(reverse("satisfacao-curso", args=[esqueleto.slug]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "Começar avaliação" in texto
    assert "Prévia interativa" not in texto
    assert "Ver pesquisas dos cursos" not in texto
    assert client.get(reverse("satisfacao-curso", args=[outro.slug]), HTTP_COOKIE=COOKIE).status_code == 404
    sem_chamadas_pesquisa(rede)


def test_duas_matriculas_abrem_as_duas_iniciais(client, env_dos_pares, esqueleto, rede):
    outro = outro_curso()
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], produtos=[PRODUTO_DO_CURSO, PRODUTO_DE_OUTRO_CURSO])
    lista = client.get(reverse("satisfacao"), HTTP_COOKIE=COOKIE)
    assert lista.status_code == 200
    for curso in (esqueleto, outro):
        url = reverse("satisfacao-curso", args=[curso.slug])
        assert url in lista.content.decode()
        resposta = client.get(url, HTTP_COOKIE=COOKIE)
        assert resposta.status_code == 200 and "Começar avaliação" in resposta.content.decode()
    sem_chamadas_pesquisa(rede)


def test_matricula_de_outro_site_nao_abre_pesquisa(client, env_dos_pares, esqueleto, rede):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], site="outra-escola")
    assert client.get(reverse("satisfacao-curso", args=[esqueleto.slug]), HTTP_COOKIE=COOKIE).status_code == 404
    sem_chamadas_pesquisa(rede)


@pytest.mark.parametrize("categoria", ["cadastrado", "na_fila", "pausado", "reembolsado", "ex_aluno"])
def test_sem_matricula_ativa_nao_abre_inicial(client, env_dos_pares, esqueleto, rede, categoria):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], categoria)
    assert client.get(reverse("satisfacao-curso", args=[esqueleto.slug]), HTTP_COOKIE=COOKIE).status_code == 403
    sem_chamadas_pesquisa(rede)


def test_visitante_recebe_entrada_sem_criar_pesquisa(client, esqueleto, rede):
    resposta = client.get(reverse("satisfacao-curso", args=[esqueleto.slug]))
    assert resposta.status_code == 200 and "Entrar com meu cadastro" in resposta.content.decode()
    sem_chamadas_pesquisa(rede)


def test_falha_da_matricula_nao_libera_outro_curso(client, env_dos_pares, esqueleto, rede):
    dublar_sessao(rede, ANA)
    rede.get(url_das_matriculas(ANA["email"])).mock(return_value=httpx.Response(503))
    assert client.get(reverse("satisfacao-curso", args=[esqueleto.slug]), HTTP_COOKIE=COOKIE).status_code == 403
    sem_chamadas_pesquisa(rede)


def test_entrada_direta_no_catalogo_e_na_pagina_do_curso(client, aluna, esqueleto, rede):
    outro = outro_curso()
    propria = reverse("satisfacao-curso", args=[esqueleto.slug])
    alheia = reverse("satisfacao-curso", args=[outro.slug])
    catalogo = client.get(reverse("catalogo"), HTTP_COOKIE=COOKIE)
    assert 'href="' + propria + '">Avaliar este curso</a>' in catalogo.content.decode()
    assert alheia not in catalogo.content.decode()
    mapa = client.get(reverse("curso", args=[esqueleto.slug]), HTTP_COOKIE=COOKIE)
    assert mapa.status_code == 200
    assert 'href="' + propria + '">Avaliar este curso</a>' in mapa.content.decode()
    sem_chamadas_pesquisa(rede)


def test_sala_da_comunidade_sem_matricula_nao_ganha_link_de_pesquisa(client, aluna, rede):
    comunidade = Curso.objects.create(site_id=SITE, slug="comunidade", nome="Comunidade", produto_id="")
    url = reverse("satisfacao-curso", args=[comunidade.slug])
    catalogo = client.get(reverse("catalogo"), HTTP_COOKIE=COOKIE)
    assert catalogo.status_code == 200 and url not in catalogo.content.decode()
    mapa = client.get(reverse("curso", args=[comunidade.slug]), HTTP_COOKIE=COOKIE)
    assert mapa.status_code == 200 and url not in mapa.content.decode()
    assert client.get(url, HTTP_COOKIE=COOKIE).status_code == 404
    sem_chamadas_pesquisa(rede)
