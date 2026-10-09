"""Tela /admin/links/: links enviados, destinos, resumo da Métricas, escrita e CSV."""
import csv
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
METRICAS = "http://metricas:8000/api/metricas"
LEADS = "http://leads:8000/api/leads"
CONVERSA = "5d0b5b8e-0a4c-4c3e-9d5e-1f2a3b4c5d6e"
LEAD = "92f0c4e1-25f4-480f-a64a-1b68d259c563"
DESTINO = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-test")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-test")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "mensageria-test")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "metricas-test")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "leads-test")


def dentro():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={
        "autenticado": True, "id": "dono-test", "email": "dono@exemplo.com", "nome_exibido": "Dono"})
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    return client


def link(**mudancas):
    return {
        "id": str(uuid.uuid4()), "token": "abcde12345", "url_curta": "https://meshcraft.top/r/abcde12345",
        "url_original": "https://exemplo.com/oferta?a=1", "destino": {"id": DESTINO, "nome": "Oferta de outubro"},
        "versao": 1, "origem": "conversa", "referencia": "ref", "campanha": "boas-vindas",
        "conversa_id": CONVERSA, "mensagem_id": None, "passo_id": None,
        "criado_em": "2026-10-09T12:00:00Z", "enviado_em": "2026-10-09T12:01:00Z",
        "acessos": {"total": 3, "provaveis": 1, "automaticos": 2, "indeterminados": 0,
                    "primeiro_provavel_em": "2026-10-09T12:05:00Z", "ultimo_em": "2026-10-09T12:06:00Z"},
        **mudancas,
    }


def destino(**mudancas):
    return {"id": DESTINO, "nome": "Oferta de outubro", "origem": "manual", "url_atual": "https://exemplo.com/oferta",
            "versao_atual": 1, "arquivado_em": None, "criado_em": "2026-10-01T12:00:00Z",
            "versoes": [{"numero": 1, "url": "https://exemplo.com/oferta", "criada_em": "2026-10-01T12:00:00Z", "criada_por": "dono"}],
            "links_enviados": 4, "acessos_provaveis": 2, **mudancas}


def leituras(itens=None, destinos=None):
    rota = respx.get(MENSAGERIA + "/links").respond(200, json={"itens": itens if itens is not None else [link()], "total": 1})
    respx.get(MENSAGERIA + "/links/destinos").respond(200, json={"itens": destinos if destinos is not None else [destino()]})
    return rota


def resumo_ok():
    respx.get(METRICAS + "/links").respond(200, json={"base": "enviados", "horas": 24, "agrupar": "destino", "grupos": [
        {"chave": DESTINO, "rotulo": "Oferta de outubro", "enviados": 7, "com_acesso_provavel": 3,
         "sem_acesso_apos_horas": 2, "acessos_automaticos": 5, "amostra_insuficiente": False}]})


@respx.mock
def test_tela_lista_links_destinos_e_repassa_filtros():
    rota = leituras()
    resumo_ok()
    r = dentro().get(reverse("destinos_rastreados"), {
        "de": "2026-10-01", "ate": "2026-10-09", "campanha": "boas-vindas", "destino_id": DESTINO, "situacao": "sem_acesso"})
    html = r.content.decode()
    assert r.status_code == 200
    assert "https://meshcraft.top/r/abcde12345" in html and "Oferta de outubro" in html
    assert "Acesso provável não prova quem tocou" in html
    assert "Sem acesso após 24 h" in html and ">7<" in html
    p = rota.calls.last.request.url.params
    assert p["site_id"] == "site-do-host" and p["de"] == "2026-10-01" and p["ate"] == "2026-10-09"
    assert p["campanha"] == "boas-vindas" and p["destino_id"] == DESTINO and p["situacao"] == "sem_acesso"
    assert reverse("destinos_rastreados_exportar") + "?" in html


