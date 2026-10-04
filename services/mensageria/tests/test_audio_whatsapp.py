"""Nota de voz do lead e resposta em voz, com o transporte simulado."""
import base64
import json

import pytest
from django.test import Client

from apps.audio.models import AudioRecebido, PreferenciaDeResposta, RespostaEmVoz
from apps.whatsapp.models import ConfiguracaoWhatsApp

pytestmark = pytest.mark.django_db(transaction=True)

OGG = b"OggS" + b"\x00" * 60
ESCRITA = {"HTTP_AUTHORIZATION": "Bearer escrita-test"}
LEITURA = {"HTTP_AUTHORIZATION": "Bearer leitura-test"}


@pytest.fixture
def configurado(settings):
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    settings.WHATSAPP_WEBHOOK_TOKEN = "retorno-local"
    settings.TOKENS_SOMENTE_LEITURA = {"leitura-test"}
    settings.TOKENS_PUBLICACAO = {"escrita-test"}
    ConfiguracaoWhatsApp.objects.create(site_id="site-b", instancia="instancia-b", ativo=True)
    return ConfiguracaoWhatsApp.objects.create(site_id="site-a", instancia="instancia-a", ativo=True)


def _upsert(provider_id="audio-1", de_mim=False, instancia="instancia-a", numero="5511988887777", base64_=None):
    mensagem = {"audioMessage": {"mimetype": "audio/ogg; codecs=opus", "seconds": 7, "ptt": True,
                                 "fileLength": "4200"}}
    if base64_:
        mensagem["base64"] = base64_
    return {"event": "messages.upsert", "instance": instancia, "data": {
        "key": {"id": provider_id, "fromMe": de_mim, "remoteJid": f"{numero}@s.whatsapp.net"},
        "message": mensagem, "messageType": "audioMessage",
    }}


def _webhook(cliente, corpo):
    return cliente.post("/webhooks/whatsapp", json.dumps(corpo), content_type="application/json",
                        HTTP_X_WEBHOOK_TOKEN="retorno-local")


def test_nota_de_voz_recebida_vira_registro_unico_e_ignora_as_proprias(configurado):
    cliente = Client()
    assert _webhook(cliente, _upsert()).json() == {"recebidas": 1}
    assert AudioRecebido.objects.count() == 1
    _webhook(cliente, _upsert())  # o provedor repete o mesmo retorno
    _webhook(cliente, _upsert(provider_id="minha", de_mim=True))
    texto = _webhook(cliente, {"event": "messages.upsert", "instance": "instancia-a", "data": {
        "key": {"id": "txt", "remoteJid": "5511988887777@s.whatsapp.net"},
        "message": {"conversation": "oi"}}})
    assert texto.json() == {"recebidas": 1}
    audio = AudioRecebido.objects.get()
    assert (audio.site_id, audio.telefone, audio.segundos, audio.situacao) == (
        "site-a", "5511988887777", 7, "recebido")
    assert audio.conteudo is None


def test_webhook_de_audio_exige_token_e_instancia_conhecida(configurado):
    cliente = Client()
    assert cliente.post("/webhooks/whatsapp", json.dumps(_upsert()), content_type="application/json").status_code == 403
    assert _webhook(cliente, _upsert(instancia="alheia")).status_code == 404
    assert not AudioRecebido.objects.exists()


def test_midia_e_baixada_pelo_transporte_uma_vez_e_guardada(configurado, monkeypatch):
    _webhook(Client(), _upsert())
    audio = AudioRecebido.objects.get()
    chamadas = []

    def gateway(metodo, caminho, dados):
        chamadas.append((metodo, caminho, dados))
        return {"base64": base64.b64encode(OGG).decode(), "mimetype": "audio/ogg; codecs=opus"}

    monkeypatch.setattr("apps.audio.servico._gateway_midia", gateway)
    cliente = Client()
    url = f"/api/mensageria/audio/site-a/{audio.pk}/conteudo"
    assert cliente.get(url, **LEITURA).status_code == 403  # a voz do lead pede o grau de escrita
    assert cliente.get(f"/api/mensageria/audio/site-b/{audio.pk}/conteudo", **ESCRITA).status_code == 404
    resposta = cliente.get(url, **ESCRITA).json()
    assert base64.b64decode(resposta["audio_base64"]) == OGG
    cliente.get(url, **ESCRITA)
    assert chamadas == [("POST", "chat/getBase64FromMediaMessage/instancia-a",
                         {"message": {"key": {"id": "audio-1"}}, "convertToMp4": False})]
    audio.refresh_from_db()
    assert bytes(audio.conteudo) == OGG and audio.tamanho_bytes == len(OGG)


