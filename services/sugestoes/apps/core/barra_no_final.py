# apps/core/barra_no_final.py
"""`/avisos/` deixa de ser 404 e passa a levar a `/avisos` — o espelho do
`APPEND_SLASH` do Django, que só sabe fazer o caminho contrário.

O SINTOMA QUE ISTO FECHA
------------------------
Medido em 27/08/2026, em produção, pelo mantenedor: toda tela interna desta
célula responde `Not Found` se a pessoa puser barra no fim.

    /forms/sugestoes/avisos      200
    /forms/sugestoes/avisos/     404   <- e ninguém deveria precisar saber disso

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
para quem já visitou. É a mesma razão pela qual a matriz de idiomas do `funil`
escolheu 302 (`PLANO-I18N` D1).

**Só GET e HEAD.** Um 302 num POST vira GET no navegador e o corpo do
formulário é descartado em silêncio — o pior modo de falha possível numa célula
cujas rotas de escrita (`votar`, `comentar`, `marcar_aviso_lido`) são todas
POST. Método diferente cai fora e recebe o 404 honesto.

**A rota nua tem de existir.** `path("healthz")` e as rotas de máquina não são
afetadas porque ninguém as pede com barra; se pedirem, a regra 2 decide.
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
        # o que o resolver desta célula entende — sob `/forms/sugestoes` o
        # `request.path` traria o prefixo e nada resolveria (armadilhas/081).
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
