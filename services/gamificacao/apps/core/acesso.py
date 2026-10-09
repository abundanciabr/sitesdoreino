"""Quem é administrador, para a página /conquistas/ ficar só com eles.

Admin = o e-mail da sessão completa (`getSessionFull`) é administrador na
célula admin (`isAdministrator`). Pertencer à equipe não concede esse acesso.

FECHADO: env ausente, timeout (3 s), erro HTTP ou resposta estranha = não admin.
Nunca levanta. No máximo uma checagem por requisição (guardada no `request`).
"""

import logging
import os

import httpx

from .sessao import http

logger = logging.getLogger(__name__)

TIMEOUT_CURTO = 3.0


def _env(nome: str) -> str:
    return (os.environ.get(nome) or "").strip()


def _email_da_sessao(request) -> str:
    base = _env("IDENTIDADE_API_URL").rstrip("/")
    token = _env("IDENTIDADE_API_TOKEN")
    cookie = request.META.get("HTTP_COOKIE", "")
    if not (base and token and cookie):
        return ""
    resposta = http().get(
        f"{base}/sessao/completa",
        headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
        timeout=TIMEOUT_CURTO,
    )
    if resposta.status_code != 200:
        logger.warning("conquistas: identidade respondeu HTTP %s", resposta.status_code)
        return ""
    corpo = resposta.json()
    if not (isinstance(corpo, dict) and corpo.get("autenticado") is True):
        return ""
    email = corpo.get("email")
    return email.strip() if isinstance(email, str) else ""


def _admin_pelo_email(request) -> bool:
    base = _env("ADMIN_API_URL").rstrip("/")
    token = _env("ADMIN_API_TOKEN")
    if not (base and token):
        return False
    email = _email_da_sessao(request)
    if not email:
        return False
    resposta = http().post(
        f"{base}/administradores/consultar",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": email},
        timeout=TIMEOUT_CURTO,
    )
    if resposta.status_code != 200:
        logger.warning("conquistas: admin respondeu HTTP %s", resposta.status_code)
        return False
    corpo = resposta.json()
    return isinstance(corpo, dict) and corpo.get("e_administrador") is True


def e_admin(request, pessoa_id) -> bool:
    if not pessoa_id:
        return False
    if hasattr(request, "_conquistas_e_admin"):
        return request._conquistas_e_admin
    try:
        resultado = _admin_pelo_email(request)
    except (httpx.HTTPError, ValueError, OSError) as erro:
        logger.warning("conquistas: não deu para conferir admin (%s)", type(erro).__name__)
        resultado = False
    except Exception as erro:  # nunca 500 por causa da conferência
        logger.warning("conquistas: erro ao conferir admin (%s)", type(erro).__name__)
        resultado = False
    request._conquistas_e_admin = resultado
    return resultado
