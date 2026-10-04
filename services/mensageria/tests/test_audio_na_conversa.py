"""Áudio dentro da conversa: a nota de voz chega na caixa de conversas, a
transcrição volta para a mesma mensagem e a resposta em voz aparece como
mensagem de saída com o texto falado."""
import base64
import json

import pytest
from django.test import Client

from apps.audio.models import AudioRecebido, RespostaEmVoz
from apps.conversas.models import Conversa, MensagemDaConversa
from apps.jornadas.models import OutboxEvent
from apps.whatsapp.models import ConfiguracaoWhatsApp

pytestmark = pytest.mark.django_db(transaction=True)

OGG = b"OggS" + b"\x00" * 40
ESCRITA = {"HTTP_AUTHORIZATION": "Bearer escrita-test"}


@pytest.fixture
def configurado(settings, monkeypatch):
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    settings.WHATSAPP_WEBHOOK_TOKEN = "retorno-local"
    settings.TOKENS_PUBLICACAO = {"escrita-test"}
    monkeypatch.setattr("apps.jornadas.tasks.relay_apos_commit", lambda: None)
    return ConfiguracaoWhatsApp.objects.create(site_id="site-a", instancia="instancia-a", ativo=True)


def _audio_do_lead(cliente, provider_id="audio-1"):
    return cliente.post("/webhooks/whatsapp", json.dumps({
        "event": "messages.upsert", "instance": "instancia-a", "data": {
            "key": {"id": provider_id, "fromMe": False, "remoteJid": "5511988887777@s.whatsapp.net"},
            "message": {"audioMessage": {"mimetype": "audio/ogg; codecs=opus", "seconds": 5}},
            "messageTimestamp": None,
        }}), content_type="application/json", HTTP_X_WEBHOOK_TOKEN="retorno-local").json()


def test_audio_fica_ligado_a_mensagem_da_conversa_e_a_transcricao_volta_para_ela(configurado):
    cliente = Client()
    _audio_do_lead(cliente)
    mensagem = MensagemDaConversa.objects.get(direcao="entrada")
    assert mensagem.midia_tipo == "audio"
    audio = AudioRecebido.objects.get()
    assert audio.mensagem_ref == str(mensagem.pk) and audio.conversa_ref == str(mensagem.conversa_id)
    resposta = cliente.post(f"/api/mensageria/audio/site-a/{audio.pk}/transcricao", json.dumps({
        "texto": "Quero o curso de aquarela", "custo_usd": "0.0003",
        "ambiguidades": [{"tipo": "produto", "trecho": "curso", "opcoes": ["A", "B"]}],
        "pergunta_de_esclarecimento": "Você fala do A ou do B?"}),
        content_type="application/json", **ESCRITA).json()
    assert resposta["mensagem_ref"] == str(mensagem.pk)
    mensagem.refresh_from_db()
    assert mensagem.transcricao == "Quero o curso de aquarela"
    evento = OutboxEvent.objects.get(event="mensagem.transcrita")
    assert evento.payload["mensagem_id"] == str(mensagem.pk)
    assert evento.payload["transcricao"] == "Quero o curso de aquarela"
    assert evento.payload["pedir_esclarecimento"] is True
    assert evento.payload["pergunta_de_esclarecimento"] == "Você fala do A ou do B?"
    assert "5511988887777" not in json.dumps(evento.payload)
    # A lista de conversas já mostra o texto do áudio.
    assert OutboxEvent.objects.filter(event="mensagem.recebida").count() == 1


def _voz(cliente, chave="resp-1", texto="Oi, aqui é o assistente da equipe."):
    return cliente.post("/api/mensageria/audio/site-a/responder-em-voz", json.dumps({
        "telefone": "5511988887777", "texto": texto, "audio_base64": base64.b64encode(OGG).decode(),
        "chave_idempotencia": chave}), content_type="application/json", **ESCRITA).json()


def test_resposta_em_voz_vira_mensagem_de_saida_com_o_texto(configurado, monkeypatch):
    monkeypatch.setattr("apps.whatsapp.service._gateway",
                        lambda metodo, caminho, dados=None: {"instance": {"state": "open"}})
    monkeypatch.setattr("apps.audio.servico._gateway_midia", lambda *a: {"key": {"id": "voz-1"}})
    cliente = Client()
    _audio_do_lead(cliente)
    resposta = _voz(cliente)
    assert resposta["resultado"] == "enviada" and resposta["status"] == "aceito"
    saida = MensagemDaConversa.objects.get(direcao="saida")
    assert resposta["mensagem_ref"] == str(saida.pk)
    assert (saida.texto, saida.midia_tipo, saida.autor, saida.estado_envio, saida.id_externo) == (
        "Oi, aqui é o assistente da equipe.", "audio", "agente", "aceito", "voz-1")
    assert RespostaEmVoz.objects.get().conversa_ref == str(saida.conversa_id)
    cliente.post("/webhooks/whatsapp", json.dumps({"event": "messages.update", "instance": "instancia-a",
                                                   "data": {"key": {"id": "voz-1"}, "update": {"status": "DELIVERY_ACK"}}}),
                 content_type="application/json", HTTP_X_WEBHOOK_TOKEN="retorno-local")
    saida.refresh_from_db()
    assert saida.estado_envio == "entregue"


def test_conversa_assumida_por_pessoa_nao_recebe_voz_do_agente(configurado, monkeypatch):
    monkeypatch.setattr("apps.audio.servico._gateway_midia", lambda *a: pytest.fail("não devia enviar"))
    cliente = Client()
    _audio_do_lead(cliente)
    Conversa.objects.update(estado="pessoa")
    resposta = _voz(cliente)
    assert resposta["resultado"] == "conversa_com_pessoa" and resposta["status"] == "nao_enviado"
    assert not RespostaEmVoz.objects.exists() and not MensagemDaConversa.objects.filter(direcao="saida").exists()
