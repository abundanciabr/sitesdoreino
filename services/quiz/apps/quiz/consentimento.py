"""Aceite de contato pelo WhatsApp no formulário do quiz.

A caixa vem desmarcada. Só vale com telefone informado. O aceite viaja nos
eventos do quiz no bloco `consentimento` (sem dado pessoal: o telefone já vai
em `lead.phone`):

    "consentimento": {"whatsapp": {
        "aceito": true,
        "texto": "<o texto que a pessoa leu>",
        "versao_texto": "whatsapp-v1",
        "registrado_em": "2026-10-03T21:00:00-03:00"   # null quando não marcou
    }}

- `quiz.completado` e `quiz.captura_parcial` levam o bloco sempre.
- `quiz.consentimento` sai quando a pessoa muda a escolha depois da primeira
  captura e antes de concluir (a captura parcial é publicada uma vez só).

Quem guarda e aplica a permissão é a mensageria (`apps.consentimentos`).
"""

from __future__ import annotations

from .models import ConsentimentoDoContato

CAMPO = "aceita_whatsapp"
VERSAO_TEXTO = "whatsapp-v1"
TEXTO_WHATSAPP = (
    "Aceito receber mensagens da equipe pelo WhatsApp neste número. "
    "Posso pedir para parar quando quiser."
)
_MARCADO = {"1", "on", "sim", "true"}


def marcou(post) -> bool:
    return (post.get(CAMPO) or "").strip().lower() in _MARCADO


def registrar(quiz, session_id, post, telefone: str):
    """Grava a escolha da sessão. Volta (registro, mudou).

    `mudou` = a permissão que vale para a mensageria mudou (marcou, desmarcou,
    ou trocou o número estando marcada).
    """
    aceita = marcou(post) and bool((telefone or "").strip())
    registro, criado = ConsentimentoDoContato.objects.get_or_create(
        quiz=quiz,
        session_id=session_id,
        defaults={
            "site_id": quiz.site_id,
            "telefone": (telefone or "")[:32],
            "aceita_whatsapp": aceita,
            "texto_whatsapp": TEXTO_WHATSAPP,
            "versao_texto": VERSAO_TEXTO,
        },
    )
    if criado:
        # Linha nova desmarcada não muda nada para quem consome.
        return registro, aceita
    telefone = (telefone or "")[:32]
    outro_numero = bool(telefone) and registro.telefone != telefone
    mudou = registro.aceita_whatsapp != aceita or (aceita and outro_numero)
    if mudou or outro_numero:
        registro.aceita_whatsapp = aceita
        if telefone:
            registro.telefone = telefone
        registro.texto_whatsapp = TEXTO_WHATSAPP
        registro.versao_texto = VERSAO_TEXTO
        registro.save()
    return registro, mudou


def bloco(registro) -> dict:
    if registro is None:
        return {
            "whatsapp": {
                "aceito": False,
                "texto": TEXTO_WHATSAPP,
                "versao_texto": VERSAO_TEXTO,
                "registrado_em": None,
            }
        }
    return {
        "whatsapp": {
            "aceito": registro.aceita_whatsapp,
            "texto": registro.texto_whatsapp,
            "versao_texto": registro.versao_texto,
            "registrado_em": (
                registro.atualizado_em.isoformat() if registro.aceita_whatsapp else None
            ),
        }
    }


def bloco_da_sessao(quiz, session_id) -> dict:
    registro = None
    if session_id:
        registro = ConsentimentoDoContato.objects.filter(
            quiz=quiz, session_id=session_id
        ).first()
    return bloco(registro)


def emitir_mudanca(quiz, captura, registro):
    """`quiz.consentimento`: a escolha mudou depois da primeira captura."""
    from .models import OutboxEvent
    from .respostas import lead_do_contato

    return OutboxEvent.objects.create(
        event="quiz.consentimento",
        payload={
            "site_id": captura.site_id,
            "quiz_slug": quiz.slug,
            "sessao": str(captura.session_id),
            "captura_id": str(captura.id),
            "lead": lead_do_contato(
                captura.lead_email, captura.lead_name, captura.lead_phone
            ),
            "consentimento": bloco(registro),
        },
    )
