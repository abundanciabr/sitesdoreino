---
schema_version: 2
armadilha: 227
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_indice_de_armadilhas.py
sinal: null
---

# A mensagem de erro ensinou o conserto que OUTRO guarda reprova — e três robôs obedeceram, os três reprovados

**Sintoma:** você faz exatamente o que a mensagem de erro mandou, e o PR fica
vermelho por causa disso. Primeiro o gerador do índice para:

```
❌ ERROR indice-de-armadilhas: número repetido em 'armadilhas/': 218
  218 — 2 arquivos:
    - armadilhas/218-<a-sua>.md
    - armadilhas/218-<a-de-outra-sessao>.md

Conserte renomeando a SUA entrada — a que ainda NÃO está na main — para o
primeiro número acima de todos, hoje 219, e regenere o índice:

  git mv armadilhas/218-<o-seu-slug>.md armadilhas/219-<o-seu-slug>.md
```

Você obedece. E aí o portão seguinte, no mesmo PR, diz o contrário:

```
  entrada-nova  FAIL   número escolhido à mão: 219
```

**Causa: dois guardas se contradiziam sobre o mesmo número.** A regra da casa
mudou em 29/08/2026 — número de armadilha passou a ser **pedido** ao almoxarife
(`python ci/reservar.py numero armadilha`, uma reserva comparar-e-trocar no
servidor do GitHub), e `ci/muralha-das-reservas.sh` passou a reprovar, em todo
PR, número novo sem reserva. O `ARMADILHAS.md` e o `CLAUDE.md` foram corrigidos
junto. **A mensagem de erro do gerador não foi** — ela continuou ensinando a
receita velha, "escolha o primeiro número acima de todos", que era exatamente o
que a muralha nova existia para recusar.

Isso é pior que documentação desatualizada. Documento desatualizado é lido por
quem tem tempo; **mensagem de erro é lida por quem está com pressa e errado** —
ela chega no momento de maior obediência que existe numa sessão. Em 30/08/2026
ela custou uma rodada de CI a **três robôs diferentes** que não se conheciam: o
da TAR-029, o autor do commit `56af952` ("número pedido ao almoxarife (a muralha
das reservas ensinou)") e a própria sessão principal. Nenhum dos três estava
errado. A instrução estava.

A pista de que a mensagem estava velha, e ninguém viu: ela **calculava** o
número novo (`livre = max(por_numero) + 1`). Um guarda que calcula o número é um
guarda que decidiu que a escolha é dele — e a partir do dia em que a escolha
passou a ser do almoxarife, esse cálculo virou uma opinião concorrente.

**Solução:** a mensagem manda pedir o número, e não escolhe nenhum — o
`git mv` continua lá (renomear ainda é o que se faz com o arquivo já escrito),
mas o destino é o `NNN` que o almoxarife devolver, e o campo `armadilha:` do
frontmatter muda junto. O cálculo do "primeiro livre" foi **removido**, não
comentado: enquanto ele existisse, alguém o imprimiria de novo. Caíram, no mesmo
PR, as outras três cópias da receita velha — o cabeçalho que o gerador escreve
dentro do `armadilhas/INDICE.md`, a mensagem de falha do teste que mede a pasta
real, e o parágrafo "se você caiu aqui" da `armadilhas/085`. Instrução errada em
quatro lugares é a lei anti-duplicação cobrando juros.

**A regra que fica, e que é maior que este caso:** quando uma regra sobe a
Escada da Imposição (Lei 1) e ganha um portão, **o inventário de quem ENSINA a
regra antiga tem de subir junto**. Não basta corrigir o documento-lei: procure a
regra velha nas mensagens de erro, nos comentários de código, nas mensagens de
`assert` e nas armadilhas que a citam. `grep` pela frase, não pelo arquivo. Dois
guardas que se contradizem não são um bug de um deles — são um dos dois vivendo
num degrau que o outro já subiu.

**Guarda:** `test_a_colisao_manda_pedir_o_numero_ao_almoxarife`, em
`ci/tests/test_indice_de_armadilhas.py`, força a colisão e afirma as duas
metades: que a mensagem ensina `ci/reservar.py numero armadilha`, e que ela não
nomeia número nenhum (o "primeiro livre" do repositório de teste não pode
aparecer em lugar nenhum da saída). Ele roda em todo PR pela suíte do testador.

**Origem:** TAR-036, 30/08/2026 — aberta pelo robô da TAR-029 depois de ele
mesmo cair, e confirmada por duas outras sessões no mesmo dia.
