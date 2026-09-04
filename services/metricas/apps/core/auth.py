# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de `TOKENS_ACEITOS_*`, um por par consumidor.

    Cópia do PADRÃO de `sugestoes`/`alunos` (Lei 3: copia-se o padrão entre
    células, nunca se importa código de uma na outra). Nome da classe em
    minúsculas de propósito: o freeze de contrato exige que a chave de
    `components.securitySchemes` seja `bearerAuth`, e o django-ninja usa o nome
    da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa, hoje só a `admin`. Esta porta não tem sessão
    de pessoa e não resolve visitante nenhum: quem fala com ela é máquina,
    sempre ([INV-P12]). A pergunta "de quem é este fato?" se responde pelo
    CORPO do evento, que veio pelo contrato, nunca por quem fez a chamada.

    UM CONJUNTO SÓ, E ISSO É DECISÃO: esta porta apenas LÊ. A `mensageria`
    precisou de dois graus (`TOKENS_SOMENTE_LEITURA_*` e `TOKENS_PUBLICACAO_*`)
    porque uma das operações dela publica texto que vai para alunos de verdade.
    Aqui não existe operação que escreva, então um segundo grau seria uma
    distinção sem diferença, e distinção sem diferença é o que faz alguém pôr o
    token na variável errada.

    O conjunto nasce VAZIO quando o env falta, e conjunto vazio recusa todo
    mundo com 401. Fail-closed por construção, e sem derrubar o boot: a célula
    sobe, o `/healthz` responde, o consumidor de eventos segue guardando fatos,
    e só a porta fica fechada até o token existir no env.
    """

    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
