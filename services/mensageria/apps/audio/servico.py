"""Receber áudio do WhatsApp, baixar a mídia pelo transporte e enviar resposta em voz.

Transporte: Evolution API v2 (o mesmo de `apps.whatsapp.service`).
- baixar: POST chat/getBase64FromMediaMessage/{instancia}
- enviar: POST message/sendWhatsAppAudio/{instancia}

A transcrição e a síntese NÃO acontecem aqui: a chave da OpenAI mora no admin.
"""
from __future__ import annotations

import base64
import binascii
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib import error, request

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.whatsapp.models import ConfiguracaoWhatsApp, EstadoDeProvedor
from apps.whatsapp.service import (
    GatewayIndisponivel,
    GatewayRespostaInvalida,
    _instancia,
    estado_da_conexao,
    normalizar_telefone,
)

from .models import AudioRecebido, PreferenciaDeResposta, RespostaEmVoz

# Nota de voz de 10 minutos em opus fica perto de 1 MB; 16 MB é o teto do
# próprio WhatsApp para áudio.
LIMITE_DE_AUDIO_BYTES = 16 * 1024 * 1024
MAX_TENTATIVAS = 5
CANAIS_COM_AUDIO = {"whatsapp"}
TRANSPORTES_COM_AUDIO = {"WHATSAPP-BAILEYS"}


