---
schema_version: 2
armadilha: 527
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o pouso escuta o evento de abertura do PR, entao qualquer janela entre abrir o PR e empurrar o recibo e uma corrida real, nao um defeito de codigo especifico para blindar.
sinal:
  - "remote ref does not exist"
gatilho:
  - "ci/pr.py"
licao: "a pista integra o PR entre o ci/pr.py abrir o PR e empurrar o recibo, porque o pouso dispara pelo evento de abertura e o PR ja esta verde. Aconteceu nos #2164, #2178 e #2188. Nao e defeito nem motivo para reabrir: o recibo e os eventos vao por PR de recibo (cherry-pick do commit do recibo num ramo novo)."
---

# 527: a pista integra o PR entre `ci/pr.py` abrir e empurrar o recibo

**Data:** 27/09/2026 · **Onde:** PRs #2164, #2178 e #2188 · **Custo evitado:**
tentar reabrir ou refazer um PR que já foi integrado, achando que algo falhou

## Sintoma

Depois de `ci/pr.py` abrir o PR, antes de o próprio comando terminar de
empurrar o commit do recibo, o pouso automático já integrou o PR: ele dispara
pelo evento de abertura, e naquele momento o PR já estava com os checks
verdes. O comando então tenta empurrar o recibo para um ramo cujo PR já foi
mergeado.

## Causa

`pouso.yml` reage ao evento de abertura do PR, não ao término do `ci/pr.py`.
Como a validação local já passou antes de abrir o PR, o SHA já nasce verde,
e a janela entre "abrir" e "empurrar recibo" é grande o bastante para o
`ci/mergear.py --automatico` correr primeiro. O merge automático apaga o
ramo remoto, e o `git push` do recibo que ainda estava em voo falha com:

```
error: remote ref does not exist
```

## Solução

Isto não é um defeito a corrigir nem motivo para reabrir o PR original. O
recibo e os eventos que não subiram a tempo seguem por um PR de recibo à
parte: `cherry-pick` do commit do recibo para um ramo novo, e abrir esse PR
separado.

## Evidência

PRs #2164, #2178 e #2188, 27/09/2026, cada um seguido de um PR de recibo
para completar o registro.
