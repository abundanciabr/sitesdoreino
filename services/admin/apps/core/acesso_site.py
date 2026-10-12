"""Consulta a lista vigente de admins para o acesso aos cursos e ao portfólio."""

from contextlib import nullcontext


def e_administrador(email):
    email = (email or "").strip().lower()
    if not email:
        return False
    try:
        from config.runtime import serving
    except ImportError:
        contexto = nullcontext()
    else:
        contexto = serving("admin")
    with contexto:
        from .porta import _emails_autorizados
        return email in _emails_autorizados()
