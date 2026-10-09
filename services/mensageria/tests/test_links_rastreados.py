"""Links rastreados de WhatsApp: reescrita, acesso, classificação e API."""
import json
import re
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.test import Client
from django.utils import timezone

from apps.conversas import envio
from apps.conversas.models import Conversa, MensagemDaConversa
from apps.jornadas import despacho
from apps.jornadas.models import OutboxEvent
from apps.links import servico
from apps.links.classificacao import classificar
from apps.links.models import Acesso, Destino, LinkIndividual
from apps.whatsapp.models import ConfiguracaoWhatsApp

from test_jornadas_whatsapp import _entrega, _liberar

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-a"
OUTRO = "site-b"
LEITURA = "token-leitura-links"
ESCRITA = "token-escrita-links"
BASE = "https://meshcraft.top/r/"
MEUS = dict(site_id=SITE, origem="manual")


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.TOKENS_SOMENTE_LEITURA = {LEITURA}
    settings.TOKENS_PUBLICACAO = {ESCRITA}
    settings.LINKS_URL_BASE = BASE
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    # O relay publica no Redis; aqui só interessa a linha da outbox.
    monkeypatch.setattr("apps.jornadas.tasks.relay_apos_commit", lambda: None)


def _reescrever(texto, referencia="r1", **extra):
    return servico.reescrever(texto, referencia=referencia, **{**MEUS, **extra})


def _tokens(texto):
    return re.findall(re.escape(BASE) + r"([a-z0-9]+)", texto)


# ---------------------------------------------------------------------------
# Reescrita
# ---------------------------------------------------------------------------


def test_uma_url_vira_link_curto_com_url_original_byte_a_byte():
    url = "https://x.y/z?a=1&b=2"
    novo, links = _reescrever(f"veja {url} agora")
    [token] = _tokens(novo)
    assert len(token) == 10 and re.fullmatch(r"[a-z0-9]{10}", token)
    assert novo == f"veja {BASE}{token} agora"
    [link] = links
    assert link.url_original == url and link.token == token
    assert link.destino.versao_atual.url == url and link.destino.origem == "automatico"


def test_repetir_a_chamada_devolve_os_mesmos_tokens_sem_duplicar():
    primeiro, _ = _reescrever("oi https://x.y/z")
    segundo, _ = _reescrever("oi https://x.y/z")
    assert primeiro == segundo and LinkIndividual.objects.count() == 1
    assert Destino.objects.count() == 1


def test_varias_urls_e_url_repetida_no_texto():
    novo, links = _reescrever("a https://x.y/1 b https://x.y/2 c https://x.y/1")
    tokens = _tokens(novo)
    assert len(tokens) == 3 and len(set(tokens)) == 2 and len(links) == 2
    assert tokens[0] == tokens[2] and LinkIndividual.objects.count() == 2


def test_url_que_ja_e_link_curto_nao_e_reescrita():
    texto = f"veja {BASE}abcde12345 e https://x.y/z"
    novo, links = _reescrever(texto)
    assert f"{BASE}abcde12345" in novo and len(links) == 1
    assert LinkIndividual.objects.filter(token="abcde12345").count() == 0


def test_pontuacao_final_fica_fora_do_link():
    novo, [link] = _reescrever("veja https://x.y/z.")
    assert novo == f"veja {BASE}{link.token}." and link.url_original == "https://x.y/z"
    novo, [link] = _reescrever("(veja https://x.y/w)", referencia="r2")
    assert novo == f"(veja {BASE}{link.token})"


def test_isolamento_entre_sites():
    _, [a] = servico.reescrever("https://x.y/z", site_id=SITE, origem="manual", referencia="r")
    _, [b] = servico.reescrever("https://x.y/z", site_id=OUTRO, origem="manual", referencia="r")
    servico.marcar_enviados([a, b])
    assert a.token != b.token and a.destino_id != b.destino_id
    resposta = _get(f"/links?site_id={SITE}").json()
    assert [i["id"] for i in resposta["itens"]] == [str(a.pk)] and resposta["total"] == 1


def test_destino_existente_do_site_e_reaproveitado():
    _, [a] = _reescrever("https://x.y/z", referencia="r1")
    _, [b] = _reescrever("https://x.y/z", referencia="r2")
    assert a.token != b.token and a.destino_id == b.destino_id


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metodo,agente,accept,esperado", [
    ("HEAD", "Mozilla/5.0", "text/html", "automatico"),
    ("GET", "WhatsApp/2.23.20 A", "*/*", "automatico"),
    ("GET", "facebookexternalhit/1.1", "text/html", "automatico"),
    ("GET", "Mozilla/5.0 (iPhone) Safari", "text/html,application/xhtml+xml", "provavel"),
    ("GET", "", "text/html", "indeterminado"),
    ("GET", "Outro/1.0", "text/html", "indeterminado"),
])
def test_classificacao(metodo, agente, accept, esperado):
    classe, motivo = classificar(metodo, agente, accept)
    assert classe == esperado and motivo


