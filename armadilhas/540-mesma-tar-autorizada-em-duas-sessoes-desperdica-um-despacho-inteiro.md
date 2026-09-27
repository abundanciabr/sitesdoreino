---
schema_version: 2
armadilha: 540
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum comando confere, antes do despacho, se outra sessao ja reivindicou a mesma TAR fora da fila local; exigiria consulta obrigatoria ao GitHub antes de todo despacho, mudanca de processo fora do alcance de uma entrada de licao
sinal:
  - "a tarefa TAR-\\d+ já terminou \\(concluida\\)"
gatilho:
  - "python ci/pr.py"
licao: "O mantenedor pode autorizar a mesma TAR em duas sessoes distintas (ex.: APPMAX e experimentos, minutos de diferenca); as duas despacham em paralelo e so uma integra. Antes de despachar uma TAR ja autorizada, confira python ci/fila.py listar --ao-vivo e gh pr list --search \"TAR-N\" para ver se outra sessao ja a reivindicou."
---

# 540: A mesma `TAR` autorizada em duas sessões desperdiça um despacho inteiro

**Data:** 27/09/2026 · **Onde:** PRs #2247 e #2248, TAR-837 ·
**Custo evitado:** um despacho inteiro perdido (~45 min de trabalho de
sessão) quando duas sessões constroem a mesma entrega em paralelo.

## Sintoma

A TAR-837 foi autorizada pelo mantenedor em duas sessões diferentes (APPMAX
às 08h29 e experimentos às 08h43). As duas despacharam a mesma tarefa em
paralelo. O PR #2248 integrou às 12:29Z; o PR #2247, com conteúdo idêntico
byte a byte, foi fechado quando a muralha da fila reprovou com

```
a tarefa TAR-837 já terminou (concluida)
```

## Causa

Nada na abertura de sessão (`ci/sessao.py`) nem no despacho confere, em
tempo real, se a TAR pedida já foi reivindicada ou concluída por outra
sessão viva. A fila local de cada bancada só reflete o que ela já buscou;
duas sessões abertas quase ao mesmo tempo não se veem uma à outra até o
`ci/pr.py` de uma delas publicar.

## Solução

Antes de despachar uma TAR que o mantenedor acabou de autorizar, confira:

```
python ci/fila.py listar --ao-vivo
gh pr list --search "TAR-837"
```

Se outra sessão já tem PR aberto ou tarefa reivindicada para o mesmo número,
não despache: aguarde o desfecho dela ou avise o mantenedor da colisão.

## Evidência

PRs #2247 (fechado, idêntico) e #2248 (integrado às 12:29Z), TAR-837,
27/09/2026.
