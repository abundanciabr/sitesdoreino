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
                          ultima_mensagem=mensagem(texto="Respondida pelo agente", direcao="saida", autor="agente", estado_envio="entregue"))
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
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "enviada", "mensagem": mensagem(direcao="saida", estado_envio="enviado"), "conversa": conversa(estado="pessoa")})
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



@respx.mock
def test_responder_fora_da_janela_com_o_agente_nao_assume_a_conversa():
    leitura_da_conversa(conversa(estado="agente", janela_aberta=False), mensagem())
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={})
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi", "referencia": str(uuid.uuid4())})
    assert r.status_code == 422 and "só um modelo aprovado" in r.content.decode()
    assert not assumir.called and not enviar.called


@respx.mock
def test_responder_descadastrado_devolve_ao_agente_o_que_assumiu():
    leitura_da_conversa(conversa(estado="agente", descadastrado=True), mensagem())
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "descadastrado", "mensagem": None})
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    r = dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi", "referencia": str(uuid.uuid4())})
    assert r.status_code == 422 and assumir.called and devolver.called
    assert json.loads(devolver.calls.last.request.content) == {"site_id": "site-do-host"}


@respx.mock
def test_responder_com_envio_incerto_nao_devolve_a_conversa():
    leitura_da_conversa(conversa(estado="agente"), mensagem())
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(side_effect=httpx.ConnectError("fora"))
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": "Oi", "referencia": str(uuid.uuid4())})
    assert not devolver.called


@respx.mock
def test_aguardando_inclui_conversa_cuja_resposta_falhou_no_envio():
    # A mensageria atualiza a hora da última mensagem mesmo quando o envio falha.
    falhou = conversa(ultima_entrada_em="2026-10-03T10:00:00Z", ultima_mensagem_em="2026-10-03T11:00:00Z",
                      ultima_mensagem=mensagem(direcao="saida", autor="agente", texto="Resposta que falhou", estado_envio="falhou", ocorrida_em="2026-10-03T11:00:00Z"))
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(falhou))
    html = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"}).content.decode()
    assert "Resposta que falhou" in html and "Aguardando resposta" in html


@respx.mock
def test_aguardando_confere_o_ultimo_recado_quando_a_lista_nao_traz():
    falhou = conversa(ultima_entrada_em="2026-10-03T10:00:00Z", ultima_mensagem_em="2026-10-03T11:00:00Z")
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(falhou))
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(None, mensagem(direcao="saida", autor="agente", texto="Não saiu", estado_envio="falhou")))
    html = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"}).content.decode()
    assert "Não saiu" in html


@respx.mock
def test_aguardando_pagina_por_quem_espera_e_nao_pela_pagina_da_mensageria():
    def com(n, espera):
        base = dict(id=str(uuid.uuid4()), ultima_entrada_em="2026-10-03T10:00:00Z")
        if espera:
            return conversa(**base, ultima_mensagem_em="2026-10-03T10:00:00Z", ultima_mensagem=mensagem(texto=f"espera {n}"))
        return conversa(**base, ultima_mensagem_em="2026-10-03T11:00:00Z",
                        ultima_mensagem=mensagem(direcao="saida", autor="agente", estado_envio="entregue", texto=f"respondida {n}"))
    # 2 páginas da mensageria, 100 conversas cada, metade esperando: 100 esperando no total.
    paginas = {1: [com(i, i % 2 == 0) for i in range(100)], 2: [com(i, i % 2 == 0) for i in range(100, 200)]}
    chamadas = []

    def responder_lista(request):
        numero = int(request.url.params["pagina"])
        chamadas.append(numero)
        return httpx.Response(200, json={"itens": paginas[numero], "total": 200, "pagina": numero, "por_pagina": 100, "tem_mais": numero == 1})
    respx.get(MENSAGERIA + "/conversas").mock(side_effect=responder_lista)
    c = dentro()
    html1 = c.get(reverse("crm_conversas"), {"estado": "aguardando"}).content.decode()
    assert html1.count('class="conv-item"') == 50 and "pagina=2" in html1 and "espera 0<" in html1
    html2 = c.get(reverse("crm_conversas"), {"estado": "aguardando", "pagina": 2}).content.decode()
    assert html2.count('class="conv-item"') == 50 and "pagina=3" not in html2 and "respondida" not in html2