# ---------------------------------------------------------------------------
# Acesso e destino
# ---------------------------------------------------------------------------


def test_registrar_acesso_cria_acesso_evento_e_devolve_destino():
    _, [link] = _reescrever("https://x.y/z?a=1&b=2")
    resposta = servico.registrar_acesso(link.token, metodo="GET", user_agent="Mozilla/5.0", accept="text/html")
    assert resposta == {"destino": "https://x.y/z?a=1&b=2", "classificacao": "provavel",
                        "motivo": "navegador com text/html"}
    assert Acesso.objects.filter(link=link).count() == 1
    evento = OutboxEvent.objects.get(event="link.acessado")
    assert evento.payload["token"] == link.token and evento.payload["classificacao"] == "provavel"
    assert "user_agent" not in evento.payload and "telefone" not in evento.payload
    assert servico.registrar_acesso("naoexiste00", metodo="GET", user_agent="", accept="") is None


def test_nova_versao_do_destino_muda_o_destino_devolvido():
    _, [link] = _reescrever("https://x.y/velho")
    r = _post(f"/links/destinos/{link.destino_id}/versoes", {"url": "https://x.y/novo", "criada_por": "ana",
                                                           "site_id": SITE}, ESCRITA)
    assert r.status_code == 201 and r.json() == {"numero": 2, "url": "https://x.y/novo"}
    resposta = servico.registrar_acesso(link.token, metodo="GET", user_agent="", accept="")
    assert resposta["destino"] == "https://x.y/novo"
    assert link.url_original == "https://x.y/velho"


# ---------------------------------------------------------------------------
# Envio: conversa, manual, jornada
# ---------------------------------------------------------------------------


def _gateway(monkeypatch, posts):
    def gateway(metodo, caminho, dados=None):
        if metodo == "GET":
            return {"instance": {"state": "open"}}
        posts.append((caminho, dados))
        return {"key": {"id": f"wamid-{len(posts)}"}}

    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)


def _conversa():
    ConfiguracaoWhatsApp.objects.create(site_id=SITE, instancia="inst", ativo=True)
    return Conversa.objects.create(site_id=SITE, canal="whatsapp", endereco="5511988887777",
                                   janela_aberta_ate=timezone.now() + timedelta(hours=2))


def test_envio_pela_conversa_reescreve_vincula_e_emite_uma_vez(monkeypatch):
    posts = []
    _gateway(monkeypatch, posts)
    conversa = _conversa()
    for _ in range(2):
        r = envio.enviar(conversa=conversa, texto="Veja https://x.y/z?a=1&b=2.", chave_idempotencia="k1",
                         autor="pessoa")
    mensagem = MensagemDaConversa.objects.get()
    [link] = LinkIndividual.objects.all()
    assert mensagem.texto == f"Veja {BASE}{link.token}."
    assert link.mensagem_id == mensagem.pk and link.conversa_id == conversa.pk
    assert link.url_original == "https://x.y/z?a=1&b=2" and link.enviado_em is not None
    assert OutboxEvent.objects.filter(event="link.enviado").count() == 1
    evento = OutboxEvent.objects.get(event="link.enviado")
    assert evento.payload["mensagem_id"] == str(mensagem.pk) and evento.payload["token"] == link.token
    assert len(posts) == 1 and link.token in posts[0][1]["text"]


def test_modelo_aprovado_nao_e_reescrito(monkeypatch):
    posts = []
    _gateway(monkeypatch, posts)
    conversa = _conversa()
    envio.enviar(conversa=conversa, texto="Veja https://x.y/z", chave_idempotencia="k2", autor="pessoa",
                 modelo={"nome": "boas_vindas"})
    assert LinkIndividual.objects.count() == 0
    assert MensagemDaConversa.objects.get().texto == "Veja https://x.y/z"


