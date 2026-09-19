---
schema_version: 2
armadilha: 392
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o harness só avisa no fim ("stopped at its 40-turn limit"), depois de os tokens terem sido gastos, e nenhum portão mede o tamanho de um brief antes do disparo; o que existe é a régua desta entrada, aplicada por quem escreve o brief
sinal:
  - stopped at its 40-turn limit
  - partial result; SendMessage to task-id to continue
  - parou no limite de turnos sem veredito
---

# 392 — Brief de revisor que pede a ficha inteira mais mutações e suíte não cabe em 40 turnos: o revisor morre calado

**Data:** 07/09/2026 · **Onde:** os revisores dos PRs #1340 e #1342 (rota `fila.json` e aba Prioridades do painel), lote da maestro · **Custo medido:** dois revisores, 101 mil e 85 mil tokens, zero linha de veredito; os dois PRs pousaram só com a leitura do revisor de pouso da pista.

## Sintoma

A maestro dispara o `revisor` com um brief caprichado: o contrato inteiro do
PR, os nove pontos da ficha, "ataque especialmente" com sete itens, sabote
cinco guardas e rode a suíte da célula. Vinte minutos depois chega a
notificação:

```
Agent "Revisor do PR 1342 (aba Prioridades)" stopped at its 40-turn limit
(partial result; SendMessage to task-id to continue)
Vou revisar o PR #1342. Começando pela conferência do diff contra o brief.
```

O "resultado parcial" é a primeira frase do revisor. Todo o trabalho dele
ficou no transcript, que ninguém lê, e o `SendMessage` que a notificação
sugere não existe neste harness. O PR pousa sem a segunda leitura, e a
maestro só descobre depois do merge.

## Causa

A ficha do `revisor` tem `maxTurns: 40`, e cada `Bash`, `Read` ou `Grep` é um
turno. Ler um diff de nove arquivos já custa dez a quinze turnos; cada
mutação custa três (sabotar, rodar, desfazer); rodar a suíte de uma célula
com banco custa mais alguns. Um brief que pede tudo isso soma sessenta
turnos ou mais, e o revisor não sabe que vai morrer: ele segue a ordem da
ficha, gasta os quarenta lendo e medindo, e o relatório, que é a última
coisa, nunca chega. Diferente do despacho, o revisor não tem PR nem registro
para deixar rastro: quando ele morre, morre inteiro.

## Solução

Dimensione o brief do revisor pelo teto, não pela vontade:

- **Leitura primeiro, mutação por último, e no máximo duas.** Peça a
  conferência do diff contra o brief, a cerca, o recibo e os estados; das
  sabotagens, escolha as duas que mais importam (o guarda novo e o filtro
  que some com fato) e diga quais são.
- **Não peça a suíte inteira.** O despacho já a rodou e colou a saída; o
  check do PR a roda de novo. Peça só o arquivo de teste do PR.
- **Escreva o teto no brief:** "no máximo 25 turnos; se não couber, devolva
  o veredito parcial dizendo o que NÃO CONFERIU". O revisor que sabe do teto
  escreve o relatório antes de bater nele.
- **Dispare o revisor quando o PR abrir, e não depois**: a leitura serve
  ANTES do pouso; depois do merge ela só rende tarefa de conserto.

O terceiro revisor deste mesmo lote (PR #1337) recebeu o teto escrito e a
lista de duas mutações; é a versão do brief que cabe.
