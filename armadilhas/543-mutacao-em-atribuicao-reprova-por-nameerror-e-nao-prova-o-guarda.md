---
schema_version: 2
armadilha: 543
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: provar_guardas.py so sabota a linha que o marcador aponta; escolher a linha certa (return/raise/condicao ou atribuicao comparada) e julgamento de quem escreve o marcador, nao algo que o script possa validar sozinho
sinal:
  - "NameError"
gatilho:
  - "ci/provar_guardas.py"
  - "ci/tests/"
licao: "Apontar # guarda: para uma ATRIBUICAO (x = f(...)) faz a sabotagem reprovar por NameError numa linha DEPOIS, nao pela asserção do invariante (mesmo engano de sabotar import). Medido: PR #2246 7 de 9 guardas por NameError; PR #2245 4 de 12. Aponte para return/raise/condicao ou atribuicao cujo VALOR o teste compara; NameError isolado nao prova nada."
---

# 543: Mutação em atribuição reprova por `NameError`, e isso não prova o guarda

**Data:** 27/09/2026 · **Onde:** PRs #2246 (admin) e #2245 (métricas) ·
**Custo evitado:** declarar um guarda "provado por mutação" quando a
sabotagem só derrubou o teste por variável indefinida, sem tocar o invariante
que o guarda deveria proteger.

## Sintoma

Comentar uma linha de atribuição (`x = f(...)` → `pass # x = f(...)`) faz o
teste correspondente reprovar, mas com

```
NameError: name 'x' is not defined
```

numa linha bem depois da sabotada, não na asserção que deveria detectar o
comportamento errado. Medido em 27/09/2026: no PR #2246 (admin), 7 de 9
guardas "provados" caíram por `NameError`; no PR #2245 (métricas), 4 de 12.

## Causa

`ci/provar_guardas.py` sabota literalmente a linha marcada, comentando-a com
o prefixo do dialeto (`pass  # ` em Python). Se essa linha é uma atribuição
cujo valor só é usado adiante, a ausência da variável quebra a execução no
primeiro uso seguinte — um erro de sintaxe/runtime, não uma reprovação de
asserção. O teste "reprova", mas por um motivo que qualquer mutação
aleatória naquele bloco também produziria: não prova que o teste sabe
distinguir o comportamento certo do errado (o mesmo engano de sabotar um
`import`, já condenado em `.claude/agents/provador.md`).

## Solução

Ao escolher onde apontar `# guarda: caminho:linha`, prefira:

- uma linha `return`, `raise` ou uma condição de uma linha só (o `if` que
  decide o caminho), cuja ausência muda o resultado que o teste lê; ou
- uma atribuição cujo **valor** o teste compara diretamente (`assert x ==
  ...`), não uma atribuição intermediária cujo nome só aparece de novo mais
  tarde.

Reprovação por `NameError` isolado, sem nenhuma asserção de invariante
reprovando no caminho, não conta como prova específica do guarda: escolha
outra linha e prove de novo.

## Evidência

PR #2246 (admin), 7 de 9 guardas por `NameError`; PR #2245 (métricas), 4 de
12; medido em 27/09/2026.
