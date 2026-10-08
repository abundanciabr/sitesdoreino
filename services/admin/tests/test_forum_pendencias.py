from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse

from apps.core.forum_pendencias import forum_pendencias
from apps.core.moldura import secoes_do_menu


def request(**params):
    req = RequestFactory().get(reverse("forum_pendencias"), params)
    req.admin = {"id": "admin-teste", "nome": "Admin", "equipe_apenas": False}
    return req


def test_pagina_preserva_filtros_links_e_datas(monkeypatch):
    monkeypatch.setenv("FORUM_API_URL", "http://forum:8000/interno")
    monkeypatch.setenv("TOKEN_FORUM", "token-teste")
    dados = {"abertas": 51, "sem_resposta": 50, "respondidas": 1, "areas": [], "total": 51,
             "pagina": 1, "paginas": 2, "itens": [{"id": 12, "titulo": "Preciso de ajuda", "autor": "Aluno",
             "area": "Dúvidas", "area_slug": "duvidas", "criado_em": "2026-10-01T12:00:00+00:00", "respostas": 0}]}
    with patch("apps.core.forum_pendencias.httpx.get", return_value=httpx.Response(200, json=dados, request=httpx.Request("GET", "http://forum:8000"))) as chamada:
        resposta = forum_pendencias(request(filtro="sem-resposta", q="Aluno"))
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert '/forum/t/12#texto' in corpo and 'Preciso de ajuda' in corpo
    assert '01/10/2026' in corpo and 'pagina=2' in corpo and 'q=Aluno' in corpo
    assert chamada.call_args.kwargs["params"]["filtro"] == "sem-resposta"
    assert any(i["rotulo"] == "Questões do fórum" for i in secoes_do_menu("/forum/pendencias/"))


def test_fonte_indisponivel_nao_parece_fila_vazia(monkeypatch):
    monkeypatch.delenv("FORUM_API_URL", raising=False)
    resposta = forum_pendencias(request())
    assert resposta.status_code == 503
    assert 'Não foi possível consultar' in resposta.content.decode()
    assert 'Nenhuma questão encontrada' not in resposta.content.decode()


def test_nao_abre_para_equipe_ou_visitante():
    req = request()
    req.admin = {"equipe_apenas": True}
    with pytest.raises(Http404):
        forum_pendencias(req)
    req.admin = None
    with pytest.raises(Http404):
        forum_pendencias(req)
