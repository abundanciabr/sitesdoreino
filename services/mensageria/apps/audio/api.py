"""Porta de máquina do áudio: o admin transcreve, sintetiza e entrega ao atendente.

Telefone nunca vai na URL: vai no corpo de um POST. Todo POST e o conteúdo do
áudio (a voz do lead) pedem o grau de publicação; só a fila de pendentes, sem
dado pessoal, é leitura.
"""
import base64
import binascii
from typing import Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import tokens_de_publicacao
from apps.whatsapp.service import GatewayIndisponivel, GatewayRespostaInvalida, normalizar_telefone

from . import servico
from .models import AudioRecebido, PreferenciaDeResposta

router = Router()


def _site(site_id: str) -> str:
    site_id = (site_id or "").strip()
    if not site_id or len(site_id) > 100:
        raise HttpError(422, "site_id invalido")
    return site_id


def _escrita(request):
    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "acesso de escrita negado")


def _telefone(valor: str) -> str:
    try:
        return normalizar_telefone(valor)
    except ValueError:
        raise HttpError(422, "telefone invalido")


def _audio(site_id: str, audio_id: int) -> AudioRecebido:
    audio = AudioRecebido.objects.filter(site_id=_site(site_id), pk=audio_id).first()
    if audio is None:
        raise HttpError(404, "audio nao encontrado")
    return audio


class Ambiguidade(Schema):
    tipo: str
    trecho: str
    motivo: str = ""
    opcoes: list[str] = []


class TranscricaoEntrada(Schema):
    texto: str
    idioma: str = ""
    segundos: Optional[float] = None
    modelo: str = ""
    custo_usd: str = "0"
    ambiguidades: list[Ambiguidade] = []
    pergunta_de_esclarecimento: str = ""


class FalhaEntrada(Schema):
    erro: str
    definitiva: bool = False


class LeadEntrada(Schema):
    telefone: str = ""
    conversa_ref: str = ""
    canal: str = "whatsapp"


class PreferenciaEntrada(Schema):
    telefone: str
    modo: str


class VozEntrada(Schema):
    telefone: str
    texto: str
    audio_base64: str
    mime: str = "audio/ogg"
    chave_idempotencia: str
    conversa_ref: str = ""
    modelo: str = ""
    voz: str = ""
    custo_usd: str = "0"


@router.get("/pendentes")
def pendentes(request, limite: int = 10):
    """Áudios esperando transcrição, de todos os sites. Sem telefone."""
    audios = AudioRecebido.objects.filter(
        situacao=AudioRecebido.Situacao.RECEBIDO,
    ).order_by("recebido_em")[: max(1, min(limite, 50))]
    return {"audios": [
        {"id": a.pk, "site_id": a.site_id, "mime": a.mime, "segundos": a.segundos,
         "tamanho_bytes": a.tamanho_bytes, "tentativas": a.tentativas}
        for a in audios
    ]}


@router.get("/{site_id}/{audio_id}/conteudo")
def conteudo(request, site_id: str, audio_id: int):
    _escrita(request)
    audio = _audio(site_id, audio_id)
    try:
        bruto = servico.baixar_midia(audio)
    except (GatewayIndisponivel, GatewayRespostaInvalida) as exc:
        servico.anotar_falha(audio, f"midia: {exc}", definitiva="limite" in str(exc))
        raise HttpError(503, "midia indisponivel agora")
    return {"id": audio.pk, "mime": audio.mime or "audio/ogg", "segundos": audio.segundos,
            "tamanho_bytes": len(bruto), "audio_base64": base64.b64encode(bruto).decode("ascii")}


@router.post("/{site_id}/{audio_id}/transcricao")
def transcricao(request, site_id: str, audio_id: int, dados: TranscricaoEntrada):
    _escrita(request)
    audio = _audio(site_id, audio_id)
    servico.guardar_transcricao(
        audio, texto=dados.texto, idioma=dados.idioma, segundos=dados.segundos,
        modelo=dados.modelo, custo_usd=dados.custo_usd,
        ambiguidades=[a.dict() for a in dados.ambiguidades],
        pergunta_de_esclarecimento=dados.pergunta_de_esclarecimento,
    )
    return servico.resumo_para_o_atendente(audio)