def _gateway_midia(method: str, caminho: str, dados: dict) -> dict:
    """Igual a `_gateway`, com espaço para a mídia na resposta."""
    base = getattr(settings, "WHATSAPP_GATEWAY_URL", "").rstrip("/")
    token = getattr(settings, "WHATSAPP_GATEWAY_TOKEN", "")
    if not base or not token:
        raise GatewayIndisponivel("gateway nao configurado")
    req = request.Request(
        base + "/" + caminho.lstrip("/"),
        data=json.dumps(dados).encode("utf-8"),
        method=method,
        headers={"apikey": token, "Content-Type": "application/json", "Origin": "http://localhost"},
    )
    try:
        with request.urlopen(req, timeout=60) as resposta:
            bruto = resposta.read(LIMITE_DE_AUDIO_BYTES * 2)
    except error.HTTPError as exc:
        raise GatewayIndisponivel(f"gateway respondeu HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise GatewayRespostaInvalida("gateway sem resposta confiavel") from exc
    try:
        payload = json.loads(bruto)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GatewayRespostaInvalida("gateway respondeu JSON invalido") from exc
    if not isinstance(payload, dict):
        raise GatewayRespostaInvalida("gateway respondeu formato invalido")
    return payload


def _decodificar(texto: str) -> bytes:
    if "," in texto[:100] and texto.startswith("data:"):
        texto = texto.split(",", 1)[1]
    return base64.b64decode(texto, validate=False)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


def _mensagem_de_audio(item: dict) -> dict | None:
    mensagem = item.get("message")
    if not isinstance(mensagem, dict):
        return None
    audio = mensagem.get("audioMessage")
    if isinstance(audio, dict):
        return audio
    return None


def registrar_do_webhook(config: ConfiguracaoWhatsApp, item: dict) -> AudioRecebido | None:
    """Um item de MESSAGES_UPSERT. Devolve o áudio guardado, ou None se não é
    áudio recebido de um lead. Repetir o mesmo item não cria outro registro."""
    if not isinstance(item, dict):
        return None
    audio = _mensagem_de_audio(item)
    chave = item.get("key") if isinstance(item.get("key"), dict) else {}
    if audio is None or chave.get("fromMe"):
        return None
    provider_id = chave.get("id")
    remoto = str(chave.get("remoteJidAlt") or chave.get("remoteJid") or "")
    if not isinstance(provider_id, str) or not provider_id or remoto.endswith("@g.us"):
        return None
    try:
        telefone = normalizar_telefone(remoto.split("@", 1)[0].split(":", 1)[0])
    except ValueError:
        return None
    segundos = audio.get("seconds")
    tamanho = audio.get("fileLength")
    try:
        tamanho = int(tamanho or 0)
    except (TypeError, ValueError):
        tamanho = 0
    conteudo = None
    embutido = (item.get("message") or {}).get("base64")
    if isinstance(embutido, str) and embutido:
        try:
            conteudo = _decodificar(embutido)
        except (binascii.Error, ValueError):
            conteudo = None
    try:
        with transaction.atomic():
            registro, _ = AudioRecebido.objects.get_or_create(
                instancia=config.instancia,
                provider_id=provider_id,
                defaults={
                    "site_id": config.site_id,
                    "telefone": telefone,
                    "mime": str(audio.get("mimetype") or "")[:80],
                    "segundos": int(segundos) if isinstance(segundos, (int, float)) and segundos >= 0 else None,
                    "tamanho_bytes": len(conteudo) if conteudo else max(tamanho, 0),
                    "conteudo": conteudo,
                },
            )
    except IntegrityError:
        registro = AudioRecebido.objects.get(instancia=config.instancia, provider_id=provider_id)
    return registro


def baixar_midia(audio: AudioRecebido) -> bytes:
    """O áudio original. Baixa pelo transporte na primeira vez e guarda."""
    if audio.conteudo:
        return bytes(audio.conteudo)
    config = ConfiguracaoWhatsApp.objects.filter(site_id=audio.site_id, instancia=audio.instancia).first()
    if config is None:
        raise GatewayIndisponivel("instancia nao configurada")
    resposta = _gateway_midia(
        "POST",
        f"chat/getBase64FromMediaMessage/{_instancia(config)}",
        {"message": {"key": {"id": audio.provider_id}}, "convertToMp4": False},
    )
    bruto = resposta.get("base64")
    if not isinstance(bruto, str) or not bruto:
        raise GatewayRespostaInvalida("gateway nao devolveu a midia")
    try:
        conteudo = _decodificar(bruto)
    except (binascii.Error, ValueError) as exc:
        raise GatewayRespostaInvalida("midia em formato invalido") from exc
    if len(conteudo) > LIMITE_DE_AUDIO_BYTES:
        raise GatewayRespostaInvalida("audio maior que o limite")
    mime = str(resposta.get("mimetype") or audio.mime or "audio/ogg")[:80]
    AudioRecebido.objects.filter(pk=audio.pk).update(
        conteudo=conteudo, tamanho_bytes=len(conteudo), mime=mime,
    )
    audio.conteudo, audio.tamanho_bytes, audio.mime = conteudo, len(conteudo), mime
    return conteudo


def _decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor or 0)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def guardar_transcricao(audio: AudioRecebido, *, texto: str, idioma: str = "", segundos=None,
                        modelo: str = "", custo_usd=0, ambiguidades=None,
                        pergunta_de_esclarecimento: str = "") -> AudioRecebido:
    ambiguidades = [a for a in (ambiguidades or []) if isinstance(a, dict)][:20]
    audio.transcricao = (texto or "").strip()
    audio.idioma = (idioma or "")[:20]
    if isinstance(segundos, (int, float)) and segundos >= 0:
        audio.segundos = int(round(segundos))
    audio.modelo = (modelo or "")[:60]
    audio.custo_usd = _decimal(custo_usd)
    audio.ambiguidades = ambiguidades
    audio.pedir_esclarecimento = bool(ambiguidades) or not audio.transcricao
    audio.pergunta_de_esclarecimento = (pergunta_de_esclarecimento or "").strip()
    audio.situacao = AudioRecebido.Situacao.TRANSCRITO
    audio.erro = ""
    audio.transcrito_em = timezone.now()
    audio.save()
    return audio


def anotar_falha(audio: AudioRecebido, erro: str, definitiva: bool = False) -> AudioRecebido:
    audio.tentativas += 1
    audio.erro = (erro or "falha na transcricao")[:300]
    if definitiva or audio.tentativas >= MAX_TENTATIVAS:
        audio.situacao = AudioRecebido.Situacao.FALHOU
    audio.save(update_fields=["tentativas", "erro", "situacao"])
    return audio


