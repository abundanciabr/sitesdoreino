---
schema_version: 2
armadilha: 287
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe dizer se o que você está prestes a construir já existe num PR aberto — a pergunta é sobre INTENÇÃO, e só quem vai começar a tarefa a tem. Um portão que tentasse medi-la precisaria adivinhar o que a sessão pretende fazer antes de ela fazer. O que existe é o GESTO, que cabe numa linha de `gh` e está escrito abaixo
---

# O trabalho já estava feito num PR aberto que ninguém leu

**Sintoma.** Você constrói uma coisa do zero, com testes, guardas e comentários
— e depois descobre um PR aberto, de dias atrás, fazendo exatamente aquilo. Nos
mesmos arquivos. Às vezes com uma decisão MELHOR do que a sua num ponto que você
resolveu por baixo.

Medido em 02/09/2026: o PR #871 (o rodapé do site na Caixa de Sugestões) foi
escrito inteiro sem ninguém notar o **#734**, aberto em 31/08 com o mesmo título,
os mesmos nove arquivos e três dos mesmos guardas de prefixo. Descobri sozinho,
depois do merge, rodando `gh pr list` por outro motivo.

**Causa.** O rito manda pedir pouso e ir embora (`RITOS.md` §2 peça 5), e é uma
boa regra: ela existe para o agente não ficar na corrida. O efeito colateral é
que **PR devolvido pela pista, ou que deu conflito, some do campo de visão de
todo mundo** — ninguém está esperando por ele. O repositório tem dezenas de
merges por dia; um PR de dois dias atrás é história antiga.

E a fila de trabalho não protege disto: ela responde "quem está fazendo o quê
AGORA", enquanto um PR aberto responde "o que já foi feito e não pousou". São
perguntas diferentes, e a segunda não tinha quem a fizesse.

**A parte cara não é o retrabalho.** É que o PR esquecido costuma ter pensado em
alguma coisa que você não pensou. No caso medido, o #734 tinha RESOLVIDO uma
restrição que eu ACEITEI: a porta da Caixa não carrega folha de estilo externa, e
eu declarei aquela tela "sem rodapé" por causa disso; ele havia transformado o
rodapé em peça incluída pelos dois moldes, com o estilo embutido e as cores do
sistema. A minha versão entregou uma tela a menos, e só não ficou assim porque a
descoberta veio no mesmo dia.

**Solução — um comando, antes de escrever a primeira linha:**

```bash
gh pr list --state open --json number,title,updatedAt --jq '.[] | "#\(.number) \(.title)"'
```

Leia a lista inteira. Ela cabe numa tela, e o custo dela é uma chamada. Se
alguma linha tocar a sua tarefa:

1. **Leia o diff antes de decidir** (`gh pr diff <N>`). Mesmo que ele não sirva
   inteiro, o que ele PENSOU costuma servir.
2. **Se ele está bom e só envelheceu**, o caminho é atualizá-lo — não abrir o
   seu ao lado.
3. **Se você seguir por outro caminho**, diga isso NO PR antigo, em comentário,
   e feche-o citando o novo. PR aberto que virou lápide é a próxima pessoa
   caindo aqui.

**A regra de bolso:** *PR aberto é trabalho pronto que ninguém está olhando.* A
lista de PRs abertos deste repositório é curta e envelhece rápido — em 02/09 ela
tinha cinco, e DOIS eram sobre a mesma peça que eu estava construindo.

**Origem:** 02/09/2026, na sequência de PRs que levou o menu e o rodapé às áreas
que ainda não os tinham (#868 a #873). O conserto entrou no #873, aproveitando o
desenho do #734.
