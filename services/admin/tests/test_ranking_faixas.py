from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.http import Http404
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.core import ranking_faixas as tela


def matricula(nome, numero, **extras):
    return dict(id=str(numero), site_id="meshcraft.top", email=f"a{numero}@example.test",
                nome_completo=nome, status="ativa", **extras)


def pedido(query="", admin=None):
    r = RequestFactory().get("/escola/ranking-faixas/" + query)
    r.admin = {"id": "admin"} if admin is None else admin
    return r


@pytest.fixture(autouse=True)
def limpar_cache():
    cache.clear()


def test_ordem_graus_empate_matriculas_e_filtros(monkeypatch):
    alunos = [matricula("Zeca", 1), matricula("Ágata", 2), matricula("Ana", 3),
              matricula("Bruno", 4), matricula("Bruno", 4)]
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self, status: alunos)
    ordens = {"a1@example.test": 1, "a2@example.test": 13,
              "a3@example.test": 7, "a4@example.test": 13}
    monkeypatch.setattr(tela, "_consultar", lambda chave: {
        "estado": "ok", "ordem": ordens[chave[1]],
        "faixa": "branca" if ordens[chave[1]] == 1 else "preta",
        "nome_faixa": "Faixa", "cor": "#ffffff"})
    ctx = {}
    original = tela.render
    def render(request, template, contexto, **kwargs):
        ctx.update(contexto)
        return original(request, template, contexto, **kwargs)
    monkeypatch.setattr(tela, "render", render)
    r = tela.ranking_faixas(pedido())
    linhas = list(ctx["pagina"])
    assert [a["nome"] for a in linhas] == ["Ágata", "Bruno", "Ana", "Zeca"]
    assert [a["posicao"] for a in linhas] == [1, 1, 3, 4]
    assert ctx["total"] == 4 and linhas[1]["matriculas"] == 2
    assert ctx["contagens"][0]["total"] == 3
    assert r["Cache-Control"] == "private, no-store"
    assert r["X-Robots-Tag"] == "noindex, nofollow"
    assert "Ranking por faixas" in r.content.decode()
    tela.ranking_faixas(pedido("?q=agata&faixa=preta"))
    assert [a["nome"] for a in ctx["pagina"]] == ["Ágata"]
    assert ctx["pagina"][0]["posicao"] == 1
    tela.ranking_faixas(pedido("?faixa=branca"))
    assert [a["nome"] for a in ctx["pagina"]] == ["Zeca"]


@pytest.mark.parametrize("admin", [{}, {"equipe_apenas": True}])
def test_recusa_sem_admin(admin):
    with pytest.raises(Http404):
        tela.ranking_faixas(pedido(admin=admin))


def test_porta_recusa_anonimo():
    assert Client().get(reverse("ranking_faixas")).status_code in (302, 403, 404)


def test_indisponibilidade_nao_vira_branca(monkeypatch):
    monkeypatch.setattr(tela, "_identidade", lambda email: ("indisponivel", ""))
    assert tela._consultar(("meshcraft.top", "a@example.test")) == {"estado": "indisponivel"}
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self, status: [matricula("Ana", 1)])
    html = tela.ranking_faixas(pedido()).content.decode()
    assert "Faixa indisponível" in html and "sem posição" in html
    assert "1º</td>" not in html


def test_sem_matriculas_e_fonte_fora(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self, status: [])
    assert "Nenhum aluno encontrado" in tela.ranking_faixas(pedido()).content.decode()
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self, status: None)
    assert tela.ranking_faixas(pedido()).status_code == 503


def test_consulta_valida_cache_e_isolamento_de_site(monkeypatch):
    monkeypatch.setattr(tela, "_identidade", lambda email: ("ok", "p1"))
    consulta = Mock(return_value={"site_id": "meshcraft.top", "pessoa_id": "p1",
        "faixa": {"atual": {"ordem": 13, "nome": "Preta · 7º Grau", "cores": ["#111111"]}}})
    monkeypatch.setattr(tela.GamificacaoClient, "resumo_aluno", consulta)
    chave = ("meshcraft.top", "ana@example.test")
    assert tela._consultar(chave)["ordem"] == 13
    assert tela._consultar(chave)["faixa"] == "preta"
    assert consulta.call_count == 1
    assert tela._consultar(("outro.site", chave[1])) == {"estado": "indisponivel"}


def test_falha_nao_e_reaproveitada_como_conquista(monkeypatch):
    identidade = Mock(side_effect=[("indisponivel", ""), ("sem_conta", "")])
    monkeypatch.setattr(tela, "_identidade", identidade)
    chave = ("meshcraft.top", "ana@example.test")
    assert tela._consultar(chave)["estado"] == "indisponivel"
    assert tela._consultar(chave)["estado"] == "sem_conta"


def test_post_nao_altera_progressao():
    r = RequestFactory().post("/escola/ranking-faixas/")
    r.admin = {"id": "admin"}
    assert tela.ranking_faixas(r).status_code == 405
