# apps/core/barra_no_final.py
"""`/quiz/<slug>/resultado/` deixa de ser 404 e passa a levar a
`/quiz/<slug>/resultado` — o espelho do `APPEND_SLASH` do Django, que só sabe
fazer o caminho contrário.

O SINTOMA QUE ISTO FECHA
------------------------
Medido em 27/08/2026, em produção, pelo mantenedor — primeiro na Caixa, e o
conserto entrou lá no PR #284. O navegador completa endereço sozinho, o
histórico guarda a forma com barra, e quem copia um link de uma conversa quase
sempre traz a barra junto.

A REGRA, E POR QUE ELA É ESTREITA DE PROPÓSITO
----------------------------------------------
Redireciona `/x/` para `/x` **somente quando as duas coisas são verdade**:

1. `/x/` não resolve em rota nenhuma (senão estaríamos roubando uma rota que
   existe e funciona), e
2. `/x` resolve.

Fora disso, nada acontece e o 404 segue seu caminho.

**NESTA CÉLULA A REGRA 1 É A QUE SUSTENTA TUDO**, e é o que a torna diferente
das outras três. O urlconf do quiz mistura as duas convenções, de propósito:

    path("quiz/<slug>/",          formulario)   <- canônica COM barra
    path("quiz/<slug>/resultado", resultado)    <- canônica SEM barra

Ou seja, `/quiz/crivo/` **é** o endereço certo do quiz, e o Django já
redireciona `/quiz/crivo` para lá sozinho (`APPEND_SLASH`, com 301). Se este
middleware agisse sobre a forma com barra, ele desfaria o redirecionamento do
Django e os dois entrariam em **laço infinito** — `/quiz/crivo/` → `/quiz/crivo`
→ `/quiz/crivo/` → … A regra 1 impede isso por construção (a forma com barra
resolve, então ele nem começa), e há guarda medindo exatamente esse laço.

**302, nunca 301.** O 301 fica cacheado no navegador de forma praticamente
permanente, e uma rota que ganhe a forma com barra amanhã ficaria inalcançável
para quem já visitou.

**Só GET e HEAD.** Um 302 num POST vira GET no navegador e o corpo é descartado
em silêncio. Aqui o POST é a RESPOSTA do quiz (`POST /quiz/<slug>/`, com as
opções marcadas, o e-mail e o nome): redirecionado, o lead se perderia sem erro,
sem log e sem linha no banco.

A QUERY É A IDENTIDADE DO RESULTADO
------------------------------------
A página de resultado é `/quiz/<slug>/resultado?lead=<uuid>` — o `lead` não é
enfeite de rastreamento, é o que diz QUAL submissão mostrar (a view devolve 404
sem ele). Perder a query no redirecionamento transformaria o conserto num 404
diferente, o que é pior que não consertar: a pessoa clicaria no link do próprio
resultado e veria "não encontrado". Por isso a query viaja junto, com guarda.
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
        # o que o resolver desta célula entende — sob `/quiz` o `request.path`
        # traria o prefixo e nada resolveria (armadilhas/081).
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
