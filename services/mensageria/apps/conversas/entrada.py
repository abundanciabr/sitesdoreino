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
from . import enderecos, leads, orientacao, interacoes
from .models import Conversa, MensagemDaConversa

logger = logging.getLogger(__name__)
JANELA_WHATSAPP = timedelta(hours=24)
# Fala mais velha que a janela do WhatsApp é histórico (sincronização, reconexão):
# guarda-se com a hora real, mas não abre janela nem chama o agente.
ANTIGA_APOS = JANELA_WHATSAPP
MENSAGEM_RECEBIDA = "mensagem.recebida"
# Plausível: depois de 2009 (o WhatsApp nem existia antes) e, no máximo, 5 minutos à frente.
_PRIMEIRO_SEGUNDO_PLAUSIVEL = 1_230_768_000
REENTREGA_SEM_ID = timedelta(minutes=10)


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
    # O provedor mandou como histórico (append): vale como registro, não como fala nova.
    historica: bool = False


def _momento(valor) -> datetime | None:
    """Timestamp do provedor (segundos) com a hora real da fala.

    Antigo mas legível volta como é: quem decide se é histórico é `receber`.
    Só ausente, ilegível ou no futuro vira None (e a fala vale como de agora).
    """
    if isinstance(valor, dict):
        valor = valor.get("low")
    try:
        segundos = int(str(valor))
        momento = datetime.fromtimestamp(segundos, tz=dt_timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if segundos < _PRIMEIRO_SEGUNDO_PLAUSIVEL or momento > timezone.now() + timedelta(minutes=5):
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


def _repetida_sem_id(conversa: Conversa, recebida: Recebida) -> bool:
    """E-mail sem Message-ID reentregue: mesmo conteúdo na mesma conversa em poucos minutos."""
    if recebida.id_externo or recebida.canal != "email":
        return False
    return conversa.mensagens.filter(
        direcao="entrada", texto=recebida.texto or "", assunto=(recebida.assunto or "")[:300],
        em_resposta_a=(recebida.em_resposta_a or "")[:300],
        ocorrida_em__gte=timezone.now() - REENTREGA_SEM_ID,
    ).exists()


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
    recebida.site_id = (recebida.site_id or "").strip()
    if not recebida.endereco or not recebida.site_id:
        return None, False  # sem site não há conversa: dado de um site nunca cai em outro
    existente = Conversa.objects.filter(
        site_id=recebida.site_id, canal=recebida.canal, endereco=recebida.endereco,
    ).first()
    if existente is not None and recebida.id_externo and existente.mensagens.filter(
        direcao="entrada", id_externo=recebida.id_externo,
    ).exists():
        return existente.mensagens.get(direcao="entrada", id_externo=recebida.id_externo), False
    if existente is not None and _repetida_sem_id(existente, recebida):
        return None, False
    ligacao = _ligar(existente, recebida)
    agora = timezone.now()
    momento = recebida.ocorrida_em or agora
    historica = recebida.historica or momento < agora - ANTIGA_APOS
    pede_parar = enderecos.pede_descadastro(recebida.texto) or (
        recebida.canal == "email" and enderecos.pede_descadastro(recebida.assunto)
    )
    equipe_confirma = False
    if not historica and not pede_parar and _espera_o_email(existente, recebida):
        email = orientacao.email_do_texto(recebida.texto)
        if email:
            # Só liga quando é inequívoco; senão a equipe confirma. Nunca responde com dado de lead.
            ligacao = _ligar_pelo_email(existente, recebida, email)
            equipe_confirma = ligacao is None
    try:
        mensagem, nova = _gravar(recebida, ligacao, momento, pede_parar, historica, equipe_confirma)
    except IntegrityError:
        # Mesmo id externo entregue duas vezes ao mesmo tempo: vale a primeira.
        repetida = MensagemDaConversa.objects.filter(
            conversa__site_id=recebida.site_id, conversa__canal=recebida.canal,
            conversa__endereco=recebida.endereco, direcao="entrada", id_externo=recebida.id_externo,
        ).first()
        if repetida is None or not recebida.id_externo:
            raise
        return repetida, False
    if nova and not historica:
        orientacao.apos_receber(mensagem, equipe_acabou_de_confirmar=equipe_confirma)
    return mensagem, nova


def _espera_o_email(conversa: Conversa | None, recebida: Recebida) -> bool:
    """A conversa é ambígua, a orientação pediu o e-mail e a equipe ainda não está confirmando?"""
    return (conversa is not None and recebida.canal == "whatsapp" and conversa.ligacao != "ligada"
            and conversa.orientacao_tipo == "ambigua" and not conversa.equipe_confirma)


def _ligar_pelo_email(conversa: Conversa, recebida: Recebida, email: str) -> leads.Ligacao | None:
    try:
        return leads.confirmar_por_email(
            site_id=recebida.site_id, email=email, telefone_da_conversa=recebida.endereco)
    except Exception:  # noqa: BLE001 - na dúvida, a equipe confirma
        logger.exception("conversas: falha ao conferir o e-mail informado")
        return None


def _gravar(recebida: Recebida, ligacao, momento, pede_parar,
            historica: bool = False, equipe_confirma: bool = False) -> tuple[MensagemDaConversa, bool]:
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
        campos = ["ultima_mensagem_em", "atualizada_em"]
        conversa.ultima_mensagem_em = max(filter(None, [conversa.ultima_mensagem_em, momento]))
        if not historica:
            campos.append("ultima_entrada_em")
            conversa.ultima_entrada_em = max(filter(None, [conversa.ultima_entrada_em, momento]))
            if recebida.canal == "whatsapp":
                conversa.janela_aberta_ate = conversa.ultima_entrada_em + JANELA_WHATSAPP
                campos.append("janela_aberta_ate")
        if recebida.caixa and not conversa.caixa:
            conversa.caixa = recebida.caixa[:254]
            campos.append("caixa")
        if conversa.estado == "encerrada" and not historica:
            conversa.estado = "agente"
            campos.append("estado")
        # Falha momentânea da célula de leads ("pendente") não desfaz o que já se sabe:
        # conversa ambígua ou sem origem continua assim até uma resposta de verdade.
        sem_resposta_da_leads = ligacao is not None and ligacao.ligacao == "pendente" and conversa.ligacao in (
            "ambigua", "desconhecida")
        if ligacao is not None and conversa.ligacao != "ligada" and not sem_resposta_da_leads:
            conversa.ligacao = ligacao.ligacao
            conversa.lead_id = ligacao.lead_id if ligacao.ligacao == "ligada" else ""
            campos += ["ligacao", "lead_id"]
            if ligacao.ligacao == "ligada" and conversa.equipe_confirma:
                conversa.equipe_confirma = False
                campos.append("equipe_confirma")
        if equipe_confirma and conversa.ligacao == "ambigua" and not conversa.equipe_confirma:
            conversa.equipe_confirma = True
            campos.append("equipe_confirma")
        conversa.save(update_fields=campos)
        registro = descadastros.registrar(conversa, momento) if pede_parar else None
        if not historica:
            evento = emitir(MENSAGEM_RECEBIDA, _evento(conversa, mensagem), envelope_extra={"ator_id": None})
            transaction.on_commit(relay_apos_commit)
            # A Central vê somente a fala nova já gravada. Savepoints isolam
            # suas falhas sem perder a entrada nem o evento do atendimento.
            try:
                with transaction.atomic():
                    from apps.jornadas.central import ao_resposta

                    ao_resposta(mensagem)
            except Exception:  # noqa: BLE001 - a caixa de entrada prevalece
                logger.exception("conversas: falha ao vincular resposta a jornada")
            try:
                with transaction.atomic():
                    from apps.jornadas.acontecimentos import encaminhar_mensagem

                    encaminhar_mensagem(mensagem, event_id=evento.event_id)
            except Exception:  # noqa: BLE001 - a caixa de entrada prevalece
                logger.exception("conversas: falha ao iniciar jornada por mensagem")
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


def de_evolution(*, site_id: str, instancia: str, item: dict, tipo_do_upsert: str = "") -> Recebida | None:
    """`tipo_do_upsert`, quando o provedor informa: notify = fala nova, append = histórico."""
    chave = item.get("key") if isinstance(item.get("key"), dict) else {}
    if chave.get("fromMe") or item.get("fromMe"):
        return None  # saída feita pelo próprio aparelho; não é fala do contato
    remoto = str(chave.get("remoteJid") or "")
    if remoto.endswith("@g.us") or remoto.endswith("@broadcast") or remoto.endswith("@newsletter"):
        return None
    numero = _telefone_do_jid(chave, item)
    identificador = chave.get("id") or item.get("keyId") or item.get("id")
    if not numero and remoto.endswith("@lid"):
        # Sem o telefone real não há como responder nem ligar ao lead. Só o id vai ao log.
        logger.warning("conversas: JID @lid sem remoteJidAlt/senderPn (instancia=%s, id=%s)",
                       instancia, identificador)
    if not numero or not isinstance(identificador, str) or not identificador:
        return None
    conteudo = interacoes.desembrulhar(item.get("message") if isinstance(item.get("message"), dict) else {})
    escolha, citada = interacoes.resposta(conteudo)
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
    texto = texto or escolha
    if not texto and not midia:
        return None  # reação, enquete, chamada: nada para a conversa
    return Recebida(site_id=site_id, canal="whatsapp", endereco=numero, texto=str(texto),
                    id_externo=identificador, caixa=instancia, midia=midia, em_resposta_a=citada,
                    ocorrida_em=_momento(item.get("messageTimestamp")),
                    historica=str(tipo_do_upsert or item.get("type") or "").lower() == "append")


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
        texto = (interacoes.TITULOS.get(str(resposta.get("id") or "")) or
                 str(resposta.get("title") or resposta.get("id") or "")) if isinstance(resposta, dict) else ""
    elif tipo in _MIDIAS_CLOUD and isinstance(item.get(tipo), dict):
        dados = item[tipo]
        midia = {"tipo": _MIDIAS_CLOUD[tipo], "referencia": f"cloud:{dados.get('id') or ''}",
                 "mime": str(dados.get("mime_type") or "")}
        texto = str(dados.get("caption") or "")
    if not texto and not midia:
        return None
    return Recebida(site_id=site_id, canal="whatsapp", endereco=numero, texto=texto,
                    id_externo=identificador, caixa=numero_id, midia=midia,
                    em_resposta_a=str((item.get("context") or {}).get("id") or "")[:300],
                    ocorrida_em=_momento(item.get("timestamp")))