@router.post("/{site_id}/{audio_id}/falha")
def falha(request, site_id: str, audio_id: int, dados: FalhaEntrada):
    _escrita(request)
    audio = servico.anotar_falha(_audio(site_id, audio_id), dados.erro, dados.definitiva)
    return {"id": audio.pk, "situacao": audio.situacao, "tentativas": audio.tentativas}


@router.post("/{site_id}/transcricoes")
def transcricoes(request, site_id: str, dados: LeadEntrada, desde_id: int = 0, marcar_entregue: bool = True):
    """Os áudios de UM lead, já com o texto, para o atendente."""
    _escrita(request)
    site_id = _site(site_id)
    audios = AudioRecebido.objects.filter(site_id=site_id, pk__gt=desde_id)
    if dados.telefone:
        telefone = _telefone(dados.telefone)
        audios = audios.filter(telefone=telefone)
        if dados.conversa_ref:
            # Liga os áudios do lead à conversa que o atendente está tocando.
            AudioRecebido.objects.filter(site_id=site_id, telefone=telefone, conversa_ref="").update(
                conversa_ref=dados.conversa_ref[:160])
    elif dados.conversa_ref:
        audios = audios.filter(conversa_ref=dados.conversa_ref)
    else:
        raise HttpError(422, "informe telefone ou conversa_ref")
    lista = list(audios.order_by("recebido_em")[:50])
    if marcar_entregue:
        from django.utils import timezone

        AudioRecebido.objects.filter(
            pk__in=[a.pk for a in lista if a.situacao != AudioRecebido.Situacao.RECEBIDO],
            entregue_em__isnull=True,
        ).update(entregue_em=timezone.now())
    return {"audios": [servico.resumo_para_o_atendente(a) for a in lista]}


@router.post("/{site_id}/formato")
def formato(request, site_id: str, dados: LeadEntrada):
    """Texto ou áudio para a próxima resposta deste lead."""
    _escrita(request)
    return servico.decidir_formato(_site(site_id), _telefone(dados.telefone), dados.canal)


@router.post("/{site_id}/preferencia")
def preferencia(request, site_id: str, dados: PreferenciaEntrada):
    _escrita(request)
    if dados.modo not in PreferenciaDeResposta.Modo.values:
        raise HttpError(422, "modo invalido: texto, audio ou espelhar")
    modo = servico.definir_preferencia(_site(site_id), _telefone(dados.telefone), dados.modo)
    return {"modo": modo}


@router.post("/{site_id}/responder-em-voz")
def responder_em_voz(request, site_id: str, dados: VozEntrada):
    _escrita(request)
    site_id = _site(site_id)
    chave = dados.chave_idempotencia.strip()
    if not chave or len(chave) > 160:
        raise HttpError(422, "chave_idempotencia obrigatoria")
    try:
        bruto = base64.b64decode(dados.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HttpError(422, "audio em base64 invalido")
    if not bruto or len(bruto) > servico.LIMITE_DE_AUDIO_BYTES:
        raise HttpError(422, "audio vazio ou grande demais")
    try:
        resposta = servico.enviar_audio(
            site_id=site_id, telefone=_telefone(dados.telefone), texto=dados.texto, audio=bruto,
            mime=dados.mime, chave_idempotencia=chave, conversa_ref=dados.conversa_ref,
            modelo=dados.modelo, voz=dados.voz, custo_usd=dados.custo_usd,
        )
    except servico.Bloqueado as bloqueio:
        return {"id": None, "resultado": bloqueio.resultado, "status": "nao_enviado", "provider_id": "",
                "erro": bloqueio.detalhe, "texto": dados.texto, "conversa_ref": dados.conversa_ref,
                "mensagem_ref": ""}
    except ValueError as exc:
        raise HttpError(422, str(exc))
    return {"id": resposta.pk, "resultado": "falhou" if resposta.status == "falhou" else "enviada",
            "status": resposta.status, "provider_id": resposta.provider_id,
            "erro": resposta.erro, "texto": resposta.texto, "conversa_ref": resposta.conversa_ref,
            "mensagem_ref": resposta.mensagem_ref}


@router.post("/{site_id}/consumo")
def consumo(request, site_id: str, dados: LeadEntrada):
    _escrita(request)
    try:
        return servico.consumo(
            _site(site_id),
            telefone=_telefone(dados.telefone) if dados.telefone and not dados.conversa_ref else "",
            conversa_ref=dados.conversa_ref,
        )
    except ValueError as exc:
        raise HttpError(422, str(exc))