def test_midia_embutida_no_retorno_dispensa_download(configurado, monkeypatch):
    _webhook(Client(), _upsert(base64_=base64.b64encode(OGG).decode()))
    monkeypatch.setattr("apps.audio.servico._gateway_midia", lambda *a: pytest.fail("não devia baixar"))
    audio = AudioRecebido.objects.get()
    resposta = Client().get(f"/api/mensageria/audio/site-a/{audio.pk}/conteudo", **ESCRITA).json()
    assert base64.b64decode(resposta["audio_base64"]) == OGG


def test_transcricao_guardada_e_entregue_ao_atendente_so_do_mesmo_lead(configurado):
    cliente = Client()
    _webhook(cliente, _upsert())
    _webhook(cliente, _upsert(provider_id="outro-lead", numero="5521977776666"))
    _webhook(cliente, _upsert(provider_id="outro-site", instancia="instancia-b"))
    pendentes = cliente.get("/api/mensageria/audio/pendentes", **LEITURA).json()["audios"]
    assert len(pendentes) == 3 and all("telefone" not in p for p in pendentes)
    audio = AudioRecebido.objects.get(provider_id="audio-1")
    corpo = {"texto": "Quero o curso de aquarela em 12 vezes", "idioma": "pt", "segundos": 7.4,
             "modelo": "gpt-4o-mini-transcribe", "custo_usd": "0.000400",
             "ambiguidades": [{"tipo": "condicao", "trecho": "12 vezes", "motivo": "baixa confiança"}],
             "pergunta_de_esclarecimento": "Você falou em 12 parcelas?"}
    url = f"/api/mensageria/audio/site-a/{audio.pk}/transcricao"
    assert cliente.post(url, json.dumps(corpo), content_type="application/json", **LEITURA).status_code == 403
    assert cliente.post(url, json.dumps(corpo), content_type="application/json", **ESCRITA).status_code == 200
    entrega = cliente.post("/api/mensageria/audio/site-a/transcricoes",
                           json.dumps({"telefone": "11988887777", "conversa_ref": "conv-9"}),
                           content_type="application/json", **ESCRITA).json()["audios"]
    assert [a["provider_id"] for a in entrega] == ["audio-1"]
    assert entrega[0]["transcricao"] == "Quero o curso de aquarela em 12 vezes"
    assert entrega[0]["pedir_esclarecimento"] is True
    assert "telefone" not in json.dumps(entrega)
    audio.refresh_from_db()
    # O áudio já estava ligado à conversa em que chegou; o atendente acha por ela também.
    assert audio.entregue_em is not None and audio.conversa_ref and audio.mensagem_ref
    assert audio.situacao == "transcrito" and str(audio.custo_usd) == "0.000400"
    pendentes = cliente.get("/api/mensageria/audio/pendentes", **LEITURA).json()["audios"]
    assert {p["site_id"] for p in pendentes} == {"site-a", "site-b"} and len(pendentes) == 2


def test_falha_repetida_para_de_tentar(configurado):
    _webhook(Client(), _upsert())
    audio = AudioRecebido.objects.get()
    url = f"/api/mensageria/audio/site-a/{audio.pk}/falha"
    for _ in range(4):
        Client().post(url, json.dumps({"erro": "sem saldo"}), content_type="application/json", **ESCRITA)
    audio.refresh_from_db()
    assert audio.situacao == "recebido" and audio.tentativas == 4
    Client().post(url, json.dumps({"erro": "sem saldo"}), content_type="application/json", **ESCRITA)
    audio.refresh_from_db()
    assert audio.situacao == "falhou"


def test_formato_segue_preferencia_e_capacidade_do_canal(configurado):
    cliente = Client()

    def formato(telefone="5511988887777", canal="whatsapp", site="site-a"):
        return cliente.post(f"/api/mensageria/audio/{site}/formato",
                            json.dumps({"telefone": telefone, "canal": canal}),
                            content_type="application/json", **ESCRITA).json()

    assert formato()["formato"] == "texto"  # lead ainda não mandou áudio
    _webhook(cliente, _upsert())
    assert formato() | {} == {"formato": "audio", "motivo": "lead_mandou_audio", "preferencia": "espelhar",
                              "canal_aceita_audio": True, "ja_respondeu_em_voz": False}
    assert formato(canal="email")["formato"] == "texto"
    preferir = lambda modo, token=ESCRITA: cliente.post(  # noqa: E731
        "/api/mensageria/audio/site-a/preferencia", json.dumps({"telefone": "5511988887777", "modo": modo}),
        content_type="application/json", **token)
    assert preferir("texto", LEITURA).status_code == 403
    assert preferir("berrar").status_code == 422
    preferir("texto")
    assert formato()["motivo"] == "lead_prefere_texto"
    preferir("audio")
    assert formato(telefone="5521900000000")["formato"] == "texto"  # preferência é de um lead só
    assert formato()["motivo"] == "lead_prefere_audio"
    ConfiguracaoWhatsApp.objects.filter(site_id="site-a").update(ativo=False)
    assert formato()["motivo"] == "canal_sem_audio"
    assert PreferenciaDeResposta.objects.count() == 1


