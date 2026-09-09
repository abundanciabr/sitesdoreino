---
schema_version: 2
armadilha: 457
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: O julgamento da revisão automática é externo; preservar o mandato no brief não impõe aprovação nem desliga a proteção.
gatilho:
  - painel/LEIA-ME.md
  - .claude/agents/despacho.md
sinal: 'mas não autoriza claramente esse novo payload e envio\.'
licao: Transporte o pedido original, o destino verificado e os limites da autorização no brief e na requisição. Antes de pedir outro sim, confira a prova existente; uma recusa exige reavaliação pela mesma proteção ou alternativa materialmente mais segura.
---

# 457 — Autorização perdida no brief vira outra pergunta

**Data:** 09/09/2026 · **Onde:** PR #1507 · **Custo evitado:** interrupções para repetir uma autorização já dada.

## Sintoma

A revisão automática recusou o envio de um recibo. Trecho literal da recusa,
com o restante omitido para preservar dados privados:

```text
mas não autoriza claramente esse novo payload e envio.
```

## Causa

A autorização precisa ser demonstrável para quem avalia a ação. Um brief
que resume apenas a tarefa pode perder o pedido original, seu destino e
seus limites. Além disso, um recibo que copia nomes ou evidências internas
pode ampliar a exposição: não é apenas uma troca mecânica de revisão.

## Solução

Levar ao brief e à requisição a autorização existente, seus limites, o
destino conferido e o conteúdo técnico mínimo a enviar. Neste trabalho,
a mesma ação foi reavaliada e aprovada após apresentar essas evidências,
sem outra autorização do mantenedor e sem alterar a proteção.

Uma nova revisão exige validação e revisão do código; por si só, não muda
a finalidade do recibo. Porém, autorização limitada explicitamente a uma
ação ou revisão continua limitada. Não inferir licença para publicar nomes,
conversas, logs ou conteúdo privado. Se a recusa persistir, usar alternativa
materialmente mais segura ou levar a decisão concreta à maestro. Nunca
trocar de ferramenta para contornar a recusa.

Evidência da orientação entregue: https://github.com/abundanciabr/sitesdoreino/pull/1507.
A orientação documenta a prática; não garante a decisão de um revisor externo.
