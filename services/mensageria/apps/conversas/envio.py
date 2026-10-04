"""Enviar na conversa: uma chave de idempotência, uma mensagem.

WhatsApp usa o mesmo cliente do envio transacional e das jornadas
(`apps.whatsapp.service.enviar_mensagem`), com origem `conversa`. E-mail sai
pelo SMTP da célula, respondendo à última mensagem recebida (In-Reply-To).

Régua do agente: quando é INICIATIVA dele (abordagem, acompanhamento, lembrete), o
robô só fala entre 08h e 20h (America/Sao_Paulo, a mesma janela das jornadas), no
máximo `CONVERSAS_TETO_DIARIO_AGENTE` mensagens por dia a cada contato (padrão 3) e
nunca a quem recusou na `Preferencia` das jornadas. RESPOSTA a quem acabou de falar
(`e_resposta`) não passa por horário nem teto, e não conta no teto das iniciativas;
descadastro, consentimento, janela de 24h e conversa assumida valem sempre.
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
PENDENTE_ABANDONADA = timedelta(minutes=2)


@dataclass
class Resultado:
    # enviada | repetida | fora_da_janela | sem_consentimento | descadastrado | conversa_com_pessoa | falhou
    # | fora_do_horario | limite_diario (as duas últimas só para autor "agente" em iniciativa dele,
    # nunca em resposta a quem acabou de falar)
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


def fala_sem_resposta(conversa: Conversa, ignorar_pk=None, **da_fala) -> bool:
    """O contato falou de verdade (não o PARAR) e ainda não houve saída depois?

    `da_fala` restringe quais falas contam (ex.: `criada_em__gt=...`). Cada fala nova
    libera UMA saída: feita a saída, a próxima só depois de outra fala. Só fala ao
    vivo conta (histórico sincronizado depois não). A ordem é a de gravação (`criada_em`).
    `ignorar_pk` é a saída que está sendo reenviada: ela não conta como resposta já dada.
    """
    ultima = conversa.mensagens.filter(direcao="entrada", descadastro=False, **da_fala).filter(
        ocorrida_em__gte=F("criada_em") - FALA_AO_VIVO).order_by("-criada_em").first()
    if ultima is None:
        return False
    saidas = conversa.mensagens.filter(direcao="saida", criada_em__gt=ultima.criada_em).exclude(
        estado_envio="falhou")
    if ignorar_pk is not None:
        saidas = saidas.exclude(pk=ignorar_pk)
    return not saidas.exists()


def e_resposta(conversa: Conversa, agora: datetime, ignorar_pk=None) -> bool:
    """A fala do agente agora é RESPOSTA (e não iniciativa dele)?

    É quando o contato falou por último (ao vivo, não o PARAR), o agente ainda não
    respondeu essa fala e a janela de 24h está aberta. No máximo uma resposta por fala
    do contato: depois dela a próxima fala do agente já é iniciativa e cai na régua, o
    que impede laço de robô. Sai dos dados da conversa, sem campo próprio.
    """
    return janela_aberta(conversa, agora) and fala_sem_resposta(
        conversa, ignorar_pk=ignorar_pk, ocorrida_em__gte=agora - FALA_AO_VIVO)


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


def _iniciativas_do_agente_no_dia(conversa: Conversa, agora: datetime, ignorar_pk=None) -> int:
    """Saídas do agente a este contato no dia de São Paulo que foram INICIATIVA dele.

    Conta em qualquer canal do mesmo lead. Resposta (a primeira saída depois de uma fala
    do contato, dentro de 24h dela, a mesma regra de `e_resposta`) não conta no teto.
    `ignorar_pk` é a própria linha que está sendo reenviada: ela não conta contra o teto.
    """
    inicio, fim = _dia_de_sao_paulo(agora)
    mesmo_contato = Q(pk=conversa.pk)
    if conversa.ligacao == "ligada" and conversa.lead_id:
        mesmo_contato |= Q(lead_id=conversa.lead_id, ligacao="ligada")
    mensagens = MensagemDaConversa.objects.filter(
        conversa__in=Conversa.objects.filter(mesmo_contato, site_id=conversa.site_id),
        ocorrida_em__gte=inicio - FALA_AO_VIVO, ocorrida_em__lt=fim,
    ).exclude(direcao="saida", estado_envio="falhou").order_by("conversa_id", "criada_em").values_list(
        "conversa_id", "direcao", "autor", "descadastro", "criada_em", "ocorrida_em", "pk")
    iniciativas, conversa_atual, fala_aberta = 0, None, None
    for conversa_id, direcao, autor, descadastro, criada_em, ocorrida_em, pk in mensagens:
        if conversa_id != conversa_atual:
            conversa_atual, fala_aberta = conversa_id, None
        if direcao == "entrada":
            if not descadastro and ocorrida_em >= criada_em - FALA_AO_VIVO:
                fala_aberta = ocorrida_em  # a fala do contato que ainda espera resposta
            continue
        foi_resposta = fala_aberta is not None and ocorrida_em - fala_aberta < FALA_AO_VIVO
        fala_aberta = None  # qualquer saída responde a fala: a próxima só depois de outra
        if autor == "agente" and pk != ignorar_pk and ocorrida_em >= inicio and not foi_resposta:
            iniciativas += 1
    return iniciativas


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


def _fora_do_horario(agora: datetime) -> Resultado | None:
    if regua.dentro_da_janela(agora):
        return None
    return Resultado("fora_do_horario", detalhe="o agente so envia entre 08h e 20h (horario de Sao Paulo)",
                     reagendar_para=regua.proxima_janela(agora))


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
    if conversa.canal == "whatsapp" and not janela_aberta(conversa):
        from apps.consentimentos.servico import situacao

        permissao = situacao(conversa.site_id, conversa.endereco)
        if not permissao.permite:
            return Resultado("sem_consentimento", detalhe=f"o contato {permissao.frase()}")
    agora = _agora()
    reenvio = existente.pk if retomada and existente else None
    if autor == "agente":
        # Resposta a quem acabou de falar não passa por horário nem teto; iniciativa passa.
        if not e_resposta(conversa, agora, ignorar_pk=reenvio) and (recusa := _fora_do_horario(agora)):
            return recusa
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
            # Com a conversa travada, de novo: se outra saída respondeu a fala enquanto esta
            # esperava, esta já é iniciativa e cai na régua (uma resposta por fala do contato).
            if autor == "agente" and not e_resposta(conversa, agora, ignorar_pk=reenvio):
                if recusa := _fora_do_horario(agora):
                    return recusa
                teto = teto_diario_do_agente()
                # Na retomada, a própria saída pendente não conta contra o teto do dia.
                ja_enviadas = _iniciativas_do_agente_no_dia(conversa, agora, ignorar_pk=reenvio)
                if ja_enviadas >= teto:
                    return Resultado("limite_diario",
                                     detalhe=f"o agente ja mandou {teto} mensagens por iniciativa hoje a este contato",
                                     reagendar_para=regua.proxima_janela(_dia_de_sao_paulo(agora)[1]))
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
        logger.warning("e-mail da conversa %s: provedor recusou: %r", conversa.pk, exc)
        return falhar(f"provedor recusou ({type(exc).__name__}: {exc})")
    except (smtplib.SMTPException, OSError) as exc:
        registrar_falha()
        logger.warning("e-mail da conversa %s: resultado incerto: %r", conversa.pk, exc)
        # Pode ter saído; não reenviar às cegas com a mesma chave.
        return falhar(f"resultado incerto ({type(exc).__name__}: {exc})", "desconhecido")
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
