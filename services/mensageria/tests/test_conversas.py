"""Caixa de entrada conversacional: WhatsApp e e-mail nos dois sentidos."""
import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.conversas import enderecos, leads
from apps.conversas.models import Conversa, Descadastro, MensagemDaConversa
from apps.jornadas.models import OutboxEvent, Preferencia
from apps.whatsapp.models import ConfiguracaoWhatsApp, MensagemWhatsApp

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-abc"
LEITURA = "token-leitura-conversas"
ESCRITA = "token-escrita-conversas"
LEAD_A = "11111111-1111-1111-1111-111111111111"
LEAD_B = "22222222-2222-2222-2222-222222222222"


class Resposta:
    def __init__(self, status, dados):
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


@pytest.fixture
def base(settings, monkeypatch):
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    settings.WHATSAPP_WEBHOOK_TOKEN = "retorno-local"
    settings.WHATSAPP_CLOUD_VERIFY_TOKEN = "verifica-local"
    settings.WHATSAPP_CLOUD_APP_SECRET = "segredo-do-app"
    settings.EMAIL_ENTRADA_TOKEN = "entrada-local"
    settings.LEADS_API_URL = "http://leads:8000/api/leads"
    settings.LEADS_API_TOKEN = "par-mensageria"
    settings.TOKENS_SOMENTE_LEITURA = {LEITURA}
    settings.TOKENS_PUBLICACAO = {ESCRITA}
    contatos = []
    pedidos = []

    def get(url, params=None, headers=None, timeout=None):
        pedidos.append((url, dict(params or {})))
        assert headers == {"Authorization": "Bearer par-mensageria"}
        if url.endswith("/leads"):
            q = params["q"].lower()
            itens = [c for c in contatos
                     if (not params.get("site_id") or c["site_id"] == params["site_id"])
                     and (q in c["telefone"].lower() or q in c["email"].lower())]
            return Resposta(200, {"itens": itens, "tem_mais": False})
        lead_id = url.rsplit("/", 1)[-1]
        achado = next((c for c in contatos if c["id"] == lead_id), None)
        return Resposta(200, achado) if achado else Resposta(404, {})

    monkeypatch.setattr("apps.conversas.leads.httpx.get", get)
    config = ConfiguracaoWhatsApp.objects.create(site_id=SITE, instancia="inst-abc", ativo=True)
    return {"contatos": contatos, "pedidos": pedidos, "config": config}


def _upsert(cliente, item, instancia="inst-abc", token="retorno-local"):
    corpo = {"event": "messages.upsert", "instance": instancia, "data": item}
    extra = {"HTTP_X_WEBHOOK_TOKEN": token} if token else {}
    return cliente.post("/webhooks/whatsapp", json.dumps(corpo), content_type="application/json", **extra)


def _item(texto="Oi, quero saber do curso", ident="ABC1", jid="5511988887777@s.whatsapp.net", **extra):
    item = {"key": {"remoteJid": jid, "fromMe": False, "id": ident},
            "message": {"conversation": texto}, "messageType": "conversation",
            "messageTimestamp": int(timezone.now().timestamp())}
    item.update(extra)
    return item


def _api(cliente, metodo, caminho, corpo=None, token=ESCRITA):
    cabecalho = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    url = "/api/mensageria" + caminho
    if metodo == "GET":
        return cliente.get(url, **cabecalho)
    return cliente.post(url, json.dumps(corpo or {}), content_type="application/json", **cabecalho)


def _gateway_aberto(monkeypatch, posts):
    def gateway(metodo, caminho, dados=None):
        if metodo == "GET":
            return {"instance": {"state": "open"}}
        posts.append((caminho, dados))
        return {"key": {"id": f"wamid-{len(posts)}"}}

    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)


# ---------------------------------------------------------------------------
# Entrada do WhatsApp (Evolution)
# ---------------------------------------------------------------------------


