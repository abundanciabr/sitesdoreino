---
schema_version: 2
armadilha: 515
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/pr.py
  - fila/eventos/*
sinal:
  - "fechar-pela-entrega"
guarda:
  tipo: nenhum
  motivo: ci/pr.py nao tem como saber se a TAR --tarefa aponta e a mesma que o proprio PR acabou de criar; a distincao exige julgamento sobre o proposito da tarefa, nao so o estado dela na fila
licao: "ci/pr.py conclui pela fila (fechar-pela-entrega, linha 564) toda TAR identificada, sem checar se ela foi CRIADA no mesmo PR que a esta fechando. O PR #2158 criou a TAR-811 e a mesma chamada a fechou concluida sem os testes previstos. TAR criada para trabalho futuro nunca entra em --tarefa nem no titulo do PR que a criou."
---

# 515: `--tarefa` numa TAR recém-criada no mesmo PR conclui sem trabalho

**Data:** 26/09/2026 · **Onde:** `ci/pr.py`, PR #2158, TAR-811, obra Appmax
· **Custo evitado:** uma TAR marcada concluída sem os testes que ela
prometia, e um incidente e uma TAR sucessora para corrigir o rastro.

## Sintoma

O PR #2158 ("pagamentos: status Appmax medidos") criou a TAR-811 na fila
como descrição do trabalho que faltava (testes de status) e, na mesma
chamada de `ci/pr.py`, essa TAR-811 apareceu como `--tarefa` (ou foi citada
no título) do próprio PR que a criou. `ci/pr.py::abrir` chama
`fila.py fechar-pela-entrega` (linha 564) para toda tarefa identificada, sem
perguntar se ela nasceu de propósito para virar trabalho de um PR seguinte.
A fila gravou a TAR-811 como concluída sem os testes existirem; a correção
saiu como incidente e TAR sucessora.

## Causa

O mecanismo de identificação de tarefa (`_identificar_tarefa`) e o de
conclusão (`fechar-pela-entrega`) são cegos ao propósito da TAR: eles só
conferem se ela existe e não está terminal. Criar e concluir a mesma TAR no
mesmo PR é sintaticamente válido e sempre vai parecer "tarefa feita",
mesmo quando o conteúdo real da tarefa é "fazer isto depois".

## Solução

Uma TAR criada para descrever trabalho futuro nunca entra em `--tarefa`
nem no título do PR que a está criando. Ela só aparece em `--tarefa` no
PR que de fato executa o que ela descreve. Ao escrever uma TAR nova na
mesma sessão que abre um PR, confira que o título e o `--tarefa` desse PR
apontam para uma tarefa diferente (a que estava sendo medida), nunca para
a que acabou de nascer.

## Origem

PR #2158, TAR-811, obra Appmax, sessões de coordenação de 26/09/2026,
`ci/pr.py` linha 564.