@respx.mock
def test_filtro_torto_nao_vai_para_a_mensageria():
    rota = leituras()
    resumo_ok()
    dentro().get(reverse("destinos_rastreados"), {"de": "ontem", "destino_id": "x", "situacao": "qualquer"})
    p = rota.calls.last.request.url.params
    assert "de" not in p and "destino_id" not in p and "situacao" not in p


@respx.mock
def test_metricas_caindo_nao_derruba_a_tela():
    leituras()
    respx.get(METRICAS + "/links").respond(500)
    r = dentro().get(reverse("destinos_rastreados"))
    assert r.status_code == 200
    assert "resumo por destino está indisponível" in r.content.decode()
    assert "Oferta de outubro" in r.content.decode()


@respx.mock
def test_mensageria_caindo_mostra_aviso_e_nao_500():
    respx.get(MENSAGERIA + "/links").respond(500)
    respx.get(MENSAGERIA + "/links/destinos").mock(side_effect=httpx.ConnectError("fora"))
    resumo_ok()
    r = dentro().get(reverse("destinos_rastreados"))
    assert r.status_code == 200
    assert "a Mensageria não respondeu" in r.content.decode()


@respx.mock
def test_sem_sessao_redireciona_e_nao_chama_a_mensageria():
    respx.get(IDENTIDADE + "/sessao/completa").respond(200, json={"autenticado": False})
    rota = respx.get(MENSAGERIA + "/links").respond(200, json={"itens": []})
    assert Client().get(reverse("destinos_rastreados")).status_code == 302
    assert not rota.called


@respx.mock
def test_novo_destino_chama_a_mensageria_audita_e_redireciona():
    rota = respx.post(MENSAGERIA + "/links/destinos").respond(201, json={"id": DESTINO})
    r = dentro().post(reverse("destinos_rastreados_novo"), {"nome": "Oferta", "url": "https://exemplo.com/x?a=1"})
    assert r.status_code == 302 and r.url.endswith("?feito=criado")
    import json
    corpo = json.loads(rota.calls.last.request.content)
    assert corpo["site_id"] == "site-do-host" and corpo["nome"] == "Oferta" and corpo["url"] == "https://exemplo.com/x?a=1"
    assert corpo["criada_por"] == "dono-test"
    assert Registro.objects.filter(detalhe="Links: criar destino", desfecho=Registro.OK).count() == 1


@respx.mock
def test_novo_destino_com_endereco_invalido_nao_chama_a_mensageria():
    rota = respx.post(MENSAGERIA + "/links/destinos").respond(201, json={})
    r = dentro().post(reverse("destinos_rastreados_novo"), {"nome": "Oferta", "url": "http://inseguro.com"})
    assert r.status_code == 302 and r.url.endswith("?erro=invalido")
    assert not rota.called


@respx.mock
def test_novo_destino_recusado_audita_como_recusado():
    respx.post(MENSAGERIA + "/links/destinos").respond(403, json={"detail": "acesso de escrita negado"})
    r = dentro().post(reverse("destinos_rastreados_novo"), {"nome": "Oferta", "url": "https://exemplo.com"})
    assert r.url.endswith("?erro=sem_publicacao")
    assert Registro.objects.get().desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_nova_versao_e_arquivar():
    versao = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/versoes").respond(201, json={"numero": 2, "url": "https://novo.com"})
    arquivar = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/arquivar").respond(200, json={"arquivado_em": "2026-10-09T12:00:00Z"})
    desarquivar = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/desarquivar").respond(200, json={"arquivado_em": None})
    c = dentro()
    r = c.post(reverse("destinos_rastreados_versao", args=[DESTINO]), {"url": "https://novo.com"})
    assert r.url.endswith("?feito=versao") and versao.calls.last.request.url.params["site_id"] == "site-do-host"
    assert c.post(reverse("destinos_rastreados_arquivar", args=[DESTINO]), {"acao": "arquivar"}).url.endswith("?feito=arquivado")
    assert c.post(reverse("destinos_rastreados_arquivar", args=[DESTINO]), {"acao": "desarquivar"}).url.endswith("?feito=desarquivado")
    assert arquivar.call_count == 1 and desarquivar.call_count == 1
    assert Registro.objects.count() == 3