def test_texto_do_whatsapp_abre_conversa_liga_lead_e_publica_evento(base):
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "ana@exemplo.com",
                             "telefone": "(11) 98888-7777"})
    resposta = _upsert(Client(), _item())
    assert resposta.status_code == 200 and resposta.json() == {"recebidas": 1}
    conversa = Conversa.objects.get()
    assert (conversa.site_id, conversa.canal, conversa.endereco) == (SITE, "whatsapp", "5511988887777")
    assert conversa.ligacao == "ligada" and conversa.lead_id == LEAD_A
    assert conversa.estado == "agente" and conversa.caixa == "inst-abc"
    assert conversa.janela_aberta_ate - conversa.ultima_entrada_em == timedelta(hours=24)
    mensagem = MensagemDaConversa.objects.get()
    assert (mensagem.direcao, mensagem.autor, mensagem.estado_envio) == ("entrada", "lead", "recebida")
    evento = OutboxEvent.objects.get(event="mensagem.recebida")
    assert evento.payload["conversa_id"] == str(conversa.id)
    assert evento.payload["canal"] == "whatsapp" and evento.payload["site"] == SITE
    assert evento.payload["lead"] == LEAD_A and evento.payload["texto"] == "Oi, quero saber do curso"
    assert evento.payload["midia"] is None and evento.payload["descadastro"] is False
    # Busca pela lista do CRM: só quiz, só o site da instância.
    assert base["pedidos"][0][1]["origem"] == "quiz" and base["pedidos"][0][1]["site_id"] == SITE


def test_entrega_repetida_nao_duplica_mensagem_nem_evento(base):
    cliente = Client()
    assert _upsert(cliente, _item()).json() == {"recebidas": 1}
    assert _upsert(cliente, _item()).json() == {"recebidas": 0}
    assert MensagemDaConversa.objects.count() == 1
    assert OutboxEvent.objects.filter(event="mensagem.recebida").count() == 1


def test_webhook_sem_token_ou_instancia_alheia_recusa(base):
    cliente = Client()
    assert _upsert(cliente, _item(), token=None).status_code == 403
    assert _upsert(cliente, _item(), instancia="inst-de-outro").status_code == 404
    assert not Conversa.objects.exists()


def test_proprio_aparelho_grupo_e_reacao_nao_viram_conversa(base):
    cliente = Client()
    proprio = _item(ident="P1")
    proprio["key"]["fromMe"] = True
    grupo = _item(ident="G1", jid="1203630@g.us")
    reacao = _item(ident="R1")
    reacao["message"] = {"reactionMessage": {"text": "👍"}}
    for item in (proprio, grupo, reacao):
        assert _upsert(cliente, item).json() == {"recebidas": 0}
    assert not Conversa.objects.exists()


def test_audio_e_imagem_chegam_como_referencia_de_midia(base):
    cliente = Client()
    audio = _item(ident="AUD1")
    audio["message"] = {"audioMessage": {"url": "https://mmg.whatsapp.net/x", "mimetype": "audio/ogg; codecs=opus",
                                         "seconds": 7, "ptt": True}}
    imagem = _item(ident="IMG1")
    imagem["message"] = {"imageMessage": {"mimetype": "image/jpeg", "caption": "meu trabalho"}}
    assert _upsert(cliente, audio).json() == {"recebidas": 1}
    assert _upsert(cliente, imagem).json() == {"recebidas": 1}
    recebido = MensagemDaConversa.objects.get(id_externo="AUD1")
    assert (recebido.midia_tipo, recebido.midia_mime) == ("audio", "audio/ogg; codecs=opus")
    assert recebido.midia_referencia == "evolution:inst-abc:AUD1" and recebido.texto == ""
    foto = MensagemDaConversa.objects.get(id_externo="IMG1")
    assert (foto.midia_tipo, foto.texto) == ("imagem", "meu trabalho")
    evento = OutboxEvent.objects.filter(event="mensagem.recebida").order_by("id").first()
    assert evento.payload["midia"] == {"tipo": "audio", "referencia": "evolution:inst-abc:AUD1",
                                       "mime": "audio/ogg; codecs=opus"}


