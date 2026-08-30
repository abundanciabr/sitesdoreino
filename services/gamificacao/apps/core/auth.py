# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de `TOKENS_ACEITOS` — um por par consumidor.

    Cópia do PADRÃO de `identidade`/`alunos`/`forum` (Lei 3: copia-se o padrão
    entre células, nunca se importa código de uma na outra). Nome da classe em
    minúsculas de propósito: o freeze de contrato exige que a chave de
    `components.securitySchemes` seja `bearerAuth`, e o django-ninja usa o nome
    da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa — não diz quem é a pessoa do outro lado do
    navegador. Quem responde ESSA pergunta é o cookie de sessão, repassado
    opaco e resolvido em `apps/core/sessao.py` contra a `identidade`.

    Confundir as duas credenciais é o erro caro desta porta, e ele tem
    consequência assimétrica nas duas operações:

    - `getPublicProfiles` responde a chamador **sem** sessão de pessoa, de
      propósito (decisão B da Sessão B de 30/08/2026): a etiqueta do aluno é
      visível para todo mundo, inclusive visitante não logado.
    - `getMyStatus` responde 200 sempre, mas o CONTEÚDO é do dono da sessão —
      sem cookie, `autenticado: false` com os números em null.

    Em nenhuma das duas o Bearer diz quem é a pessoa. E o Bearer é o ÚNICO
    cadeado desta porta: a célula roda sob `SCRIPT_NAME=/conquistas` e o corte
    do prefixo é do Django, não do Traefik, então `/api/gamificacao/...` é
    alcançável pela borda pública em `meshcraft.top/conquistas/...`
    (`armadilhas/186`; guarda em `tests/test_healthz_script_name.py`). Não
    copie daqui a frase "a porta interna não resolve pela borda" — na
    `identidade` ela é verdadeira, aqui não.
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
