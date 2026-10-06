import datetime as dt

import httpx
import pytest
import respx
from django.test import RequestFactory

from apps.core import ciclo
from apps.core.ciclo_produtos import PAINEIS, montar_painel, montar_visao_ciclo


@pytest.mark.parametrize("chave,meta", [("curso", 500), ("desafio", 10000)])
def test_dias_somam_a_semana_e_semanas_somam_a_meta(chave, meta):
    painel = montar_painel(chave, [], dt.date(2026, 10, 5))
    assert sum(s["meta"] for s in painel["semanas"]) == meta
    for semana in painel["semanas"]:
        assert sum(int(d["meta"].replace(".", "")) for d in semana["dias"] if d["meta"] != "—") == semana["meta"]
    assert painel["preparacao"]["meta"] == 0
    assert [s["n"] for s in painel["recuperacoes"]] == [11, 12]


def test_recuperacao_conta_o_fim_de_semana_e_recalcula_o_saldo():
    alunos = [{"origem": "comprou", "status": "ativa", "virou_aluno_em": "2026-12-13T23:00:00-03:00"}] * 350
    alunos += [{"origem": "comprou", "status": "ativa", "virou_aluno_em": "2026-12-20T20:00:00-03:00"}] * 80
    painel = montar_painel("curso", alunos, dt.date(2026, 12, 21))
    assert painel["recuperacoes"][0]["meta"] == "75"
    assert painel["recuperacoes"][1]["meta"] == "70"
    assert [d["meta"] for d in painel["recuperacoes"][1]["dias"]] == ["18", "18", "17", "17"]


def test_compra_sem_data_nao_vira_zero():
    painel = montar_painel("curso", [{"origem": "comprou", "status": "ativa"}], dt.date(2026, 10, 5))
    assert painel["total"] is None
    assert painel["datas_ausentes"] == 1


@pytest.mark.parametrize("hoje,semana,etapa,proxima", [
    (dt.date(2026, 10, 6), 1, "Preparar", 2),
    (dt.date(2026, 10, 12), 2, "Validar", 3),
    (dt.date(2026, 11, 9), 6, "Crescer", 7),
    (dt.date(2026, 12, 13), 10, "Crescer", None),
])
def test_home_acompanha_a_semana_e_a_etapa(hoje, semana, etapa, proxima):
    visao = montar_visao_ciclo(montar_painel("desafio", [], hoje), hoje)
    assert visao["atual"]["n"] == semana
    assert [e["nome"] for e in visao["etapas"] if e["atual"]] == [etapa]
    assert (visao["proxima"]["n"] if visao["proxima"] else None) == proxima


@pytest.mark.parametrize("hoje,estado", [
    (dt.date(2026, 10, 4), "O ciclo ainda não começou"),
    (dt.date(2026, 12, 14), "Semanas de recuperação"),
    (dt.date(2026, 12, 28), "Ciclo encerrado"),
])
def test_home_fora_do_plano_nao_fica_presa_na_preparacao(hoje, estado):
    visao = montar_visao_ciclo(montar_painel("desafio", None, hoje), hoje)
    assert visao["atual"] is None
    assert not any(e["atual"] for e in visao["etapas"])
    assert visao["estado"] == estado


@respx.mock
def test_mesma_pessoa_comprando_os_dois_produtos_conta_em_ambos(monkeypatch):
    monkeypatch.setattr(ciclo.CatalogoClient, "site_por_host", lambda self, host: {"id": "mesh"})
    monkeypatch.setattr(ciclo.CatalogoClient, "oferta_do_site", lambda self, site, slug: (self.OK, {
        "product": {"id": "desafio-id" if slug.startswith("desafio") else "curso-id"}
    }))
    monkeypatch.setattr(ciclo.CatalogoClient, "listar_produtos", lambda self: [
        {"id": "curso-id", "slug": PAINEIS["curso"]["slug"]},
        {"id": "desafio-id", "slug": PAINEIS["desafio"]["slug"]},
    ])
    base = {"origem": "comprou", "status": "ativa", "site_id": "mesh", "email": "mesma@exemplo.test",
            "virou_aluno_em": "2026-10-13T12:00:00-03:00"}
    monkeypatch.setattr(ciclo.AlunosClient, "alunos", lambda self: [
        {**base, "id": "1", "product_id": "curso-id"},
        {**base, "id": "2", "product_id": "desafio-id"},
        {**base, "id": "3", "product_id": "curso-id", "site_id": "outro-site"},
        {**base, "id": "4", "product_id": "desafio-id", "origem": "liberado"},
        {**base, "id": "5", "product_id": "curso-id", "status": "reembolsada"},
    ])
    monkeypatch.setattr("apps.core.vendas_do_crm.vinculos", lambda pessoas: {
        p["id"]: {"contato_crm_id": "mesmo-contato", "venda_origem": "quiz"} for p in pessoas
    })
    monkeypatch.setattr(ciclo.LeadsClient, "_pedir", lambda *a, **kw: ("indisponivel", None))
    for chave in PAINEIS:
        request = RequestFactory().get("/placar/ciclo/", {"produto": chave})
        request.admin = {"nome": "Teste"}
        resposta = ciclo.ciclo(request)
        html = resposta.content.decode()
        assert resposta.status_code == 200
        assert PAINEIS[chave]["nome"] in html
        assert '<strong>1</strong><span>vendas realizadas</span>' in html
        assert 'aria-current="page"' in html