def test_numero_lid_usa_o_telefone_alternativo(base):
    item = _item(jid="123456789@lid")
    item["key"]["senderPn"] = "5511988887777@s.whatsapp.net"
    assert _upsert(Client(), item).json() == {"recebidas": 1}
    assert Conversa.objects.get().endereco == "5511988887777"


def test_conectar_assina_mensagens_recebidas(base, settings, monkeypatch):
    from apps.whatsapp.service import conectar

    settings.WHATSAPP_WEBHOOK_URL = "http://aplicacao:8000/webhooks/whatsapp"
    webhooks = []

    def gateway(metodo, caminho, dados=None):
        if caminho.startswith("webhook/set/"):
            webhooks.append(dados)
        return {"instance": {"state": "open"}} if "connectionState" in caminho else {}

    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)
    conectar(SITE)
    assert "MESSAGES_UPSERT" in webhooks[0]["webhook"]["events"]


# ---------------------------------------------------------------------------
# Ligação com o lead
# ---------------------------------------------------------------------------


def test_numero_sem_nono_digito_liga_ao_mesmo_contato(base):
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "a@b.com", "telefone": "+55 (11) 9 8888-7777"})
    assert leads.procurar(site_id=SITE, canal="whatsapp", endereco="551188887777").lead_id == LEAD_A
    assert enderecos.chave_telefone("11988887777") == enderecos.chave_telefone("551188887777")


def test_telefone_de_dois_contatos_fica_ambiguo_sem_dados_de_ninguem(base):
    base["contatos"] += [
        {"id": LEAD_A, "site_id": SITE, "email": "ana@b.com", "telefone": "11988887777"},
        {"id": LEAD_B, "site_id": SITE, "email": "bia@b.com", "telefone": "(11) 98888-7777"},
    ]
    _upsert(Client(), _item())
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ambigua" and conversa.lead_id == ""
    assert OutboxEvent.objects.get().payload["lead"] is None
    dados = _api(Client(), "GET", f"/conversas/{conversa.id}?site_id={SITE}", token=LEITURA).json()
    assert dados["ambigua"] is True and dados["lead_id"] is None
    corpo = json.dumps(dados)
    assert "ana@b.com" not in corpo and "bia@b.com" not in corpo and LEAD_B not in corpo


def test_desconhecido_fica_fora_da_lista_comercial(base):
    _upsert(Client(), _item())
    cliente = Client()
    assert Conversa.objects.get().ligacao == "desconhecida"
    assert _api(cliente, "GET", f"/conversas?site_id={SITE}", token=LEITURA).json()["total"] == 0
    todas = _api(cliente, "GET", f"/conversas?site_id={SITE}&ligacao=todas", token=LEITURA).json()
    assert todas["total"] == 1 and todas["itens"][0]["endereco_mascarado"].endswith("7777")
    assert "5511988887777" not in json.dumps(todas)


def test_leads_fora_do_ar_deixa_pendente_e_liga_na_proxima_mensagem(base, settings):
    settings.LEADS_API_TOKEN = ""
    cliente = Client()
    _upsert(cliente, _item(ident="1"))
    assert Conversa.objects.get().ligacao == "pendente"
    settings.LEADS_API_TOKEN = "par-mensageria"
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "a@b.com", "telefone": "11988887777"})
    _upsert(cliente, _item(ident="2", texto="oi de novo"))
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ligada" and conversa.lead_id == LEAD_A


def test_contato_de_outro_site_nao_liga(base):
    base["contatos"].append({"id": LEAD_A, "site_id": "outro-site", "email": "a@b.com", "telefone": "11988887777"})
    _upsert(Client(), _item())
    assert Conversa.objects.get().ligacao == "desconhecida"


# ---------------------------------------------------------------------------
# WhatsApp Business Platform (Cloud API oficial)
# ---------------------------------------------------------------------------


def _assinado(cliente, corpo, segredo="segredo-do-app"):
    bruto = json.dumps(corpo).encode()
    assinatura = "sha256=" + hmac.new(segredo.encode(), bruto, hashlib.sha256).hexdigest()
    return cliente.post("/webhooks/whatsapp/cloud", bruto, content_type="application/json",
                        HTTP_X_HUB_SIGNATURE_256=assinatura)


