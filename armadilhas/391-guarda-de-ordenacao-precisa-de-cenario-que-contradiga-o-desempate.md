---
schema_version: 2
armadilha: 391
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhuma muralha enxerga um cenário de teste fraco; o que existe é a prova por mutação que a ficha do despacho já exige (§4), e esta entrada diz COMO montar o cenário para a mutação ter chance de reprovar
sinal:
  - guarda de ordenação
  - sabotagem passou verde
  - cenário fraco de ordenação
---

# 391 — Guarda de ORDENAÇÃO precisa de um cenário em que o desempate contradiga a regra, senão a mutação passa verde

**Data:** 07/09/2026 · **Onde:** PR #1342 (a aba Prioridades do painel do dono), `painel/testes/teste_logica.js` · **Custo evitado:** uma regra de ordem sem guarda de verdade na tela do mantenedor, descoberta só quando a lista aparecesse fora de ordem na cara dele.

## Sintoma

Você escreve a regra "a fila dos robôs sai por importância, da maior para a
menor, e o id desempata". Escreve o teste com três tarefas, roda: verde. Aí
faz a mutação que a ficha do despacho manda (§4): apaga a comparação por
importância e deixa só o desempate por id. Roda de novo:

```
  PASS a fila dos robôs sai por importância, da maior para a menor
```

Continua verde. O guarda não testa nada: o cenário tinha as tarefas
`TAR-001` (90), `TAR-002` (70), `TAR-003` (40), e a ordem por id era a MESMA
ordem por importância. Qualquer implementação que ordene por id passa.

## Causa

É a mesma doença da `armadilhas/317`, agora numa ordenação: o teste está
certo e o mundo dele é pequeno demais para conter o erro. Numa regra de
ordem, "pequeno demais" tem forma exata: **todos os critérios do cenário
concordam entre si**. Quando o desempate (id, data de criação, ordem de
inserção) já produz a ordem esperada, a regra principal pode ser apagada
sem que nada mude. E o desempate por id concorda com a importância com
frequência, porque quem escreve o cenário numera as tarefas na ordem em que
pensa nelas: a mais importante primeiro.

## Solução

Monte o cenário para que cada critério CONTRADIGA o seguinte:

```js
// o id vai na ordem contrária da importância, e a data também
{ id: "TAR-003", importancia: 90 },   // mais importante, MAIOR id
{ id: "TAR-001", importancia: 40 },   // menos importante, MENOR id
{ id: "TAR-002", importancia: 70 }
// esperado: TAR-003, TAR-002, TAR-001
```

Assim, uma implementação que ordene por id devolve `001, 002, 003` e o
teste reprova. Regra geral: **para cada critério de ordem, o cenário precisa
de um par de itens em que SÓ aquele critério decide, e em que os outros
critérios apontariam para a ordem contrária.** Para uma regra com três
critérios (selo, importância, id), são três pares assim, e a mutação de cada
critério tem de pintar vermelho o par dele.

Vale para toda ordenação com desempate: pedidos por peso e depois por idade,
alertas por gravidade e depois por data, tarefas por selo e depois por número.
O sinal de que o cenário está fraco é sempre o mesmo: a mutação passa verde na
primeira tentativa. Quando isso acontecer, corrija o cenário, nunca o código.