# --- ajustes sobre a caixa que já está no ar (04/10/2026) -------------------------------------


def outra_conversa():
    return conversa(id=str(uuid.uuid4()))


@respx.mock
def test_lista_busca_no_maximo_dez_recados_por_pagina():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(*[outra_conversa() for _ in range(12)]))
    busca = respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(200, json=mensagens(None, mensagem(texto="Oi")))
    dentro().get(reverse("crm_conversas"))
    assert busca.call_count == 10


@respx.mock
def test_lista_para_no_primeiro_tropeco_dos_recados():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(*[outra_conversa() for _ in range(5)]))
    busca = respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(502)
    r = dentro().get(reverse("crm_conversas"))
    assert r.status_code == 200 and busca.call_count == 1


@respx.mock
def test_filtro_aguardando_nao_busca_recado_de_quem_ja_esta_esperando():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(*[outra_conversa() for _ in range(3)]))
    busca = respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(200, json=mensagens(None, mensagem()))
    r = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"})
    assert r.status_code == 200 and not busca.called
    assert r.content.decode().count("Aguardando resposta</span>") == 3


@respx.mock
def test_filtro_aguardando_vazio_esconde_mais_conversas_e_descadastrada_nao_espera():
    respondida = conversa(id=str(uuid.uuid4()), ultima_entrada_em="2026-10-03T10:00:00Z", ultima_mensagem_em="2026-10-03T11:00:00Z")
    parou = conversa(id=str(uuid.uuid4()), descadastrado=True)
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(respondida, parou, tem_mais=True))
    respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(
        200, json=mensagens(None, mensagem(direcao="saida", autor="agente", estado_envio="entregue")))
    html = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"}).content.decode()
    assert "Mais conversas" not in html and "Nenhuma conversa com este filtro" in html
    # Sem filtro, a mesma lista mostra o link e a descadastrada não ganha o selo de espera.
    html = dentro().get(reverse("crm_conversas")).content.decode()
    assert "Mais conversas" in html and "Aguardando resposta</span>" not in html


@respx.mock
def test_lista_usa_a_ultima_mensagem_da_api_sem_buscar_de_novo():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(conversa(ultima_mensagem=mensagem(texto="Já veio na lista"))))
    busca = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens())
    html = dentro().get(reverse("crm_conversas")).content.decode()
    assert "Já veio na lista" in html and not busca.called


def responder_com(resultado, *, conv=None, **extras):
    leitura_da_conversa(conv or conversa(estado="pessoa"), mensagem())
    return respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(
        200, json={"resultado": resultado, "mensagem": extras.pop("mensagem", None), "conversa": conversa(), **extras})


def enviar_resposta(texto="Voltando ao assunto"):
    return dentro().post(reverse("crm_conversa", args=[CONVERSA]), {"gesto": "responder", "texto": texto, "referencia": str(uuid.uuid4())})


@pytest.mark.parametrize("estado_envio", ["enviado", "entregue", "lido"])
@respx.mock
def test_responder_so_diz_enviada_quando_o_envio_esta_confirmado(estado_envio):
    responder_com("enviada", mensagem=mensagem(direcao="saida", estado_envio=estado_envio))
    r = enviar_resposta()
    assert r.status_code == 302 and r["Location"].endswith("?feito=3")


@pytest.mark.parametrize("estado_envio", ["desconhecido", "reservado", "aceito", "pendente"])
@respx.mock
def test_responder_sem_entrega_confirmada_avisa_e_guarda_o_texto(estado_envio):
    responder_com("enviada", mensagem=mensagem(direcao="saida", estado_envio=estado_envio))
    r = enviar_resposta("Texto que fica")
    html = r.content.decode()
    assert r.status_code == 200
    assert "Enviada, mas a entrega não foi confirmada; veja o histórico antes de reenviar" in html
    assert "Mensagem enviada." not in html
    assert "Texto que fica</textarea>" in html