def _cloud(valor, numero_id="PNID-1"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{
        "field": "messages",
        "value": {"messaging_product": "whatsapp",
                  "metadata": {"display_phone_number": "5511900000000", "phone_number_id": numero_id},
                  **valor}}]}]}


def test_cloud_verificacao_hub_challenge(base):
    cliente = Client()
    ok = cliente.get("/webhooks/whatsapp/cloud", {"hub.mode": "subscribe", "hub.verify_token": "verifica-local",
                                                 "hub.challenge": "1158201444"})
    assert ok.status_code == 200 and ok.content == b"1158201444"
    errado = cliente.get("/webhooks/whatsapp/cloud", {"hub.mode": "subscribe", "hub.verify_token": "x",
                                                     "hub.challenge": "1"})
    assert errado.status_code == 403


def test_cloud_exige_assinatura_e_recebe_texto_audio_e_estados(base):
    ConfiguracaoWhatsApp.objects.create(site_id="site-cloud", instancia="PNID-1", ativo=True,
                                        transporte="WHATSAPP-BUSINESS")
    cliente = Client()
    corpo = _cloud({"contacts": [{"profile": {"name": "Ana"}, "wa_id": "5511977776666"}], "messages": [
        {"from": "5511977776666", "id": "wamid.T1", "timestamp": str(int(timezone.now().timestamp())),
         "type": "text", "text": {"body": "Quanto custa?"}},
        {"from": "5511977776666", "id": "wamid.A1", "timestamp": str(int(timezone.now().timestamp())),
         "type": "audio", "audio": {"id": "MEDIA-9", "mime_type": "audio/ogg; codecs=opus", "voice": True}},
    ]})
    assert _assinado(cliente, corpo, segredo="outro").status_code == 403
    resposta = _assinado(cliente, corpo)
    assert resposta.status_code == 200 and resposta.json()["recebidas"] == 2
    conversa = Conversa.objects.get(site_id="site-cloud")
    assert conversa.endereco == "5511977776666" and conversa.caixa == "PNID-1"
    audio = conversa.mensagens.get(id_externo="wamid.A1")
    assert (audio.midia_tipo, audio.midia_referencia) == ("audio", "cloud:MEDIA-9")
    enviada = MensagemWhatsApp.objects.create(site_id="site-cloud", instancia="PNID-1", origem="manual",
                                              referencia="r1", destinatario="5511977776666", corpo="x",
                                              provider_id="wamid.OUT", status="aceito")
    for estado in ("delivered", "sent", "read"):
        _assinado(cliente, _cloud({"statuses": [{"id": "wamid.OUT", "status": estado, "recipient_id": "5511977776666"}]}))
    enviada.refresh_from_db()
    assert enviada.status == "lido"
    # Número da Meta sem site configurado é ignorado sem erro (a Meta não repete).
    assert _assinado(cliente, _cloud({"messages": []}, numero_id="PNID-X")).json()["ignoradas"] == 1


# ---------------------------------------------------------------------------
# Entrada de e-mail
# ---------------------------------------------------------------------------


def _email(cliente, corpo, caminho="/webhooks/email/recebido", token="entrada-local"):
    extra = {"HTTP_X_WEBHOOK_TOKEN": token} if token else {}
    return cliente.post(caminho, json.dumps(corpo), content_type="application/json", **extra)


def test_email_recebido_liga_pelo_endereco_e_deduplica(base):
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "Ana@Exemplo.com", "telefone": ""})
    cliente = Client()
    corpo = {"from": "Ana <ana@exemplo.com>", "to": "contato@meshcraft.top", "subject": "Dúvida",
             "text": "Tem parcelamento?", "message-id": "<m1@mail>", "in-reply-to": ""}
    assert _email(cliente, corpo, token="errado").status_code == 403
    assert _email(cliente, corpo).json() == {"recebidas": 1, "ignoradas": 0}
    assert _email(cliente, corpo).json() == {"recebidas": 0, "ignoradas": 0}
    conversa = Conversa.objects.get()
    assert (conversa.site_id, conversa.canal, conversa.endereco) == (SITE, "email", "ana@exemplo.com")
    assert conversa.lead_id == LEAD_A and conversa.janela_aberta_ate is None
    mensagem = conversa.mensagens.get()
    assert (mensagem.assunto, mensagem.id_externo) == ("Dúvida", "<m1@mail>")
    assert OutboxEvent.objects.get().payload["canal"] == "email"


