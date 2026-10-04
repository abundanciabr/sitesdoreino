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


# --- funil por etapa, qualidade do atendimento e desempenho técnico (04/10/2026) ---------------

METRICAS = "http://metricas:8000/api/metricas"


def _grupo_funil(**extra):
    base = {"abertas": 40, "com_resposta": 12, "com_link_enviado": 6, "com_pedido": 4, "ganhas": 3,
            "receita_centavos": 29700, "perdidas": 1, "amostra_insuficiente": False}
    return {**base, **extra}


def _corpo_do_funil():
    return {
        "site_id": "site-a", "desde": "2026-09-01", "ate": "2026-10-03", "amostra_minima": 30,
        "oportunidades": 45, "mensagens_recebidas": 20,
        "por_estrategia": [
            dict(_grupo_funil(), estrategia_versao=1),
            dict(_grupo_funil(abertas=5, com_resposta=1, com_link_enviado=0, com_pedido=0, ganhas=0, receita_centavos=0,
                              perdidas=0, amostra_insuficiente=True), estrategia_versao=2),
        ],
        "por_atendente": [
            dict(_grupo_funil(abertas=30), atendente="agente"),
            dict(_grupo_funil(abertas=15, amostra_insuficiente=True), atendente="pessoa"),
        ],
    }


@pytest.fixture
def metricas(monkeypatch):
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "t-metricas")


@respx.mock
def test_funil_aparece_na_tela_com_amostra_insuficiente(monkeypatch, metricas):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    rota = respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(200, json=_corpo_do_funil()))
    r = dentro().get(reverse("crm_resultados"), {"site_id": "site-a", "desde": "2026-09-01", "ate": "2026-10-03"})
    assert r.status_code == 200
    params = rota.calls.last.request.url.params
    assert params["site_id"] == "site-a" and params["desde"] == "2026-09-01" and params["ate"] == "2026-10-03"
    assert rota.calls.last.request.headers["Authorization"] == "Bearer t-metricas"
    funil = r.context["funil"]
    assert funil["disponivel"] and funil["total"]["abertas"] == 45 and funil["total"]["ganhas"] == 3
    assert [l["nome"] for l in funil["por_estrategia"]] == ["Versão 1", "Versão 2"]
    assert [l["nome"] for l in funil["por_atendente"]] == ["Agente", "Pessoa"]
    html = r.content.decode()
    assert "Funil de vendas" in html and "Por versão de estratégia" in html and "Por atendente" in html
    assert "R$ 297,00" in html and "amostra insuficiente" in html
    # sem o registro dos agentes, o que só ele sabe fica indisponível
    assert funil["com_mensagem_do_agente"] is None


@respx.mock
def test_metricas_fora_do_ar_vira_aviso_e_o_resto_da_pagina_continua(monkeypatch, metricas):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(503))
    r = dentro().get(reverse("crm_resultados"), {"site_id": "site-a"})
    assert r.status_code == 200
    assert r.context["funil"]["disponivel"] is False
    html = r.content.decode()
    assert "O funil ainda está indisponível" in html and "Conversão dos quizzes" in html
    assert "Ainda indisponível: os agentes comerciais ainda não registram trabalho" in html


@respx.mock
def test_sem_par_de_metricas_ou_sem_site_o_funil_diz_indisponivel(monkeypatch):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    sem_par = dentro().get(reverse("crm_resultados"), {"site_id": "site-a"})
    assert sem_par.status_code == 200 and "aguarda a conexão com a medição" in sem_par.content.decode()
    sem_site = dentro().get(reverse("crm_resultados"))
    assert sem_site.status_code == 200 and "de qual site perguntar" in sem_site.content.decode()


@respx.mock
def test_funil_fora_do_contrato_vira_aviso(monkeypatch, metricas):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    torto = _corpo_do_funil()
    torto["por_estrategia"][0]["abertas"] = "muitas"
    respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(200, json=torto))
    r = dentro().get(reverse("crm_resultados"), {"site_id": "site-a"})
    assert r.status_code == 200 and r.context["funil"]["disponivel"] is False


