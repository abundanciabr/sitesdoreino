---
schema_version: 2
armadilha: 530
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/pr.py
  - painel/registros/*
sinal:
  - "tarefa não identificada para esta sessão"
guarda:
  tipo: nenhum
  motivo: "_identificar_tarefa nao tem como saber que o proprio recibo do PR e a prova que a divida do livro pede; distinguir isso exigiria repetir em ci/pr.py a mesma regra de isencao de ci/divida_do_livro.py, mudanca de codigo fora do alcance desta entrada"
licao: "ci/pr.py exige uma TAR identificavel mesmo quando o PR so escritura painel/ ou fila/ e ja seria isento da divida do livro. O PR 2160 pousou sem recibo por contar como isento; o PR 2182 precisou de uma TAR so para satisfazer ci/pr.py. Antes de abrir um PR so de painel/fila, reserve ou reutilize uma TAR com --tarefa."
---

# 530: `ci/pr.py` exige TAR mesmo em PR que só escritura `painel/`

**Data:** 26 e 27/09/2026 · **Onde:** `ci/pr.py`, PRs #2160 e #2182, obra
Appmax · **Custo evitado:** abrir o PR sem TAR e travar tarde, já com commit
e push feitos, numa entrega que a dívida do livro trataria como isenta.

## Sintoma

`ci/divida_do_livro.py` isenta explicitamente o PR que só escritura
`painel/` e/ou `fila/` ("PR que só escritura (painel/ e/ou fila/) é isento:
ele É o registro", `ci/divida_do_livro.py` linhas 294 e 417). Isso não
dispensa `ci/pr.py`: sua própria função `_identificar_tarefa` continua
exigindo um candidato a TAR (por `--tarefa`, pela tarefa da abertura, por
ramo já reivindicado, ou citada no título/corpo), e sem nenhum deles recusa
com

```
PAROU POR SEGURANÇA: tarefa não identificada para esta sessão
```

O PR #2160 (V8, medição pública da vista) pousou sem recibo por contar como
isento perante a dívida do livro; o PR #2182 (lições da coordenação) teve
que criar a TAR-822 só para que `ci/pr.py` aceitasse abrir o PR, mesmo o
conteúdo sendo apenas armadilhas e índice.

## Causa

Duas travas independentes leem a mesma árvore de arquivos com regras
diferentes: `ci/divida_do_livro.py` pergunta "este PR precisa de um
registro no livro, ou ele já É o registro?" e isenta `painel/`/`fila/`
puros; `ci/pr.py::_identificar_tarefa` pergunta "que tarefa da fila este PR
fecha?" e nunca considera a resposta "nenhuma, porque este PR é
autoisento". As duas perguntas soam parecidas mas não são a mesma.

## Solução

Antes de abrir um PR que só toca `painel/` e/ou `fila/`, não presuma que a
isenção da dívida do livro dispensa a fila: reserve uma TAR (mesmo pequena,
`--move manutencao`) ou reutilize uma já aberta com `--tarefa TAR-NNN`. O
recibo pode acabar isento pela dívida do livro; a identificação da tarefa em
`ci/pr.py` continua exigida do mesmo jeito.

## Origem

PRs #2160 e #2182, obra Appmax, sessões de coordenação de 26 e 27/09/2026;
`ci/pr.py::_identificar_tarefa` e `ci/divida_do_livro.py` linhas 294 e 417.
