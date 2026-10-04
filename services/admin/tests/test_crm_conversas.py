"""Caixa de conversas do CRM: lista, conversa, assumir/devolver e responder pela API da mensageria."""
import json
import uuid

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
CATALOGO = "http://catalogo:8000/api/catalogo"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
LEADS = "http://leads:8000/api/leads"
CONVERSA = "5d0b5b8e-0a4c-4c3e-9d5e-1f2a3b4c5d6e"
LEAD = "92f0c4e1-25f4-480f-a64a-1b68d259c563"
OPORTUNIDADE = "24e45be2-77bb-4a32-a388-78d2ce9adcad"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-test")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-test")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-test")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "leads-test")


def dentro():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={
        "autenticado": True, "id": "dono-test", "email": "dono@exemplo.com", "nome_exibido": "Dono"})
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    return client


def conversa(**mudancas):
    return {"id": CONVERSA, "site_id": "site-do-host", "canal": "whatsapp", "endereco_mascarado": "+55 11 9****-4321",
            "lead_id": LEAD, "ligacao": "ligada", "ambigua": False, "estado": "agente", "assumida_por": None,
            "janela_aberta_ate": "2026-10-04T15:00:00Z", "janela_aberta": True, "descadastrado": False,
            "ultima_entrada_em": "2026-10-03T15:00:00Z", "ultima_mensagem_em": "2026-10-03T15:00:00Z", **mudancas}


def mensagem(**mudancas):
    return {"id": str(uuid.uuid4()), "conversa_id": CONVERSA, "direcao": "entrada", "autor": "lead", "texto": "Quanto custa?",
            "midia": None, "transcricao": None, "estado_envio": "recebida", "erro": None, "descadastro": False,
            "ocorrida_em": "2026-10-03T15:00:00Z", **mudancas}


def lista(*itens, tem_mais=False):
    return {"itens": list(itens), "total": len(itens), "pagina": 1, "por_pagina": 50, "tem_mais": tem_mais}


def mensagens(conv=None, *msgs):
    return {"conversa": conv or conversa(), "mensagens": list(msgs)}


def leitura_da_conversa(conv=None, *msgs):
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(conv, *msgs))
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json={"id": LEAD, "nome": "Ana Souza", "linha_do_tempo": []})
    respx.get(LEADS + "/crm").respond(200, json={"itens": [{"id": OPORTUNIDADE, "lead_id": LEAD}], "resumo": {}, "total": 1})


@respx.mock
def test_lista_mostra_canal_estado_ultimo_recado_e_pede_o_site_do_host():
    rota = respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(conversa(ultima_mensagem={**mensagem(), "texto": "Quero saber o preço"})))
    r = dentro().get(reverse("crm_conversas"), {"estado": "pessoa", "canal": "whatsapp"})
    html = r.content.decode()
    assert r.status_code == 200
    assert "Quero saber o preço" in html and "WhatsApp" in html and "Com o agente" in html
    assert 'conv-selo">Com o agente' in html and 'conv-selo espera">Aguardando resposta' in html
    assert reverse("crm_conversa", args=[CONVERSA]) in html
    params = rota.calls.last.request.url.params
    assert params["site_id"] == "site-do-host" and params["estado"] == "pessoa" and params["canal"] == "whatsapp"
    assert params["ligacao"] == "todas"


@respx.mock
def test_lista_busca_ultimo_recado_quando_a_lista_nao_traz():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(conversa()))
    rota = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(None, mensagem(texto="Oi, tudo bem?")))
    r = dentro().get(reverse("crm_conversas"))
    assert "Oi, tudo bem?" in r.content.decode()
    assert rota.calls.last.request.url.params["limite"] == "1"


