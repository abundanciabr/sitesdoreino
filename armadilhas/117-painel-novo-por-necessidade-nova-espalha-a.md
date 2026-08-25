# Painel novo a cada necessidade nova espalha a verdade — e o "precisa de você" acaba em três painéis diferentes, onde um pedido do mantenedor pode se perder

**Sintoma:** o mantenedor abre um painel, não acha o que procura, abre outro,
encontra uma versão diferente do mesmo fato — e conclui, com as palavras dele
(25/08/2026): *"eu acabei criando vários painéis e me perdendo do mesmo jeito"*.
No inventário daquele dia havia **6 painéis** em `arquivos/`, e a lista
**"precisa de você"** existia simultaneamente em **três** deles
(`painel-fundacao` na caixa do topo, `painel-roadmap` como "3 escolhas
esperando você", `painel-retomada` na seção 6). O `painel-10x` já havia
envelhecido a ponto de "mentir" — está registrado assim na própria memória do
projeto.

**Causa:** cada sessão que precisou de uma superfície nova **criou um painel
novo**, e não havia regra dizendo onde cada tipo de fato mora. Sem essa regra,
todo painel vira dono de uma cópia da verdade, e cópia envelhece sozinha. O
agravante específico: quando o que espera uma **decisão humana** está em N
lugares, basta um deles não ser atualizado para um pedido ao mantenedor sumir
de vista — e o painel que ele abriu naquele dia é justamente o que decide se
ele fica sabendo.

**Solução:**

1. **Painel novo é proibido por padrão.** Precisou de superfície nova? Crie uma
   **seção** dentro do painel existente que atende àquele público, não um
   arquivo novo. Painéis existem por *público* (o dono · as sessões de robô ·
   a história), nunca por *assunto* — assunto vira seção.
2. **O que espera o humano mora num lugar só.** Qualquer outro painel que
   precise citar pendência dele **aponta** para essa caixa, nunca repete a
   lista. A fonte é a tabela `§1 — PRECISA DE VOCÊ` do
   `ARMADILHAS-OPERACAO.md`; a caixa do painel é a vitrine dela.
3. **Painel de era encerrada não fica solto na pasta.** Congele-o como
   fotografia datada (banner "este painel é histórico, de DD/MM") e aponte para
   o painel vivo — foi o que já se fez, na mão, com `painel-prompts-fase-d`. Um
   painel antigo que ainda parece atual é a forma mais barata de um agente ou o
   mantenedor tomarem decisão com dado velho.

**Origem:** sessão de 25/08/2026, ao estudar o padrão-ouro de painéis a pedido
do mantenedor. O fenômeno tem nome na indústria — *dashboard sprawl* — e a cura
padrão é a mesma de qualquer duplicação de estado: **uma fonte de verdade,
várias vistas, um endereço de entrada**. Metade dela o projeto já praticava sem
o nome (`painel-dados.js` separando dados do renderizador, card C2 do
PLANO-10X). O cardápio completo e a proposta de reforma ficaram em
`arquivos/cardapio-de-paineis.html` — que está fora do Git, então esta entrada
existe para que a lição sobreviva ao arquivo.
