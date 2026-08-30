# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de `TOKENS_ACEITOS_*` — um por par consumidor.

    Cópia do PADRÃO de `identidade`/`alunos`/`sugestoes` (Lei 3: copia-se o
    padrão entre células, nunca se importa código de uma na outra). Nome da
    classe em minúsculas de propósito: o freeze de contrato exige que a chave
    de `components.securitySchemes` seja `bearerAuth`, e o django-ninja usa o
    nome da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa — não diz quem é a pessoa do outro lado do
    navegador, porque nesta porta NÃO HÁ pessoa nenhuma: a superfície interna
    do fórum não recebe cookie e não reconhece ninguém.

    É por isso que ela só responde sobre ÁREA PÚBLICA (ver `apps/core/api.py`):
    sem pessoa, o único recorte que se pode devolver com honestidade é o que
    qualquer visitante — e o robô do Google — já veria.
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
