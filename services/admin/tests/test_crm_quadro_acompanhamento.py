"""O quadro do CRM: sinais de acompanhamento no cartão, dois filtros novos e o menu das quatro áreas."""
import httpx
import pytest
import respx
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.core.templatetags import crm_menu

BASE = "http://leads:8000/api/leads"
SESSAO = "http://identidade:8000/interno/sessao/completa"
ID = "24e45be2-77bb-4a32-a388-78d2ce9adcad"
LEAD = "92f0c4e1-25f4-480f-a64a-1b68d259c563"
RESUMO = {"contatos": 10, "sem_oportunidade": 0, "abertas": 1, "atrasadas": 0, "ganhas": 0}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", BASE)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-de-teste")
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade-teste")
    settings.ADMIN_EMAILS = "dono@example.com"


def dentro():
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={"autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": "dono@example.com", "papel": None}))
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def item(**mudancas):
    base = {
        "id": ID, "lead_id": LEAD, "etapa": "negociacao", "situacao": "aberta",
        "titular": {"id": "crm-recuperacao"},
        "contato": {"id": LEAD, "nome": "Ana", "email": "ana@example.com"},
        "proximo_passo": {"descricao": "Retomar a conversa sobre o Pix", "executar_ate": "2099-10-05T15:00:00-03:00"},
        "prazo": "2099-10-05T15:00:00-03:00",
        "atendido_por": {"tipo": "agente", "nome": "Assistente de vendas"},
        "ultimo_contato_em": "2026-10-02T14:30:00-03:00",
        "objecao_principal": "Acha caro para o momento",
        "aguardando_resposta": True,
        "historico": [],
    }
    return {**base, **mudancas}


def quadro(itens):
    return httpx.Response(200, json={"itens": itens, "resumo": RESUMO, "pagina": 1, "total": len(itens), "tem_mais": False})


@respx.mock
def test_cartao_mostra_os_sinais_de_acompanhamento():
    respx.get(BASE + "/crm").mock(return_value=quadro([item()]))
    html = dentro().get(reverse("crm")).content.decode()
    assert "Agente · Assistente de vendas" in html
    assert "Aguardando resposta" in html
    assert "Objeção: Acha caro para o momento" in html
    assert "Último contato: 02/10/2026 14:30" in html
    assert "Prazo: 05/10/2099 15:00" in html
    assert "Retomar a conversa sobre o Pix" in html


@respx.mock
def test_cartao_de_pessoa_sem_objecao_nem_espera():
    respx.get(BASE + "/crm").mock(return_value=quadro([item(
        atendido_por={"tipo": "pessoa", "nome": "Marina"}, objecao_principal="",
        aguardando_resposta=False, ultimo_contato_em=None)]))
    html = dentro().get(reverse("crm")).content.decode()
    assert "Pessoa · Marina" in html
    assert "Aguardando resposta</span>" not in html
    assert "Objeção:" not in html
    assert "Último contato: nenhum ainda" in html


@respx.mock
def test_cartao_sem_atendente_cai_no_responsavel_antigo():
    respx.get(BASE + "/crm").mock(return_value=quadro([item(atendido_por=None)]))
    html = dentro().get(reverse("crm")).content.decode()
    assert "Responsável: crm-recuperacao" in html


@respx.mock
def test_cartao_de_api_antiga_sem_campos_novos_nao_quebra():
    antigo = item()
    for campo in ("atendido_por", "ultimo_contato_em", "objecao_principal", "aguardando_resposta", "prazo"):
        antigo.pop(campo)
    respx.get(BASE + "/crm").mock(return_value=quadro([antigo]))
    r = dentro().get(reverse("crm"))
    assert r.status_code == 200
    assert "Ana" in r.content.decode()


@respx.mock
def test_texto_do_atendente_e_da_objecao_nao_vira_html():
    respx.get(BASE + "/crm").mock(return_value=quadro([item(
        atendido_por={"tipo": "pessoa", "nome": "<script>x()</script>"},
        objecao_principal="<b>caro</b>")]))
    html = dentro().get(reverse("crm")).content.decode()
    assert "<script>x()" not in html and "<b>caro</b>" not in html
    assert "&lt;script&gt;" in html