@respx.mock
def test_exportar_csv_com_bom_cabecalho_e_celula_protegida():
    leituras(itens=[link(campanha="=HYPERLINK(1)")])
    r = dentro().get(reverse("destinos_rastreados_exportar"), {"campanha": "x"})
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    corpo = r.content
    assert corpo.startswith("﻿".encode("utf-8"))
    linhas = corpo.decode("utf-8-sig").splitlines()
    assert linhas[0].startswith("token,url_curta,url_original,destino,versao")
    assert "abcde12345" in linhas[1] and "'=HYPERLINK(1)" in linhas[1]


@respx.mock
def test_exportar_pede_5000_linhas():
    rota = leituras()
    dentro().get(reverse("destinos_rastreados_exportar"))
    assert rota.calls.last.request.url.params["limite"] == "5000"


@respx.mock
def test_conversa_mostra_bloco_de_links():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"conversa": {
        "id": CONVERSA, "site_id": "site-do-host", "canal": "whatsapp", "endereco_mascarado": "+55 11 9****-4321",
        "lead_id": LEAD, "ligacao": "ligada", "ambigua": False, "estado": "agente", "assumida_por": None}, "mensagens": []})
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json={"id": LEAD, "nome": "Ana", "linha_do_tempo": []})
    respx.get(LEADS + "/crm").respond(200, json={"itens": [], "resumo": {}, "total": 0})
    rota = respx.get(MENSAGERIA + "/links").respond(200, json={"itens": [link()], "total": 1})
    r = dentro().get(reverse("crm_conversa", args=[CONVERSA]))
    html = r.content.decode()
    assert r.status_code == 200 and "Links enviados e acessos" in html and "https://meshcraft.top/r/abcde12345" in html
    assert "o link pode ter sido encaminhado" in html
    assert rota.calls.last.request.url.params["conversa_id"] == CONVERSA


@respx.mock
def test_conversa_continua_quando_os_links_nao_respondem():
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").respond(200, json={"conversa": {
        "id": CONVERSA, "site_id": "site-do-host", "canal": "whatsapp", "endereco_mascarado": "+55 11 9****-4321",
        "lead_id": LEAD, "ligacao": "ligada", "ambigua": False, "estado": "agente", "assumida_por": None}, "mensagens": []})
    respx.get(LEADS + f"/leads/{LEAD}").respond(200, json={"id": LEAD, "nome": "Ana", "linha_do_tempo": []})
    respx.get(LEADS + "/crm").respond(200, json={"itens": [], "resumo": {}, "total": 0})
    respx.get(MENSAGERIA + "/links").respond(500)
    r = dentro().get(reverse("crm_conversa", args=[CONVERSA]))
    assert r.status_code == 200 and "Sem leitura dos links agora." in r.content.decode()


@respx.mock
def test_conta_do_robo_consegue_ler_a_tela():
    import io
    from django.core.management import call_command
    saida = io.StringIO()
    call_command("conta_do_robo", "emitir", stdout=saida, stderr=io.StringIO())
    respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-do-host"})
    leituras()
    resumo_ok()
    r = Client(HTTP_AUTHORIZATION="Robo " + saida.getvalue().strip()).get("/links/")
    assert r.status_code == 200


@respx.mock
def test_nova_versao_404_e_403_dizem_a_causa_e_auditam_recusa():
    rota = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/versoes")
    rota.respond(404, json={"detail": "x"})
    r = dentro().post(reverse("destinos_rastreados_versao", args=[DESTINO]), {"url": "https://novo.com"})
    assert r.url.endswith("?erro=nao_existe")
    rota.respond(403, json={"detail": "acesso de escrita negado"})
    r = dentro().post(reverse("destinos_rastreados_versao", args=[DESTINO]), {"url": "https://novo.com"})
    assert r.url.endswith("?erro=sem_publicacao")
    assert {x.desfecho for x in Registro.objects.all()} == {Registro.RECUSADO_PELA_CELULA}