@pytest.mark.skipif(not apps.is_installed("apps.comercial"), reason="agentes comerciais ainda não estão nesta célula")
@respx.mock
def test_qualidade_e_desempenho_batem_com_os_trabalhos_criados(metricas):
    Trabalho = apps.get_model("comercial", "TrabalhoComercial")
    Decisao = apps.get_model("comercial", "DecisaoComercial")
    agora = timezone.now()

    def trabalho(chave, tipo="atender_mensagem", **campos):
        return Trabalho.objects.create(tipo=tipo, chave_idempotencia=chave, site_id=campos.pop("site_id", "site-a"), **campos)

    def decisao(t, call, ferramenta, resultado, entrada=None, saida=None):
        return Decisao.objects.create(trabalho=t, call_id=call, papel="atendimento", ferramenta=ferramenta,
                                      resultado=resultado, entrada=entrada or {}, saida=saida or {})

    t1 = trabalho("q1", entrada={"descadastro": True}, tentativas=1, iniciado_em=agora)
    t2 = trabalho("q2", estado="falhou", tentativas=3, iniciado_em=agora)
    t3 = trabalho("q3", estado="envio_incerto", tentativas=2)
    t4 = trabalho("q4", tentativas=1, iniciado_em=agora)
    teste = trabalho("q5", teste=True, estado="falhou", entrada={"descadastro": True})
    outro_site = trabalho("q6", site_id="site-b", estado="falhou")
    decisao(t4, "p1", "passar_para_responsavel", "feito", entrada={"motivo": "O lead pediu para falar com uma pessoa"})
    decisao(t4, "p2", "enviar_mensagem", "feito", saida={"resultado": "enviada", "canal": "whatsapp"})
    decisao(t1, "p3", "enviar_mensagem", "recusado", saida={"resultado": "fora_da_janela"})
    decisao(t2, "p4", "enviar_mensagem", "recusado", saida={"resultado": "fora_do_horario"})
    decisao(t3, "p5", "enviar_mensagem", "recusado", saida={"resultado": "limite_diario"})
    decisao(t3, "p6", "enviar_mensagem", "recusado", saida={"resultado": "limite_do_dia"})
    decisao(teste, "p7", "enviar_mensagem", "recusado", saida={"resultado": "fora_da_janela"})
    decisao(outro_site, "p8", "enviar_mensagem", "recusado", saida={"resultado": "fora_da_janela"})
    # o trabalho demorou 90 segundos para responder e esperou 30 na fila
    Trabalho.objects.filter(pk=t4.pk).update(criado_em=agora - timedelta(seconds=90), iniciado_em=agora - timedelta(seconds=60))
    Decisao.objects.filter(trabalho=t4, call_id="p2").update(criada_em=agora)

    desde = (agora - timedelta(days=1)).date()
    ate = (agora + timedelta(days=1)).date()
    q = crm_resultados.atendimento.qualidade(desde, ate, "site-a")
    assert q["disponivel"] and q["trabalhos"] == 4
    assert q["descadastros"] == 1 and q["descadastros_fonte"] == "agentes"
    assert q["passaram_para_pessoa"] == 1 and q["passagem_por_motivo"] == [{"nome": "Pediu para falar com uma pessoa", "n": 1}]
    assert q["falharam"] == 1 and q["envio_incerto"] == 1
    assert (q["janela"], q["horario"], q["teto"], q["recusadas_total"]) == (1, 1, 2, 4)
    tudo = crm_resultados.atendimento.qualidade(desde, ate, "")
    assert tudo["trabalhos"] == 5 and tudo["falharam"] == 2 and tudo["janela"] == 2  # teste fica fora

    d = crm_resultados.atendimento.desempenho(desde, ate, "site-a")
    assert d["disponivel"] and d["trabalhos"] == 4
    assert d["respostas"] == 1 and d["resposta_media_texto"] == "1 min 30 s" and d["resposta_pior_texto"] == "1 min 30 s"
    assert d["fila_amostra"] == 3 and d["fila_pior_texto"] == "30 s"
    assert d["tentativas_amostra"] == 4 and d["tentativas_maximo"] == 3 and d["tentativas_media_texto"] == "1,8"
    assert d["falharam"] == 1 and d["envio_incerto"] == 1 and d["falhas_taxa_texto"] == "25,0%"

    # na tela, com o filtro de período e de site
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(200, json=_corpo_do_funil()))
    r = dentro().get(reverse("crm_resultados"), {"site_id": "site-a", "desde": desde.isoformat(), "ate": ate.isoformat()})
    assert r.status_code == 200
    assert r.context["qualidade"]["falharam"] == 1 and r.context["desempenho"]["respostas"] == 1
    assert r.context["funil"]["com_mensagem_do_agente"] == 0  # t4 é sem oportunidade: só conta quem tem oportunidade
    html = r.content.decode()
    assert "Qualidade do atendimento" in html and "Desempenho técnico" in html and "1 min 30 s" in html
    assert "O lead pediu" not in html  # a frase do agente nunca aparece, só o grupo


