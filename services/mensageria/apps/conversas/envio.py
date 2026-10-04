"""Enviar na conversa: uma chave de idempotência, uma mensagem.

WhatsApp usa o mesmo cliente do envio transacional e das jornadas
(`apps.whatsapp.service.enviar_mensagem`), com origem `conversa`. E-mail sai
pelo SMTP da célula, respondendo à última mensagem recebida (In-Reply-To).

Régua do agente: o robô só fala entre 08h e 20h (America/Sao_Paulo, a mesma
janela das jornadas), no máximo `CONVERSAS_TETO_DIARIO_AGENTE` mensagens por dia
a cada contato (padrão 3) e nunca a quem recusou na `Preferencia` das jornadas.
Pessoa da equipe fala a qualquer hora e sem teto.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.mail import EmailMessage, make_msgid
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.jornadas import regua

from . import descadastro as descadastros
from . import enderecos
from .models import Conversa, MensagemDaConversa

logger = logging.getLogger(__name__)
TETO_DIARIO_PADRAO = 3
# Fala do contato só conta como "nova" quando chegou perto da hora em que ela foi dita
# (histórico sincronizado depois não libera resposta a quem pediu para parar).
FALA_AO_VIVO = timedelta(hours=24)


@dataclass
class Resultado:
    # enviada | repetida | fora_da_janela | descadastrado | conversa_com_pessoa | falhou
    # | fora_do_horario | limite_diario (as duas últimas só para autor "agente")
    resultado: str
    mensagem: MensagemDaConversa | None = None
    detalhe: str = ""
    # Quando a recusa é só de horário ou de teto do dia: o próximo instante permitido.
    reagendar_para: datetime | None = None


def janela_aberta(conversa: Conversa, agora=None) -> bool:
    if conversa.canal != "whatsapp":
        return True
    agora = agora or timezone.now()
    return bool(conversa.janela_aberta_ate and conversa.janela_aberta_ate > agora)


def fala_sem_resposta(conversa: Conversa, **da_fala) -> bool:
    """O contato falou de verdade (não o PARAR) e ainda não houve saída depois?

    `da_fala` restringe quais falas contam (ex.: `criada_em__gt=...`). Cada fala nova
    libera UMA saída: feita a saída, a próxima só depois de outra fala. Só fala ao
    vivo conta (histórico sincronizado depois não). A ordem é a de gravação (`criada_em`).
    """
    ultima = conversa.mensagens.filter(direcao="entrada", descadastro=False, **da_fala).filter(
        ocorrida_em__gte=F("criada_em") - FALA_AO_VIVO).order_by("-criada_em").first()
    if ultima is None:
        return False
    return not conversa.mensagens.filter(direcao="saida", criada_em__gt=ultima.criada_em).exclude(
        estado_envio="falhou").exists()


def bloqueio_por_descadastro(conversa: Conversa) -> bool:
    """Descadastrado só recebe resposta a uma fala NOVA dele, nunca acompanhamento.

    Depois do PARAR, cada fala nova libera no máximo UMA saída. "Depois" é pela ordem de
    gravação: a hora do provedor tem resolução de segundo e a fala no mesmo segundo do
    PARAR não pode ficar de fora.
    """
    registro = descadastros.ativo(conversa)
    if registro is None:
        return False
    parada = conversa.mensagens.filter(direcao="entrada", descadastro=True).order_by("-criada_em").first()
    if parada is not None:
        return not fala_sem_resposta(conversa, criada_em__gt=parada.criada_em)
    return not fala_sem_resposta(conversa, ocorrida_em__gte=registro.registrado_em)


def _agora() -> datetime:
    return timezone.now()


def teto_diario_do_agente() -> int:
    try:
        teto = int(getattr(settings, "CONVERSAS_TETO_DIARIO_AGENTE", TETO_DIARIO_PADRAO))
    except (TypeError, ValueError):
        return TETO_DIARIO_PADRAO
    return teto if teto > 0 else TETO_DIARIO_PADRAO


def _dia_de_sao_paulo(agora: datetime) -> tuple[datetime, datetime]:
    inicio = timezone.make_aware(datetime.combine(timezone.localdate(agora), time.min),
                                 timezone.get_current_timezone())
    return inicio, inicio + timedelta(days=1)


def _mensagens_do_agente_no_dia(conversa: Conversa, agora: datetime) -> int:
    """Saídas do agente a este contato no dia de São Paulo (em qualquer canal do mesmo lead)."""
    inicio, fim = _dia_de_sao_paulo(agora)
    mesmo_contato = Q(pk=conversa.pk)
    if conversa.ligacao == "ligada" and conversa.lead_id:
        mesmo_contato |= Q(lead_id=conversa.lead_id, ligacao="ligada")
    return MensagemDaConversa.objects.filter(
        conversa__in=Conversa.objects.filter(mesmo_contato, site_id=conversa.site_id),
        direcao="saida", autor="agente", ocorrida_em__gte=inicio, ocorrida_em__lt=fim,
    ).exclude(estado_envio="falhou").count()


def recusa_por_preferencia(conversa: Conversa) -> bool:
    """A pessoa recusou o acompanhamento neste canal na Preferencia das jornadas?

    A Preferencia é por id de plataforma; o id vem da identidade pelo e-mail do
    contato. Sem como achar a pessoa, ausência não é recusa (o PARAR desta caixa
    já barra por `bloqueio_por_descadastro`). Preferência ilegível recusa.
    """
    from apps.jornadas.models import Preferencia

    recusadas = Preferencia.objects.filter(
        site_id=conversa.site_id, canal=conversa.canal, aceita=False,
        classe__in=descadastros.CLASSES_DE_ACOMPANHAMENTO,
    )
    try:
        if not recusadas.exists():
            return False
        pessoa = descadastros.pessoa_da_conversa(conversa)
        return bool(pessoa) and recusadas.filter(destinatario_id=pessoa).exists()
    except DatabaseError:
        logger.exception("conversas: preferencia ilegivel; o agente nao envia")
        return True


def _estado_whatsapp(status: str) -> str:
    return status if status in {"desconhecido", "aceito", "enviado", "entregue", "lido", "falhou"} else "desconhecido"


def enviar(*, conversa: Conversa, texto: str, chave_idempotencia: str, autor: str = "agente",
           autor_id: str = "", modelo: dict | None = None, assunto: str = "") -> Resultado:
    chave = chave_idempotencia.strip()
    existente = conversa.mensagens.filter(chave_idempotencia=chave).first()
    if existente is not None and existente.estado_envio != "falhou":
        return Resultado("repetida", _sincronizar(existente))
    if autor == "agente" and conversa.estado == "pessoa":
        return Resultado("conversa_com_pessoa", detalhe="uma pessoa da equipe assumiu esta conversa")
    if bloqueio_por_descadastro(conversa):
        return Resultado("descadastrado", detalhe=f"o contato pediu para parar no {conversa.canal}")
    if conversa.canal == "whatsapp" and not janela_aberta(conversa) and not modelo:
        return Resultado("fora_da_janela",
                         detalhe="fora das 24h desde a ultima mensagem do contato; use modelo aprovado")
    agora = _agora()
    if autor == "agente":
        if not regua.dentro_da_janela(agora):
            return Resultado("fora_do_horario", detalhe="o agente so envia entre 08h e 20h (horario de Sao Paulo)",
                             reagendar_para=regua.proxima_janela(agora))
        # Responder a uma fala dele de agora é atendimento; a preferência vale para o resto.
        if not fala_sem_resposta(conversa, ocorrida_em__gte=agora - FALA_AO_VIVO) and recusa_por_preferencia(conversa):
            return Resultado("descadastrado", detalhe=f"o contato recusou mensagens no {conversa.canal}")
    try:
        with transaction.atomic():
            # Trava a conversa: duas saídas ao mesmo tempo não passam juntas pelo teto
            # nem pela regra de uma saída por fala depois do PARAR.
            Conversa.objects.select_for_update().filter(pk=conversa.pk).first()
            if bloqueio_por_descadastro(conversa):
                return Resultado("descadastrado", detalhe=f"o contato pediu para parar no {conversa.canal}")
            if autor == "agente":
                teto = teto_diario_do_agente()
                if _mensagens_do_agente_no_dia(conversa, agora) >= teto:
                    return Resultado("limite_diario",
                                     detalhe=f"o agente ja mandou {teto} mensagens hoje a este contato",
                                     reagendar_para=regua.proxima_janela(_dia_de_sao_paulo(agora)[1]))
            if existente is None:
                existente = MensagemDaConversa.objects.create(
                    conversa=conversa, direcao="saida", autor=autor, autor_id=autor_id[:100],
                    texto=texto, assunto=assunto[:300], estado_envio="pendente",
                    chave_idempotencia=chave, ocorrida_em=timezone.now(),
                )
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

    if enderecos.remetente_automatico(conversa.endereco):
        return falhar("endereco automatico (nao responda ou devolucao): nao recebe mensagem")
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