def test_email_no_formato_do_brevo_com_site_na_url(base):
    corpo = {"items": [{"From": {"Name": "Bia", "Address": "bia@exemplo.com"},
                        "To": [{"Address": "oi@site.com"}], "Subject": "Re: Proposta",
                        "RawTextBody": "Pode ser no pix?", "MessageId": "<b1@x>", "InReplyTo": "<nosso@x>"}]}
    assert _email(Client(), corpo, caminho="/webhooks/email/recebido/site-xyz").json()["recebidas"] == 1
    conversa = Conversa.objects.get()
    assert conversa.site_id == "site-xyz" and conversa.caixa == "oi@site.com"
    assert conversa.mensagens.get().em_resposta_a == "<nosso@x>"


def test_resposta_de_email_encontra_o_site_pela_mensagem_respondida(base, settings):
    settings.EMAIL_HOST, settings.DEFAULT_FROM_EMAIL = "smtp.teste", "equipe@meshcraft.top"
    cliente = Client()
    aberta = _api(cliente, "POST", "/conversas", {"site_id": SITE, "canal": "email", "lead_id": LEAD_A,
                                                  "endereco": "ana@exemplo.com"}).json()
    enviada = _api(cliente, "POST", f"/conversas/{aberta['id']}/mensagens",
                   {"site_id": SITE, "texto": "Olá Ana", "chave_idempotencia": "k1", "assunto": "Seu resultado"}).json()
    message_id = enviada["mensagem"]["id_externo"]
    assert enviada["resultado"] == "enviada" and message_id
    _email(cliente, {"from": "ana@exemplo.com", "to": "equipe@meshcraft.top", "subject": "Re: Seu resultado",
                     "text": "Obrigada!", "message_id": "<r1@x>", "in_reply_to": message_id})
    assert Conversa.objects.count() == 1
    assert Conversa.objects.get().mensagens.filter(direcao="entrada").count() == 1


# ---------------------------------------------------------------------------
# Descadastro
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("texto", ["PARAR", "Sair.", "stop!", "descadastrar", " Parar "])
def test_palavras_de_descadastro(texto):
    assert enderecos.pede_descadastro(texto)


@pytest.mark.parametrize("texto", ["não quero parar de estudar", "como faço para sair do grupo?", ""])
def test_frase_com_a_palavra_nao_e_descadastro(texto):
    assert not enderecos.pede_descadastro(texto)


