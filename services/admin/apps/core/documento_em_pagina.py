"""O documento que é uma PÁGINA VISUAL inteira, e não só texto (TAR-596).

Pedido do mantenedor em 21/09/2026: *"o documento pode ser uma página visual
inteira, não só texto"*. Lei: `docs/decisoes/DECISAO-a-area-de-documentos.md`.

## A saída não foi ampliar o Markdown

`documentos.para_html` aceita oito marcas e **escapa o texto inteiro antes de
aplicar qualquer uma delas**. Isso é certo, continua, e é o que torna o `|safe`
dos dois templates seguro (§6 da lei). Alargá-lo para caber HTML, CSS, SVG e
Canvas seria trocar uma regra mecânica ("marcação não passa") por uma lista de
tags permitidas — e uma lista de tags permitidas é uma coisa que se erra.

O que este arquivo faz é **parar de desenhar documento rico DENTRO da página do
site**. Um documento de formato `pagina` é servido CRU por uma rota própria, e
a página do site o mostra dentro de um `<iframe>` cujo `sandbox` **não tem**
`allow-same-origin`.

## Por que a ausência de `allow-same-origin` é a peça inteira

Um `<iframe>` de mesma origem sem `sandbox` não isola nada: o que roda dentro
dele é código do meshcraft rodando na origem do meshcraft, com acesso ao cookie
de sessão, ao `localStorage` e ao DOM da página de fora. Acrescentar
`allow-same-origin` a um sandbox de mesma origem faz exatamente isso: **desliga
o sandbox**.

Sem ele, o navegador dá ao documento uma **origem opaca**. O script roda, o
Canvas desenha, o gráfico plota e a folha de estilo pinta, e nada disso alcança
um cookie, um armazenamento ou um nó do DOM desta casa. É o que permite dar a
folha em branco sem dar a chave.

Guardas: `tests/test_pagina_visual_do_documento.py`, que mede o atributo tanto
na página renderizada quanto na fonte de TODO template desta área, e reprova
também o iframe que nascesse sem `sandbox` nenhum.

## A altura, e por que a procedência não se confere pelo `origin`

Um iframe não cresce com o conteúdo. A resposta da moldura leva, colado ao fim
do documento, o `SCRIPT_DA_ALTURA` — que mede e manda o número por
`postMessage` —, e a página de fora escuta e ajusta.

Do lado de fora, a mensagem é aceita comparando `event.source` com o
`contentWindow` do elemento do iframe, **nunca pelo `event.origin`**: numa
origem opaca o `origin` chega como a string `"null"`, e qualquer outro conteúdo
sandboxed da mesma página mandaria `"null"` igualzinho. O elemento é a única
procedência que distingue.

Sem JavaScript no navegador de quem lê, nada disso acontece e o iframe fica na
altura mínima que o CSS da página já lhe dá: menos página visível, nunca tela
em branco.
"""

from __future__ import annotations

import base64
import hashlib
import re

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from . import documentos
from .models import Documento
from .porta import PortaAdministrativa

#: O script que a moldura cola no fim do documento servido. Roda DENTRO do
#: sandbox, onde `allow-scripts` o permite.
#:
#: O alvo do `postMessage` é `"*"`, e isso é deliberado: a carga é um número de
#: pixels, não há segredo que possa vazar para quem quer que esteja escutando,
#: e a conferência que importa é a do outro lado, onde a mensagem é aceita pelo
#: ELEMENTO de onde veio. Exigir uma origem aqui só criaria um jeito de a
#: altura parar de funcionar em silêncio.
SCRIPT_DA_ALTURA = """
<script>
(function () {
  var ultima = 0;
  function medir() {
    var raiz = document.documentElement, corpo = document.body;
    var altura = Math.max(
      raiz ? raiz.scrollHeight : 0,
      corpo ? corpo.scrollHeight : 0
    );
    if (altura && altura !== ultima) {
      ultima = altura;
      parent.postMessage(
        { meshcraft: "altura-do-documento", altura: altura }, "*"
      );
    }
  }
  window.addEventListener("load", medir);
  window.addEventListener("resize", medir);
  if (window.ResizeObserver && document.documentElement) {
    new ResizeObserver(medir).observe(document.documentElement);
  }
  medir();
})();
</script>
"""

