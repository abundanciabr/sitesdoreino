---
schema_version: 2
armadilha: 492
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/pr.py
sinal:
  - "tarefa ja encerrada por outro fato"
  - "tarefa ausente, ambigua ou fila invalida"
guarda:
  tipo: sino
  dono: ci/pr.py
  detector: _submeter_fila e _identificar_tarefa
licao: "ci/pr.py --tarefa so aceita evento concluida cuja evidencia seja ESTE PR. Tarefa ja entregue por OUTRO PR, ou PR que so registra achado, trava o rito DEPOIS de commitar e abrir o PR. Antes de --tarefa, confira se a prova honesta e este PR; senao, git status e commit a mao do recibo ja gerado."
---

# `ci/pr.py --tarefa` assume que a prova da tarefa é o próprio PR

**Data:** 18/09/2026 · **Onde:** `ci/pr.py` ·
**Custo evitado:** um recibo do livro gerado e sem commit, ou cartões desfeitos por engano

## Sintoma

Dois agentes independentes, no mesmo dia, bateram nesta trava por caminhos
diferentes:

1. Ao fechar a TAR-435 com a evidência honesta do PR #1683 (a entrega já
   tinha entrado por outro PR, e faltava só escrever o evento de
   fechamento), o rito parou com:

   ```
   PAROU POR SEGURANCA: tarefa ja encerrada por outro fato
   ```

   O PR #1746 já tinha sido aberto e o recibo já tinha sido escrito quando a
   trava disparou: o recibo ficou sem commit.

2. Ao abrir um PR que só registra um achado novo, sem entregar nenhuma
   tarefa, `_identificar_tarefa` recusou com:

   ```
   tarefa ausente, ambigua ou fila invalida
   ```

   mesmo quando o corpo do PR citava duas TAR relacionadas ao achado, porque
   não havia como escolher qual delas o PR "entrega".

## Causa

`_submeter_fila` (linha 537) chama `submeter` e depois
`fechar-pela-entrega`, e só aceita um evento `concluida` cuja `evidencia`
seja exatamente a URL do PR que está sendo aberto naquele momento.
`_identificar_tarefa` (linha 645) reforça a mesma suposição do lado
contrário: se o PR não entrega claramente uma única tarefa, ela recusa
identificar qualquer uma. As duas funções presumem que "a tarefa que o PR
cita" e "a tarefa que este PR prova" são sempre a mesma coisa. Quando a
prova de uma tarefa já existe em outro PR, ou quando o PR não prova tarefa
nenhuma (só registra um fato), a suposição quebra, e a trava dispara depois
que o commit e a abertura do PR já aconteceram.

## Solução

Antes de chamar `ci/pr.py --tarefa TAR-NNN`, pergunte: a evidência honesta
desta tarefa é ESTE PR que estou abrindo agora, ou é outro? Se for outro
PR (a entrega já aconteceu em outro lugar e falta só fechar o evento):

- Chame `ci/pr.py` sem `--tarefa` para este PR.
- Depois de o rito travar (ou antes, se você já sabe que vai travar),
  confira `git status`: o commit e o recibo do livro já foram gerados por
  `ci/pr.py` e continuam corretos, sem alterar uma linha.
- Commite a mão o que sobrou (o recibo/registro), sem editar o conteúdo
  que `ci/pr.py` já escreveu, e declare isso no corpo do PR.
- Feche a tarefa separadamente com `python ci/fila.py concluir TAR-NNN
  --evidencia <URL do OUTRO PR>`.

Se o PR não entrega tarefa nenhuma (só registra achado), não force
`--tarefa`: abra o PR sem ele. Citar a TAR relacionada em prosa no corpo do
PR é suficiente; forçar `_identificar_tarefa` a escolher entre duas tarefas
ambíguas quebra o rito e pode levar a desfazer trabalho de fila que estava
certo.

## O que NÃO é a causa

Não é bug em `_submeter_fila` nem em `_identificar_tarefa`: as duas fazem
exatamente o que a assinatura promete, aceitar só a prova que é este PR. O
problema é a suposição implícita de que todo PR com `--tarefa` prova aquela
tarefa, que não é verdade quando a fila e o PR se desalinham no tempo.
