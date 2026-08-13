# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor.

    Nome da classe em minúsculas de propósito: o freeze de contrato exige que a
    chave de components.securitySchemes exportada seja "bearerAuth" (django-ninja
    usa o nome da classe do callback de auth como chave do security scheme).
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