@respx.mock
def test_filtro_ambigua_pede_ligacao_e_nao_liga_ficha():
    rota = respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(conversa(ambigua=True, ligacao="ambigua", lead_id=None, ultima_mensagem=mensagem())))
    r = dentro().get(reverse("crm_conversas"), {"estado": "ambigua"})
    assert rota.calls.last.request.url.params["ligacao"] == "ambigua"
    assert "Contato ambíguo" in r.content.decode()
    assert reverse("contato", args=[LEAD]) not in r.content.decode()


@respx.mock
def test_filtro_aguardando_mostra_so_quem_falou_por_ultimo():
    respondida = conversa(id=str(uuid.uuid4()), ultima_entrada_em="2026-10-03T10:00:00Z", ultima_mensagem_em="2026-10-03T11:00:00Z",
                          ultima_mensagem=mensagem(texto="Respondida pelo agente"))
    esperando = conversa(ultima_mensagem=mensagem(texto="Ainda esperando"))
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(respondida, esperando))
    html = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"}).content.decode()
    assert "Ainda esperando" in html and "Respondida pelo agente" not in html


@respx.mock
def test_lista_com_mensageria_fora_do_ar_avisa_sem_500():
    respx.get(MENSAGERIA + "/conversas").mock(side_effect=httpx.ConnectError("fora"))
    r = dentro().get(reverse("crm_conversas"))
    assert r.status_code == 503
    assert "Não foi possível consultar as conversas" in r.content.decode()


@respx.mock
def test_lista_sem_caixa_na_mensageria_aparece_como_ainda_indisponivel():
    respx.get(MENSAGERIA + "/conversas").respond(404, json={"detail": "Not Found"})
    r = dentro().get(reverse("crm_conversas"))
    assert r.status_code == 200
    assert "ainda não está disponível" in r.content.decode()


@respx.mock
def test_lista_sem_par_configurado(monkeypatch):
    monkeypatch.delenv("MENSAGERIA_API_TOKEN")
    r = dentro().get(reverse("crm_conversas"))
    assert r.status_code == 503
    assert "aguardando a conexão com a mensageria" in r.content.decode()


@respx.mock
def test_conversa_mostra_dois_sentidos_midia_transcricao_e_ligacoes():
    leitura_da_conversa(None,
                        mensagem(texto="Quanto custa?"),
                        mensagem(direcao="saida", autor="agente", texto="Custa R$ 97.", estado_envio="entregue", ocorrida_em="2026-10-03T15:01:00Z"),
                        mensagem(texto="", midia={"tipo": "audio", "referencia": "m1", "mime": "audio/ogg"}, transcricao="Posso pagar no Pix?", ocorrida_em="2026-10-03T15:02:00Z"))
    r = dentro().get(reverse("crm_conversa", args=[CONVERSA]))
    html = r.content.decode()
    assert r.status_code == 200
    assert "Ana Souza" in html and "Quanto custa?" in html and "Custa R$ 97." in html and "Entregue" in html
    assert "Áudio" in html and "Transcrição: Posso pagar no Pix?" in html
    assert reverse("contato", args=[LEAD]) in html and reverse("crm_oportunidade", args=[OPORTUNIDADE]) in html
    assert "24 horas" in html and "Assumir a conversa" in html


@respx.mock
def test_conversa_fora_da_janela_explica_modelo_aprovado():
    leitura_da_conversa(conversa(janela_aberta=False, janela_aberta_ate="2026-10-01T15:00:00Z"), mensagem())
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert "só dá para enviar um modelo de mensagem aprovado" in html
    assert 'name="modelo"' in html


@respx.mock
def test_conversa_ambigua_nao_consulta_nem_mostra_ficha():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(conversa(ambigua=True, ligacao="ambigua", lead_id=None), mensagem()))
    leads = respx.get(url__startswith=LEADS).respond(200, json={})
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert "mais de um contato" in html and not leads.called


@respx.mock
def test_conversa_com_mensageria_fora_do_ar():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(502)
    r = dentro().get(reverse("crm_conversa", args=[CONVERSA]))
    assert r.status_code == 503 and "Não foi possível consultar" in r.content.decode()