@respx.mock
def test_mostrar_arquivados_preserva_filtros_e_resumo_diz_o_periodo():
    leituras()
    resumo_ok()
    html = dentro().get(reverse("destinos_rastreados"), {"campanha": "boas-vindas", "situacao": "sem_acesso"}).content.decode()
    assert "arquivados=1" in html and "campanha=boas-vindas" in html and "situacao=sem_acesso" in html
    assert "últimos 30 dias" in html


# ---------------------------------------------------------------------------
# Encaixe: JSON REAL devolvido pela API da Mensageria
# (copiado de test_forma_real_da_api_e_dos_eventos_que_os_consumidores_copiam)
# ---------------------------------------------------------------------------
LINK_REAL = {
    "id": "407396d2-88a9-436b-ac21-65b05f019fa0", "token": "3z4rcifp61",
    "url_curta": "https://meshcraft.top/r/3z4rcifp61",
    "url_original": "https://loja.exemplo/p?a=1&b=x%20y#fim",
    "destino": {"id": "2a74cced-f66c-4e96-a852-3f6faf8c43a0", "nome": "https://loja.exemplo/p"},
    "versao": 1, "origem": "conversa", "referencia": "ref-1", "campanha": "boas-vindas",
    "conversa_id": "7fa3334b-a32a-43f0-a65f-0a03810ab7bd", "mensagem_id": None, "passo_id": None,
    "criado_em": "2026-10-09T17:40:55.325342+00:00", "enviado_em": "2026-10-09T17:40:55.333455+00:00",
    "acessos": {"total": 3, "provaveis": 2, "automaticos": 1, "indeterminados": 0,
                "primeiro_provavel_em": "2026-10-09T17:40:55.341760+00:00",
                "ultimo_em": "2026-10-09T17:40:55.596698+00:00"},
}
DESTINO_REAL = {
    "id": "2a74cced-f66c-4e96-a852-3f6faf8c43a0", "nome": "https://loja.exemplo/p", "origem": "automatico",
    "url_atual": "https://loja.exemplo/p?a=1&b=x%20y#fim", "versao_atual": 1, "arquivado_em": None,
    "criado_em": "2026-10-09T17:40:55.321779+00:00",
    "versoes": [{"numero": 1, "url": "https://loja.exemplo/p?a=1&b=x%20y#fim",
                 "criada_em": "2026-10-09T17:40:55.323747+00:00", "criada_por": "automatico"}],
    "links_enviados": 1, "acessos_provaveis": 2,
}
# Resposta REAL de GET /api/metricas/links (mesmo conjunto de chaves travado em
# services/metricas/tests/test_links_rastreados.py::test_encaixe_resposta_real_para_o_admin).
RESUMO_REAL = {"base": "enviados", "horas": 24, "agrupar": "destino", "grupos": [
    {"chave": "2a74cced-f66c-4e96-a852-3f6faf8c43a0", "rotulo": "https://loja.exemplo/p", "enviados": 1,
     "com_acesso_provavel": 1, "sem_acesso_apos_horas": 0, "acessos_automaticos": 1, "amostra_insuficiente": True}]}


