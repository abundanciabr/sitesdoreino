---
schema_version: 2
armadilha: 237
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: "nenhum portao consegue saber que um icone DEVERIA ter partes animadas; so quem desenha sabe. Os testes que nasceram junto guardam o caso desta casa (o mascote), nao a classe. Degrau 1: leitura."
sinal: null
---

# Ícone dentro de `<use>` não anima por partes — o CSS de fora não alcança o shadow DOM

**Sintoma:** você põe o ícone no estojo de `<symbol>` da moldura, usa
`<svg><use href="#i-mascote"/></svg>` como todos os outros ícones da página, e
escreve o CSS da animação. O ícone aparece **perfeito e parado**. Nenhum erro no
console, nenhum aviso, nenhum teste vermelho: o `<svg>` está lá, o `@keyframes`
está na folha, e as duas coisas simplesmente não se encontram.

**Causa:** o que o `<use>` instancia vira **shadow DOM**. Um seletor de fora
alcança o elemento `<use>` (e, por herança, propriedades como `color` e
`fill: currentColor` — que é justamente por isso que o estojo de ícones desta
casa funciona), mas **não alcança nenhum elemento lá dentro**. `.mascote-olho`,
`.mascote-topo`, `.mascote-corpo` não existem para o CSS da página: existem só
dentro da cópia. Animar o ícone INTEIRO (girar, pulsar) continua funcionando,
porque isso se aplica ao `<use>`; animar **uma peça** dele, não.

É a mesma pegadinha do `.gizmo-gira` da moldura da Caixa ter dado certo: aquele
SVG está **inline** no `base_caixa.html`, não dentro de um `<use>`.

**Solução:** ícone com partes animadas vai **inline** no template, com uma
classe por peça. Se ele aparece em mais de uma tela da mesma célula, o jeito de
não duplicar é um `{% include %}` (um `_mascote.html`), não o `<symbol>`.

**A regra de bolso:** `<symbol>` + `<use>` é para desenho que muda de COR e de
TAMANHO. Desenho que muda por dentro vai inline.

**Como perceber em 10 segundos**, antes de reescrever a animação achando que o
`@keyframes` está errado: abra o inspetor e clique no ícone. Se o que aparece for
`#shadow-root` com o desenho lá dentro, o CSS de fora nunca vai entrar — o
problema não é a animação.

**Origem:** o mascote 3D das caixas de escrever do fórum e da Caixa de Sugestões
(pedido do mantenedor em 30/08/2026). A primeira versão dele era um SVG desenhado
à mão que precisava piscar só os olhos e acender só a face de cima — e foi ao
tentar guardá-lo no estojo de `<symbol>` da moldura, ao lado dos ícones de
categoria, que isto apareceu. O desenho que ficou no ar acabou sendo outro (um
cubo que gira, feito de `<div>`, por causa da `armadilhas/239`), mas a lição vale
para o próximo ícone com partes vivas: `<symbol>` + `<use>` é para desenho que
muda de COR e de TAMANHO.
