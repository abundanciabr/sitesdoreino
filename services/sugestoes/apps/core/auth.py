# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor.

    Cópia do padrão de `alunos` (Lei 3: copia-se o PADRÃO, nunca o arquivo por
    import cruzado). Nome da classe em minúsculas de propósito: o freeze de
    contrato exige que a chave de `components.securitySchemes` exportada seja
    `bearerAuth`, e o django-ninja usa o nome da classe do callback de auth
    como chave do security scheme.

    **Este token responde "QUEM CHAMA", nunca "quem é o visitante".** São duas
    perguntas que se cruzam neste endpoint e confundi-las seria grave: o Bearer
    prova que o chamador é uma célula da casa (o `funil`); quem é a PESSOA vem
    do cookie de sessão que o `funil` repassa. Token válido com visitante
    anônimo é resposta 200 dizendo "ninguém", e não 401 — ver `apps/core/api.py`.
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