def test_resposta_em_voz_guarda_texto_envia_uma_vez_e_soma_no_consumo(configurado, monkeypatch):
    chamadas = []
    monkeypatch.setattr("apps.whatsapp.service._gateway",
                        lambda metodo, caminho, dados=None: {"instance": {"state": "open"}})

    def gateway(metodo, caminho, dados):
        chamadas.append((caminho, dados["number"], base64.b64decode(dados["audio"])))
        return {"key": {"id": "voz-1"}}

    monkeypatch.setattr("apps.audio.servico._gateway_midia", gateway)
    cliente = Client()
    _webhook(cliente, _upsert())
    audio = AudioRecebido.objects.get()
    cliente.post(f"/api/mensageria/audio/site-a/{audio.pk}/transcricao",
                 json.dumps({"texto": "oi", "custo_usd": "0.001"}), content_type="application/json", **ESCRITA)
    corpo = {"telefone": "5511988887777", "texto": "Oi, aqui é o assistente da equipe.",
             "audio_base64": base64.b64encode(OGG).decode(), "mime": "audio/ogg",
             "chave_idempotencia": "resp-1", "conversa_ref": "conv-9", "custo_usd": "0.002",
             "modelo": "gpt-4o-mini-tts", "voz": "coral"}
    url = "/api/mensageria/audio/site-a/responder-em-voz"
    primeira = cliente.post(url, json.dumps(corpo), content_type="application/json", **ESCRITA).json()
    segunda = cliente.post(url, json.dumps(corpo), content_type="application/json", **ESCRITA).json()
    assert primeira == segunda
    assert primeira["status"] == "aceito" and primeira["texto"] == corpo["texto"]
    assert chamadas == [("message/sendWhatsAppAudio/instancia-a", "5511988887777", OGG)]
    voz = RespostaEmVoz.objects.get()
    assert bytes(voz.conteudo) == OGG and voz.texto == corpo["texto"]
    _webhook(cliente, {"event": "messages.update", "instance": "instancia-a",
                       "data": {"key": {"id": "voz-1"}, "update": {"status": "PLAYED"}}})
    voz.refresh_from_db()
    assert voz.status == "lido"
    assert cliente.post("/api/mensageria/audio/site-a/consumo", json.dumps({"telefone": "5511988887777"}),
                        content_type="application/json", **LEITURA).status_code == 403
    consumo = cliente.post("/api/mensageria/audio/site-a/consumo", json.dumps({"telefone": "5511988887777"}),
                           content_type="application/json", **ESCRITA).json()
    assert consumo["transcricao_usd"] == "0.001000" and consumo["sintese_usd"] == "0.002000"
    assert consumo["total_usd"] == "0.003000" and consumo["armazenamento_bytes"] == 4200 + len(OGG)
    outro = cliente.post("/api/mensageria/audio/site-b/consumo", json.dumps({"telefone": "5511988887777"}),
                         content_type="application/json", **ESCRITA).json()
    assert outro["total_usd"] == "0"
    formato = cliente.post("/api/mensageria/audio/site-a/formato", json.dumps({"telefone": "5511988887777"}),
                           content_type="application/json", **ESCRITA).json()
    assert formato["ja_respondeu_em_voz"] is True


def test_resposta_em_voz_com_instancia_desconectada_falha_sem_post(configurado, monkeypatch):
    monkeypatch.setattr("apps.whatsapp.service._gateway",
                        lambda metodo, caminho, dados=None: {"instance": {"state": "close"}})
    monkeypatch.setattr("apps.audio.servico._gateway_midia", lambda *a: pytest.fail("não devia enviar"))
    resposta = Client().post("/api/mensageria/audio/site-a/responder-em-voz", json.dumps({
        "telefone": "5511988887777", "texto": "oi", "audio_base64": base64.b64encode(OGG).decode(),
        "chave_idempotencia": "resp-2"}), content_type="application/json", **ESCRITA).json()
    assert resposta["status"] == "falhou" and resposta["erro"] == "instancia desconectada"
