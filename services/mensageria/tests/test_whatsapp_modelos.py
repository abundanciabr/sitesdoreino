"""Modelos aprovados do WhatsApp oficial, com a Cloud API simulada."""
import hashlib
import hmac
import io
import json
from urllib import error

import pytest
from django.test import Client

from apps.whatsapp_modelos import cloud
from apps.whatsapp_modelos.models import EnvioDeModelo, ModeloWhatsApp
from apps.whatsapp_modelos.modelos import aplicar_status, enviar_modelo, sincronizar_modelos

pytestmark = pytest.mark.django_db(transaction=True)

LEITURA = "leitura-teste"
ESCRITA = "escrita-teste"

MODELOS = {"data": [
    {"id": "111", "name": "primeiro_contato", "language": "pt_BR", "status": "APPROVED",
     "category": "MARKETING", "components": [
         {"type": "BODY", "text": "Oi {{1}}, vi seu resultado no {{2}}. Quer saber do {{3}}?"},
         {"type": "BUTTONS", "buttons": [{"type": "URL", "text": "Ver", "url": "https://meshcraft.top/c/{{1}}"}]},
     ]},
    {"id": "222", "name": "convite_nomeado", "language": "pt_BR", "status": "APPROVED",
     "category": "MARKETING", "parameter_format": "NAMED", "components": [
         {"type": "BODY", "text": "Oi {{first_name}}, sobre {{oferta}}"}]},
    {"id": "333", "name": "em_analise", "language": "pt_BR", "status": "PENDING",
     "category": "UTILITY", "components": [{"type": "BODY", "text": "Oi"}]},
    {"id": "444", "name": "com_imagem", "language": "pt_BR", "status": "APPROVED",
     "category": "MARKETING", "components": [{"type": "HEADER", "format": "IMAGE"},
                                             {"type": "BODY", "text": "Oi"}]},
], "paging": {"cursors": {"after": "x"}}}

LEAD = {"nome": "Ana", "quiz": "Quiz da Vocação", "oferta": "Curso Base", "link": "abc123"}


@pytest.fixture
def ligado(settings):
    settings.WHATSAPP_CLOUD_ACCESS_TOKEN = "token-teste"
    settings.WHATSAPP_CLOUD_WABA_ID = "waba-1"
    settings.WHATSAPP_CLOUD_PHONE_NUMBER_ID = "num-1"
    settings.WHATSAPP_CLOUD_APP_SECRET = "segredo-app"
    settings.WHATSAPP_CLOUD_VERIFY_TOKEN = "verifica"
    return settings


@pytest.fixture
def meta(ligado, monkeypatch):
    chamadas = []
    respostas = {"POST": [{"messages": [{"id": "wamid.1"}]}]}

    def pedir(method, caminho, *, dados=None, params=None):
        chamadas.append((method, caminho, dados, params))
        if method == "GET":
            return MODELOS
        resposta = respostas["POST"].pop(0) if respostas["POST"] else {"messages": [{"id": "wamid.x"}]}
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(cloud, "pedir", pedir)
    return chamadas, respostas


@pytest.fixture
def tokens(settings):
    settings.TOKENS_SOMENTE_LEITURA = {LEITURA}
    settings.TOKENS_PUBLICACAO = {ESCRITA}


def test_sincroniza_estado_variaveis_e_mapeamento(meta):
    chamadas, _ = meta
    resultado = sincronizar_modelos()
    assert resultado["modelos"] == 4
    assert chamadas[0][1] == "waba-1/message_templates"
    primeiro = ModeloWhatsApp.objects.get(nome="primeiro_contato")
    assert primeiro.estado == "aprovado" and primeiro.suportado
    assert primeiro.mapeamento == {"body:1": "nome", "body:2": "quiz", "body:3": "oferta", "button.0:1": "link"}
    assert ModeloWhatsApp.objects.get(nome="convite_nomeado").mapeamento == {
        "body:first_name": "nome", "body:oferta": "oferta"}
    assert ModeloWhatsApp.objects.get(nome="em_analise").estado == "pendente"
    imagem = ModeloWhatsApp.objects.get(nome="com_imagem")
    assert not imagem.suportado and "midia" in imagem.motivo