def test_envio_manual_reescreve(monkeypatch):
    posts = []
    _gateway(monkeypatch, posts)
    ConfiguracaoWhatsApp.objects.create(site_id=SITE, instancia="inst", ativo=True)
    r = _post(f"/whatsapp/{SITE}/send", {"destinatario": "5511988887777", "corpo": "oi https://x.y/m",
                                         "referencia": "manual-1"}, ESCRITA)
    assert r.status_code == 200
    [link] = LinkIndividual.objects.all()
    assert link.origem == "manual" and link.referencia == "manual-1" and link.enviado_em is not None
    assert link.token in posts[0][1]["text"] and "https://x.y/m" not in posts[0][1]["text"]


def test_despacho_de_jornada_reescreve(monkeypatch):
    from apps.consentimentos.servico import registrar
    from apps.whatsapp import service

    entrega = _entrega()
    # Texto publicado é imutável no banco; troca o que o despacho lê.
    monkeypatch.setattr(despacho, "_texto", lambda passo, idioma: "Aula https://x.y/aula?a=1&b=2")
    registrar(site_id=entrega.inscricao.site_id, telefone="+55 11 90000-0001", aceito=True,
              origem="quiz.completado")
    _liberar(monkeypatch)
    monkeypatch.setattr(despacho, "_telefone_da_pessoa", lambda **k: ("+55 11 90000-0001", "pt-br", ""))
    enviados = []

    def enviar_mensagem(**kwargs):
        enviados.append(kwargs)
        return SimpleNamespace(status="aceito", erro="")

    monkeypatch.setattr(service, "consultar_mensagem", lambda **k: None)
    monkeypatch.setattr(service, "enviar_mensagem", enviar_mensagem)
    despacho.processar_entrega(inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id)
    [link] = LinkIndividual.objects.all()
    assert link.origem == "jornada" and link.passo_id == entrega.passo_id
    assert link.jornada_slug == entrega.inscricao.jornada.slug and link.enviado_em is not None
    assert enviados[0]["corpo"] == f"Aula {BASE}{link.token}"
    assert OutboxEvent.objects.filter(event="link.enviado").count() == 1


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _cab(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}


def _get(caminho, token=LEITURA):
    return Client().get("/api/mensageria" + caminho, **_cab(token))


def _post(caminho, corpo, token=LEITURA):
    return Client().post("/api/mensageria" + caminho, json.dumps(corpo), content_type="application/json",
                         **_cab(token))


def test_api_acesso_com_token_de_leitura_desconhecido_e_sem_token():
    _, [link] = _reescrever("https://x.y/z")
    corpo = {"metodo": "GET", "user_agent": "Mozilla/5.0", "accept": "text/html"}
    r = _post(f"/links/{link.token}/acesso", corpo)
    assert r.status_code == 200 and r.json()["destino"] == "https://x.y/z"
    assert r.json()["classificacao"] == "provavel"
    r = _post("/links/naoexiste00/acesso", corpo)
    assert r.status_code == 404 and r.json() == {"detail": "link desconhecido"}
    assert _post(f"/links/{link.token}/acesso", corpo, token=None).status_code == 401


def test_api_destinos_escrita_exige_publicacao():
    corpo = {"site_id": SITE, "nome": "Oferta", "url": "https://x.y/oferta", "criada_por": "ana"}
    assert _post("/links/destinos", corpo, LEITURA).status_code == 403
    r = _post("/links/destinos", corpo, ESCRITA)
    assert r.status_code == 201 and r.json()["url_atual"] == "https://x.y/oferta"
    destino_id = r.json()["id"]
    assert _post(f"/links/destinos/{destino_id}/arquivar", {"site_id": SITE}, LEITURA).status_code == 403
    assert _post(f"/links/destinos/{destino_id}/arquivar", {"site_id": SITE}, ESCRITA).json()["arquivado_em"]
    assert _post(f"/links/destinos/{destino_id}/arquivar", {"site_id": OUTRO}, ESCRITA).status_code == 404
    assert _get(f"/links/destinos?site_id={SITE}").json()["itens"] == []
    lista = _get(f"/links/destinos?site_id={SITE}&incluir_arquivados=1").json()["itens"]
    assert [d["id"] for d in lista] == [destino_id] and lista[0]["versoes"][0]["numero"] == 1
    assert _post(f"/links/destinos/{destino_id}/desarquivar", {"site_id": SITE}, ESCRITA).json() == {
        "arquivado_em": None}