@pytest.mark.skipif(not apps.is_installed("apps.comercial"), reason="agentes comerciais ainda não estão nesta célula")
@respx.mock
def test_descadastros_vem_da_mensageria_quando_ela_responde(monkeypatch):
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "t")
    respx.get(MENSAGERIA + "/conversas/resultados").mock(return_value=httpx.Response(200, json={
        "por_canal": [{"canal": "whatsapp", "descadastros": 3}, {"canal": "email", "descadastros": 2}]}))
    hoje = timezone.localdate()
    q = crm_resultados.atendimento.qualidade(hoje, hoje, "site-a")
    assert q["descadastros"] == 5 and q["descadastros_fonte"] == "mensageria"


def test_duracao_em_portugues_simples():
    d = crm_resultados.atendimento.duracao
    assert d(None) == "ainda indisponível"
    assert (d(0), d(45), d(125), d(4200)) == ("0 s", "45 s", "2 min 05 s", "1 h 10 min")


@pytest.mark.skipif(not apps.is_installed("apps.comercial"), reason="agentes comerciais ainda não estão nesta célula")
@respx.mock
@pytest.mark.parametrize("parametros", [
    {"ate": "9999-12-31"},
    {"desde": "0001-01-01", "ate": "9999-12-31"},
    {"desde": "0001-01-01"},
])
def test_data_no_limite_do_calendario_nao_derruba_qualidade_e_desempenho(metricas, parametros):
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(200, json=_corpo_do_funil()))
    r = dentro().get(reverse("crm_resultados"), dict(parametros, site_id="site-a"))
    assert r.status_code == 200
    assert r.context["qualidade"]["disponivel"] and r.context["desempenho"]["disponivel"]


@respx.mock
def test_periodo_acima_do_teto_da_medicao_pede_periodo_menor_sem_perguntar(monkeypatch, metricas):
    monkeypatch.setattr(crm_resultados, "_modelos_comerciais", lambda: None)
    respx.get(BASE + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=fatos()))
    rota = respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(422))
    r = dentro().get(reverse("crm_resultados"), {"site_id": "site-a", "desde": "2024-01-01", "ate": "2026-10-03"})
    assert r.status_code == 200 and r.context["funil"]["disponivel"] is False
    assert "Escolha um período mais curto" in r.content.decode() and "Tente de novo" not in r.content.decode()
    assert not rota.called
    # 366 dias ainda cabem
    respx.get(METRICAS + "/crm/funil").mock(return_value=httpx.Response(200, json=_corpo_do_funil()))
    ok = dentro().get(reverse("crm_resultados"), {"site_id": "site-a", "desde": "2025-10-04", "ate": "2026-10-04"})
    assert ok.context["funil"]["disponivel"] is True


@pytest.mark.skipif(not apps.is_installed("apps.comercial"), reason="agentes comerciais ainda não estão nesta célula")
def test_fatos_dos_agentes_consulta_em_lotes_e_da_o_mesmo_resultado(monkeypatch):
    from django.db import connection

    Trabalho = apps.get_model("comercial", "TrabalhoComercial")
    Decisao = apps.get_model("comercial", "DecisaoComercial")
    oportunidades, compras = [], []
    for n in range(7):
        t = Trabalho.objects.create(tipo="abordar", chave_idempotencia=f"k{n}", oportunidade_id=f"op-{n}",
                                    contato_id=f"l-{n}", site_id="site-a", custo_usd=Decimal("0.10"))
        Decisao.objects.create(trabalho=t, call_id=f"c{n}", papel="abordagem", versao_estrategia=3,
                               ferramenta="enviar_mensagem", resultado="feito", custo_usd=Decimal("0.30"),
                               saida={"canal": "whatsapp", "conversa_id": f"cv-{n}"})
        oportunidades.append({"id": f"op-{n}", "lead_id": f"l-{n}"})
    # Trabalho sem oportunidade, achado só pelo contato.
    Trabalho.objects.create(tipo="abordar", chave_idempotencia="sem-op", oportunidade_id="", contato_id="l-3", site_id="site-a")
    inteiro = crm_resultados.fatos_dos_agentes(oportunidades, compras)

    maior = []

    def espiar(execute, sql, params, many, context):
        maior.append(len(params or ()))
        return execute(sql, params, many, context)

    monkeypatch.setattr(crm_resultados, "LOTE_DO_IN", 2)
    with connection.execute_wrapper(espiar):
        em_lotes = crm_resultados.fatos_dos_agentes(oportunidades, compras)
    assert max(maior) <= 2 + 1  # o lote mais a marca de teste
    assert em_lotes["envios"]["whatsapp"]["enviadas"] == inteiro["envios"]["whatsapp"]["enviadas"] == 7
    assert em_lotes["custo_modelos_usd"] == inteiro["custo_modelos_usd"]