def test_envio_preenche_variaveis_e_chave_repetida_nao_reenvia(meta):
    chamadas, _ = meta
    sincronizar_modelos()
    envio = enviar_modelo(site_id="site-a", chave_idempotencia="abordagem:op-1", destinatario="(11) 98888-7777",
                          modelo="primeiro_contato", variaveis=LEAD, referencia="op-1")
    de_novo = enviar_modelo(site_id="site-a", chave_idempotencia="abordagem:op-1", destinatario="11988887777",
                            modelo="primeiro_contato", variaveis=LEAD, referencia="op-1")
    assert envio.estado == "aceito" and envio.provider_id == "wamid.1"
    assert de_novo.pk == envio.pk
    posts = [c for c in chamadas if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][1] == "num-1/messages"
    corpo = posts[0][2]
    assert corpo["to"] == "5511988887777" and corpo["type"] == "template"
    assert corpo["template"]["name"] == "primeiro_contato"
    assert corpo["template"]["language"] == {"code": "pt_BR"}
    assert corpo["template"]["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "Ana"},
                                        {"type": "text", "text": "Quiz da Vocação"},
                                        {"type": "text", "text": "Curso Base"}]},
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": "abc123"}]},
    ]


def test_parametro_nomeado_e_texto_sem_quebra_de_linha(meta):
    chamadas, _ = meta
    sincronizar_modelos()
    enviar_modelo(site_id="site-a", chave_idempotencia="j-1", destinatario="5511988887777",
                  modelo="convite_nomeado", variaveis={"nome": "Ana\n\nMaria", "oferta": "Curso"}, origem="jornada")
    corpo = [c for c in chamadas if c[0] == "POST"][0][2]
    assert corpo["template"]["components"] == [{"type": "body", "parameters": [
        {"type": "text", "text": "Ana Maria", "parameter_name": "first_name"},
        {"type": "text", "text": "Curso", "parameter_name": "oferta"}]}]


def test_sem_credencial_nao_chama_a_meta_e_pode_tentar_depois(settings, monkeypatch):
    settings.WHATSAPP_CLOUD_ACCESS_TOKEN = ""
    monkeypatch.setattr(cloud, "pedir", lambda *a, **k: pytest.fail("nao devia chamar a Meta"))
    envio = enviar_modelo(site_id="site-a", chave_idempotencia="k", destinatario="5511988887777",
                          modelo="primeiro_contato", variaveis=LEAD)
    assert envio.estado == "falhou" and envio.retomavel
    assert "ainda nao ligado" in envio.erro


def test_dado_faltando_modelo_pendente_ou_sem_suporte_falham_antes_do_envio(meta):
    chamadas, _ = meta
    sincronizar_modelos()
    faltando = enviar_modelo(site_id="site-a", chave_idempotencia="a", destinatario="5511988887777",
                             modelo="primeiro_contato", variaveis={"nome": "Ana"})
    pendente = enviar_modelo(site_id="site-a", chave_idempotencia="b", destinatario="5511988887777",
                             modelo="em_analise", variaveis=LEAD)
    imagem = enviar_modelo(site_id="site-a", chave_idempotencia="c", destinatario="5511988887777",
                           modelo="com_imagem", variaveis=LEAD)
    telefone = enviar_modelo(site_id="site-a", chave_idempotencia="d", destinatario="123",
                             modelo="primeiro_contato", variaveis=LEAD)
    assert "Quiz respondido" in faltando.erro and faltando.retomavel
    assert pendente.erro == "modelo nao aprovado ou nao sincronizado"
    assert "midia" in imagem.erro
    assert telefone.erro == "telefone invalido"
    assert not [c for c in chamadas if c[0] == "POST"]