def test_parar_grava_preferencia_barra_agendados_e_bloqueia_acompanhamento(base, settings, monkeypatch):
    from test_jornadas_whatsapp import _entrega
    from test_jornadas_motor import PESSOA

    entrega = _entrega()  # passo relacional pendente no WhatsApp, site-abc
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "ana@exemplo.com", "telefone": "11988887777"})
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "par-identidade")
    perguntas = []

    def post(url, json=None, headers=None, timeout=None):
        perguntas.append((url, json))
        return Resposta(200, {"id": PESSOA})

    monkeypatch.setattr("apps.conversas.descadastro.httpx.post", post)
    cliente = Client()
    _upsert(cliente, _item(texto="PARAR", ident="S1"))
    conversa = Conversa.objects.get()
    registro = Descadastro.objects.get()
    assert (registro.site_id, registro.canal, registro.endereco) == (SITE, "whatsapp", "5511988887777")
    assert registro.preferencia_registrada
    assert perguntas == [("http://identidade:8000/interno/pessoas/por-email", {"email": "ana@exemplo.com"})]
    prefs = Preferencia.objects.filter(destinatario_id=PESSOA, site_id=SITE, canal="whatsapp")
    assert {(p.classe, p.aceita) for p in prefs} == {("relacional", False), ("engajamento", False)}
    entrega.refresh_from_db()
    assert entrega.resultado == "barrada_por_preferencia"
    assert OutboxEvent.objects.get(event="mensagem.recebida").payload["descadastro"] is True
    posts = []
    _gateway_aberto(monkeypatch, posts)
    recusa = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                  {"site_id": SITE, "texto": "Última chance!", "chave_idempotencia": "seguimento-1"}).json()
    assert recusa["resultado"] == "descadastrado" and recusa["mensagem"] is None and not posts
    assert _api(cliente, "GET", f"/conversas/{conversa.id}?site_id={SITE}", token=LEITURA).json()["descadastrado"]
    # O contato volta a falar: responder à pergunta dele é atendimento, não acompanhamento.
    _upsert(cliente, _item(texto="Mudei de ideia, qual o preço?", ident="S2",
                           messageTimestamp=int(timezone.now().timestamp()) + 5))
    resposta = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                    {"site_id": SITE, "texto": "Custa R$ 97.", "chave_idempotencia": "resposta-1"}).json()
    assert resposta["resultado"] == "enviada" and len(posts) == 1


def test_descadastro_sem_identidade_fica_pendente_e_tarefa_retoma(base, monkeypatch):
    from apps.conversas.descadastro import aplicar_pendentes

    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "ana@exemplo.com", "telefone": "11988887777"})
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    _upsert(Client(), _item(texto="SAIR"))
    registro = Descadastro.objects.get()
    assert not registro.preferencia_registrada and "identidade" in registro.preferencia_motivo
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "par-identidade")
    monkeypatch.setattr("apps.conversas.descadastro.httpx.post",
                        lambda *a, **k: Resposta(200, {"id": "pessoa-x"}))
    assert aplicar_pendentes() == 1
    assert Preferencia.objects.filter(destinatario_id="pessoa-x", canal="whatsapp", aceita=False).count() == 2


def test_descadastro_por_email_pelo_assunto(base, monkeypatch):
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    _email(Client(), {"from": "ana@exemplo.com", "subject": "descadastrar", "text": "> mensagem antiga citada",
                      "message_id": "<d1@x>", "site_id": SITE})
    assert Descadastro.objects.get().canal == "email"


# ---------------------------------------------------------------------------
# APIs internas: listar, mensagens, enviar, assumir e devolver
# ---------------------------------------------------------------------------


def _conversa_ligada(base):
    base["contatos"].append({"id": LEAD_A, "site_id": SITE, "email": "ana@exemplo.com", "telefone": "11988887777"})
    _upsert(Client(), _item())
    return Conversa.objects.get()


def test_listar_por_lead_e_estado_e_ver_mensagens(base):
    conversa = _conversa_ligada(base)
    cliente = Client()
    por_lead = _api(cliente, "GET", f"/conversas?site_id={SITE}&lead_id={LEAD_A}", token=LEITURA).json()
    assert [c["id"] for c in por_lead["itens"]] == [str(conversa.id)]
    assert _api(cliente, "GET", f"/conversas?site_id={SITE}&estado=pessoa", token=LEITURA).json()["total"] == 0
    mensagens = _api(cliente, "GET", f"/conversas/{conversa.id}/mensagens?site_id={SITE}", token=LEITURA).json()
    assert mensagens["conversa"]["janela_aberta"] is True
    assert [m["texto"] for m in mensagens["mensagens"]] == ["Oi, quero saber do curso"]


def test_outro_site_e_sem_token_nao_veem_a_conversa(base):
    conversa = _conversa_ligada(base)
    cliente = Client()
    assert _api(cliente, "GET", f"/conversas/{conversa.id}?site_id=outro-site", token=LEITURA).status_code == 404
    assert _api(cliente, "GET", f"/conversas/{conversa.id}/mensagens?site_id=outro-site",
                token=LEITURA).status_code == 404
    assert _api(cliente, "GET", f"/conversas?site_id=outro-site&ligacao=todas", token=LEITURA).json()["total"] == 0
    assert _api(cliente, "GET", f"/conversas?site_id={SITE}", token=None).status_code == 401
    assert _api(cliente, "POST", f"/conversas/{conversa.id}/assumir",
                {"site_id": SITE, "pessoa_id": "p1"}, token=LEITURA).status_code == 403


