---
schema_version: 2
armadilha: 526
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o rito nao tem como distinguir uma citacao textual de uma tarefa de uma declaracao real de qual tarefa aquele PR fecha; so quem escreve o titulo ou o detalhe sabe a intencao.
sinal:
  - "fila invalida: evento depois do fim"
gatilho:
  - "ci/pr.py"
licao: "ci/pr.py identifica qualquer TAR-N no --titulo ou no --detalhe e embarca eventos submetida/concluida dessa tarefa mesmo sem --tarefa, sem conferir depende_de nem se a tarefa ja terminou. Cite so a TAR da propria entrega; outra tarefa vira \"tarefa 818\" sem prefixo, ate o rito passar a usar so --tarefa."
---

# 526: `ci/pr.py` deduz a tarefa de qualquer `TAR-N` citado no título ou no detalhe

**Data:** 27/09/2026 · **Onde:** PRs #2189 e #2190 · **Custo evitado:** fechar
ou tocar uma tarefa que não é a do PR, quebrando a fila e exigindo remendo manual

## Sintoma

Dois PRs citaram outra tarefa só como referência de texto, e o rito fechou
essa tarefa de verdade:

- PR #2190: título com "(TAR-819)" fechou a TAR-819, que estava bloqueada
  esperando a TAR-800 terminar.
- PR #2189: detalhe citava "TAR-818", já concluída pelo PR #2188; o evento
  duplicado fez a muralha reprovar com:

```
fila invalida: evento depois do fim
```

Foi preciso `git rm` dos dois eventos indevidos e marcar `tarefa: null` no
recibo para destravar o pouso.

## Causa

`ci/pr.py` procura o padrão `TAR-N` em `--titulo` e `--detalhe` para inferir
qual tarefa o PR fecha, e usa esse número mesmo quando `--tarefa` não foi
passado. Ele não confere se `depende_de` daquela tarefa ainda está aberto
nem se ela já tem evento de conclusão: qualquer menção textual vira uma
tentativa de submeter e concluir a tarefa citada.

## Solução

Até o rito ser corrigido para usar só `--tarefa` (nunca inferir do texto),
cite outra tarefa sempre sem o prefixo `TAR-`, por exemplo "tarefa 818", para
não disparar a dedução. Quando o PR realmente fecha uma tarefa, passe
`--tarefa TAR-N` explicitamente.

## Evidência

PRs #2189 e #2190, 27/09/2026, remendados com `git rm` dos eventos indevidos
e `tarefa: null` no recibo.
