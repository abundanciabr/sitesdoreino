from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from django.urls import reverse

from tests.test_crm_satisfacao import entrar, ambiente, QUIZ
from tests.test_satisfacao_painel import avaliacao


@respx.mock
def test_lista_com_nota_zero_data_e_acesso_ao_historico():
    cliente = entrar()
    rota = respx.get(QUIZ + "/interno/nps/respondentes").mock(return_value=httpx.Response(200, json={
        "alunos": 1, "total": 1, "pagina": 1, "paginas": 2, "itens": [{
            "id": "pesquisa-1", "aluno_id": "aluno-1", "nome": "Ana Silva", "email": "ana@example.test",
            "curso": "Desenho", "concluida_em": "2026-10-08T15:00:00Z", "nota": 0, "retrato": "A conferir",
        }],
    }))
    item = avaliacao()
    item["resultado"]["nps"] = 0
    respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={"avaliacoes": [item], "atendimentos": []}))
    resposta = cliente.get(reverse("crm_satisfacao_respondentes"), {"site_id": "escola", "q": "Ana"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "Ana Silva" not in texto
    for trecho in ("Ana", "Desenho", "0/10", "08/10/2026 12:00", "O que ele respondeu", "1 aluno", "Próxima"):
        assert trecho in texto
    assert rota.calls.last.request.url.params["site_id"] == "escola"
    assert rota.calls.last.request.url.params["q"] == "Ana"
    assert parse_qs(urlsplit(resposta.context["itens"][0]["url"]).query)["aluno_id"] == ["aluno-1"]
    assert 'name="q"' in texto


@respx.mock
def test_vazio_e_indisponibilidade_sao_distintos():
    cliente = entrar()
    rota = respx.get(QUIZ + "/interno/nps/respondentes")
    rota.mock(return_value=httpx.Response(200, json={"alunos": 0, "total": 0, "pagina": 1, "paginas": 1, "itens": []}))
    url = reverse("crm_satisfacao_respondentes")
    assert "Nenhum aluno concluiu" in cliente.get(url, {"site_id": "escola"}).content.decode()
    rota.mock(return_value=httpx.Response(503))
    texto = cliente.get(url, {"site_id": "escola"}).content.decode()
    assert "Não foi possível consultar" in texto and "Nenhum aluno concluiu" not in texto


@respx.mock
def test_lista_requer_administrador():
    from django.test import Client
    url = reverse("crm_satisfacao_respondentes")
    assert Client().get(url).status_code in (302, 404)
    assert entrar("aluno@example.test").get(url).status_code == 404
