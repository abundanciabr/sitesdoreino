# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de `TOKENS_ACEITOS`, um por par consumidor.

    Cópia do PADRÃO de `identidade`/`alunos`/`forum`/`gamificacao` (Lei 3:
    copia-se o padrão entre células, nunca se importa código de uma na outra).
    Nome da classe em minúsculas de propósito: o freeze de contrato exige que a
    chave de `components.securitySchemes` seja `bearerAuth`, e o django-ninja
    usa o nome da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa (no degrau 1.3, o editor do Admin, com
    `TOKENS_ACEITOS_ADMIN`), e não diz quem é a pessoa do outro lado do
    navegador. A pergunta "quem é a pessoa" só nasce nesta célula no degrau 1.8,
    com a sessão repassada à `identidade`; a porta deste arquivo é máquina para
    máquina, sem sessão e sem cookie.

    E o Bearer é o ÚNICO cadeado desta porta: a célula roda sob
    `SCRIPT_NAME=/cursos` e o corte do prefixo é do Django, não do Traefik,
    então `/api/cursos/...` é alcançável pela borda pública em
    `meshcraft.top/cursos/api/cursos/...` (`armadilhas/186`; premissa fixada em
    `tests/test_healthz_script_name.py`). Não copie daqui a frase "a porta
    interna não resolve pela borda": na `identidade` ela é verdadeira, aqui não.
    O guarda que importa é o 401 em TODAS as operações, inclusive com o
    conjunto de tokens vazio (`tests/test_porta_exige_bearer.py`).
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
