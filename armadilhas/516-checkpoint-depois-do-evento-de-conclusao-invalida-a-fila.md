---
schema_version: 2
armadilha: 516
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/fila.py
  - fila/eventos/*
sinal:
  - "checkpoint registrado"
guarda:
  tipo: nenhum
  motivo: "cmd_checkpoint (ci/fila.py) so confere se a TAR existe na fila (tarefas), nao se ela ja tem evento terminal; ensinar isso a maquina e correcao de codigo em ci/fila.py, fora do alcance de uma entrada de licao"
licao: "python ci/fila.py checkpoint <TAR> grava o evento mesmo com concluida ou cancelada anterior: cmd_checkpoint (linha 2698) so recusa TAR ausente da fila, nunca TAR ja terminal. Checkpoint apos conclusao invalida a leitura da fila e reprova o PR na muralha (PRs 2160 e 2161). Confira o estado com ci/fila.py listar antes de gerar checkpoint."
---

# 516: checkpoint gravado depois do evento de conclusão invalida a fila

**Data:** 26 e 27/09/2026 · **Onde:** `ci/fila.py`, PRs #2160 e #2161, obra
Appmax · **Custo evitado:** dois PRs reprovados na muralha por uma fila que
a própria casa deixou inconsistente.

## Sintoma

`python ci/fila.py checkpoint TAR-NNN ...` grava o evento sem erro nenhum,
mesmo quando essa TAR já tem um evento `concluida` (ou `cancelada`)
anterior. A leitura calculada da fila trata o checkpoint como se fosse um
ponto de retomada de tarefa viva; a muralha reprovou os PRs #2160 e #2161
porque a cadeia de eventos da TAR ficou com um checkpoint depois do
encerramento, sequência que a lógica de estados não espera.

## Causa

`cmd_checkpoint` (`ci/fila.py`, linha 2698) confere apenas se a TAR existe
em `tarefas` (`if tid not in tarefas`); não há checagem do estado calculado
da TAR (concluída, cancelada) antes de escrever o evento. Qualquer sessão
que rode `checkpoint` numa TAR que outra sessão já encerrou entre a leitura
e a escrita (ou por engano, apontando para o número errado) grava uma
sequência que a fila não sabe interpretar.

## Solução

1. Antes de `python ci/fila.py checkpoint <TAR>`, confira o estado atual:
   ```bash
   python ci/fila.py listar
   ```
   TAR já concluída ou cancelada: não grave checkpoint nela.
2. Se o checkpoint já foi gravado por engano, a correção é um evento novo
   (nunca editar o já escrito) que o time da fila decida como tratar; não
   existe hoje um jeito de "desfazer" um checkpoint fora de ordem.
3. **Correção fora do alcance desta entrada:** `cmd_checkpoint` deveria
   recusar checkpoint em TAR com evento terminal, do mesmo jeito que já
   recusa TAR ausente. Isso é mudança de código em `ci/fila.py`, candidata
   a tarefa própria na fila, não algo que uma lição resolva.

## Origem

PRs #2160 e #2161, obra Appmax, sessões de coordenação de 26 e 27/09/2026,
`ci/fila.py` linha 2698 (`cmd_checkpoint`).
