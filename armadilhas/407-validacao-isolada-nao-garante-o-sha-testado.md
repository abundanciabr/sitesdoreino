---
schema_version: 2
armadilha: 407
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/pr.py
guarda:
  tipo: nenhum
  motivo: a auditoria identificou a lacuna; nenhum guarda foi acrescentado nesta escrituração
sinal: 'validacao isolada aprova depois de o comando trocar HEAD'
licao: 'Isolar o checkout nao prova a revisao executada. Confira commit e arvore antes e depois de cada comando; alteracao invalida a evidencia atribuida ao SHA original.'
---

# 407: Checkout isolado nao garante a revisao que o comando testou

**Sintoma.** A validacao local termina verde e atribui a prova ao SHA entregue, mas um comando troca o HEAD do checkout isolado para uma base anterior antes de executar os testes.

**Causa.** O isolamento elimina arquivos externos; nao impede que o proprio comando mude a revisao. Exit zero nao demonstra qual codigo foi testado.

**Licao.** A evidencia deve vincular commit e arvore observados antes e depois de cada comando. Uma mudanca de revisao invalida a prova, mesmo com testes verdes.

**Limite da constatacao.** O caso foi reproduzido em validacao local de `ci/pr.py`. Nao demonstra contorno dos checks do GitHub, merge indevido ou alteracao em producao. Esta entrada registra o achado, sem declarar a correcao implementada.
