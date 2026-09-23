# Roteiro de execução dos agentes

Este roteiro usa as fontes que já governam a casa: contrato e progresso vivem
em eventos da fila, estado operacional é calculado por `ci/fila.py`, e fatos
concluídos continuam no livro de ocorrências.

## Iniciar

1. Reconciliar a tarefa ou o pedido:
   `python ci/mapa_de_execucao.py --tar TAR-NNN`
2. Abrir ou retomar a bancada indicada pelo pacote.
3. Pegar a tarefa somente quando ela estiver `na fila`:
   `python ci/fila.py pegar TAR-NNN --quem agent/area/tarefa`

## Registrar contrato

O contrato ativo é um JSON versionado registrado como evento:

`python ci/fila.py contrato TAR-NNN --quem agent/area/tarefa --arquivo contrato.json`

O arquivo precisa declarar objetivo, entregáveis, escopo incluído, não objetivos,
restrições, etapas, critérios de entrada, critérios de aceite, evidências
exigidas, condição de encerramento, limites de autonomia e ações do mantenedor.

## Tratar descobertas

Toda descoberta entra classificada, sem ampliar o plano ativo sozinha:

`python ci/fila.py descoberta TAR-NNN --quem agent/area/tarefa --classificacao C --criterio "..." --detalhe "..." --evidencia "..." --encaminhamento "..."`

Classificações:

- `A`: bloqueio necessário.
- `B`: regressão introduzida.
- `C`: problema preexistente independente.
- `D`: melhoria opcional.
- `E`: mudança material de escopo.

`C` e `D` seguem para backlog ou registro separado. `E` preserva o contrato
anterior e exige decisão antes de virar plano ativo.

## Registrar checkpoint

Checkpoint guarda retomada, não status manual:

`python ci/fila.py checkpoint TAR-NNN --quem agent/area/tarefa --plano "fase 2" --ultimo-avanco "..." --proxima-acao "..." --verificacao "comando e resultado"`

Use antes de interrupção conhecida, depois de marco verificável e ao mudar a
abordagem após tentativas sem avanço.

## Detectar ausência de progresso

Quando uma tentativa não move critério nenhum:

`python ci/fila.py tentativa-sem-progresso TAR-NNN --quem agent/area/tarefa --bloqueio "..." --hipotese "..." --resultado "..."`

A quarta tentativa consecutiva no mesmo bloqueio é recusada. A saída correta é
registrar checkpoint com nova abordagem ou bloquear a tarefa com a menor ação
que destrava:

`python ci/fila.py bloquear TAR-NNN --quem agent/area/tarefa --motivo "..." --espera fila`

## Acompanhar e retomar

Consultar o estado canônico:

`python ci/fila.py listar --ao-vivo --json`

Consultar o pacote de retomada:

`python ci/mapa_de_execucao.py --tar TAR-NNN`

O JSON mostra fase real, dependências, contrato, último checkpoint, descobertas,
tentativas sem progresso, próxima ação e limites do pacote. Snapshot local
declara GitHub, reservas e runtime como não medidos.

## Concluir

Conclusão exige evidência:

`python ci/fila.py concluir TAR-NNN --quem agent/area/tarefa --evidencia "..." --verificado-em AAAA-MM-DD`

Entrega por PR continua usando a submissão e reconciliação existentes. Uma tarefa
com PR submetido não fecha por texto livre.
