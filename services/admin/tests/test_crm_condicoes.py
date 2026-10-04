"""/admin/crm/condicoes/: o mantenedor marca quais condições existentes do
checkout o agente pode oferecer. A tela só mostra e grava o que o checkout diz."""
import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

CHECKOUT = "http://checkout:8000/api/checkout"
SESSAO = "http://identidade:8000/interno/sessao/completa"
LISTA = CHECKOUT + "/interno/condicoes-agente"
OFERTA = "curso-esqueleto"
MARCA = CHECKOUT + f"/interno/ofertas/{OFERTA}/condicoes-agente"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("CHECKOUT_API_URL", CHECKOUT)
    monkeypatch.setenv("CHECKOUT_API_TOKEN", "token-admin-checkout")
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade-teste")
    settings.ADMIN_EMAILS = "dono@example.com"


def dentro(csrf=False):
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={"autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": "dono@example.com", "papel": None}))
    c = Client(enforce_csrf_checks=csrf)
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def item(id, metodo, parcelas, total, **extra):
    return {"id": id, "tipo": "condicao", "metodo": metodo, "parcelas": parcelas, "total_cents": total, "parcela_cents": (total // parcelas) if parcelas else None, "vencimento_minutos": None, "liberada": False, **extra}


def resposta(*ofertas):
    return {"site_id": "site-aaa", "ofertas": list(ofertas)}


def oferta(itens, **extra):
    return {"oferta_ref": OFERTA, "disponivel": True, "oferta": {"slug": OFERTA, "produto": "Curso Esqueleto", "preco_cents": 990, "preco": "R$ 9,90", "preco_vigente_cents": 990}, "parcelas": {"consulta": "ok", "maximo": 3}, "itens": itens, **extra}


@respx.mock
def test_tela_mostra_o_que_existe_e_o_que_ja_esta_marcado():
    rota = respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta(oferta([
        item("pix", "pix", 1, 990, vencimento_minutos=30, liberada=True),
        item("card_3x", "card", 3, 1050),
    ]))))
    r = dentro().get(reverse("crm_condicoes"))
    html = r.content.decode()
    assert r.status_code == 200
    assert "Curso Esqueleto" in html and "R$ 9,90" in html
    assert 'value="pix" checked' in html
    assert 'value="card_3x" checked' not in html and 'value="card_3x"' in html
    assert "Cartão em 3x de R$ 3,50" in html
    assert rota.calls.last.request.headers["authorization"] == "Bearer token-admin-checkout"
    assert rota.calls.last.request.headers["host"] == "testserver"


def test_url_da_tela_fica_sob_o_crm():
    assert reverse("crm_condicoes").endswith("/crm/condicoes/")


@respx.mock
def test_pesquisa_de_outra_oferta_vai_na_consulta():
    rota = respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta()))
    r = dentro().get(reverse("crm_condicoes"), {"oferta": "outra-oferta"})
    assert r.status_code == 200
    assert rota.calls.last.request.url.params["oferta"] == "outra-oferta"
    assert "Ainda não há oferta para marcar" in r.content.decode()


@respx.mock
def test_oferta_que_nao_pode_ser_lida_aparece_com_o_motivo():
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta(
        {"oferta_ref": "velha", "disponivel": False, "motivo": "oferta inexistente ou despublicada neste site", "itens": []}
    )))
    html = dentro().get(reverse("crm_condicoes")).content.decode()
    assert "velha" in html and "despublicada" in html


@respx.mock
def test_checkout_fora_do_ar_diz_isso_e_nao_da_500():
    respx.get(LISTA).mock(return_value=httpx.Response(503))
    r = dentro().get(reverse("crm_condicoes"))
    assert r.status_code == 503
    assert "Não foi possível consultar o checkout" in r.content.decode()


@respx.mock
def test_sem_ligacao_com_o_checkout_diz_que_ainda_nao_esta_ligada(monkeypatch):
    monkeypatch.delenv("CHECKOUT_API_URL")
    r = dentro().get(reverse("crm_condicoes"))
    assert r.status_code == 503
    assert "ainda não está ligada" in r.content.decode()


