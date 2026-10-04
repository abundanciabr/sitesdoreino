"""Fatos por coorte de quiz para o painel de resultados comerciais."""

import pytest

from apps.core.handlers import ao_quiz_completado
from test_compra_da_oportunidade import (  # noqa: F401  (admin é fixture)
    _entregar, admin, aprovado, estorno, pedido, quiz, recusado,
)

pytestmark = pytest.mark.django_db

URL = "/api/leads/resultados/comerciais"


def _quiz_com_campanha(slug, email, campanha):
    _entregar(ao_quiz_completado, {
        "site_id": "site-a", "quiz_slug": slug, "result_key": "x",
        "lead": {"email": email, "name": "Pessoa"}, "utm": {"utm_campaign": campanha},
    })


def test_conversao_por_quiz_receita_liquida_e_recuperacao(client, admin):
    crivo = quiz("crivo", email="ana@gmail.com")
    quiz("crivo", email="bia@gmail.com")
    cura = quiz("cura", email="caio@gmail.com")
    # teste fica fora dos totais
    quiz("crivo", email="qa@example.com")

    pedido("ped-1", email="ana@gmail.com", oportunidade_ref=str(crivo.id), oferta_ref="of-crivo")
    recusado("ped-1", email="ana@gmail.com")
    aprovado("ped-1", email="ana@gmail.com", valor=1000)
    pedido("ped-2", email="caio@gmail.com", oportunidade_ref=str(cura.id), oferta_ref="of-cura")
    aprovado("ped-2", email="caio@gmail.com", valor=500)
    estorno("ped-2")

    dados = client.get(URL, **admin).json()
    assert dados["totais"]["elegiveis"] == 3
    assert dados["totais"]["compradores"] == 2
    assert dados["totais"]["compras_aprovadas"] == 2
    assert dados["totais"]["compras_recuperadas"] == 1
    assert dados["totais"]["aprovado_centavos"] == 1500
    assert dados["totais"]["estornos_centavos"] == 500
    assert dados["totais"]["liquido_centavos"] == 1000
    assert dados["testes_fora"]["oportunidades"] == 1
    por_quiz = {q["quiz"]: q for q in dados["por_quiz"]}
    assert por_quiz["crivo"]["elegiveis"] == 2 and por_quiz["crivo"]["compradores"] == 1
    assert por_quiz["crivo"]["conversao"] == 0.5
    assert por_quiz["cura"]["liquido_centavos"] == 0
    assert {o["oferta"] for o in dados["por_oferta"]} == {"of-crivo", "of-cura"}
    compra = next(c for c in dados["compras"] if c["pedido_id"] == "ped-1")
    assert compra["oportunidade_id"] == str(crivo.id) and compra["recuperada"] is True
    # só identificadores opacos: nada de e-mail ou nome na resposta
    texto = str(dados)
    assert "ana@gmail.com" not in texto and "Maria" not in texto
    assert len(dados["oportunidades"]) == 3


def test_filtros_por_quiz_campanha_e_oferta(client, admin):
    _quiz_com_campanha("crivo", "a@gmail.com", "primavera")
    _quiz_com_campanha("crivo", "b@gmail.com", "outono")
    cura = quiz("cura", email="c@gmail.com")
    pedido("ped-9", email="c@gmail.com", oportunidade_ref=str(cura.id), oferta_ref="of-cura")
    aprovado("ped-9", email="c@gmail.com")

    so_crivo = client.get(URL, {"quiz": "crivo"}, **admin).json()
    assert so_crivo["totais"]["elegiveis"] == 2
    primavera = client.get(URL, {"campanha": "primavera"}, **admin).json()
    assert primavera["totais"]["elegiveis"] == 1
    assert [c["campanha"] for c in primavera["por_campanha"]] == ["primavera"]
    oferta = client.get(URL, {"oferta": "of-cura"}, **admin).json()
    assert oferta["totais"]["compras_aprovadas"] == 1
    nenhuma = client.get(URL, {"oferta": "outra"}, **admin).json()
    assert nenhuma["totais"]["compras_aprovadas"] == 0
    futuro = client.get(URL, {"desde": "2999-01-01"}, **admin).json()
    assert futuro["totais"]["elegiveis"] == 0 and futuro["totais"]["conversao"] is None


def test_site_id_isola_os_numeros_de_cada_site(client, admin):
    _quiz_com_campanha("crivo", "a@gmail.com", "primavera")
    _entregar(ao_quiz_completado, {
        "site_id": "site-b", "quiz_slug": "crivo", "result_key": "x",
        "lead": {"email": "b@gmail.com", "name": "Pessoa"}, "utm": {"utm_campaign": "outono"},
    })
    a = client.get(URL, {"site_id": "site-a"}, **admin).json()
    b = client.get(URL, {"site_id": "site-b"}, **admin).json()
    assert a["totais"]["elegiveis"] == 1 and [c["campanha"] for c in a["por_campanha"]] == ["primavera"]
    assert b["totais"]["elegiveis"] == 1 and [c["campanha"] for c in b["por_campanha"]] == ["outono"]
    # sem site_id é a visão da plataforma inteira, só para o par do painel
    assert client.get(URL, **admin).json()["totais"]["elegiveis"] == 2


def test_exige_o_par_do_painel(client, admin):
    assert client.get(URL).status_code in (401, 403)
    assert client.get(URL, {"desde": "ontem"}, **admin).status_code == 422