@respx.mock
def test_conversa_de_outro_site_e_404():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(404, json={"detail": "conversa inexistente"})
    assert dentro().get(reverse("crm_conversa", args=[CONVERSA])).status_code == 404


@respx.mock
def test_assumir_e_devolver_levam_quem_e_o_site():
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    c = dentro()
    r = c.post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "assumir", "pessoa_id": "forjado"})
    assert r.status_code == 302 and r["Location"].endswith("?feito=1")
    assert json.loads(assumir.calls.last.request.content) == {"site_id": "site-do-host", "pessoa_id": "dono-test"}
    r = c.post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "devolver"})
    assert r.status_code == 302
    assert json.loads(devolver.calls.last.request.content) == {"site_id": "site-do-host"}
    assert Registro.objects.filter(alvo=CONVERSA, desfecho=Registro.OK).count() == 2


@respx.mock
def test_responder_assume_antes_e_envia_como_pessoa_com_chave_estavel():
    leitura_da_conversa(None, mensagem())
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "enviada", "mensagem": mensagem(direcao="saida"), "conversa": conversa(estado="pessoa")})
    referencia = str(uuid.uuid4())
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi, Ana!", "referencia": referencia})
    assert r.status_code == 302 and r["Location"].endswith("?feito=3")
    assert assumir.called
    corpo = json.loads(enviar.calls.last.request.content)
    assert corpo == {"site_id": "site-do-host", "texto": "Oi, Ana!", "chave_idempotencia": "painel:" + referencia, "autor": "pessoa", "autor_id": "dono-test"}


@respx.mock
def test_responder_fora_da_janela_explica_e_guarda_o_texto():
    leitura_da_conversa(conversa(estado="pessoa", janela_aberta=False), mensagem())
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "fora_da_janela", "detalhe": "x", "mensagem": None, "conversa": conversa()})
    referencia = str(uuid.uuid4())
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Voltando ao assunto", "referencia": referencia})
    html = r.content.decode()
    assert r.status_code == 422
    assert "só um modelo aprovado" in html and "Voltando ao assunto" in html and referencia in html


@respx.mock
def test_responder_com_modelo_aprovado_envia_o_modelo():
    leitura_da_conversa(conversa(estado="pessoa", janela_aberta=False), mensagem())
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "enviada", "mensagem": mensagem(direcao="saida"), "conversa": conversa()})
    dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "", "modelo": "retomada_curso", "referencia": str(uuid.uuid4())})
    assert json.loads(enviar.calls.last.request.content)["modelo"] == {"nome": "retomada_curso", "idioma": "pt_BR", "componentes": []}


@respx.mock
def test_responder_com_mensageria_fora_do_ar_nao_afirma_envio():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(side_effect=httpx.ConnectError("fora"))
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={})
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi", "referencia": str(uuid.uuid4())})
    assert r.status_code == 503 and not enviar.called
    assert "Mensagem enviada" not in r.content.decode()


@respx.mock
def test_responder_sem_texto_nem_referencia_nao_chama_a_mensageria():
    leitura_da_conversa(None, mensagem())
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={})
    c = dentro()
    assert c.post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "", "referencia": str(uuid.uuid4())}).status_code == 422
    assert c.post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi"}).status_code == 422
    assert not enviar.called


@respx.mock
def test_descadastrado_explica_por_que_nao_enviou():
    leitura_da_conversa(conversa(estado="pessoa", descadastrado=True), mensagem())
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "descadastrado", "mensagem": None, "conversa": conversa()})
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi", "referencia": str(uuid.uuid4())})
    assert r.status_code == 422 and "pediu para não receber mais mensagens" in r.content.decode()


@respx.mock
def test_sem_sessao_nao_abre():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={"autenticado": False})
    r = Client().get(reverse("crm_conversas"))
    assert r.status_code in (302, 401, 403)
