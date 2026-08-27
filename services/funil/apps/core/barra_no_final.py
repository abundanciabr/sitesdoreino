# apps/core/barra_no_final.py
"""`/cadastro/` deixa de ser 404 e passa a levar a `/cadastro` — o espelho do
`APPEND_SLASH` do Django, que só sabe fazer o caminho contrário.

O SINTOMA QUE ISTO FECHA
------------------------
Medido em 27/08/2026, em produção: todo caminho de conteúdo desta célula
responde `Not Found` se a pessoa puser barra no fim.

    /cadastro      200
    /cadastro/     404   <- e ninguém deveria precisar saber disso

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
formulário é descartado em silêncio. Aqui isso é crítico e está escrito na
matriz do `PLANO-I18N` D1, que preservou `POST /leads` e `POST /cadastro`
justamente evitando redirecionamento no meio do caminho. Método diferente cai
fora e recebe o 404 honesto.

**A rota nua tem de existir.** `/healthz`, `/sitemap.xml` e `/static/**` são
rotas de MÁQUINA e servidas só na forma nua; se alguém as pedir com barra, a
regra 2 decide, e nenhuma gêmea nova nasce (`armadilhas/086`).

O IDIOMA, E POR QUE ISTO NÃO BRIGA COM A MATRIZ DO D1
-----------------------------------------------------
Esta célula resolve idioma ANTES do urlconf: `SiteResolutionMiddleware` decapa
`/en|/es` de `request.path_info` e deixa `request.path` completo (para
canonical e logs). Este middleware entra DEPOIS dele na lista, então:

* resolve contra `path_info` — já sem o idioma, que é o que o urlconf entende;
* redireciona para `request.path` sem a barra — **com** o idioma preservado.

Resultado, MEDIDO caso a caso contra a matriz do D1 (o mapa abaixo saiu de
uma varredura real, não de raciocínio — a primeira versão desta docstring
errava duas linhas dele, ver a nota no fim):

    /cadastro/        404 -> 302 /cadastro         (conserto)
    /es/cadastro/     404 -> 302 /es/cadastro      (conserto, idioma preservado)
    /es/              200, intocado                (resolve: regra 1 barra o meio)
    /es               302 -> /es/, intocado        (não é 404: nem chega aqui)
    /                 200, intocado                (a raiz nunca é mexida)
    /nao-existe/      404, intocado                (regra 2)

**O idioma PADRÃO não tem prefixo nenhum** — o D1 revisto (25/08/2026) o pôs na
raiz nua. Então `/<padrão>/qualquer-coisa` é 404 nas duas formas e o middleware
não age: a regra 2 exige que a forma NUA resolva, e ela também não resolve.
Isso é o comportamento desejado, e tem guarda próprio
(`test_o_idioma_padrao_nao_ganha_um_prefixo_inventado`): dar existência a
`/<padrão>/` recriaria a duplicação de endereço que o D1 foi revisto para
eliminar.

    Nota para quem vier depois: até 27/08/2026 este bloco afirmava
    `/en/cadastro/ -> 302 /en/cadastro` e `/pt-br/ -> 404`. As duas linhas
    estavam erradas — `en` é o padrão (mora na raiz nua) e `pt-br` é
    prefixado, de modo que `/pt-br/` responde 200. O erro veio de raciocinar
    sobre a matriz em vez de medi-la; os testes deste middleware agora medem.

A regra 1 (*"não age se a forma COM barra resolve"*) é o que garante que o
prefixo de idioma — cuja forma canônica é COM barra — nunca seja tocado.
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