def test_api_lista_com_filtros_de_situacao_e_conversa():
    conversa = _conversa()
    _, [com] = servico.reescrever("https://x.y/1", site_id=SITE, origem="conversa", referencia="a",
                                  conversa_id=conversa.pk)
    _, [sem] = servico.reescrever("https://x.y/2", site_id=SITE, origem="manual", referencia="b")
    servico.marcar_enviados([com, sem])
    servico.registrar_acesso(com.token, metodo="GET", user_agent="Mozilla/5.0", accept="text/html")
    servico.registrar_acesso(sem.token, metodo="HEAD", user_agent="WhatsApp/2", accept="")

    def ids(consulta):
        return {i["id"] for i in _get(f"/links?site_id={SITE}&{consulta}").json()["itens"]}

    assert ids("situacao=com_acesso_provavel") == {str(com.pk)}
    assert ids("situacao=todos") == {str(com.pk), str(sem.pk)}
    assert ids(f"conversa_id={conversa.pk}") == {str(com.pk)}
    item = next(i for i in _get(f"/links?site_id={SITE}").json()["itens"] if i["id"] == str(com.pk))
    assert item["acessos"]["provaveis"] == 1 and item["url_curta"] == BASE + com.token
    assert item["acessos"]["primeiro_provavel_em"]
    assert _get("/links").status_code == 422
    acessos = _get(f"/links/{sem.pk}/acessos?site_id={SITE}").json()["acessos"]
    assert acessos[0]["classificacao"] == "automatico" and acessos[0]["metodo"] == "HEAD"
    assert _get(f"/links/{sem.pk}/acessos?site_id={OUTRO}").status_code == 404
    sem_acesso = {i["id"] for i in _get(f"/links?site_id={SITE}&situacao=sem_acesso").json()["itens"]}
    # Prévia automática do WhatsApp não conta como acesso: continua "sem acesso".
    assert sem_acesso == {str(sem.pk)}


def test_url_maior_que_o_limite_fica_como_esta_sem_rastreio():
    longa = "https://x.y/" + "a" * 2100
    texto, links = _reescrever(f"veja {longa} ok")
    assert texto == f"veja {longa} ok" and links == []


@pytest.mark.parametrize("final", ["*", "_", "!", "?", ":", "~"])
def test_marca_de_formatacao_e_pontuacao_ficam_fora_da_url(final):
    texto, [link] = _reescrever(f"veja {'*' if final == '*' else ''}https://x.y/a{final} ok")
    assert link.url_original == "https://x.y/a"
    assert texto.endswith(f"{BASE}{link.token}{final} ok")


def test_nome_do_destino_automatico_nao_leva_query_string():
    _, [link] = _reescrever("https://x.y/1?email=a@b.c#frag")
    assert link.destino.nome == "https://x.y/1" and link.url_original == "https://x.y/1?email=a@b.c#frag"


def test_lista_nao_mostra_link_que_nunca_saiu():
    _reescrever("https://x.y/nunca")
    assert _get(f"/links?site_id={SITE}").json()["total"] == 0


def test_enviado_desconhecido_vira_enviado_na_chamada_repetida(monkeypatch):
    from apps.whatsapp.models import MensagemWhatsApp

    def gateway(metodo, caminho, dados=None):
        return {"instance": {"state": "open"}} if metodo == "GET" else {}  # sem key.id: "desconhecido"

    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)
    conversa = _conversa()
    r = envio.enviar(conversa=conversa, texto="Veja https://x.y/d", chave_idempotencia="kd", autor="pessoa")
    assert r.mensagem.estado_envio == "desconhecido"
    [link] = LinkIndividual.objects.all()
    assert link.enviado_em is None and OutboxEvent.objects.filter(event="link.enviado").count() == 0
    # O webhook confirma depois: a mensagem passa a "enviado".
    MensagemWhatsApp.objects.update(status="enviado")
    r = envio.enviar(conversa=conversa, texto="Veja https://x.y/d", chave_idempotencia="kd", autor="pessoa")
    assert r.resultado == "repetida"
    link.refresh_from_db()
    assert link.enviado_em is not None
    assert OutboxEvent.objects.filter(event="link.enviado").count() == 1


def test_parentese_balanceado_fica_na_url_e_https_sem_endereco_nao_vira_link():
    _, [link] = _reescrever("wiki https://en.wikipedia.org/wiki/Foo_(bar) fim")
    assert link.url_original == "https://en.wikipedia.org/wiki/Foo_(bar)"
    texto, [link2] = _reescrever("(veja https://x.y/p)", referencia="r2")
    assert link2.url_original == "https://x.y/p" and texto.endswith(f"{BASE}{link2.token})")
    texto, links = _reescrever("veja https://. fim", referencia="r3")
    assert links == [] and texto == "veja https://. fim"