@respx.mock
def test_responder_sobre_conversa_do_agente_devolve_ao_agente_se_o_envio_falha():
    responder_com("fora_da_janela", conv=conversa(estado="agente"), detalhe="x")
    assumir = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    r = enviar_resposta("Voltando ao assunto")
    html = r.content.decode()
    assert r.status_code == 422 and assumir.called and devolver.called
    assert json.loads(devolver.calls.last.request.content) == {"site_id": "site-do-host"}
    assert "Nada foi enviado; a conversa continua com o agente" in html and "Voltando ao assunto</textarea>" in html
    assert Registro.objects.filter(alvo=CONVERSA, detalhe="Conversa: devolver (envio recusado)").exists()


@respx.mock
def test_responder_recusado_pela_mensageria_tambem_devolve_ao_agente():
    leitura_da_conversa(conversa(estado="agente"), mensagem())
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(422, json={"detail": "texto obrigatorio"})
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    r = enviar_resposta()
    assert devolver.called and "Nada foi enviado; a conversa continua com o agente" in r.content.decode()


@respx.mock
def test_responder_nao_devolve_se_a_conversa_ja_era_da_pessoa():
    responder_com("fora_da_janela")
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    r = enviar_resposta()
    assert r.status_code == 422 and not devolver.called
    assert "continua com o agente" not in r.content.decode()


@respx.mock
def test_responder_com_a_devolucao_falhando_manda_usar_o_botao():
    responder_com("descadastrado", conv=conversa(estado="agente"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").mock(side_effect=httpx.ConnectError("fora"))
    html = enviar_resposta().content.decode()
    assert "Devolver ao agente" in html and "não conseguimos devolver a conversa ao agente" in html


@respx.mock
def test_escrita_espera_15_segundos_e_leitura_5():
    leitura_da_conversa(conversa(estado="pessoa"), mensagem())
    enviar = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"resultado": "falhou", "mensagem": None, "conversa": conversa()})
    enviar_resposta()
    assert enviar.calls.last.request.extensions["timeout"]["read"] == 15.0
    leitura = [c.request for c in respx.calls if c.request.method == "GET" and c.request.url.path.endswith("/mensagens")][0]
    assert leitura.extensions["timeout"]["read"] == 5.0


@respx.mock
def test_timeout_do_envio_diz_que_pode_ter_saido_e_nao_devolve_ao_agente():
    leitura_da_conversa(conversa(estado="agente"), mensagem())
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/assumir").respond(200, json=conversa(estado="pessoa"))
    respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(side_effect=httpx.ReadTimeout("demorou"))
    devolver = respx.post(MENSAGERIA + f"/conversas/{CONVERSA}/devolver").respond(200, json=conversa())
    r = enviar_resposta("Pode ter ido")
    html = r.content.decode()
    assert r.status_code == 200 and not devolver.called
    assert "O envio pode ter saído" in html and "Confira o histórico" in html and "Pode ter ido</textarea>" in html


@pytest.mark.parametrize("resultado,frase", [
    ("sem_consentimento", "Esta pessoa ainda não autorizou receber mensagens por WhatsApp."),
    ("fora_do_horario", "fora do horário permitido"),
    ("limite_diario", "limite de mensagens do dia"),
    ("limite_do_dia", "limite de mensagens do dia"),
])
@respx.mock
def test_resultados_de_recusa_tem_texto_proprio(resultado, frase):
    responder_com(resultado)
    r = enviar_resposta()
    html = r.content.decode()
    assert r.status_code == 422 and frase in html and "O envio falhou" not in html


@respx.mock
def test_oportunidade_do_lead_so_liga_a_aberta():
    leitura_da_conversa(None, mensagem())
    encerrada = "7a0f5f50-2f43-4a8e-9a42-5d1f6a0c9b11"
    rota = respx.get(LEADS + "/crm").respond(200, json={"itens": [
        {"id": encerrada, "lead_id": LEAD, "situacao": "encerrada"},
        {"id": OPORTUNIDADE, "lead_id": LEAD, "situacao": "aberta"}], "resumo": {}, "total": 2})
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert rota.calls.last.request.url.params["situacao"] == "aberta"
    assert reverse("crm_oportunidade", args=[OPORTUNIDADE]) in html
    assert reverse("crm_oportunidade", args=[encerrada]) not in html


