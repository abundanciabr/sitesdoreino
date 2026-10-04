"""Mensagens que chegam do contato: WhatsApp (Evolution e Cloud API) e e-mail.

O texto do contato é conteúdo. Nada aqui o interpreta como comando, exceto o
pedido de descadastro, que é só a mensagem inteira ser PARAR/SAIR/STOP.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import descadastro as descadastros
from . import enderecos, leads
from .models import Conversa, MensagemDaConversa

logger = logging.getLogger(__name__)
JANELA_WHATSAPP = timedelta(hours=24)
MENSAGEM_RECEBIDA = "mensagem.recebida"


@dataclass
class Recebida:
    site_id: str
    canal: str
    endereco: str
    texto: str = ""
    id_externo: str = ""
    caixa: str = ""
    assunto: str = ""
    em_resposta_a: str = ""
    midia: dict = field(default_factory=dict)  # {tipo, referencia, mime}
    ocorrida_em: datetime | None = None


def _momento(valor) -> datetime | None:
    """Timestamp do provedor (segundos) aceito só quando é plausível."""
    if isinstance(valor, dict):
        valor = valor.get("low")
    try:
        segundos = int(str(valor))
    except (TypeError, ValueError):
        return None
    agora = timezone.now()
    momento = datetime.fromtimestamp(segundos, tz=dt_timezone.utc) if segundos > 0 else None
    if momento is None or momento > agora + timedelta(minutes=5) or momento < agora - timedelta(days=7):
        return None
    return momento


def _ligar(conversa: Conversa | None, recebida: Recebida) -> leads.Ligacao | None:
    if conversa is not None and conversa.ligacao == "ligada":
        return None
    try:
        return leads.procurar(site_id=recebida.site_id, canal=recebida.canal, endereco=recebida.endereco)
    except Exception:  # noqa: BLE001 - ligação é melhoria; a mensagem não se perde
        logger.exception("conversas: falha ao ligar a conversa ao lead")
        return leads.Ligacao("pendente")


def _evento(conversa: Conversa, mensagem: MensagemDaConversa) -> dict:
    lead = conversa.lead_id if conversa.ligacao == "ligada" else None
    midia = ({"tipo": mensagem.midia_tipo, "referencia": mensagem.midia_referencia,
              "mime": mensagem.midia_mime} if mensagem.midia_tipo else None)
    return {
        "conversa_id": str(conversa.id),
        "mensagem_id": str(mensagem.id),
        "canal": conversa.canal,
        "site": conversa.site_id,
        "site_id": conversa.site_id,
        "lead": lead,
        "lead_ligacao": conversa.ligacao,
        "texto": mensagem.texto,
        "assunto": mensagem.assunto,
        "midia": midia,
        "estado_conversa": conversa.estado,
        "janela_aberta_ate": conversa.janela_aberta_ate.isoformat() if conversa.janela_aberta_ate else None,
        "descadastro": mensagem.descadastro,
        "recebida_em": mensagem.ocorrida_em.isoformat(),
    }


def receber(recebida: Recebida) -> tuple[MensagemDaConversa | None, bool]:
    """Grava a mensagem e publica `mensagem.recebida`. Volta (mensagem, nova)."""
    recebida.endereco = enderecos.endereco_do_canal(recebida.canal, recebida.endereco)
    if not recebida.endereco:
        return None, False
    existente = Conversa.objects.filter(
        site_id=recebida.site_id, canal=recebida.canal, endereco=recebida.endereco,
    ).first()
    if existente is not None and recebida.id_externo and existente.mensagens.filter(
        direcao="entrada", id_externo=recebida.id_externo,
    ).exists():
        return existente.mensagens.get(direcao="entrada", id_externo=recebida.id_externo), False
    ligacao = _ligar(existente, recebida)
    momento = recebida.ocorrida_em or timezone.now()
    pede_parar = enderecos.pede_descadastro(recebida.texto) or (
        recebida.canal == "email" and enderecos.pede_descadastro(recebida.assunto)
    )
    try:
        return _gravar(recebida, ligacao, momento, pede_parar)
    except IntegrityError:
        # Mesmo id externo entregue duas vezes ao mesmo tempo: vale a primeira.
        repetida = MensagemDaConversa.objects.filter(
            conversa__site_id=recebida.site_id, conversa__canal=recebida.canal,
            conversa__endereco=recebida.endereco, direcao="entrada", id_externo=recebida.id_externo,
        ).first()
        if repetida is None or not recebida.id_externo:
            raise
        return repetida, False


def _gravar(recebida: Recebida, ligacao, momento, pede_parar) -> tuple[MensagemDaConversa, bool]:
    from apps.jornadas.eventos import emitir
    from apps.jornadas.tasks import relay_apos_commit

    with transaction.atomic():
        conversa, _ = Conversa.objects.select_for_update().get_or_create(
            site_id=recebida.site_id, canal=recebida.canal, endereco=recebida.endereco,
            defaults={"caixa": recebida.caixa[:254]},
        )
        if recebida.id_externo:
            repetida = conversa.mensagens.filter(direcao="entrada", id_externo=recebida.id_externo).first()
            if repetida is not None:
                return repetida, False
        mensagem = MensagemDaConversa.objects.create(
            conversa=conversa, direcao="entrada", autor="lead",
            texto=recebida.texto or "", assunto=(recebida.assunto or "")[:300],
            midia_tipo=str(recebida.midia.get("tipo") or "")[:20],
            midia_referencia=str(recebida.midia.get("referencia") or "")[:300],
            midia_mime=str(recebida.midia.get("mime") or "")[:120],
            estado_envio="recebida", id_externo=(recebida.id_externo or "")[:300],
            em_resposta_a=(recebida.em_resposta_a or "")[:300],
            descadastro=pede_parar, ocorrida_em=momento,
        )
        campos = ["ultima_entrada_em", "ultima_mensagem_em", "atualizada_em"]
        conversa.ultima_entrada_em = max(filter(None, [conversa.ultima_entrada_em, momento]))
        conversa.ultima_mensagem_em = max(filter(None, [conversa.ultima_mensagem_em, momento]))
        if recebida.canal == "whatsapp":
            conversa.janela_aberta_ate = conversa.ultima_entrada_em + JANELA_WHATSAPP
            campos.append("janela_aberta_ate")
        if recebida.caixa and not conversa.caixa:
            conversa.caixa = recebida.caixa[:254]
            campos.append("caixa")
        if conversa.estado == "encerrada":
            conversa.estado = "agente"
            campos.append("estado")
        if ligacao is not None and conversa.ligacao != "ligada":
            conversa.ligacao = ligacao.ligacao
            conversa.lead_id = ligacao.lead_id if ligacao.ligacao == "ligada" else ""
            campos += ["ligacao", "lead_id"]
        conversa.save(update_fields=campos)
        registro = descadastros.registrar(conversa, momento) if pede_parar else None
        emitir(MENSAGEM_RECEBIDA, _evento(conversa, mensagem), envelope_extra={"ator_id": None})
        transaction.on_commit(relay_apos_commit)
    if registro is not None:
        try:
            descadastros.aplicar_preferencia(registro)
        except Exception:  # noqa: BLE001 - a tarefa periódica retoma
            logger.exception("conversas: preferencia do descadastro ficou pendente")
    return mensagem, True


# ---------------------------------------------------------------------------
# WhatsApp pela Evolution (messages.upsert)
# ---------------------------------------------------------------------------

_MIDIAS_EVOLUTION = {
    "audioMessage": "audio", "imageMessage": "imagem", "videoMessage": "video",
    "documentMessage": "documento", "stickerMessage": "figurinha",
}


def _telefone_do_jid(chave: dict, item: dict) -> str:
    candidatos = [chave.get("remoteJid"), chave.get("remoteJidAlt"), chave.get("senderPn"),
                  item.get("senderPn")]
    for jid in candidatos:
        if isinstance(jid, str) and jid.endswith("@s.whatsapp.net"):
            return jid.split("@", 1)[0].split(":", 1)[0]
    return ""


def de_evolution(*, site_id: str, instancia: str, item: dict) -> Recebida | None:
    chave = item.get("key") if isinstance(item.get("key"), dict) else {}
    if chave.get("fromMe") or item.get("fromMe"):
        return None  # saída feita pelo próprio aparelho; não é fala do contato
    remoto = str(chave.get("remoteJid") or "")
    if remoto.endswith("@g.us") or remoto.endswith("@broadcast") or remoto.endswith("@newsletter"):
        return None
    numero = _telefone_do_jid(chave, item)
    identificador = chave.get("id") or item.get("keyId") or item.get("id")
    if not numero or not isinstance(identificador, str) or not identificador:
        return None
    conteudo = item.get("message") if isinstance(item.get("message"), dict) else {}
    texto = conteudo.get("conversation") or ""
    if not texto and isinstance(conteudo.get("extendedTextMessage"), dict):
        texto = conteudo["extendedTextMessage"].get("text") or ""
    midia = {}
    for nome, tipo in _MIDIAS_EVOLUTION.items():
        dados = conteudo.get(nome)
        if isinstance(dados, dict):
            midia = {"tipo": tipo, "referencia": f"evolution:{instancia}:{identificador}",
                     "mime": str(dados.get("mimetype") or "")}
            texto = texto or str(dados.get("caption") or "")
            break
    if not texto and not midia:
        return None  # reação, enquete, chamada: nada para a conversa
    return Recebida(site_id=site_id, canal="whatsapp", endereco=numero, texto=str(texto),
                    id_externo=identificador, caixa=instancia, midia=midia,
                    ocorrida_em=_momento(item.get("messageTimestamp")))


# ---------------------------------------------------------------------------
# WhatsApp Business Platform (Cloud API oficial)
# ---------------------------------------------------------------------------

_MIDIAS_CLOUD = {"audio": "audio", "image": "imagem", "video": "video",
                 "document": "documento", "sticker": "figurinha"}


def de_cloud(*, site_id: str, numero_id: str, item: dict) -> Recebida | None:
    numero = str(item.get("from") or "")
    identificador = item.get("id")
    if not numero or not isinstance(identificador, str) or not identificador:
        return None
    tipo = item.get("type")
    texto = ""
    midia = {}
    if tipo == "text" and isinstance(item.get("text"), dict):
        texto = str(item["text"].get("body") or "")
    elif tipo == "button" and isinstance(item.get("button"), dict):
        texto = str(item["button"].get("text") or "")
    elif tipo == "interactive" and isinstance(item.get("interactive"), dict):
        resposta = item["interactive"].get("button_reply") or item["interactive"].get("list_reply") or {}
        texto = str(resposta.get("title") or "") if isinstance(resposta, dict) else ""
    elif tipo in _MIDIAS_CLOUD and isinstance(item.get(tipo), dict):
        dados = item[tipo]
        midia = {"tipo": _MIDIAS_CLOUD[tipo], "referencia": f"cloud:{dados.get('id') or ''}",
                 "mime": str(dados.get("mime_type") or "")}
        texto = str(dados.get("caption") or "")
    if not texto and not midia:
        return None
    return Recebida(site_id=site_id, canal="whatsapp", endereco=numero, texto=texto,
                    id_externo=identificador, caixa=numero_id, midia=midia,
                    ocorrida_em=_momento(item.get("timestamp")))