#: O CSP da resposta da moldura, e **só ele**: nem `default-src`, nem
#: `script-src`, nem `style-src`.
#:
#: Parece frouxo e não é. O que contém esta resposta é o `sandbox` do elemento
#: que a enquadra, do lado de fora: origem opaca, sem cookie, sem
#: armazenamento, sem DOM da casa. Uma política restritiva aqui não
#: acrescentaria isolamento nenhum — só quebraria a folha em branco que o
#: mantenedor pediu, e o documento dele deixaria de desenhar sem dizer por quê.
#:
#: `frame-ancestors 'self'` é o que sobra, e é o que importa: um site de fora
#: não consegue emoldurar esta resposta e usá-la como se fosse dele.
#:
#: **O `X-Frame-Options` correspondente vem do Traefik**, e as duas concordam:
#: a cadeia `seguranca-admin` (`infra/traefik/dynamic/plataforma.yml`) manda
#: `SAMEORIGIN`, e não `DENY` — `DENY` proibiria o enquadramento inclusive de
#: mesma origem, e o iframe não abriria em produção enquanto abre em `make dev`,
#: onde não há Traefik. É o mesmo par que `porta.py::_com_seguranca` já mantém,
#: e o mesmo erro que `armadilhas/109` registra.
CSP_DA_MOLDURA = "frame-ancestors 'self'"

#: O `<script>` embutido da página de FORA, para o hash do CSP. Mesma regex de
#: `painel.py`, `robos.py` e `livro.py`, letra por letra: divergir aqui seria a
#: Lei 3 (duplicar e divergir) escondida numa expressão regular.
_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def csp_da_pagina(resposta) -> str:
    """O CSP da página de FORA: o da porta, mais o hash do escutador.

    A porta manda `script-src 'self'` em toda resposta desta célula, e sob essa
    regra o escutador da altura não roda (`armadilhas/199`). O jeito da casa é
    o hash, nunca `'unsafe-inline'`: o hash libera exatamente estes bytes, e
    `'unsafe-inline'` liberaria qualquer script injetado.

    Os hashes de estilo vêm de `PortaAdministrativa.hashes_de_estilo`, e não de
    uma segunda cópia da regra aqui: a folha desta área mora embutida no
    `<head>`, e uma conta própria divergiria da da porta no primeiro dia em que
    uma das duas mudasse, deixando a página sem estilo nenhum.
    """
    hashes = " ".join(
        "'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(resposta.content)
    )
    return (
        "default-src 'self'; "
        f"script-src 'self' {hashes}; "
        f"style-src 'self'{PortaAdministrativa.hashes_de_estilo(resposta)}; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )


def _moldura(documento) -> HttpResponse:
    """O corpo do documento, verbatim, mais o script da altura.

    **Verbatim é o ponto inteiro do formato.** Nada é escapado, nada é
    reordenado, nada é acrescentado no meio: o que o autor escreveu é o que o
    navegador recebe. O único acréscimo vem depois do documento inteiro, e é o
    script que mede a altura.
    """
    resposta = HttpResponse(
        documento.corpo + SCRIPT_DA_ALTURA, content_type="text/html; charset=utf-8"
    )
    # Atribuição, e não `setdefault`: esta é a resposta em que a política da
    # porta não serve, e deixá-la ganhar apagaria a folha em branco.
    resposta["Content-Security-Policy"] = CSP_DA_MOLDURA
    # O `X-Content-Type-Options: nosniff` desta resposta NÃO é escrito aqui: ele
    # vem do `SecurityMiddleware` do Django, que o manda em toda resposta desta
    # célula (`SECURE_CONTENT_TYPE_NOSNIFF` é `True` por omissão, e o
    # `settings.py` não o desliga). Escrevê-lo de novo criaria uma segunda fonte
    # para o mesmo fato, e a que sobraria quando alguém desligasse a de cima
    # seria esta — dando a impressão de que a célula inteira ainda está
    # protegida quando só esta rota estaria. O cabeçalho é medido na resposta
    # servida por `tests/test_pagina_visual_do_documento.py`, onde uma mudança
    # naquele ajuste reprova.
    return resposta


@require_GET
def doc_publico_moldura(request, nome):
    """O corpo cru de um documento público de formato `pagina`.

    **404 para todo o resto**, e as duas condições são as mesmas da página que
    a enquadra: o documento tem de estar no ar E ser de formato `pagina`. Um
    404 para o documento de texto não é higiene — é o que impede esta rota de
    virar um segundo endereço servindo, sem passar pelo renderizador que
    escapa, o mesmo conteúdo que a outra serve escapado.

    E 404 em vez de 403 para o privado, pelo §5 da lei: um 403 confirmaria que
    o documento existe.
    """
    documento = documentos.ler(nome)
    if (
        documento is None
        or not documento.no_ar
        or documento.formato != Documento.Formato.PAGINA
    ):
        raise Http404("documento não encontrado")
    return _moldura(documento)


@require_GET
def documento_admin_moldura(request, nome):
    """O mesmo corpo cru, para quem passou pela porta.

    Serve o privado e o arquivado, como a página administrativa já serve: sem
    isto, o mantenedor não conseguiria VER a página que acabou de escrever
    antes de decidir publicá-la, que é justamente quando ele precisa vê-la.
    """
    documento = documentos.ler(nome)
    if documento is None or documento.formato != Documento.Formato.PAGINA:
        raise Http404("documento não encontrado")
    return _moldura(documento)
