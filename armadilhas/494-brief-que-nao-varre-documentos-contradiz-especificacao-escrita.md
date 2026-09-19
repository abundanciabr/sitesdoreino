---
schema_version: 2
armadilha: 494
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão confere se um brief de sessão contradiz um documento específico dentro de `documentos/`; a varredura por assunto antes de especificar é julgamento do maestro, não algo que um teste de CI consiga generalizar sem falso positivo.
sinal:
  - "ancora_de_preco"
  - "valor riscado"
gatilho:
  - documentos/
licao: "Antes de especificar superfície de produto (página, funil, oferta), varra `documentos/` por assunto: a especificação escrita do mantenedor vence brief de sessão. Cite a fonte (arquivo e linha) em vez de reescrever de memória; se o brief e o documento divergem, o documento manda."
---

# 494: Brief que não varre `documentos/` pode contradizer especificação escrita do mantenedor

## Sintoma

Um brief de sessão (maestro, 19/09/2026) especificou um slot
`oferta.ancora_de_preco` para a página de vendas. O mantenedor já havia
especificado essa mesma página em `documentos/ferramentas-do-projeto-meshcraft.md`,
ferramenta 73 (linha 961): "o preço uma vez, sem ancoragem". A ferramenta 74
(linha 971) proíbe por escrito, entre outros padrões, "valor riscado". O slot
inventado no brief é exatamente o padrão proibido.

## Causa

O brief nasceu de memória da sessão, sem varrer `documentos/` pelo assunto
("página de vendas", "oferta", "preço"). `documentos/` guarda decisão de
produto do mantenedor, registrada fora do fluxo normal de PR, e não aparece
em `git log` nem em `grep` de código; só aparece para quem procura por
assunto antes de escrever a especificação.

## Lição

Antes de escrever brief ou especificar superfície de produto, varra
`documentos/` por assunto. Quando a especificação do mantenedor já existir,
cite-a (arquivo e linha) em vez de reescrevê-la de memória; se a sua
especificação diverge da dele, a dele vence.

## Evidência

Contrato (#1772) e implementação em `catalogo` (#1773) chegaram a incorporar
o slot proibido. Um terceiro despacho, que varreu `documentos/` por conta
própria, encontrou a divergência e corrigiu os dois PRs antes de qualquer
pouso: nada do slot proibido chegou à main. `documentos/ferramentas-do-projeto-meshcraft.md`
linhas 961 e 971 conferidas nesta sessão.
