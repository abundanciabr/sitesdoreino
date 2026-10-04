"""Eventos do quiz que trazem o aceite de contato pelo WhatsApp."""

from .servico import registrar_do_evento_do_quiz


def ao_quiz_completado(data, event_id=None, ator_id=None):
    registrar_do_evento_do_quiz(data, event_id, "quiz.completado")


def ao_quiz_captura_parcial(data, event_id=None, ator_id=None):
    registrar_do_evento_do_quiz(data, event_id, "quiz.captura_parcial")


def ao_quiz_consentimento(data, event_id=None, ator_id=None):
    registrar_do_evento_do_quiz(data, event_id, "quiz.consentimento")