@respx.mock
def test_sem_oportunidade_aberta_nao_liga_nada():
    leitura_da_conversa(None, mensagem())
    respx.get(LEADS + "/crm").respond(200, json={"itens": [{"id": OPORTUNIDADE, "lead_id": LEAD, "situacao": "encerrada"}], "resumo": {}, "total": 1})
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert "Abrir a oportunidade" not in html


@pytest.mark.parametrize("como,esperado", [
    ("dono-test", "(você)"),
    ("aparelho", "(Arameu)"),
    ("arameu@exemplo.com", "(Arameu)"),
    ("identidade-7f3a9c", "(outra pessoa da equipe)"),
])
@respx.mock
def test_conversa_mostra_quem_assumiu_e_nunca_o_identificador_cru(como, esperado):
    from django.utils import timezone

    from apps.core.models import AparelhoDaEquipe, MembroDaEquipe

    membro = MembroDaEquipe.objects.create(nome="Arameu", email="arameu@exemplo.com")
    aparelho = AparelhoDaEquipe.objects.create(membro=membro, chave_hash="h" * 64, como_entrou="link", ultimo_uso_em=timezone.now())
    assumida_por = f"aparelho-{aparelho.pk}" if como == "aparelho" else como
    leitura_da_conversa(conversa(estado="pessoa", assumida_por=assumida_por), mensagem())
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert esperado in html
    if como == "identidade-7f3a9c":
        assert como not in html


@respx.mock
def test_mensagens_anteriores_usam_antes_de_da_api():
    cem = [mensagem(ocorrida_em=f"2026-10-03T{h:02d}:{m:02d}:00+00:00") for h in range(2, 6) for m in range(0, 60, 2)][:100]
    rota = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(None, *cem))
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json={"id": LEAD, "nome": "Ana Souza", "linha_do_tempo": []})
    respx.get(LEADS + "/crm").respond(200, json={"itens": [], "resumo": {}, "total": 0})
    c = dentro()
    html = c.get(reverse("crm_conversa", args=[CONVERSA])).content.decode()
    assert "Mensagens anteriores" in html and "antes_de=2026-10-03T02%3A00%3A00%2B00%3A00" in html
    assert "antes_de" not in rota.calls.last.request.url.params
    html = c.get(reverse("crm_conversa", args=[CONVERSA]), {"antes_de": "2026-10-03T02:00:00+00:00"}).content.decode()
    assert rota.calls.last.request.url.params["antes_de"] == "2026-10-03T02:00:00+00:00"
    assert "Voltar às mais recentes" in html


@respx.mock
def test_poucas_mensagens_nao_mostram_anteriores_e_antes_de_invalido_some():
    rota = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json=mensagens(None, mensagem()))
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json={"id": LEAD, "nome": "Ana Souza", "linha_do_tempo": []})
    respx.get(LEADS + "/crm").respond(200, json={"itens": [], "resumo": {}, "total": 0})
    html = dentro().get(reverse("crm_conversa", args=[CONVERSA]), {"antes_de": "isso-nao-e-data"}).content.decode()
    assert "Mensagens anteriores" not in html and "antes_de" not in rota.calls.last.request.url.params


def respondida_pela_hora():
    # Pela hora parece respondida: só o último recado diz se a resposta saiu.
    return conversa(id=str(uuid.uuid4()), ultima_entrada_em="2026-10-03T10:00:00Z", ultima_mensagem_em="2026-10-03T11:00:00Z")


@respx.mock
def test_filtro_aguardando_confere_no_maximo_dez_recados():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(*[respondida_pela_hora() for _ in range(15)]))
    confere = respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(
        200, json=mensagens(None, mensagem(direcao="saida", autor="agente", estado_envio="entregue")))
    r = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"})
    assert r.status_code == 200 and confere.call_count == 10


@respx.mock
def test_filtro_aguardando_para_no_primeiro_tropeco_da_conferencia():
    respx.get(MENSAGERIA + "/conversas").respond(200, json=lista(*[respondida_pela_hora() for _ in range(15)]))
    confere = respx.get(url__regex=r"^" + MENSAGERIA + r"/conversas/[^/]+/mensagens").respond(502)
    r = dentro().get(reverse("crm_conversas"), {"estado": "aguardando"})
    assert r.status_code == 200 and confere.call_count == 1
