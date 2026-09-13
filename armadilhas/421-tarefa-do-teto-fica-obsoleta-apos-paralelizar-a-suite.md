---
schema_version: 2
armadilha: 421
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - fila/tarefas/253-o-teto-do-make-ci-nao-cabe-na-maquina-real-do-mantenedor-e-v.json
  - ci/ci.py
guarda:
  tipo: teste
  detector: ci/tests/test_suite_em_paralelo.py
sinal:
  - "TAR-253 ainda descreve estouro embora xdist esteja ligado no testador"
licao: Antes de aumentar um teto fixo, meça o comando atual com as otimizações já incorporadas. A TAR-332 liga -n auto quando xdist existe e reduziu a suíte para menos de 900 segundos; a falha restante precisa ser tratada como ambiente, não escondida como tempo.
---

# O teto da suíte fica obsoleto depois que o testador ganha paralelismo

**Sintoma.** A TAR-253 registrava 5664 segundos para a suíte em série no
Windows dentro do OneDrive, acima do teto de 900 segundos de `ci/ci.py`.

**Conferência atual.** O código já usa `pytest-xdist` com `-n auto` quando a
dependência existe. Nesta bancada, a suíte terminou em 256,8 segundos e saiu
com `FAIL` por `/bin/bash` ausente no WSL, sem estourar o teto e sem virar
`ERROR` de instrumentação.

**Lição.** A correção da classe já está em `armadilhas/332`,
`ci/ci.py::_em_paralelo` e `ci/tests/test_suite_em_paralelo.py`. A TAR-253 é
obsoleta e deve ser cancelada como resolvida. A ausência de `/bin/bash` é um
bloqueio de ambiente diferente e não deve ser mascarada elevando o relógio.
