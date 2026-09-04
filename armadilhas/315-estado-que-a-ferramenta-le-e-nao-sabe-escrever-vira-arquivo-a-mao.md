---
schema_version: 2
armadilha: 315
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: o verbo novo tem de recusar tudo o que a validação recusaria depois, senão ele vira fábrica de fila inválida; são cinco guardas porque são cinco recusas distintas, e a prova de que cada um morde é a mutação de uma linha por vez
sinal:
  - "_escrever_evento("
  - "RECUSADO: bloquear sem motivo não existe"
---

# O estado que a ferramenta sabe LER e não sabe ESCREVER vira arquivo feito à mão

**Sintoma.** Duas sessões do mesmo lote, sem falar uma com a outra, escreveram
um arquivo de evento da fila à mão, em JSON, fora do balcão. Uma delas chamou
`fila._escrever_evento` por dentro do módulo. Nenhuma das duas estava
contornando regra nenhuma: elas só queriam registrar um estado que o balcão
calcula desde que nasceu e nunca soube criar.

**Causa.** `ci/fila.py` tinha `criar`, `pegar`, `soltar`, `concluir` e `validar`.
O estado `bloqueada` existia dos dois lados de todo o resto: `calcular_estados`
o computa, `validar` exige `detalhe` nele, o painel o mostra, e as tarefas
`bloqueada` da fila eram todas de eventos escritos à mão. **Faltava só o verbo.**

Uma superfície que exibe um estado e não oferece o gesto de produzi-lo não
impede o gesto: ela o empurra para fora da ferramenta, onde nenhuma recusa
existe. E foi de propósito que as recusas foram construídas: escrever o evento
à mão pula a recusa no espelho, pula a soltura da reserva no servidor, pula a
conferência de "essa tarefa já terminou", e pula a exigência de motivo que a
própria `validar` faz depois. É a porta de entrada da `armadilhas/192` — o
arquivo nasce onde ninguém commita, o PR viaja sem ele, e `validar` responde
`✅ Fila válida` porque o que não está lá não pode reprovar.

**Solução.** O verbo entrou:

```bash
python ci/fila.py bloquear TAR-NNN --quem "sessao-x" --motivo "o que trava, e o que destrava"
```

Ele recusa no espelho (como `concluir`, porque o comprovante tem de nascer na
bancada para embarcar no PR), recusa sem motivo, recusa tarefa que já terminou,
e solta a reserva no servidor — quem bloqueia larga a tarefa, senão a trava viva
continuaria contando como `reivindicada` na vista ao vivo até expirar sozinha em
três horas, e o quadro mostraria duas verdades sobre a mesma linha.

`soltar` continua livre no espelho, e a diferença é deliberada: devolver à fila
uma tarefa presa é gesto de emergência, e emergência não pode depender de ter
worktree.

**Prova.** Cinco guardas em `ci/tests/test_fila.py`, vermelhos contra a versão
sem o verbo (5 de 5, por `AttributeError`). Depois do verde, seis mutações
deliberadas, uma linha por vez — e cada uma derruba **exatamente um** guarda,
que é o que prova que nenhum deles está verde por tabela:

| mutação | quem cai |
|---|---|
| o motivo deixa de ser exigido | o guarda do motivo |
| o evento nasce com o nome errado (`devolvida`) | o guarda do estado calculado |
| o motivo vai para o campo errado | o guarda do estado calculado |
| a reserva não é solta | o guarda da reserva |
| o espelho deixa de recusar | o guarda do espelho |
| tarefa terminada passa a aceitar bloqueio | o guarda do fim |

**A régua que fica, e vale para qualquer superfície desta casa:** para cada
estado que uma ferramenta CALCULA, pergunte quem o escreve. Se a resposta for
"uma pessoa, num editor de texto", o estado tem um caminho sem portão — e o
portão que existe no fim da fila não protege o que nunca passou por ele.
