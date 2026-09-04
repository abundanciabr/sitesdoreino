---
schema_version: 2
armadilha: 321
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o despacho da tarefa é lido UMA vez, quando o robô a pega; nada relê por ele, e `git merge origin/main` traz o arquivo novo sem chamar atenção para ele. O que existe é a ordem de conferir o despacho contra o `origin/main` antes de abrir o PR, e a conferência do `toca` que já compara a tarefa com o diff
sinal:
  - "o despacho mudou depois que eu peguei a tarefa"
  - "duas sessoes na mesma celula"
  - "EMENDA DE"
  - "a emenda chegou depois"
---

# Emenda à lei não alcança o robô que já está construindo, e o código nasce fiel à versão revogada

**Sintoma.** Duas sessões trabalham na mesma célula no mesmo dia. A primeira
pega uma tarefa no balcão e começa a escrever código. A segunda conversa com o
mantenedor, ele muda uma regra, e ela emenda a lei, o plano e o **despacho da
tarefa que a primeira já está executando**. A emenda entra na `main` a tempo.
Mesmo assim, o PR da primeira chega completo, verde, bem testado, e **fiel à
regra revogada** — porque o despacho foi lido uma vez, no minuto em que ela
pegou a tarefa.

Caso real de 04/09/2026, na célula `encomendas`. A sessão A pegou a TAR-120 (as
tabelas) às 12:47 UTC. A sessão B perguntou ao mantenedor, ele liberou a
negociação, e a emenda entrou na `main` às 12:53 UTC, com um parágrafo escrito
no despacho da própria TAR-120 mandando a máquina de estado nascer já com os
estados novos. A sessão A mergeou a `main` mais de uma vez depois disso (os
commits de merge estão no ramo dela) e ainda assim entregou a máquina com os 15
estados da lei original. O PR dela tinha 76 testes verdes e 29 guardas provados
por mutação: **a qualidade não protege contra estar construindo a coisa
anterior.**

**Causa.** O despacho é um texto que o robô lê **uma vez**, e nada o relê por
ele. `git merge origin/main` traz o arquivo da tarefa atualizado junto com
outros trezentos, sem destacá-lo — e um robô no meio de uma migração não tem
motivo para reabrir o próprio enunciado. A emenda também não é um conflito de
texto: os dois lados mexeram em arquivos diferentes, então o Git resolve tudo
sozinho, em silêncio.

É a família do padrão 7 da `RETROSPECTIVA-FASE-D.md` (sessões paralelas), com
uma diferença que vale nomear: ali o perigo era **duas sessões escrevendo o
mesmo arquivo**; aqui é **uma sessão mudando a especificação da outra**, que o
Git não enxerga como colisão nenhuma.

**Solução, e ela é barata dos dois lados.**

1. **Quem constrói: releia o despacho do `origin/main` antes de abrir o PR.**
   Uma linha, e ela vale para toda tarefa que dure mais de meia hora numa casa
   com sessões paralelas:

   ```bash
   git show origin/main:fila/tarefas/<NNN>-*.json | python -m json.tool | grep -A5 despacho
   ```

   Se o texto mudou desde que você pegou a tarefa, **pare e leia a diferença
   antes de pedir pouso**.

2. **Quem emenda: crie a tarefa de correção no MESMO PR da emenda**, em vez de
   confiar que o despacho alcança quem já está a caminho. Ela nasce dependendo
   da tarefa em voo, custa um arquivo, e é a única forma que não depende de
   ninguém reler nada. Em 04/09 essa tarefa foi criada só depois, quando o
   estrago já estava na `main` — e o conserto custou uma migração inteira em vez
   de um parágrafo.

3. **E, se o estrago já aconteceu, conserte por migração e não por reescrita.**
   O trabalho da outra sessão está certo para a lei que ela leu, e refazê-lo
   jogaria fora testes e guardas bons. No caso real, a correção foi uma
   `0002_*` acrescentando quatro estados e movendo o pagamento de lugar, com o
   `reverse_sql` devolvendo a função à versão da `0001` byte a byte.

**O que torna este caso barato, e nem sempre será:** a célula ainda não estava
no ar e o banco estava vazio, então a correção foi uma migração num banco sem
uma linha. Descoberto depois do lançamento, seria migração de dados, telas
refeitas e um estado de encomenda que já existia em produção com o significado
antigo. **A pergunta que decide o custo é sempre a mesma: isto já foi para
produção?**

**Parentes.** `armadilhas/313` (o mantenedor pede o que a própria lei dele
proíbe) é a origem desta: foi a reabertura descrita lá que gerou a emenda daqui.
`armadilhas/148` (ler do `origin/main`) é a disciplina que quase resolveu o
caso: a sessão A leu do `origin/main`, mas leu **no começo**, e o problema é
que a especificação mudou no meio.