@respx.mock
def test_salvar_manda_so_as_marcadas_com_o_autor_da_sessao_e_registra():
    rota = respx.put(MARCA).mock(return_value=httpx.Response(200, json={"condicoes": []}))
    r = dentro(csrf=False).post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA, "liberar": ["pix", "card_3x"]})
    assert r.status_code == 302 and r["Location"].endswith("?salvo=1")
    corpo = json.loads(rota.calls.last.request.content)
    assert corpo == {"liberadas": ["pix", "card_3x"], "autor": "operador-real"}
    assert rota.calls.last.request.headers["host"] == "testserver"
    registro = Registro.objects.get()
    assert registro.alvo == OFERTA and registro.desfecho == Registro.OK


@respx.mock
def test_salvar_sem_nenhuma_marca_limpa_as_condicoes():
    rota = respx.put(MARCA).mock(return_value=httpx.Response(200, json={"condicoes": []}))
    dentro().post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA})
    assert json.loads(rota.calls.last.request.content)["liberadas"] == []


@respx.mock
def test_salvar_recusado_pelo_checkout_mostra_o_motivo_dele():
    respx.put(MARCA).mock(return_value=httpx.Response(422, json={"detail": "não existe agora para esta oferta: card_12x"}))
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta(oferta([item("pix", "pix", 1, 990)]))))
    r = dentro().post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA, "liberar": ["card_12x"]})
    assert r.status_code == 422
    assert "card_12x" in r.content.decode()
    assert Registro.objects.get().desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_salvar_sem_resposta_nao_diz_que_salvou():
    respx.put(MARCA).mock(side_effect=httpx.ConnectError("fora"))
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta(oferta([item("pix", "pix", 1, 990)]))))
    r = dentro().post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA, "liberar": ["pix"]})
    assert r.status_code == 503
    html = r.content.decode()
    assert "Não conseguimos confirmar" in html and "Condições salvas" not in html
    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_salvar_sem_oferta_pede_para_escolher():
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=resposta()))
    r = dentro().post(reverse("crm_condicoes_salvar"), {"liberar": ["pix"]})
    assert r.status_code == 422
    assert "Escolha a oferta" in r.content.decode()


@respx.mock
def test_salvar_exige_o_cracha_de_administrador_e_o_token_csrf():
    respx.get(SESSAO).mock(return_value=httpx.Response(401))
    anonimo = Client()
    assert anonimo.get(reverse("crm_condicoes")).status_code in (302, 401, 403)
    assert anonimo.post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA}).status_code in (302, 401, 403)
    sem_csrf = dentro(csrf=True).post(reverse("crm_condicoes_salvar"), {"oferta": OFERTA})
    assert sem_csrf.status_code == 403


@respx.mock
def test_o_quadro_do_crm_leva_para_a_tela(monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", "http://leads:8000/api/leads")
    monkeypatch.setenv("LEADS_API_TOKEN", "t")
    respx.get("http://leads:8000/api/leads/crm").mock(return_value=httpx.Response(200, json={"itens": [], "resumo": {}, "pagina": 1, "total": 0, "tem_mais": False}))
    html = dentro().get(reverse("crm")).content.decode()
    assert reverse("crm_condicoes") in html


# --- ajustes de 04/10/2026 (segunda rodada) ----------------------------------------------------


@respx.mock
def test_oferta_com_nome_comprido_nao_derruba_a_auditoria_depois_do_salvamento():
    longa = "curso-" + "x" * 74  # 80 caracteres; o `alvo` da auditoria aceita 64
    rota = respx.put(url__regex=r"^" + CHECKOUT + r"/interno/ofertas/.+/condicoes-agente$").mock(
        return_value=httpx.Response(200, json={"condicoes": []}))
    r = dentro().post(reverse("crm_condicoes_salvar"), {"oferta": longa, "liberar": ["pix"]})
    assert r.status_code == 302 and r["Location"].endswith("?salvo=1") and rota.called
    registro = Registro.objects.get()
    assert registro.alvo == longa[:64] and registro.desfecho == Registro.OK
