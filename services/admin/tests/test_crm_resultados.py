"""Painel de resultados comerciais: números da coorte, custos, margem e versões."""
from datetime import datetime, timedelta, timezone as fuso
from decimal import Decimal

import httpx
import pytest
import respx
from django.apps import apps
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import crm_resultados

BASE = "http://leads:8000/api/leads"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
SESSAO = "http://identidade:8000/interno/sessao/completa"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", BASE)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-de-teste")
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade-teste")
    for nome in ("CRM_REAIS_POR_DOLAR", "CRM_CUSTO_WHATSAPP_CENTAVOS", "CRM_CUSTO_EMAIL_CENTAVOS", "MENSAGERIA_API_URL", "MENSAGERIA_API_TOKEN"):
        monkeypatch.delenv(nome, raising=False)
    settings.ADMIN_EMAILS = "dono@example.com"


def dentro():
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={"autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": "dono@example.com", "papel": None}))
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def grupo(**extra):
    base = {"elegiveis": 3, "compradores": 2, "conversao": 0.6667, "compras_aprovadas": 2, "compras_revertidas": 1,
            "compras_recuperadas": 1, "aprovado_centavos": 1500, "estornos_centavos": 500, "liquido_centavos": 1000}
    return {**base, **extra}


def fatos():
    return {
        "moeda": "BRL", "filtros": {},
        "totais": grupo(),
        "por_quiz": [grupo(quiz="crivo")],
        "por_campanha": [grupo(campanha="primavera")],
        "por_oferta": [grupo(oferta="of-crivo")],
        "oportunidades": [
            {"id": "op-1", "lead_id": "l-1", "quiz": "crivo", "campanha": "primavera"},
            {"id": "op-2", "lead_id": "l-2", "quiz": "crivo", "campanha": "primavera"},
            {"id": "op-3", "lead_id": "l-3", "quiz": "cura", "campanha": "sem campanha"},
        ],
        "oportunidades_truncadas": False,
        "compras": [
            {"pedido_id": "p-1", "oportunidade_id": "op-1", "lead_id": "l-1", "quiz": "crivo", "campanha": "primavera", "oferta": "of-crivo",
             "aprovado_em": "2026-10-02T12:00:00+00:00", "aprovado_centavos": 1000, "estornos_centavos": 0, "liquido_centavos": 1000,
             "recuperada": True, "revertida": False},
            {"pedido_id": "p-3", "oportunidade_id": "op-3", "lead_id": "l-3", "quiz": "cura", "campanha": "sem campanha", "oferta": "of-cura",
             "aprovado_em": "2026-10-02T12:00:00+00:00", "aprovado_centavos": 500, "estornos_centavos": 500, "liquido_centavos": 0,
             "recuperada": False, "revertida": True},
        ],
        "testes_fora": {"oportunidades": 4, "compras": 1},
    }


@respx.mock
def test_tela_mostra_conversao_receita_liquida_e_agentes_indisponiveis(monkeypatch):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    rota = respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    r = dentro().get(reverse("crm_resultados"), {"quiz": "crivo", "desde": "2026-09-01", "ate": "2026-10-03"})
    assert r.status_code == 200
    html = r.content.decode()
    assert "66,7%" in html and "R$ 10,00" in html and "R$ 5,00" in html
    assert "ainda indisponível" in html and "Não é lucro" in html
    assert "consumo dos modelos" in html
    params = rota.calls.last.request.url.params
    assert params["quiz"] == "crivo" and params["desde"] == "2026-09-01" and params["ate"] == "2026-10-03"
    assert "Amostra pequena" in html


@respx.mock
def test_leads_fora_do_ar_vira_aviso_e_nao_zero():
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(404))
    r = dentro().get(reverse("crm_resultados"))
    assert r.status_code == 503
    html = r.content.decode()
    assert "ainda estão indisponíveis" in html and "R$ 0,00" not in html


def _agentes_falsos():
    agora = timezone.now()
    antes = datetime(2026, 10, 1, tzinfo=fuso.utc)
    return {
        "trabalhos": 3,
        "custo_modelos_usd": Decimal("2.00"),
        "assistidas": [dict(fatos()["compras"][0], versao=("abordagem", 2))],
        "atendidas": 2,
        "versoes": {
            ("abordagem", 1): {"custo_usd": Decimal("0.50"), "oportunidades": {"op-2"}, "envios": {"whatsapp": 1}},
            ("abordagem", 2): {"custo_usd": Decimal("1.50"), "oportunidades": {"op-1"}, "envios": {"whatsapp": 3}},
        },
        "envios": {
            "whatsapp": {"enviadas": 4, "pessoas": {"l-1", "l-2"}, "primeiro_envio": {"c-1": (antes, "site-a"), "c-2": (antes, "site-a")}},
            "email": {"enviadas": 0, "pessoas": set(), "primeiro_envio": {}},
        },
        "envios_sem_canal": 0,
        "_agora": agora,
    }


