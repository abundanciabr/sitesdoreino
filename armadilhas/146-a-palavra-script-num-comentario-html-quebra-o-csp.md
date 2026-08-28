# A palavra `script` entre `<>` num COMENTÁRIO HTML quebra o CSP — e só em produção

**Sintoma:** a página abre perfeita por `file://` e no `make dev`, e **em
produção não renderiza nada**. O console do navegador mostra algo como:

```
Refused to execute inline script because it violates the following
Content-Security-Policy directive: "script-src 'self' 'sha256-…'".
Either the 'unsafe-inline' keyword, a hash ('sha256-…'), or a nonce is required.
```

O hash que o servidor mandou **existe** — só não corresponde a nenhum bloco real
da página.

**Causa:** quando o CSP é calculado por HASH do script embutido, o servidor
precisa achar as ilhas de script no HTML, e faz isso com uma expressão regular.
A da `admin` é esta (`services/admin/apps/core/painel.py`):

```python
_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)
```

Ela não sabe o que é comentário. Se qualquer lugar do arquivo — inclusive dentro
de `<!-- … -->` — contiver a tag de abertura literal, a regex começa a casar ali
e vai até o **primeiro** fechamento seguinte, que é o fim do primeiro bloco de
verdade. Resultado: um hash é calculado sobre "texto de comentário + código do
primeiro bloco", e o primeiro bloco real **fica sem hash nenhum**. O navegador
recusa executá-lo.

É especialmente traiçoeiro porque **o comentário costuma existir justamente para
explicar o bloco de script logo abaixo** — quanto melhor a documentação, mais
provável o defeito. E porque o CSP só é aplicado pela view do Django: abrir o
mesmo arquivo por `file://` não tem servidor, não tem cabeçalho, e funciona.

**Solução:** nunca escreva a tag literal em prosa. Diga "uma tag de script", ou
"tag de script com `src`". No código que GERA HTML, monte a tag por
concatenação, para o próprio arquivo-fonte não conter a sequência:

```js
var ABRE = "<" + "script>";
var FECHA = "<" + "/script>";
```

**Como conferir sem navegador** — conte as ilhas com a MESMA regex do servidor e
veja se o número bate com o de blocos reais:

```bash
python -c "
import re, io
h = io.open('painel/painel.html', encoding='utf-8').read().encode('utf-8')
rx = re.compile(rb'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.DOTALL|re.IGNORECASE)
for i, m in enumerate(rx.findall(h)):
    print(i+1, len(m), m[:60].decode('utf-8','replace').strip())
"
```

Ilha que começa com texto em português em vez de código é o sinal.

**Custo real:** pego em 27/08/2026 no PR #331, durante a reconstrução do painel,
**antes** de ser mergeado — a suíte inteira estava verde e o `file://` abria
normal. Se tivesse passado, o sintoma seria "o painel abre no meu PC e não abre
no site", que é exatamente a forma de falha que custou quatro telas vermelhas num
dia neste mesmo painel.

**Família:** é a mesma classe de `armadilhas/083` e `/029` — defeito que só
existe atrás do servidor, invisível para toda a suíte local. Regra da casa que se
aplica: *prova de fora*.