def test_acesso_nao_chama_o_relay_e_nul_vira_422(monkeypatch):
    from apps.jornadas import tasks

    _, [link] = _reescrever("https://x.y/n")
    chamadas = []
    monkeypatch.setattr(tasks, "relay_apos_commit", lambda *a, **k: chamadas.append(1))
    servico.registrar_acesso(link.token, metodo="GET", user_agent="Mozilla/5.0", accept="text/html")
    assert chamadas == [] and OutboxEvent.objects.filter(event="link.acessado").count() == 1
    resposta = _post(f"/links/{link.token}/acesso", {"metodo": "GET", "user_agent": "Moz\x00illa", "accept": ""})
    assert resposta.status_code == 200
    assert _post("/links/destinos", {"site_id": SITE, "nome": "n", "url": "https://x.y/\x00a"},
                 ESCRITA).status_code == 422


def test_destino_automatico_de_mensagem_recusada_nao_aparece_na_lista(monkeypatch):
    _gateway(monkeypatch, [])
    conversa = _conversa()
    Conversa.objects.filter(pk=conversa.pk).update(janela_aberta_ate=timezone.now() - timedelta(hours=1))
    conversa.refresh_from_db()
    r = envio.enviar(conversa=conversa, texto="Veja https://x.y/recusada", chave_idempotencia="kr", autor="pessoa")
    assert r.resultado == "fora_da_janela" and LinkIndividual.objects.count() == 1
    assert _get(f"/links/destinos?site_id={SITE}").json()["itens"] == []


# ---------------------------------------------------------------------------
# Encaixe com os consumidores (funil, admin, métricas)
# ---------------------------------------------------------------------------
# Os consumidores copiam o JSON REAL destas respostas e destes eventos como mock
# nos testes deles. Este teste trava a forma exata: se a API mudar uma chave, ele
# quebra aqui e avisa que os três precisam acompanhar.


def test_forma_real_da_api_e_dos_eventos_que_os_consumidores_copiam():
    conversa = _conversa()
    _, [link] = servico.reescrever("https://loja.exemplo/p?a=1&b=x%20y#fim", site_id=SITE, origem="conversa",
                                   referencia="ref-1", conversa_id=conversa.pk, jornada_slug="boas-vindas")
    servico.marcar_enviados([link])
    acesso = _post(f"/links/{link.token}/acesso",
                   {"metodo": "GET", "user_agent": "Mozilla/5.0", "accept": "text/html"}).json()
    servico.registrar_acesso(link.token, metodo="HEAD", user_agent="WhatsApp/2", accept="")

    assert acesso == {"destino": "https://loja.exemplo/p?a=1&b=x%20y#fim", "classificacao": "provavel",
                      "motivo": "navegador com text/html"}

    lista = _get(f"/links?site_id={SITE}").json()
    assert set(lista) == {"itens", "total"} and lista["total"] == 1
    item = lista["itens"][0]
    assert set(item) == {"id", "token", "url_curta", "url_original", "destino", "versao", "origem", "referencia",
                         "campanha", "conversa_id", "mensagem_id", "passo_id", "criado_em", "enviado_em", "acessos"}
    assert set(item["destino"]) == {"id", "nome"}
    assert set(item["acessos"]) == {"total", "provaveis", "automaticos", "indeterminados",
                                    "primeiro_provavel_em", "ultimo_em"}
    assert item["acessos"]["total"] == 2 and item["url_curta"] == BASE + link.token

    destinos = _get(f"/links/destinos?site_id={SITE}").json()
    assert set(destinos) == {"itens"}
    assert set(destinos["itens"][0]) == {"id", "nome", "origem", "url_atual", "versao_atual", "arquivado_em",
                                         "criado_em", "versoes", "links_enviados", "acessos_provaveis"}
    assert set(destinos["itens"][0]["versoes"][0]) == {"numero", "url", "criada_em", "criada_por"}

    acessos = _get(f"/links/{link.pk}/acessos?site_id={SITE}").json()
    assert set(acessos) == {"acessos"}
    assert set(acessos["acessos"][0]) == {"ocorrido_em", "metodo", "classificacao", "motivo", "user_agent"}

    enviado = OutboxEvent.objects.get(event="link.enviado").payload
    assert set(enviado) == {"site_id", "link_id", "token", "destino_id", "destino_nome", "versao", "origem",
                            "referencia", "campanha", "conversa_id", "mensagem_id", "passo_id", "enviado_em"}
    for evento in OutboxEvent.objects.filter(event="link.acessado"):
        assert set(evento.payload) == {"site_id", "link_id", "token", "destino_id", "versao", "origem", "campanha",
                                       "mensagem_id", "passo_id", "classificacao", "motivo", "metodo", "ocorrido_em"}
