---
schema_version: 2
armadilha: 349
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão consegue medir "outra conversa do mantenedor já está neste assunto"; o balcão da fila tranca TAREFA (reserva no servidor), e pedido que chega direto pela conversa não tem número de tarefa para trancar — o que existe é a consulta de dois segundos deste arquivo, feita por quem está na frente, antes do primeiro despacho
sinal:
  - o arquivo que eu ia criar ja esta na main
  - PR aberto com o mesmo assunto
  - duas sessoes na mesma obra
  - o mesmo documento por duas sessoes
---

# Duas sessões do mantenedor na MESMA obra: o segundo PR nasce morto, e quem paga é ele

**Sintoma.** Você recebe um pedido pela conversa ("retome X"), faz o
reconhecimento, escreve o brief, dispara os despachos, e no meio do caminho
descobre que outra sessão do mesmo mantenedor entregou a mesma coisa: o arquivo
que o seu robô ia criar **já está na `main`**, vindo de um PR que pousou minutos
antes. O seu `git merge origin/main` não acusa conflito nenhum, porque não há o
que conflitar. O trabalho já foi feito.

**Causa.** Nada neste repositório impede duas sessões de pegarem o mesmo
assunto. O balcão (`ci/fila.py pegar`) tranca TAREFA, com reserva atômica no
servidor do GitHub — mas só tranca quem passa por ele. Pedido que chega direto
pela conversa não tem número de tarefa, não passa pelo balcão e portanto não
tranca nada. Duas conversas abertas no mesmo dia, sobre o mesmo assunto,
produzem dois planos, dois briefs e dois PRs que ninguém pediu em dobro.

**O que custou em 05/09/2026**, o dia em que isto foi medido: duas sessões
retomaram o portfólio do aluno com minutos de diferença. Uma escreveu o
`CS-PAGES-0001` cobrindo os 18 degraus do plano; a outra encomendou um documento
mais estreito, só do checklist, e ainda pôs o guia na célula errada. O PR mais
estreito foi jogado fora inteiro, e o mantenedor teve de parar o que estava
fazendo para arbitrar qual das duas sessões continuava com a obra.

**Solução: duas consultas, antes do primeiro `Agent`.**

```bash
# quem está com a mão no assunto AGORA
gh pr list --state open --limit 50 --json number,title \
  --jq '.[] | "\(.number) \(.title)"' | grep -i "<assunto>"

# quem acabou de pousar (o seu origin/main pode ser de 10 minutos atrás)
git fetch origin && git log origin/main --since="6 hours ago" --oneline | grep -i "<assunto>"
```

Custa dois segundos e cabe antes de qualquer despacho. **O limite, dito na
cara:** ela só enxerga quem já abriu PR. Duas sessões que começam no mesmo
minuto não se veem por aqui, e nenhuma consulta barata resolve isso.

**Quando as duas já estão em voo, quem decide é o mantenedor.** A sessão que
descobre a outra manda um recado (`send_message`) com o estado REAL do próprio
lado, **medido por comando e não de memória**, e para de trabalhar no assunto.
Não feche o PR do outro nem "resolva" por conta própria: o recado que chegou
aqui em 05/09 pedia para eu fechar um PR que, minutos antes, eu já tinha
reduzido justamente à metade que ninguém mais tinha feito. Fechar teria matado
uma correção viva por causa de um retrato velho.

**Não confunda com as vizinhas.** A [135](135-suas-edicoes-sumiram-outra-sessao-trocou-o-ramo.md)
e a [068](068-lote-outra-sessao-escrevendo-no-seu-worktree-git.md) são duas
sessões na mesma PASTA, e a cura delas é a bancada própria. Esta é a mesma OBRA,
e worktree nenhum a evita: o desperdício acontece com as duas sessões
trabalhando certinho, cada uma na sua bancada.
