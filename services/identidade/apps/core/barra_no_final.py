# apps/core/barra_no_final.py
"""`/entrar/google/` deixa de ser 404 e passa a levar a `/entrar/google` — o
espelho do `APPEND_SLASH` do Django, que só sabe fazer o caminho contrário.

O SINTOMA QUE ISTO FECHA
------------------------
Medido em 27/08/2026, em produção, pelo mantenedor — primeiro na Caixa, e o
conserto entrou lá no PR #284. Nesta célula ele dói mais que nas outras, porque
o que fica inalcançável é a **porta de entrada da plataforma**:

    /entrar/google      302 para o Google
    /entrar/google/     404   <- e a pessoa não consegue nem tentar entrar

Não é caso raro. O navegador completa endereço sozinho, o histórico guarda a
forma com barra, e quem copia um link de uma conversa quase sempre traz a barra
junto. O Django resolve o caminho oposto desde sempre (`APPEND_SLASH`: pediu
`/x`, a rota é `/x/`, ele redireciona) e **não** tem o simétrico.

A REGRA, E POR QUE ELA É ESTREITA DE PROPÓSITO
----------------------------------------------
Redireciona `/x/` para `/x` **somente quando as duas coisas são verdade**:

1. `/x/` não resolve em rota nenhuma (senão estaríamos roubando uma rota que
   existe e funciona), e
2. `/x` resolve.

Fora disso, nada acontece e o 404 segue seu caminho. Essa estreiteza é o que
torna o middleware seguro de ligar numa célula viva: ele não consegue mudar o
destino de nenhuma URL que já funcionava — só dá destino a uma que não tinha.

**302, nunca 301.** O 301 fica cacheado no navegador de forma praticamente
permanente, e uma rota que ganhe a forma com barra amanhã ficaria inalcançável
para quem já visitou.

**Só GET e HEAD.** Um 302 num POST vira GET no navegador e o corpo é descartado
em silêncio. Aqui o caso concreto é `POST /entrar/sair`: se a forma com barra
fosse redirecionada, o pedido de SAIR viraria um GET e a pessoa continuaria
logada achando que saiu — numa célula cuja única razão de existir é a sessão.
`POST /entrar/sair/` segue 404, que é o fracasso barulhento e correto.

O QUE ESTA CÉLULA TEM DE DIFERENTE
-----------------------------------
**Não há `FORCE_SCRIPT_NAME` aqui** (a `identidade` é servida na raiz do host, e
o `config/settings.py` explica por quê). Então `request.path` e
`request.path_info` são iguais, e a distinção que o código faz abaixo é inócua
nesta célula. Ela foi mantida de propósito: é a mesma peça da `sugestoes` e do
`funil`, onde a distinção é o que a faz funcionar (`armadilhas/081`), e uma
cópia que "simplifica" o que não entende é como se planta a divergência entre
células que deveriam ser idênticas.

**A superfície de máquina (`/interno/`) também é alcançada** — `/interno/sessao/`
passa a redirecionar para `/interno/sessao`. Isso não afrouxa nada: o
redirecionamento não carrega credencial nem resposta, e quem chega ao destino
sem o Bearer do par continua levando 401. Há guarda para exatamente isso, porque
"middleware que mexe em 404" é o tipo de peça que precisa provar que não virou
um caminho lateral para dentro.
"""

from django.http import HttpResponseRedirect
from django.urls import Resolver404, resolve

SEGUROS = frozenset({"GET", "HEAD"})


def _resolve(caminho: str) -> bool:
    """Existe rota para este caminho? (sem executar a view)"""
    try:
        resolve(caminho)
    except Resolver404:
        return False
    return True


class BarraNoFinal:
    """Middleware. Ver a docstring do módulo para a regra e o porquê de cada
    restrição."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if resposta.status_code != 404:
            return resposta
        if request.method not in SEGUROS:
            return resposta

        # `path_info` é o caminho SEM o prefixo público (`SCRIPT_NAME`), que é
        # o que o resolver da célula entende. Aqui os dois são iguais (não há
        # prefixo); ver a nota da docstring sobre manter a peça idêntica.
        caminho = request.path_info
        if not caminho.endswith("/") or caminho == "/":
            return resposta

        nu = caminho.rstrip("/")
        if not nu or _resolve(caminho) or not _resolve(nu):
            return resposta

        # `request.path` (COM o prefixo público) é o que vai no Location: o
        # navegador precisa do endereço público, não do interno.
        destino = request.path.rstrip("/")
        if request.META.get("QUERY_STRING"):
            destino = f"{destino}?{request.META['QUERY_STRING']}"
        return HttpResponseRedirect(destino)