def test_enviar_whatsapp_e_idempotente_e_acompanha_entrega(base, monkeypatch):
    conversa = _conversa_ligada(base)
    posts = []
    _gateway_aberto(monkeypatch, posts)
    cliente = Client()
    pedido = {"site_id": SITE, "texto": "Olá! Sou o assistente da equipe.", "chave_idempotencia": "turno-1"}
    primeira = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", pedido).json()
    segunda = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", pedido).json()
    assert primeira["resultado"] == "enviada" and segunda["resultado"] == "repetida"
    assert primeira["mensagem"]["id"] == segunda["mensagem"]["id"]
    assert len(posts) == 1 and posts[0][0] == "message/sendText/inst-abc"
    assert primeira["mensagem"]["estado_envio"] == "aceito" and primeira["mensagem"]["id_externo"] == "wamid-1"
    retorno = {"event": "messages.update", "instance": "inst-abc",
               "data": {"keyId": "wamid-1", "status": "DELIVERY_ACK"}}
    Client().post("/webhooks/whatsapp", json.dumps(retorno), content_type="application/json",
                  HTTP_X_WEBHOOK_TOKEN="retorno-local")
    mensagens = _api(cliente, "GET", f"/conversas/{conversa.id}/mensagens?site_id={SITE}", token=LEITURA).json()
    assert mensagens["mensagens"][-1]["estado_envio"] == "entregue"
    assert MensagemWhatsApp.objects.get().origem == "conversa"


def test_fora_da_janela_devolve_fora_da_janela_salvo_modelo(base, monkeypatch):
    conversa = _conversa_ligada(base)
    Conversa.objects.filter(pk=conversa.pk).update(janela_aberta_ate=timezone.now() - timedelta(minutes=1))
    posts = []
    _gateway_aberto(monkeypatch, posts)
    cliente = Client()
    fora = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                {"site_id": SITE, "texto": "Oi de novo", "chave_idempotencia": "f1"}).json()
    assert fora["resultado"] == "fora_da_janela" and fora["mensagem"] is None and not posts
    # Fora da janela, só com o aceite do contato (test_consentimentos.py).
    from apps.consentimentos.servico import registrar as registrar_aceite

    registrar_aceite(site_id=SITE, telefone="5511988887777", aceito=True, origem="quiz.completado")
    # Transporte atual (Baileys) não tem modelo aprovado: falha explícita, nada sai.
    modelo = {"site_id": SITE, "chave_idempotencia": "m1", "modelo": {"nome": "retomada", "idioma": "pt_BR"}}
    sem_modelo = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", modelo).json()
    assert sem_modelo["resultado"] == "falhou" and "modelo" in sem_modelo["mensagem"]["erro"] and not posts
    ConfiguracaoWhatsApp.objects.filter(pk=base["config"].pk).update(transporte="WHATSAPP-BUSINESS")
    modelo["chave_idempotencia"] = "m2"
    com_modelo = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens", modelo).json()
    assert com_modelo["resultado"] == "enviada"
    assert posts == [("message/sendTemplate/inst-abc", {"number": "5511988887777", "name": "retomada",
                                                         "language": "pt_BR", "components": []})]