@respx.mock
def test_custos_margem_resposta_e_versoes_inconclusivas(monkeypatch):
    monkeypatch.setattr(crm_resultados, "fatos_dos_agentes", lambda o, c: _agentes_falsos())
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "t")
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    respx.get(MENSAGERIA + "/conversas/resultados").mock(return_value=httpx.Response(404))
    respx.get(MENSAGERIA + "/conversas").mock(return_value=httpx.Response(200, json={
        "itens": [{"id": "c-1", "ultima_entrada_em": "2026-10-01T10:00:00+00:00"}, {"id": "c-2", "ultima_entrada_em": None}],
        "tem_mais": False,
    }))
    r = dentro().get(reverse("crm_resultados"), {"dolar": "5,00", "tarifa_whatsapp": "25"})
    assert r.status_code == 200
    ctx = r.context
    # modelos: US$ 2,00 x 5 = R$ 10,00; WhatsApp: 4 x 25 centavos = R$ 1,00
    assert ctx["custo_centavos"] == 1100
    assert ctx["custo_por_venda"] == 550
    # margem = líquido (R$ 10,00) - custos medidos; desconto não é subtraído de novo
    assert ctx["margem_centavos"] == -100
    assert ctx["assistidas"] == 1
    canal = ctx["resposta"]["canais"][0]
    assert canal["canal"] == "whatsapp" and canal["enviadas"] == 4 and canal["responderam"] == 1
    assert canal["entregues"] is None
    assert [v["versao"] for v in ctx["versoes"]] == [1, 2]
    assert ctx["comparacoes"] == [{"papel": "abordagem", "conclusivo": False, "melhor": None, "papel_nome": "Abordagem"}]
    html = r.content.decode()
    assert "resultado inconclusivo" in html and "taxas do provedor de pagamento" in html


@respx.mock
def test_sem_cotacao_custo_fica_indisponivel_e_nao_vira_zero(monkeypatch):
    monkeypatch.setattr(crm_resultados, "fatos_dos_agentes", lambda o, c: _agentes_falsos())
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    r = dentro().get(reverse("crm_resultados"))
    assert r.status_code == 200
    assert r.context["custo_centavos"] is None and r.context["margem_centavos"] is None
    assert any("dólar" in f for f in r.context["faltam"])
    assert any("WhatsApp" in f for f in r.context["faltam"])


@respx.mock
def test_filtro_por_versao_recalcula_a_coorte(monkeypatch):
    monkeypatch.setattr(crm_resultados, "fatos_dos_agentes", lambda o, c: _agentes_falsos())
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    r = dentro().get(reverse("crm_resultados"), {"estrategia": "abordagem:2", "dolar": "5", "tarifa_whatsapp": "10"})
    assert r.status_code == 200
    totais = r.context["totais"]
    assert totais["elegiveis"] == 1 and totais["compras_aprovadas"] == 1 and totais["liquido_centavos"] == 1000
    # só o custo da versão 2: US$ 1,50 x 5 + 3 mensagens x 10 centavos
    assert r.context["custo_centavos"] == 780 and r.context["custo_por_venda"] == 780
    vazia = dentro().get(reverse("crm_resultados"), {"estrategia": "abordagem:9", "dolar": "5"})
    assert vazia.context["totais"]["elegiveis"] == 0 and vazia.context["custo_centavos"] == 0


def test_resultados_por_versao_amostra_suficiente():
    pessoas = {f"op-{i}" for i in range(40)}
    agentes = {"versoes": {("atendimento", 1): {"custo_usd": Decimal(0), "oportunidades": pessoas},
                           ("atendimento", 2): {"custo_usd": Decimal(0), "oportunidades": pessoas}}}
    vendas = {("atendimento", 1): [{"liquido_centavos": 100}] * 5, ("atendimento", 2): [{"liquido_centavos": 100}] * 9}
    linhas, comparacoes = crm_resultados._versoes(agentes, vendas)
    assert all(l["suficiente"] for l in linhas)
    assert comparacoes == [{"papel": "atendimento", "conclusivo": True, "melhor": 2}]


def test_reais_com_valor_negativo():
    assert crm_resultados.reais(-150) == "-R$ 1,50"
    assert crm_resultados.reais(123456) == "R$ 1.234,56"
    assert crm_resultados.reais(None) == "ainda indisponível"