def resumo_para_o_atendente(audio: AudioRecebido) -> dict:
    """O que o atendente recebe: o texto do áudio, os trechos incertos e a
    referência ao original. Nada de telefone."""
    return {
        "audio_id": audio.pk,
        "provider_id": audio.provider_id,
        "conversa_ref": audio.conversa_ref,
        "recebido_em": audio.recebido_em.isoformat(),
        "situacao": audio.situacao,
        "segundos": audio.segundos,
        "transcricao": audio.transcricao,
        "ambiguidades": audio.ambiguidades,
        "pedir_esclarecimento": audio.pedir_esclarecimento,
        "pergunta_de_esclarecimento": audio.pergunta_de_esclarecimento,
        "custo_usd": str(audio.custo_usd),
    }


# ---------------------------------------------------------------------------
# Preferência e capacidade
# ---------------------------------------------------------------------------


def canal_aceita_audio(site_id: str, canal: str = "whatsapp") -> bool:
    if canal not in CANAIS_COM_AUDIO:
        return False
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id, ativo=True).first()
    return bool(config and config.transporte in TRANSPORTES_COM_AUDIO)


def preferencia(site_id: str, telefone: str) -> str:
    registro = PreferenciaDeResposta.objects.filter(site_id=site_id, telefone=telefone).first()
    return registro.modo if registro else PreferenciaDeResposta.Modo.ESPELHAR


def definir_preferencia(site_id: str, telefone: str, modo: str) -> str:
    PreferenciaDeResposta.objects.update_or_create(
        site_id=site_id, telefone=telefone, defaults={"modo": modo},
    )
    return modo


def decidir_formato(site_id: str, telefone: str, canal: str = "whatsapp") -> dict:
    """Responder em texto ou em áudio, e por quê."""
    modo = preferencia(site_id, telefone)
    aceita = canal_aceita_audio(site_id, canal)
    ultimo_audio = AudioRecebido.objects.filter(site_id=site_id, telefone=telefone).order_by("-recebido_em").first()
    ja_falou = RespostaEmVoz.objects.filter(site_id=site_id, telefone=telefone).exclude(status="falhou").exists()
    if not aceita:
        formato, motivo = "texto", "canal_sem_audio"
    elif modo == PreferenciaDeResposta.Modo.TEXTO:
        formato, motivo = "texto", "lead_prefere_texto"
    elif modo == PreferenciaDeResposta.Modo.AUDIO:
        formato, motivo = "audio", "lead_prefere_audio"
    elif ultimo_audio is not None and _ultima_entrada_foi_audio(site_id, telefone, ultimo_audio):
        formato, motivo = "audio", "lead_mandou_audio"
    else:
        formato, motivo = "texto", "lead_mandou_texto"
    return {
        "formato": formato,
        "motivo": motivo,
        "preferencia": modo,
        "canal_aceita_audio": aceita,
        "ja_respondeu_em_voz": ja_falou,
    }


def _ultima_entrada_foi_audio(site_id: str, telefone: str, ultimo_audio: AudioRecebido) -> bool:
    """Vale o áudio recente: o lead mandou voz nas últimas 24 horas."""
    return timezone.now() - ultimo_audio.recebido_em <= timedelta(hours=24)


# ---------------------------------------------------------------------------
# Saída em voz
# ---------------------------------------------------------------------------


ORDEM = {"desconhecido": 0, "falhou": 0, "aceito": 1, "enviado": 2, "entregue": 3, "lido": 4}


