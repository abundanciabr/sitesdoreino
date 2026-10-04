"""Enviar na conversa: uma chave de idempotência, uma mensagem.

WhatsApp usa o mesmo cliente do envio transacional e das jornadas
(`apps.whatsapp.service.enviar_mensagem`), com origem `conversa`. E-mail sai
pelo SMTP da célula, respondendo à última mensagem recebida (In-Reply-To).
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage, make_msgid
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import descadastro as descadastros
from .models import Conversa, MensagemDaConversa

logger = logging.getLogger(__name__)
PENDENTE_ABANDONADA = timedelta(minutes=2)


@dataclass
class Resultado:
    resultado: str  # enviada | repetida | fora_da_janela | descadastrado | conversa_com_pessoa | falhou
    mensagem: MensagemDaConversa | None = None
    detalhe: str = ""


def janela_aberta(conversa: Conversa, agora=None) -> bool:
    if conversa.canal != "whatsapp":
        return True
    agora = agora or timezone.now()
    return bool(conversa.janela_aberta_ate and conversa.janela_aberta_ate > agora)


def bloqueio_por_descadastro(conversa: Conversa) -> bool:
    """Descadastrado só recebe resposta a uma fala NOVA dele, nunca acompanhamento."""
    registro = descadastros.ativo(conversa)
    if registro is None:
        return False
    return not conversa.mensagens.filter(
        direcao="entrada", descadastro=False, ocorrida_em__gt=registro.registrado_em,
    ).exists()


def _pendente_abandonada(mensagem: MensagemDaConversa) -> bool:
    """Linha criada e nunca enviada: o processo caiu antes de chamar o provedor."""
    return (mensagem.estado_envio == "pendente" and mensagem.mensagem_whatsapp_id is None
            and mensagem.ocorrida_em < timezone.now() - PENDENTE_ABANDONADA)


def _estado_whatsapp(status: str) -> str:
    return status if status in {"desconhecido", "aceito", "enviado", "entregue", "lido", "falhou"} else "desconhecido"


def enviar(*, conversa: Conversa, texto: str, chave_idempotencia: str, autor: str = "agente",
           autor_id: str = "", modelo: dict | None = None, assunto: str = "") -> Resultado:
    chave = chave_idempotencia.strip()
    existente = conversa.mensagens.filter(chave_idempotencia=chave).first()
    retomada = False
    if existente is not None and existente.estado_envio != "falhou":
        if not _pendente_abandonada(existente):
            return Resultado("repetida", _sincronizar(existente))
        retomada = True
    if autor == "agente" and conversa.estado == "pessoa":
        return Resultado("conversa_com_pessoa", detalhe="uma pessoa da equipe assumiu esta conversa")
    if bloqueio_por_descadastro(conversa):
        return Resultado("descadastrado", detalhe=f"o contato pediu para parar no {conversa.canal}")
    if conversa.canal == "whatsapp" and not janela_aberta(conversa) and not modelo:
        return Resultado("fora_da_janela",
                         detalhe="fora das 24h desde a ultima mensagem do contato; use modelo aprovado")
    try:
        with transaction.atomic():
            if existente is None:
                existente = MensagemDaConversa.objects.create(
                    conversa=conversa, direcao="saida", autor=autor, autor_id=autor_id[:100],
                    texto=texto, assunto=assunto[:300], estado_envio="pendente",
                    chave_idempotencia=chave, ocorrida_em=timezone.now(),
                )
            elif retomada:
                # Quem ganhar a disputa pela linha abandonada é o único a reenviar.
                reservada = MensagemDaConversa.objects.filter(
                    pk=existente.pk, estado_envio="pendente", mensagem_whatsapp__isnull=True,
                    ocorrida_em__lt=timezone.now() - PENDENTE_ABANDONADA,
                ).update(ocorrida_em=timezone.now())
                if not reservada:
                    return Resultado("repetida", _sincronizar(existente))
                existente.refresh_from_db()
            else:
                existente.estado_envio, existente.erro = "pendente", ""
                existente.save(update_fields=["estado_envio", "erro"])
    except IntegrityError:
        repetida = conversa.mensagens.filter(chave_idempotencia=chave).first()
        return Resultado("repetida", repetida)
    if conversa.canal == "whatsapp":
        mensagem = _enviar_whatsapp(conversa, existente, modelo)
    else:
        mensagem = _enviar_email(conversa, existente)
    Conversa.objects.filter(pk=conversa.pk).update(ultima_mensagem_em=mensagem.ocorrida_em)
    return Resultado("falhou" if mensagem.estado_envio == "falhou" else "enviada", mensagem, mensagem.erro)


def _enviar_whatsapp(conversa: Conversa, mensagem: MensagemDaConversa, modelo: dict | None) -> MensagemDaConversa:
    from apps.whatsapp.service import enviar_mensagem

    resultado = enviar_mensagem(
        site_id=conversa.site_id, destinatario=conversa.endereco, corpo=mensagem.texto,
        origem="conversa", referencia=f"{conversa.id}:{mensagem.chave_idempotencia}", modelo=modelo,
    )
    mensagem.mensagem_whatsapp = resultado
    mensagem.estado_envio = _estado_whatsapp(resultado.status)
    mensagem.erro = (resultado.erro or "")[:300]
    mensagem.id_externo = resultado.provider_id or ""
    mensagem.save(update_fields=["mensagem_whatsapp", "estado_envio", "erro", "id_externo"])
    return mensagem


def _sincronizar(mensagem: MensagemDaConversa) -> MensagemDaConversa:
    """Saída por WhatsApp acompanha o estado que os retornos do provedor gravam."""
    if mensagem.mensagem_whatsapp_id:
        atual = mensagem.mensagem_whatsapp
        estado = _estado_whatsapp(atual.status)
        if estado != mensagem.estado_envio or atual.provider_id != mensagem.id_externo:
            mensagem.estado_envio = estado
            mensagem.id_externo = atual.provider_id or ""
            mensagem.erro = (atual.erro or "")[:300]
            mensagem.save(update_fields=["estado_envio", "id_externo", "erro"])
    return mensagem


def _enviar_email(conversa: Conversa, mensagem: MensagemDaConversa) -> MensagemDaConversa:
    from apps.eventos.capacidade import CapacidadeDoProvedor, registrar_falha, registrar_sucesso, reservar_envio
    from apps.eventos.models import EnderecoDeEmail

    def falhar(erro: str, estado: str = "falhou") -> MensagemDaConversa:
        mensagem.estado_envio, mensagem.erro = estado, erro[:300]
        mensagem.save(update_fields=["estado_envio", "erro"])
        return mensagem

    if EnderecoDeEmail.objects.filter(email=conversa.endereco).exists():
        return falhar("endereco bloqueado por devolucao ou reclamacao")
    if not (settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL):
        return falhar("e-mail nao configurado neste ambiente")
    ultima = conversa.mensagens.filter(direcao="entrada").exclude(id_externo="").order_by("-ocorrida_em").first()
    assunto = mensagem.assunto or (ultima.assunto if ultima else "")
    if ultima and assunto and not assunto.lower().startswith("re:"):
        assunto = "Re: " + assunto
    remetente = settings.DEFAULT_FROM_EMAIL
    dominio = remetente.rsplit("@", 1)[-1].strip(">") or None
    message_id = make_msgid(domain=dominio)
    cabecalhos = {"Message-ID": message_id}
    if ultima:
        cabecalhos["In-Reply-To"] = ultima.id_externo
        cabecalhos["References"] = ultima.id_externo
    carta = EmailMessage(subject=assunto or "Mensagem da equipe", body=mensagem.texto,
                         from_email=remetente, to=[conversa.endereco], headers=cabecalhos)
    try:
        reservar_envio()
    except CapacidadeDoProvedor:
        return falhar("limite de envio do provedor; tente de novo mais tarde")
    try:
        quantos = carta.send(fail_silently=False)
    except (smtplib.SMTPConnectError, smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused, ConnectionError, TimeoutError) as exc:
        registrar_falha()
        return falhar(f"provedor recusou ({type(exc).__name__})")
    except (smtplib.SMTPException, OSError) as exc:
        registrar_falha()
        # Pode ter saído; não reenviar às cegas com a mesma chave.
        return falhar(f"resultado incerto ({type(exc).__name__})", "desconhecido")
    if quantos != 1:
        return falhar("provedor nao aceitou a carta")
    registrar_sucesso()
    mensagem.estado_envio = "enviado"
    mensagem.id_externo = message_id
    mensagem.assunto = assunto[:300]
    mensagem.em_resposta_a = ultima.id_externo if ultima else ""
    mensagem.erro = ""
    mensagem.save(update_fields=["estado_envio", "id_externo", "assunto", "em_resposta_a", "erro"])
    return mensagem
