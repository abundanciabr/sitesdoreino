---
schema_version: 2
armadilha: 419
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - fila/tarefas/228-o-repetidor-de-deploy-confere-a-esteira-e-precisa-conferir-a.json
  - ci/rerun_de_deploy.py
guarda:
  tipo: CI
  dono: ci/tests/test_rerun_de_deploy.py
sinal:
  - "TAR-228 continua na fila embora TAR-210 já prove a mesma correção"
licao: Antes de implementar uma tarefa antiga, compare o sintoma e a evidência exigida com tarefas concluídas e seus testes. Se o mecanismo já existe, cancele a duplicata com a prova, em vez de alterar novamente o código.
---

# Uma tarefa duplicada fica aberta depois que a correção já pousou

**Sintoma.** A TAR-228 descrevia que o repetidor de deploy confundia a esteira
com a célula publicada e exigia um teste em que uma célula ausente levasse a
`REPETIR`. A TAR-210 já tinha entregue esse mecanismo em `ci/rerun_de_deploy.py`,
com os testes `test_o_deploy_posterior_que_nao_construiu_a_celula_NAO_a_cobre` e
`test_a_regra_de_parada_vale_TAMBEM_quando_falta_celula`.

**Causa.** A fila não fechou automaticamente a TAR-228 quando a TAR-210 foi
concluída. A tarefa duplicada continuou parecendo trabalho vivo e ocupou uma
posição de prioridade.

**Lição.** A decisão correta é cancelar a TAR-228 como duplicata, citando o PR
que entregou a correção e os testes que provam o comportamento. Uma nova
mudança em `ci/rerun_de_deploy.py` repetiria código já protegido e aumentaria o
risco de divergência entre duas curas.