def enviar_audio(*, site_id: str, telefone: str, texto: str, audio: bytes, mime: str,
                 chave_idempotencia: str, conversa_ref: str = "", modelo: str = "",
                 voz: str = "", custo_usd=0) -> RespostaEmVoz:
    """Reserva a chave antes do POST, como o envio de texto. Mesma chave não
    envia duas vezes; resultado desconhecido não é reenviado às cegas."""
    if connection.in_atomic_block:
        raise RuntimeError("envio de audio exige transacao externa concluida")
    if not texto.strip():
        raise ValueError("o texto falado e obrigatorio")
    numero = normalizar_telefone(telefone)
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id, ativo=True).first()
    with transaction.atomic():
        resposta, criada = RespostaEmVoz.objects.select_for_update().get_or_create(
            site_id=site_id, chave_idempotencia=chave_idempotencia,
            defaults={
                "telefone": numero, "conversa_ref": conversa_ref,
                "texto": texto.strip(), "mime": mime[:80], "tamanho_bytes": len(audio),
                "conteudo": audio, "modelo": modelo[:60], "voz": voz[:40],
                "custo_usd": _decimal(custo_usd), "instancia": config.instancia if config else "",
            },
        )
        if not criada:
            return resposta
    if config is None or config.transporte not in TRANSPORTES_COM_AUDIO:
        resposta.status, resposta.erro = "falhou", "canal sem audio"
        resposta.save(update_fields=["status", "erro", "atualizado_em"])
        return resposta
    estado = estado_da_conexao(site_id)
    if estado["estado"] != "open":
        resposta.status = "falhou"
        resposta.erro = "instancia desconectada" if estado["estado"] != "indisponivel" else estado["erro"]
        resposta.save(update_fields=["status", "erro", "atualizado_em"])
        return resposta
    try:
        retorno = _gateway_midia("POST", f"message/sendWhatsAppAudio/{_instancia(config)}", {
            "number": numero, "audio": base64.b64encode(audio).decode("ascii"),
        })
    except GatewayIndisponivel as exc:
        seguro = str(exc) in {"gateway nao configurado", "gateway respondeu HTTP 401",
                              "gateway respondeu HTTP 403", "gateway respondeu HTTP 404"}
        resposta.status = "falhou" if seguro else "desconhecido"
        resposta.erro = str(exc)
    except GatewayRespostaInvalida as exc:
        resposta.status, resposta.erro = "desconhecido", str(exc)
    else:
        chave = retorno.get("key")
        provider_id = chave.get("id") if isinstance(chave, dict) else None
        if isinstance(provider_id, str) and provider_id:
            resposta.provider_id, resposta.status, resposta.erro = provider_id, "aceito", ""
            anterior = EstadoDeProvedor.objects.filter(instancia=config.instancia, provider_id=provider_id).first()
            if anterior and ORDEM.get(anterior.status, 0) > ORDEM["aceito"]:
                resposta.status = anterior.status
        else:
            resposta.status, resposta.erro = "desconhecido", "gateway aceitou sem identificador de mensagem"
    resposta.save(update_fields=["provider_id", "status", "erro", "atualizado_em"])
    return resposta


def atualizar_estado_de_voz(instancia: str, provider_id: str, estado: str) -> int:
    """Retorno do provedor (MESSAGES_UPDATE) para uma resposta em voz."""
    alteradas = 0
    for resposta in RespostaEmVoz.objects.filter(instancia=instancia, provider_id=provider_id):
        if estado == "falhou":
            if resposta.status in ("entregue", "lido"):
                continue
            resposta.status, resposta.erro = "falhou", "provedor informou falha"
        elif ORDEM.get(estado, 0) > ORDEM.get(resposta.status, 0):
            resposta.status, resposta.erro = estado, ""
        else:
            continue
        resposta.save(update_fields=["status", "erro", "atualizado_em"])
        alteradas += 1
    return alteradas


def consumo(site_id: str, *, telefone: str = "", conversa_ref: str = "") -> dict:
    """Custo de áudio de UMA conversa: transcrição, síntese e armazenamento."""
    audios = AudioRecebido.objects.filter(site_id=site_id)
    vozes = RespostaEmVoz.objects.filter(site_id=site_id)
    if conversa_ref:
        audios, vozes = audios.filter(conversa_ref=conversa_ref), vozes.filter(conversa_ref=conversa_ref)
    elif telefone:
        audios, vozes = audios.filter(telefone=telefone), vozes.filter(telefone=telefone)
    else:
        raise ValueError("informe telefone ou conversa_ref")
    transcricao = sum((a.custo_usd for a in audios.only("custo_usd")), Decimal("0"))
    sintese = sum((v.custo_usd for v in vozes.only("custo_usd")), Decimal("0"))
    armazenamento = sum(a.tamanho_bytes for a in audios.only("tamanho_bytes")) + sum(
        v.tamanho_bytes for v in vozes.only("tamanho_bytes"))
    return {
        "audios_recebidos": audios.count(),
        "respostas_em_voz": vozes.exclude(status="falhou").count(),
        "transcricao_usd": str(transcricao),
        "sintese_usd": str(sintese),
        "armazenamento_bytes": armazenamento,
        "total_usd": str(transcricao + sintese),
    }