def test_assumir_cala_o_agente_e_devolver_libera(base, monkeypatch):
    conversa = _conversa_ligada(base)
    posts = []
    _gateway_aberto(monkeypatch, posts)
    cliente = Client()
    assumida = _api(cliente, "POST", f"/conversas/{conversa.id}/assumir", {"site_id": SITE, "pessoa_id": "equipe-7"}).json()
    assert assumida["estado"] == "pessoa" and assumida["assumida_por"] == "equipe-7"
    agente = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                  {"site_id": SITE, "texto": "oi", "chave_idempotencia": "a1"}).json()
    assert agente["resultado"] == "conversa_com_pessoa" and not posts
    pessoa = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                  {"site_id": SITE, "texto": "Oi, aqui é a Carla", "chave_idempotencia": "p1",
                   "autor": "pessoa", "autor_id": "equipe-7"}).json()
    assert pessoa["resultado"] == "enviada" and pessoa["mensagem"]["autor"] == "pessoa"
    devolvida = _api(cliente, "POST", f"/conversas/{conversa.id}/devolver", {"site_id": SITE}).json()
    assert devolvida["estado"] == "agente" and devolvida["assumida_por"] is None
    assert _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                {"site_id": SITE, "texto": "oi", "chave_idempotencia": "a2"}).json()["resultado"] == "enviada"


def test_encerrada_reabre_com_nova_mensagem(base):
    conversa = _conversa_ligada(base)
    _api(Client(), "POST", f"/conversas/{conversa.id}/encerrar", {"site_id": SITE})
    assert Conversa.objects.get().estado == "encerrada"
    _upsert(Client(), _item(ident="novo", texto="voltei"))
    assert Conversa.objects.get().estado == "agente"


def test_email_sai_respondendo_a_ultima_mensagem(base, settings):
    settings.EMAIL_HOST, settings.DEFAULT_FROM_EMAIL = "smtp.teste", "equipe@meshcraft.top"
    cliente = Client()
    _email(cliente, {"from": "ana@exemplo.com", "subject": "Dúvida", "text": "Tem certificado?",
                     "message_id": "<q1@x>", "site_id": SITE})
    conversa = Conversa.objects.get()
    resposta = _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                    {"site_id": SITE, "texto": "Tem sim!", "chave_idempotencia": "e1"}).json()
    assert resposta["resultado"] == "enviada" and resposta["mensagem"]["estado_envio"] == "enviado"
    carta = mail.outbox[-1]
    assert carta.to == ["ana@exemplo.com"] and carta.subject == "Re: Dúvida"
    assert carta.extra_headers["In-Reply-To"] == "<q1@x>"
    assert _api(cliente, "POST", f"/conversas/{conversa.id}/mensagens",
                {"site_id": SITE, "texto": "Tem sim!", "chave_idempotencia": "e1"}).json()["resultado"] == "repetida"
    assert len(mail.outbox) == 1


def test_email_sem_smtp_falha_explicito(base, settings):
    settings.EMAIL_HOST = ""
    cliente = Client()
    aberta = _api(cliente, "POST", "/conversas", {"site_id": SITE, "canal": "email", "lead_id": LEAD_A,
                                                  "endereco": "ana@exemplo.com"}).json()
    falha = _api(cliente, "POST", f"/conversas/{aberta['id']}/mensagens",
                 {"site_id": SITE, "texto": "oi", "chave_idempotencia": "x1"}).json()
    assert falha["resultado"] == "falhou" and "nao configurado" in falha["mensagem"]["erro"]


def test_abrir_conversa_proativa_nao_troca_o_lead(base):
    cliente = Client()
    corpo = {"site_id": SITE, "canal": "whatsapp", "lead_id": LEAD_A, "endereco": "(11) 98888-7777"}
    aberta = _api(cliente, "POST", "/conversas", corpo).json()
    assert aberta["lead_id"] == LEAD_A and aberta["janela_aberta"] is False
    assert _api(cliente, "POST", "/conversas", corpo).json()["id"] == aberta["id"]
    assert _api(cliente, "POST", "/conversas", {**corpo, "lead_id": LEAD_B}).status_code == 409


def test_transcricao_fica_ligada_ao_audio(base):
    conversa = _conversa_ligada(base)
    mensagem = conversa.mensagens.get()
    dados = _api(Client(), "POST", f"/conversas/{conversa.id}/mensagens/{mensagem.id}/transcricao",
                 {"site_id": SITE, "transcricao": "quero saber do curso"}).json()
    assert dados["transcricao"] == "quero saber do curso"