@pytest.mark.skipif(not apps.is_installed("apps.comercial"), reason="agentes comerciais ainda não estão nesta célula")
def test_fatos_dos_agentes_com_o_registro_real():
    Trabalho = apps.get_model("comercial", "TrabalhoComercial")
    Decisao = apps.get_model("comercial", "DecisaoComercial")
    t = Trabalho.objects.create(tipo="abordar", chave_idempotencia="k1", oportunidade_id="op-1", contato_id="l-1",
                                site_id="site-a", custo_usd=Decimal("0.10"))
    teste = Trabalho.objects.create(tipo="abordar", chave_idempotencia="k2", oportunidade_id="op-2", teste=True)
    Decisao.objects.create(trabalho=t, call_id="c1", papel="abordagem", versao_estrategia=3, ferramenta="enviar_mensagem",
                           resultado="feito", custo_usd=Decimal("0.30"), saida={"canal": "whatsapp", "conversa_id": "cv-1"})
    Decisao.objects.create(trabalho=teste, call_id="c2", papel="abordagem", versao_estrategia=3, ferramenta="enviar_mensagem",
                           resultado="feito", custo_usd=Decimal("9"), saida={"canal": "whatsapp"})
    depois = (timezone.now() + timedelta(hours=1)).isoformat()
    compras = [{"oportunidade_id": "op-1", "lead_id": "l-1", "aprovado_em": depois, "liquido_centavos": 1000}]
    oportunidades = [{"id": "op-1", "lead_id": "l-1"}, {"id": "op-2", "lead_id": "l-2"}]
    fatos_ = crm_resultados.fatos_dos_agentes(oportunidades, compras)
    assert fatos_["custo_modelos_usd"] == Decimal("0.30")
    assert len(fatos_["assistidas"]) == 1 and fatos_["assistidas"][0]["versao"] == ("abordagem", 3)
    assert fatos_["envios"]["whatsapp"]["enviadas"] == 1


# --- ajustes de 04/10/2026 (segunda rodada) ----------------------------------------------------


@respx.mock
def test_pagina_de_resultados_tem_o_menu_das_areas_do_crm(monkeypatch):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    html = dentro().get(reverse("crm_resultados")).content.decode()
    assert 'aria-label="Áreas do CRM"' in html
    assert f'href="{reverse("crm")}"' in html and f'href="{reverse("crm_resultados")}" class="aba ativa"' in html


@pytest.mark.parametrize("parametros", [
    {"desde": "2026-02-31"},
    {"ate": "2026-13-45", "desde": "2026-09-01"},
    {"desde": "0000-00-00"},
    {"dolar": "inf"},
    {"dolar": "-inf"},
    {"dolar": "nan"},
    {"dolar": "1e99999999"},
    {"tarifa_whatsapp": "Infinity", "tarifa_email": "1e999999"},
    {"estrategia": "abordagem:²"},
    {"estrategia": "abordagem:١٢"},
    {"estrategia": "abordagem:" + "9" * 5000},
    {"dolar": "²"},
])
@respx.mock
def test_valor_mal_escrito_na_url_nao_derruba_a_pagina_de_resultados(monkeypatch, parametros):
    monkeypatch.setattr(crm_resultados, "fatos_dos_agentes", lambda o, c: _agentes_falsos())
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    r = dentro().get(reverse("crm_resultados"), parametros)
    assert r.status_code == 200
    # Cotação e tarifa inválidas valem como "não informadas": o custo fica indisponível, não vira número falso.
    if any(k in parametros for k in ("dolar", "tarifa_whatsapp")):
        assert r.context["custo_centavos"] is None


def test_decimal_so_aceita_numero_finito_e_razoavel():
    assert crm_resultados._decimal("5,40") == Decimal("5.40")
    assert crm_resultados._decimal("0") == Decimal("0")
    for ruim in ("inf", "-inf", "nan", "sNaN", "1e99999999", "1000001", "-1", "abc", ""):
        assert crm_resultados._decimal(ruim) is None


def test_data_impossivel_cai_no_periodo_padrao():
    from datetime import date

    padrao = date(2026, 10, 1)
    assert crm_resultados._data("2026-02-31", padrao) == padrao
    assert crm_resultados._data("", padrao) == padrao
    assert crm_resultados._data("2026-02-28", padrao) == date(2026, 2, 28)
    assert crm_resultados._inteiro("12") == 12
    assert crm_resultados._inteiro("²") is None and crm_resultados._inteiro("9" * 10) is None
