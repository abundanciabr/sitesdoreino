---
schema_version: 2
armadilha: 296
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: services/funil/tests/test_ver_como.py
sinal:
  - `uso: .% t "chave.literal"`
  - `TemplateSyntaxError` numa página cujo template você só COMENTOU
---

# Citar uma tag do Django dentro de comentário HTML derruba a página inteira

**Sintoma:** você escreve um comentário `<!-- … -->` explicando o template, cita
a tag que está documentando, e a página passa a estourar 500 com uma mensagem
que fala de uma linha que "não existe":

```
django.template.exceptions.TemplateSyntaxError: uso: {% t "chave.literal" [var=expr …] %}
```

Você lê o template inteiro procurando a tag malformada e não acha nenhuma —
porque a que está quebrada é a do **comentário**.

**Causa:** `<!-- -->` é comentário para o NAVEGADOR, e o Django nunca o vê como
tal. O motor de template varre o arquivo inteiro em busca de `{% … %}` antes de
qualquer HTML existir, então uma tag citada dentro de um comentário é uma tag
**de verdade** — e uma citação como `{% t %}`, escrita para mostrar o nome da
tag, é literalmente a chamada sem argumento que o parser recusa.

Nesta casa o estrago é maior que o normal, e por um bom motivo: os templates
daqui carregam comentários LONGOS de propósito (a lei manda escrever o porquê
junto do código). Quanto melhor o comentário, maior a chance de ele citar a
coisa que documenta.

**Solução — escreva o NOME da tag, sem as chaves:**

```
ERRADO:  <!-- as opções estão à mão porque {% t %} recusa chave dinâmica -->
certo:   <!-- as opções estão à mão porque a tag de tradução recusa chave dinâmica -->
```

Se a citação precisar mesmo das chaves (um exemplo de uso), há duas saídas
legítimas: `{% templatetag openblock %}` para produzir o `{%` sem que ele seja
interpretado, ou pôr o exemplo num `{% comment %}`…`{% endcomment %}`, que é o
comentário DO DJANGO e realmente engole o que está dentro. Note a ironia útil:
`{% comment %}` protege, `<!-- -->` não — os dois parecem a mesma coisa e são
opostos exatamente nisto.

**Como reconhecer em dois segundos:** a mensagem cita a forma de USO da tag (o
texto de ajuda dela), e não um erro sobre um valor. Texto de ajuda aparecendo
em produção quase sempre significa "alguém chamou isto sem argumento" — e num
template que você só documentou, o suspeito é o comentário.

**Contexto:** caiu em 02/09/2026 no PR da prévia da equipe ("ver como"), num
comentário que explicava por que as quatro opções da tela estão escritas à mão
em vez de num laço. O comentário estava certo; a citação é que era executável.
