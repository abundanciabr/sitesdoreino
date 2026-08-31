---
schema_version: 2
armadilha: 239
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: "nenhum portao consegue saber que um desenho DEVERIA girar em 3D; so quem desenha sabe. Os testes do mascote guardam o caso desta casa (preserve-3d presente na folha servida), nao a classe. Degrau 1: leitura."
sinal: null
---

# `transform-style: preserve-3d` não vale dentro de um `<svg>` — o cubo achata em vez de girar

**Sintoma:** você monta um cubo de seis faces para girar de verdade, escreve o
`rotateY(360deg)`, e o que aparece na tela é um retângulo que **estica e encolhe**
a cada volta, como uma folha de papel virando. As faces laterais nunca aparecem;
as de trás vazam por cima das da frente. Nenhum erro no console.

**Causa:** `transform-style: preserve-3d` — a propriedade que faz os filhos de um
elemento viverem no MESMO espaço 3D do pai, em vez de serem achatados na
superfície dele — **é do modelo de caixas do CSS, e não do modelo de renderização
do SVG.** Dentro de um `<svg>`, os filhos são achatados de volta ao plano do
desenho e cada `translateZ` vira zero. O `perspective` do pai também não os
alcança. Isso não é bug de navegador: é a especificação, e vale em todos eles.

O que FUNCIONA dentro de SVG é a transformação 2D: mover, girar no plano, escalar,
inclinar. É por isso que dá para fingir 3D em SVG desenhando as faces à mão (um
tijolo visto de três quartos é só três polígonos), mas não dá para GIRAR esse
tijolo — a cada quadro as faces visíveis mudariam, e nenhuma transformação 2D
sabe disso.

**Solução:** rotação 3D de verdade se faz com `<div>`. Seis divs de mesmo tamanho,
posicionadas uma sobre a outra, cada uma empurrada para a sua face
(`translateZ(metade)` depois de `rotateX/Y`), dentro de um pai com
`transform-style: preserve-3d`, dentro de um avô com `perspective`. Sem o
`perspective` do avô o cubo gira "chapado": as faces mudam de largura, mas nada
se aproxima do olho, e o efeito lê como origami.

**A regra de bolso:** desenho 3D estático → SVG. Desenho 3D que GIRA → caixas do
CSS. E os dois convivem: o resto da página continua em SVG.

**A pegadinha secundária, que custa a segunda rodada:** com `prefers-reduced-motion`
você desliga a animação — e o cubo para em `rotateY(0)`, que é a face da frente
sozinha, ou seja, um quadrado chapado. Desligar movimento não pode significar
jogar fora a informação. Pare-o numa pose de três quartos:

```css
@media (prefers-reduced-motion: reduce) {
  .cubo { animation: none; transform: rotateX(-18deg) rotateY(-32deg); }
}
```

**Origem:** o mascote das caixas de escrever do fórum e da Caixa de Sugestões
(31/08/2026). O mantenedor escolheu, entre quatro desenhos animados, o tijolo que
gira — e foi essa escolha que trocou o `<svg>` por `<div>`. A próxima sessão que
achar estranho o único ícone da casa que não é SVG deve ler este arquivo antes de
"consertar" a inconsistência.