def test_recusa_da_meta_permite_nova_tentativa_e_timeout_nao(meta):
    chamadas, respostas = meta
    sincronizar_modelos()
    respostas["POST"] = [cloud.CloudRecusou(400, "131026"), {"messages": [{"id": "wamid.2"}]}]
    recusado = enviar_modelo(site_id="site-a", chave_idempotencia="r", destinatario="5511988887777",
                             modelo="primeiro_contato", variaveis=LEAD)
    assert recusado.estado == "falhou" and recusado.erro_codigo == "131026" and recusado.retomavel
    retomado = enviar_modelo(site_id="site-a", chave_idempotencia="r", destinatario="5511988887777",
                             modelo="primeiro_contato", variaveis=LEAD)
    assert retomado.pk == recusado.pk and retomado.estado == "aceito" and retomado.tentativas == 2

    respostas["POST"] = [cloud.CloudSemResposta("meta sem resposta confiavel")]
    incerto = enviar_modelo(site_id="site-a", chave_idempotencia="t", destinatario="5511988887777",
                            modelo="primeiro_contato", variaveis=LEAD)
    assert incerto.estado == "desconhecido"
    enviar_modelo(site_id="site-a", chave_idempotencia="t", destinatario="5511988887777",
                  modelo="primeiro_contato", variaveis=LEAD)
    assert len([c for c in chamadas if c[0] == "POST"]) == 3


def test_mesma_chave_em_outro_site_e_outro_envio(meta):
    sincronizar_modelos()
    a = enviar_modelo(site_id="site-a", chave_idempotencia="k", destinatario="5511988887777",
                      modelo="primeiro_contato", variaveis=LEAD)
    b = enviar_modelo(site_id="site-b", chave_idempotencia="k", destinatario="5511988887777",
                      modelo="primeiro_contato", variaveis=LEAD)
    assert a.pk != b.pk


def test_status_da_meta_nao_regride_e_chega_antes_do_envio(meta):
    _, respostas = meta
    sincronizar_modelos()
    assert not aplicar_status({"id": "wamid.cedo", "status": "delivered"})
    respostas["POST"] = [{"messages": [{"id": "wamid.cedo"}]}]
    envio = enviar_modelo(site_id="site-a", chave_idempotencia="s", destinatario="5511988887777",
                          modelo="primeiro_contato", variaveis=LEAD)
    assert envio.estado == "entregue"
    aplicar_status({"id": "wamid.cedo", "status": "sent"})
    envio.refresh_from_db()
    assert envio.estado == "entregue"
    aplicar_status({"id": "wamid.cedo", "status": "failed", "errors": [{"code": 131049}]})
    envio.refresh_from_db()
    assert envio.estado == "entregue"


def _assinado(corpo: dict) -> tuple[bytes, str]:
    bruto = json.dumps(corpo).encode()
    return bruto, "sha256=" + hmac.new(b"segredo-app", bruto, hashlib.sha256).hexdigest()


