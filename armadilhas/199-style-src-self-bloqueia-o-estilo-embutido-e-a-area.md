---
schema_version: 2
armadilha: 199
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/admin/tests/test_estilo_chega_ao_navegador.py
sinal:
  - `Applying inline style violates`
  - `style-src 'self'`
---

# `style-src 'self'` bloqueia o `<style>` embutido — a área inteira fica SEM ESTILO, e nada fica vermelho

**Sintoma.** As telas de uma célula chegam ao navegador **sem estilo nenhum** —
texto preto em fundo branco, tudo empilhado. Em produção e só lá. Nenhum teste
reprova, nenhum log acusa, o `curl` traz o HTML **completo**, com o `<style>`
inteiro dentro do `<head>`. Só o console do navegador diz o que está
acontecendo:

```
Applying inline style violates the following Content Security Policy directive
'style-src 'self''. Either the 'unsafe-inline' keyword, a hash
('sha256-g1URTZmJNLktPGlRhWn6uQA0uhs8YibnAsi1DpcL2EQ='), or a nonce
('nonce-...') is required to enable inline execution. The action has been
blocked.
```

**Causa.** Duas decisões certas que se anulam:

1. O estilo mora **embutido** no `<head>` porque célula sob `SCRIPT_NAME` que
   serve estático por tag monta endereço da célula ERRADA (`armadilhas/083` e
   `/102`) — a folha embutida é a saída sem rota e sem armadilha.
2. A política de segurança manda `style-src 'self'`, que significa *"só folha
   vinda da minha origem por `<link>`"* — e **estilo embutido não é isso**.

A combinação não quebra nada mecanicamente: a página responde 200, o HTML está
certo, o servidor está saudável. O navegador simplesmente **joga a folha fora**
ao renderizar.

Medido em produção em 30/08/2026 na célula `admin`: toda tela da área — visão
geral, escola, alunos, Caixa, documentos, o mapa do site — estava assim. As duas
exceções (`/admin/painel/` e a aba "Os robôs") escapavam por acidente feliz:
elas mandam CSP própria, com `'unsafe-inline'` no `style-src`, porque precisavam
disso para outra coisa.

**Por que nada pegou.** O test client do Django **não aplica CSP** — ele devolve
o HTML e o header, e nenhum dos dois "sabe" que um proíbe o outro. O `curl`
baixa e não renderiza. Os dois ficam verdes para sempre. É o padrão 1 da
`RETROSPECTIVA-FASE-D` na sua forma mais silenciosa: o instrumento não mede a
propriedade que interessa, e o silêncio dele parece aprovação.

**Solução — hash, nunca `'unsafe-inline'`.** Some à política o `sha256` do
conteúdo de cada `<style>`, calculado **da resposta servida**, para não haver
hash a lembrar de atualizar quando o CSS mudar:

```python
_ESTILO = re.compile(rb"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
hashes = {"'sha256-" + base64.b64encode(hashlib.sha256(m).digest()).decode() + "'"
          for m in _ESTILO.findall(resposta.content)}
```

`'unsafe-inline'` "consertaria" em uma palavra e liberaria **qualquer** estilo
injetado — inclusive um vindo de conteúdo de terceiro. O hash libera exatamente
aqueles bytes. É o mesmo desenho que `services/admin/apps/core/painel.py` já
usava para o script embutido.

**Como conferir de fora, sem depender de extensão nem de plano pago** — é este
comando que provou o defeito e provou o conserto:

```bash
chrome --headless=new --disable-gpu --enable-logging=stderr \
  --virtual-time-budget=5000 --user-data-dir=/tmp/csp --dump-dom \
  "https://SEU-SITE/pagina" 2>&1 | grep -i "content security policy"
```

Saída vazia = o navegador não recusou nada.

**A metade que o hash NÃO cobre:** atributo `style="..."` solto na marcação
continua bloqueado — para ele o padrão exige `'unsafe-hashes'` mais o hash de
cada valor, o que não escala. O conserto certo é tirar os atributos e pôr
classes na folha. Enquanto isso não acontece, a folha volta e só os ajustes
pontuais (uma margem aqui, uma cor ali) se perdem — é a diferença entre uma
página feia e uma página sem desenho nenhum.