@respx.mock
def test_encaixe_tela_csv_e_conversa_com_o_json_real():
    rota = respx.get(MENSAGERIA + "/links").respond(200, json={"itens": [LINK_REAL], "total": 1})
    respx.get(MENSAGERIA + "/links/destinos").respond(200, json={"itens": [DESTINO_REAL]})
    metricas = respx.get(METRICAS + "/links").respond(200, json=RESUMO_REAL)
    c = dentro()
    r = c.get(reverse("destinos_rastreados"), {"de": "2026-10-01", "ate": "2026-10-09"})
    html = r.content.decode()
    assert r.status_code == 200 and not r.context["avisos"]
    assert LINK_REAL["url_curta"] in html and "https://loja.exemplo/p" in html
    assert r.context["links"][0]["acessos"]["provaveis"] == 2
    assert r.context["links"][0]["primeiro_provavel_momento"] is not None
    assert r.context["resumo"] == RESUMO_REAL["grupos"]
    p = metricas.calls.last.request.url.params
    assert p["site_id"] == "site-do-host" and p["de"] == "2026-10-01" and p["ate"] == "2026-10-09"
    assert p["agrupar"] == "destino" and p["base"] == "enviados" and p["horas"] == "24"
    # CSV: cada coluna lê a chave certa do JSON real
    linhas = c.get(reverse("destinos_rastreados_exportar")).content.decode("utf-8-sig").splitlines()
    [cabecalho, valores] = list(csv.reader(linhas[:2]))
    linha = dict(zip(cabecalho, valores))
    assert linha["token"] == "3z4rcifp61" and linha["url_curta"] == LINK_REAL["url_curta"]
    assert linha["destino"] == "https://loja.exemplo/p" and linha["versao"] == "1"
    assert linha["acessos_total"] == "3" and linha["acessos_provaveis"] == "2"
    assert linha["acessos_automaticos"] == "1" and linha["primeiro_provavel_em"] == LINK_REAL["acessos"]["primeiro_provavel_em"]
    assert linha["conversa_id"] == LINK_REAL["conversa_id"] and linha["mensagem_id"] == ""


@respx.mock
def test_encaixe_escritas_com_site_na_query_e_no_corpo_e_resposta_real():
    novo = {k: v for k, v in DESTINO_REAL.items() if k not in ("links_enviados", "acessos_provaveis")}
    criar = respx.post(MENSAGERIA + "/links/destinos").respond(201, json=novo)
    versao = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/versoes").respond(201, json={"numero": 2, "url": "https://novo.com"})
    arquivar = respx.post(MENSAGERIA + f"/links/destinos/{DESTINO}/arquivar").respond(200, json={"arquivado_em": "2026-10-09T17:40:55.325342+00:00"})
    c = dentro()
    assert c.post(reverse("destinos_rastreados_novo"), {"nome": "Nome", "url": "https://x.y/n"}).url.endswith("?feito=criado")
    assert c.post(reverse("destinos_rastreados_versao", args=[DESTINO]), {"url": "https://novo.com"}).url.endswith("?feito=versao")
    assert c.post(reverse("destinos_rastreados_arquivar", args=[DESTINO]), {"acao": "arquivar"}).url.endswith("?feito=arquivado")
    assert set(json.loads(criar.calls.last.request.content)) == {"site_id", "nome", "url", "criada_por"}
    assert set(json.loads(versao.calls.last.request.content)) == {"site_id", "url", "criada_por"}
    assert versao.calls.last.request.url.params["site_id"] == "site-do-host"
    assert arquivar.calls.last.request.url.params["site_id"] == "site-do-host"
    assert json.loads(arquivar.calls.last.request.content) == {"site_id": "site-do-host"}
    assert criar.calls.last.request.headers["Authorization"] == "Bearer mensageria-test"


@respx.mock
def test_nome_longo_nao_estoura_a_auditoria():
    respx.post(MENSAGERIA + "/links/destinos").respond(201, json={"id": DESTINO})
    r = dentro().post(reverse("destinos_rastreados_novo"), {"nome": "N" * 100, "url": "https://exemplo.com/x"})
    assert r.status_code == 302 and r.url.endswith("?feito=criado")
    assert Registro.objects.get().alvo == "N" * 64


@respx.mock
def test_destino_sem_id_valido_e_descartado_sem_500():
    leituras(destinos=[destino(id="nao-e-uuid"), {"nome": "x"}])
    resumo_ok()
    r = dentro().get(reverse("destinos_rastreados"))
    assert r.status_code == 200


@respx.mock
def test_arquivados_volta_no_filtro_e_so_ate_diz_30_dias():
    leituras()
    resumo_ok()
    html = dentro().get(reverse("destinos_rastreados"), {"arquivados": "1", "ate": "2026-10-01"}).content.decode()
    assert 'name="arquivados" value="1"' in html and "30 dias até 2026-10-01" in html
