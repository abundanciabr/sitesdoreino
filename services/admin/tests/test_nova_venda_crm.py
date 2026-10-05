import datetime as dt
import json

import httpx
import pytest
import respx
from django.test import RequestFactory
from django.template.loader import render_to_string

from apps.core import vendas_do_crm, views
from apps.core.clients import AlunosClient
from apps.core.placar import contar_compras


def test_escola_mostra_origem_e_campanha_sem_perguntar_a_origem():
    html = render_to_string("admin/escola_alunos.html", {
        "esperando": [{"id": "1", "origem_identificada": {
            "origem_rotulo": "Quiz", "origem_registrada": "quiz:crivo", "campanha": "instagram · entrada",
            "contato_crm_id": "00000000-0000-4000-8000-000000000001"}}],
        "cursos": [{"id": "curso", "name": "Curso"}], "admin": {},
    })
    assert "Origem identificada pelo sistema" in html
    assert "quiz:crivo" in html and "instagram · entrada" in html
    assert 'name="venda_origem"' not in html
    assert 'name="nova_venda"' in html


@pytest.mark.django_db
@pytest.mark.parametrize("origem", ["", "quiz", "trafego", "crm"])
def test_liberar_com_a_origem_e_o_contato_conferido(monkeypatch, origem):
    calls = []
    monkeypatch.setattr(AlunosClient, "fila", lambda *a: [{"id": "1", "email": "certo@dominio.com", "site_id": "site"}])
    monkeypatch.setattr(AlunosClient, "decidir", lambda *a, **kw: (calls.append(kw) or (AlunosClient.OK, "")))
    def contatos(pessoas):
        assert pessoas[0]["email"] == "certo@dominio.com"
        return {"1": {"contato_crm_id": "lead-confirmado", "venda_origem": origem or "quiz"}}
    monkeypatch.setattr(vendas_do_crm, "vinculos", contatos)
    request = RequestFactory().post("/escola/decidir", {
        "alvo": "1", "decisao": "liberar", "product_id": "curso", "venda_origem": "forjada", "nova_venda": "1" if origem else "",
        "pessoa_email": "forjado@dominio.com", "contato_crm_id": "forjado",
    })
    request.admin = {"id": "dono", "email": "dono@dominio.com"}
    resposta = views.escola_decidir(request)
    assert resposta.status_code == 302 and "resultado=liberado" in resposta.url
    assert calls[0].get("venda_origem", "") == origem
    assert calls[0].get("contato_crm_id", "") == ("lead-confirmado" if origem else "")


@pytest.mark.django_db
@pytest.mark.parametrize("retorno,recado", [({}, "sem-contato-crm"), (None, "crm-indisponivel")])
def test_sem_vinculo_confirmado_nao_libera_como_venda(monkeypatch, retorno, recado):
    monkeypatch.setattr(AlunosClient, "fila", lambda *a: [{"id": "1", "site_id": "site", "email": "a@dominio.com"}])
    monkeypatch.setattr(vendas_do_crm, "vinculos", lambda pessoas: retorno)
    monkeypatch.setattr(AlunosClient, "decidir", lambda *a, **kw: pytest.fail("não deveria liberar"))
    request = RequestFactory().post("/escola/decidir", {"alvo": "1", "decisao": "liberar", "product_id": "curso", "nova_venda": "1"})
    request.admin = {"id": "dono"}
    assert recado in views.escola_decidir(request).url


@respx.mock
def test_placar_cruza_o_crm_sem_contar_testes_antigos_ou_pessoa_duas_vezes(monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", "http://leads/api/leads")
    monkeypatch.setenv("LEADS_API_TOKEN", "token-local")
    base = {"site_id": "site", "status": "ativa", "virou_aluno_em": "2026-10-04T12:00:00-03:00"}
    alunos = [{**base, "id": str(n), "origem": origem} for n, origem in enumerate([
        "comprou", "comprou", "comprou", "liberado", "teste",
    ])]
    route = respx.post("http://leads/api/leads/alunos/vinculos-comerciais").respond(200, json={"vinculos": {
        "0": {"contato_crm_id": "lead", "venda_origem": "quiz"},
        "1": {"contato_crm_id": "lead", "venda_origem": "quiz"},
    }})
    qualificadas = vendas_do_crm.para_o_placar(alunos)
    r = contar_compras(qualificadas, dt.date(2026, 9, 3), dt.date(2026, 10, 4))
    assert r["ciclo"] == r["mes"] == 1
    assert len(json.loads(route.calls[0].request.content)["pessoas"]) == 3
    route.respond(503)
    assert vendas_do_crm.para_o_placar(alunos) is None
    assert vendas_do_crm.para_o_placar(alunos[3:]) == alunos[3:]
