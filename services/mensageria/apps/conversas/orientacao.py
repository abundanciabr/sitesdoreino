"""Orientação fixa a quem escreve sem ser lead do quiz (ou de telefone ambíguo).

Texto simples por site, sem modelo de linguagem e sem dado de lead. Vale só no
WhatsApp, dentro da janela de 24h que a própria mensagem da pessoa abriu, e no
máximo uma vez a cada 24h por conversa. Quem pediu PARAR não recebe nada; o
envio passa por `envio.enviar` (descadastro, janela e conversa assumida valem).
Resposta a quem acabou de falar não passa por horário nem teto (é "resposta"
na régua do agente; aqui o autor é "sistema", que nunca entra nessa régua).

Quem não veio do quiz NUNCA vira contato nem oportunidade: a conversa só fica na
caixa da equipe, com a etiqueta "sem origem no quiz".
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import enderecos, envio
from .models import Conversa, MensagemDaConversa, OrientacaoDoSite

logger = logging.getLogger(__name__)
INTERVALO = timedelta(hours=24)
_EMAIL = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")

PEDIDO_DE_EMAIL = (
    "Olá! Aqui é o assistente da equipe. Para continuar o seu atendimento, preciso "
    "confirmar quem é você. Pode me dizer o e-mail que você usou no quiz? "
    "Se preferir não receber mensagens, responda PARAR."
)
CONFIRMACAO = (
    "Obrigado! Recebi a informação e passei para a equipe confirmar. "
    "Assim que estiver tudo certo, a conversa continua por aqui."
)


def email_do_texto(texto: str) -> str:
    """O primeiro e-mail que a pessoa escreveu, ou vazio."""
    for achado in _EMAIL.findall(texto or ""):
        endereco = enderecos.email(achado)
        if endereco:
            return endereco
    return ""


def texto_para_quem_nao_e_do_quiz(site_id: str) -> str:
    config = OrientacaoDoSite.objects.filter(site_id=site_id).first()
    quiz = (config.endereco_quiz if config else "").strip()
    geral = (config.atendimento_geral if config else "").strip()
    onde = f"em {quiz}" if quiz else "no nosso site"
    atendimento = (
        f"Para falar com a equipe sobre outro assunto: {geral}."
        if geral else
        "Sua mensagem ficou na caixa de entrada da equipe, que responde assim que puder."
    )
    return (
        "Olá! Aqui é o assistente da equipe. O atendimento por este número é para quem "
        f"fez o quiz do site. Se você ainda não fez, é só responder ao quiz {onde} e a "
        f"conversa continua por aqui. {atendimento} "
        "Se preferir não receber mensagens, responda PARAR."
    )


def _reservar(conversa_id, tipo: str):
    """Marca a orientação como enviada agora, a menos que já tenha saído nas últimas 24h.

    Volta o estado anterior (para desfazer se o envio não sair) ou None quando
    não deve enviar. A trava na linha evita duas orientações com duas mensagens
    chegando juntas.
    """
    agora = timezone.now()
    with transaction.atomic():
        conversa = Conversa.objects.select_for_update().get(pk=conversa_id)
        if conversa.orientacao_enviada_em and conversa.orientacao_enviada_em > agora - INTERVALO:
            return None
        anterior = (conversa.orientacao_enviada_em, conversa.orientacao_tipo)
        conversa.orientacao_enviada_em, conversa.orientacao_tipo = agora, tipo
        conversa.save(update_fields=["orientacao_enviada_em", "orientacao_tipo", "atualizada_em"])
        return anterior


def _desfazer(conversa_id, anterior) -> None:
    Conversa.objects.filter(pk=conversa_id).update(
        orientacao_enviada_em=anterior[0], orientacao_tipo=anterior[1])


def _enviar(conversa: Conversa, mensagem: MensagemDaConversa, tipo: str, texto: str):
    return envio.enviar(
        conversa=conversa, texto=texto, chave_idempotencia=f"orientacao:{tipo}:{mensagem.id}",
        autor="sistema", autor_id=f"orientacao:{tipo}",
    )


def apos_receber(mensagem: MensagemDaConversa, *, equipe_acabou_de_confirmar: bool = False) -> str:
    """Envia, se couber, a orientação da conversa. Volta o que fez (para o log e os testes).

    Nunca levanta: a mensagem recebida já está gravada e a falta de orientação
    não pode derrubar a entrada.
    """
    try:
        return _apos_receber(mensagem, equipe_acabou_de_confirmar)
    except Exception:  # noqa: BLE001 - a orientação é cortesia; a mensagem não se perde
        logger.exception("conversas: falha ao orientar a conversa %s", mensagem.conversa_id)
        return "falhou"


def _apos_receber(mensagem: MensagemDaConversa, equipe_acabou_de_confirmar: bool) -> str:
    conversa = Conversa.objects.get(pk=mensagem.conversa_id)
    if conversa.canal != "whatsapp" or mensagem.descadastro or conversa.estado != "agente":
        return "nada"
    if not envio.janela_aberta(conversa):
        return "nada"  # a orientação só vale dentro da janela que a própria pessoa abriu
    if equipe_acabou_de_confirmar:
        resultado = _enviar(conversa, mensagem, "confirmacao", CONFIRMACAO)
        return f"confirmacao:{resultado.resultado}"
    if conversa.ligacao == "desconhecida":
        tipo, texto = "desconhecida", texto_para_quem_nao_e_do_quiz(conversa.site_id)
    elif conversa.ligacao == "ambigua" and not conversa.equipe_confirma:
        tipo, texto = "ambigua", PEDIDO_DE_EMAIL
    else:
        return "nada"
    anterior = _reservar(conversa.pk, tipo)
    if anterior is None:
        return "ja_orientada"
    try:
        resultado = _enviar(conversa, mensagem, tipo, texto)
    except Exception:
        _desfazer(conversa.pk, anterior)
        raise
    if resultado.resultado not in ("enviada", "repetida"):
        _desfazer(conversa.pk, anterior)  # não saiu: a próxima fala da pessoa tenta de novo
    return f"{tipo}:{resultado.resultado}"