def test_webhook_verifica_assinatura_e_aplica_status_e_estado_do_modelo(meta):
    sincronizar_modelos()
    envio = enviar_modelo(site_id="site-a", chave_idempotencia="w", destinatario="5511988887777",
                          modelo="primeiro_contato", variaveis=LEAD)
    cliente = Client()
    url = "/webhooks/whatsapp/cloud"
    assert cliente.get(url, {"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "9"}).status_code == 403
    ok = cliente.get(url, {"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "9"})
    assert ok.status_code == 200 and ok.content == b"9"
    corpo = {"entry": [{"changes": [
        {"field": "messages", "value": {"statuses": [{"id": envio.provider_id, "status": "read"}]}},
        {"field": "message_template_status_update",
         "value": {"event": "PAUSED", "message_template_id": "111", "reason": "baixa qualidade"}},
    ]}]}
    bruto, assinatura = _assinado(corpo)
    assert cliente.post(url, bruto, content_type="application/json",
                        HTTP_X_HUB_SIGNATURE_256="sha256=falsa").status_code == 403
    resposta = cliente.post(url, bruto, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=assinatura)
    assert resposta.status_code == 200 and resposta.json() == {"atualizados": 2}
    envio.refresh_from_db()
    assert envio.estado == "lido"
    modelo = ModeloWhatsApp.objects.get(modelo_id="111")
    assert modelo.estado == "pausado" and modelo.motivo == "baixa qualidade"


def test_api_painel_sincroniza_mapeia_e_envia(meta, tokens):
    cliente = Client()
    base = "/api/mensageria/whatsapp-modelos/"
    leitura = {"HTTP_AUTHORIZATION": "Bearer " + LEITURA}
    escrita = {"HTTP_AUTHORIZATION": "Bearer " + ESCRITA}
    assert cliente.post(base + "sincronizar", **leitura).status_code == 403
    assert cliente.post(base + "sincronizar", **escrita).json()["modelos"] == 4
    painel = cliente.get(base + "site-a", **leitura).json()
    assert painel["canal_oficial"] == "ligado"
    assert {m["nome"] for m in painel["modelos"]} >= {"primeiro_contato", "em_analise"}
    modelo = next(m for m in painel["modelos"] if m["nome"] == "primeiro_contato")
    mapeado = cliente.post(base + "modelos/mapeamento",
                           json.dumps({"modelo_id": modelo["id"], "mapeamento": {"body:3": "link"}}),
                           content_type="application/json", **escrita)
    assert mapeado.status_code == 200 and mapeado.json()["mapeamento"]["body:3"] == "link"
    assert cliente.post(base + "modelos/mapeamento",
                        json.dumps({"modelo_id": modelo["id"], "mapeamento": {"body:3": "renda"}}),
                        content_type="application/json", **escrita).status_code == 422
    envio = cliente.post(base + "site-a/enviar", json.dumps({
        "chave_idempotencia": "abordagem:op-9", "destinatario": "5511988887777",
        "modelo": "primeiro_contato", "variaveis": LEAD, "referencia": "op-9"}),
        content_type="application/json", **escrita)
    assert envio.status_code == 200
    dados = envio.json()
    assert dados["estado"] == "aceito" and dados["numero_mascarado"].endswith("7777")
    assert "5511988887777" not in json.dumps(dados)
    consulta = cliente.get(base + "site-a/envios/abordagem:op-9", **leitura)
    assert consulta.json()["id"] == dados["id"]
    assert cliente.get(base + "site-b/envios/abordagem:op-9", **leitura).status_code == 404
    outro = cliente.get(base + "site-b", **leitura).json()
    assert outro["envios"] == []


def test_api_sem_canal_diz_que_nao_esta_ligado(tokens, settings):
    settings.WHATSAPP_CLOUD_ACCESS_TOKEN = ""
    cliente = Client()
    base = "/api/mensageria/whatsapp-modelos/"
    assert cliente.get(base + "site-a", HTTP_AUTHORIZATION="Bearer " + LEITURA).json()["canal_oficial"] == "nao_ligado"
    assert cliente.post(base + "sincronizar", HTTP_AUTHORIZATION="Bearer " + ESCRITA).json()[
        "canal_oficial"] == "nao_ligado"


def test_cliente_http_separa_recusa_de_incerteza(ligado, monkeypatch):
    def recusa(*a, **k):
        raise error.HTTPError("u", 400, "x", {}, io.BytesIO(b'{"error": {"code": 132001, "message": "x"}}'))

    monkeypatch.setattr(cloud.request, "urlopen", recusa)
    with pytest.raises(cloud.CloudRecusou) as exc:
        cloud.pedir("POST", "num-1/messages", dados={})
    assert exc.value.codigo == "132001"

    def falha(*a, **k):
        raise error.HTTPError("u", 503, "x", {}, io.BytesIO(b""))

    monkeypatch.setattr(cloud.request, "urlopen", falha)
    with pytest.raises(cloud.CloudSemResposta):
        cloud.pedir("POST", "num-1/messages", dados={})