@respx.mock
def test_filtros_de_quem_atende_e_aguardando_vao_para_a_api():
    rota = respx.get(BASE + "/crm").mock(return_value=quadro([item()]))
    r = dentro().get(reverse("crm"), {"atendido_por": "agente", "aguardando_resposta": "sim"})
    params = rota.calls.last.request.url.params
    assert params["atendido_por"] == "agente" and params["aguardando_resposta"] == "sim"
    html = r.content.decode()
    assert '<option value="agente" selected>' in html
    assert '<option value="sim" selected>' in html
    assert "Limpar filtros" in html


@respx.mock
def test_filtro_invalido_e_ignorado_sem_erro():
    rota = respx.get(BASE + "/crm").mock(return_value=quadro([item()]))
    r = dentro().get(reverse("crm"), {"atendido_por": "robo", "aguardando_resposta": "talvez"})
    assert r.status_code == 200
    params = rota.calls.last.request.url.params
    assert "atendido_por" not in params and "aguardando_resposta" not in params


@respx.mock
def test_paginacao_guarda_os_filtros_novos():
    respx.get(BASE + "/crm").mock(return_value=httpx.Response(200, json={"itens": [item()], "resumo": RESUMO, "pagina": 1, "total": 150, "tem_mais": True}))
    html = dentro().get(reverse("crm"), {"atendido_por": "pessoa", "aguardando_resposta": "nao"}).content.decode()
    assert "atendido_por=pessoa" in html and "aguardando_resposta=nao" in html and "pagina=2" in html


@respx.mock
def test_menu_mostra_as_quatro_areas_e_marca_oportunidades():
    respx.get(BASE + "/crm").mock(return_value=quadro([item()]))
    html = dentro().get(reverse("crm")).content.decode()
    for nome in ("Oportunidades", "Conversas", "Agentes", "Resultados"):
        assert nome in html
    assert f'<a href="{reverse("crm")}" class="aba ativa" aria-current="page">Oportunidades</a>' in html


def test_menu_com_paginas_existentes_vira_link_e_marca_a_area_aberta(monkeypatch):
    enderecos = {"crm": "/admin/crm/", "crm_conversas": "/admin/crm/conversas/", "crm_agentes": "/admin/crm/agentes/", "crm_resultados": "/admin/crm/resultados/"}

    def falso(nome):
        if nome not in enderecos:
            raise NoReverseMatch(nome)
        return enderecos[nome]

    monkeypatch.setattr(crm_menu, "reverse", falso)
    areas = crm_menu.areas_do_crm("/admin/crm/conversas/abc/")
    assert [a["nome"] for a in areas] == ["Oportunidades", "Conversas", "Agentes", "Resultados"]
    assert [a["endereco"] for a in areas] == list(enderecos.values())
    assert [a["nome"] for a in areas if a["ativa"]] == ["Conversas"]
    assert [a["nome"] for a in crm_menu.areas_do_crm("/admin/crm/") if a["ativa"]] == ["Oportunidades"]
    assert [a["nome"] for a in crm_menu.areas_do_crm("/admin/crm/9f0c/") if a["ativa"]] == ["Oportunidades"]


def test_menu_com_pagina_que_ainda_nao_existe_nao_derruba(monkeypatch):
    def so_crm(nome):
        if nome != "crm":
            raise NoReverseMatch(nome)
        return "/admin/crm/"

    monkeypatch.setattr(crm_menu, "reverse", so_crm)
    areas = crm_menu.areas_do_crm("/admin/crm/")
    assert [a["nome"] for a in areas if not a["endereco"]] == ["Conversas", "Agentes", "Resultados"]


def test_menu_aceita_a_rota_antiga_dos_agentes(monkeypatch):
    def antiga(nome):
        if nome != "agentes_comerciais":
            raise NoReverseMatch(nome)
        return "/admin/crm/agentes/"

    monkeypatch.setattr(crm_menu, "reverse", antiga)
    agentes = [a for a in crm_menu.areas_do_crm("/admin/crm/agentes/") if a["nome"] == "Agentes"][0]
    assert agentes["endereco"] == "/admin/crm/agentes/" and agentes["ativa"]
