# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor.

    Cópia do padrão de `alunos`/`sugestoes` (Lei 3: copia-se o PADRÃO, nunca o
    arquivo por import cruzado). Nome da classe em minúsculas de propósito: o
    freeze de contrato exige que a chave de `components.securitySchemes`
    exportada seja `bearerAuth`, e o django-ninja usa o nome da classe do
    callback de auth como chave do security scheme.

    Esta célula nasce com DOIS pares (`docs/decisoes/DECISAO-fase-4-do-sininho.md`):
    `sugestoes→notificacoes` (a tela de avisos da Caixa) e `funil→notificacoes`
    (o sininho). `TOKENS_ACEITOS` já nasce genérico — um `set` de todo valor de
    env que comece com `TOKENS_ACEITOS_` — então um par novo é só uma variável
    de env nova (`TOKENS_ACEITOS_FUNIL`, `TOKENS_ACEITOS_SUGESTOES`), sem tocar
    neste arquivo (`config/settings.py`).
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
