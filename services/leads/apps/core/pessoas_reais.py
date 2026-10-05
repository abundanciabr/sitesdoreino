"""Recusa dados de teste antes de criar contatos ou histórico comercial."""
import re
from functools import wraps
from django.conf import settings

MARCADOR = re.compile(r"(^|[^a-z0-9])(teste|test|sandbox|canario|canário)([^a-z0-9]|$)", re.I)
DOMINIOS = {"example.com", "example.org", "example.net", "exemplo.test", "testuser.com", "teste.meshcraft.top"}


class ContatoDeTeste(ValueError):
    pass


def dados_de_teste(dados):
    if not isinstance(dados, dict):
        return False
    if any(dados.get(k) is True for k in ("em_teste", "is_test", "test_mode", "sandbox")):
        return True
    if str(dados.get("ambiente", "")).lower() in {"sandbox", "test", "teste"}:
        return True
    if str(dados.get("origem", "")).lower() == "teste":
        return True
    for campo in ("name", "nome", "nome_completo", "lead_name", "source", "site_id", "platform_site_id"):
        if MARCADOR.search(str(dados.get(campo) or "")):
            return True
    for campo in ("email", "lead_email"):
        email = str(dados.get(campo) or "").strip().lower()
        dominio = email.rsplit("@", 1)[-1] if "@" in email else ""
        if dominio in DOMINIOS or dominio.endswith((".test", ".invalid", ".example")):
            return True
    if any(str(t).lower() in {"teste", "test", "sandbox"} for t in dados.get("tags", []) or []):
        return True
    return any(dados_de_teste(dados.get(k)) for k in ("customer", "contato", "lead", "metadata", "context"))


def conferir(dados):
    # A exceção existe apenas para fixtures em bancos isolados de testes.
    if getattr(settings, "CRM_REJEITAR_TESTES", True) and dados_de_teste(dados):
        raise ContatoDeTeste("O CRM aceita somente pessoas reais. Dados de teste não são permitidos.")


def ignorar_evento_de_teste(funcao):
    @wraps(funcao)
    def executar(event_id, data):
        from django.db import transaction
        try:
            with transaction.atomic():
                conferir(data)
                return funcao(event_id, data)
        except ContatoDeTeste:
            return None
    return executar
